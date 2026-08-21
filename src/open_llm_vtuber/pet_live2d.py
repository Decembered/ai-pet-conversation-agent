"""Map pet reactions onto the Live2D assets a model really ships.

The domain layer decides *what happened* (see :mod:`pet_domain`); this module
decides *how it can be shown* with the motions and expressions that exist on
disk. It never invents a motion: when a model has no matching animation the
resolver reports an explicit degradation so the browser can fall back to the
expression, bubble and particle layer instead of silently doing nothing.

The module deliberately depends on the standard library only, so it can be
unit tested without the web stack.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PET_RENDER_SCHEMA_VERSION = "1.0"

#: Semantic tokens used to recognise a native motion for a reaction animation.
#: Matching is done against the motion group name and the motion file/entry
#: name, so a model that ships ``motions/eat_01.motion3.json`` is detected
#: automatically without hard-coding indices.
REACTION_MOTION_TOKENS: dict[str, tuple[str, ...]] = {
    "eat": ("eat", "eating", "feed", "food", "meal"),
    "play": ("play", "playing", "toy", "fun"),
    "clean": ("clean", "bath", "wash", "shower", "bubble"),
    "sleep": ("sleep", "sleeping", "nap", "rest", "zzz"),
}

#: Reasons reported back to the browser and to the tests.
REASON_NATIVE_MOTION = "native_motion"
REASON_NO_MATCHING_MOTION = "no_matching_motion"
REASON_MODEL_UNAVAILABLE = "model_assets_unavailable"
REASON_NO_EXPRESSION = "no_matching_expression"
REASON_NO_REACTION = "no_reaction"


@dataclass(frozen=True, slots=True)
class MotionRef:
    """A motion that exists in the model's ``model3.json``."""

    group: str
    index: int
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"group": self.group, "index": self.index, "name": self.name}


@dataclass(frozen=True, slots=True)
class ExpressionRef:
    """An expression that exists in the model's ``model3.json``."""

    index: int
    name: str

    def to_dict(self) -> dict[str, Any]:
        return {"index": self.index, "name": self.name}


@dataclass(frozen=True, slots=True)
class ReactionRendering:
    """How a reaction should be rendered with the assets that exist."""

    animation: str
    motion: MotionRef | None = None
    expression: ExpressionRef | None = None
    degraded: bool = True
    reason: str = REASON_NO_REACTION
    missing_motion_asset: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PET_RENDER_SCHEMA_VERSION,
            "animation": self.animation,
            "motion": self.motion.to_dict() if self.motion else None,
            "expression": self.expression.to_dict() if self.expression else None,
            "degraded": self.degraded,
            "reason": self.reason,
            "missing_motion_asset": self.missing_motion_asset,
        }


def _motion_name(entry: Mapping[str, Any], fallback_index: int) -> str:
    """Derive a readable motion name from a ``model3.json`` motion entry."""

    declared = entry.get("Name")
    if isinstance(declared, str) and declared.strip():
        return declared.strip()
    file_path = entry.get("File")
    if isinstance(file_path, str) and file_path.strip():
        stem = Path(file_path.strip()).name
        for suffix in (".motion3.json", ".json"):
            if stem.endswith(suffix):
                return stem[: -len(suffix)]
        return stem
    return f"motion_{fallback_index}"


class Live2dReactionResolver:
    """Resolve :class:`~.pet_domain.models.ReactionPlan` hints to real assets.

    The resolver is intentionally forgiving: a missing model directory, an
    unreadable ``model3.json`` or an unknown animation must never break a state
    change, so every failure downgrades to a reported degradation instead of an
    exception.
    """

    def __init__(
        self,
        model_info: Mapping[str, Any] | None = None,
        project_root: Path | str | None = None,
        error: str | None = None,
    ) -> None:
        self.model_info: dict[str, Any] = dict(model_info or {})
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.error = error
        self.model_name: str = str(self.model_info.get("name", "") or "")
        self.emotion_map: dict[str, int] = {
            str(key).lower(): int(value)
            for key, value in (self.model_info.get("emotionMap") or {}).items()
            if isinstance(value, (int, float))
        }
        self.motions: list[MotionRef] = []
        self.expressions: list[str] = []
        self._load_model_assets()

    # ------------------------------------------------------------------
    # construction helpers
    # ------------------------------------------------------------------
    @classmethod
    def from_model_name(
        cls,
        model_name: str,
        model_dict_path: Path | str = "model_dict.json",
        project_root: Path | str | None = None,
    ) -> Live2dReactionResolver:
        """Build a resolver from ``model_dict.json`` without ever raising."""

        root = Path(project_root) if project_root else Path.cwd()
        if not model_name:
            return cls(project_root=root, error="no model name configured")

        dict_path = Path(model_dict_path)
        if not dict_path.is_absolute():
            dict_path = root / dict_path
        try:
            entries = json.loads(dict_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            return cls(project_root=root, error=f"model dictionary unreadable: {exc}")

        if not isinstance(entries, list):
            return cls(project_root=root, error="model dictionary is not a list")

        matched = next(
            (
                entry
                for entry in entries
                if isinstance(entry, Mapping) and entry.get("name") == model_name
            ),
            None,
        )
        if matched is None:
            return cls(
                project_root=root, error=f"{model_name} not found in model dictionary"
            )
        return cls(model_info=matched, project_root=root)

    def _model3_path(self) -> Path | None:
        url = self.model_info.get("url")
        if not isinstance(url, str) or not url.strip():
            return None
        relative = url.strip().lstrip("/")
        return self.project_root / relative

    def _load_model_assets(self) -> None:
        path = self._model3_path()
        if path is None:
            self.error = self.error or "model url missing in model dictionary"
            return
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, UnicodeDecodeError) as exc:
            self.error = f"model3.json unreadable: {exc}"
            return

        references = document.get("FileReferences")
        if not isinstance(references, Mapping):
            self.error = "model3.json has no FileReferences"
            return

        motion_groups = references.get("Motions")
        if isinstance(motion_groups, Mapping):
            for group, entries in motion_groups.items():
                if not isinstance(entries, list):
                    continue
                for index, entry in enumerate(entries):
                    if not isinstance(entry, Mapping):
                        continue
                    self.motions.append(
                        MotionRef(
                            group=str(group),
                            index=index,
                            name=_motion_name(entry, index),
                        )
                    )

        expressions = references.get("Expressions")
        if isinstance(expressions, list):
            for index, entry in enumerate(expressions):
                if isinstance(entry, Mapping):
                    name = entry.get("Name")
                    self.expressions.append(
                        str(name) if name else f"expression_{index}"
                    )

    # ------------------------------------------------------------------
    # capability reporting
    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        """True when at least one real motion or expression was loaded."""

        return bool(self.motions or self.expressions)

    def motion_group_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for motion in self.motions:
            counts[motion.group] = counts.get(motion.group, 0) + 1
        return counts

    def find_motion(self, animation: str) -> MotionRef | None:
        """Return a motion whose group or name matches the animation intent."""

        if not animation:
            return None
        tokens = REACTION_MOTION_TOKENS.get(animation.lower(), (animation.lower(),))
        for motion in self.motions:
            haystack = f"{motion.group} {motion.name}".lower()
            if any(token and token in haystack for token in tokens):
                return motion
        return None

    def find_expression(self, name: str | None) -> ExpressionRef | None:
        """Resolve an emotion label (or raw expression name) to an expression."""

        if not name:
            return None
        label = str(name).strip().lower()
        if not label:
            return None

        index = self.emotion_map.get(label)
        if index is None:
            for position, expression in enumerate(self.expressions):
                if expression.lower() == label:
                    return ExpressionRef(index=position, name=expression)
            return None
        if 0 <= index < len(self.expressions):
            return ExpressionRef(index=index, name=self.expressions[index])
        return None

    def missing_motion_assets(self) -> list[str]:
        """Reaction intents this model still needs art for."""

        if not self.available:
            return sorted(REACTION_MOTION_TOKENS)
        return sorted(
            animation
            for animation in REACTION_MOTION_TOKENS
            if self.find_motion(animation) is None
        )

    @property
    def capabilities(self) -> dict[str, Any]:
        """A compact, secret-free description of what this model can show."""

        return {
            "schema_version": PET_RENDER_SCHEMA_VERSION,
            "model": self.model_name,
            "available": self.available,
            "error": self.error,
            "motion_groups": self.motion_group_counts(),
            "motions": [motion.to_dict() for motion in self.motions],
            "expressions": list(self.expressions),
            "emotion_map": dict(self.emotion_map),
            "missing_motion_assets": self.missing_motion_assets(),
        }

    # ------------------------------------------------------------------
    # resolution
    # ------------------------------------------------------------------
    def resolve(self, reaction: Mapping[str, Any] | None) -> ReactionRendering:
        """Turn a reaction plan into a concrete, honest rendering instruction."""

        if not isinstance(reaction, Mapping):
            return ReactionRendering(animation="", reason=REASON_NO_REACTION)

        animation = str(reaction.get("animation", "") or "")
        fallback = reaction.get("fallback_expression")

        if not self.available:
            return ReactionRendering(
                animation=animation,
                reason=REASON_MODEL_UNAVAILABLE,
                missing_motion_asset=animation or None,
            )

        motion = self.find_motion(animation)
        if motion is not None:
            return ReactionRendering(
                animation=animation,
                motion=motion,
                expression=self.find_expression(fallback),
                degraded=False,
                reason=REASON_NATIVE_MOTION,
            )

        expression = self.find_expression(fallback)
        return ReactionRendering(
            animation=animation,
            expression=expression,
            degraded=True,
            reason=(
                REASON_NO_MATCHING_MOTION
                if expression is not None
                else REASON_NO_EXPRESSION
            ),
            missing_motion_asset=animation or None,
        )


def render_payload(
    reaction: Mapping[str, Any] | None,
    resolver: Live2dReactionResolver | None,
) -> dict[str, Any] | None:
    """Serialise the rendering plan for a reaction, or ``None`` when absent."""

    if not isinstance(reaction, Mapping):
        return None
    if resolver is None:
        return None
    return resolver.resolve(reaction).to_dict()


def decorate_reaction_messages(
    messages: list[dict[str, Any]],
    resolver: Live2dReactionResolver | None,
) -> list[dict[str, Any]]:
    """Attach a ``render`` block to every ``pet_reaction`` message in place.

    Additive, schema v1 compatible: consumers that ignore ``render`` keep
    working exactly as before.
    """

    for message in messages:
        if message.get("type") != "pet_reaction":
            continue
        render = render_payload(message.get("reaction"), resolver)
        if render is not None:
            message["render"] = render
    return messages

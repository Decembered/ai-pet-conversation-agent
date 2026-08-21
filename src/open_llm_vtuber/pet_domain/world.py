"""A small, honest world for the pet: time of day, routine, and behaviour.

Phase E gives the pet a life that keeps running when nobody is looking at it.
Three recoverable behaviours only — resting, studying, playing — decided by an
explicit priority chain instead of by the language model:

    user interaction  >  state alert  >  routine slot  >  idle

The world is persisted, so restarting the app resumes the current event instead
of inventing a new one, and a long absence produces a *summary* rather than a
replay of everything that "happened".

Backgrounds follow the same rule as Live2D motions in :mod:`pet_live2d`: only
files that really exist on disk are offered, and a missing file degrades to a
self-authored gradient instead of a broken image.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

WORLD_SCHEMA_VERSION = "1.0"

BEHAVIORS = ("resting", "studying", "playing")

REASON_USER_INTERACTION = "user_interaction"
REASON_STATE_ALERT = "state_alert"
REASON_ROUTINE = "routine"
REASON_IDLE = "idle"

#: How recently the owner must have interacted for the world to follow them.
USER_INTERACTION_WINDOW = timedelta(minutes=5)

#: A gap longer than this is summarised instead of replayed.
OFFLINE_SUMMARY_THRESHOLD = timedelta(minutes=30)

BEHAVIOR_LABELS = {
    "resting": "休息",
    "studying": "学习",
    "playing": "玩耍",
}

PHASE_LABELS = {
    "morning": "清晨",
    "day": "白天",
    "evening": "傍晚",
    "night": "夜里",
}

#: Interactions the owner can start during each behaviour. The world never
#: blocks care actions — it only says what fits the moment.
BEHAVIOR_INTERACTIONS = {
    "resting": ("feed_pet", "clean_pet", "put_pet_to_sleep", "play_with_pet"),
    "studying": ("feed_pet", "clean_pet", "play_with_pet"),
    "playing": ("feed_pet", "clean_pet", "play_with_pet"),
}

#: Background candidates shipped with the upstream project. They are local
#: assets (``backgrounds/`` is git-ignored), so availability is always checked.
BACKGROUND_CANDIDATES = {
    ("resting", "morning"): "room-interior-illustration.jpeg",
    ("resting", "day"): "room-interior-illustration.jpeg",
    ("resting", "evening"): "ceiling-window-room-night.jpeg",
    ("resting", "night"): "ceiling-window-room-night.jpeg",
    ("studying", "morning"): "lernado-diff-classroom-center.jpeg",
    ("studying", "day"): "lernado-diff-classroom-center.jpeg",
    ("studying", "evening"): "computer-room-illustration.jpeg",
    ("studying", "night"): "computer-room-illustration.jpeg",
    ("playing", "morning"): "mountain-range-illustration.jpeg",
    ("playing", "day"): "mountain-range-illustration.jpeg",
    ("playing", "evening"): "cartoon-night-landscape-moon.jpeg",
    ("playing", "night"): "night-scene-cartoon-moon.jpeg",
}

#: Always-available fallback so the world still changes visibly on a fresh
#: clone, where the ignored ``backgrounds/`` directory may be empty.
PHASE_GRADIENTS = {
    "morning": "linear-gradient(160deg, #ffd8a8 0%, #ffe9c8 45%, #cfe3ff 100%)",
    "day": "linear-gradient(160deg, #bfe0ff 0%, #e8f2ff 50%, #fff4d6 100%)",
    "evening": "linear-gradient(160deg, #f6a37c 0%, #b06a8f 55%, #4a4a7d 100%)",
    "night": "linear-gradient(160deg, #1b2340 0%, #2a3358 50%, #46406b 100%)",
}

#: Subtle colour wash applied over whichever background is in use.
PHASE_TINTS = {
    "morning": "rgba(255, 205, 140, 0.16)",
    "day": "rgba(255, 255, 255, 0.05)",
    "evening": "rgba(255, 138, 92, 0.18)",
    "night": "rgba(28, 38, 80, 0.34)",
}


def _local_now() -> datetime:
    """Timezone-aware local time; the pet lives in the user's day, not in UTC."""

    return datetime.now().astimezone()


@dataclass(frozen=True, slots=True)
class DayMoment:
    """Where the pet is in its day."""

    moment: datetime
    phase: str

    @property
    def label(self) -> str:
        return PHASE_LABELS.get(self.phase, self.phase)

    def to_dict(self) -> dict[str, Any]:
        return {
            "at": self.moment.isoformat(),
            "date": self.moment.date().isoformat(),
            "hour": self.moment.hour,
            "phase": self.phase,
            "phase_label": self.label,
        }


class WorldClock:
    """Maps real local time onto the pet's day phases."""

    def __init__(self, clock: Callable[[], datetime] = _local_now) -> None:
        self.clock = clock

    def now(self) -> datetime:
        value = self.clock()
        return value if value.tzinfo else value.astimezone()

    @staticmethod
    def phase_for_hour(hour: int) -> str:
        if 5 <= hour < 11:
            return "morning"
        if 11 <= hour < 18:
            return "day"
        if 18 <= hour < 22:
            return "evening"
        return "night"

    def moment(self, at: datetime | None = None) -> DayMoment:
        value = at or self.now()
        if value.tzinfo is None:
            value = value.astimezone()
        return DayMoment(moment=value, phase=self.phase_for_hour(value.hour))


@dataclass(frozen=True, slots=True)
class RoutineSlot:
    """One controlled slot of the pet's day."""

    behavior: str
    start_hour: int
    end_hour: int  # exclusive; 24 means "until midnight"

    def contains(self, hour: int) -> bool:
        return self.start_hour <= hour < self.end_hour


class RoutineScheduler:
    """A deterministic daily routine — same day, same plan, no randomness."""

    DEFAULT_SLOTS: tuple[RoutineSlot, ...] = (
        RoutineSlot("resting", 0, 7),
        RoutineSlot("resting", 7, 9),
        RoutineSlot("studying", 9, 12),
        RoutineSlot("playing", 12, 14),
        RoutineSlot("studying", 14, 18),
        RoutineSlot("playing", 18, 21),
        RoutineSlot("resting", 21, 24),
    )

    def __init__(self, slots: tuple[RoutineSlot, ...] | None = None) -> None:
        self.slots = slots or self.DEFAULT_SLOTS

    def slot_for(self, moment: datetime) -> RoutineSlot:
        for slot in self.slots:
            if slot.contains(moment.hour):
                return slot
        return RoutineSlot("resting", moment.hour, moment.hour + 1)

    def slot_end(self, moment: datetime) -> datetime:
        slot = self.slot_for(moment)
        start_of_day = moment.replace(hour=0, minute=0, second=0, microsecond=0)
        return start_of_day + timedelta(hours=slot.end_hour)

    def behaviors_between(self, start: datetime, end: datetime) -> list[str]:
        """Behaviours the routine would have covered in a closed period."""

        if end <= start:
            return []
        seen: list[str] = []
        cursor = start.replace(minute=0, second=0, microsecond=0)
        guard = 0
        while cursor < end and guard < 24 * 14:
            behavior = self.slot_for(cursor).behavior
            if not seen or seen[-1] != behavior:
                seen.append(behavior)
            cursor += timedelta(hours=1)
            guard += 1
        return seen


@dataclass(frozen=True, slots=True)
class BehaviorDecision:
    """What the pet should be doing, and why."""

    behavior: str
    reason: str
    note: str = ""
    expected_end_at: datetime | None = None


class BehaviorPlanner:
    """Priority chain: owner first, then needs, then routine, then idle."""

    def __init__(
        self,
        scheduler: RoutineScheduler | None = None,
        user_window: timedelta = USER_INTERACTION_WINDOW,
    ) -> None:
        self.scheduler = scheduler or RoutineScheduler()
        self.user_window = user_window

    # Mapping from a just-performed care action to what the world shows.
    ACTIVITY_BEHAVIOR = {
        "playing": ("playing", "主人正在陪我玩"),
        "eating": ("resting", "刚刚吃过东西，慢慢消化"),
        "bathing": ("resting", "刚洗完澡，暖烘烘地待着"),
        "sleeping": ("resting", "正在睡觉"),
        "tired": ("resting", "有点累了"),
    }

    def decide(self, state: Any, moment: DayMoment) -> BehaviorDecision:
        now = moment.moment
        slot_end = self.scheduler.slot_end(now)

        interaction = self._from_recent_interaction(state, now)
        if interaction is not None:
            return interaction

        alert = self._from_state_alert(state, now)
        if alert is not None:
            return alert

        slot = self.scheduler.slot_for(now)
        return BehaviorDecision(
            behavior=slot.behavior,
            reason=REASON_ROUTINE,
            note=f"{PHASE_LABELS.get(moment.phase, '')}的日程：{BEHAVIOR_LABELS[slot.behavior]}",
            expected_end_at=slot_end,
        )

    def _from_recent_interaction(
        self, state: Any, now: datetime
    ) -> BehaviorDecision | None:
        activity = getattr(state, "activity", None)
        updated_at = getattr(state, "last_updated_at", None)
        if not activity or updated_at is None:
            return None
        if activity not in self.ACTIVITY_BEHAVIOR:
            return None
        if now - updated_at.astimezone(now.tzinfo) > self.user_window:
            return None
        behavior, note = self.ACTIVITY_BEHAVIOR[activity]
        return BehaviorDecision(
            behavior=behavior,
            reason=REASON_USER_INTERACTION,
            note=note,
            expected_end_at=now + self.user_window,
        )

    def _from_state_alert(self, state: Any, now: datetime) -> BehaviorDecision | None:
        alerts = (
            (getattr(state, "hunger", 0) >= 80, "肚子饿得咕咕叫，想吃点东西"),
            (getattr(state, "energy", 100) <= 20, "精力见底了，需要好好休息"),
            (getattr(state, "cleanliness", 100) <= 25, "身上有点脏，想洗个澡"),
            (getattr(state, "mood", 100) <= 20, "心情有点低落，想被陪一会儿"),
        )
        for triggered, note in alerts:
            if triggered:
                return BehaviorDecision(
                    behavior="resting",
                    reason=REASON_STATE_ALERT,
                    note=note,
                    expected_end_at=now + timedelta(minutes=20),
                )
        return None


@dataclass(slots=True)
class WorldEvent:
    """One stretch of the pet's life, persisted so it survives a restart."""

    event_id: str
    user_id: str
    behavior: str
    reason: str
    started_at: datetime
    expected_end_at: datetime
    day_phase: str
    note: str = ""
    interactions: tuple[str, ...] = field(default_factory=tuple)

    def is_active(self, now: datetime) -> bool:
        return self.started_at <= now < self.expected_end_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "user_id": self.user_id,
            "behavior": self.behavior,
            "behavior_label": BEHAVIOR_LABELS.get(self.behavior, self.behavior),
            "reason": self.reason,
            "note": self.note,
            "started_at": self.started_at.isoformat(),
            "expected_end_at": self.expected_end_at.isoformat(),
            "day_phase": self.day_phase,
            "day_phase_label": PHASE_LABELS.get(self.day_phase, self.day_phase),
            "interactions": list(self.interactions),
        }


def background_for(
    behavior: str,
    phase: str,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    """Pick a background that exists, or fall back to a generated gradient."""

    root = Path(project_root) if project_root else Path.cwd()
    file_name = BACKGROUND_CANDIDATES.get((behavior, phase))
    available = bool(file_name) and (root / "backgrounds" / file_name).is_file()
    return {
        "phase": phase,
        "behavior": behavior,
        "file": file_name if available else None,
        "url": f"/bg/{file_name}" if available else None,
        "available": available,
        "gradient": PHASE_GRADIENTS.get(phase, PHASE_GRADIENTS["day"]),
        "tint": PHASE_TINTS.get(phase, PHASE_TINTS["day"]),
        "missing_asset": None if available else file_name,
    }


class WorldService:
    """Plan, persist and resume the pet's current world event."""

    def __init__(
        self,
        repository: Any,
        clock: WorldClock | None = None,
        scheduler: RoutineScheduler | None = None,
        planner: BehaviorPlanner | None = None,
        project_root: Path | str | None = None,
    ) -> None:
        self.repository = repository
        self.clock = clock or WorldClock()
        self.scheduler = scheduler or RoutineScheduler()
        self.planner = planner or BehaviorPlanner(self.scheduler)
        self.project_root = Path(project_root) if project_root else Path.cwd()

    def current_world(self, user_id: str, state: Any) -> dict[str, Any]:
        moment = self.clock.moment()
        now = moment.moment
        decision = self.planner.decide(state, moment)
        stored = self._load_current(user_id)

        summary = self._offline_summary(stored, now)
        event = self._resume_or_start(user_id, stored, decision, moment)

        return {
            "schema_version": WORLD_SCHEMA_VERSION,
            "now": moment.to_dict(),
            "event": event.to_dict(),
            "background": background_for(
                event.behavior, event.day_phase, self.project_root
            ),
            "offline_summary": summary,
            "routine": [
                {
                    "behavior": slot.behavior,
                    "behavior_label": BEHAVIOR_LABELS.get(slot.behavior, slot.behavior),
                    "start_hour": slot.start_hour,
                    "end_hour": slot.end_hour,
                }
                for slot in self.scheduler.slots
            ],
        }

    # ------------------------------------------------------------------
    # persistence helpers
    # ------------------------------------------------------------------
    def _load_current(self, user_id: str) -> WorldEvent | None:
        row = self.repository.get_latest_world_event(user_id)
        if not row:
            return None
        try:
            return WorldEvent(
                event_id=row["event_id"],
                user_id=row["user_id"],
                behavior=row["behavior"],
                reason=row["reason"],
                started_at=datetime.fromisoformat(row["started_at"]),
                expected_end_at=datetime.fromisoformat(row["expected_end_at"]),
                day_phase=row.get("day_phase", "day"),
                note=row.get("note", ""),
                interactions=tuple(row.get("interactions") or ()),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _resume_or_start(
        self,
        user_id: str,
        stored: WorldEvent | None,
        decision: BehaviorDecision,
        moment: DayMoment,
    ) -> WorldEvent:
        now = moment.moment
        if (
            stored
            and stored.is_active(now)
            and stored.behavior == decision.behavior
            and stored.reason == decision.reason
        ):
            # Restarting the app must not restart the pet's afternoon.
            return stored

        event = WorldEvent(
            event_id=str(uuid4()),
            user_id=user_id,
            behavior=decision.behavior,
            reason=decision.reason,
            started_at=now,
            expected_end_at=decision.expected_end_at or (now + timedelta(hours=1)),
            day_phase=moment.phase,
            note=decision.note,
            interactions=tuple(BEHAVIOR_INTERACTIONS.get(decision.behavior, ())),
        )
        self.repository.save_world_event(
            event_id=event.event_id,
            user_id=event.user_id,
            behavior=event.behavior,
            reason=event.reason,
            started_at=event.started_at.isoformat(),
            expected_end_at=event.expected_end_at.isoformat(),
            payload={
                "day_phase": event.day_phase,
                "note": event.note,
                "interactions": list(event.interactions),
            },
        )
        return event

    def _offline_summary(self, stored: WorldEvent | None, now: datetime) -> str | None:
        """Summarise a long absence instead of replaying it."""

        if stored is None:
            return None
        gap = now - stored.expected_end_at.astimezone(now.tzinfo)
        if gap < OFFLINE_SUMMARY_THRESHOLD:
            return None

        behaviors = self.scheduler.behaviors_between(stored.expected_end_at, now)
        if not behaviors:
            return None
        hours = max(1, int(gap.total_seconds() // 3600))
        described = "、".join(BEHAVIOR_LABELS.get(item, item) for item in behaviors[:3])
        return f"你不在的大约 {hours} 小时里，小光按日程{described}了一阵子。"

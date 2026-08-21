"""Privacy-preserving presence events and proactive interaction decisions."""

from dataclasses import dataclass
from typing import Literal

PresenceEventType = Literal["entered", "left", "smile", "idle"]


@dataclass(frozen=True, slots=True)
class PresenceEvent:
    """Describe a camera-derived event without storing an image or identity."""

    event_type: PresenceEventType
    observed_at: float


@dataclass(frozen=True, slots=True)
class ProactiveDecision:
    """Represent whether the pet should proactively speak or act."""

    should_trigger: bool
    message: str
    action: str | None = None


class ProactiveScheduler:
    """Apply cooldowns to low-risk presence events before triggering the pet."""

    def __init__(self, cooldown_seconds: float = 300.0) -> None:
        self.cooldown_seconds = cooldown_seconds
        self._last_trigger_at: dict[PresenceEventType, float] = {}

    def evaluate(self, event: PresenceEvent) -> ProactiveDecision:
        """Turn a presence event into a cooldown-aware action decision."""
        last_trigger = self._last_trigger_at.get(event.event_type)
        if (
            last_trigger is not None
            and event.observed_at - last_trigger < self.cooldown_seconds
        ):
            return ProactiveDecision(False, "")

        messages: dict[PresenceEventType, tuple[str, str | None]] = {
            "entered": ("欢迎回来！我刚好想和你聊两句。", "wave"),
            "left": ("我会安静等你回来，路上注意安全。", "wave"),
            "smile": ("看到你笑，我也开心起来啦！", "happy"),
            "idle": ("要不要休息一下，或者让我陪你聊会儿？", "nuzzle"),
        }
        message, action = messages[event.event_type]
        self._last_trigger_at[event.event_type] = event.observed_at
        return ProactiveDecision(True, message, action)

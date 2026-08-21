"""Business rules for querying and caring for the SLAI Pet.

Every numeric rule for a pet action lives here: the HTTP routes, the MCP tools
and the browser must never invent their own deltas.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from .models import PetActionResult, PetState, ReactionPlan, utc_now
from .repository import PetStateRepository


class PetStateService:
    """Own pet state, elapsed-time decay, and idempotent actions."""

    def __init__(
        self,
        repository: PetStateRepository,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.repository = repository
        self.clock = clock

    def get_pet_state(self, user_id: str = "default") -> PetState:
        now = self._now()
        state = self.repository.get_state(user_id)
        if state is None:
            state = PetState(user_id=user_id, last_updated_at=now)
            self.repository.save_state(state)
            return state

        decayed = self._apply_elapsed_time(state, now)
        self.repository.save_state(decayed)
        return decayed

    def feed_pet(
        self,
        user_id: str = "default",
        food: str = "小鱼干",
        request_id: str | None = None,
    ) -> PetActionResult:
        """Feed the pet once: hunger drops, mood and intimacy rise."""

        def mutate(state: PetState) -> None:
            state.hunger -= 30
            state.mood += 8
            state.intimacy += 3
            state.energy += 2
            state.activity = "eating"
            state.location = "pet_home"
            state.experience += 2

        return self._commit_action(
            user_id=user_id,
            action="feed_pet",
            event_type="PetFed",
            request_id=request_id,
            mutate=mutate,
            reaction=ReactionPlan(
                kind="feed_success",
                animation="eat",
                fallback_expression="joy",
                bubble=f"好香！谢谢你的{food}！",
                particle="fish",
                sound="feed_chime",
                duration_ms=3200,
            ),
            message=f"宠物吃下了{food}，饥饿度下降，心情和亲密度上升。",
            duplicate_message=f"这次喂食已经完成过了，不会重复吃掉{food}。",
            extra_payload={"food": food},
        )

    def play_with_pet(
        self,
        user_id: str = "default",
        game: str = "追激光笔",
        request_id: str | None = None,
    ) -> PetActionResult:
        """Play once: energy is spent, mood, intimacy and experience rise."""

        def mutate(state: PetState) -> None:
            state.energy -= 12
            state.mood += 12
            state.intimacy += 5
            state.experience += 3
            state.activity = "playing"
            state.location = "pet_home"

        return self._commit_action(
            user_id=user_id,
            action="play_with_pet",
            event_type="PetPlayed",
            request_id=request_id,
            mutate=mutate,
            reaction=ReactionPlan(
                kind="play_success",
                animation="play",
                fallback_expression="joy",
                bubble=f"{game}好好玩！再来一次嘛～",
                particle="star",
                sound="play_chime",
                duration_ms=3000,
            ),
            message=f"宠物和你玩了{game}，精力下降，心情和亲密度上升。",
            duplicate_message=f"这次{game}已经玩过了，不会重复记一次。",
            extra_payload={"game": game},
        )

    def clean_pet(
        self,
        user_id: str = "default",
        method: str = "洗澡",
        request_id: str | None = None,
    ) -> PetActionResult:
        """Clean the pet once: cleanliness rises, mood improves slightly."""

        def mutate(state: PetState) -> None:
            state.cleanliness += 35
            state.mood += 4
            state.intimacy += 1
            state.energy -= 3
            state.experience += 1
            state.activity = "bathing"
            state.location = "pet_home"

        return self._commit_action(
            user_id=user_id,
            action="clean_pet",
            event_type="PetCleaned",
            request_id=request_id,
            mutate=mutate,
            reaction=ReactionPlan(
                kind="clean_success",
                animation="clean",
                fallback_expression="joy",
                bubble=f"{method}完毕，香喷喷的！",
                particle="bubble",
                sound="clean_chime",
                duration_ms=3200,
            ),
            message=f"宠物完成了{method}，清洁度上升。",
            duplicate_message=f"这次{method}已经完成过了，不会重复清洁。",
            extra_payload={"method": method},
        )

    def put_pet_to_sleep(
        self,
        user_id: str = "default",
        request_id: str | None = None,
    ) -> PetActionResult:
        """Send the pet to sleep: energy then recovers while time passes."""

        def mutate(state: PetState) -> None:
            state.energy += 10
            state.health += 2
            state.mood += 2
            state.experience += 1
            state.activity = "sleeping"
            state.location = "pet_home"

        return self._commit_action(
            user_id=user_id,
            action="put_pet_to_sleep",
            event_type="PetSlept",
            request_id=request_id,
            mutate=mutate,
            reaction=ReactionPlan(
                kind="sleep_success",
                animation="sleep",
                fallback_expression="neutral",
                bubble="Zzz… 我先睡一会儿，晚安～",
                particle="zzz",
                sound="sleep_chime",
                duration_ms=3600,
            ),
            message="宠物进入睡眠，精力会随着时间逐步恢复。",
            duplicate_message="宠物已经因为这次请求睡下了，不会重复记录。",
        )

    def _commit_action(
        self,
        *,
        user_id: str,
        action: str,
        event_type: str,
        request_id: str | None,
        mutate: Callable[[PetState], None],
        reaction: ReactionPlan,
        message: str,
        duplicate_message: str,
        extra_payload: dict[str, object] | None = None,
    ) -> PetActionResult:
        """Apply one action atomically, idempotently and with audit events.

        Retrying with the same ``request_id`` never changes the state twice and
        never replays a reaction, which is what keeps the LLM, the HTTP button
        and the MCP process from double-counting the same intent.
        """

        request_id = request_id or str(uuid4())
        existing = self.repository.get_event_by_request(request_id)
        if existing:
            return PetActionResult(
                action=action,
                state=self.get_pet_state(user_id),
                message=duplicate_message,
                request_id=request_id,
                event_id=existing["event_id"],
                duplicate=True,
            )

        state = self.get_pet_state(user_id)
        before = state.to_dict()
        mutate(state)
        state.last_updated_at = self._now()
        state.normalize()
        after = state.to_dict()
        changes = self._state_changes(before, after)

        event_id = str(uuid4())
        payload: dict[str, object] = {
            "action": action,
            "state_after": after,
            "changes": changes,
            "reaction": reaction.to_dict(),
        }
        if extra_payload:
            payload.update(extra_payload)
        self.repository.save_state_with_event(
            state,
            event_id=event_id,
            request_id=request_id,
            event_type=event_type,
            payload=payload,
        )
        return PetActionResult(
            action=action,
            state=state,
            message=message,
            request_id=request_id,
            event_id=event_id,
            changes=changes,
            reaction=reaction,
        )

    @staticmethod
    def _state_changes(
        before: dict[str, object], after: dict[str, object]
    ) -> dict[str, dict[str, object]]:
        """Return public state deltas used by UI animation and event consumers."""

        fields = (
            "hunger",
            "energy",
            "health",
            "mood",
            "cleanliness",
            "intimacy",
            "location",
            "activity",
            "level",
            "experience",
            "maturity",
        )
        changes: dict[str, dict[str, object]] = {}
        for field in fields:
            previous = before[field]
            current = after[field]
            if previous == current:
                continue
            change: dict[str, object] = {"before": previous, "after": current}
            if isinstance(previous, (int, float)) and isinstance(current, (int, float)):
                change["delta"] = round(current - previous, 2)
            changes[field] = change
        return changes

    def _apply_elapsed_time(self, state: PetState, now: datetime) -> PetState:
        elapsed_seconds = max(0.0, (now - state.last_updated_at).total_seconds())
        elapsed_hours = min(elapsed_seconds / 3600.0, 72.0)
        if elapsed_hours < 0.01:
            return replace(state, last_updated_at=now)

        if state.activity == "sleeping":
            # Sleeping is a persisted behaviour, not a one-off animation: the
            # pet keeps recovering while the app is closed.
            state.energy += 6.0 * elapsed_hours
            state.health += 0.5 * elapsed_hours
            state.mood += 1.0 * elapsed_hours
            state.hunger += 1.0 * elapsed_hours
            state.cleanliness -= 0.2 * elapsed_hours
            if state.energy >= 100:
                state.activity = "resting"
        else:
            state.hunger += 2.0 * elapsed_hours
            state.energy -= 1.0 * elapsed_hours
            state.cleanliness -= 0.5 * elapsed_hours
            if state.hunger >= 80:
                state.mood -= 1.0 * elapsed_hours
            if state.energy <= 20:
                state.activity = "tired"
        state.last_updated_at = now
        state.normalize()
        return state

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

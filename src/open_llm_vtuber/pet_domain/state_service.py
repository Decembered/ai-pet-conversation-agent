"""Business rules for querying and feeding the initial SLAI Pet."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from .models import PetActionResult, PetState, utc_now
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
        request_id = request_id or str(uuid4())
        existing = self.repository.get_event_by_request(request_id)
        if existing:
            return PetActionResult(
                action="feed_pet",
                state=self.get_pet_state(user_id),
                message=f"这次喂食已经完成过了，不会重复吃掉{food}。",
                request_id=request_id,
                event_id=existing["event_id"],
                duplicate=True,
            )

        state = self.get_pet_state(user_id)
        state.hunger -= 30
        state.mood += 8
        state.intimacy += 3
        state.energy += 2
        state.activity = "eating"
        state.location = "pet_home"
        state.experience += 2
        state.last_updated_at = self._now()
        state.normalize()

        event_id = str(uuid4())
        self.repository.save_state_with_event(
            state,
            event_id=event_id,
            request_id=request_id,
            event_type="PetFed",
            payload={"food": food, "state_after": state.to_dict()},
        )
        return PetActionResult(
            action="feed_pet",
            state=state,
            message=f"宠物吃下了{food}，饥饿度下降，心情和亲密度上升。",
            request_id=request_id,
            event_id=event_id,
        )

    def _apply_elapsed_time(self, state: PetState, now: datetime) -> PetState:
        elapsed_seconds = max(0.0, (now - state.last_updated_at).total_seconds())
        elapsed_hours = min(elapsed_seconds / 3600.0, 72.0)
        if elapsed_hours < 0.01:
            return replace(state, last_updated_at=now)

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

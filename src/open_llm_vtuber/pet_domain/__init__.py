"""Core SLAI Pet domain services.

The domain package owns persistent pet state and business rules. LLMs and
frontends must use these services (normally through tools) instead of inventing
or directly mutating state.
"""

from .models import PetActionResult, PetState, ReactionPlan
from .repository import PetStateRepository
from .state_service import PetStateService
from .world import (
    BehaviorPlanner,
    RoutineScheduler,
    WorldClock,
    WorldEvent,
    WorldService,
)

__all__ = [
    "PetActionResult",
    "PetState",
    "ReactionPlan",
    "PetStateRepository",
    "PetStateService",
    "BehaviorPlanner",
    "RoutineScheduler",
    "WorldClock",
    "WorldEvent",
    "WorldService",
]

"""Core SLAI Pet domain services.

The domain package owns persistent pet state and business rules. LLMs and
frontends must use these services (normally through tools) instead of inventing
or directly mutating state.
"""

from .models import PetActionResult, PetState
from .repository import PetStateRepository
from .state_service import PetStateService

__all__ = [
    "PetActionResult",
    "PetState",
    "PetStateRepository",
    "PetStateService",
]

"""Data models for the SLAI Pet state vertical slice."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    """Clamp and round a pet attribute to the public 0-100 range."""

    return round(max(minimum, min(maximum, value)), 2)


@dataclass(slots=True)
class PetState:
    """Server-owned source of truth for a pet's current basic state.

    ``hunger`` represents how hungry the pet is, so feeding decreases it.
    All numeric attributes are kept in the inclusive 0-100 range.
    """

    user_id: str = "default"
    hunger: float = 25.0
    energy: float = 80.0
    health: float = 100.0
    mood: float = 75.0
    cleanliness: float = 80.0
    intimacy: float = 10.0
    location: str = "pet_home"
    activity: str = "resting"
    level: int = 1
    experience: int = 0
    maturity: float = 5.0
    last_updated_at: datetime = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.last_updated_at is None:
            self.last_updated_at = utc_now()
        elif self.last_updated_at.tzinfo is None:
            self.last_updated_at = self.last_updated_at.replace(tzinfo=timezone.utc)
        self.normalize()

    def normalize(self) -> None:
        """Enforce public field bounds after every business operation."""

        self.hunger = clamp(self.hunger)
        self.energy = clamp(self.energy)
        self.health = clamp(self.health)
        self.mood = clamp(self.mood)
        self.cleanliness = clamp(self.cleanliness)
        self.intimacy = clamp(self.intimacy)
        self.maturity = clamp(self.maturity)
        self.level = max(1, int(self.level))
        self.experience = max(0, int(self.experience))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["last_updated_at"] = self.last_updated_at.isoformat()
        return data

    @classmethod
    def from_row(cls, row: Any) -> PetState:
        return cls(
            user_id=row["user_id"],
            hunger=row["hunger"],
            energy=row["energy"],
            health=row["health"],
            mood=row["mood"],
            cleanliness=row["cleanliness"],
            intimacy=row["intimacy"],
            location=row["location"],
            activity=row["activity"],
            level=row["level"],
            experience=row["experience"],
            maturity=row["maturity"],
            last_updated_at=datetime.fromisoformat(row["last_updated_at"]),
        )


@dataclass(slots=True)
class PetActionResult:
    """Auditable result returned by a state-changing pet action."""

    action: str
    state: PetState
    message: str
    request_id: str
    event_id: str
    duplicate: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": True,
            "action": self.action,
            "message": self.message,
            "request_id": self.request_id,
            "event_id": self.event_id,
            "duplicate": self.duplicate,
            "state": self.state.to_dict(),
        }

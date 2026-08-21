"""Application-level coordinator for the pet domain services."""

from dataclasses import dataclass
from pathlib import Path
import time

from .artifacts import ArtifactService
from .memory import MemoryRecord, MemoryStore
from .personas import PersonaId, PersonaProfile, build_system_prompt, get_persona
from .proactivity import PresenceEvent, ProactiveDecision, ProactiveScheduler
from .state import ActionResult, PetState, PetWorldService


@dataclass(frozen=True, slots=True)
class PetTextResponse:
    """Represent a local response for state and action intents."""

    message: str
    state: PetState
    action: ActionResult | None = None


class PetRuntime:
    """Coordinate state, memory, persona, skills and proactive events."""

    def __init__(
        self,
        db_path: str | Path = Path("data/pet.sqlite3"),
        artifact_root: str | Path = Path("data/artifacts"),
        persona_id: PersonaId = "sunny",
    ) -> None:
        self.world = PetWorldService(db_path)
        self.memory = MemoryStore(db_path)
        self.artifacts = ArtifactService(db_path, artifact_root)
        self.scheduler = ProactiveScheduler()
        self.persona: PersonaProfile = get_persona(persona_id)

    def state_summary(self, pet_id: str) -> str:
        """Return a compact state string suitable for system prompt injection."""
        state = self.world.get_state(pet_id)
        return (
            f"饥饿 {state.hunger:.0f}/100，精力 {state.energy:.0f}/100，"
            f"健康 {state.health:.0f}/100，心情 {state.mood:.0f}/100，"
            f"亲密度 {state.intimacy:.0f}/100，等级 {state.level}"
        )

    def build_prompt(self, pet_id: str, memory_query: str = "") -> str:
        """Build a persona prompt with current state and recalled facts."""
        memories = (
            self.memory.recall(pet_id, memory_query, limit=5) if memory_query else []
        )
        memory_summary = "；".join(
            f"{record.key}={record.value}" for record in memories
        )
        return build_system_prompt(
            self.persona, self.state_summary(pet_id), memory_summary
        )

    def respond_to_text(self, pet_id: str, text: str) -> PetTextResponse | None:
        """Handle local state intents before the remote LLM is called."""
        action = self.world.infer_action(text)
        if action is not None:
            result = self.world.perform_action(pet_id, action)
            return PetTextResponse(
                f"{result.message} {self.persona.catchphrase}", result.state, result
            )
        if self.world.is_state_question(text):
            state = self.world.get_state(pet_id)
            return PetTextResponse(
                f"我现在的状态是：{self._state_text(state)}。{self.persona.catchphrase}",
                state,
            )
        return None

    def remember(
        self, pet_id: str, key: str, value: str, importance: float = 0.5
    ) -> MemoryRecord:
        """Store one owner fact for later sessions."""
        return self.memory.remember(pet_id, key, value, importance)

    def observe(
        self, event_type: str, observed_at: float | None = None
    ) -> ProactiveDecision:
        """Evaluate a camera presence signal without retaining camera data."""
        event = PresenceEvent(
            event_type, observed_at if observed_at is not None else time.time()
        )
        return self.scheduler.evaluate(event)

    def switch_persona(self, persona_id: PersonaId) -> PersonaProfile:
        """Switch the active persona package."""
        self.persona = get_persona(persona_id)
        return self.persona

    @staticmethod
    def _state_text(state: PetState) -> str:
        return (
            f"饥饿{state.hunger:.0f}，精力{state.energy:.0f}，健康{state.health:.0f}，"
            f"心情{state.mood:.0f}，亲密度{state.intimacy:.0f}，等级{state.level}"
        )

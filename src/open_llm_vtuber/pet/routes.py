"""HTTP endpoints for the AI pet domain API."""

from dataclasses import asdict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .personas import PersonaId, list_personas
from .runtime import PetRuntime
from .state import PetAction


class ActionRequest(BaseModel):
    """Request one state-changing pet action."""

    pet_id: str = Field(default="demo", min_length=1, max_length=80)
    action: PetAction


class MemoryRequest(BaseModel):
    """Request one durable owner fact."""

    pet_id: str = Field(default="demo", min_length=1, max_length=80)
    key: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=500)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


class ArtifactRequest(BaseModel):
    """Request a local writing or drawing artifact."""

    pet_id: str = Field(default="demo", min_length=1, max_length=80)
    title: str = Field(default="宠物作品", max_length=80)
    recipient: str = Field(default="主人", max_length=80)
    content: str = Field(default="", max_length=5000)


class ObserveRequest(BaseModel):
    """Request evaluation of a privacy-preserving camera event."""

    event_type: str = Field(min_length=1, max_length=20)
    observed_at: float | None = None


class TextRequest(BaseModel):
    """Request a local pet response for the offline demo path."""

    pet_id: str = Field(default="demo", min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=1000)


def init_pet_routes(runtime: PetRuntime) -> APIRouter:
    """Create the versioned pet API router."""
    router = APIRouter(prefix="/api/pet", tags=["pet"])

    @router.get("/state")
    async def get_state(pet_id: str = "demo"):
        return runtime.world.get_state(pet_id)

    @router.post("/respond")
    async def respond(request: TextRequest):
        response = runtime.respond_to_text(request.pet_id, request.text)
        if response is None:
            return {
                "handled": False,
                "message": "这句话需要连接 LLM 才能继续聊，我先陪你看看状态。",
                "state": runtime.world.get_state(request.pet_id),
            }
        return {"handled": True, **asdict(response)}

    @router.post("/actions")
    async def perform_action(request: ActionRequest):
        return runtime.world.perform_action(request.pet_id, request.action)

    @router.post("/memory")
    async def remember(request: MemoryRequest):
        return runtime.remember(
            request.pet_id, request.key, request.value, request.importance
        )

    @router.get("/memory")
    async def recall(pet_id: str = "demo", query: str = "", limit: int = 5):
        return runtime.memory.recall(pet_id, query, limit)

    @router.post("/skills/letter")
    async def write_letter(request: ArtifactRequest):
        if not request.content.strip():
            raise HTTPException(status_code=400, detail="content cannot be empty")
        return _artifact_payload(
            runtime.artifacts.write_letter(
                request.pet_id, request.recipient, request.content, request.title
            )
        )

    @router.post("/skills/drawing")
    async def create_drawing(request: ArtifactRequest):
        caption = request.content or request.title
        return _artifact_payload(
            runtime.artifacts.create_drawing(request.pet_id, caption, request.title)
        )

    @router.get("/artifacts")
    async def list_artifacts(pet_id: str = "demo", limit: int = 20):
        return [
            _artifact_payload(artifact)
            for artifact in runtime.artifacts.list_artifacts(pet_id, limit)
        ]

    @router.post("/observe")
    async def observe(request: ObserveRequest):
        try:
            decision = runtime.observe(request.event_type, request.observed_at)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return decision

    @router.get("/proactive/tick")
    async def proactive_tick(pet_id: str = "demo"):
        return runtime.proactive_tick(pet_id)

    @router.get("/personas")
    async def personas():
        return list_personas()

    @router.post("/persona/{persona_id}")
    async def switch_persona(persona_id: PersonaId):
        return runtime.switch_persona(persona_id)

    @router.get("/prompt")
    async def prompt(pet_id: str = "demo", memory_query: str = ""):
        return {"prompt": runtime.build_prompt(pet_id, memory_query)}

    return router


def _artifact_payload(artifact) -> dict[str, str | float]:
    payload = asdict(artifact)
    payload["path"] = f"/pet-artifacts/{artifact.path.name}"
    return payload

"""HTTP endpoints used by the SLAI Pet status panel."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from .config_manager.utils import Config
from .pet_domain import PetStateRepository, PetStateService


class FeedPetRequest(BaseModel):
    user_id: str = Field("default", min_length=1, max_length=128)
    food: str = Field("小鱼干", min_length=1, max_length=64)
    request_id: str | None = Field(None, max_length=128)


def _profile_from_config(config: Config) -> dict[str, object]:
    character = config.character_config
    tts_name = character.tts_config.tts_model
    tts_settings = getattr(character.tts_config, tts_name, None)
    voice = getattr(tts_settings, "voice", "") if tts_settings else ""
    agent_config = getattr(character, "agent_config", None)
    basic_config = (
        getattr(
            getattr(agent_config, "agent_settings", None), "basic_memory_agent", None
        )
        if agent_config
        else None
    )
    provider = getattr(basic_config, "llm_provider", "")
    model_config = (
        getattr(getattr(agent_config, "llm_configs", None), provider, None)
        if provider
        else None
    )
    model = getattr(model_config, "model", "")
    capabilities = ["真实状态", "自主工具调用", "成长记录"]
    if getattr(model_config, "supports_vision", False):
        capabilities.append("视觉感知")
    return {
        "name": character.character_name,
        "persona": character.conf_name,
        "live2d_model": character.live2d_model_name,
        "voice": voice,
        "model": model,
        "catchphrase": "今天也要闪闪发光！",
        "capabilities": capabilities,
    }


def init_pet_routes(
    config: Config,
    service: PetStateService | None = None,
) -> APIRouter:
    """Create pet routes with an injectable state service for tests."""

    pet_service = service or PetStateService(PetStateRepository("data/pet.db"))
    router = APIRouter(prefix="/api/pet", tags=["SLAI Pet"])

    @router.get("/state")
    async def get_pet_state(user_id: str = "default") -> dict[str, object]:
        state = pet_service.get_pet_state(user_id)
        return {
            "success": True,
            "profile": _profile_from_config(config),
            "state": state.to_dict(),
        }

    @router.post("/feed")
    async def feed_pet(request: FeedPetRequest) -> dict[str, object]:
        return pet_service.feed_pet(
            user_id=request.user_id,
            food=request.food,
            request_id=request.request_id,
        ).to_dict()

    return router

"""HTTP endpoints used by the SLAI Pet status panel."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .config_manager.utils import Config
from .pet_domain import PetStateRepository, PetStateService, WorldService
from .pet_live2d import (
    Live2dReactionResolver,
    decorate_reaction_messages,
    render_payload,
)
from .pet_speech import (
    PET_SPEECH_SCHEMA_VERSION,
    PetSpeechBroadcaster,
    pet_speech_broadcaster,
)

PET_EVENT_SCHEMA_VERSION = "1.0"


class PetActionRequest(BaseModel):
    """Shared, validated envelope for every state-changing pet action."""

    user_id: str = Field("default", min_length=1, max_length=128)
    request_id: str | None = Field(None, max_length=128)


class FeedPetRequest(PetActionRequest):
    food: str = Field("小鱼干", min_length=1, max_length=64)


class PlayWithPetRequest(PetActionRequest):
    game: str = Field("追激光笔", min_length=1, max_length=64)


class CleanPetRequest(PetActionRequest):
    method: str = Field("洗澡", min_length=1, max_length=64)


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


def _messages_for_event(
    event: dict[str, Any],
    live2d_resolver: Live2dReactionResolver | None = None,
) -> list[dict[str, Any]]:
    """Convert a committed domain event into stable browser event messages."""

    payload = event.get("payload", {})
    state = payload.get("state_after")
    if not isinstance(state, dict):
        return []

    common = {
        "schema_version": PET_EVENT_SCHEMA_VERSION,
        "sequence": event["sequence"],
        "event_id": event["event_id"],
        "request_id": event["request_id"],
        "user_id": event["user_id"],
        "occurred_at": event["created_at"],
        "action": payload.get("action", event["event_type"]),
    }
    messages = [
        {
            "type": "pet_state_changed",
            **common,
            "changes": payload.get("changes", {}),
            "state": state,
        }
    ]
    reaction = payload.get("reaction")
    if isinstance(reaction, dict):
        messages.append(
            {
                "type": "pet_reaction",
                **common,
                "reaction": reaction,
            }
        )
    return decorate_reaction_messages(messages, live2d_resolver)


def init_pet_routes(
    config: Config,
    service: PetStateService | None = None,
    event_poll_interval: float = 0.25,
    live2d_resolver: Live2dReactionResolver | None = None,
    speech_broadcaster: PetSpeechBroadcaster | None = None,
    world_service: WorldService | None = None,
) -> APIRouter:
    """Create pet routes with an injectable state service for tests."""

    pet_service = service or PetStateService(PetStateRepository("data/pet.db"))
    resolver = live2d_resolver or Live2dReactionResolver.from_model_name(
        str(getattr(config.character_config, "live2d_model_name", "") or "")
    )
    speech = speech_broadcaster or pet_speech_broadcaster
    world = world_service or WorldService(pet_service.repository)
    router = APIRouter(prefix="/api/pet", tags=["SLAI Pet"])

    @router.get("/state")
    async def get_pet_state(user_id: str = "default") -> dict[str, object]:
        state = pet_service.get_pet_state(user_id)
        return {
            "success": True,
            "profile": _profile_from_config(config),
            "state": state.to_dict(),
            "live2d": resolver.capabilities,
        }

    def _with_render(payload: dict[str, object]) -> dict[str, object]:
        render = render_payload(payload.get("reaction"), resolver)
        if render is not None:
            payload["render"] = render
        return payload

    @router.post("/feed")
    async def feed_pet(request: FeedPetRequest) -> dict[str, object]:
        return _with_render(
            pet_service.feed_pet(
                user_id=request.user_id,
                food=request.food,
                request_id=request.request_id,
            ).to_dict()
        )

    @router.post("/play")
    async def play_with_pet(request: PlayWithPetRequest) -> dict[str, object]:
        return _with_render(
            pet_service.play_with_pet(
                user_id=request.user_id,
                game=request.game,
                request_id=request.request_id,
            ).to_dict()
        )

    @router.post("/clean")
    async def clean_pet(request: CleanPetRequest) -> dict[str, object]:
        return _with_render(
            pet_service.clean_pet(
                user_id=request.user_id,
                method=request.method,
                request_id=request.request_id,
            ).to_dict()
        )

    @router.post("/sleep")
    async def put_pet_to_sleep(request: PetActionRequest) -> dict[str, object]:
        return _with_render(
            pet_service.put_pet_to_sleep(
                user_id=request.user_id,
                request_id=request.request_id,
            ).to_dict()
        )

    @router.get("/world")
    async def get_pet_world(user_id: str = "default") -> dict[str, object]:
        """Current world event, background and offline summary."""

        state = pet_service.get_pet_state(user_id)
        return {"success": True, **world.current_world(user_id, state)}

    @router.get("/speech/recent")
    async def recent_pet_speech(limit: int = 10) -> dict[str, object]:
        """Short display buffer for the drawer. Not long-term memory."""

        return {
            "success": True,
            "schema_version": PET_SPEECH_SCHEMA_VERSION,
            "kind": "recent_conversation",
            "items": speech.recent(max(0, min(limit, 50))),
        }

    @router.websocket("/events")
    async def stream_pet_events(
        websocket: WebSocket,
        user_id: str = "default",
    ) -> None:
        """Stream committed state and reaction events, including MCP writes."""

        if not user_id or len(user_id) > 128:
            await websocket.close(code=1008)
            return

        await websocket.accept()
        repository = pet_service.repository
        sequence = await asyncio.to_thread(
            repository.get_latest_event_sequence, user_id
        )
        speech_queue = speech.subscribe()
        await websocket.send_json(
            {
                "type": "pet_events_ready",
                "schema_version": PET_EVENT_SCHEMA_VERSION,
                "sequence": sequence,
            }
        )

        try:
            while True:
                events = await asyncio.to_thread(
                    repository.list_events_after,
                    sequence,
                    user_id,
                )
                for event in events:
                    for message in _messages_for_event(event, resolver):
                        await websocket.send_json(message)
                    sequence = event["sequence"]

                # Spoken sentences share this channel so the head bubble and
                # the status card stay in one ordered stream for the browser.
                while True:
                    try:
                        await websocket.send_json(speech_queue.get_nowait())
                    except asyncio.QueueEmpty:
                        break

                try:
                    await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=max(0.05, event_poll_interval),
                    )
                except asyncio.TimeoutError:
                    pass
        except WebSocketDisconnect:
            return
        finally:
            speech.unsubscribe(speech_queue)

    return router

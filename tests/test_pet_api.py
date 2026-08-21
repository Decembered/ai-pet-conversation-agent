from __future__ import annotations

import json

import anyio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from open_llm_vtuber.pet.routes import init_pet_routes
from open_llm_vtuber.pet.runtime import PetRuntime
from open_llm_vtuber.service_context import ServiceContext
from open_llm_vtuber.websocket_handler import WebSocketHandler


def test_pet_http_api_exposes_state_actions_memory_and_skills(tmp_path) -> None:
    app = FastAPI()
    app.include_router(
        init_pet_routes(PetRuntime(tmp_path / "pet.sqlite3", tmp_path / "artifacts"))
    )

    with TestClient(app) as client:
        state = client.get("/api/pet/state", params={"pet_id": "demo"})
        response = client.post(
            "/api/pet/respond",
            json={"pet_id": "demo", "text": "你现在怎么样"},
        )
        action = client.post(
            "/api/pet/actions", json={"pet_id": "demo", "action": "feed"}
        )
        memory = client.post(
            "/api/pet/memory",
            json={"pet_id": "demo", "key": "zodiac", "value": "天秤座"},
        )
        recalled = client.get(
            "/api/pet/memory", params={"pet_id": "demo", "query": "我的星座"}
        )
        letter = client.post(
            "/api/pet/skills/letter",
            json={"pet_id": "demo", "recipient": "主人", "content": "早点休息"},
        )
        observe = client.post(
            "/api/pet/observe", json={"event_type": "entered", "observed_at": 100}
        )

    assert state.status_code == 200
    assert state.json()["level"] == 1
    assert response.json()["handled"] is True
    assert action.json()["action"] == "feed"
    assert memory.json()["value"] == "天秤座"
    assert recalled.json()[0]["key"] == "zodiac"
    assert letter.json()["kind"] == "letter"
    assert letter.json()["path"].startswith("/pet-artifacts/")
    assert observe.json()["should_trigger"] is True


def test_websocket_text_intent_updates_state_without_llm(tmp_path) -> None:
    class FakeWebSocket:
        def __init__(self) -> None:
            self.messages: list[str] = []

        async def send_text(self, message: str) -> None:
            self.messages.append(message)

    async def run() -> list[dict]:
        runtime = PetRuntime(tmp_path / "pet.sqlite3", tmp_path / "artifacts")
        handler = WebSocketHandler(ServiceContext(), pet_runtime=runtime)
        websocket = FakeWebSocket()
        await handler._route_message(
            websocket, "client", {"type": "text-input", "text": "给你一条鱼"}
        )
        return [json.loads(message) for message in websocket.messages]

    messages = anyio.run(run)

    assert messages[0]["source"] == "pet-domain"
    assert messages[1]["type"] == "pet-action-result"
    assert messages[1]["action"] == "feed"

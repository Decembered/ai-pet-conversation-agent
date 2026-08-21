"""API tests for the status panel's pet endpoints."""

from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from open_llm_vtuber.pet_domain import PetStateRepository, PetStateService
from open_llm_vtuber.pet_routes import init_pet_routes


class PetRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        test_temp_root = Path.cwd() / "tmp" / "tests"
        test_temp_root.mkdir(parents=True, exist_ok=True)
        self.database_path = test_temp_root / f"pet-api-{uuid4()}.db"
        self.addCleanup(self.database_path.unlink, missing_ok=True)
        service = PetStateService(PetStateRepository(self.database_path))
        tts = SimpleNamespace(
            tts_model="edge_tts",
            edge_tts=SimpleNamespace(voice="zh-CN-XiaoxiaoNeural"),
        )
        character = SimpleNamespace(
            character_name="小光",
            conf_name="SLAI Pet · 小太阳",
            live2d_model_name="mao_pro",
            tts_config=tts,
        )
        config = SimpleNamespace(character_config=character)
        app = FastAPI()
        app.include_router(
            init_pet_routes(
                config=config,
                service=service,
                event_poll_interval=0.01,
            )
        )
        self.client = TestClient(app)

    def test_state_endpoint_exposes_profile_and_persistent_state(self) -> None:
        response = self.client.get("/api/pet/state")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["profile"]["name"], "小光")
        self.assertEqual(payload["state"]["level"], 1)

    def test_feed_endpoint_updates_the_state(self) -> None:
        before = self.client.get("/api/pet/state").json()["state"]
        response = self.client.post(
            "/api/pet/feed",
            json={"food": "小鱼干", "request_id": "ui-test-feed"},
        )

        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertLess(result["state"]["hunger"], before["hunger"])
        self.assertGreater(result["state"]["intimacy"], before["intimacy"])
        self.assertEqual(result["reaction"]["animation"], "eat")
        self.assertLess(result["changes"]["hunger"]["delta"], 0)

    def test_event_websocket_streams_committed_feed_reaction(self) -> None:
        with self.client.websocket_connect("/api/pet/events?user_id=default") as events:
            ready = events.receive_json()
            self.assertEqual(ready["type"], "pet_events_ready")
            self.assertEqual(ready["schema_version"], "1.0")

            response = self.client.post(
                "/api/pet/feed",
                json={"food": "小鱼干", "request_id": "ws-test-feed"},
            )
            self.assertEqual(response.status_code, 200)

            state_event = events.receive_json()
            reaction_event = events.receive_json()
            self.assertEqual(state_event["type"], "pet_state_changed")
            self.assertEqual(state_event["event_id"], response.json()["event_id"])
            self.assertEqual(state_event["state"]["activity"], "eating")
            self.assertLess(state_event["changes"]["hunger"]["delta"], 0)
            self.assertEqual(reaction_event["type"], "pet_reaction")
            self.assertEqual(reaction_event["reaction"]["particle"], "fish")

    def test_event_websocket_observes_external_repository_writes(self) -> None:
        with self.client.websocket_connect("/api/pet/events?user_id=default") as events:
            events.receive_json()
            external_service = PetStateService(PetStateRepository(self.database_path))
            result = external_service.feed_pet(
                food="苹果",
                request_id="external-mcp-style-feed",
            )

            state_event = events.receive_json()
            reaction_event = events.receive_json()
            self.assertEqual(state_event["event_id"], result.event_id)
            self.assertEqual(state_event["type"], "pet_state_changed")
            self.assertEqual(reaction_event["type"], "pet_reaction")


if __name__ == "__main__":
    unittest.main()

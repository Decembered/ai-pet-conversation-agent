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
        app.include_router(init_pet_routes(config=config, service=service))
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


if __name__ == "__main__":
    unittest.main()

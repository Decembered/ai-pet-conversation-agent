"""Regression tests for the play / clean / sleep pet behaviours (Phase B)."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from open_llm_vtuber.pet_domain import PetStateRepository, PetStateService

try:  # pragma: no cover - exercised implicitly by the skip decorator
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    FASTAPI_AVAILABLE = False


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class PetCareActionTests(unittest.TestCase):
    def setUp(self) -> None:
        test_temp_root = Path.cwd() / "tmp" / "tests"
        test_temp_root.mkdir(parents=True, exist_ok=True)
        self.database_path = test_temp_root / f"pet-actions-{uuid4()}.db"
        self.addCleanup(self.database_path.unlink, missing_ok=True)
        self.clock = MutableClock(datetime(2026, 8, 22, 9, tzinfo=timezone.utc))
        self.repository = PetStateRepository(self.database_path)
        self.service = PetStateService(self.repository, self.clock)

    # ------------------------------------------------------------------
    # play
    # ------------------------------------------------------------------
    def test_play_spends_energy_and_builds_the_relationship(self) -> None:
        before = self.service.get_pet_state("owner-1")

        result = self.service.play_with_pet(
            user_id="owner-1", game="追激光笔", request_id="play-001"
        )

        self.assertFalse(result.duplicate)
        self.assertLess(result.state.energy, before.energy)
        self.assertGreater(result.state.mood, before.mood)
        self.assertGreater(result.state.intimacy, before.intimacy)
        self.assertGreater(result.state.experience, before.experience)
        self.assertEqual(result.state.activity, "playing")
        self.assertEqual(result.reaction.kind, "play_success")
        self.assertEqual(result.reaction.animation, "play")
        self.assertLess(result.changes["energy"]["delta"], 0)

    # ------------------------------------------------------------------
    # clean
    # ------------------------------------------------------------------
    def test_clean_raises_cleanliness_and_persists(self) -> None:
        state = self.service.get_pet_state("owner-1")
        state.cleanliness = 20
        self.repository.save_state(state)

        result = self.service.clean_pet(user_id="owner-1", request_id="clean-001")
        reloaded = PetStateRepository(self.database_path).get_state("owner-1")

        self.assertEqual(result.state.cleanliness, 55)
        self.assertEqual(result.state.activity, "bathing")
        self.assertEqual(result.reaction.particle, "bubble")
        self.assertEqual(reloaded.to_dict(), result.state.to_dict())

    # ------------------------------------------------------------------
    # sleep
    # ------------------------------------------------------------------
    def test_sleep_switches_activity_and_recovers_energy_over_time(self) -> None:
        state = self.service.get_pet_state("owner-1")
        state.energy = 30
        self.repository.save_state(state)

        asleep = self.service.put_pet_to_sleep(user_id="owner-1", request_id="sleep-1")
        self.assertEqual(asleep.state.activity, "sleeping")
        self.assertEqual(asleep.reaction.kind, "sleep_success")

        self.clock.value += timedelta(hours=2)
        rested = self.service.get_pet_state("owner-1")

        # Sleeping recovers energy instead of draining it, and the pet wakes up
        # on its own once it is fully rested.
        self.assertEqual(rested.energy, asleep.state.energy + 12)
        self.assertEqual(rested.activity, "sleeping")

    def test_a_fully_rested_pet_wakes_up_by_itself(self) -> None:
        self.service.put_pet_to_sleep(user_id="owner-1", request_id="sleep-2")
        self.clock.value += timedelta(hours=24)

        rested = self.service.get_pet_state("owner-1")

        self.assertEqual(rested.energy, 100)
        self.assertEqual(rested.activity, "resting")

    # ------------------------------------------------------------------
    # shared guarantees
    # ------------------------------------------------------------------
    def test_every_action_is_idempotent_per_request_id(self) -> None:
        cases = (
            ("play_with_pet", self.service.play_with_pet),
            ("clean_pet", self.service.clean_pet),
            ("put_pet_to_sleep", self.service.put_pet_to_sleep),
        )
        for action, call in cases:
            with self.subTest(action=action):
                request_id = f"repeat-{action}"
                first = call(user_id="owner-1", request_id=request_id)
                sequence = self.repository.get_latest_event_sequence("owner-1")
                second = call(user_id="owner-1", request_id=request_id)

                self.assertFalse(first.duplicate)
                self.assertTrue(second.duplicate)
                self.assertEqual(first.event_id, second.event_id)
                self.assertIsNone(second.reaction)
                self.assertEqual(
                    self.repository.get_latest_event_sequence("owner-1"), sequence
                )

    def test_each_action_writes_its_own_event_type(self) -> None:
        self.service.play_with_pet(user_id="owner-2", request_id="p")
        self.service.clean_pet(user_id="owner-2", request_id="c")
        self.service.put_pet_to_sleep(user_id="owner-2", request_id="s")

        events = self.repository.list_events_after(0, "owner-2")

        self.assertEqual(
            [event["event_type"] for event in events],
            ["PetPlayed", "PetCleaned", "PetSlept"],
        )
        self.assertEqual(
            [event["payload"]["action"] for event in events],
            ["play_with_pet", "clean_pet", "put_pet_to_sleep"],
        )

    def test_values_stay_inside_the_public_range(self) -> None:
        state = self.service.get_pet_state("owner-1")
        state.energy = 4
        state.cleanliness = 98
        state.mood = 99
        self.repository.save_state(state)

        played = self.service.play_with_pet(user_id="owner-1", request_id="clamp-play")
        cleaned = self.service.clean_pet(user_id="owner-1", request_id="clamp-clean")

        self.assertEqual(played.state.energy, 0)
        self.assertEqual(cleaned.state.cleanliness, 100)
        for result in (played, cleaned):
            for value in (
                result.state.hunger,
                result.state.energy,
                result.state.health,
                result.state.mood,
                result.state.cleanliness,
                result.state.intimacy,
                result.state.maturity,
            ):
                self.assertGreaterEqual(value, 0)
                self.assertLessEqual(value, 100)


@unittest.skipUnless(FASTAPI_AVAILABLE, "FastAPI is required for route tests")
class PetCareRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        from open_llm_vtuber.pet_routes import init_pet_routes

        test_temp_root = Path.cwd() / "tmp" / "tests"
        test_temp_root.mkdir(parents=True, exist_ok=True)
        self.database_path = test_temp_root / f"pet-care-api-{uuid4()}.db"
        self.addCleanup(self.database_path.unlink, missing_ok=True)
        service = PetStateService(PetStateRepository(self.database_path))
        character = SimpleNamespace(
            character_name="小光",
            conf_name="SLAI Pet · 小太阳",
            live2d_model_name="mao_pro",
            tts_config=SimpleNamespace(
                tts_model="edge_tts",
                edge_tts=SimpleNamespace(voice="zh-CN-XiaoxiaoNeural"),
            ),
        )
        app = FastAPI()
        app.include_router(
            init_pet_routes(
                config=SimpleNamespace(character_config=character),
                service=service,
                event_poll_interval=0.01,
            )
        )
        self.client = TestClient(app)

    def test_each_care_endpoint_changes_state_and_returns_a_reaction(self) -> None:
        cases = (
            ("/api/pet/play", "playing", "play_success"),
            ("/api/pet/clean", "bathing", "clean_success"),
            ("/api/pet/sleep", "sleeping", "sleep_success"),
        )
        for path, activity, kind in cases:
            with self.subTest(path=path):
                result = self.client.post(
                    path, json={"request_id": f"route-{uuid4()}"}
                ).json()

                self.assertTrue(result["success"])
                self.assertEqual(result["state"]["activity"], activity)
                self.assertEqual(result["reaction"]["kind"], kind)
                self.assertIn("render", result)

    def test_repeated_request_id_does_not_change_state_twice(self) -> None:
        request_id = f"route-repeat-{uuid4()}"
        first = self.client.post(
            "/api/pet/play", json={"request_id": request_id}
        ).json()
        second = self.client.post(
            "/api/pet/play", json={"request_id": request_id}
        ).json()

        self.assertFalse(first["duplicate"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["state"]["energy"], second["state"]["energy"])
        self.assertIsNone(second["reaction"])

    def test_care_events_reach_the_pet_event_stream(self) -> None:
        with self.client.websocket_connect("/api/pet/events?user_id=default") as events:
            events.receive_json()
            response = self.client.post(
                "/api/pet/clean", json={"request_id": f"route-ws-{uuid4()}"}
            ).json()

            state_event = events.receive_json()
            reaction_event = events.receive_json()

        self.assertEqual(state_event["action"], "clean_pet")
        self.assertEqual(state_event["event_id"], response["event_id"])
        self.assertEqual(reaction_event["reaction"]["particle"], "bubble")
        self.assertEqual(reaction_event["render"], response["render"])

    def test_invalid_parameters_are_rejected(self) -> None:
        response = self.client.post("/api/pet/play", json={"game": ""})

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()

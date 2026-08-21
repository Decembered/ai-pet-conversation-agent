"""Regression tests for SLAI Pet's first persistent state vertical slice."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from open_llm_vtuber.pet_domain import PetStateRepository, PetStateService


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class PetStateServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        test_temp_root = Path.cwd() / "tmp" / "tests"
        test_temp_root.mkdir(parents=True, exist_ok=True)
        self.database_path = test_temp_root / f"pet-{uuid4()}.db"
        self.addCleanup(self.database_path.unlink, missing_ok=True)
        self.clock = MutableClock(datetime(2026, 8, 21, 12, tzinfo=timezone.utc))
        self.repository = PetStateRepository(self.database_path)
        self.service = PetStateService(self.repository, self.clock)

    def test_first_query_creates_persistent_default_state(self) -> None:
        state = self.service.get_pet_state("owner-1")

        self.assertEqual(state.user_id, "owner-1")
        self.assertEqual(state.hunger, 25.0)
        self.assertEqual(state.location, "pet_home")
        self.assertIsNotNone(self.repository.get_state("owner-1"))

    def test_elapsed_time_updates_state_without_per_second_writes(self) -> None:
        initial = self.service.get_pet_state("owner-1")
        self.clock.value += timedelta(hours=2)

        current = self.service.get_pet_state("owner-1")

        self.assertEqual(current.hunger, initial.hunger + 4)
        self.assertEqual(current.energy, initial.energy - 2)
        self.assertEqual(current.cleanliness, initial.cleanliness - 1)

    def test_feed_changes_and_persists_real_state(self) -> None:
        before = self.service.get_pet_state("owner-1")

        result = self.service.feed_pet(
            user_id="owner-1",
            food="小鱼干",
            request_id="feed-001",
        )
        reloaded = PetStateRepository(self.database_path).get_state("owner-1")

        self.assertFalse(result.duplicate)
        self.assertLess(result.state.hunger, before.hunger)
        self.assertGreater(result.state.mood, before.mood)
        self.assertGreater(result.state.intimacy, before.intimacy)
        self.assertEqual(reloaded.to_dict(), result.state.to_dict())
        self.assertLess(result.changes["hunger"]["delta"], 0)
        self.assertEqual(result.reaction.kind, "feed_success")
        self.assertIn("小鱼干", result.reaction.bubble)

        events = self.repository.list_events_after(0, "owner-1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_id"], result.event_id)
        self.assertEqual(events[0]["payload"]["reaction"]["animation"], "eat")

    def test_feed_request_is_idempotent(self) -> None:
        first = self.service.feed_pet(
            user_id="owner-1",
            food="苹果",
            request_id="same-request",
        )
        sequence_after_first = self.repository.get_latest_event_sequence("owner-1")
        second = self.service.feed_pet(
            user_id="owner-1",
            food="苹果",
            request_id="same-request",
        )

        self.assertFalse(first.duplicate)
        self.assertTrue(second.duplicate)
        self.assertEqual(first.event_id, second.event_id)
        self.assertEqual(first.state.hunger, second.state.hunger)
        self.assertIsNone(second.reaction)
        self.assertEqual(
            self.repository.get_latest_event_sequence("owner-1"),
            sequence_after_first,
        )

    def test_values_are_clamped_to_public_range(self) -> None:
        state = self.service.get_pet_state("owner-1")
        state.hunger = 5
        state.mood = 99
        self.repository.save_state(state)

        result = self.service.feed_pet(
            user_id="owner-1",
            food="大餐",
            request_id="feed-clamp",
        )

        self.assertEqual(result.state.hunger, 0)
        self.assertEqual(result.state.mood, 100)
        self.assertTrue(
            all(
                0 <= value <= 100
                for value in (
                    result.state.hunger,
                    result.state.energy,
                    result.state.health,
                    result.state.mood,
                    result.state.cleanliness,
                    result.state.intimacy,
                    result.state.maturity,
                )
            )
        )


if __name__ == "__main__":
    unittest.main()

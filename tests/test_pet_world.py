"""The pet's minimal living world: clock, routine, priorities and resume."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from open_llm_vtuber.pet_domain import PetStateRepository, PetStateService, WorldService
from open_llm_vtuber.pet_domain.world import (
    REASON_ROUTINE,
    REASON_STATE_ALERT,
    REASON_USER_INTERACTION,
    BehaviorPlanner,
    RoutineScheduler,
    WorldClock,
    background_for,
)

LOCAL = timezone(timedelta(hours=8))


def fixed_clock(value: datetime) -> WorldClock:
    return WorldClock(clock=lambda: value)


def state_at(moment: datetime, **overrides):
    """A pet state stub with sane defaults; only the read fields matter here."""

    defaults = {
        "hunger": 25.0,
        "energy": 80.0,
        "health": 100.0,
        "mood": 75.0,
        "cleanliness": 80.0,
        "activity": "resting",
        "last_updated_at": moment,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class WorldClockTests(unittest.TestCase):
    def test_day_is_split_into_four_phases(self) -> None:
        cases = {6: "morning", 13: "day", 19: "evening", 23: "night", 3: "night"}
        for hour, expected in cases.items():
            with self.subTest(hour=hour):
                self.assertEqual(WorldClock.phase_for_hour(hour), expected)

    def test_moment_reports_phase_and_date(self) -> None:
        clock = fixed_clock(datetime(2026, 8, 22, 20, 30, tzinfo=LOCAL))

        moment = clock.moment().to_dict()

        self.assertEqual(moment["phase"], "evening")
        self.assertEqual(moment["phase_label"], "傍晚")
        self.assertEqual(moment["date"], "2026-08-22")


class RoutineSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scheduler = RoutineScheduler()

    def test_routine_only_uses_the_three_recoverable_behaviours(self) -> None:
        behaviors = {slot.behavior for slot in self.scheduler.slots}

        self.assertEqual(behaviors, {"resting", "studying", "playing"})

    def test_the_day_is_covered_without_gaps(self) -> None:
        for hour in range(24):
            with self.subTest(hour=hour):
                moment = datetime(2026, 8, 22, hour, tzinfo=LOCAL)
                self.assertIn(
                    self.scheduler.slot_for(moment).behavior,
                    {"resting", "studying", "playing"},
                )

    def test_slot_end_is_a_real_timestamp(self) -> None:
        moment = datetime(2026, 8, 22, 10, 15, tzinfo=LOCAL)

        end = self.scheduler.slot_end(moment)

        self.assertEqual(end, datetime(2026, 8, 22, 12, 0, tzinfo=LOCAL))

    def test_behaviors_between_collapses_repeats(self) -> None:
        start = datetime(2026, 8, 22, 9, tzinfo=LOCAL)
        end = datetime(2026, 8, 22, 15, tzinfo=LOCAL)

        behaviors = self.scheduler.behaviors_between(start, end)

        self.assertEqual(behaviors, ["studying", "playing", "studying"])


class BehaviorPriorityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = BehaviorPlanner()
        self.moment = fixed_clock(datetime(2026, 8, 22, 10, tzinfo=LOCAL)).moment()

    def test_recent_owner_interaction_wins_over_everything(self) -> None:
        state = state_at(
            self.moment.moment - timedelta(minutes=1),
            activity="playing",
            hunger=95,  # an alert that must not win
        )

        decision = self.planner.decide(state, self.moment)

        self.assertEqual(decision.behavior, "playing")
        self.assertEqual(decision.reason, REASON_USER_INTERACTION)

    def test_a_stale_interaction_no_longer_wins(self) -> None:
        state = state_at(self.moment.moment - timedelta(hours=3), activity="playing")

        decision = self.planner.decide(state, self.moment)

        self.assertEqual(decision.reason, REASON_ROUTINE)

    def test_state_alerts_win_over_the_routine(self) -> None:
        state = state_at(self.moment.moment - timedelta(hours=3), energy=8)

        decision = self.planner.decide(state, self.moment)

        self.assertEqual(decision.behavior, "resting")
        self.assertEqual(decision.reason, REASON_STATE_ALERT)
        self.assertIn("精力", decision.note)

    def test_routine_drives_an_undisturbed_day(self) -> None:
        state = state_at(self.moment.moment - timedelta(hours=6))

        decision = self.planner.decide(state, self.moment)

        self.assertEqual(decision.behavior, "studying")
        self.assertEqual(decision.reason, REASON_ROUTINE)
        self.assertEqual(
            decision.expected_end_at, datetime(2026, 8, 22, 12, tzinfo=LOCAL)
        )


class BackgroundTests(unittest.TestCase):
    def test_an_existing_file_is_offered_as_a_url(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            (root / "backgrounds").mkdir()
            (root / "backgrounds" / "room-interior-illustration.jpeg").write_bytes(b"x")

            background = background_for("resting", "morning", project_root=root)

        self.assertTrue(background["available"])
        self.assertEqual(background["url"], "/bg/room-interior-illustration.jpeg")
        self.assertIsNone(background["missing_asset"])

    def test_a_missing_file_degrades_to_a_generated_gradient(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            background = background_for(
                "studying", "night", project_root=Path(raw_root)
            )

        self.assertFalse(background["available"])
        self.assertIsNone(background["url"])
        self.assertTrue(background["gradient"].startswith("linear-gradient"))
        self.assertEqual(background["missing_asset"], "computer-room-illustration.jpeg")

    def test_every_phase_and_behaviour_pair_has_a_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            for behavior in ("resting", "studying", "playing"):
                for phase in ("morning", "day", "evening", "night"):
                    with self.subTest(behavior=behavior, phase=phase):
                        background = background_for(
                            behavior, phase, project_root=Path(raw_root)
                        )
                        self.assertIsNotNone(background["missing_asset"])
                        self.assertTrue(background["tint"])


class WorldServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        test_temp_root = Path.cwd() / "tmp" / "tests"
        test_temp_root.mkdir(parents=True, exist_ok=True)
        self.database_path = test_temp_root / f"pet-world-{uuid4()}.db"
        self.addCleanup(self.database_path.unlink, missing_ok=True)
        self.repository = PetStateRepository(self.database_path)
        self.service = PetStateService(self.repository)

    def world_at(self, moment: datetime) -> WorldService:
        return WorldService(self.repository, clock=fixed_clock(moment))

    def test_a_restart_resumes_the_same_event(self) -> None:
        moment = datetime(2026, 8, 22, 10, tzinfo=LOCAL)
        state = state_at(moment - timedelta(hours=4))

        first = self.world_at(moment).current_world("owner-1", state)
        # A brand new service instance stands in for an app restart.
        second = self.world_at(moment + timedelta(minutes=20)).current_world(
            "owner-1", state
        )

        self.assertEqual(first["event"]["event_id"], second["event"]["event_id"])
        self.assertEqual(first["event"]["started_at"], second["event"]["started_at"])

    def test_a_new_slot_starts_a_new_event(self) -> None:
        state = state_at(datetime(2026, 8, 22, 6, tzinfo=LOCAL))
        morning = self.world_at(datetime(2026, 8, 22, 10, tzinfo=LOCAL)).current_world(
            "owner-1", state
        )
        afternoon = self.world_at(
            datetime(2026, 8, 22, 13, tzinfo=LOCAL)
        ).current_world("owner-1", state)

        self.assertEqual(morning["event"]["behavior"], "studying")
        self.assertEqual(afternoon["event"]["behavior"], "playing")
        self.assertNotEqual(
            morning["event"]["event_id"], afternoon["event"]["event_id"]
        )

    def test_a_long_absence_is_summarised_not_replayed(self) -> None:
        state = state_at(datetime(2026, 8, 22, 6, tzinfo=LOCAL))
        self.world_at(datetime(2026, 8, 22, 10, tzinfo=LOCAL)).current_world(
            "owner-1", state
        )

        later = self.world_at(datetime(2026, 8, 22, 17, tzinfo=LOCAL)).current_world(
            "owner-1", state
        )

        self.assertIsNotNone(later["offline_summary"])
        self.assertIn("小时", later["offline_summary"])
        # A summary, not a queue of events to replay.
        self.assertNotIn("events", later)

    def test_a_short_gap_is_not_summarised(self) -> None:
        state = state_at(datetime(2026, 8, 22, 6, tzinfo=LOCAL))
        self.world_at(datetime(2026, 8, 22, 10, tzinfo=LOCAL)).current_world(
            "owner-1", state
        )

        soon = self.world_at(datetime(2026, 8, 22, 11, tzinfo=LOCAL)).current_world(
            "owner-1", state
        )

        self.assertIsNone(soon["offline_summary"])

    def test_the_world_payload_is_self_describing(self) -> None:
        state = state_at(datetime(2026, 8, 22, 6, tzinfo=LOCAL))

        payload = self.world_at(datetime(2026, 8, 22, 23, tzinfo=LOCAL)).current_world(
            "owner-1", state
        )

        self.assertEqual(payload["now"]["phase"], "night")
        self.assertEqual(payload["event"]["behavior_label"], "休息")
        self.assertIn("feed_pet", payload["event"]["interactions"])
        self.assertEqual(payload["background"]["phase"], "night")
        self.assertEqual(len(payload["routine"]), len(RoutineScheduler().slots))

    def test_real_pet_state_objects_are_accepted(self) -> None:
        """The planner must work with the real domain object, not just stubs."""

        state = self.service.get_pet_state("owner-2")

        payload = self.world_at(datetime(2026, 8, 22, 15, tzinfo=LOCAL)).current_world(
            "owner-2", state
        )

        self.assertIn(payload["event"]["behavior"], {"resting", "studying", "playing"})


if __name__ == "__main__":
    unittest.main()

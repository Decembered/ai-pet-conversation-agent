"""Live2D reaction rendering: real asset inventory and honest degradation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from open_llm_vtuber.pet_live2d import (
    REASON_MODEL_UNAVAILABLE,
    REASON_NATIVE_MOTION,
    REASON_NO_EXPRESSION,
    Live2dReactionResolver,
    decorate_reaction_messages,
    render_payload,
)

try:  # pragma: no cover - exercised implicitly by the skip decorator
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    FASTAPI_AVAILABLE = False

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _write_model(
    root: Path,
    *,
    motions: dict[str, list[dict[str, str]]],
    expressions: list[str],
    emotion_map: dict[str, int],
) -> Path:
    """Create a minimal model dictionary + model3.json pair for tests."""

    runtime = root / "live2d-models" / "probe" / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "probe.model3.json").write_text(
        json.dumps(
            {
                "Version": 3,
                "FileReferences": {
                    "Motions": motions,
                    "Expressions": [
                        {"Name": name, "File": f"expressions/{name}.exp3.json"}
                        for name in expressions
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "model_dict.json").write_text(
        json.dumps(
            [
                {
                    "name": "probe",
                    "url": "/live2d-models/probe/runtime/probe.model3.json",
                    "emotionMap": emotion_map,
                }
            ]
        ),
        encoding="utf-8",
    )
    return root


class MaoProInventoryTests(unittest.TestCase):
    """The bundled mao_pro model is the current source of truth for Phase A."""

    def setUp(self) -> None:
        self.resolver = Live2dReactionResolver.from_model_name(
            "mao_pro", project_root=PROJECT_ROOT
        )

    def test_inventory_matches_the_shipped_model_assets(self) -> None:
        capabilities = self.resolver.capabilities

        self.assertTrue(capabilities["available"])
        self.assertIsNone(capabilities["error"])
        self.assertEqual(
            capabilities["motion_groups"],
            {
                "Idle": 1,
                "": 6,
                "Eat": 1,
                "Play": 1,
                "Clean": 1,
                "Sleep": 1,
                "SleepIdle": 1,
                "Wake": 1,
            },
        )
        self.assertEqual(
            capabilities["expressions"],
            [f"exp_0{index}" for index in range(1, 9)],
        )

    def test_bundled_pet_actions_have_native_motions(self) -> None:
        expected_groups = {
            "eat": "Eat",
            "play": "Play",
            "clean": "Clean",
            "sleep": "Sleep",
        }
        for animation, group in expected_groups.items():
            with self.subTest(animation=animation):
                rendering = self.resolver.resolve(
                    {"animation": animation, "fallback_expression": "joy"}
                )
                self.assertIsNotNone(rendering.motion)
                self.assertEqual(rendering.motion.group, group)
                self.assertFalse(rendering.degraded)
                self.assertEqual(rendering.reason, REASON_NATIVE_MOTION)
                self.assertIsNone(rendering.missing_motion_asset)
                self.assertEqual(rendering.expression.name, "exp_04")

    def test_missing_art_is_reported_for_planned_interactions(self) -> None:
        self.assertEqual(
            self.resolver.missing_motion_assets(),
            [],
        )

    def test_generated_motion_files_use_real_parameters_and_valid_metadata(self) -> None:
        runtime = PROJECT_ROOT / "live2d-models" / "mao_pro" / "runtime"
        display_info = json.loads(
            (runtime / "mao_pro.cdi3.json").read_text(encoding="utf-8")
        )
        parameter_ids = {item["Id"] for item in display_info["Parameters"]}
        expected_loops = {
            "eat_01.motion3.json": False,
            "play_01.motion3.json": False,
            "clean_01.motion3.json": False,
            "sleep_enter.motion3.json": False,
            "sleep_idle.motion3.json": True,
            "wake_01.motion3.json": False,
        }

        for filename, should_loop in expected_loops.items():
            with self.subTest(filename=filename):
                motion = json.loads(
                    (runtime / "motions" / filename).read_text(encoding="utf-8")
                )
                curves = motion["Curves"]
                segment_count = 0
                point_count = 0
                for curve in curves:
                    self.assertIn(curve["Id"], parameter_ids)
                    segments = curve["Segments"]
                    cursor = 2
                    points = 1
                    while cursor < len(segments):
                        segment_type = segments[cursor]
                        cursor += 1
                        cursor += 6 if segment_type == 1 else 2
                        segment_count += 1
                        points += 1
                    self.assertEqual(cursor, len(segments))
                    point_count += points

                meta = motion["Meta"]
                self.assertEqual(meta["CurveCount"], len(curves))
                self.assertEqual(meta["TotalSegmentCount"], segment_count)
                self.assertEqual(meta["TotalPointCount"], point_count)
                self.assertEqual(meta["Loop"], should_loop)


class ReactionResolutionTests(unittest.TestCase):
    def test_native_motion_is_used_when_the_model_ships_one(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = _write_model(
                Path(raw_root),
                motions={
                    "Idle": [{"File": "motions/idle_01.motion3.json"}],
                    "Action": [
                        {"File": "motions/wave_01.motion3.json"},
                        {"File": "motions/eat_01.motion3.json"},
                    ],
                },
                expressions=["exp_01", "exp_02", "exp_03", "exp_04"],
                emotion_map={"neutral": 0, "joy": 3},
            )
            resolver = Live2dReactionResolver.from_model_name(
                "probe", project_root=root
            )

            rendering = resolver.resolve(
                {"animation": "eat", "fallback_expression": "joy"}
            )

        self.assertFalse(rendering.degraded)
        self.assertEqual(rendering.reason, REASON_NATIVE_MOTION)
        self.assertEqual(rendering.motion.group, "Action")
        self.assertEqual(rendering.motion.index, 1)
        self.assertEqual(rendering.motion.name, "eat_01")
        # The fallback expression is still reported so the client can combine
        # the motion with a matching face.
        self.assertEqual(rendering.expression.name, "exp_04")

    def test_unknown_fallback_expression_degrades_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = _write_model(
                Path(raw_root),
                motions={"Idle": [{"File": "motions/idle_01.motion3.json"}]},
                expressions=["exp_01"],
                emotion_map={"neutral": 0},
            )
            resolver = Live2dReactionResolver.from_model_name(
                "probe", project_root=root
            )

            rendering = resolver.resolve(
                {"animation": "eat", "fallback_expression": "ecstatic"}
            )

        self.assertIsNone(rendering.motion)
        self.assertIsNone(rendering.expression)
        self.assertTrue(rendering.degraded)
        self.assertEqual(rendering.reason, REASON_NO_EXPRESSION)

    def test_missing_model_assets_never_break_a_reaction(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            resolver = Live2dReactionResolver.from_model_name(
                "absent", project_root=Path(raw_root)
            )

            rendering = resolver.resolve(
                {"animation": "eat", "fallback_expression": "joy"}
            )

        self.assertFalse(resolver.available)
        self.assertIsNotNone(resolver.error)
        self.assertEqual(rendering.reason, REASON_MODEL_UNAVAILABLE)
        self.assertIsNone(rendering.motion)
        self.assertIsNone(rendering.expression)

    def test_capabilities_expose_no_filesystem_paths(self) -> None:
        resolver = Live2dReactionResolver.from_model_name(
            "mao_pro", project_root=PROJECT_ROOT
        )

        serialised = json.dumps(resolver.capabilities, ensure_ascii=False)

        self.assertNotIn(str(PROJECT_ROOT), serialised)


class ReactionMessageDecorationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = Live2dReactionResolver.from_model_name(
            "mao_pro", project_root=PROJECT_ROOT
        )

    def test_only_reaction_messages_are_decorated(self) -> None:
        messages = [
            {"type": "pet_state_changed", "event_id": "e1", "state": {}},
            {
                "type": "pet_reaction",
                "event_id": "e1",
                "reaction": {"animation": "eat", "fallback_expression": "joy"},
            },
        ]

        decorated = decorate_reaction_messages(messages, self.resolver)

        self.assertNotIn("render", decorated[0])
        self.assertEqual(decorated[1]["render"]["expression"]["name"], "exp_04")
        self.assertFalse(decorated[1]["render"]["degraded"])
        self.assertEqual(decorated[1]["render"]["motion"]["group"], "Eat")
        # Schema v1 stays intact: the original reaction is never rewritten.
        self.assertEqual(decorated[1]["reaction"]["animation"], "eat")

    def test_payload_is_omitted_without_a_resolver(self) -> None:
        self.assertIsNone(render_payload({"animation": "eat"}, None))
        self.assertIsNone(render_payload(None, self.resolver))


@unittest.skipUnless(FASTAPI_AVAILABLE, "FastAPI is required for route tests")
class PetRouteRenderTests(unittest.TestCase):
    """The HTTP and WebSocket surfaces carry the resolved rendering plan."""

    def setUp(self) -> None:
        from open_llm_vtuber.pet_domain import PetStateRepository, PetStateService
        from open_llm_vtuber.pet_routes import init_pet_routes

        test_temp_root = Path.cwd() / "tmp" / "tests"
        test_temp_root.mkdir(parents=True, exist_ok=True)
        self.database_path = test_temp_root / f"pet-live2d-{uuid4()}.db"
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
                live2d_resolver=Live2dReactionResolver.from_model_name(
                    "mao_pro", project_root=PROJECT_ROOT
                ),
            )
        )
        self.client = TestClient(app)

    def test_state_endpoint_reports_live2d_capabilities(self) -> None:
        payload = self.client.get("/api/pet/state").json()

        self.assertEqual(payload["live2d"]["model"], "mao_pro")
        self.assertIn("exp_04", payload["live2d"]["expressions"])
        self.assertEqual(payload["live2d"]["missing_motion_assets"], [])

    def test_feed_response_carries_the_render_plan(self) -> None:
        result = self.client.post(
            "/api/pet/feed",
            json={"food": "小鱼干", "request_id": f"render-{uuid4()}"},
        ).json()

        self.assertEqual(result["render"]["animation"], "eat")
        self.assertEqual(result["render"]["motion"]["group"], "Eat")
        self.assertEqual(result["render"]["reason"], REASON_NATIVE_MOTION)
        self.assertEqual(result["render"]["expression"]["name"], "exp_04")

    def test_event_stream_carries_the_same_render_plan(self) -> None:
        with self.client.websocket_connect("/api/pet/events?user_id=default") as events:
            events.receive_json()
            response = self.client.post(
                "/api/pet/feed",
                json={"food": "小鱼干", "request_id": f"render-ws-{uuid4()}"},
            ).json()

            events.receive_json()  # pet_state_changed
            reaction_event = events.receive_json()

        self.assertEqual(reaction_event["type"], "pet_reaction")
        self.assertEqual(reaction_event["event_id"], response["event_id"])
        self.assertEqual(reaction_event["render"], response["render"])


if __name__ == "__main__":
    unittest.main()

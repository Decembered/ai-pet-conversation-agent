"""Head-bubble speech projection: filtering, fan-out and the recent buffer."""

from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from open_llm_vtuber.pet_speech import (
    MAX_SPEECH_CHARS,
    PetSpeechBroadcaster,
    clean_speech_text,
)

try:  # pragma: no cover - exercised implicitly by the skip decorator
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    FASTAPI_AVAILABLE = False


class SpeechTextTests(unittest.TestCase):
    def test_control_tags_never_reach_the_bubble(self) -> None:
        self.assertEqual(
            clean_speech_text("[joy] 今天也要闪闪发光！"), "今天也要闪闪发光！"
        )
        self.assertEqual(clean_speech_text("好呀[neutral]我在听"), "好呀我在听")

    def test_chinese_brackets_are_preserved(self) -> None:
        self.assertEqual(clean_speech_text("我在读《小王子》"), "我在读《小王子》")
        self.assertEqual(clean_speech_text("「早安」"), "「早安」")

    def test_non_string_input_is_tolerated(self) -> None:
        self.assertEqual(clean_speech_text(None), "")
        self.assertEqual(clean_speech_text(42), "")


class BroadcasterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.broadcaster = PetSpeechBroadcaster(history_limit=5, queue_size=3)

    async def test_subscribers_receive_published_sentences(self) -> None:
        queue = self.broadcaster.subscribe()

        message = self.broadcaster.publish("[joy]主人早安", name="小光")

        delivered = await asyncio.wait_for(queue.get(), timeout=1)
        self.assertEqual(delivered, message)
        self.assertEqual(delivered["type"], "pet_speech")
        self.assertEqual(delivered["text"], "主人早安")
        self.assertEqual(delivered["name"], "小光")
        self.assertEqual(delivered["sequence"], 1)

    async def test_empty_sentences_are_dropped(self) -> None:
        queue = self.broadcaster.subscribe()

        self.assertIsNone(self.broadcaster.publish("   "))
        self.assertIsNone(self.broadcaster.publish("[joy]"))

        self.assertTrue(queue.empty())
        self.assertEqual(self.broadcaster.recent(), [])

    async def test_a_slow_subscriber_loses_the_oldest_sentence_not_the_newest(
        self,
    ) -> None:
        queue = self.broadcaster.subscribe()
        for index in range(5):
            self.broadcaster.publish(f"第{index}句")

        drained = []
        while not queue.empty():
            drained.append(queue.get_nowait()["text"])

        # queue_size is 3: the newest sentences survive, the pipeline never blocks.
        self.assertEqual(drained, ["第2句", "第3句", "第4句"])

    async def test_unsubscribe_stops_delivery(self) -> None:
        queue = self.broadcaster.subscribe()
        self.broadcaster.unsubscribe(queue)

        self.broadcaster.publish("还在吗")

        self.assertTrue(queue.empty())
        self.assertEqual(self.broadcaster.subscriber_count, 0)

    async def test_long_sentences_are_truncated_and_flagged(self) -> None:
        message = self.broadcaster.publish("啦" * (MAX_SPEECH_CHARS + 20))

        self.assertTrue(message["truncated"])
        self.assertEqual(len(message["text"]), MAX_SPEECH_CHARS)

    async def test_recent_is_a_bounded_display_buffer(self) -> None:
        for index in range(8):
            self.broadcaster.publish(f"第{index}句")

        recent = self.broadcaster.recent(limit=3)

        self.assertEqual([item["text"] for item in recent], ["第5句", "第6句", "第7句"])
        # history_limit is 5, so the buffer never grows without bound.
        self.assertEqual(len(self.broadcaster.recent(limit=50)), 5)

    async def test_only_audio_payloads_with_display_text_are_published(self) -> None:
        self.assertIsNone(self.broadcaster.publish_display_payload({"type": "control"}))
        self.assertIsNone(
            self.broadcaster.publish_display_payload({"type": "audio", "audio": None})
        )
        self.assertIsNone(self.broadcaster.publish_display_payload("not a payload"))

        message = self.broadcaster.publish_display_payload(
            {
                "type": "audio",
                "audio": "…",
                "display_text": {"text": "[joy]好呀！", "name": "小光"},
            }
        )

        self.assertEqual(message["text"], "好呀！")
        self.assertEqual(message["name"], "小光")

    async def test_camera_frames_never_enter_the_speech_stream(self) -> None:
        """Privacy guard: only the spoken text may leave the pipeline here."""

        message = self.broadcaster.publish_display_payload(
            {
                "type": "audio",
                "audio": "…",
                "display_text": {"text": "我好像看到了一只猫", "name": "小光"},
                "images": ["data:image/png;base64,AAAACAMERAFRAME"],
                "actions": {"pictures": ["data:image/png;base64,BBBBCAMERAFRAME"]},
            }
        )

        self.assertEqual(
            set(message),
            {
                "type",
                "schema_version",
                "sequence",
                "text",
                "name",
                "truncated",
                "occurred_at",
            },
        )
        serialised = json.dumps(message, ensure_ascii=False)
        self.assertNotIn("base64", serialised)
        self.assertNotIn("CAMERAFRAME", serialised)
        self.assertNotIn(
            "base64", json.dumps(self.broadcaster.recent(), ensure_ascii=False)
        )


@unittest.skipUnless(FASTAPI_AVAILABLE, "FastAPI is required for route tests")
class SpeechRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        from open_llm_vtuber.pet_domain import PetStateRepository, PetStateService
        from open_llm_vtuber.pet_routes import init_pet_routes

        test_temp_root = Path.cwd() / "tmp" / "tests"
        test_temp_root.mkdir(parents=True, exist_ok=True)
        self.database_path = test_temp_root / f"pet-speech-{uuid4()}.db"
        self.addCleanup(self.database_path.unlink, missing_ok=True)
        self.broadcaster = PetSpeechBroadcaster()
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
                service=PetStateService(PetStateRepository(self.database_path)),
                event_poll_interval=0.01,
                speech_broadcaster=self.broadcaster,
            )
        )
        self.client = TestClient(app)

    def test_recent_endpoint_returns_the_display_buffer(self) -> None:
        self.broadcaster.publish("[joy]主人早安", name="小光")

        payload = self.client.get("/api/pet/speech/recent?limit=5").json()

        self.assertTrue(payload["success"])
        self.assertEqual(payload["kind"], "recent_conversation")
        self.assertEqual(payload["items"][0]["text"], "主人早安")

    def test_speech_reaches_the_pet_event_stream(self) -> None:
        with self.client.websocket_connect("/api/pet/events?user_id=default") as events:
            events.receive_json()  # pet_events_ready
            self.broadcaster.publish("我在这儿哦", name="小光")

            message = events.receive_json()

        self.assertEqual(message["type"], "pet_speech")
        self.assertEqual(message["text"], "我在这儿哦")

    def test_subscription_is_released_when_the_socket_closes(self) -> None:
        with self.client.websocket_connect("/api/pet/events?user_id=default") as events:
            events.receive_json()
            self.assertEqual(self.broadcaster.subscriber_count, 1)

        self.assertEqual(self.broadcaster.subscriber_count, 0)


if __name__ == "__main__":
    unittest.main()

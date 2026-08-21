"""Regression tests for smooth sentence-level TTS streaming."""

from __future__ import annotations

import asyncio
import unittest

from open_llm_vtuber.agent.output_types import Actions, DisplayText, SentenceOutput
from open_llm_vtuber.agent.transformers import merge_short_sentences


class TTSSmoothingTests(unittest.TestCase):
    def test_short_sentences_are_merged_into_one_audio_unit(self) -> None:
        async def source():
            yield self._output("你好呀！", [3])
            yield self._output("晚上好！", [0])
            yield self._output("今天过得怎么样？", [3])

        async def collect():
            pipeline = merge_short_sentences(min_tts_chars=12)(source)
            return [item async for item in pipeline()]

        results = asyncio.run(collect())

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0].display_text.text, "你好呀！晚上好！今天过得怎么样？"
        )
        self.assertEqual(results[0].tts_text, "你好呀！晚上好！今天过得怎么样？")
        self.assertEqual(results[0].actions.expressions, [3, 0])

    def test_long_sentence_is_streamed_without_waiting_for_next_one(self) -> None:
        long_text = "这是一句足够长、可以立即开始合成语音的回复。"

        async def source():
            yield self._output(long_text, [3])
            raise AssertionError("the transformer consumed beyond the ready output")

        async def first_item():
            pipeline = merge_short_sentences(min_tts_chars=12)(source)
            return await anext(pipeline())

        result = asyncio.run(first_item())
        self.assertEqual(result.tts_text, long_text)

    @staticmethod
    def _output(text: str, expressions: list[int]) -> SentenceOutput:
        return SentenceOutput(
            display_text=DisplayText(text=text),
            tts_text=text,
            actions=Actions(expressions=expressions),
        )


if __name__ == "__main__":
    unittest.main()

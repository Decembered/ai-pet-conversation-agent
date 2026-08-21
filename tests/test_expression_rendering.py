"""Regression tests for Live2D control tags in visible dialogue."""

from __future__ import annotations

import asyncio
import unittest

from open_llm_vtuber.agent.transformers import actions_extractor, display_processor
from open_llm_vtuber.live2d_model import Live2dModel
from open_llm_vtuber.utils.sentence_divider import (
    SentenceWithTags,
    TagInfo,
    TagState,
)


class ExpressionRenderingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.model = Live2dModel("mao_pro")

    def test_expression_tags_drive_actions_but_are_hidden_from_text(self) -> None:
        async def source():
            yield SentenceWithTags(
                text="你好呀！ [joy] 今天过得怎么样？ [neutral]",
                tags=[TagInfo("", TagState.NONE)],
            )

        pipeline = display_processor(self.model)(actions_extractor(self.model)(source))

        async def collect():
            return [item async for item in pipeline()]

        results = asyncio.run(collect())
        _, display, actions = results[0]

        self.assertEqual(display.text, "你好呀！ 今天过得怎么样？")
        self.assertEqual(actions.expressions, [3, 0])

    def test_expression_removal_is_case_insensitive(self) -> None:
        self.assertEqual(
            self.model.remove_emotion_keywords("[JOY] 闪闪发光！"),
            "闪闪发光！",
        )


if __name__ == "__main__":
    unittest.main()

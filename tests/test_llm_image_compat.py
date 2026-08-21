"""Tests for text-only OpenAI-compatible model input handling."""

from __future__ import annotations

import unittest

from open_llm_vtuber.agent.stateless_llm.openai_compatible_llm import AsyncLLM
from open_llm_vtuber.config_manager.stateless_llm import OpenAICompatibleConfig


class LLMImageCompatibilityTests(unittest.TestCase):
    def test_images_are_removed_but_text_and_metadata_are_preserved(self) -> None:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "帮我看看当前状态"},
                    {
                        "type": "image_url",
                        "image_url": {"url": "data:image/jpeg;base64,secret-image"},
                    },
                ],
                "name": "owner",
            },
            {"role": "assistant", "content": "好的"},
        ]

        sanitized = AsyncLLM._without_images(messages)

        self.assertEqual(sanitized[0]["content"], "帮我看看当前状态")
        self.assertEqual(sanitized[0]["name"], "owner")
        self.assertEqual(sanitized[1]["content"], "好的")
        self.assertNotIn("secret-image", str(sanitized))
        self.assertIsInstance(messages[0]["content"], list)

    def test_vision_capability_is_configurable(self) -> None:
        config = OpenAICompatibleConfig(
            base_url="https://example.invalid/v1",
            llm_api_key="test-only",
            model="text-model",
            supports_vision=False,
        )

        self.assertFalse(config.supports_vision)


if __name__ == "__main__":
    unittest.main()

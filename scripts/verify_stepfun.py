"""Verify the configured StepFun endpoint without printing credentials/content."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
from pathlib import Path

from open_llm_vtuber.agent.stateless_llm_factory import LLMFactory
from open_llm_vtuber.config_manager import read_yaml, validate_config


async def main() -> None:
    config = validate_config(read_yaml("conf.yaml"))
    agent_config = config.character_config.agent_config
    basic_config = agent_config.agent_settings.basic_memory_agent
    llm_config = agent_config.llm_configs.openai_compatible_llm
    llm = LLMFactory.create_llm(
        basic_config.llm_provider,
        **llm_config.model_dump(),
    )
    image_path = Path("avatars/mao.png")
    image_mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
    image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Reply with exactly: API connected"},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image_mime};base64,{image_data}",
                        "detail": "low",
                    },
                },
            ],
        }
    ]
    chunks: list[str] = []
    async for part in llm.chat_completion(messages):
        if isinstance(part, str):
            chunks.append(part)
    response = "".join(chunks).strip()
    print(
        {
            "stepfun_ok": bool(response)
            and not response.startswith("Error calling the chat endpoint"),
            "vision_enabled": llm.supports_vision,
            "response_chars": len(response),
        }
    )


if __name__ == "__main__":
    asyncio.run(main())

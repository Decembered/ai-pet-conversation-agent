"""Fan out the pet's spoken sentences to the pet event stream.

The conversation pipeline already produces a filtered ``display_text`` for every
sentence it sends to the browser. Phase C projects that same text into the head
bubble, so the bubble and the chat history always show the same words and the
internal ``[joy]`` style control tags never leak into either.

This module is deliberately small and dependency free: it is an in-process
fan-out, not a message broker. Publishing must never raise and never block the
conversation, so a slow or dead subscriber loses the oldest queued sentence
instead of stalling the pipeline.
"""

from __future__ import annotations

import asyncio
import re
from collections import deque
from datetime import datetime, timezone
from typing import Any, Mapping

PET_SPEECH_SCHEMA_VERSION = "1.0"

#: Longest sentence kept for the bubble and the drawer. Anything longer is
#: truncated and flagged, so the UI never has to guess.
MAX_SPEECH_CHARS = 400

# Defence in depth: the transformers layer already removes emotion tags, but the
# bubble must never show one if a new tag style slips through.
_CONTROL_TAG = re.compile(r"\[[A-Za-z_][A-Za-z0-9_]*\]")
_WHITESPACE = re.compile(r"[ \t]{2,}")


def clean_speech_text(text: str) -> str:
    """Strip control tags and normalise whitespace for display."""

    if not isinstance(text, str):
        return ""
    without_tags = _CONTROL_TAG.sub("", text)
    return _WHITESPACE.sub(" ", without_tags).strip()


class PetSpeechBroadcaster:
    """In-process pub/sub for the sentences the pet just said."""

    def __init__(self, history_limit: int = 30, queue_size: int = 64) -> None:
        self.history_limit = history_limit
        self.queue_size = queue_size
        self._history: deque[dict[str, Any]] = deque(maxlen=history_limit)
        self._subscribers: list[asyncio.Queue] = []
        self._sequence = 0

    # ------------------------------------------------------------------
    # subscription
    # ------------------------------------------------------------------
    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=self.queue_size)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    # ------------------------------------------------------------------
    # publishing
    # ------------------------------------------------------------------
    def publish(self, text: str, name: str | None = None) -> dict[str, Any] | None:
        """Publish one spoken sentence; returns the message, or None if empty."""

        cleaned = clean_speech_text(text)
        if not cleaned:
            return None

        truncated = len(cleaned) > MAX_SPEECH_CHARS
        if truncated:
            cleaned = cleaned[:MAX_SPEECH_CHARS]

        self._sequence += 1
        message = {
            "type": "pet_speech",
            "schema_version": PET_SPEECH_SCHEMA_VERSION,
            "sequence": self._sequence,
            "text": cleaned,
            "name": name or "",
            "truncated": truncated,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }
        self._history.append(message)

        for queue in list(self._subscribers):
            self._offer(queue, message)
        return message

    def publish_display_payload(
        self, payload: Mapping[str, Any]
    ) -> dict[str, Any] | None:
        """Publish from an outgoing ``audio`` payload, ignoring anything else."""

        try:
            if not isinstance(payload, Mapping) or payload.get("type") != "audio":
                return None
            display_text = payload.get("display_text")
            if not isinstance(display_text, Mapping):
                return None
            return self.publish(
                text=str(display_text.get("text", "")),
                name=str(display_text.get("name", "") or ""),
            )
        except Exception:
            # A bubble is never worth breaking a conversation for.
            return None

    @staticmethod
    def _offer(queue: asyncio.Queue, message: dict[str, Any]) -> None:
        """Deliver without blocking; drop the oldest item when a client lags."""

        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            try:
                queue.get_nowait()
                queue.put_nowait(message)
            except (asyncio.QueueEmpty, asyncio.QueueFull):
                pass

    # ------------------------------------------------------------------
    # history
    # ------------------------------------------------------------------
    def recent(self, limit: int = 10) -> list[dict[str, Any]]:
        """Most recent sentences, oldest first.

        This is a short display buffer for the drawer's "recent conversation"
        panel. It is explicitly **not** long-term memory: nothing here is
        summarised, scored or persisted.
        """

        if limit <= 0:
            return []
        items = list(self._history)
        return items[-limit:]

    def reset(self) -> None:
        self._history.clear()
        self._subscribers.clear()
        self._sequence = 0


#: Process-wide broadcaster used by the conversation pipeline and the routes.
pet_speech_broadcaster = PetSpeechBroadcaster()

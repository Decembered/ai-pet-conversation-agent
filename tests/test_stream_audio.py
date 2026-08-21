"""Tests for audio payload conversion without external ffmpeg binaries."""

from __future__ import annotations

import base64
import math
import struct
import unittest
import wave
from pathlib import Path
from uuid import uuid4

from open_llm_vtuber.utils.stream_audio import prepare_audio_payload


class StreamAudioTests(unittest.TestCase):
    def test_wav_is_encoded_with_normalized_volume_chunks(self) -> None:
        test_temp_root = Path.cwd() / "tmp" / "tests"
        test_temp_root.mkdir(parents=True, exist_ok=True)
        audio_path = test_temp_root / f"audio-{uuid4()}.wav"
        self.addCleanup(audio_path.unlink, missing_ok=True)
        sample_rate = 16_000
        with wave.open(str(audio_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            samples = (
                int(12_000 * math.sin(2 * math.pi * 440 * index / sample_rate))
                for index in range(sample_rate // 5)
            )
            wav_file.writeframes(
                b"".join(struct.pack("<h", value) for value in samples)
            )

        payload = prepare_audio_payload(str(audio_path), chunk_length_ms=20)
        wav_bytes = base64.b64decode(payload["audio"])

        self.assertEqual(wav_bytes[:4], b"RIFF")
        self.assertGreater(len(payload["volumes"]), 1)
        self.assertAlmostEqual(max(payload["volumes"]), 1.0)


if __name__ == "__main__":
    unittest.main()

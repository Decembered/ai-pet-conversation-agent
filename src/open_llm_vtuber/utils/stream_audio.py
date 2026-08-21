import base64
from io import BytesIO
from typing import TYPE_CHECKING

import numpy as np
import soundfile as sf
from ..agent.output_types import Actions
from ..agent.output_types import DisplayText

if TYPE_CHECKING:
    from pydub import AudioSegment


def _get_volume_by_chunks(audio: "AudioSegment", chunk_length_ms: int) -> list:
    """
    Calculate the normalized volume (RMS) for each chunk of the audio.

    Parameters:
        audio (AudioSegment): The audio segment to process.
        chunk_length_ms (int): The length of each audio chunk in milliseconds.

    Returns:
        list: Normalized volumes for each chunk.
    """
    from pydub.utils import make_chunks

    chunks = make_chunks(audio, chunk_length_ms)
    volumes = [chunk.rms for chunk in chunks]
    max_volume = max(volumes)
    if max_volume == 0:
        raise ValueError("Audio is empty or all zero.")
    return [volume / max_volume for volume in volumes]


def _decode_with_soundfile(
    audio_path: str, chunk_length_ms: int
) -> tuple[bytes, list[float]]:
    """Decode common audio formats without requiring external ffmpeg binaries."""

    samples, sample_rate = sf.read(audio_path, dtype="float32", always_2d=True)
    wav_buffer = BytesIO()
    sf.write(wav_buffer, samples, sample_rate, format="WAV", subtype="PCM_16")

    frames_per_chunk = max(1, int(sample_rate * chunk_length_ms / 1000))
    volumes = []
    for start in range(0, len(samples), frames_per_chunk):
        chunk = samples[start : start + frames_per_chunk]
        volumes.append(float(np.sqrt(np.mean(np.square(chunk), dtype=np.float64))))
    max_volume = max(volumes, default=0.0)
    if max_volume <= 0:
        raise ValueError("Audio is empty or all zero.")
    return wav_buffer.getvalue(), [volume / max_volume for volume in volumes]


def prepare_audio_payload(
    audio_path: str | None,
    chunk_length_ms: int = 20,
    display_text: DisplayText = None,
    actions: Actions = None,
    forwarded: bool = False,
) -> dict[str, any]:
    """
    Prepares the audio payload for sending to a broadcast endpoint.
    If audio_path is None, returns a payload with audio=None for silent display.

    Parameters:
        audio_path (str | None): The path to the audio file to be processed, or None for silent display
        chunk_length_ms (int): The length of each audio chunk in milliseconds
        display_text (DisplayText, optional): Text to be displayed with the audio
        actions (Actions, optional): Actions associated with the audio

    Returns:
        dict: The audio payload to be sent
    """
    if isinstance(display_text, DisplayText):
        display_text = display_text.to_dict()

    if not audio_path:
        # Return payload for silent display
        return {
            "type": "audio",
            "audio": None,
            "volumes": [],
            "slice_length": chunk_length_ms,
            "display_text": display_text,
            "actions": actions.to_dict() if actions else None,
            "forwarded": forwarded,
        }

    try:
        audio_bytes, volumes = _decode_with_soundfile(audio_path, chunk_length_ms)
    except Exception as soundfile_error:
        try:
            from pydub import AudioSegment

            audio = AudioSegment.from_file(audio_path)
            audio_bytes = audio.export(format="wav").read()
            volumes = _get_volume_by_chunks(audio, chunk_length_ms)
        except Exception as pydub_error:
            raise ValueError(
                "Error loading or converting generated audio file to wav file "
                f"'{audio_path}': soundfile={soundfile_error}; pydub={pydub_error}"
            ) from pydub_error
    audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")

    payload = {
        "type": "audio",
        "audio": audio_base64,
        "volumes": volumes,
        "slice_length": chunk_length_ms,
        "display_text": display_text,
        "actions": actions.to_dict() if actions else None,
        "forwarded": forwarded,
    }

    return payload


# Example usage:
# payload, duration = prepare_audio_payload("path/to/audio.mp3", display_text="Hello", expression_list=[0,1,2])

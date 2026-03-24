"""Speech-to-Text using OpenAI Whisper API."""

from __future__ import annotations

import io
import logging
from pathlib import Path

from openai import OpenAI

import config

logger = logging.getLogger(__name__)

MAX_AUDIO_SIZE = 25 * 1024 * 1024  # 25 MB (Whisper API limit)


def transcribe_audio(audio_bytes: bytes, client: OpenAI | None = None, filename: str = "audio.wav") -> str:
    """Transcribe audio bytes to text using OpenAI Whisper.

    Args:
        audio_bytes: Raw audio data (wav, mp3, m4a, etc.)
        client: OpenAI client instance.
        filename: Filename hint for the API (affects format detection).

    Returns:
        Transcribed text string, or empty string on failure.
    """
    if not audio_bytes:
        return ""
    if len(audio_bytes) > MAX_AUDIO_SIZE:
        logger.error("Audio file too large: %.1f MB (limit: 25 MB)", len(audio_bytes) / 1024 / 1024)
        return ""
    client = client or OpenAI(api_key=config.OPENAI_API_KEY)
    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        return transcript.text.strip()
    except Exception as e:
        logger.error("STT transcription failed: %s", e)
        return ""

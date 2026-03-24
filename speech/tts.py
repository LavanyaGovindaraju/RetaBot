"""Text-to-Speech using edge-tts (free, no API key required)."""

from __future__ import annotations

import asyncio
import io
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


async def _synthesize(text: str, voice: str) -> bytes:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


def text_to_speech(text: str, voice: str = "en-US-JennyNeural") -> bytes:
    """Convert text to speech audio bytes (MP3).

    Returns raw MP3 bytes that can be played or saved.
    """
    if not text or not text.strip():
        return b""
    try:
        # Handle case where an event loop is already running (e.g. in Streamlit)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                audio_bytes = pool.submit(asyncio.run, _synthesize(text, voice)).result()
        else:
            audio_bytes = asyncio.run(_synthesize(text, voice))
        return audio_bytes
    except Exception as e:
        logger.error("TTS failed: %s", e)
        return b""


def save_tts(text: str, output_path: str | Path, voice: str = "en-US-JennyNeural") -> Path:
    """Generate speech and save to a file."""
    audio = text_to_speech(text, voice)
    path = Path(output_path)
    path.write_bytes(audio)
    return path

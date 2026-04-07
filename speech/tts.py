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


def _run_synthesis(text: str, voice: str) -> bytes:
    """Run async synthesis in a dedicated thread with its own event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_synthesize(text, voice))
    finally:
        loop.close()


def text_to_speech(text: str, voice: str = "en-US-JennyNeural") -> bytes:
    """Convert text to speech audio bytes (MP3).

    Returns raw MP3 bytes that can be played or saved.
    Always runs in a separate thread with its own event loop to avoid
    conflicts with Streamlit's running event loop on Windows.
    """
    if not text or not text.strip():
        return b""
    try:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_run_synthesis, text, voice)
            return future.result(timeout=30)
    except Exception as e:
        logger.error("TTS failed: %s", e)
        return b""


def save_tts(text: str, output_path: str | Path, voice: str = "en-US-JennyNeural") -> Path:
    """Generate speech and save to a file."""
    audio = text_to_speech(text, voice)
    path = Path(output_path)
    path.write_bytes(audio)
    return path

"""Speech-to-text orchestration for reviewed user recordings."""
from __future__ import annotations

from ai_eod_assistant.ai.base import AIProvider


def transcribe_audio(provider: AIProvider, audio: bytes, mime_type: str = "audio/wav") -> str:
    """Transcribe a recording through a provider that supports audio input."""
    transcriber = getattr(provider, "transcribe_audio", None)
    if not callable(transcriber):
        raise RuntimeError("The configured AI provider does not support audio transcription.")
    return str(transcriber(audio, mime_type)).strip()

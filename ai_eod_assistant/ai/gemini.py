"""Gemini API provider implementation."""
from __future__ import annotations

from ai_eod_assistant.ai.base import AIProvider


class GeminiProvider(AIProvider):
    """Gemini-backed implementation of the AIProvider interface."""

    name = "gemini"

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("Gemini API key is required.")
        self.model = model
        from google import genai

        self._client = genai.Client(api_key=api_key)

    def generate(self, prompt: str) -> str:
        response = self._client.models.generate_content(model=self.model, contents=prompt)
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini returned an empty response.")
        return text.strip()

    def transcribe_audio(self, audio: bytes, mime_type: str = "audio/wav") -> str:
        """Transcribe a user-recorded audio clip without inferring missing details."""
        if not audio:
            raise ValueError("Audio data is required for transcription.")
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.model,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=audio, mime_type=mime_type),
                        types.Part.from_text(
                            text=(
                                "Transcribe this user-recorded audio exactly. Return only the "
                                "transcript. Do not summarize, interpret, or add work that was not spoken."
                            )
                        ),
                    ],
                )
            ],
        )
        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini returned an empty transcription.")
        return text.strip()

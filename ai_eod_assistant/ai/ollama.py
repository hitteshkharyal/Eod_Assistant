"""Local Ollama provider for offline EOD generation."""
from __future__ import annotations

import json
from urllib import error, request

from ai_eod_assistant.ai.base import AIProvider


class OllamaProvider(AIProvider):
    """Generate text through an Ollama server running on the user's machine."""

    name = "ollama"

    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434") -> None:
        if not model.strip():
            raise ValueError("An Ollama model name is required.")
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt: str) -> str:
        payload = json.dumps({"model": self.model, "prompt": prompt, "stream": False}).encode("utf-8")
        call = request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(call, timeout=180) as response:
                result = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(
                f"Could not connect to Ollama at {self.base_url}. Start Ollama and run: ollama pull {self.model}"
            ) from exc
        text = str(result.get("response", "")).strip()
        if not text:
            raise RuntimeError("Ollama returned an empty response.")
        return text

    def transcribe_audio(self, audio: bytes, mime_type: str = "audio/wav") -> str:
        raise RuntimeError(
            "Offline audio transcription requires a local audio-capable model. "
            "Use text input or select Online for Gemini STT."
        )
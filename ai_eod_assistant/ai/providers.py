"""Factory for the configured online or offline AI provider."""
from __future__ import annotations

from ai_eod_assistant.ai.base import AIProvider
from ai_eod_assistant.ai.gemini import GeminiProvider
from ai_eod_assistant.ai.ollama import OllamaProvider


def build_provider(
    mode: str,
    *,
    gemini_api_key: str | None,
    model: str,
    ollama_base_url: str,
) -> AIProvider:
    """Create the selected provider and fail clearly when configuration is missing."""
    if mode == "Offline (Ollama)":
        return OllamaProvider(model=model, base_url=ollama_base_url)
    if not gemini_api_key:
        raise ValueError("Add GEMINI_API_KEY in Settings before using the online provider.")
    return GeminiProvider(api_key=gemini_api_key, model=model)
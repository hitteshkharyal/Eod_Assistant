"""AI provider abstractions."""
from __future__ import annotations

from abc import ABC, abstractmethod


class AIProvider(ABC):
    """Interface for online and future offline AI providers."""

    name: str

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate text from a prompt."""

    def summarize(self, content: str) -> str:
        """Summarize text using the provider."""
        return self.generate(f"Summarize this work evidence clearly and factually:\n\n{content}")

    def analyze(self, content: str) -> str:
        """Analyze text using the provider."""
        return self.generate(f"Analyze this work evidence. Separate confirmed facts from uncertainty:\n\n{content}")

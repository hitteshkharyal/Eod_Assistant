"""EOD report generation orchestration."""
from __future__ import annotations

from datetime import date

from ai_eod_assistant.ai.base import AIProvider
from ai_eod_assistant.ai.prompts import build_eod_prompt


class EODGenerator:
    """Builds prompts and delegates generation to the configured AI provider."""

    def __init__(self, provider: AIProvider) -> None:
        self.provider = provider

    def generate_report(self, report_date: date, evidence: str) -> str:
        prompt = build_eod_prompt(report_date, evidence)
        return self.provider.generate(prompt)

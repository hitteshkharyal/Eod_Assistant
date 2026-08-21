from __future__ import annotations

import re
import sqlite3
from datetime import date
from pathlib import Path

from ai_eod_assistant.ai.base import AIProvider
from ai_eod_assistant.ai.prompts import build_eod_prompt
from ai_eod_assistant.backend.eod_service import EODService
from ai_eod_assistant.database.db import initialize_database

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


class SnapshotProvider(AIProvider):
    name = "snapshot-provider"

    def generate(self, prompt: str) -> str:
        assert normalize_timestamps(prompt) == (SNAPSHOT_DIR / "eod_prompt.txt").read_text(encoding="utf-8") + "\n"
        return (SNAPSHOT_DIR / "eod_report.md").read_text(encoding="utf-8")


def memory_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_database(connection)
    return connection


def normalize_timestamps(value: str) -> str:
    return re.sub(r"\[\d{4}-\d{2}-\d{2}T[^\]]+\]", "[TIMESTAMP]", value)


def test_eod_prompt_snapshot() -> None:
    prompt = build_eod_prompt(date(2026, 8, 19), "Confirmed user-provided text evidence:\n- [TIMESTAMP] Completed backend service layer.")
    assert prompt == (SNAPSHOT_DIR / "eod_prompt.txt").read_text(encoding="utf-8") + "\n"


def test_backend_eod_generation_snapshot() -> None:
    with memory_connection() as connection:
        service = EODService(connection)
        saved = service.add_text_activity("Completed backend service layer.")
        report_date = date(2026, 8, 19)
        connection.execute("UPDATE user_inputs SET timestamp = ? WHERE id = ?", (f"{report_date.isoformat()}T12:00:00+00:00", saved.id))
        connection.commit()
        preview = service.build_preview(report_date)
        normalized_evidence = normalize_timestamps(preview.evidence)
        assert normalized_evidence == (SNAPSHOT_DIR / "text_evidence.txt").read_text(encoding="utf-8")
        report = service.generate_and_save_eod(report_date, SnapshotProvider())
        assert report.content == (SNAPSHOT_DIR / "eod_report.md").read_text(encoding="utf-8")

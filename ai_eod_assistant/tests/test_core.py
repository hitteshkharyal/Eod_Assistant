from __future__ import annotations

import sqlite3
from datetime import date

from ai_eod_assistant.ai.base import AIProvider
from ai_eod_assistant.ai.eod_generator import EODGenerator
from ai_eod_assistant.ai.ollama import OllamaProvider
from ai_eod_assistant.ai.providers import build_provider
from ai_eod_assistant.auth import authenticate, change_password, create_member, create_team_admin, initialize_auth
from ai_eod_assistant.ai.prompts import build_eod_prompt
from ai_eod_assistant.backend.eod_service import EODService
from ai_eod_assistant.database.db import initialize_database
from ai_eod_assistant.processing.context import build_text_evidence
from ai_eod_assistant.ui.voice import build_report_summary


class FakeProvider(AIProvider):
    name = "fake"

    def generate(self, prompt: str) -> str:
        assert "Never invent work" in prompt
        return "## EOD — 2026-08-19\n\n### Work Completed\n- Wrote tests."


def memory_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    initialize_database(connection)
    return connection


def test_prompt_contains_evidence_priority() -> None:
    prompt = build_eod_prompt(date(2026, 8, 19), "Implemented MVP")
    assert "Evidence priority" in prompt
    assert "Implemented MVP" in prompt


def test_eod_generator_uses_provider() -> None:
    report = EODGenerator(FakeProvider()).generate_report(date(2026, 8, 19), "Wrote tests")
    assert "Work Completed" in report


def test_backend_service_round_trip() -> None:
    with memory_connection() as connection:
        service = EODService(connection)
        saved = service.add_text_activity("Built Phase 1 backend service")
        assert saved.id is not None
        preview = service.build_preview(saved.timestamp.date())
        assert "Built Phase 1 backend service" in preview.evidence
        report = service.generate_and_save_eod(saved.timestamp.date(), FakeProvider())
        assert report.id is not None
        assert service.recent_reports(1)[0].content.startswith("## EOD")


def test_task_context_is_included_in_preview() -> None:
    with memory_connection() as connection:
        service = EODService(connection)
        task = service.add_task("Monitoring EOD", "Summarize the monitored implementation work")
        preview = service.build_preview(date.today())
        assert task in preview.tasks
        assert "Monitoring EOD" in preview.evidence
        assert "Summarize the monitored implementation work" in preview.evidence


def test_context_builder_empty_evidence() -> None:
    assert build_text_evidence([]) == ""


def test_report_summary_is_short_plain_text() -> None:
    report = """## EOD — 2026-08-21

### Work Completed
- Built the monitoring task flow.

### Technical Work
- Added task context to the EOD prompt.

### Issues / Challenges
- None reported.

### Next Steps
- Validate the Gemini flow.
"""
    summary = build_report_summary(report)
    assert summary == "Built the monitoring task flow. Added task context to the EOD prompt. None reported. Validate the Gemini flow."
    assert "#" not in summary


def test_offline_provider_selection_does_not_require_api_key() -> None:
    provider = build_provider(
        "Offline (Ollama)",
        gemini_api_key=None,
        model="llama3.2:3b",
        ollama_base_url="http://localhost:11434/",
    )
    assert isinstance(provider, OllamaProvider)
    assert provider.base_url == "http://localhost:11434"


def test_seeded_admin_and_team_accounts() -> None:
    with memory_connection() as connection:
        initialize_auth(connection)
        admin = authenticate(connection, "admin", "admin123")
        assert admin is not None
        assert admin.team_name == "alpha"
        member = create_member(connection, "alice", "member-pass", admin.team_id)
        assert authenticate(connection, "alice", "member-pass") == member
        other_admin = create_team_admin(connection, "lead", "lead-pass", "beta")
        assert other_admin.role == "admin"
        assert other_admin.team_name == "beta"
        change_password(connection, admin, "alice", "new-member-pass")
        assert authenticate(connection, "alice", "new-member-pass") is not None


def test_member_history_is_isolated_from_old_and_other_member_reports() -> None:
    with memory_connection() as connection:
        initialize_auth(connection)
        admin = authenticate(connection, "admin", "admin123")
        assert admin is not None
        alice = create_member(connection, "alice", "alice-pass", admin.team_id)
        bob = create_member(connection, "bob", "bob-pass", admin.team_id)
        service = EODService(connection, alice)
        service.reports.save(date.today(), "Alice report", "fake", alice.id)
        service.reports.save(date.today(), "Bob report", "fake", bob.id)
        service.reports.save(date.today(), "Legacy report", "fake", None)
        assert [report.content for report in service.recent_reports()] == ["Alice report"]

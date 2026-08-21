"""Backend service layer for the Phase 1 EOD workflow."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date

from ai_eod_assistant.ai.base import AIProvider
from ai_eod_assistant.auth import AuthUser, initialize_auth
from ai_eod_assistant.ai.eod_generator import EODGenerator
from ai_eod_assistant.database.db import initialize_database
from ai_eod_assistant.database.models import EODReport, Task, UserInput
from ai_eod_assistant.database.repositories import EODReportRepository, SettingsRepository, TaskRepository, UserInputRepository
from ai_eod_assistant.processing.context import build_task_context, build_text_evidence


@dataclass(frozen=True)
class EODPreview:
    """Prepared report evidence that can be reviewed before model generation."""

    report_date: date
    evidence: str
    inputs: list[UserInput]
    tasks: list[Task]


class EODService:
    """Coordinates repositories, context building, AI generation, and report persistence."""

    def __init__(self, connection: sqlite3.Connection, current_user: AuthUser | None = None) -> None:
        self.connection = connection
        initialize_database(connection)
        initialize_auth(connection)
        self.current_user = current_user
        self.user_inputs = UserInputRepository(connection)
        self.tasks = TaskRepository(connection)
        self.reports = EODReportRepository(connection)
        self.settings = SettingsRepository(connection)

    def add_text_activity(self, content: str) -> UserInput:
        """Store explicit user-provided text evidence."""
        return self.user_inputs.add_text(content, self.current_user.id if self.current_user else None)

    def add_task(self, title: str, description: str = "") -> Task:
        """Store a task that can be selected when recording monitoring evidence."""
        team_id = self.current_user.team_id if self.current_user else None
        return self.tasks.add(title, description, team_id)

    def active_tasks(self) -> list[Task]:
        return self.tasks.list_active(self.current_user.team_id if self.current_user else None)

    def add_voice_activity(self, transcript: str) -> UserInput:
        """Store a user-reviewed voice transcript as evidence."""
        return self.user_inputs.add(transcript, input_type="voice", user_id=self.current_user.id if self.current_user else None)

    def add_workspace_activity(self, evidence: str) -> UserInput:
        """Store a user-authorized local workspace scan as cautious evidence."""
        return self.user_inputs.add(evidence, input_type="workspace", user_id=self.current_user.id if self.current_user else None)

    def add_external_activity(self, source: str, content: str) -> UserInput:
        """Store activity explicitly imported from another user-authorized tool."""
        return self.user_inputs.add(content, input_type=f"external:{source.strip() or 'unknown'}", user_id=self.current_user.id if self.current_user else None)

    def build_preview(self, report_date: date) -> EODPreview:
        """Build the exact evidence block that may be sent to an AI provider."""
        inputs = self.user_inputs.list_for_date(report_date, user_id=self.current_user.id if self.current_user and self.current_user.role == "member" else None, team_id=self.current_user.team_id if self.current_user and self.current_user.role == "admin" else None)
        tasks = self.tasks.list_active(self.current_user.team_id if self.current_user else None)
        evidence = "\n\n".join(filter(None, [build_task_context(tasks), build_text_evidence(inputs)]))
        return EODPreview(report_date=report_date, evidence=evidence, inputs=inputs, tasks=tasks)

    def generate_and_save_eod(self, report_date: date, provider: AIProvider, provider_label: str | None = None) -> EODReport:
        """Generate a report using reviewed evidence and save the result."""
        preview = self.build_preview(report_date)
        content = EODGenerator(provider).generate_report(report_date, preview.evidence)
        return self.reports.save(report_date, content, provider_label or provider.name, self.current_user.id if self.current_user else None)

    def recent_reports(self, limit: int = 20) -> list[EODReport]:
        """Return recently generated EOD reports."""
        if self.current_user and self.current_user.role == "admin":
            return self.reports.list_recent(limit, team_id=self.current_user.team_id)
        return self.reports.list_recent(limit, user_id=self.current_user.id if self.current_user else None)

    def search_team_reports(self, member_id: int | None = None, report_date: date | None = None, query: str = "") -> list[EODReport]:
        if not self.current_user or self.current_user.role != "admin":
            raise PermissionError("Only team leaders can search team EOD history.")
        return self.reports.search_team(self.current_user.team_id, member_id, report_date, query)

    def clear_all_reports(self) -> int:
        if not self.current_user or self.current_user.role != "admin":
            raise PermissionError("Only admins can clear EOD history.")
        return self.reports.delete_all()

    def save_model_setting(self, model: str) -> None:
        """Persist the non-secret preferred model name."""
        self.settings.set("gemini_model", model)

    def save_ai_settings(self, mode: str, model: str, ollama_base_url: str) -> None:
        """Persist non-secret provider settings for the next session."""
        self.settings.set("ai_mode", mode)
        self.settings.set("ai_model", model)
        self.settings.set("ollama_base_url", ollama_base_url)

"""Repository helpers for persistence operations."""
from __future__ import annotations

import sqlite3
from datetime import date, datetime

from ai_eod_assistant.database.models import AppSetting, EODReport, Task, UserInput, utc_now


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _user_input_from_row(row: sqlite3.Row) -> UserInput:
    return UserInput(
        id=int(row["id"]),
        timestamp=_parse_datetime(row["timestamp"]),
        input_type=str(row["input_type"]),
        content=str(row["content"]),
    )


def _report_from_row(row: sqlite3.Row) -> EODReport:
    return EODReport(
        id=int(row["id"]),
        date=date.fromisoformat(str(row["date"])),
        content=str(row["content"]),
        created_at=_parse_datetime(str(row["created_at"])),
        ai_provider=str(row["ai_provider"]),
        username=str(row["username"]) if "username" in row.keys() and row["username"] else None,
    )


def _task_from_row(row: sqlite3.Row) -> Task:
    return Task(
        id=int(row["id"]),
        created_at=_parse_datetime(str(row["created_at"])),
        title=str(row["title"]),
        description=str(row["description"]),
        status=str(row["status"]),
    )


class UserInputRepository:
    """Persistence operations for explicit user inputs."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add(self, content: str, input_type: str = "text", user_id: int | None = None) -> UserInput:
        cleaned_content = content.strip()
        if not cleaned_content:
            raise ValueError("User input content cannot be empty.")
        timestamp = utc_now().isoformat()
        cursor = self.connection.execute(
            "INSERT INTO user_inputs (timestamp, input_type, content, user_id) VALUES (?, ?, ?, ?) RETURNING id",
            (timestamp, input_type, cleaned_content, user_id),
        )
        self.connection.commit()
        row = self.connection.execute("SELECT * FROM user_inputs WHERE id = ?", (cursor.fetchone()["id"],)).fetchone()
        return _user_input_from_row(row)

    def add_text(self, content: str, user_id: int | None = None) -> UserInput:
        return self.add(content, input_type="text", user_id=user_id)

    def list_for_date(self, target_date: date, user_id: int | None = None, team_id: int | None = None) -> list[UserInput]:
        scope = ""
        scope_value: tuple[object, ...] = ()
        if user_id is not None:
            scope = " AND user_id = ?"
            scope_value = (user_id,)
        elif team_id is not None:
            scope = " AND user_id IN (SELECT id FROM users WHERE team_id = ?)"
            scope_value = (team_id,)
        rows = self.connection.execute(
            f"SELECT * FROM user_inputs WHERE substr(timestamp, 1, 10) = ?{scope} ORDER BY timestamp ASC",
            (target_date.isoformat(), *scope_value),
        ).fetchall()
        return [_user_input_from_row(row) for row in rows]


class TaskRepository:
    """Persistence operations for user-defined work items."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add(self, title: str, description: str = "", team_id: int | None = None) -> Task:
        cleaned_title = title.strip()
        if not cleaned_title:
            raise ValueError("Task title cannot be empty.")
        cursor = self.connection.execute(
            "INSERT INTO tasks (created_at, title, description, team_id) VALUES (?, ?, ?, ?) RETURNING id",
            (utc_now().isoformat(), cleaned_title, description.strip(), team_id),
        )
        self.connection.commit()
        row = self.connection.execute("SELECT * FROM tasks WHERE id = ?", (cursor.fetchone()["id"],)).fetchone()
        return _task_from_row(row)

    def list_active(self, team_id: int | None = None) -> list[Task]:
        scope = "" if team_id is None else " WHERE team_id = ?"
        rows = self.connection.execute(
            f"SELECT * FROM tasks{scope} {'AND' if scope else 'WHERE'} status = 'active' ORDER BY created_at DESC",
            () if team_id is None else (team_id,),
        ).fetchall()
        return [_task_from_row(row) for row in rows]


class EODReportRepository:
    """Persistence operations for generated EOD reports."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save(self, report_date: date, content: str, ai_provider: str, user_id: int | None = None) -> EODReport:
        created_at = utc_now().isoformat()
        cursor = self.connection.execute(
            "INSERT INTO eod_reports (date, content, created_at, ai_provider, user_id) VALUES (?, ?, ?, ?, ?) RETURNING id",
            (report_date.isoformat(), content, created_at, ai_provider, user_id),
        )
        self.connection.commit()
        row = self.connection.execute("SELECT * FROM eod_reports WHERE id = ?", (cursor.fetchone()["id"],)).fetchone()
        return _report_from_row(row)

    def list_recent(self, limit: int = 20, user_id: int | None = None, team_id: int | None = None) -> list[EODReport]:
        scope = ""
        scope_value: tuple[object, ...] = ()
        if user_id is not None:
            scope = " WHERE user_id = ?"
            scope_value = (user_id,)
        elif team_id is not None:
            scope = " WHERE user_id IN (SELECT id FROM users WHERE team_id = ?)"
            scope_value = (team_id,)
        rows = self.connection.execute(
            f"SELECT eod_reports.*, users.username AS username FROM eod_reports LEFT JOIN users ON users.id = eod_reports.user_id{scope} ORDER BY eod_reports.created_at DESC LIMIT ?",
            (*scope_value, limit),
        ).fetchall()
        return [_report_from_row(row) for row in rows]

    def delete_all(self) -> int:
        cursor = self.connection.execute("DELETE FROM eod_reports")
        self.connection.commit()
        return cursor.rowcount

    def search_team(self, team_id: int, member_id: int | None = None, report_date: date | None = None, query: str = "", limit: int = 100) -> list[EODReport]:
        clauses = ["users.team_id = ?"]
        values: list[object] = [team_id]
        if member_id is not None:
            clauses.append("eod_reports.user_id = ?")
            values.append(member_id)
        if report_date is not None:
            clauses.append("eod_reports.date = ?")
            values.append(report_date.isoformat())
        if query.strip():
            clauses.append("(eod_reports.content LIKE ? OR users.username LIKE ?)")
            wildcard = f"%{query.strip()}%"
            values.extend([wildcard, wildcard])
        rows = self.connection.execute(
            "SELECT eod_reports.*, users.username AS username FROM eod_reports "
            "JOIN users ON users.id = eod_reports.user_id WHERE " + " AND ".join(clauses) +
            " ORDER BY eod_reports.date DESC, eod_reports.created_at DESC LIMIT ?",
            (*values, limit),
        ).fetchall()
        return [_report_from_row(row) for row in rows]


class SettingsRepository:
    """Persistence operations for non-secret settings."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def set(self, key: str, value: str) -> None:
        self.connection.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.connection.commit()

    def get(self, key: str) -> str | None:
        row = self.connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else None

    def list_all(self) -> list[AppSetting]:
        rows = self.connection.execute("SELECT key, value FROM settings ORDER BY key ASC").fetchall()
        return [AppSetting(key=str(row["key"]), value=str(row["value"])) for row in rows]

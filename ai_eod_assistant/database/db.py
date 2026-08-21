"""SQLite connection helpers with safe initialization."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ai_eod_assistant.config.settings import get_settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS user_inputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    input_type TEXT NOT NULL DEFAULT 'text',
    content TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eod_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    ai_provider TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_eod_reports_date ON eod_reports(date);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active'
);

CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_id INTEGER NOT NULL REFERENCES teams(id),
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'member')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_team_id ON users(team_id);
"""


def get_database_path(database_path: str | None = None) -> Path:
    """Resolve the configured SQLite database path."""
    raw_path = database_path or get_settings().database_path
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def get_connection(database_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with row access by column name."""
    path = get_database_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(connection: sqlite3.Connection | None = None) -> None:
    """Create missing tables and indexes without dropping existing data."""
    if connection is None:
        with get_connection() as owned_connection:
            owned_connection.executescript(SCHEMA_SQL)
            owned_connection.commit()
        return
    connection.executescript(SCHEMA_SQL)
    for table, column, definition in (
        ("user_inputs", "user_id", "INTEGER REFERENCES users(id)"),
        ("eod_reports", "user_id", "INTEGER REFERENCES users(id)"),
        ("tasks", "team_id", "INTEGER REFERENCES teams(id)"),
    ):
        columns = {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    connection.commit()
    connection.commit()

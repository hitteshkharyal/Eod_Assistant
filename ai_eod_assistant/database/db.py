"""SQLite connection helpers with safe initialization."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from ai_eod_assistant.config.settings import get_settings


SQLITE_SCHEMA_SQL = """
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

POSTGRES_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS teams (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    team_id BIGINT NOT NULL REFERENCES teams(id),
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'member')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_team_id ON users(team_id);

CREATE TABLE IF NOT EXISTS user_inputs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TEXT NOT NULL,
    input_type TEXT NOT NULL DEFAULT 'text',
    content TEXT NOT NULL,
    user_id BIGINT REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS eod_reports (
    id BIGSERIAL PRIMARY KEY,
    date TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    ai_provider TEXT NOT NULL,
    user_id BIGINT REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_eod_reports_date ON eod_reports(date);

CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS tasks (
    id BIGSERIAL PRIMARY KEY,
    created_at TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'active',
    team_id BIGINT REFERENCES teams(id)
);

CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
"""


class PostgresConnection:
    """Small compatibility adapter for the repository layer's SQLite-style API."""

    def __init__(self, connection: object) -> None:
        self.connection = connection

    def execute(self, sql: str, parameters: tuple[object, ...] = ()):
        query = sql.replace("?", "%s")
        cursor = self.connection.cursor()
        cursor.execute(query, parameters)
        return cursor

    def executescript(self, sql: str) -> None:
        for statement in sql.split(";"):
            if statement.strip():
                self.execute(statement)

    def commit(self) -> None:
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()


def get_database_path(database_path: str | None = None) -> Path:
    """Resolve the configured SQLite database path."""
    raw_path = database_path or get_settings().database_path
    path = Path(raw_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def get_connection(database_path: str | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with row access by column name."""
    database_url = get_settings().database_url
    if database_url:
        import psycopg
        from psycopg.rows import dict_row

        return PostgresConnection(psycopg.connect(database_url, row_factory=dict_row))  # type: ignore[return-value]
    path = get_database_path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(connection: sqlite3.Connection | None = None) -> None:
    """Create missing tables and indexes without dropping existing data."""
    if connection is None:
        with get_connection() as owned_connection:
            owned_connection.executescript(
                SQLITE_SCHEMA_SQL if isinstance(owned_connection, sqlite3.Connection) else POSTGRES_SCHEMA_SQL
            )
            owned_connection.commit()
        return
    if isinstance(connection, sqlite3.Connection):
        connection.executescript(SQLITE_SCHEMA_SQL)
        columns_to_add = (
            ("user_inputs", "user_id", "INTEGER REFERENCES users(id)"),
            ("eod_reports", "user_id", "INTEGER REFERENCES users(id)"),
            ("tasks", "team_id", "INTEGER REFERENCES teams(id)"),
        )
        for table, column, definition in columns_to_add:
            columns = {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({table})")}
            if column not in columns:
                connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    else:
        connection.executescript(POSTGRES_SCHEMA_SQL)
    connection.commit()
    connection.commit()

"""Dataclasses representing persisted Phase 1 records."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class UserInput:
    """User-provided evidence for an EOD report."""

    id: int
    timestamp: datetime
    input_type: str
    content: str


@dataclass(frozen=True)
class Task:
    """A user-defined work item used to explain monitoring evidence."""

    id: int
    created_at: datetime
    title: str
    description: str
    status: str


@dataclass(frozen=True)
class EODReport:
    """Generated EOD report stored for history."""

    id: int
    date: date
    content: str
    created_at: datetime
    ai_provider: str
    username: str | None = None


@dataclass(frozen=True)
class AppSetting:
    """Persisted non-secret application setting."""

    key: str
    value: str

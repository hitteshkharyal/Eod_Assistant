"""Application configuration loaded from environment variables and .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


def _load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE pairs without overriding existing environment values."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    """Runtime settings for the AI EOD Assistant."""

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    ai_mode: str = "Online (Gemini)"
    ollama_model: str = "llama3.2:3b"
    ollama_base_url: str = "http://127.0.0.1:11434"
    admin_recovery_key: str | None = None
    database_path: str = "ai_eod_assistant/data/eod_assistant.db"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    _load_dotenv(ROOT_DIR / ".env")
    return Settings(
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        ai_mode=os.getenv("AI_MODE", "Online (Gemini)"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        admin_recovery_key=os.getenv("ADMIN_RECOVERY_KEY") or None,
        database_path=os.getenv("DATABASE_PATH", "ai_eod_assistant/data/eod_assistant.db"),
    )

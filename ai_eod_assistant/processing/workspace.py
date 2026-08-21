"""Explicit, local-only workspace activity collection."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
from urllib import request

IGNORED_DIRECTORY_NAMES = {".git", ".venv", "__pycache__", "node_modules", "build", "dist"}


@dataclass(frozen=True)
class WorkspaceChange:
    """A file changed within a user-selected workspace."""

    workspace: Path
    project_name: str
    relative_path: str
    modified_at: datetime
    language_hint: str


def _project_name(workspace: Path) -> str:
    """Use the nearest Git project name when available, otherwise the selected folder."""
    for candidate in (workspace, *workspace.parents):
        if (candidate / ".git").exists():
            return candidate.name
    return workspace.name


def _language_hint(path: Path) -> str:
    hints = {
        ".py": "Python",
        ".js": "JavaScript",
        ".ts": "TypeScript",
        ".tsx": "TypeScript/React",
        ".jsx": "JavaScript/React",
        ".md": "Markdown",
        ".json": "JSON",
        ".yml": "YAML",
        ".yaml": "YAML",
        ".sql": "SQL",
    }
    return hints.get(path.suffix.lower(), path.suffix.lstrip(".").upper() or "file")


def scan_workspace(workspace_path: str, since: datetime, max_files: int = 200) -> list[WorkspaceChange]:
    """Return recent file modifications from one explicitly selected local directory.

    This performs no hidden monitoring and skips common dependency/build folders.
    """
    workspace = Path(workspace_path).expanduser().resolve()
    if not workspace.is_dir():
        raise ValueError("Choose an existing workspace directory.")
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)

    changes: list[WorkspaceChange] = []
    for path in workspace.rglob("*"):
        if any(part in IGNORED_DIRECTORY_NAMES for part in path.parts):
            continue
        if not path.is_file():
            continue
        try:
            modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if modified_at < since:
            continue
        changes.append(
            WorkspaceChange(
                workspace=workspace,
                project_name=_project_name(workspace),
                relative_path=path.relative_to(workspace).as_posix(),
                modified_at=modified_at,
                language_hint=_language_hint(path),
            )
        )

    changes.sort(key=lambda item: item.modified_at, reverse=True)
    return changes[:max_files]


def format_workspace_evidence(changes: list[WorkspaceChange]) -> str:
    """Format cautious file-change evidence for review before it reaches the model."""
    if not changes:
        return ""
    first = changes[0]
    lines = [
        "User-authorized workspace file activity (file modification is evidence of activity, not proof of completion):",
        f"- Project: {first.project_name}",
        f"- Workspace: {first.workspace}",
        f"- Files changed: {len(changes)}",
    ]
    lines.extend(
        f"- [{item.modified_at.isoformat()}] {item.relative_path} ({item.language_hint})" for item in changes
    )
    return "\n".join(lines)


def scan_remote_workspace(connector_url: str, workspace_path: str, since: datetime, max_files: int = 200) -> list[WorkspaceChange]:
    """Request an explicit local-folder scan from a reachable Ollama connector."""
    payload = json.dumps({"workspace_path": workspace_path, "since": since.isoformat(), "max_files": max_files}).encode("utf-8")
    call = request.Request(
        f"{connector_url.rstrip('/')}/scan",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(call, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("error"):
        raise ValueError(str(result["error"]))
    return [
        WorkspaceChange(
            workspace=Path(item["workspace"]),
            project_name=str(item["project_name"]),
            relative_path=str(item["relative_path"]),
            modified_at=datetime.fromisoformat(str(item["modified_at"])),
            language_hint=str(item["language_hint"]),
        )
        for item in result.get("changes", [])
    ]

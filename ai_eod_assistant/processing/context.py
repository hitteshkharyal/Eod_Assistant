"""Context building from persisted evidence."""
from __future__ import annotations

from ai_eod_assistant.database.models import Task, UserInput


def build_task_context(tasks: list[Task]) -> str:
    """Describe active tasks so the model can relate evidence to intended work."""
    if not tasks:
        return ""
    lines = ["Active user-defined tasks:"]
    for task in tasks:
        detail = f": {task.description}" if task.description else ""
        lines.append(f"- Task {task.id}: {task.title}{detail}")
    return "\n".join(lines)


def build_text_evidence(user_inputs: list[UserInput]) -> str:
    """Convert user text inputs into a clear evidence block for the model."""
    if not user_inputs:
        return ""
    text_only = all(item.input_type == "text" for item in user_inputs)
    lines = ["Confirmed user-provided text evidence:" if text_only else "Collected evidence:"]
    for item in user_inputs:
        source = "" if text_only else f" [{item.input_type}]"
        lines.append(f"- [{item.timestamp.isoformat()}]{source} {item.content}")
    return "\n".join(lines)

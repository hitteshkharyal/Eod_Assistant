"""Prompts for factual EOD generation."""
from __future__ import annotations

from datetime import date

EOD_SYSTEM_INSTRUCTIONS = """You generate factual professional end-of-day reports.
Never invent work. Prioritize explicit user statements over inferred activity.
If evidence is uncertain, use cautious wording or include it under pending clarification.
Do not claim an app/window being open proves productive work was completed."""


def build_eod_prompt(report_date: date, evidence: str) -> str:
    """Build the prompt for the online MVP EOD report."""
    return f"""{EOD_SYSTEM_INSTRUCTIONS}

Create a concise professional EOD report for {report_date.isoformat()} using only the evidence below.

Evidence priority:
1. Explicit user description
2. User voice description
3. Explicitly imported document/chat content
4. Strong activity evidence
5. Weak activity evidence

Use active task descriptions to group and explain related evidence, but do not claim a task was completed unless the evidence supports it.

Use this format exactly:
## EOD — {report_date.isoformat()}

### Work Completed
- ...

### Technical Work
- ...

### Issues / Challenges
- ...

### Communication / Documentation
- ...

### Pending Work
- ...

### Next Steps
- ...

Evidence:
{evidence if evidence.strip() else "No confirmed user-provided work evidence."}
"""

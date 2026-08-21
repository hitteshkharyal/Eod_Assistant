"""Browser-local text-to-speech controls for report playback."""
from __future__ import annotations

import re

import streamlit as st


def build_report_summary(report: str, max_lines: int = 4) -> str:
  """Return a short plain-text summary suitable for speech playback."""
  if not report.strip() or max_lines < 1:
    return ""

  summary_lines: list[str] = []
  preferred_sections = {"Work Completed", "Technical Work", "Issues / Challenges", "Next Steps"}
  current_section = ""
  for raw_line in report.splitlines():
    line = raw_line.strip()
    if line.startswith("### "):
      current_section = line[4:].strip()
      continue
    if not line.startswith("-") or current_section not in preferred_sections:
      continue
    cleaned = re.sub(r"^[-*]\s*", "", line)
    cleaned = re.sub(r"[`*_#]", "", cleaned).strip()
    if cleaned and cleaned.lower() not in {item.lower() for item in summary_lines}:
      summary_lines.append(cleaned)
    if len(summary_lines) >= max_lines:
      break

  if not summary_lines:
    cleaned_report = re.sub(r"[`*_#]", "", report)
    return " ".join(cleaned_report.split())[:500]
  return " ".join(summary_lines)


_TTS_COMPONENT = st.components.v2.component(
    "browser_text_to_speech",
    html="""<div id="root"></div>""",
    js="""
export default function ({ data, parentElement }) {
  const root = parentElement.querySelector("#root")
  if (!root) return
  root.replaceChildren()
  const speak = document.createElement("button")
  const stop = document.createElement("button")
  const note = document.createElement("span")
  speak.type = "button"
  stop.type = "button"
  speak.textContent = "Speak summary"
  stop.textContent = "Stop"
  note.textContent = " Playback uses this browser's local speech engine."
  root.append(speak, stop, note)
  speak.onclick = () => {
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance((data && data.text) || "")
    utterance.lang = (data && data.language) || "en-US"
    window.speechSynthesis.speak(utterance)
  }
  stop.onclick = () => window.speechSynthesis.cancel()
  return () => window.speechSynthesis.cancel()
}
""",
)


def render_speech_controls(text: str, *, key: str) -> None:
  """Render local browser TTS controls for a short report summary."""
  summary = build_report_summary(text)
  if summary:
    _TTS_COMPONENT(data={"text": summary, "language": "en-US"}, key=key, height=48)

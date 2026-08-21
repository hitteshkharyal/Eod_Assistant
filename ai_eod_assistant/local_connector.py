"""Local Ollama connector for users running the hosted app.

Run with: python -m ai_eod_assistant.local_connector
"""
from __future__ import annotations

import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, request

from ai_eod_assistant.processing.workspace import format_workspace_evidence, scan_workspace

OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
CONNECTOR_TOKEN = os.getenv("OLLAMA_CONNECTOR_TOKEN", "")


def ollama_request(path: str, payload: dict | None = None) -> dict:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    call = request.Request(
        f"{OLLAMA_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST" if body is not None else "GET",
    )
    with request.urlopen(call, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def detect_ollama() -> dict:
    """Return local Ollama status and installed model names."""
    try:
        models = ollama_request("/api/tags").get("models", [])
        return {"available": True, "url": OLLAMA_URL, "models": [item.get("name") for item in models]}
    except (OSError, error.URLError) as exc:
        executable = "ollama.exe" if os.name == "nt" else "ollama"
        try:
            version = subprocess.run([executable, "--version"], capture_output=True, text=True, timeout=5, check=False)
            installed = version.returncode == 0
        except OSError:
            installed = False
        return {"available": False, "installed": installed, "url": OLLAMA_URL, "error": str(exc)}


class ConnectorHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Connector-Token")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        self._send(204, {})

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        if self.path == "/health":
            self._send(200, detect_ollama())
            return
        if self.path == "/models":
            status = detect_ollama()
            self._send(200 if status.get("available") else 503, status)
            return
        self._send(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
        if self.path == "/scan":
            if CONNECTOR_TOKEN and self.headers.get("X-Connector-Token") != CONNECTOR_TOKEN:
                self._send(401, {"error": "Invalid connector token"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                changes = scan_workspace(
                    str(payload.get("workspace_path", "")),
                    __import__("datetime").datetime.fromisoformat(str(payload.get("since"))),
                    int(payload.get("max_files", 200)),
                )
                self._send(200, {"changes": [
                    {"workspace": str(item.workspace), "project_name": item.project_name, "relative_path": item.relative_path,
                     "modified_at": item.modified_at.isoformat(), "language_hint": item.language_hint}
                    for item in changes
                ], "evidence": format_workspace_evidence(changes)})
            except (ValueError, OSError, json.JSONDecodeError) as exc:
                self._send(400, {"error": str(exc)})
            return
        if self.path not in {"/generate", "/api/generate"}:
            self._send(404, {"error": "Not found"})
            return
        if CONNECTOR_TOKEN and self.headers.get("X-Connector-Token") != CONNECTOR_TOKEN:
            self._send(401, {"error": "Invalid connector token"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            model, prompt = str(payload.get("model", "")).strip(), str(payload.get("prompt", ""))
            if not model or not prompt:
                self._send(400, {"error": "model and prompt are required"})
                return
            result = ollama_request("/api/generate", {"model": model, "prompt": prompt, "stream": False})
            self._send(200, {"response": str(result.get("response", "")).strip(), "model": model})
        except (ValueError, OSError, error.URLError, json.JSONDecodeError) as exc:
            self._send(502, {"error": str(exc)})

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    host = os.getenv("OLLAMA_CONNECTOR_HOST", "127.0.0.1")
    port = int(os.getenv("OLLAMA_CONNECTOR_PORT", "8765"))
    print(f"Ollama connector listening on http://{host}:{port}")
    ThreadingHTTPServer((host, port), ConnectorHandler).serve_forever()


if __name__ == "__main__":
    main()

"""Loopback-only lifecycle supervisor for the local IMP workstation."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.platform.local_launcher import (
    API_HOST,
    API_PORT,
    UI_HOST,
    UI_PORT,
    PlatformController,
    ServiceRecord,
    WindowsSystem,
)


CONTROL_HOST = "127.0.0.1"
CONTROL_PORT = 8767
ALLOWED_ACTIONS = frozenset({"setup", "start", "stop", "restart", "open", "check_update", "apply_update"})
ALLOWED_ORIGINS = frozenset({"http://127.0.0.1:5173", "http://localhost:5173"})


def normalize_action(value: object) -> str | None:
    action = str(value or "").strip().lower()
    return action if action in ALLOWED_ACTIONS else None


def _read_operation_path(root: Path) -> Path:
    return root / ".local/operator-lifecycle-operations.json"


def _read_operations(root: Path) -> dict[str, dict[str, Any]]:
    path = _read_operation_path(root)
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_operation(root: Path, operation: dict[str, Any]) -> None:
    path = _read_operation_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    operations = _read_operations(root)
    operations[str(operation["operation_id"])] = operation
    descriptor, temporary_name = tempfile.mkstemp(prefix=".operator-operation.", suffix=".tmp", dir=str(path.parent))
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(operations, handle, sort_keys=True, separators=(",", ":"))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def update_operation(root: Path, operation_id: str, *, status: str, detail: str | None = None) -> None:
    operations = _read_operations(root)
    operation = operations.get(operation_id)
    if operation is None:
        return
    operation = dict(operation)
    operation["status"] = status
    operation["updated_at"] = time.time()
    if detail:
        operation["detail"] = detail
    _write_operation(root, operation)


def build_control_status(root: Path | None = None) -> dict[str, Any]:
    repository = (root or Path(__file__).resolve().parents[2]).resolve()
    controller = PlatformController(root=repository)
    records = controller._read_state()
    services: list[dict[str, Any]] = []
    for record in records:
        services.append(
            {
                "name": record.name,
                "pid": record.pid,
                "owned": controller._is_owned(record),
                "log_path": record.log_path,
            }
        )
    api_ready = controller.system.url_ready(f"http://{API_HOST}:{API_PORT}/context")
    ui_ready = controller.system.url_ready(f"http://{UI_HOST}:{UI_PORT}/")
    control_ready = controller.system.url_ready(f"http://{CONTROL_HOST}:{CONTROL_PORT}/control/status")
    required_owned = all(
        any(row["name"] == name and row["owned"] for row in services)
        for name in ("api", "ui", "control")
    )
    status = "READY" if api_ready and ui_ready and control_ready and required_owned else "PARTIAL" if records else "STOPPED"
    return {
        "schema_version": "operator-lifecycle/1.0",
        "status": status,
        "services": services,
        "logs": sorted({str(row["log_path"]) for row in services}),
        "last_action": None,
        "update": check_update(repository),
    }


def check_update(root: Path | None = None) -> dict[str, Any]:
    repository = (root or Path(__file__).resolve().parents[2]).resolve()
    git = "git.exe" if os.name == "nt" and shutil_which("git.exe") else "git"
    if shutil_which(git) is None:
        return {"status": "UNAVAILABLE", "detail": "Git is not installed."}
    status = subprocess.run([git, "status", "--porcelain"], cwd=repository, capture_output=True, text=True, check=False)
    branch = subprocess.run([git, "branch", "--show-current"], cwd=repository, capture_output=True, text=True, check=False)
    upstream = subprocess.run([git, "rev-parse", "--abbrev-ref", "--symbolic-full-name", """@{upstream}"""], cwd=repository, capture_output=True, text=True, check=False)
    if status.returncode:
        return {"status": "UNAVAILABLE", "detail": "Git status could not be read."}
    if status.stdout.strip():
        return {"status": "BLOCKED", "detail": "Local tracked changes must be resolved before updating.", "branch": branch.stdout.strip()}
    if upstream.returncode:
        return {"status": "UNAVAILABLE", "detail": "The current branch has no configured upstream.", "branch": branch.stdout.strip()}
    counts = subprocess.run(
        [git, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
        cwd=repository,
        capture_output=True,
        text=True,
        check=False,
    )
    if counts.returncode:
        return {"status": "UNAVAILABLE", "detail": "The upstream revision could not be inspected.", "branch": branch.stdout.strip()}
    parts = counts.stdout.split()
    ahead, behind = (int(parts[0]), int(parts[1])) if len(parts) == 2 else (0, 0)
    state = "AVAILABLE" if behind > 0 and ahead == 0 else "CURRENT" if behind == 0 else "BLOCKED"
    detail = "Fast-forward update available." if state == "AVAILABLE" else "Local branch is current." if state == "CURRENT" else "Branches have diverged; update is blocked."
    return {"status": state, "detail": detail, "branch": branch.stdout.strip(), "ahead": ahead, "behind": behind, "upstream": upstream.stdout.strip()}


def shutil_which(name: str) -> str | None:
    import shutil

    return shutil.which(name)


def _spawn_action(root: Path, action: str) -> dict[str, Any]:
    operation_id = f"op-{uuid.uuid4().hex[:16]}"
    operation = {
        "operation_id": operation_id,
        "action": action,
        "status": "QUEUED",
        "created_at": time.time(),
        "secrets_included": False,
    }
    _write_operation(root, operation)
    python = root / ".venv/Scripts/python.exe"
    if not python.is_file():
        python = Path(sys.executable)
    log_path = root / ".local/platform-control.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [str(python), str(root / "tools/platform/local_launcher.py"), action]
    if action == "start":
        command.append("--open")
    environment = dict(os.environ)
    environment["IMP_OPERATOR_OPERATION_ID"] = operation_id
    with log_path.open("ab") as log_handle:
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(command, cwd=str(root), env=environment, stdin=subprocess.DEVNULL, stdout=log_handle, stderr=subprocess.STDOUT, creationflags=flags, close_fds=True)
    return operation


class ControlHandler(BaseHTTPRequestHandler):
    root: Path

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        origin = self.headers.get("Origin")
        if origin is not None and origin not in ALLOWED_ORIGINS:
            self.send_response(HTTPStatus.FORBIDDEN)
            self.end_headers()
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/control/status":
            self._send(build_control_status(self.root))
            return
        if parsed.path.startswith("/control/operations/"):
            operation_id = parsed.path.removeprefix("/control/operations/")
            operation = _read_operations(self.root).get(operation_id)
            if operation is None:
                self._send({"error": "Operation not found", "reason_code": "OPERATION_NOT_FOUND"}, HTTPStatus.NOT_FOUND)
            else:
                self._send(operation)
            return
        self._send({"error": "Unknown control path", "reason_code": "CONTROL_ROUTE_NOT_FOUND"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/control/actions":
            self._send({"error": "Unknown control path", "reason_code": "CONTROL_ROUTE_NOT_FOUND"}, HTTPStatus.NOT_FOUND)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError):
            self._send({"error": "Invalid JSON body", "reason_code": "CONTROL_JSON_INVALID"}, HTTPStatus.BAD_REQUEST)
            return
        action = normalize_action(body.get("action") if isinstance(body, dict) else None)
        if action is None:
            self._send({"error": "Unsupported lifecycle action", "reason_code": "CONTROL_ACTION_INVALID"}, HTTPStatus.BAD_REQUEST)
            return
        if action == "check_update":
            self._send({"operation_id": "check-update", "status": "SUCCEEDED", "result": check_update(self.root), "secrets_included": False})
            return
        if action == "apply_update":
            update = check_update(self.root)
            if update.get("status") != "AVAILABLE":
                self._send({"operation_id": "apply-update", "status": "BLOCKED", "result": update, "secrets_included": False})
                return
        self._send(_spawn_action(self.root, action), HTTPStatus.ACCEPTED)


def serve(*, root: Path, host: str, port: int) -> None:
    handler = type("BoundControlHandler", (ControlHandler,), {"root": root.resolve()})
    server = ThreadingHTTPServer((host, port), handler)
    print(json.dumps({"host": host, "port": port, "status": "serving"}), flush=True)
    server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("serve", "status", "check_update"))
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument("--host", default=CONTROL_HOST)
    parser.add_argument("--port", type=int, default=CONTROL_PORT)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if args.command == "serve":
        serve(root=root, host=args.host, port=args.port)
        return 0
    payload = build_control_status(root) if args.command == "status" else check_update(root)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("status") not in {"BLOCKED", "UNAVAILABLE", "PARTIAL"} else 1


if __name__ == "__main__":
    raise SystemExit(main())

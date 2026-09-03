"""Windows-first project preflight and repair commands for IMP."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_PACKAGES = ("tzdata", "numpy", "pymongo", "scikit-learn")


def _check(
    check_id: str,
    label: str,
    status: str,
    detail: str,
    *,
    required: bool = True,
    next_action: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": check_id,
        "label": label,
        "status": status,
        "detail": detail,
        "required": required,
    }
    if next_action:
        row["next_action"] = next_action
    return row


def _default_executable_available(name: str) -> bool:
    return shutil.which(name) is not None


def _env_status(root: Path) -> tuple[str, str, str | None]:
    env_path = root / ".env"
    if not env_path.exists():
        return "OPTIONAL", "No local .env; safe defaults will be used.", "Create .env only for optional providers."
    try:
        for line_number, raw_line in enumerate(env_path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line or not line.split("=", 1)[0].strip():
                return "FAIL", f"Malformed entry at line {line_number}.", "Fix the .env entry and run setup again."
    except OSError:
        return "FAIL", "The local .env file cannot be read.", "Check file permissions and retry setup."
    return "PASS", "Local environment file is readable.", None


def collect_preflight(
    root: Path | None = None,
    *,
    python_version: tuple[int, int] | None = None,
    node_available: bool | None = None,
    npm_available: bool | None = None,
    git_available: bool | None = None,
) -> dict[str, Any]:
    """Return a value-blind, deterministic report of local setup readiness."""

    repository = (root or ROOT).resolve()
    version = python_version or (sys.version_info.major, sys.version_info.minor)
    node_ok = _default_executable_available("node") if node_available is None else node_available
    npm_ok = _default_executable_available("npm.cmd" if os.name == "nt" else "npm") if npm_available is None else npm_available
    git_ok = _default_executable_available("git") if git_available is None else git_available

    checks = [
        _check(
            "python",
            "Python 3.11",
            "PASS" if version == (3, 11) else "FAIL",
            f"Detected Python {version[0]}.{version[1]}.",
            next_action="Install CPython 3.11 and run setup again." if version != (3, 11) else None,
        ),
        _check(
            "node",
            "Node.js",
            "PASS" if node_ok else "FAIL",
            "Node.js is available on PATH." if node_ok else "Node.js is not available on PATH.",
            next_action="Install Node.js LTS, then run setup again." if not node_ok else None,
        ),
        _check(
            "npm",
            "npm",
            "PASS" if npm_ok else "FAIL",
            "npm is available on PATH." if npm_ok else "npm is not available on PATH.",
            next_action="Install Node.js LTS, then run setup again." if not npm_ok else None,
        ),
        _check(
            "git",
            "Git",
            "PASS" if git_ok else "OPTIONAL",
            "Git is available on PATH." if git_ok else "Git is unavailable; application update checks are disabled.",
            required=False,
            next_action="Install Git to enable application update checks." if not git_ok else None,
        ),
        _check(
            "api_entrypoint",
            "Platform API source",
            "PASS" if (repository / "tools/ui1/run_ui_api.py").is_file() else "FAIL",
            "API entrypoint found." if (repository / "tools/ui1/run_ui_api.py").is_file() else "API entrypoint is missing.",
            next_action="Restore tools/ui1/run_ui_api.py from the repository." if not (repository / "tools/ui1/run_ui_api.py").is_file() else None,
        ),
        _check(
            "python_environment",
            "Project Python environment",
            "PASS" if (repository / ".venv/Scripts/python.exe").is_file() else "ACTION_REQUIRED",
            "Project .venv is ready." if (repository / ".venv/Scripts/python.exe").is_file() else "Project .venv is missing.",
            next_action="Run setup to create the project environment." if not (repository / ".venv/Scripts/python.exe").is_file() else None,
        ),
        _check(
            "ui_dependencies",
            "UI dependencies",
            "PASS" if (repository / "ui/node_modules").is_dir() else "ACTION_REQUIRED",
            "UI dependencies are installed." if (repository / "ui/node_modules").is_dir() else "ui/node_modules is missing.",
            next_action="Run setup to install UI dependencies." if not (repository / "ui/node_modules").is_dir() else None,
        ),
    ]
    env_state, env_detail, env_action = _env_status(repository)
    checks.append(_check("local_env", "Local configuration", env_state, env_detail, required=False, next_action=env_action))

    required_failures = [row for row in checks if row["required"] and row["status"] not in {"PASS", "OPTIONAL"}]
    action_required = [row for row in checks if row["status"] == "ACTION_REQUIRED"]
    status = "BLOCKED" if required_failures else ("ACTION_REQUIRED" if action_required else "READY")
    return {
        "schema_version": "operator-preflight/1.0",
        "status": status,
        "root": str(repository),
        "checks": checks,
        "secrets_included": False,
        "next_action": (
            "Install the missing system prerequisite(s)."
            if required_failures
            else "Run setup to repair the project environment."
            if action_required
            else "Ready to start the platform."
        ),
    }


def _run(command: list[str], *, cwd: Path) -> None:
    completed = subprocess.run(command, cwd=str(cwd), check=False)
    if completed.returncode:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {command[0]}")


def write_preflight_reports(root: Path, report: dict[str, Any]) -> None:
    """Persist value-blind JSON and human-readable preflight reports."""

    local = root / ".local"
    local.mkdir(parents=True, exist_ok=True)
    (local / "preflight.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lines = [
        "Integrated Market Platform preflight",
        f"Status: {report.get('status', 'UNKNOWN')}",
        f"Next action: {report.get('next_action', 'Review the checks below.')}",
        "",
    ]
    for check in report.get("checks", []):
        lines.append(
            f"[{check.get('status', 'UNKNOWN')}] {check.get('label', check.get('id', 'check'))}: {check.get('detail', '')}"
        )
        if check.get("next_action"):
            lines.append(f"  Next: {check['next_action']}")
    (local / "preflight.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def setup_project(root: Path | None = None) -> dict[str, Any]:
    """Repair project-local dependencies, then return a fresh preflight report."""

    repository = (root or ROOT).resolve()
    python_executable = repository / ".venv/Scripts/python.exe"
    if not python_executable.is_file():
        system_python = shutil.which("py") or shutil.which("python")
        if not system_python:
            raise RuntimeError("Python 3.11 is required to create .venv")
        if Path(system_python).name.casefold() == "py.exe":
            _run([system_python, "-3.11", "-m", "venv", str(repository / ".venv")], cwd=repository)
        else:
            if (sys.version_info.major, sys.version_info.minor) != (3, 11):
                raise RuntimeError("The Python executable on PATH is not CPython 3.11; install Python 3.11 or use the py launcher")
            _run([system_python, "-m", "venv", str(repository / ".venv")], cwd=repository)
    python_executable = repository / ".venv/Scripts/python.exe"
    if not python_executable.is_file():
        raise RuntimeError(".venv creation completed without Scripts/python.exe")

    _run([str(python_executable), "-m", "pip", "install", *RUNTIME_PACKAGES], cwd=repository)
    ui = repository / "ui"
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise RuntimeError("npm is required to install UI dependencies")
    _run([npm, "ci"], cwd=ui)
    (repository / ".local").mkdir(parents=True, exist_ok=True)
    (repository / ".private").mkdir(parents=True, exist_ok=True)
    report = collect_preflight(repository)
    write_preflight_reports(repository, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "setup"))
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        report = collect_preflight(root) if args.command == "check" else setup_project(root)
        if args.command == "check":
            write_preflight_reports(root, report)
    except (OSError, RuntimeError) as exc:
        print(json.dumps({"schema_version": "operator-preflight/1.0", "status": "BLOCKED", "error": str(exc), "secrets_included": False}))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())

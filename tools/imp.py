"""Canonical IMP developer command router.

This is intentionally a thin, standard-library-only facade over the existing
manifest validator and the repository's explicit UI commands. It centralizes
workflow selection without becoming a second test or suite inventory.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLOSURE_REPORT = Path("artifacts/developer-workflow/closure-report.json")
DEFAULT_TELEMETRY_PATH = Path(".local/developer-workflow/telemetry.jsonl")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def _telemetry_path(root: Path) -> Path:
    configured = os.environ.get("IMP_TELEMETRY_PATH")
    path = Path(configured) if configured else root / DEFAULT_TELEMETRY_PATH
    return path if path.is_absolute() else root / path


def _record_telemetry(
    root: Path,
    *,
    command: str,
    argv: Sequence[str],
    exit_code: int,
    wall_seconds: float,
) -> None:
    path = _telemetry_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "schema_version": "1.0",
        "event_type": "developer_command",
        "recorded_at": _utc_now(),
        "command": command,
        "argv": list(argv),
        "exit_code": exit_code,
        "status": "passed" if exit_code == 0 else "failed",
        "wall_seconds": round(wall_seconds, 6),
        "ci": os.environ.get("CI", "").lower() == "true",
    }
    iteration = os.environ.get("IMP_AGENT_ITERATION")
    if iteration and iteration.isdigit():
        event["agent_iteration"] = int(iteration)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")


def _run(
    root: Path,
    *,
    label: str,
    command: Sequence[str],
    env: dict[str, str] | None = None,
    telemetry_root: Path | None = None,
    stream_output: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    if stream_output:
        completed = subprocess.run(list(command), cwd=str(root), env=env, check=False)
    else:
        completed = subprocess.run(
            list(command),
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    wall_seconds = time.perf_counter() - started
    if completed.stdout:
        print(completed.stdout, end="" if completed.stdout.endswith("\n") else "\n")
    if completed.stderr:
        print(completed.stderr, file=sys.stderr, end="" if completed.stderr.endswith("\n") else "\n")
    _record_telemetry(
        telemetry_root or root,
        command=label,
        argv=command,
        exit_code=completed.returncode,
        wall_seconds=wall_seconds,
    )
    return {
        "command": label,
        "argv": list(command),
        "status": "passed" if completed.returncode == 0 else "failed",
        "exit_code": completed.returncode,
        "wall_seconds": round(wall_seconds, 6),
    }


def summarize_telemetry(root: Path) -> dict[str, Any]:
    path = _telemetry_path(root)
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        lines = []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("event_type") == "developer_command":
            events.append(event)
    command_counts: dict[str, int] = {}
    for event in events:
        command = str(event.get("command", "unknown"))
        command_counts[command] = command_counts.get(command, 0) + 1
    return {
        "events": len(events),
        "command_counts": dict(sorted(command_counts.items())),
        "redundant_command_events": sum(max(0, count - 1) for count in command_counts.values()),
        "validation_wall_seconds": round(
            sum(
                float(event.get("wall_seconds", 0.0))
                for event in events
                if str(event.get("command", "")).startswith(("validate ", "test ", "closure "))
            ),
            6,
        ),
        "ci_wall_seconds": round(
            sum(float(event.get("wall_seconds", 0.0)) for event in events if event.get("ci") is True),
            6,
        ),
        "agent_iterations": sorted(
            {
                int(event["agent_iteration"])
                for event in events
                if isinstance(event.get("agent_iteration"), int)
            }
        ),
    }


def _python_environment(root: Path) -> dict[str, str]:
    environment = dict(os.environ)
    pythonpath = [str(root / "src"), str(root)]
    if environment.get("PYTHONPATH"):
        pythonpath.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(pythonpath)
    return environment


def _npm_executable() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def classify_changed_area(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("ui/"):
        return "ui"
    if normalized.startswith("docs/") or normalized in {"README.md", "AGENTS.md"}:
        return "documentation"
    if (
        normalized.startswith("tools/")
        or normalized.startswith(".cursor/")
        or normalized.startswith("manifests/")
    ):
        return "developer-tooling"
    if normalized.startswith("tests/"):
        return "tests"
    if normalized.startswith("fixtures/") or normalized.startswith("evidence/"):
        return "fixtures"
    if "/paper/" in f"/{normalized}" or normalized.startswith("src/market_platform_foundation/paper/"):
        return "paper"
    if normalized.startswith("src/"):
        return "backend"
    if normalized.startswith(".github/"):
        return "ci"
    return "other"


def build_closure_report(
    *,
    repository_root: Path,
    changed_files: Sequence[str],
    validation_evidence: dict[str, Any],
    baseline_failures: Sequence[dict[str, Any]],
    documentation_changes: Sequence[str],
    risk_status: str,
) -> dict[str, Any]:
    areas = sorted({classify_changed_area(path) for path in changed_files})
    return {
        "schema_version": "1.0",
        "report_type": "imp_closure",
        "generated_at": _utc_now(),
        "repository_root": str(repository_root.resolve()),
        "changed_files": sorted(set(changed_files)),
        "changed_areas": areas,
        "documentation_changes": sorted(set(documentation_changes)),
        "baseline": {
            "classification": "pre_existing_dirty_tree",
            "failures": [dict(row) for row in baseline_failures],
        },
        "validation": validation_evidence,
        "risk": {
            "status": risk_status,
            "live_execution_authorized": False,
            "paper_authority_changed": any(
                area == "paper" for area in areas
            ),
        },
        "telemetry": {
            "path": str(_telemetry_path(repository_root).resolve()),
            "enabled": True,
            "summary": summarize_telemetry(repository_root),
        },
    }


def _git_changed_files(root: Path) -> tuple[str, ...]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", "-z"],
        cwd=str(root),
        capture_output=True,
        check=False,
    )
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "-z"],
        cwd=str(root),
        capture_output=True,
        check=False,
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=str(root),
        capture_output=True,
        check=False,
    )
    if any(result.returncode != 0 for result in (completed, staged, untracked)):
        return ()
    values = completed.stdout.split(b"\0") + staged.stdout.split(b"\0") + untracked.stdout.split(b"\0")
    return tuple(sorted({value.decode("utf-8", errors="replace") for value in values if value}))


def _baseline_failures(root: Path, path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    validation = payload.get("validation", {}) if isinstance(payload, dict) else {}
    rows: list[dict[str, Any]] = []
    for mode in ("changed", "full"):
        value = validation.get(mode, {}) if isinstance(validation, dict) else {}
        if not isinstance(value, dict):
            continue
        failures = int(value.get("failures", 0) or 0)
        errors = int(value.get("errors", 0) or 0)
        if failures or errors:
            rows.append(
                {
                    "mode": mode,
                    "failures": failures,
                    "errors": errors,
                    "wall_seconds": value.get("wall_seconds"),
                    "areas": value.get("areas", []),
                }
            )
    return rows


def _read_validation_summary(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return fallback
    if not isinstance(payload, dict):
        return fallback
    return {
        "status": payload.get("status", fallback["status"]),
        "mode": payload.get("mode", fallback["command"]),
        "tests_run": payload.get("tests_run", 0),
        "skips": payload.get("skips", 0),
        "failures": payload.get("failures", 0),
        "errors": payload.get("errors", 0),
        "wall_seconds": payload.get("wall_seconds", fallback["wall_seconds"]),
        "full_suite_required": payload.get("full_suite_required", False),
        "selected_suites": payload.get("selected_suites", []),
    }


def _validation_command(root: Path, mode: str, args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        str(root / "tools" / "validate.py"),
        mode,
    ]
    if getattr(args, "target", None):
        command.append(args.target)
    if getattr(args, "workers", None):
        command.extend(["--workers", str(args.workers)])
    if getattr(args, "baseline", None):
        command.extend(["--baseline", str(args.baseline)])
    if getattr(args, "paths_file", None):
        command.extend(["--paths-file", str(args.paths_file)])
    if getattr(args, "json_path", None):
        command.extend(["--json", str(args.json_path)])
    if getattr(args, "explain", False):
        command.append("--explain")
    if getattr(args, "fail_fast", False):
        command.append("--fail-fast")
    result = _run(
        root,
        label=f"validate {mode}",
        command=command,
        env=_python_environment(root),
        stream_output=True,
    )
    return int(result["exit_code"])


def _diagnostics(root: Path) -> dict[str, Any]:
    status = subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    lines = status.stdout.splitlines()
    return {
        "schema_version": "1.0",
        "report_type": "imp_environment",
        "generated_at": _utc_now(),
        "repository_root": str(root.resolve()),
        "branch": lines[0] if lines else "unknown",
        "changed_file_count": len(_git_changed_files(root)),
        "python": {"executable": sys.executable, "version": platform.python_version()},
        "node": {"available": shutil.which("node") is not None},
        "npm": {"available": shutil.which("npm") is not None},
        "validation_manifest": (root / "tools" / "validation_manifest.json").is_file(),
        "live_gate_values_present": sorted(
            name
            for name in os.environ
            if name.startswith("IMP_") and ("LIVE" in name or "EXECUTION" in name)
        ),
        "safety_note": "Diagnostics never authorize execution and do not print gate values.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    groups = parser.add_subparsers(dest="group", required=True)

    env = groups.add_parser("env", help="show safe environment diagnostics")
    env.add_argument("--json", dest="json_path", type=Path)

    formatting = groups.add_parser("format", help="check changed-file whitespace")
    formatting.add_argument("--json", dest="json_path", type=Path)

    lint = groups.add_parser("lint", help="run cheap syntax/type checks")
    lint.add_argument("--all", action="store_true", dest="all_files")
    lint.add_argument("--json", dest="json_path", type=Path)

    tests = groups.add_parser("test", help="run affected or focused tests")
    test_actions = tests.add_subparsers(dest="action", required=True)
    affected = test_actions.add_parser("affected", help="run manifest-selected affected suites")
    affected.add_argument("--workers", type=int, default=2)
    affected.add_argument("--baseline", type=Path)
    affected.add_argument("--paths-file", type=Path)
    affected.add_argument("--json", dest="json_path", type=Path)
    affected.add_argument("--explain", action="store_true")
    affected.add_argument("--fail-fast", action="store_true")
    focused = test_actions.add_parser("focused", help="run explicit unittest selectors")
    focused.add_argument("selectors", nargs="+")
    focused.add_argument("--json", dest="json_path", type=Path)

    validation = groups.add_parser("validate", help="run canonical validation modes")
    validation_actions = validation.add_subparsers(dest="action", required=True)
    for action in ("fast", "changed", "full"):
        command = validation_actions.add_parser(action)
        command.add_argument("--workers", type=int, default=2)
        if action == "changed":
            command.add_argument("--baseline", type=Path)
            command.add_argument("--paths-file", type=Path)
        command.add_argument("--json", dest="json_path", type=Path)
        command.add_argument("--explain", action="store_true")
        command.add_argument("--fail-fast", action="store_true")
    domain = validation_actions.add_parser("domain")
    domain.add_argument("target")
    domain.add_argument("--workers", type=int, default=2)
    domain.add_argument("--json", dest="json_path", type=Path)
    live = validation_actions.add_parser("live")
    live.add_argument("target")
    live.add_argument("--workers", type=int, default=1)
    live.add_argument("--json", dest="json_path", type=Path)

    review = groups.add_parser("review", help="run pre-review format and affected gates")
    review.add_argument("--workers", type=int, default=2)
    review.add_argument("--json", dest="json_path", type=Path)

    closure = groups.add_parser("closure", help="run final evidence and write a closure report")
    closure.add_argument("--baseline-report", type=Path, default=Path("artifacts/developer-workflow/baseline.json"))
    closure.add_argument("--output", type=Path, default=DEFAULT_CLOSURE_REPORT)
    closure.add_argument("--workers", type=int, default=2)
    closure.add_argument("--skip-ui", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = REPOSITORY_ROOT
    if args.group == "env":
        report = _diagnostics(root)
        if args.json_path:
            _write_json(args.json_path, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0

    if args.group == "format":
        result = _run(root, label="format", command=["git", "diff", "--check"])
        if args.json_path:
            _write_json(args.json_path, result)
        return int(result["exit_code"])

    if args.group == "lint":
        results = [
            _run(
                root,
                label="lint python",
                command=[sys.executable, "-m", "compileall", "-q", "src", "tests", "tools"],
                env=_python_environment(root),
            )
        ]
        changed = _git_changed_files(root)
        if args.all_files or any(path.startswith("ui/") for path in changed):
            results.append(
                _run(
                    root / "ui",
                    label="lint ui",
                    command=[_npm_executable(), "run", "typecheck"],
                    env=dict(os.environ),
                    telemetry_root=root,
                )
            )
        status = "passed" if all(row["exit_code"] == 0 for row in results) else "failed"
        report = {"schema_version": "1.0", "status": status, "checks": results}
        if args.json_path:
            _write_json(args.json_path, report)
        return 0 if status == "passed" else 1

    if args.group == "test" and args.action == "affected":
        return _validation_command(root, "changed", args)

    if args.group == "test" and args.action == "focused":
        command = [
            sys.executable,
            str(root / "tools" / "validation_worker.py"),
            "--repository-root",
            str(root),
            "--suite-id",
            "focused",
        ]
        for selector in args.selectors:
            command.extend(["--selector", selector])
        result = _run(root, label="test focused", command=command, env=_python_environment(root))
        if args.json_path:
            _write_json(args.json_path, result)
        return int(result["exit_code"])

    if args.group == "validate":
        return _validation_command(root, args.action, args)

    if args.group == "review":
        format_result = _run(root, label="review format", command=["git", "diff", "--check"])
        review_json = root / ".local" / "developer-workflow" / "review-validation.json"
        changed_args = argparse.Namespace(
            target=None,
            workers=args.workers,
            baseline=None,
            paths_file=None,
            json_path=review_json,
            explain=True,
            fail_fast=True,
        )
        changed_exit = _validation_command(root, "changed", changed_args)
        report = {
            "schema_version": "1.0",
            "report_type": "imp_review",
            "status": "passed" if format_result["exit_code"] == 0 and changed_exit == 0 else "failed",
            "format": format_result,
            "changed": _read_validation_summary(
                review_json,
                {
                    "command": "changed",
                    "status": "passed" if changed_exit == 0 else "failed",
                    "wall_seconds": 0,
                },
            ),
        }
        if args.json_path:
            _write_json(args.json_path, report)
        return 0 if format_result["exit_code"] == 0 and changed_exit == 0 else 1

    if args.group == "closure":
        changed_files = _git_changed_files(root)
        full_json = root / ".local" / "developer-workflow" / "full-validation.json"
        full_args = argparse.Namespace(
            target=None,
            workers=args.workers,
            baseline=None,
            json_path=full_json,
            explain=False,
            fail_fast=False,
        )
        full_exit = _validation_command(root, "full", full_args)
        evidence: dict[str, Any] = {
            "full": _read_validation_summary(
                full_json,
                {"command": "full", "status": "passed" if full_exit == 0 else "failed", "wall_seconds": 0},
            )
        }
        format_result = _run(root, label="closure format", command=["git", "diff", "--check"])
        evidence["format"] = format_result
        docs_changed = tuple(path for path in changed_files if classify_changed_area(path) == "documentation")
        if docs_changed:
            docs_result = _run(
                root,
                label="closure docs",
                command=[sys.executable, str(root / "tools" / "check_docs_links.py")],
                env=_python_environment(root),
            )
            evidence["documentation"] = docs_result
        if not args.skip_ui and any(path.startswith("ui/") for path in changed_files):
            for label, command in (
                        ("closure ui test", [_npm_executable(), "test", "--", "--run"]),
                        ("closure ui typecheck", [_npm_executable(), "run", "typecheck"]),
                        ("closure ui build", [_npm_executable(), "run", "build"]),
            ):
                evidence[label] = _run(
                    root / "ui",
                    label=label,
                    command=command,
                    env=dict(os.environ),
                    telemetry_root=root,
                )
        baseline_failures = _baseline_failures(root, args.baseline_report)
        risk_status = "blocked_by_validation" if full_exit != 0 else "review_required"
        report = build_closure_report(
            repository_root=root,
            changed_files=changed_files,
            validation_evidence=evidence,
            baseline_failures=baseline_failures,
            documentation_changes=docs_changed,
            risk_status=risk_status,
        )
        _write_json(root / args.output, report)
        print(f"Wrote closure report: {args.output}")
        return full_exit

    return 2


if __name__ == "__main__":
    raise SystemExit(main())

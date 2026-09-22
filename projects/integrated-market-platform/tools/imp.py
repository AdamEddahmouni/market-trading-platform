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
        "environment": _load_environment_module().build_environment_report(repository_root),
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
        "core_checkpoint_required": payload.get("core_checkpoint_required", False),
        "selected_suites": payload.get("selected_suites", []),
    }


def _validation_command(root: Path, mode: str, args: argparse.Namespace) -> int:
    command = [
        _validation_python(root),
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
    if getattr(args, "plan", False):
        command.append("--plan")
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


HARD_PYTHON_VERSION = (3, 11)
_MANIFEST_READABLE: bool | None = None


def _supported_python() -> bool:
    try:
        major, minor = (int(part) for part in platform.python_version_tuple()[:2])
    except (TypeError, ValueError, IndexError):
        return False
    return (major, minor) >= HARD_PYTHON_VERSION


def _manifest_readable(root: Path) -> bool:
    global _MANIFEST_READABLE
    if _MANIFEST_READABLE is not None:
        return _MANIFEST_READABLE
    try:
        try:
            from tools.validation_manifest import load_manifest
        except ModuleNotFoundError:  # pragma: no cover - direct script execution.
            from validation_manifest import load_manifest  # type: ignore[no-redef]

        load_manifest(root / "tools" / "validation_manifest.json", repository_root=root)
    except Exception:
        _MANIFEST_READABLE = False
        return False
    _MANIFEST_READABLE = True
    return True


def _load_storage_audit_module():
    try:
        from tools import storage_audit as storage_module
    except ModuleNotFoundError:  # pragma: no cover - direct script execution.
        import storage_audit as storage_module  # type: ignore[no-redef]
    return storage_module


def _storage_command(root: Path, args: argparse.Namespace) -> int:
    if args.action != "audit":
        print(f"unknown storage action: {args.action}", file=sys.stderr)
        return 2
    storage_module = _load_storage_audit_module()
    argv = []
    if getattr(args, "json", False):
        argv.append("--json")
    if getattr(args, "top", None) is not None:
        argv.extend(["--top", str(args.top)])
    if getattr(args, "include_cursor", False):
        argv.append("--include-cursor")
    if getattr(args, "root", None) is not None:
        argv.extend(["--root", str(args.root)])
    if getattr(args, "quiet", False):
        argv.append("--quiet")
    return int(storage_module.run_cli(argv, repository_root=root))


def _load_environment_module():
    try:
        from tools import environment as environment_module
    except ModuleNotFoundError:  # pragma: no cover - direct script execution.
        import environment as environment_module  # type: ignore[no-redef]
    return environment_module


def _load_ci_job_selector():
    try:
        from tools import ci_job_selector as selector_module
    except ModuleNotFoundError:  # pragma: no cover - direct script execution.
        import ci_job_selector as selector_module  # type: ignore[no-redef]
    return selector_module


def _ci_jobs_command(root: Path, args: argparse.Namespace) -> int:
    selector = _load_ci_job_selector()
    paths_readable = True
    try:
        explicit = selector.load_paths(getattr(args, "paths", ()), paths_file=args.paths_file)
    except OSError as exc:
        print(f"ci jobs: failed to read paths: {exc}", file=sys.stderr)
        explicit = ()
        paths_readable = False
    if explicit:
        paths = explicit
    elif not paths_readable:
        paths = ()
    elif args.always_run:
        paths = ()
    else:
        paths = tuple(
            path
            for path in (selector.normalize_changed_path(item) for item in _git_changed_files(root))
            if path
        )
    selection = selector.select_ci_jobs(
        paths,
        always_run=args.always_run,
        paths_readable=paths_readable,
    )
    if args.json_path:
        _write_json(args.json_path, selection)
    print(json.dumps(selection, indent=2, sort_keys=True))
    return 0


def _load_opend_hop_interpreter():
    root = str(REPOSITORY_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from tools.moomoo import opend_hop_interpreter as hop_module

    return hop_module


def _validation_python(root: Path) -> str:
    environment_module = _load_environment_module()
    try:
        return str(environment_module.effective_python_executable(root))
    except RuntimeError:
        return sys.executable


def _environment_status(report: dict[str, Any]) -> tuple[str, list[str]]:
    """Derive env health from prerequisite checks.

    Hard prerequisites (unsupported Python, missing git, invalid repository
    root, unreadable validation manifest) fail the command. Optional
    capabilities (node/npm) degrade the report but never fail it.
    """

    checks = report.get("prerequisites", {})
    hard: list[str] = []
    resolved_supported = checks.get("resolved_python_supported", checks.get("python_version_supported", True))
    if not resolved_supported:
        hard.append("unsupported resolved python interpreter")
    if not checks.get("git_available", False):
        hard.append("missing git executable")
    if not checks.get("repository_root_valid", False):
        hard.append("invalid repository root")
    if not checks.get("manifest_readable", False):
        hard.append("unreadable validation manifest")
    if not checks.get("timezone_ready", True):
        hard.append("missing timezone data")
    if hard:
        return ("unhealthy", hard)
    optional: list[str] = []
    if not checks.get("node_available", True):
        optional.append("node")
    if not checks.get("npm_available", True):
        optional.append("npm")
    return ("degraded" if optional else "healthy", [])


def _diagnostics(root: Path) -> dict[str, Any]:
    status = subprocess.run(
        ["git", "status", "--short", "--branch"],
        cwd=str(root),
        capture_output=True,
        text=True,
        check=False,
    )
    lines = status.stdout.splitlines()
    manifest_path = root / "tools" / "validation_manifest.json"
    environment_module = _load_environment_module()
    environment_report = environment_module.build_environment_report(root)
    tz_ready = bool(environment_report["timezone"]["ready"])
    resolved = environment_report["python"]
    return {
        "schema_version": "1.1",
        "report_type": "imp_environment",
        "generated_at": _utc_now(),
        "repository_root": str(root.resolve()),
        "branch": lines[0] if lines else "unknown",
        "changed_file_count": len(_git_changed_files(root)),
        "python": {
            "executable": sys.executable,
            "version": platform.python_version(),
            "resolved_executable": resolved["resolved_executable"],
            "resolved_version": resolved["resolved_version"],
            "resolution_source": resolved["resolution_source"],
        },
        "worktree": environment_report.get("worktree"),
        "environment": environment_report.get("environment"),
        "node": {"available": shutil.which("node") is not None},
        "npm": {"available": shutil.which("npm") is not None},
        "validation_manifest": manifest_path.is_file(),
        "prerequisites": {
            "python_version_supported": _supported_python(),
            "resolved_python_supported": bool(resolved["supported"]),
            "git_available": shutil.which("git") is not None,
            "repository_root_valid": manifest_path.is_file() and (root / "src").is_dir(),
            "manifest_readable": _manifest_readable(root),
            "timezone_ready": tz_ready,
            "node_available": shutil.which("node") is not None,
            "npm_available": shutil.which("npm") is not None,
        },
        "next_commands": environment_report.get("next_commands", []),
        "live_gate_values_present": sorted(
            name
            for name in os.environ
            if name.startswith("IMP_") and ("LIVE" in name or "EXECUTION" in name)
        ),
        "performance": _performance_env_summary(root),
        "safety_note": "Diagnostics never authorize execution and do not print gate values.",
    }


def _performance_env_summary(root: Path) -> dict[str, Any]:
    try:
        from tools.performance_telemetry import performance_status_for_env
    except ModuleNotFoundError:  # pragma: no cover - direct script execution.
        from performance_telemetry import performance_status_for_env  # type: ignore[no-redef]
    return performance_status_for_env(root)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    groups = parser.add_subparsers(dest="group", required=True)

    env = groups.add_parser("env", help="show safe environment diagnostics")
    env.add_argument("--json", dest="json_path", type=Path)
    env_actions = env.add_subparsers(dest="env_action")
    bootstrap = env_actions.add_parser(
        "bootstrap",
        help="explicitly link a shared canonical virtual environment into this worktree",
    )
    bootstrap.add_argument(
        "--link-venv",
        action="store_true",
        help="create a local .venv junction/symlink to the discovered canonical environment",
    )
    bootstrap.add_argument(
        "--force",
        action="store_true",
        help="replace an existing mismatched .venv link",
    )
    env_actions.add_parser(
        "install-opend",
        help="install optional vendor OpenD SDK (moomoo-api) into the IMP interpreter",
    )

    state_path = groups.add_parser(
        "state-path",
        help="compare effective vs canonical IMP durable state directories",
    )
    state_path.add_argument("--json", dest="json_path", type=Path)

    storage = groups.add_parser(
        "storage",
        help="read-only repository storage observability (never deletes)",
    )
    storage_actions = storage.add_subparsers(dest="action", required=True)
    storage_audit = storage_actions.add_parser(
        "audit",
        help="non-destructive storage audit; output is advisory and is not deletion authority",
    )
    storage_audit.add_argument("--json", action="store_true", help="Machine-readable JSON")
    storage_audit.add_argument("--top", type=int, default=25, help="Largest-path rank count")
    storage_audit.add_argument(
        "--include-cursor",
        action="store_true",
        help="Inspect this repository's project-scoped Cursor storage (sizes only)",
    )
    storage_audit.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Override scan/git root (tests and explicit local roots)",
    )
    storage_audit.add_argument("--quiet", action="store_true", help="Suppress progress on stderr")

    ci = groups.add_parser("ci", help="classify expensive CI slices without running product code")
    ci_actions = ci.add_subparsers(dest="action", required=True)
    ci_jobs = ci_actions.add_parser(
        "jobs",
        help="report which expensive GitHub CI slices current changes need",
    )
    ci_jobs.add_argument("paths", nargs="*", help="optional explicit changed paths")
    ci_jobs.add_argument("--paths-file", type=Path)
    ci_jobs.add_argument("--always-run", action="store_true")
    ci_jobs.add_argument("--json", dest="json_path", type=Path)

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
    affected.add_argument("--plan", action="store_true")
    affected.add_argument("--fail-fast", action="store_true")
    focused = test_actions.add_parser("focused", help="run explicit unittest selectors")
    focused.add_argument("selectors", nargs="+")
    focused.add_argument("--json", dest="json_path", type=Path)

    validation = groups.add_parser("validate", help="run canonical validation modes")
    validation_actions = validation.add_subparsers(dest="action", required=True)
    for action in ("fast", "changed", "full", "e2e"):
        command = validation_actions.add_parser(action)
        command.add_argument("--workers", type=int, default=2)
        if action == "changed":
            command.add_argument("--baseline", type=Path)
            command.add_argument("--paths-file", type=Path)
        command.add_argument("--json", dest="json_path", type=Path)
        command.add_argument("--explain", action="store_true")
        command.add_argument("--plan", action="store_true")
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

    providers = groups.add_parser(
        "providers",
        help="provider capability matrix and readiness diagnostics (read-only)",
    )
    provider_actions = providers.add_subparsers(dest="action", required=True)
    capability_matrix = provider_actions.add_parser(
        "capability-matrix",
        help="emit deterministic capability-matrix snapshot",
    )
    capability_matrix.add_argument(
        "--output",
        type=Path,
        help="Write snapshot JSON (default: stdout)",
    )
    capability_matrix.add_argument(
        "--skip-readiness",
        action="store_true",
        help="Do not merge provider_readiness gate rows",
    )
    audit = provider_actions.add_parser(
        "audit",
        help="capability-matrix audit merged with value-blind readiness",
    )
    audit.add_argument("--json", action="store_true", help="Machine-readable JSON")
    audit.add_argument(
        "--probe-local",
        action="store_true",
        help="Probe loopback Moomoo/IBKR ports when building rows",
    )
    gaps = provider_actions.add_parser(
        "gaps",
        help="coverage-gap report for a campaign requirement profile",
    )
    gaps.add_argument(
        "--profile",
        default="FTEP-V1-001",
        help="Campaign requirement profile id (default: FTEP-V1-001)",
    )
    gaps.add_argument("--json", action="store_true", help="Machine-readable JSON")
    gaps.add_argument("--probe-local", action="store_true")
    campaign_readiness = provider_actions.add_parser(
        "campaign-readiness",
        help="fail-closed preflight + gap-engine readiness for a campaign slug",
    )
    campaign_readiness.add_argument(
        "campaign_slug",
        nargs="?",
        default="FTEP-V1-001",
        help="Forward-test campaign slug (default: FTEP-V1-001)",
    )
    campaign_readiness.add_argument("--json", action="store_true")
    campaign_readiness.add_argument("--probe-local", action="store_true")

    ftep = groups.add_parser("ftep", help="read-only FTEP campaign observability")
    ftep_actions = ftep.add_subparsers(dest="action", required=True)
    campaign_status = ftep_actions.add_parser(
        "campaign-status",
        help="compose campaign progress from receipts and readiness gates",
    )
    campaign_status.add_argument(
        "campaign_slug",
        nargs="?",
        default="FTEP-V1-002",
        help="Forward-test campaign slug (default: FTEP-V1-002)",
    )
    campaign_status.add_argument("--json", action="store_true", help="Machine-readable JSON")
    campaign_status.add_argument(
        "--probe-local",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    opportunity_summaries = ftep_actions.add_parser(
        "opportunity-summaries",
        help="read-only ranked opportunity summaries from sample/fixture rows",
    )
    opportunity_summaries.add_argument(
        "--campaign-slug",
        default="FTEP-V1-002",
        help="Campaign slug stamped on summaries (default: FTEP-V1-002)",
    )
    opportunity_summaries.add_argument("--json", action="store_true")
    opportunity_summaries.add_argument(
        "--sample",
        action="store_true",
        help="Use built-in fixture attention rows",
    )
    opportunity_summaries.add_argument(
        "--input",
        type=Path,
        help="Optional JSON file with attention-candidate rows",
    )
    integrity_check = ftep_actions.add_parser(
        "integrity-check",
        help="deterministic manifest and readiness integrity assertions",
    )
    integrity_check.add_argument(
        "campaign_slug",
        nargs="?",
        default="FTEP-V1-002",
        help="Forward-test campaign slug (default: FTEP-V1-002)",
    )
    integrity_check.add_argument("--json", action="store_true", help="Machine-readable JSON")
    session_start = ftep_actions.add_parser(
        "session-start",
        help="governed SIGNAL_ONLY session start (--dry-run gates only)",
    )
    session_start.add_argument(
        "campaign_slug",
        nargs="?",
        default="FTEP-V1-002",
        help="Forward-test campaign slug (default: FTEP-V1-002)",
    )
    session_start.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate gates only; no session or lock writes",
    )
    session_start.add_argument("--json", action="store_true", help="Machine-readable JSON")
    session_release = ftep_actions.add_parser(
        "session-release",
        help="governed campaign binding release (--dry-run gates only)",
    )
    session_release.add_argument(
        "campaign_slug",
        nargs="?",
        default="FTEP-V1-002",
        help="Forward-test campaign slug for evidence routing (default: FTEP-V1-002)",
    )
    session_release.add_argument(
        "--account-id",
        required=True,
        help="Paper account id scoped to the active campaign binding",
    )
    session_release.add_argument(
        "--campaign-id",
        help="Optional campaign id; fail closed when active binding differs",
    )
    session_release.add_argument(
        "--session-id",
        help="Optional forward_test_session_id; fail closed when binding differs",
    )
    session_release.add_argument(
        "--expect-manifest-fingerprint",
        help="Fail closed unless the active binding fingerprint matches exactly",
    )
    session_release.add_argument(
        "--expect-manifest-path-substring",
        help="Fail closed unless manifest_path contains this substring",
    )
    session_release.add_argument(
        "--require-frozen-manifest-fingerprint",
        action="store_true",
        help="Fail closed when binding fingerprint differs from frozen manifest",
    )
    session_release.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate release gates without durable writes",
    )
    session_release.add_argument("--json", action="store_true", help="Machine-readable JSON")
    watch_catalysts = ftep_actions.add_parser(
        "watch-catalysts",
        help=(
            "read-only catalyst attention watch (fixture dry-run; no locks). "
            "Does not forward --live-ingress; use tools/ftep_watch_catalysts.py "
            "FTEP-V1-002 --live-ingress for prospective Finviz ingress."
        ),
    )
    watch_catalysts.add_argument(
        "campaign_slug",
        nargs="?",
        default="FTEP-V1-002",
        help="Forward-test campaign slug (default: FTEP-V1-002)",
    )
    watch_catalysts.add_argument("--json", action="store_true")
    watch_catalysts.add_argument(
        "--dry-run",
        action="store_true",
        help="Acknowledge read-only mode (default behavior)",
    )
    watch_catalysts.add_argument(
        "--fixture",
        action="store_true",
        help="Force campaign attention fixture",
    )
    watch_catalysts.add_argument("--input", type=Path, help="Optional attention row JSON file")
    record_prospective_lock = ftep_actions.add_parser(
        "record-prospective-lock",
        help="governed prospective lock gates (--dry-run only; no lock writes)",
    )
    record_prospective_lock.add_argument(
        "campaign_slug",
        nargs="?",
        default="FTEP-V1-002",
        help="Forward-test campaign slug (default: FTEP-V1-002)",
    )
    record_prospective_lock.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate lock invariants without durable writes",
    )
    record_prospective_lock.add_argument("--json", action="store_true")
    record_prospective_lock.add_argument(
        "--fixture",
        action="store_true",
        help="Force campaign attention fixture for catalyst qualification",
    )
    record_prospective_lock.add_argument(
        "--input",
        type=Path,
        help="Optional JSON file with attention-candidate rows",
    )
    finviz_preflight = ftep_actions.add_parser(
        "finviz-prospective-preflight",
        help="software-only Finviz prospective watch preflight (no live fetch)",
    )
    finviz_preflight.add_argument(
        "campaign_slug",
        nargs="?",
        default="FTEP-V1-002",
        help="Forward-test campaign slug (default: FTEP-V1-002)",
    )
    finviz_preflight.add_argument("--json", action="store_true")

    item9 = groups.add_parser("item9", help="Item 9 BAR_OHLCV prospective operator helpers")
    item9_actions = item9.add_subparsers(dest="action", required=True)
    item9_preflight = item9_actions.add_parser(
        "next-rth-preflight",
        help="read-only next-RTH prospective collection preflight (no --poll)",
    )
    item9_preflight.add_argument("--instrument-id", default="AAPL")
    item9_preflight.add_argument("--receipt-dir", type=Path, default=None)
    item9_preflight.add_argument("--json", action="store_true")
    item9_preflight.add_argument("--now-ns", type=int, default=None)
    item9_readiness = item9_actions.add_parser(
        "readiness-snapshot",
        help="read-only validation readiness snapshot (no fitting; no receipt writes)",
    )
    item9_readiness.add_argument("--receipt-dir", type=Path, default=None)
    item9_readiness.add_argument("--repo-root", type=Path, default=None)
    item9_readiness.add_argument("--prefer-local-default", action="store_true")
    item9_readiness.add_argument("--output", type=Path, default=None)
    item9_cal_preflight = item9_actions.add_parser(
        "calibration-preflight",
        help="read-only calibration preflight READY/BLOCKED (never fits; ABSENT auth ok)",
    )
    item9_cal_preflight.add_argument("--receipt-dir", type=Path, default=None)
    item9_cal_preflight.add_argument("--repo-root", type=Path, default=None)
    item9_cal_preflight.add_argument("--prefer-local-default", action="store_true")
    item9_cal_preflight.add_argument("--output", type=Path, default=None)

    historical = groups.add_parser(
        "historical-data",
        help="historical RTH development corpus builder (HISTORICAL_DEVELOPMENT)",
    )
    historical_actions = historical.add_subparsers(dest="action", required=True)
    hist_build = historical_actions.add_parser("build", help="build 1m US equity RTH dataset")
    hist_build.add_argument("--provider", required=True, choices=("moomoo-opend", "fixture"))
    hist_build.add_argument("--instrument", required=True)
    hist_build.add_argument("--start", required=True, dest="start_date")
    hist_build.add_argument("--end", required=True, dest="end_date")
    hist_build.add_argument("--resolution", default="1m")
    hist_build.add_argument("--session", default="RTH")
    hist_build.add_argument("--fixture-path", type=Path)
    hist_build.add_argument("--artifact-root", type=Path)
    hist_build.add_argument("--holidays", default="")
    hist_build.add_argument("--early-closes", default="")
    hist_build.add_argument("--json", action="store_true")

    hist_demo = historical_actions.add_parser(
        "demo",
        help="Lane D e2e: fixture corpus → features → risk simulation (HISTORICAL_DEVELOPMENT)",
    )
    hist_demo.add_argument("--provider", default="fixture", choices=("fixture",))
    hist_demo.add_argument("--instrument", default="AAPL")
    hist_demo.add_argument("--start", required=True, dest="start_date")
    hist_demo.add_argument("--end", required=True, dest="end_date")
    hist_demo.add_argument("--fixture-path", type=Path, required=True)
    hist_demo.add_argument("--corpus-artifact-root", type=Path)
    hist_demo.add_argument("--demo-artifact-root", type=Path)
    hist_demo.add_argument("--json", action="store_true")

    hist_harness = historical_actions.add_parser(
        "harness",
        help="historical research harness v1 (HISTORICAL_DEVELOPMENT)",
    )
    hist_harness.add_argument("--provider", default="fixture", choices=("fixture",))
    hist_harness.add_argument("--instrument", default="AAPL")
    hist_harness.add_argument("--start", required=True, dest="start_date")
    hist_harness.add_argument("--end", required=True, dest="end_date")
    hist_harness.add_argument("--fixture-path", type=Path, required=True)
    hist_harness.add_argument("--corpus-artifact-root", type=Path)
    hist_harness.add_argument("--harness-artifact-root", type=Path)
    hist_harness.add_argument("--experiment-id", default="hist-research-default-experiment")
    hist_harness.add_argument("--hypothesis-id", default="hist-research-default-hypothesis")
    hist_harness.add_argument("--json", action="store_true")

    benchmark = groups.add_parser(
        "benchmark",
        help="intelligence benchmark protocol integration (IBP v1 minimal)",
    )
    benchmark_actions = benchmark.add_subparsers(dest="action", required=True)
    bench_intel = benchmark_actions.add_parser(
        "intelligence",
        help="IBP harness adapter, Smoke10 plan, readiness",
    )
    bench_intel_actions = bench_intel.add_subparsers(dest="bench_action", required=True)
    bench_readiness = bench_intel_actions.add_parser("readiness", help="Smoke10 readiness")
    bench_readiness.add_argument("--json", action="store_true")
    bench_adapt = bench_intel_actions.add_parser(
        "adapt",
        help="adapt historical_research_run_manifest_v1 to IBP record",
    )
    bench_adapt.add_argument("--manifest", type=Path, required=True)
    bench_adapt.add_argument("--json", action="store_true")
    bench_smoke = bench_intel_actions.add_parser(
        "smoke10-plan",
        help="Smoke10 invocation contract (scores NOT executed)",
    )
    bench_smoke.add_argument("--manifest", type=Path)
    bench_smoke.add_argument("--json", action="store_true")
    bench_smoke_run = bench_intel_actions.add_parser(
        "smoke10-run",
        help="execute one bounded Smoke10 baseline (scores executed)",
    )
    bench_smoke_run.add_argument("--manifest", type=Path)
    bench_smoke_run.add_argument("--artifact-root", type=Path)
    bench_smoke_run.add_argument("--json", action="store_true")
    bench_suite = bench_intel_actions.add_parser("suite-info", help="suite catalog metadata")
    bench_suite.add_argument("--json", action="store_true")

    return parser


def _providers_command(root: Path, args: argparse.Namespace) -> int:
    python = _validation_python(root)
    env = _python_environment(root)
    if args.action == "capability-matrix":
        command = [python, str(root / "tools" / "providers" / "capability_matrix.py")]
        if args.output:
            command.extend(["--output", str(args.output)])
        if args.skip_readiness:
            command.append("--skip-readiness")
        command.extend(["--repository-root", str(root)])
    else:
        command = [python, str(root / "tools" / "provider_readiness.py"), args.action]
        if args.action == "gaps":
            command.extend(["--profile", args.profile])
        elif args.action == "campaign-readiness":
            command.append(args.campaign_slug)
        if getattr(args, "json", False):
            command.append("--json")
        if getattr(args, "probe_local", False):
            command.append("--probe-local")
    result = _run(
        root,
        label=f"providers {args.action}",
        command=command,
        env=env,
        stream_output=True,
    )
    return int(result["exit_code"])


def _item9_command(root: Path, args: argparse.Namespace) -> int:
    python = _validation_python(root)
    env = _python_environment(root)
    if args.action == "next-rth-preflight":
        command = [python, str(root / "tools" / "item9_next_rth_preflight.py")]
        if args.instrument_id:
            command.extend(["--instrument-id", str(args.instrument_id)])
        if args.receipt_dir is not None:
            command.extend(["--receipt-dir", str(args.receipt_dir)])
        if args.json:
            command.append("--json")
        if args.now_ns is not None:
            command.extend(["--now-ns", str(args.now_ns)])
        label = "item9 next-rth-preflight"
    elif args.action == "readiness-snapshot":
        command = [python, str(root / "tools" / "item9_readiness_snapshot.py")]
        if args.receipt_dir is not None:
            command.extend(["--receipt-dir", str(args.receipt_dir)])
        if getattr(args, "repo_root", None) is not None:
            command.extend(["--repo-root", str(args.repo_root)])
        if getattr(args, "prefer_local_default", False):
            command.append("--prefer-local-default")
        if getattr(args, "output", None) is not None:
            command.extend(["--output", str(args.output)])
        label = "item9 readiness-snapshot"
    elif args.action == "calibration-preflight":
        command = [python, str(root / "tools" / "item9_calibration_preflight.py")]
        if args.receipt_dir is not None:
            command.extend(["--receipt-dir", str(args.receipt_dir)])
        if getattr(args, "repo_root", None) is not None:
            command.extend(["--repo-root", str(args.repo_root)])
        if getattr(args, "prefer_local_default", False):
            command.append("--prefer-local-default")
        if getattr(args, "output", None) is not None:
            command.extend(["--output", str(args.output)])
        label = "item9 calibration-preflight"
    else:
        print(f"unknown item9 action: {args.action}", file=sys.stderr)
        return 2
    result = _run(
        root,
        label=label,
        command=command,
        env=env,
        stream_output=True,
    )
    return int(result["exit_code"])


def _benchmark_command(root: Path, args: argparse.Namespace) -> int:
    if args.action != "intelligence":
        print(f"unknown benchmark action: {args.action}", file=sys.stderr)
        return 2
    python = _validation_python(root)
    env = _python_environment(root)
    command = [python, str(root / "tools" / "benchmarks" / "intelligence_cli.py"), args.bench_action]
    if args.bench_action in {"adapt", "smoke10-plan", "smoke10-run"} and getattr(
        args, "manifest", None
    ) is not None:
        command.extend(["--manifest", str(args.manifest)])
    if args.bench_action == "smoke10-run" and getattr(args, "artifact_root", None) is not None:
        command.extend(["--artifact-root", str(args.artifact_root)])
    if getattr(args, "json", False):
        command.append("--json")
    result = _run(
        root,
        label=f"benchmark intelligence {args.bench_action}",
        command=command,
        env=env,
        stream_output=True,
    )
    return int(result["exit_code"])


def _historical_data_command(root: Path, args: argparse.Namespace) -> int:
    if args.action not in {"build", "demo", "harness"}:
        print(f"unknown historical-data action: {args.action}", file=sys.stderr)
        return 2
    python = _validation_python(root)
    env = _python_environment(root)
    if args.action == "build":
        script = "build_cli.py"
    elif args.action == "harness":
        script = "harness_cli.py"
    else:
        script = "demo_cli.py"
    command = [python, str(root / "tools" / "historical_data" / script)]
    if args.action == "build":
        command.extend(
            [
                "--provider",
                args.provider,
                "--instrument",
                args.instrument,
                "--start",
                args.start_date,
                "--end",
                args.end_date,
                "--resolution",
                args.resolution,
                "--session",
                args.session,
            ]
        )
        if args.fixture_path:
            command.extend(["--fixture-path", str(args.fixture_path)])
        if args.artifact_root:
            command.extend(["--artifact-root", str(args.artifact_root)])
        if args.holidays:
            command.extend(["--holidays", args.holidays])
        if args.early_closes:
            command.extend(["--early-closes", args.early_closes])
    elif args.action == "demo":
        command.extend(
            [
                "--provider",
                args.provider,
                "--instrument",
                args.instrument,
                "--start",
                args.start_date,
                "--end",
                args.end_date,
                "--fixture-path",
                str(args.fixture_path),
            ]
        )
        if args.corpus_artifact_root:
            command.extend(["--corpus-artifact-root", str(args.corpus_artifact_root)])
        if args.demo_artifact_root:
            command.extend(["--demo-artifact-root", str(args.demo_artifact_root)])
    else:
        command.extend(
            [
                "--provider",
                args.provider,
                "--instrument",
                args.instrument,
                "--start",
                args.start_date,
                "--end",
                args.end_date,
                "--fixture-path",
                str(args.fixture_path),
            ]
        )
        if args.corpus_artifact_root:
            command.extend(["--corpus-artifact-root", str(args.corpus_artifact_root)])
        if args.harness_artifact_root:
            command.extend(["--harness-artifact-root", str(args.harness_artifact_root)])
        if args.experiment_id:
            command.extend(["--experiment-id", str(args.experiment_id)])
        if args.hypothesis_id:
            command.extend(["--hypothesis-id", str(args.hypothesis_id)])
    if args.json:
        command.append("--json")
    result = _run(
        root,
        label=f"historical-data {args.action}",
        command=command,
        env=env,
        stream_output=True,
    )
    return int(result["exit_code"])


def _ftep_command(root: Path, args: argparse.Namespace) -> int:
    python = _validation_python(root)
    env = _python_environment(root)
    if args.action == "campaign-status":
        command = [python, str(root / "tools" / "ftep_campaign_status.py"), args.campaign_slug]
        if getattr(args, "json", False):
            command.append("--json")
    elif args.action == "opportunity-summaries":
        command = [python, str(root / "tools" / "opportunity_summaries.py")]
        if args.campaign_slug:
            command.extend(["--campaign-slug", args.campaign_slug])
        if getattr(args, "sample", False):
            command.append("--sample")
        if getattr(args, "input", None):
            command.extend(["--input", str(args.input)])
        if getattr(args, "json", False):
            command.append("--json")
    elif args.action == "integrity-check":
        command = [python, str(root / "tools" / "ftep_integrity_check.py"), args.campaign_slug]
        if getattr(args, "json", False):
            command.append("--json")
    elif args.action == "session-start":
        command = [python, str(root / "tools" / "ftep_session_start.py"), args.campaign_slug]
        if getattr(args, "dry_run", False):
            command.append("--dry-run")
        if getattr(args, "json", False):
            command.append("--json")
    elif args.action == "session-release":
        command = [python, str(root / "tools" / "ftep_session_release.py"), args.campaign_slug]
        command.extend(["--account-id", args.account_id])
        if getattr(args, "campaign_id", None):
            command.extend(["--campaign-id", args.campaign_id])
        if getattr(args, "session_id", None):
            command.extend(["--session-id", args.session_id])
        if getattr(args, "expect_manifest_fingerprint", None):
            command.extend(
                ["--expect-manifest-fingerprint", args.expect_manifest_fingerprint]
            )
        if getattr(args, "expect_manifest_path_substring", None):
            command.extend(
                [
                    "--expect-manifest-path-substring",
                    args.expect_manifest_path_substring,
                ]
            )
        if getattr(args, "require_frozen_manifest_fingerprint", False):
            command.append("--require-frozen-manifest-fingerprint")
        if getattr(args, "dry_run", False):
            command.append("--dry-run")
        if getattr(args, "json", False):
            command.append("--json")
    elif args.action == "watch-catalysts":
        command = [python, str(root / "tools" / "ftep_watch_catalysts.py"), args.campaign_slug]
        if getattr(args, "fixture", False):
            command.append("--fixture")
        if getattr(args, "input", None):
            command.extend(["--input", str(args.input)])
        if getattr(args, "dry_run", False):
            command.append("--dry-run")
        if getattr(args, "json", False):
            command.append("--json")
    elif args.action == "record-prospective-lock":
        command = [
            python,
            str(root / "tools" / "ftep_record_prospective_lock.py"),
            args.campaign_slug,
            "--dry-run",
        ]
        if getattr(args, "fixture", False):
            command.append("--fixture")
        if getattr(args, "input", None):
            command.extend(["--input", str(args.input)])
        if getattr(args, "json", False):
            command.append("--json")
    elif args.action == "finviz-prospective-preflight":
        command = [
            python,
            str(root / "tools" / "ftep_finviz_prospective_preflight.py"),
            args.campaign_slug,
        ]
        if getattr(args, "json", False):
            command.append("--json")
    else:
        print(f"unknown ftep action: {args.action}", file=sys.stderr)
        return 2
    result = _run(
        root,
        label=f"ftep {args.action}",
        command=command,
        env=env,
        stream_output=True,
    )
    return int(result["exit_code"])


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = REPOSITORY_ROOT
    if args.group == "env":
        if getattr(args, "env_action", None) == "bootstrap":
            if not args.link_venv:
                print("bootstrap requires --link-venv", file=sys.stderr)
                return 2
            environment_module = _load_environment_module()
            try:
                payload = environment_module.link_local_venv(root, force=args.force)
            except RuntimeError as exc:
                print(f"bootstrap failed: {exc}", file=sys.stderr)
                return 1
            if args.json_path:
                _write_json(args.json_path, payload)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0
        if getattr(args, "env_action", None) == "install-opend":
            environment_module = _load_environment_module()
            hop_module = _load_opend_hop_interpreter()
            try:
                python = environment_module.effective_python_executable(root)
            except RuntimeError:
                python = Path(sys.executable)
            payload = hop_module.install_opend_extra(python=Path(python))
            if args.json_path:
                _write_json(args.json_path, payload)
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0 if payload.get("status") == "READY" else 1
        report = _diagnostics(root)
        status, hard_failures = _environment_status(report)
        report["status"] = status
        report["hard_failures"] = hard_failures
        if args.json_path:
            _write_json(args.json_path, report)
        print(json.dumps(report, indent=2, sort_keys=True))
        if hard_failures:
            print(
                "hard prerequisite failures: " + ", ".join(hard_failures),
                file=sys.stderr,
            )
            return 1
        return 0

    if args.group == "state-path":
        command = [sys.executable, str(root / "tools" / "state_path_diagnostic.py")]
        if args.json_path:
            command.extend(["--json", str(args.json_path)])
        result = _run(root, label="state-path", command=command, env=_python_environment(root))
        return int(result["exit_code"])

    if args.group == "storage":
        return _storage_command(root, args)

    if args.group == "ci":
        return _ci_jobs_command(root, args)

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
            _validation_python(root),
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

    if args.group == "providers":
        return _providers_command(root, args)

    if args.group == "ftep":
        return _ftep_command(root, args)

    if args.group == "item9":
        return _item9_command(root, args)

    if args.group == "historical-data":
        return _historical_data_command(root, args)

    if args.group == "benchmark":
        return _benchmark_command(root, args)

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

"""Stable performance telemetry for validation receipts and developer diagnostics."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from tools.performance_budget import (
        PerformanceBudget,
        classify_performance,
        load_performance_budget,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution.
    from performance_budget import (  # type: ignore[no-redef]
        PerformanceBudget,
        classify_performance,
        load_performance_budget,
    )


TELEMETRY_SCHEMA_VERSION = "1.0"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_repository_state(repository_root: Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    sha = ""
    dirty = False
    branch = "unknown"
    try:
        sha = (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=str(root),
                text=True,
                stderr=subprocess.DEVNULL,
            )
            .strip()
        )
        status = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=str(root),
            text=True,
            stderr=subprocess.DEVNULL,
        )
        dirty = bool(status.strip())
        branch = (
            subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(root),
                text=True,
                stderr=subprocess.DEVNULL,
            )
            .strip()
        )
    except (OSError, subprocess.CalledProcessError):
        pass
    return {
        "repository_sha": sha,
        "repository_dirty": dirty,
        "repository_branch": branch,
    }


def environment_fingerprint(repository_root: Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    os_family = "windows" if os.name == "nt" else platform.system().lower()
    ci = os.environ.get("CI", "").lower() == "true"
    environment_class = (
        "ci_linux" if ci and os_family != "windows" else f"local_{os_family}_warm_venv"
    )
    fingerprint = {
        "telemetry_schema_version": TELEMETRY_SCHEMA_VERSION,
        "recorded_at": utc_now(),
        "os_family": os_family,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "logical_cpu_count": os.cpu_count() or 0,
        "ci": ci,
        "environment_class": environment_class,
        "baseline_logical_cpu_count": 8,
    }
    fingerprint.update(git_repository_state(root))
    return fingerprint


def suite_timing_summary(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Aggregate suite-level timing from worker results."""

    suite_rows: list[dict[str, Any]] = []
    for worker in receipt.get("worker_results", []):
        suite_id = str(worker.get("suite_id", ""))
        wall_seconds = float(worker.get("wall_seconds", 0.0))
        process_wall = float(worker.get("process_wall_seconds", wall_seconds))
        suite_rows.append(
            {
                "suite_id": suite_id,
                "wall_seconds": round(wall_seconds, 6),
                "process_wall_seconds": round(process_wall, 6),
                "discovery_seconds": round(float(worker.get("discovery_seconds", 0.0)), 6),
                "tests_run": int(worker.get("tests_run", 0)),
                "status": str(worker.get("status", "")),
            }
        )
    suite_rows.sort(key=lambda row: row["wall_seconds"], reverse=True)
    schedule = receipt.get("execution_schedule", {})
    wave_summary = []
    for wave in schedule.get("waves", []):
        wave_summary.append(
            {
                "wave_id": wave.get("wave_id"),
                "policy": wave.get("policy"),
                "concurrency": wave.get("concurrency"),
                "suite_count": len(wave.get("suite_ids", [])),
            }
        )
    return {
        "suite_timings": suite_rows,
        "slowest_suites": suite_rows[:5],
        "wave_summary": wave_summary,
    }


def enrich_validation_receipt(
    receipt: dict[str, Any],
    *,
    repository_root: Path,
    budget: PerformanceBudget | None = None,
) -> dict[str, Any]:
    """Attach stable performance telemetry and budget classification to a receipt."""

    root = Path(repository_root).resolve()
    budget_obj = budget or load_performance_budget(root / "manifests" / "performance_budget.json")
    environment = environment_fingerprint(root)
    timing = suite_timing_summary(receipt)
    classification = classify_performance(
        receipt,
        budget=budget_obj,
        environment=environment,
    )
    ended_at = utc_now()
    performance = {
        "telemetry_schema_version": TELEMETRY_SCHEMA_VERSION,
        "started_at": receipt.get("started_at"),
        "ended_at": ended_at,
        "wall_seconds": round(float(receipt.get("wall_seconds", 0.0)), 6),
        "validation_mode": receipt.get("mode"),
        "selected_suite_count": len(receipt.get("selected_suites", [])),
        "tests_run": receipt.get("tests_run"),
        "skips": receipt.get("skips"),
        "failures": receipt.get("failures"),
        "errors": receipt.get("errors"),
        "requested_workers": receipt.get("workers"),
        "effective_workers": receipt.get("effective_workers", receipt.get("workers")),
        "scheduler_version": receipt.get("scheduler_version"),
        "selector_version": receipt.get("selector_version"),
        "manifest_hash": receipt.get("manifest_hash"),
        "environment": environment,
        "suite_timing": timing,
        "budget": classification,
    }
    if classification.get("classification") in {"REGRESSION", "SEVERE_REGRESSION", "WARNING"}:
        performance["regression_explain"] = format_regression_explanation(
            receipt, classification, timing
        )
    receipt["performance_telemetry"] = performance
    return receipt


def format_regression_explanation(
    receipt: Mapping[str, Any],
    classification: Mapping[str, Any],
    timing: Mapping[str, Any],
) -> str:
    lines = [
        f"classification={classification.get('classification')}",
        f"wall_seconds={classification.get('observed_wall_seconds')}",
        f"baseline_median_seconds={classification.get('baseline_median_seconds')}",
        f"absolute_delta_seconds={classification.get('absolute_delta_seconds')}",
        f"percentage_delta={classification.get('percentage_delta')}%",
    ]
    if classification.get("threshold_crossed"):
        lines.append(f"threshold_crossed={classification['threshold_crossed']}")
    slowest = timing.get("slowest_suites", [])
    if slowest:
        top = ", ".join(
            f"{row['suite_id']}:{row['wall_seconds']}s" for row in slowest[:3]
        )
        lines.append(f"slowest_suites={top}")
    lines.append(f"tests_run={receipt.get('tests_run')} failures={receipt.get('failures')}")
    return "; ".join(lines)


def performance_status_for_env(repository_root: Path) -> dict[str, Any]:
    """Lightweight performance-budget summary for imp env (no validation execution)."""

    root = Path(repository_root).resolve()
    budget_path = root / "manifests" / "performance_budget.json"
    if not budget_path.is_file():
        return {
            "available": False,
            "reason": "missing performance budget manifest",
        }
    budget = load_performance_budget(budget_path)
    return {
        "available": True,
        "budget_version": budget.budget_version,
        "telemetry_schema_version": budget.telemetry_schema_version,
        "gating_policy": budget.gating_policy,
        "maturity_status": budget.maturity_status,
        "default_workers": 2,
        "scheduler_version": budget.parent_scheduler_version,
        "selector_version": budget.parent_selector_version,
        "canonical_workloads": sorted(budget.workloads.keys()),
        "remote_status": budget.raw.get("remote_status", {}),
        "budget_path": str(budget_path.relative_to(root)).replace("\\", "/"),
    }


def append_ephemeral_telemetry(
    receipt: dict[str, Any],
    *,
    repository_root: Path,
) -> Path | None:
    """Optionally append receipt summary to local telemetry store (bounded, gitignored)."""

    if os.environ.get("IMP_PERF_TELEMETRY", "1") == "0":
        return None
    root = Path(repository_root).resolve()
    target = root / ".local" / "developer-workflow" / "performance-telemetry.jsonl"
    performance = receipt.get("performance_telemetry", {})
    if not performance:
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "recorded_at": performance.get("ended_at"),
        "mode": receipt.get("mode"),
        "status": receipt.get("status"),
        "wall_seconds": performance.get("wall_seconds"),
        "classification": performance.get("budget", {}).get("classification"),
        "workload_id": performance.get("budget", {}).get("workload_id"),
        "repository_sha": performance.get("environment", {}).get("repository_sha"),
        "ci": performance.get("environment", {}).get("ci", False),
    }
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        import json

        handle.write(json.dumps(summary, sort_keys=True, separators=(",", ":")) + "\n")
    return target

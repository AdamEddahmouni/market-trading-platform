"""Collect repeated validation timing samples for P7 baseline evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from tools.performance_budget import load_performance_budget, summarize_variance
except ModuleNotFoundError:
    from performance_budget import load_performance_budget, summarize_variance  # type: ignore[no-redef]


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolved_python(root: Path) -> str:
    try:
        from tools.environment import effective_python_executable

        return str(effective_python_executable(root))
    except Exception:
        return sys.executable


def _run_validation(
    root: Path,
    mode: str,
    *,
    workers: int,
    domain: str | None = None,
) -> dict[str, Any]:
    json_path = root / ".local" / "developer-workflow" / f"p7-bench-{mode}-{domain or 'all'}.json"
    command = [
        _resolved_python(root),
        str(root / "tools" / "imp.py"),
        "validate",
        mode,
        "--workers",
        str(workers),
        "--json",
        str(json_path),
    ]
    if mode == "domain" and domain:
        command.append(domain)
    started = time.perf_counter()
    completed = subprocess.run(command, cwd=str(root), check=False, capture_output=True, text=True)
    wall_seconds = time.perf_counter() - started
    receipt: dict[str, Any] = {}
    json_path = root / ".local" / "developer-workflow" / f"p7-bench-{mode}-{domain or 'all'}.json"
    if json_path.is_file():
        receipt = json.loads(json_path.read_text(encoding="utf-8"))
    return {
        "exit_code": completed.returncode,
        "orchestrator_wall_seconds": wall_seconds,
        "receipt_wall_seconds": float(receipt.get("wall_seconds", 0.0)),
        "tests_run": int(receipt.get("tests_run", 0)),
        "skips": int(receipt.get("skips", 0)),
        "failures": int(receipt.get("failures", 0)),
        "errors": int(receipt.get("errors", 0)),
        "classification": receipt.get("performance_telemetry", {})
        .get("budget", {})
        .get("classification"),
    }


def measure_series(
    root: Path,
    *,
    mode: str,
    workers: int,
    repeats: int,
    domain: str | None = None,
) -> dict[str, Any]:
    samples: list[float] = []
    runs: list[dict[str, Any]] = []
    for index in range(repeats):
        row = _run_validation(root, mode, workers=workers, domain=domain)
        runs.append(row)
        if row["exit_code"] == 0 and row["receipt_wall_seconds"] > 0:
            samples.append(row["receipt_wall_seconds"])
    return {
        "mode": mode,
        "workers": workers,
        "domain": domain,
        "repeats": repeats,
        "runs": runs,
        "variance": summarize_variance(samples),
        "all_green": all(run["exit_code"] == 0 for run in runs),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--targets",
        nargs="+",
        default=["fast", "domain:macro"],
        help="fast, full, domain:macro, etc.",
    )
    arguments = parser.parse_args(argv)
    root = REPOSITORY_ROOT
    budget = load_performance_budget(root / "manifests" / "performance_budget.json")
    series: list[dict[str, Any]] = []
    for target in arguments.targets:
        if target.startswith("domain:"):
            mode = "domain"
            domain = target.split(":", 1)[1]
            workers = 2
        elif target == "fast":
            mode = "fast"
            domain = None
            workers = 1
        else:
            mode = target
            domain = None
            workers = 2
        series.append(
            measure_series(
                root,
                mode=mode,
                workers=workers,
                repeats=arguments.repeats,
                domain=domain,
            )
        )
    payload = {
        "schema_version": "1.0",
        "report_type": "p7_baseline_measurement",
        "generated_at": _utc_now(),
        "budget_version": budget.budget_version,
        "measurement_claim": "MEASURED",
        "series": series,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {arguments.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

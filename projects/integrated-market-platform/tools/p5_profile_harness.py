"""Opt-in P5 profiling harness — not part of validation inventory."""

from __future__ import annotations

import argparse
import cProfile
import json
import pstats
import subprocess
import sys
import time
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def _import_decomposition() -> dict[str, float]:
    py = sys.executable
    root = str(ROOT)
    results: dict[str, float] = {}

    started = time.perf_counter()
    subprocess.run([py, "-c", "pass"], cwd=root, capture_output=True, check=False)
    results["python_startup"] = time.perf_counter() - started

    started = time.perf_counter()
    subprocess.run(
        [
            py,
            "-c",
            "import importlib.util; "
            f"spec=importlib.util.spec_from_file_location('vw', r'{ROOT / 'tools' / 'validation_worker.py'}'); "
            "m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)",
        ],
        cwd=root,
        capture_output=True,
        check=False,
    )
    results["validation_worker_import"] = time.perf_counter() - started

    started = time.perf_counter()
    subprocess.run(
        [
            py,
            "-c",
            f"import sys; sys.path[:0]=[r'{root}/src', r'{root}']; import tests.platform",
        ],
        cwd=root,
        capture_output=True,
        check=False,
    )
    results["tests_platform_package"] = time.perf_counter() - started

    started = time.perf_counter()
    subprocess.run(
        [
            py,
            "-c",
            f"import sys; sys.path[:0]=[r'{root}/src', r'{root}']; "
            "from market_platform_foundation.ui_api.workspace_evidence import build_workspace_evidence_payload",
        ],
        cwd=root,
        capture_output=True,
        check=False,
    )
    results["workspace_evidence_import"] = time.perf_counter() - started

    started = time.perf_counter()
    proc = subprocess.run(
        [py, "-m", "unittest", "discover", "-s", "tests/platform", "-q"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    results["unittest_discovery_platform"] = time.perf_counter() - started
    results["unittest_discovery_platform_exit"] = float(proc.returncode)
    return results


def _profile_workspace_evidence(symbol: str = "BOXL", runs: int = 1) -> dict[str, object]:
    from market_platform_foundation.ui_api.store import ReplayStore, TRACKED_ASSISTANT_AUDIT_ROOT
    from market_platform_foundation.ui_api.workspace_evidence import build_workspace_evidence_payload

    collection_root = ROOT.parent
    store = ReplayStore(collection_root=collection_root, assistant_audit_root=TRACKED_ASSISTANT_AUDIT_ROOT)
    store.load()

    samples: list[float] = []
    profiler = cProfile.Profile()
    for _ in range(runs):
        started = time.perf_counter()
        profiler.enable()
        build_workspace_evidence_payload(store, symbol)
        profiler.disable()
        samples.append(time.perf_counter() - started)
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(25)
    return {
        "symbol": symbol,
        "runs": runs,
        "samples_seconds": samples,
        "median_seconds": sorted(samples)[len(samples) // 2],
        "top_cumulative": stream.getvalue(),
    }


def _profile_short_intelligence_load(runs: int = 5) -> dict[str, object]:
    from market_platform_foundation.ui_api.workspace_evidence import _load_short_intelligence_store

    samples: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        _load_short_intelligence_store("BOXL")
        samples.append(time.perf_counter() - started)
    return {
        "runs": runs,
        "samples_seconds": samples,
        "median_seconds": sorted(samples)[len(samples) // 2],
    }


def _profile_build_evidence() -> dict[str, object]:
    from tools.ui1.run_ui_api import build_evidence

    output_dir = ROOT / ".local" / "p5-profile-evidence"
    started = time.perf_counter()
    profiler = cProfile.Profile()
    profiler.enable()
    bundle = build_evidence(output_dir)
    profiler.disable()
    wall = time.perf_counter() - started
    stream = StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")
    stats.print_stats(30)
    return {
        "wall_seconds": wall,
        "aggregate_status": bundle.get("aggregate_status"),
        "top_cumulative": stream.getvalue(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode",
        choices=("import-decomposition", "workspace-evidence", "short-intelligence", "build-evidence"),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    if args.mode == "import-decomposition":
        payload: dict[str, object] = _import_decomposition()
    elif args.mode == "workspace-evidence":
        payload = _profile_workspace_evidence(runs=args.runs)
    elif args.mode == "short-intelligence":
        payload = _profile_short_intelligence_load(runs=args.runs)
    else:
        payload = _profile_build_evidence()
    text = json.dumps(payload, indent=2, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

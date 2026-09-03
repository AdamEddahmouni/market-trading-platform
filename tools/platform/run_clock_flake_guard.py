"""CI-oriented flake guard: platform persistence tests under adversarial clock conditions.

The frozen-wall-clock defect (duplicate session ids, tied event timestamps,
colliding audit-store hashes) is covered by targeted regression tests; this
guard makes that coverage explicit and broad: it replays the platform
persistence test module(s) for N iterations under two patched clock scenarios —
a fully frozen wall clock and a clock that jumps backward and forward — and
asserts ``monotonic_wall_ns`` stays strictly increasing under the same patches,
so any incidental time dependence in those suites surfaces deterministically.

Strictly offline (no network, no subprocesses). Writes
``evidence/platform/clock-flake-guard-report.json`` and exits non-zero on any
failure, so CI can gate on it.

Usage:
    python tools/platform/run_clock_flake_guard.py [--iterations N]
        [--scenarios frozen,jump] [--module tests/platform/test_paper_p3.py] ...
"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.clock import monotonic_wall_ns, reset_clock_for_tests  # noqa: E402
from market_platform_foundation.offline_guard import install_guard  # noqa: E402

CLOCK_PATCH_TARGET = "market_platform_foundation.clock.time.time_ns"
FROZEN_NS = 1787000000000000000
INVARIANT_SAMPLES = 64
REPORT_PATH = ROOT / "evidence/platform/clock-flake-guard-report.json"
DEFAULT_MODULES = ["tests/platform/test_paper_p3.py"]


def _jump_script(base: int) -> list[int]:
    """Raw wall-clock values that freeze, jump backward, jump forward, and freeze again."""
    return [
        base,
        base,
        base - 5_000_000_000,
        base + 1_000_000_000,
        base - 100_000_000_000,
        base,
        base,
        base + 60_000_000_000,
    ]


def _frozen_patch() -> mock._patch:
    return mock.patch(CLOCK_PATCH_TARGET, return_value=FROZEN_NS)


def _jump_patch() -> mock._patch:
    return mock.patch(CLOCK_PATCH_TARGET, side_effect=itertools.cycle(_jump_script(FROZEN_NS)))


SCENARIOS: dict[str, Callable[[], mock._patch]] = {
    "frozen": _frozen_patch,
    "jump": _jump_patch,
}


def _test_id(test: unittest.TestCase) -> str:
    return f"{test.__class__.__module__}.{test.__class__.__name__}.{test._testMethodName}"


def _detail(err: tuple[type[BaseException], BaseException, Any]) -> str:
    exc_type, exc, _traceback = err
    return f"{exc_type.__name__}: {exc}"


class _CollectingResult(unittest.TestResult):
    """Collect failures/errors with test ids instead of printing them."""

    def __init__(self) -> None:
        super().__init__()
        self.problems: list[dict[str, str]] = []

    def addError(self, test: unittest.TestCase, err: Any) -> None:  # noqa: N802 - unittest API
        super().addError(test, err)
        self.problems.append({"kind": "ERROR", "test": _test_id(test), "detail": _detail(err)})

    def addFailure(self, test: unittest.TestCase, err: Any) -> None:  # noqa: N802 - unittest API
        super().addFailure(test, err)
        self.problems.append({"kind": "FAIL", "test": _test_id(test), "detail": _detail(err)})


def _assert_clock_invariant() -> tuple[bool, str]:
    """Sample the clock under the active patch; it must be strictly increasing."""
    samples = [monotonic_wall_ns() for _ in range(INVARIANT_SAMPLES)]
    increasing = all(b > a for a, b in zip(samples, samples[1:]))
    detail = (
        f"{len(samples)} samples, strictly_increasing={increasing}, "
        f"first={samples[0]}, last={samples[-1]}"
    )
    return increasing, detail


def _load_module(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(f"clock_guard_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load test module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module.__name__] = module
    spec.loader.exec_module(module)
    return module


def _run_scenario(
    name: str,
    patch_factory: Callable[[], mock._patch],
    modules: list[Any],
    iterations: int,
) -> dict[str, Any]:
    problems: list[dict[str, str]] = []
    tests_run = 0
    invariant_ok = True
    invariant_detail = ""
    loader = unittest.TestLoader()
    for _index in range(iterations):
        reset_clock_for_tests()
        # Fresh suites per iteration: in this interpreter
        # ``TestSuite._cleanup`` is a class attribute, so ``_removeTestAtIndex``
        # nulls every test slot after a single ``run`` — a suite object can
        # only be executed once.
        suites = [loader.loadTestsFromModule(module) for module in modules]
        with patch_factory():
            result = _CollectingResult()
            for suite in suites:
                suite.run(result)
            ok, detail = _assert_clock_invariant()
            invariant_ok = invariant_ok and ok
            invariant_detail = detail
        tests_run += result.testsRun
        problems.extend(result.problems)
    return {
        "clock_invariant": invariant_ok,
        "clock_invariant_detail": invariant_detail,
        "failures": problems,
        "iterations": iterations,
        "tests_run": tests_run,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--iterations", type=int, default=3, help="iterations per scenario (default 3)")
    parser.add_argument("--scenarios", default="frozen,jump", help="comma-separated scenarios (default frozen,jump)")
    parser.add_argument("--module", action="append", dest="modules", help="test module path (repeatable)")
    parser.add_argument("--report", default=str(REPORT_PATH), help="evidence report output path")
    args = parser.parse_args(argv)

    install_guard([])

    module_paths = [Path(value) for value in (args.modules or DEFAULT_MODULES)]
    try:
        modules = [_load_module(path) for path in module_paths]
    except Exception as exc:  # pragma: no cover - import failure path
        print(f"clock-flake-guard: module load failed: {exc}")
        return 1

    selected = [name for name in args.scenarios.split(",") if name]
    unknown = [name for name in selected if name not in SCENARIOS]
    if unknown:
        print(f"clock-flake-guard: unknown scenarios: {', '.join(unknown)}")
        return 1

    scenario_results: dict[str, dict[str, Any]] = {}
    for name in selected:
        scenario_results[name] = _run_scenario(name, SCENARIOS[name], modules, args.iterations)
        row = scenario_results[name]
        print(
            f"clock-flake-guard: scenario={name} iterations={row['iterations']} "
            f"tests={row['tests_run']} failures={len(row['failures'])} "
            f"clock_invariant={row['clock_invariant']}"
        )

    failures = [
        row
        for result in scenario_results.values()
        for row in result["failures"]
    ]
    invariant_failed = [name for name, row in scenario_results.items() if not row["clock_invariant"]]
    status = "passed" if not failures and not invariant_failed else "failed"

    report = {
        "aggregate_status": status,
        "clock_patch_target": CLOCK_PATCH_TARGET,
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f0Z"),
        "failures": failures,
        "invariant_failed_scenarios": invariant_failed,
        "iterations": args.iterations,
        "logical_id": "platform.clock_flake_guard_report",
        "mode": "TEST_REPLAY",
        "modules": [str(path) for path in module_paths],
        "offline": True,
        "scenarios": scenario_results,
        "schema_version": "1.0.0",
        "summary": (
            f"Clock flake guard: {status} — {len(selected)} scenario(s), "
            f"{len(failures)} test failure(s), {len(invariant_failed)} invariant failure(s)."
        ),
    }
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

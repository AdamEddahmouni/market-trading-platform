"""Run controlled validation mutations in a disposable repository shadow.

The canonical checkout is read-only to this tool. Each mutation is applied to a
temporary copy, its expected detector must fail, and the original shadow file is
restored before the next check.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.validate import create_baseline_snapshot, write_json_atomic


@dataclass(frozen=True, slots=True)
class Mutation:
    id: str
    path: str
    mode: str
    before: str
    after: str
    expected_detector: str


MUTATIONS: tuple[Mutation, ...] = (
    Mutation(
        id="bitemporal-knowledge-time-removed",
        path="src/market_platform_foundation/runtime/bitemporal_store.py",
        mode="fast",
        before="""    return _interval_contains(record.valid_from, record.valid_to, market_time) and _interval_contains(
        record.known_from,
        record.known_to,
        knowledge_time,
    )""",
        after="""    return _interval_contains(record.valid_from, record.valid_to, market_time)""",
        expected_detector="tests/runtime/test_bitemporal_store.py::BitemporalStoreTests::test_correction_invisible_before_known_from",
    ),
    Mutation(
        id="fred-missing-dot-becomes-zero",
        path="src/market_platform_foundation/fred/normalize.py",
        mode="fast",
        before='''    if raw is None or raw == "" or raw == ".":
        return None, None, (FredQualityFlag.MISSING_VALUE.value,)''',
        after='''    if raw == ".":
        return ".", 0.0, ()
    if raw is None or raw == "":
        return None, None, (FredQualityFlag.MISSING_VALUE.value,)''',
        expected_detector="tests/fred/test_fred.py::FredNormalizeTests::test_missing_dot_is_unknown_not_zero",
    ),
    Mutation(
        id="credential-redaction-removed",
        path="src/market_platform_foundation/credential_audit.py",
        mode="fast",
        before='''        "sanitized_location": location,
    }''',
        after='''        "sanitized_location": location,
        "matched_value": _matched_value,
    }''',
        expected_detector="tests/phase0/test_credential_audit.py::CredentialAuditTests::test_match_output_contains_no_value_or_context",
    ),
    Mutation(
        id="wrong-listing-authority-routing",
        path="src/market_platform_foundation/short_intelligence/threshold_coverage.py",
        mode="changed",
        before="""    return ThresholdCoverageState(
        authority=authority,
        status=ThresholdCoverageStatus.NOT_APPLICABLE,""",
        after="""    return ThresholdCoverageState(
        authority=ThresholdAuthority.NASDAQ,
        status=ThresholdCoverageStatus.NOT_APPLICABLE,""",
        expected_detector="tests/short_intelligence/test_threshold_coverage.py::CoverageRoutingTests::test_nasdaq_absence_is_not_global_negative_for_nyse_listed",
    ),
    Mutation(
        id="fred-realtime-end-as-availability",
        path="src/market_platform_foundation/fred/availability.py",
        mode="changed",
        before="""        if is_date_only(knowledge_start_date):
            available_time = knowledge_start_date
            precision = AvailabilityPrecision.DATE_ONLY.value""",
        after="""        if is_date_only(knowledge_start_date):
            available_time = realtime_end
            precision = AvailabilityPrecision.DATE_ONLY.value""",
        expected_detector="tests/fred/test_fred.py::FredRevisionTests::test_realtime_end_not_used_as_available_time_regression",
    ),
    Mutation(
        id="eia-period-end-as-availability",
        path="src/market_platform_foundation/eia/normalize.py",
        mode="changed",
        before="    available_time = api_first_observed_time or scheduled_release_time or observed_time",
        after="    available_time = period_end",
        expected_detector="tests/eia/test_eia.py::EiaPitTests::test_wpsr_pre_release_not_visible",
    ),
)


def apply_mutation(path: Path, before: str, after: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(before) != 1:
        raise ValueError(f"mutation target must occur exactly once in {path}")
    path.write_text(text.replace(before, after, 1), encoding="utf-8")


def _copy_shadow(repository_root: Path, destination: Path) -> None:
    ignored_names = {".venv", "node_modules", "__pycache__", ".pytest_cache"}

    def ignore(_directory: str, names: list[str]) -> set[str]:
        return {name for name in names if name in ignored_names or name.endswith(".pyc")}

    shutil.copytree(repository_root, destination, ignore=ignore)


def _failed_selectors(report: dict[str, Any]) -> list[str]:
    selectors: set[str] = set()
    for worker in report.get("worker_results", []):
        for key in ("failure_details", "error_details"):
            for detail in worker.get(key, []):
                selector = str(detail.get("selector", ""))
                if selector:
                    selectors.add(selector)
    return sorted(selectors)


def run_mutation_verification(repository_root: Path, *, workers: int = 2) -> dict[str, Any]:
    root = repository_root.resolve()
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="platform-validation-mutations-") as temporary:
        temporary_root = Path(temporary).resolve()
        shadow = (temporary_root / "repository").resolve()
        if temporary_root not in shadow.parents:
            raise RuntimeError("refusing to create mutation shadow outside the temporary directory")
        _copy_shadow(root, shadow)
        baseline_path = temporary_root / "baseline.json"
        baseline_path.write_text(
            json.dumps(create_baseline_snapshot(shadow), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        for index, mutation in enumerate(MUTATIONS, 1):
            target = shadow / mutation.path
            original = target.read_bytes()
            result_path = temporary_root / f"result-{index}.json"
            check_started = time.perf_counter()
            try:
                apply_mutation(target, mutation.before, mutation.after)
                command = [
                    sys.executable,
                    str(shadow / "tools" / "validate.py"),
                    mutation.mode,
                    "--workers",
                    str(workers),
                    "--json",
                    str(result_path),
                ]
                if mutation.mode == "changed":
                    command.extend(["--baseline", str(baseline_path)])
                completed = subprocess.run(
                    command,
                    cwd=shadow,
                    capture_output=True,
                    text=True,
                    timeout=180,
                    check=False,
                )
                report = json.loads(result_path.read_text(encoding="utf-8"))
                failed = _failed_selectors(report)
                detector_failed = mutation.expected_detector in failed
                rows.append(
                    {
                        "mutation": asdict(mutation) | {"before": "<redacted source transform>", "after": "<redacted source transform>"},
                        "validation_status": report.get("status"),
                        "return_code": completed.returncode,
                        "detector_failed": detector_failed,
                        "failed_selectors": failed,
                        "selected_suites": report.get("selected_suites", []),
                        "tests_run": report.get("tests_run", 0),
                        "wall_seconds": report.get("wall_seconds", 0.0),
                        "check_wall_seconds": time.perf_counter() - check_started,
                    }
                )
            finally:
                target.write_bytes(original)

    passed = all(
        row["return_code"] != 0
        and row["validation_status"] == "failed"
        and row["detector_failed"]
        for row in rows
    ) and len(rows) == len(MUTATIONS)
    return {
        "schema_version": "1.0",
        "report_type": "controlled_mutation_verification",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "canonical_checkout_mutated": False,
        "status": "passed" if passed else "failed",
        "mutations_required": len(MUTATIONS),
        "mutations_detected": sum(bool(row["detector_failed"]) for row in rows),
        "workers": workers,
        "checks": rows,
        "wall_seconds": time.perf_counter() - started,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    report = run_mutation_verification(arguments.repository_root, workers=arguments.workers)
    write_json_atomic(arguments.output, report)
    print(
        f"{report['status'].upper()} mutation verification: "
        f"{report['mutations_detected']}/{report['mutations_required']} detected "
        f"in {report['wall_seconds']:.3f}s"
    )
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

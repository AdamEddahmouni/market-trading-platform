"""Informational runner-overhead and fixed-fixture production benchmarks.

This tool intentionally has no absolute performance pass/fail thresholds. It
writes a report only when ``--output`` is supplied.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Sequence


Operation = Callable[[], object]


def _timing_summary(samples: list[float]) -> dict[str, Any]:
    return {
        "sample_seconds": samples,
        "minimum_seconds": min(samples),
        "median_seconds": statistics.median(samples),
        "mean_seconds": statistics.fmean(samples),
        "maximum_seconds": max(samples),
    }


def _unavailable(name: str, reason: str) -> dict[str, str]:
    return {"name": name, "availability": "unavailable", "reason": reason}


def measure_operation(
    name: str,
    operation: Operation,
    *,
    iterations: int = 1_000,
    repeat: int = 5,
) -> dict[str, Any]:
    """Measure a callable, or explicitly report why it cannot be measured."""

    if iterations < 1 or repeat < 1:
        raise ValueError("iterations and repeat must be at least 1")
    try:
        operation()
    except Exception as exc:  # An optional production adapter may not be present.
        return _unavailable(name, f"{type(exc).__name__}: {exc}")

    samples: list[float] = []
    try:
        for _ in range(repeat):
            started = time.perf_counter()
            for _ in range(iterations):
                operation()
            samples.append(time.perf_counter() - started)
    except Exception as exc:
        return _unavailable(name, f"{type(exc).__name__}: {exc}")

    row = {
        "name": name,
        "availability": "measured",
        "iterations_per_sample": iterations,
        "repeat": repeat,
        **_timing_summary(samples),
    }
    row["median_seconds_per_operation"] = row["median_seconds"] / iterations
    return row


def measure_command(
    name: str,
    command: Sequence[str],
    *,
    repository_root: Path,
    repeat: int,
) -> dict[str, Any]:
    """Measure isolated command wall time while retaining its exit codes."""

    if repeat < 1:
        raise ValueError("repeat must be at least 1")
    samples: list[float] = []
    return_codes: list[int] = []
    stdout_bytes: list[int] = []
    stderr_bytes: list[int] = []
    try:
        for _ in range(repeat):
            started = time.perf_counter()
            completed = subprocess.run(
                list(command),
                cwd=str(repository_root),
                check=False,
                capture_output=True,
            )
            samples.append(time.perf_counter() - started)
            return_codes.append(completed.returncode)
            stdout_bytes.append(len(completed.stdout))
            stderr_bytes.append(len(completed.stderr))
    except OSError as exc:
        return _unavailable(name, f"{type(exc).__name__}: {exc}")
    return {
        "name": name,
        "availability": "measured",
        "repeat": repeat,
        "command_label": name,
        "return_codes": return_codes,
        "stdout_bytes": stdout_bytes,
        "stderr_bytes": stderr_bytes,
        **_timing_summary(samples),
    }


def _measure_fixture_operation(
    name: str,
    fixture_refs: Sequence[str],
    prepare: Callable[[], Operation],
    *,
    iterations: int,
    repeat: int,
) -> dict[str, Any]:
    """Prepare fixed inputs outside the clock, then time the production API."""

    try:
        operation = prepare()
    except Exception as exc:
        row: dict[str, Any] = _unavailable(name, f"{type(exc).__name__}: {exc}")
    else:
        row = measure_operation(name, operation, iterations=iterations, repeat=repeat)
    row["fixture_refs"] = list(fixture_refs)
    return row


def _macro_observations(repository_root: Path) -> tuple[list[object], str]:
    from market_platform_foundation.fred.contracts import MacroObservation
    from market_platform_foundation.fred.registry import lookup_canonical

    fixture = repository_root / "tests" / "fixtures" / "fred" / "cross_frequency_pit.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    observations: list[object] = []
    for row in payload["series"]:
        entry = lookup_canonical(str(row["canonical_indicator_id"]))
        if entry is None:
            raise ValueError(f"unmapped macro fixture row: {row['canonical_indicator_id']}")
        available_time = str(row["available_time"])
        raw_value = str(row["value"])
        observations.append(
            MacroObservation(
                canonical_indicator_id=entry.canonical_indicator_id,
                series_id=entry.fred_series_id,
                observation_date=str(row["observation_date"]),
                raw_value=raw_value,
                normalized_value=float(raw_value),
                frequency=entry.frequency,
                units=entry.units,
                seasonal_adjustment=entry.seasonal_adjustment,
                source_agency=entry.original_source,
                fred_release_id=entry.fred_release_id,
                realtime_start=available_time,
                realtime_end="9999-12-31",
                vintage_date=str(row["observation_date"]),
                knowledge_start_date=available_time,
                available_time=available_time,
                availability_precision="TIMESTAMP",
                observed_time=available_time,
                retrieved_time=available_time,
            )
        )
    return observations, str(payload["decision_time"])


def _simulation_events(repository_root: Path) -> list[dict[str, Any]]:
    fixture = (
        repository_root
        / "tests"
        / "fixtures"
        / "providers"
        / "distribution"
        / "nvda_bars_slice.json"
    )
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    base_time = 2_000_000_000_000_000_000
    events: list[dict[str, Any]] = []
    for index, bar in enumerate(payload["bars"][:20]):
        available_time = base_time + index * 60_000_000_000
        events.append(
            {
                "available_time": available_time,
                "bar_payload": {
                    "close": str(bar["close"]),
                    "high": str(bar["high"]),
                    "low": str(bar["low"]),
                    "open": str(bar["open"]),
                    "timeframe": "1_MINUTE",
                    "volume": 10_000 + index * 100,
                },
                "channel_id": "NVDA-FIXTURE",
                "event_time": available_time - 1,
                "event_type": "BAR_OHLCV_1M",
                "historical_ingested_time": available_time,
                "ingest_run_id": "BENCHMARK-FIXTURE",
                "instrument_id": str(payload["symbol"]),
                "normalization_version": "benchmark/1.0.0",
                "normalized_event_id": f"benchmark-bar-{index}",
                "operation": "UPSERT",
                "publisher_id": "FIXTURE",
                "quality_observation_refs": [],
                "raw_reference": fixture.relative_to(repository_root).as_posix(),
                "schema_version": "1.0.0",
                "source_instance_id": "FIXTURE",
                "source_record_id": f"benchmark-{index}",
                "source_revision_id": "1",
                "venue_id": "US_EQUITY",
            }
        )
    return events


def _production_operations(
    repository_root: Path, *, operation_iterations: int, repeat: int
) -> list[dict[str, Any]]:
    source_root = str(repository_root / "src")
    added_source_path = source_root not in sys.path
    if added_source_path:
        sys.path.insert(0, source_root)
    try:
        def prepare_p0_join() -> Operation:
            from market_platform_foundation.contracts.reference import ReferenceKind
            from market_platform_foundation.runtime.pit_joins import join_as_of, store_from_fixture

            store = store_from_fixture()
            market_time = "2025-01-15T20:00:00.000000000Z"
            knowledge_time = "2024-06-14T23:59:59.000000000Z"
            return lambda: join_as_of(
                store,
                ReferenceKind.FUTURES_SPEC,
                "ES",
                market_time,
                knowledge_time,
            )

        def prepare_bitemporal_lookup() -> Operation:
            from market_platform_foundation.contracts.reference import ReferenceKind
            from market_platform_foundation.runtime.pit_joins import store_from_fixture

            store = store_from_fixture()
            return lambda: store.as_of(
                ReferenceKind.FUTURES_SPEC,
                "ES",
                "2025-01-15T20:00:00.000000000Z",
                "2024-06-14T23:59:59.000000000Z",
            )

        def prepare_fred_registry() -> Operation:
            from market_platform_foundation.fred.registry import lookup_canonical

            payload = json.loads(
                (
                    repository_root
                    / "tests"
                    / "fixtures"
                    / "fred"
                    / "cross_frequency_pit.json"
                ).read_text(encoding="utf-8")
            )
            canonical_id = str(payload["series"][0]["canonical_indicator_id"])
            return lambda: lookup_canonical(canonical_id)

        def prepare_eia_registry() -> Operation:
            from market_platform_foundation.eia.registry import lookup_canonical

            fixture = (
                repository_root / "tests" / "fixtures" / "eia" / "petroleum_weekly_rows.json"
            )
            json.loads(fixture.read_text(encoding="utf-8"))
            return lambda: lookup_canonical("COMMERCIAL_CRUDE_STOCKS")

        def prepare_macro_state() -> Operation:
            from market_platform_foundation.fred.pit import macro_state_as_of

            observations, decision_time = _macro_observations(repository_root)
            return lambda: macro_state_as_of(observations, decision_time=decision_time)

        def prepare_energy_context() -> Operation:
            from market_platform_foundation.cftc.store import CotStore
            from market_platform_foundation.eia.cross_asset import build_energy_market_context
            from market_platform_foundation.eia.normalize import normalize_api_row
            from market_platform_foundation.eia.store import EiaStore

            observations, decision_time = _macro_observations(repository_root)
            fixture = (
                repository_root / "tests" / "fixtures" / "eia" / "petroleum_weekly_rows.json"
            )
            payload = json.loads(fixture.read_text(encoding="utf-8"))
            eia_store = EiaStore()
            for source_row in payload["rows"]:
                observation = normalize_api_row(
                    source_row,
                    observed_time=str(payload["observed_time"]),
                    retrieved_time=str(payload["retrieved_time"]),
                    api_first_observed_time=str(payload["observed_time"]),
                )
                if observation is not None:
                    eia_store.add_observation(observation)
            cot_store = CotStore()
            return lambda: build_energy_market_context(
                macro_observations=observations,
                cot_store=cot_store,
                eia_store=eia_store,
                decision_time=max(decision_time, "2026-08-20T16:00:00Z"),
                contract_family_id="CL",
            )

        def prepare_short_pressure() -> Operation:
            from market_platform_foundation.finra.short_interest import normalize_short_interest_row
            from market_platform_foundation.short_intelligence.identity import SymbolMap
            from market_platform_foundation.short_intelligence.pressure import pressure_state
            from market_platform_foundation.short_intelligence.store import ShortIntelligenceStore

            fixture_dir = repository_root / "tests" / "fixtures" / "short_intelligence"
            symbol_map = SymbolMap.from_path(fixture_dir / "symbol_map.json")
            payload = json.loads(
                (fixture_dir / "consolidated_short_interest_slice.json").read_text(
                    encoding="utf-8"
                )
            )
            store = ShortIntelligenceStore()
            store.add_short_interest(
                normalize_short_interest_row(
                    payload[0],
                    symbol_map=symbol_map,
                    observed_time="2026-08-11T20:45:00Z",
                    retrieved_time="2026-08-11T20:45:00Z",
                )
            )
            return lambda: pressure_state(store, "BIYA", "2026-08-11T21:00:00Z")

        def prepare_cftc_mapping() -> Operation:
            from market_platform_foundation.cftc.mapping import load_mapper_from_fixture

            fixture = (
                repository_root
                / "tests"
                / "fixtures"
                / "cftc"
                / "product_hierarchy_slice.json"
            )
            mapper = load_mapper_from_fixture(fixture)
            return lambda: mapper.resolve(
                cftc_contract_market_code="13874+",
                market_and_exchange_names="E-MINI S&P 500",
            )

        def prepare_simulation() -> Operation:
            from market_platform_foundation.risk_simulation.evaluation import (
                run_risk_simulation_evaluation,
            )

            events = _simulation_events(repository_root)
            return lambda: run_risk_simulation_evaluation(
                events, enable_squeeze_replay=False
            )

        p0_fixture = "tests/fixtures/platform/p0/p0_bitemporal_slice.json"
        macro_fixture = "tests/fixtures/fred/cross_frequency_pit.json"
        energy_fixture = "tests/fixtures/eia/petroleum_weekly_rows.json"
        short_fixtures = (
            "tests/fixtures/short_intelligence/consolidated_short_interest_slice.json",
            "tests/fixtures/short_intelligence/symbol_map.json",
        )
        measured = [
            _measure_fixture_operation(
                "p0_as_of_lookup",
                (p0_fixture,),
                prepare_p0_join,
                iterations=operation_iterations,
                repeat=repeat,
            ),
            _measure_fixture_operation(
                "bitemporal_revision_lookup",
                (p0_fixture,),
                prepare_bitemporal_lookup,
                iterations=operation_iterations,
                repeat=repeat,
            ),
            _measure_fixture_operation(
                "fred_registry_lookup",
                (macro_fixture,),
                prepare_fred_registry,
                iterations=operation_iterations,
                repeat=repeat,
            ),
            _measure_fixture_operation(
                "eia_registry_lookup",
                (energy_fixture,),
                prepare_eia_registry,
                iterations=operation_iterations,
                repeat=repeat,
            ),
            _measure_fixture_operation(
                "macro_state_as_of",
                (macro_fixture,),
                prepare_macro_state,
                iterations=min(operation_iterations, 200),
                repeat=repeat,
            ),
            _measure_fixture_operation(
                "energy_market_context",
                (macro_fixture, energy_fixture),
                prepare_energy_context,
                iterations=min(operation_iterations, 50),
                repeat=repeat,
            ),
            _measure_fixture_operation(
                "short_pressure_state",
                short_fixtures,
                prepare_short_pressure,
                iterations=min(operation_iterations, 500),
                repeat=repeat,
            ),
            _measure_fixture_operation(
                "cftc_product_mapping",
                ("tests/fixtures/cftc/product_hierarchy_slice.json",),
                prepare_cftc_mapping,
                iterations=operation_iterations,
                repeat=repeat,
            ),
            _measure_fixture_operation(
                "representative_simulation_operation",
                ("tests/fixtures/providers/distribution/nvda_bars_slice.json",),
                prepare_simulation,
                iterations=min(operation_iterations, 10),
                repeat=repeat,
            ),
        ]
    finally:
        if added_source_path:
            sys.path.remove(source_root)
    return measured


def run_benchmarks(
    repository_root: Path,
    *,
    repeat: int = 5,
    operation_iterations: int = 1_000,
    include_fast: bool = False,
    fast_command: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Return an informational benchmark report without writing files."""

    if repeat < 1 or operation_iterations < 1:
        raise ValueError("repeat and operation_iterations must be at least 1")
    root = Path(repository_root).resolve()
    startup = measure_command(
        "python_startup",
        (sys.executable, "-I", "-c", "pass"),
        repository_root=root,
        repeat=repeat,
    )
    tiny_worker_source = (
        "import unittest; "
        "case=type('Tiny',(unittest.TestCase,),{'test_ok':lambda self:self.assertTrue(True)}); "
        "result=unittest.TestResult(); unittest.defaultTestLoader.loadTestsFromTestCase(case).run(result); "
        "raise SystemExit(0 if result.wasSuccessful() else 1)"
    )
    tiny_worker = measure_command(
        "tiny_unittest_worker",
        (sys.executable, "-I", "-c", tiny_worker_source),
        repository_root=root,
        repeat=repeat,
    )
    if include_fast:
        command = tuple(fast_command) if fast_command is not None else (
            sys.executable,
            str(root / "tools" / "validate.py"),
            "fast",
        )
        fast = measure_command(
            "fast_validation", command, repository_root=root, repeat=repeat
        )
    else:
        fast = {
            "name": "fast_validation",
            "availability": "not_requested",
            "reason": "use --include-fast to benchmark the FAST command",
        }

    return {
        "schema_version": "1.0",
        "report_type": "informational_benchmark",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository_root": str(root),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "logical_cpu_count": os.cpu_count(),
        "configuration": {
            "repeat": repeat,
            "operation_iterations": operation_iterations,
            "fast_included": include_fast,
        },
        "runner_overhead": [startup, tiny_worker, fast],
        "production_operations": _production_operations(
            root, operation_iterations=operation_iterations, repeat=repeat
        ),
        "interpretation": (
            "Informational timings only; no absolute performance pass/fail threshold is applied."
        ),
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    """Atomically write a benchmark report to an explicitly supplied path."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repeat", type=int, default=5)
    parser.add_argument("--operation-iterations", type=int, default=1_000)
    parser.add_argument("--include-fast", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        report = run_benchmarks(
            arguments.repository_root,
            repeat=arguments.repeat,
            operation_iterations=arguments.operation_iterations,
            include_fast=arguments.include_fast,
        )
    except ValueError as exc:
        print(f"benchmark configuration error: {exc}", file=sys.stderr)
        return 2
    if arguments.output is not None:
        write_report(arguments.output, report)
    print(json.dumps(report, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "measure_command",
    "measure_operation",
    "run_benchmarks",
    "write_report",
]

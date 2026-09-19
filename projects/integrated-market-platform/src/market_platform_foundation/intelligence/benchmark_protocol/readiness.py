"""Assess whether Smoke10 wiring is ready (not whether scores were run)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .historical_harness_adapter import adapt_historical_research_run_manifest_v1
from .suite_catalog import load_suite_catalog, suite_catalog_fingerprint
from .smoke10 import build_smoke10_invocation_contract


def assess_benchmark_smoke10_readiness(
    repository_root: Path,
    *,
    sample_historical_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    try:
        catalog = load_suite_catalog(repository_root)
        suite_catalog_fingerprint(catalog)
    except (OSError, ValueError, FileNotFoundError) as error:
        reasons.append(f"SUITE_CATALOG:{error}")
        return _readiness_payload(False, reasons)

    try:
        contract = build_smoke10_invocation_contract(repository_root)
        if contract.get("scores_executed"):
            reasons.append("SMOKE10_SCORES_MUST_NOT_BE_PREEXECUTED")
    except (OSError, ValueError, FileNotFoundError) as error:
        reasons.append(f"SMOKE10_CONTRACT:{error}")
        return _readiness_payload(False, reasons)

    if sample_historical_manifest is not None:
        try:
            record = adapt_historical_research_run_manifest_v1(
                sample_historical_manifest,
                suite_id=catalog.get("suite_id"),
                suite_catalog_fingerprint=suite_catalog_fingerprint(catalog),
            )
            build_smoke10_invocation_contract(repository_root, historical_run_record=record)
        except ValueError as error:
            reasons.append(f"HISTORICAL_ADAPTER:{error}")
            return _readiness_payload(False, reasons)

    if reasons:
        return _readiness_payload(False, reasons)
    return _readiness_payload(True, reasons)


def _readiness_payload(ready: bool, reasons: list[str]) -> dict[str, Any]:
    return {
        "BENCHMARK_SMOKE10_READY": "YES" if ready else "NO",
        "protocol_status": "MINIMAL_GREENFIELD_V1",
        "full_suite_case_count": 30,
        "smoke10_case_count": 10,
        "scores_executed": False,
        "reasons": reasons,
    }


__all__ = ["assess_benchmark_smoke10_readiness"]

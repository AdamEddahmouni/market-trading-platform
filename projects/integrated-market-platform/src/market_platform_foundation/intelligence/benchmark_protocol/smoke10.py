"""Smoke10 invocation contract (plan + wiring; scores not executed by default)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .suite_catalog import load_suite_catalog, smoke10_case_ids, suite_catalog_fingerprint
from .types import IBP_SMOKE10_CONTRACT_ID, IBP_SMOKE10_CASE_COUNT


def build_smoke10_invocation_contract(
    repository_root: Path,
    *,
    historical_run_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a reproducible Smoke10 plan without running evaluators or scoring."""
    catalog = load_suite_catalog(repository_root)
    cases = catalog["cases"]
    smoke_ids = smoke10_case_ids(catalog)
    case_plans: list[dict[str, Any]] = []
    for case_id in smoke_ids:
        case = next(row for row in cases if row["case_id"] == case_id)
        case_plans.append(
            {
                "case_id": case_id,
                "blind_mode": case.get("blind_mode"),
                "input_profile": case.get("input_profile"),
                "evaluator_gold_ref": case.get("evaluator_gold_ref"),
                "evaluator_gold_loaded_for_sut": False,
                "scores_executed": False,
                "historical_harness_fixture": case.get("historical_harness_fixture"),
            }
        )
    contract: dict[str, Any] = {
        "contract_id": IBP_SMOKE10_CONTRACT_ID,
        "suite_id": catalog.get("suite_id"),
        "suite_catalog_fingerprint": suite_catalog_fingerprint(catalog),
        "case_count": IBP_SMOKE10_CASE_COUNT,
        "case_plans": case_plans,
        "scores_executed": False,
        "evaluator_invoked": False,
        "historical_harness_integration": historical_run_record is not None,
    }
    if historical_run_record is not None:
        contract["historical_harness_ibp_record_fingerprint"] = historical_run_record.get(
            "record_fingerprint"
        )
    return contract


__all__ = ["build_smoke10_invocation_contract"]

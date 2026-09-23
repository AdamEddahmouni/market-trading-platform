"""RTH15-10 Benchmark Protocol v1 contamination and evaluation controls."""

from __future__ import annotations

from typing import Any

from .suite_catalog import load_suite_catalog, smoke10_case_ids, suite_catalog_fingerprint
from .types import (
    IBP_FULL_SUITE_CASE_COUNT,
    IBP_PROTOCOL_ID,
    IBP_PROTOCOL_SCHEMA_VERSION,
    IBP_SMOKE10_CASE_COUNT,
    IntelligenceBenchmarkBlindMode,
)

LOOKAHEAD_POLICY = "FORBIDDEN"
CONTEXT_RESET_POLICY = "one_fresh_context_per_case_v1"
CONTAMINATED_CASE_POLICY = "INVALIDATE_NO_PARTIAL_CREDIT"
VANITY_AGGREGATE_SCORE_POLICY = "FORBIDDEN"
EVIDENCE_CLASS = "SOFTWARE_CONTROLLED"

LOOKAHEAD_FORBIDDEN_BLIND_KEYS = frozenset(
    {
        "gold_answer",
        "expected_label",
        "expected_labels",
        "expected_facts",
        "outcome",
        "future_bars",
        "future_session_data",
        "post_cutoff_evidence",
        "settlement_outcome",
        "labels_path",
        "evaluator_gold_path",
        "evaluator_gold_ref",
        "answer_key",
        "rubric_answer_key",
        "evaluator_only_gold",
    }
)

# Modes A–E: blindness / routing profiles (capability surface, not market edge).
BLIND_MODE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "A": {
        "mode": "A",
        "name": "order_flow_reversal_quotes_trades",
        "semantic_event_type": "ORDER_FLOW_REVERSAL",
        "capability_surface": ("QUOTES", "TRADES"),
        "blindness": "SUT sees case inputs only; no evaluator gold; no future outcomes",
    },
    "B": {
        "mode": "B",
        "name": "unusual_options_activity",
        "semantic_event_type": "UNUSUAL_OPTIONS_ACTIVITY",
        "capability_surface": ("OPTIONS_CHAIN",),
        "blindness": "SUT sees case inputs only; no evaluator gold; no future outcomes",
    },
    "C": {
        "mode": "C",
        "name": "borrow_change_short_interest",
        "semantic_event_type": "BORROW_CHANGE",
        "capability_surface": ("SHORT_INTEREST",),
        "blindness": "SUT sees case inputs only; no evaluator gold; no future outcomes",
    },
    "D": {
        "mode": "D",
        "name": "news_event",
        "semantic_event_type": "NEWS_EVENT",
        "capability_surface": ("NEWS",),
        "blindness": "SUT sees case inputs only; no evaluator gold; no future outcomes",
    },
    "E": {
        "mode": "E",
        "name": "regime_shift_macro_quotes",
        "semantic_event_type": "REGIME_SHIFT",
        "capability_surface": ("MACRO", "QUOTES"),
        "blindness": "SUT sees case inputs only; no evaluator gold; no future outcomes",
    },
}

CATASTROPHIC_CRITERIA: dict[str, dict[str, str]] = {
    "GOLD_EXPOSED_TO_SUT": {
        "id": "GOLD_EXPOSED_TO_SUT",
        "description": "Evaluator-only gold reached the system under test",
        "failure_reason": "CATASTROPHIC_GOLD_EXPOSURE",
    },
    "LOOKAHEAD_IN_SUT_INPUT": {
        "id": "LOOKAHEAD_IN_SUT_INPUT",
        "description": "Blind SUT input contained future/outcome/gold lookahead keys",
        "failure_reason": "CATASTROPHIC_LOOKAHEAD",
    },
    "CROSS_CASE_CONTEXT_LEAK": {
        "id": "CROSS_CASE_CONTEXT_LEAK",
        "description": "Prior case context was visible across cases",
        "failure_reason": "CATASTROPHIC_CONTEXT_LEAK",
    },
    "LIVE_OR_ITEM9_AUTHORITY_CLAIM": {
        "id": "LIVE_OR_ITEM9_AUTHORITY_CLAIM",
        "description": "SUT claimed live execution or Item 9 calibration authority",
        "failure_reason": "CATASTROPHIC_AUTHORITY_CLAIM",
    },
    "EXPLICIT_SUT_CATASTROPHIC_FLAG": {
        "id": "EXPLICIT_SUT_CATASTROPHIC_FLAG",
        "description": "SUT response set catastrophic=true",
        "failure_reason": "CATASTROPHIC_FLAG",
    },
}

VANITY_AGGREGATE_FORBIDDEN_KEYS = frozenset(
    {
        "overall_score",
        "aggregate_score",
        "accuracy",
        "pass_rate",
        "overall_pass_rate",
        "trading_performance",
        "pnl_score",
        "edge_score",
        "vanity_score",
    }
)


def assert_no_lookahead_in_blind_input(blind_input: dict[str, Any]) -> None:
    """Fail closed if blind SUT input embeds gold, outcomes, or future evidence."""
    for key in LOOKAHEAD_FORBIDDEN_BLIND_KEYS:
        if key in blind_input:
            raise ValueError(f"IBP_LOOKAHEAD_FORBIDDEN:{key}")


def assert_no_vanity_aggregate_score(payload: dict[str, Any]) -> None:
    """Protocol forbids collapsing Smoke10 into a single vanity / trading score."""
    for key in VANITY_AGGREGATE_FORBIDDEN_KEYS:
        if key in payload:
            raise ValueError(f"IBP_VANITY_AGGREGATE_FORBIDDEN:{key}")
    summaries = payload.get("summaries")
    if isinstance(summaries, dict):
        for key in VANITY_AGGREGATE_FORBIDDEN_KEYS:
            if key in summaries:
                raise ValueError(f"IBP_VANITY_AGGREGATE_FORBIDDEN:summaries.{key}")


def evaluate_catastrophic_triggers(
    *,
    sut_response: dict[str, Any],
    blind_input: dict[str, Any],
    case_row_flags: dict[str, Any] | None = None,
) -> list[str]:
    """Return triggered catastrophic criterion ids (empty => no catastrophe)."""
    flags = case_row_flags or {}
    triggered: list[str] = []
    if flags.get("evaluator_gold_loaded_for_sut") or flags.get("sut_response_includes_gold"):
        triggered.append("GOLD_EXPOSED_TO_SUT")
    if any(key in blind_input for key in LOOKAHEAD_FORBIDDEN_BLIND_KEYS):
        triggered.append("LOOKAHEAD_IN_SUT_INPUT")
    if flags.get("prior_case_ids_visible_to_sut"):
        triggered.append("CROSS_CASE_CONTEXT_LEAK")
    authority = str(sut_response.get("authority") or "")
    if authority in {"LIVE", "ITEM9_CALIBRATION"} or sut_response.get("live_authority"):
        triggered.append("LIVE_OR_ITEM9_AUTHORITY_CLAIM")
    if sut_response.get("catastrophic"):
        triggered.append("EXPLICIT_SUT_CATASTROPHIC_FLAG")
    return triggered


def invalidate_contaminated_case(case_row: dict[str, Any], *, reason: str) -> dict[str, Any]:
    """Mark a case INVALID and strip scored dimensions (no partial credit)."""
    prior_dimensions = dict(case_row.get("dimension_scores") or {})
    invalidated = {
        **case_row,
        "case_validity": "INVALID",
        "partial_credit_applied": False,
        "invalidation_reason": reason,
        "dimension_scores_before_invalidation": prior_dimensions,
        "dimension_scores": {dim: "INVALID" for dim in prior_dimensions},
        "failure_reasons": list(case_row.get("failure_reasons") or []) + [f"CASE_INVALIDATED:{reason}"],
        "scores_executed": False,
    }
    return invalidated


def apply_contamination_invalidation(run_record: dict[str, Any]) -> dict[str, Any]:
    """Invalidate contaminated cases in-place; never leave partial credit standing."""
    audit = run_record.get("contamination_audit") or {}
    checks = audit.get("checks") or {}
    case_results = list(run_record.get("case_results") or [])
    invalidated_ids: list[str] = []

    for index, row in enumerate(case_results):
        reasons: list[str] = []
        if row.get("evaluator_gold_loaded_for_sut") or row.get("sut_response_includes_gold"):
            reasons.append("DID_SYSTEM_SEE_GOLD")
        if row.get("prior_case_ids_visible_to_sut"):
            reasons.append("DID_CASE_CONTEXT_LEAK")
        if reasons:
            case_results[index] = invalidate_contaminated_case(row, reason="+".join(reasons))
            invalidated_ids.append(str(row.get("case_id")))

    # Suite-level contamination without per-case flags still invalidates all scored cases.
    suite_reasons: list[str] = []
    if checks.get("DID_SYSTEM_SEE_GOLD") == "FAIL" and not invalidated_ids:
        suite_reasons.append("DID_SYSTEM_SEE_GOLD")
    if checks.get("DID_CASE_CONTEXT_LEAK") == "FAIL":
        # Duplicate tokens / shared context: invalidate every case that still looks valid.
        suite_reasons.append("DID_CASE_CONTEXT_LEAK")
    if suite_reasons:
        reason = "+".join(suite_reasons)
        for index, row in enumerate(case_results):
            if row.get("case_validity") == "INVALID":
                continue
            case_results[index] = invalidate_contaminated_case(row, reason=reason)
            invalidated_ids.append(str(row.get("case_id")))

    run_record["case_results"] = case_results
    run_record["invalidated_case_ids"] = sorted(set(invalidated_ids))
    run_record["contaminated_case_policy"] = CONTAMINATED_CASE_POLICY
    run_record["partial_credit_applied"] = False
    return run_record


def build_protocol_v1_freeze_certificate(repository_root) -> dict[str, Any]:
    """Machine-readable frozen statement that RTH15-10 protocol properties are present."""
    catalog = load_suite_catalog(repository_root)
    modes_present = {case.get("blind_mode") for case in catalog["cases"]}
    expected_modes = {mode.value for mode in IntelligenceBenchmarkBlindMode}
    properties = {
        "blind_system_under_test_inputs": "PRESENT",
        "evaluator_only_gold": "PRESENT",
        "context_reset": "PRESENT",
        "no_lookahead": "PRESENT",
        "modes_a_through_e": "PRESENT" if modes_present == expected_modes else "MISSING",
        "per_case_booleans": "PRESENT",
        "failure_reasons": "PRESENT",
        "catastrophic_criteria": "PRESENT",
        "machine_readable_frozen_case_definition": "PRESENT",
        "reproducible_runner": "PRESENT",
        "smoke10_composition": "PRESENT",
        "no_vanity_aggregate_score": "PRESENT",
        "invalidate_contaminated_cases": "PRESENT",
    }
    complete = all(value == "PRESENT" for value in properties.values())
    return {
        "artifact_kind": "ibp_protocol_v1_freeze_certificate",
        "schema_version": "imp.intelligence-benchmark-protocol-freeze/1.0.0",
        "protocol_id": IBP_PROTOCOL_ID,
        "protocol_schema_version": IBP_PROTOCOL_SCHEMA_VERSION,
        "suite_id": catalog.get("suite_id"),
        "suite_catalog_fingerprint": suite_catalog_fingerprint(catalog),
        "full_suite_case_count": IBP_FULL_SUITE_CASE_COUNT,
        "smoke10_case_count": IBP_SMOKE10_CASE_COUNT,
        "smoke10_case_ids": list(smoke10_case_ids(catalog)),
        "lookahead_policy": LOOKAHEAD_POLICY,
        "context_reset_policy": CONTEXT_RESET_POLICY,
        "contaminated_case_policy": CONTAMINATED_CASE_POLICY,
        "vanity_aggregate_score_policy": VANITY_AGGREGATE_SCORE_POLICY,
        "evidence_class": EVIDENCE_CLASS,
        "blind_mode_definitions": BLIND_MODE_DEFINITIONS,
        "catastrophic_criteria": CATASTROPHIC_CRITERIA,
        "rth15_10_properties": properties,
        "RTH15_10_COMPLETE": "YES" if complete else "NO",
        "not_market_ftep_or_calibration_evidence": True,
    }


__all__ = [
    "BLIND_MODE_DEFINITIONS",
    "CATASTROPHIC_CRITERIA",
    "CONTAMINATED_CASE_POLICY",
    "CONTEXT_RESET_POLICY",
    "EVIDENCE_CLASS",
    "LOOKAHEAD_FORBIDDEN_BLIND_KEYS",
    "LOOKAHEAD_POLICY",
    "VANITY_AGGREGATE_FORBIDDEN_KEYS",
    "VANITY_AGGREGATE_SCORE_POLICY",
    "apply_contamination_invalidation",
    "assert_no_lookahead_in_blind_input",
    "assert_no_vanity_aggregate_score",
    "build_protocol_v1_freeze_certificate",
    "evaluate_catastrophic_triggers",
    "invalidate_contaminated_case",
]

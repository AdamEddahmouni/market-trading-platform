"""Serialization for strategy research promotion registry artifacts."""

from __future__ import annotations

from typing import Any

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from .research_types import (
    ResearchPromotionReasonCode,
    ResearchResultSummaryV1,
    RuntimeParityComparisonRecordV1,
    RuntimeParityDisposition,
    STRATEGY_RESEARCH_PROMOTION_REGISTRY_IMPLEMENTATION_VERSION,
    StrategyResearchEvidenceBundleV1,
    StrategyResearchPromotionLifecycleState,
    StrategyResearchPromotionRecordV1,
    StrategyResearchPromotionTransitionV1,
)


def _result_to_dict(result: ResearchResultSummaryV1 | None) -> dict[str, Any] | None:
    if result is None:
        return None
    return {
        "summary_id": result.summary_id,
        "metric_name": result.metric_name,
        "metric_value": result.metric_value,
        "sample_count": result.sample_count,
        "window_label": result.window_label,
        "report_ref": result.report_ref,
    }


def _result_from_dict(payload: dict[str, Any] | None) -> ResearchResultSummaryV1 | None:
    if payload is None:
        return None
    return ResearchResultSummaryV1(
        summary_id=str(payload["summary_id"]),
        metric_name=str(payload["metric_name"]),
        metric_value=payload.get("metric_value"),
        sample_count=payload.get("sample_count"),
        window_label=str(payload.get("window_label", "")),
        report_ref=payload.get("report_ref"),
    )


def strategy_research_evidence_bundle_v1_to_dict(
    bundle: StrategyResearchEvidenceBundleV1,
) -> dict[str, Any]:
    return {
        "strategy_id": bundle.strategy_id,
        "runtime_id": bundle.runtime_id,
        "runtime_version": bundle.runtime_version,
        "source_hash": bundle.source_hash,
        "dataset_hashes": list(bundle.dataset_hashes),
        "pit_classification": bundle.pit_classification,
        "in_sample_result": _result_to_dict(bundle.in_sample_result),
        "out_of_sample_result": _result_to_dict(bundle.out_of_sample_result),
        "walk_forward_result": _result_to_dict(bundle.walk_forward_result),
        "transaction_cost_assumptions": bundle.transaction_cost_assumptions,
        "regime_sensitivity": bundle.regime_sensitivity,
        "capacity_liquidity_notes": bundle.capacity_liquidity_notes,
        "multiple_testing_controls": bundle.multiple_testing_controls,
        "challenger_results": list(bundle.challenger_results),
        "known_contradictions": list(bundle.known_contradictions),
        "metadata": dict(bundle.metadata),
    }


def strategy_research_evidence_bundle_v1_from_dict(
    payload: dict[str, Any],
) -> StrategyResearchEvidenceBundleV1:
    return StrategyResearchEvidenceBundleV1(
        strategy_id=str(payload["strategy_id"]),
        runtime_id=str(payload.get("runtime_id", "")),
        runtime_version=str(payload.get("runtime_version", "")),
        source_hash=str(payload.get("source_hash", "")),
        dataset_hashes=tuple(str(item) for item in payload.get("dataset_hashes", [])),
        pit_classification=str(payload.get("pit_classification", "")),
        in_sample_result=_result_from_dict(payload.get("in_sample_result")),
        out_of_sample_result=_result_from_dict(payload.get("out_of_sample_result")),
        walk_forward_result=_result_from_dict(payload.get("walk_forward_result")),
        transaction_cost_assumptions=str(payload.get("transaction_cost_assumptions", "")),
        regime_sensitivity=str(payload.get("regime_sensitivity", "")),
        capacity_liquidity_notes=str(payload.get("capacity_liquidity_notes", "")),
        multiple_testing_controls=str(payload.get("multiple_testing_controls", "")),
        challenger_results=tuple(str(item) for item in payload.get("challenger_results", [])),
        known_contradictions=tuple(str(item) for item in payload.get("known_contradictions", [])),
        metadata=dict(payload.get("metadata") or {}),
    )


def runtime_parity_comparison_record_v1_to_dict(
    record: RuntimeParityComparisonRecordV1,
) -> dict[str, Any]:
    return {
        "schema_version": record.schema_version,
        "comparison_id": record.comparison_id,
        "strategy_id": record.strategy_id,
        "reference_runtime_id": record.reference_runtime_id,
        "candidate_runtime_id": record.candidate_runtime_id,
        "reference_source_hash": record.reference_source_hash,
        "candidate_source_hash": record.candidate_source_hash,
        "disposition": record.disposition.value,
        "metric_comparisons": [dict(item) for item in record.metric_comparisons],
        "notes": record.notes,
        "implementation_version": record.implementation_version,
        "metadata": dict(record.metadata),
    }


def runtime_parity_comparison_record_v1_from_dict(
    payload: dict[str, Any],
) -> RuntimeParityComparisonRecordV1:
    return RuntimeParityComparisonRecordV1(
        comparison_id=str(payload["comparison_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        strategy_id=str(payload["strategy_id"]),
        reference_runtime_id=str(payload["reference_runtime_id"]),
        candidate_runtime_id=str(payload["candidate_runtime_id"]),
        reference_source_hash=str(payload["reference_source_hash"]),
        candidate_source_hash=str(payload["candidate_source_hash"]),
        disposition=RuntimeParityDisposition(str(payload["disposition"])),
        metric_comparisons=tuple(dict(item) for item in payload.get("metric_comparisons", [])),
        notes=str(payload.get("notes", "")),
        implementation_version=str(
            payload.get(
                "implementation_version",
                STRATEGY_RESEARCH_PROMOTION_REGISTRY_IMPLEMENTATION_VERSION,
            )
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


def strategy_research_promotion_record_v1_to_dict(
    record: StrategyResearchPromotionRecordV1,
) -> dict[str, Any]:
    return {
        "schema_version": record.schema_version,
        "promotion_record_id": record.promotion_record_id,
        "strategy_id": record.strategy_id,
        "lifecycle_state": record.lifecycle_state.value,
        "evidence": strategy_research_evidence_bundle_v1_to_dict(record.evidence),
        "parity_records": [
            runtime_parity_comparison_record_v1_to_dict(item) for item in record.parity_records
        ],
        "reason_codes": [code.value for code in record.reason_codes],
        "review_eligible": record.review_eligible,
        "grants_execution_authority": record.grants_execution_authority,
        "updated_at_ns": record.updated_at_ns,
        "implementation_version": record.implementation_version,
        "metadata": dict(record.metadata),
    }


def strategy_research_promotion_record_v1_from_dict(
    payload: dict[str, Any],
) -> StrategyResearchPromotionRecordV1:
    return StrategyResearchPromotionRecordV1(
        promotion_record_id=str(payload["promotion_record_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        strategy_id=str(payload["strategy_id"]),
        lifecycle_state=StrategyResearchPromotionLifecycleState(str(payload["lifecycle_state"])),
        evidence=strategy_research_evidence_bundle_v1_from_dict(payload["evidence"]),
        parity_records=tuple(
            runtime_parity_comparison_record_v1_from_dict(item)
            for item in payload.get("parity_records", [])
        ),
        reason_codes=tuple(
            ResearchPromotionReasonCode(str(code)) for code in payload.get("reason_codes", [])
        ),
        review_eligible=bool(payload.get("review_eligible", False)),
        grants_execution_authority=bool(payload.get("grants_execution_authority", False)),
        updated_at_ns=int(payload.get("updated_at_ns", 0)),
        implementation_version=str(
            payload.get(
                "implementation_version",
                STRATEGY_RESEARCH_PROMOTION_REGISTRY_IMPLEMENTATION_VERSION,
            )
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


def strategy_research_promotion_transition_v1_to_dict(
    event: StrategyResearchPromotionTransitionV1,
) -> dict[str, Any]:
    return {
        "schema_version": event.schema_version,
        "event_id": event.event_id,
        "promotion_record_id": event.promotion_record_id,
        "from_state": event.from_state.value if event.from_state else None,
        "to_state": event.to_state.value,
        "effective_at_ns": event.effective_at_ns,
        "reason_codes": [code.value for code in event.reason_codes],
        "metadata": dict(event.metadata),
    }


def strategy_research_promotion_transition_v1_from_dict(
    payload: dict[str, Any],
) -> StrategyResearchPromotionTransitionV1:
    from_state_raw = payload.get("from_state")
    return StrategyResearchPromotionTransitionV1(
        event_id=str(payload["event_id"]),
        schema_version=str(payload.get("schema_version", INTELLIGENCE_SCHEMA_VERSION)),
        promotion_record_id=str(payload["promotion_record_id"]),
        from_state=(
            StrategyResearchPromotionLifecycleState(str(from_state_raw))
            if from_state_raw is not None
            else None
        ),
        to_state=StrategyResearchPromotionLifecycleState(str(payload["to_state"])),
        effective_at_ns=int(payload["effective_at_ns"]),
        reason_codes=tuple(
            ResearchPromotionReasonCode(str(code)) for code in payload.get("reason_codes", [])
        ),
        metadata=dict(payload.get("metadata") or {}),
    )


__all__ = [
    "runtime_parity_comparison_record_v1_from_dict",
    "runtime_parity_comparison_record_v1_to_dict",
    "strategy_research_evidence_bundle_v1_from_dict",
    "strategy_research_evidence_bundle_v1_to_dict",
    "strategy_research_promotion_record_v1_from_dict",
    "strategy_research_promotion_record_v1_to_dict",
    "strategy_research_promotion_transition_v1_from_dict",
    "strategy_research_promotion_transition_v1_to_dict",
]

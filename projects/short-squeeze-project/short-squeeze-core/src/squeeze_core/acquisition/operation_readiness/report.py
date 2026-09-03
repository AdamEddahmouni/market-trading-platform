"""Assemble the deterministic Batch 07 operation-readiness report from frozen evidence.

Pure, offline, outcome-blind. Consumes only frozen provenance metadata and the Batch 06
resolved semantics; never reads OHLCV, forward bars, or an outcome; never evaluates a
Phase 3A rule. Running it twice yields byte-identical output.
"""

from __future__ import annotations

from pathlib import Path

from ..ibkr_semantics.evidence import OFFICIAL_TRADES_EVIDENCE
from ..ibkr_semantics.resolver import ResolvedIbkrSemantics, resolve_ibkr_semantics
from ..identifiers import deterministic_acquisition_id
from .admissibility import AdmissibilityContext, assess_operation, context_from_resolved
from .dependencies import (
    PHASE2_OPERATION_DEPENDENCIES,
    PHASE3A_RULE_DEPENDENCIES,
)
from .evidence_inputs import (
    FROZEN_BOUNDARY,
    FROZEN_COHORT,
    boundary_id_for,
    load_detection_context_evidence,
)
from .models import (
    BAR_INTERVAL_SECONDS,
    OPERATION_READINESS_POLICY_VERSION,
    SEMANTIC_RESOLUTION_POLICY_VERSION,
    TIMESTAMP_UNCERTAINTY_POLICY,
    AdmissibilityStatus,
    CaseOperationReadiness,
    OperationAdmissibility,
    OperationKind,
    OperationReadinessReport,
    Phase3ARequestReadiness,
    ReadinessFrequencySummary,
    ReasonCode,
)
from .phase3a_readiness import assess_request_readiness, build_all_rule_records
from .timestamp_uncertainty import build_envelope

_BLOCKED = {
    AdmissibilityStatus.BLOCKED_MISSING_SEMANTICS,
    AdmissibilityStatus.BLOCKED_MISSING_EVIDENCE,
    AdmissibilityStatus.BLOCKED_ALIGNMENT,
    AdmissibilityStatus.BLOCKED_CONFLICT,
}

# Supporting/positive reason codes that describe why something is admissible; they are
# never themselves a blocker even when attached to a blocked operation's reason list.
_NON_BLOCKING_REASONS = {
    ReasonCode.MARKET_BARS_PRESENT,
    ReasonCode.FINAL_BAR_DEFINITELY_COMPLETED,
    ReasonCode.PRICE_RATIO_SPLIT_INVARIANT,
    ReasonCode.DIVIDEND_ADJUSTMENT_NOT_APPLIED,
}

_TEMPORAL_ALIGNMENT_DEP = next(
    dep for dep, _ in PHASE3A_RULE_DEPENDENCIES if dep.operation == "COMPLETED_BAR_AVAILABLE"
)


def _semantic_resolution_id(resolved: ResolvedIbkrSemantics) -> str:
    return deterministic_acquisition_id(
        {
            "result_type": "BATCH07_SEMANTIC_RESOLUTION",
            "policy_version": SEMANTIC_RESOLUTION_POLICY_VERSION,
            "price_adjustment_semantics": resolved.price_adjustment_semantics.value,
            "volume_adjustment_semantics": resolved.volume_adjustment_semantics.value,
            "timestamp_semantics": resolved.timestamp_semantics.value,
            "session_coverage": resolved.session_coverage.value,
            "volume_unit_code": resolved.volume_unit_code.value,
            "unresolved_fields": sorted(resolved.unresolved_fields),
        }
    )


def _evidence_id(case_id: str, boundary_id: str, sha256: str, byte_length: int) -> str:
    return deterministic_acquisition_id(
        {
            "result_type": "BATCH07_EVIDENCE",
            "case_id": case_id,
            "boundary_id": boundary_id,
            "artifact_sha256": sha256,
            "artifact_byte_length": byte_length,
        }
    )


def _association_id(
    case_id: str, boundary_id: str, sha256: str, byte_length: int
) -> str:
    return deterministic_acquisition_id(
        {
            "result_type": "BATCH07_ASSOCIATION",
            "case_id": case_id,
            "boundary_id": boundary_id,
            "artifact_sha256": sha256,
            "artifact_byte_length": byte_length,
            "semantic_resolution_policy_version": SEMANTIC_RESOLUTION_POLICY_VERSION,
            "operation_readiness_policy_version": OPERATION_READINESS_POLICY_VERSION,
        }
    )


def _blocking_reasons(*groups: tuple[OperationAdmissibility, ...]) -> tuple[ReasonCode, ...]:
    reasons: set[ReasonCode] = set()
    for group in groups:
        for item in group:
            if item.status in _BLOCKED:
                reasons.update(item.reason_codes)
    reasons -= _NON_BLOCKING_REASONS
    return tuple(sorted(reasons, key=lambda item: item.value))


def build_report(batch05_root: Path) -> OperationReadinessReport:
    resolved = resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE)
    semantic_resolution_id = _semantic_resolution_id(resolved)
    evidence = load_detection_context_evidence(batch05_root)

    cases: list[CaseOperationReadiness] = []
    shared_ctx: AdmissibilityContext | None = None

    for symbol, case_id in FROZEN_COHORT:
        ev = evidence[symbol]
        boundary_id = boundary_id_for(case_id, symbol)
        env = build_envelope(
            ev.coverage.observed_coverage_end, BAR_INTERVAL_SECONDS, FROZEN_BOUNDARY
        )
        ctx = context_from_resolved(
            resolved,
            market_bars_present=ev.coverage.bar_count > 0,
            final_bar_definitely_completed=env.definitely_completed_before_boundary,
            final_bar_straddles_boundary=env.straddles_boundary,
        )
        if shared_ctx is None:
            shared_ctx = ctx

        phase2 = tuple(assess_operation(dep, ctx) for dep in PHASE2_OPERATION_DEPENDENCIES)
        price_ops = tuple(
            item
            for item in phase2
            if _kind_of(item.operation) in (OperationKind.PRICE_ONLY_RATIO, OperationKind.PRICE_ONLY_ABSOLUTE_LEVEL)
        )
        volume_ops = tuple(
            item for item in phase2 if _kind_of(item.operation) is OperationKind.VOLUME_DEPENDENT
        )
        temporal = assess_operation(_TEMPORAL_ALIGNMENT_DEP, ctx)
        rule_records = build_all_rule_records(ctx)
        request_readiness = assess_request_readiness(
            has_frozen_symbol=True,
            has_frozen_boundary_as_of=True,
            has_policy_version=True,
            has_enabled_rule_ids=True,
        )
        evidence_id = _evidence_id(case_id, boundary_id, ev.csv_sha256, ev.csv_byte_length)
        association_id = _association_id(
            case_id, boundary_id, ev.csv_sha256, ev.csv_byte_length
        )

        cases.append(
            CaseOperationReadiness(
                case_id=case_id,
                symbol=symbol,
                frozen_boundary_id=boundary_id,
                detection_context_artifact_sha256=ev.csv_sha256,
                artifact_byte_length=ev.csv_byte_length,
                coverage=ev.coverage,
                bar_interval=ev.coverage.bar_interval,
                timestamp_representation="EPOCH_SECONDS_UTC",
                timestamp_interval_semantics=resolved.timestamp_semantics.value,
                timestamp_uncertainty_policy=TIMESTAMP_UNCERTAINTY_POLICY,
                price_adjustment_semantics=resolved.price_adjustment_semantics.value,
                volume_adjustment_semantics=resolved.volume_adjustment_semantics.value,
                volume_unit_semantics=resolved.volume_unit_code.value,
                session_request_policy="USE_RTH_0_EXTENDED_ELIGIBLE",
                provider_filtering_disclosure=resolved.filtered_feed_disclosure,
                final_bar_uncertainty=env,
                price_operation_readiness=price_ops,
                volume_operation_readiness=volume_ops,
                temporal_alignment_readiness=temporal,
                phase2_metric_readiness=phase2,
                phase3a_rule_dependency_readiness=rule_records,
                phase3a_request_readiness=request_readiness,
                blocking_reason_codes=_blocking_reasons(price_ops, volume_ops, (temporal,)),
                supporting_evidence_ids=(evidence_id, boundary_id),
                supporting_semantic_resolution_ids=(semantic_resolution_id,),
                association_id=association_id,
            )
        )

    assert shared_ctx is not None
    rule_matrix = build_all_rule_records(shared_ctx)
    summaries = _build_summaries(tuple(cases), rule_matrix)

    return OperationReadinessReport(
        # Per-case boundary ids differ (they bind the case attempt id); this is the
        # shared boundary instant descriptor for the cohort.
        frozen_boundary_id="SHARED_BOUNDARY_INSTANT_2026-07-18T13:37:55.017661Z",
        operation_dependency_matrix=PHASE2_OPERATION_DEPENDENCIES,
        phase3a_rule_dependency_matrix=rule_matrix,
        cases=tuple(cases),
        summaries=summaries,
    )


def _kind_of(operation: str) -> OperationKind:
    for dep in PHASE2_OPERATION_DEPENDENCIES:
        if dep.operation == operation:
            return dep.kind
    raise KeyError(operation)


def _counts(values: list[str]) -> tuple[tuple[str, int], ...]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return tuple(sorted(counts.items(), key=lambda item: item[0]))


def _build_summaries(
    cases: tuple[CaseOperationReadiness, ...], rule_matrix
) -> tuple[ReadinessFrequencySummary, ...]:
    request_counts = _counts([c.phase3a_request_readiness.value for c in cases])
    rule_status_counts = _counts([r.admissibility_status.value for r in rule_matrix])
    metric_status_counts = _counts(
        [m.status.value for c in cases for m in c.phase2_metric_readiness]
    )
    blocker_counts = _counts(
        [code.value for c in cases for code in c.blocking_reason_codes]
    )
    alignment_counts = _counts(
        [
            c.temporal_alignment_readiness.status.value
            for c in cases
        ]
    )
    n_cases = len(cases)
    return (
        ReadinessFrequencySummary(
            label="phase3a_request_readiness_over_cases",
            denominator=n_cases,
            counts=request_counts,
        ),
        ReadinessFrequencySummary(
            label="phase3a_rule_admissibility_over_25_rules",
            denominator=len(rule_matrix),
            counts=rule_status_counts,
        ),
        ReadinessFrequencySummary(
            label="phase2_metric_admissibility_over_case_operation_pairs",
            denominator=sum(len(c.phase2_metric_readiness) for c in cases),
            counts=metric_status_counts,
        ),
        ReadinessFrequencySummary(
            label="blocking_reason_frequency_over_case_blocker_pairs",
            denominator=sum(len(c.blocking_reason_codes) for c in cases),
            counts=blocker_counts,
        ),
        ReadinessFrequencySummary(
            label="temporal_alignment_over_cases",
            denominator=n_cases,
            counts=alignment_counts,
        ),
    )


__all__ = ["build_report"]

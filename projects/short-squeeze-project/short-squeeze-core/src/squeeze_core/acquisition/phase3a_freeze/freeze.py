"""Orchestrate the Batch 08 freeze in the mandated order, for all 13 frozen cases.

Per case, in order: verify frozen identity and boundary; bind the frozen admissibility
policy; freeze the evidence association; serialize and hash the Phase 3A request; run the
existing evaluator; serialize and hash the result; run the leakage audit; emit a sanitized
summary. No outcome is accessed at any point, and every case stays represented even if its
own construction or evaluation fails.

Pure and offline. Running twice over unchanged inputs yields byte-identical output.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from squeeze_core.contracts import Observation
from squeeze_core.evaluation.models import (
    CandidateEvaluationPolicy,
    CandidateEvaluationResult,
    RuleEvaluationRequest,
)
from squeeze_core.evaluation.policies import DEFAULT_POLICY_PATH, load_policy
from squeeze_core.metrics.models import MetricResult

from ..ibkr_semantics.evidence import OFFICIAL_TRADES_EVIDENCE
from ..ibkr_semantics.resolver import resolve_ibkr_semantics
from ..cohort_registry import CohortCase, resolve_cohort_cases
from ..operation_readiness.evidence_inputs import (
    DETECTION_CONTEXT_REQUEST,
    FORWARD_REQUEST,
    boundary_id_for,
    forward_artifact_identity,
    load_detection_context_evidence,
)
from ..operation_readiness.models import (
    CaseOperationReadiness,
    Phase3ARuleDependencyRecord,
)
from ..operation_readiness.report import build_report
from ..operation_readiness.timestamp_uncertainty import build_envelope
from .evidence_adapter import (
    BAR_INTERVAL,
    BAR_INTERVAL_SECONDS,
    DetectionContextBars,
    EvidenceAccessLog,
    load_detection_context_bars,
)
from .leakage import audit_case, build_audit_request, ordering_holds
from .metric_adapter import InsufficientAdmissibleBarsError, build_percentage_return
from .models import (
    FREEZE_POLICY_VERSION,
    GLOBAL_PREFLIGHT_VERDICT,
    PHASE3A_EVALUATION_VERSION,
    PHASE3A_POLICY_VERSION,
    CaseFreezeRecord,
    EvidenceAssociation,
    FreezeStatus,
    ObservationSupplyPolicy,
    ReceiptModelingPolicy,
    TemporalSelection,
    TimestampInterpretation,
)
from .readiness_adapter import build_bundle, build_readiness_records
from .request_builder import build_request
from .result_runner import blocking_reasons, rule_outcome_records, run_evaluation
from .serialization import (
    artifact_ref,
    freeze_id,
    request_identity,
    result_identity,
    serialize_phase3a_request,
    serialize_phase3a_result,
)

#: Frozen: the timestamp reading used to serialize bar boundaries (value-invariant, see
#: docs/batch-08-phase3a-request-result-freeze-plan.md Section 9.1).
FROZEN_INTERPRETATION = TimestampInterpretation.LABEL_IS_INTERVAL_START

#: Frozen: which admissible bars the request itself carries (see ObservationSupplyPolicy).
FROZEN_SUPPLY_POLICY = ObservationSupplyPolicy.ADMISSIBLE_METRIC_BOUNDARY_BARS

#: Frozen: the Batch 01 discovery manifest the leakage audit contrasts against.
DISCOVERY_MANIFEST_ID = "BATCH01_DISCOVERY_MANIFEST"


@dataclass(frozen=True)
class CaseFreezeOutputs:
    """Everything one frozen case produced, private artifacts included."""

    record: CaseFreezeRecord
    request: RuleEvaluationRequest | None
    request_bytes: bytes | None
    evaluation: CandidateEvaluationResult | None
    result_bytes: bytes | None
    metric: MetricResult | None
    association: EvidenceAssociation
    temporal: TemporalSelection


def load_phase3a_policy(path: Path | None = None) -> CandidateEvaluationPolicy:
    """Load the committed Phase 3A policy and verify its frozen version strings."""
    policy = load_policy(path or DEFAULT_POLICY_PATH)
    if policy.policy_version != PHASE3A_POLICY_VERSION:
        raise ValueError(f"unexpected Phase 3A policy version: {policy.policy_version}")
    if policy.evaluation_version != PHASE3A_EVALUATION_VERSION:
        raise ValueError(
            f"unexpected Phase 3A evaluation version: {policy.evaluation_version}"
        )
    return policy


def batch07_readiness(
    batch05_root: Path,
    *,
    cohort_track: str = "frozen",
) -> dict[str, CaseOperationReadiness]:
    """Rebuild the authoritative Batch 07 readiness report and index it by case id.

    Batch 07 is the authoritative admissibility input, so its own code path produces the
    record ids Batch 08 cites. Nothing is recomputed independently and no verdict is
    altered; ``build_report`` is pure, offline, and reads provenance metadata only.
    """
    from ..operation_readiness.report import build_report

    report = build_report(batch05_root, cohort_track=cohort_track)
    if report.global_preflight_verdict != GLOBAL_PREFLIGHT_VERDICT:
        raise ValueError("the Batch 04 global preflight verdict is not PREFLIGHT_REJECTED")
    if not report.global_preflight_unchanged:
        raise ValueError("the Batch 04 global preflight is not marked unchanged")
    return {case.case_id: case for case in report.cases}


def rule_records_for(case: CaseOperationReadiness) -> dict[str, Phase3ARuleDependencyRecord]:
    """The Batch 07 25-rule dependency matrix for one case, unmodified."""
    return {record.rule_id: record for record in case.phase3a_rule_dependency_readiness}


def _retrieval_completed_at(batch05_root: Path, symbol: str) -> datetime:
    """The Batch 05 retrieval completion time, used only by the sensitivity policy."""
    import json

    rows = json.loads(
        (batch05_root / "requests" / "request-manifest.json").read_text(encoding="utf-8")
    )
    for row in rows:
        if row["symbol"] == symbol and row["request_name"] == DETECTION_CONTEXT_REQUEST:
            raw = row.get("retrieval_completed_at") or row.get("last_timestamp_utc")
            if raw is None:
                raise KeyError(f"no retrieval timestamp for {symbol}")
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(UTC)
    raise KeyError(f"no detection-context request manifest row for {symbol}")


def _temporal_selection(
    bars: DetectionContextBars,
    *,
    boundary: datetime,
    supply_policy: ObservationSupplyPolicy,
    supplied_count: int,
) -> TemporalSelection:
    labels = bars.labels
    last = labels.included[-1] if labels.included else boundary
    envelope = build_envelope(last, BAR_INTERVAL_SECONDS, boundary)
    return TemporalSelection(
        timestamp_uncertainty_policy="bidirectional_1min_envelope.v1",
        timestamp_interpretation=bars.interpretation,
        observation_supply_policy=supply_policy,
        bar_interval=BAR_INTERVAL.value,
        bar_interval_seconds=BAR_INTERVAL_SECONDS,
        boundary=boundary,
        first_included_label=labels.included[0] if labels.included else boundary,
        last_included_label=last,
        last_included_latest_possible_completion=envelope.latest_possible_completion,
        included_bar_count=len(labels.included),
        supplied_observation_count=supplied_count,
        metric_window_bar_count=len(labels.included),
        excluded_straddling_bar_count=labels.straddling_count,
        excluded_post_boundary_bar_count=labels.post_boundary_count,
    )


def select_supplied_observations(
    bars: DetectionContextBars,
    metric: MetricResult | None,
    supply_policy: ObservationSupplyPolicy,
) -> tuple[Observation, ...]:
    """The observations attached to the request, per the declared supply policy.

    Under ``ADMISSIBLE_METRIC_BOUNDARY_BARS`` these are exactly the observations the
    canonical metric consumed -- taken from the metric's own ``input_observation_ids``, so
    the request carries precisely the evidence the admissible operation used and nothing
    is hand-picked here.
    """
    if supply_policy is ObservationSupplyPolicy.ALL_DEFINITELY_COMPLETED_BARS:
        return bars.observations
    if metric is None:
        return bars.observations
    wanted = set(metric.input_observation_ids)
    return tuple(item for item in bars.observations if item.observation_id in wanted)


def freeze_case(
    *,
    symbol: str,
    case_id: str,
    boundary: datetime,
    batch05_root: Path,
    policy: CandidateEvaluationPolicy,
    batch07_case: CaseOperationReadiness,
    receipt_policy: ReceiptModelingPolicy = (
        ReceiptModelingPolicy.PROVIDER_AVAILABILITY_AS_RECEIPT
    ),
    interpretation: TimestampInterpretation = FROZEN_INTERPRETATION,
    supply_policy: ObservationSupplyPolicy = FROZEN_SUPPLY_POLICY,
    access_log: EvidenceAccessLog | None = None,
) -> CaseFreezeOutputs:
    """Freeze one case in the mandated order."""
    log = access_log if access_log is not None else EvidenceAccessLog()
    readiness_by_rule = rule_records_for(batch07_case)

    # (1)-(3) frozen identity and boundary, recomputed rather than trusted.
    boundary_id = boundary_id_for(case_id, symbol)
    if batch07_case.case_id != case_id or batch07_case.symbol != symbol:
        raise ValueError(f"Batch 07 readiness record does not match case {case_id}")
    if batch07_case.frozen_boundary_id != boundary_id:
        raise ValueError(f"frozen boundary id disagrees with Batch 07 for {case_id}")
    coverage = load_detection_context_evidence(batch05_root)[symbol]
    forward = forward_artifact_identity(batch05_root)[symbol]
    if batch07_case.detection_context_artifact_sha256 != coverage.csv_sha256:
        raise ValueError(f"Batch 07 artifact hash disagrees with the manifest for {symbol}")

    # (4)-(5) admissibility policy bound, evidence association frozen.
    association = EvidenceAssociation(
        case_id=case_id,
        symbol=symbol,
        boundary_id=boundary_id,
        boundary_time=boundary,
        detection_context_artifact_name=f"{symbol}-detection-context.csv",
        detection_context_artifact_sha256=coverage.csv_sha256,
        detection_context_artifact_byte_length=coverage.csv_byte_length,
        forward_artifact_name=f"{symbol}-frozen-forward-24h.csv",
        forward_artifact_sha256=forward[0],
        forward_artifact_byte_length=forward[1],
        forward_artifact_status=GLOBAL_PREFLIGHT_VERDICT,
        forward_ohlcv_accessed=False,
        global_preflight_status=GLOBAL_PREFLIGHT_VERDICT,
        batch07_readiness_record_id=str(batch07_case.deterministic_id),
        batch07_association_id=str(batch07_case.association_id),
        batch07_request_readiness=batch07_case.phase3a_request_readiness.value,
        batch07_temporal_alignment_status=(
            batch07_case.temporal_alignment_readiness.status.value
        ),
        price_adjustment_semantics=batch07_case.price_adjustment_semantics,
        observed_coverage_start=coverage.coverage.observed_coverage_start,
        observed_coverage_end=coverage.coverage.observed_coverage_end,
        observed_bar_count=coverage.coverage.bar_count,
    )

    bars = load_detection_context_bars(
        batch05_root / "raw" / association.detection_context_artifact_name,
        symbol=symbol,
        boundary=boundary,
        retrieval_completed_at=_retrieval_completed_at(batch05_root, symbol),
        receipt_policy=receipt_policy,
        interpretation=interpretation,
        log=log,
    )
    if bars.artifact_sha256 != coverage.csv_sha256:
        raise ValueError(f"detection-context artifact hash changed for {symbol}")

    # The metric is computed over the FULL admissible window (the Phase 2 metric path is
    # linear), independently of how many observations the request itself carries.
    try:
        metric: MetricResult | None = build_percentage_return(
            bars, as_of=boundary, interpretation=interpretation
        )
    except InsufficientAdmissibleBarsError:
        # Preserve the request; the rule resolves through canonical missingness.
        metric = None

    supplied = select_supplied_observations(bars, metric, supply_policy)
    temporal = _temporal_selection(
        bars,
        boundary=boundary,
        supply_policy=supply_policy,
        supplied_count=len(supplied),
    )

    bundle = build_bundle(symbol, supplied, boundary)
    readiness = build_readiness_records(bundle, policy, metric)

    # (6)-(7) request serialized, frozen, hashed.
    request = build_request(
        symbol=symbol,
        as_of=boundary,
        policy=policy,
        observations=supplied,
        metric=metric,
        readiness=readiness,
    )
    request_bytes = serialize_phase3a_request(request)
    metric_ids = () if metric is None else (str(metric.deterministic_id),)
    readiness_ids = tuple(str(item.deterministic_id) for item in readiness)
    admissible_evidence_ids = tuple(str(item.observation_id) for item in supplied)
    request_id = freeze_id(
        request_identity(
            association=association,
            temporal=temporal,
            receipt_policy=receipt_policy,
            phase3a_policy_version=policy.policy_version,
            phase3a_evaluation_version=policy.evaluation_version,
            enabled_rule_ids=policy.enabled_rule_ids,
            admissible_evidence_ids=admissible_evidence_ids,
            metric_ids=metric_ids,
            readiness_ids=readiness_ids,
        )
    )

    # (8)-(10) existing evaluator executed; result serialized, frozen, hashed.
    evaluation = run_evaluation(request, policy)
    result_bytes = serialize_phase3a_result(evaluation)
    outcomes = rule_outcome_records(evaluation, readiness_by_rule)
    result_id = freeze_id(
        result_identity(
            request_id=request_id,
            candidate_evaluation_id=str(evaluation.deterministic_id),
            rule_outcomes=outcomes,
        )
    )

    # (11) leakage audit.
    audit_request = build_audit_request(
        case_id=case_id,
        boundary=boundary,
        discovery_manifest_id=DISCOVERY_MANIFEST_ID,
    )
    if not ordering_holds(audit_request):
        raise ValueError(f"freeze ordering violated for {case_id}")
    audit = audit_case(
        case_id=case_id,
        boundary=boundary,
        discovery_manifest_id=DISCOVERY_MANIFEST_ID,
    )

    blocked_dependencies = tuple(
        rule_id
        for rule_id, record in readiness_by_rule.items()
        if record.admissibility_status.value.startswith("BLOCKED")
    )
    case_blockers = {
        code for item in outcomes for code in item.blocking_reason_codes
    }

    record = CaseFreezeRecord(
        receipt_modeling_policy=receipt_policy,
        freeze_status=FreezeStatus.REQUEST_AND_RESULT_FROZEN,
        case_id=case_id,
        symbol=symbol,
        boundary_id=boundary_id,
        boundary_time=boundary,
        batch07_readiness_record_id=association.batch07_readiness_record_id,
        detection_context_artifact_name=association.detection_context_artifact_name,
        detection_context_artifact_sha256=association.detection_context_artifact_sha256,
        detection_context_artifact_byte_length=(
            association.detection_context_artifact_byte_length
        ),
        global_preflight_status=GLOBAL_PREFLIGHT_VERDICT,
        temporal_selection=temporal,
        evidence_association_id=str(association.deterministic_id),
        admissible_evidence_ids=admissible_evidence_ids,
        blocked_evidence_dependencies=blocked_dependencies,
        metric_ids=metric_ids,
        readiness_ids=readiness_ids,
        phase3a_request_id=request_id,
        phase3a_request_artifact=artifact_ref("PHASE3A_REQUEST", request_bytes),
        phase3a_result_id=result_id,
        phase3a_result_artifact=artifact_ref("PHASE3A_RESULT", result_bytes),
        candidate_evaluation_id=str(evaluation.deterministic_id),
        rule_outcomes=outcomes,
        leakage_audit_status=(
            "LEAKAGE_AUDIT_PASSED" if audit.passed else "LEAKAGE_AUDIT_FAILED"
        ),
        leakage_audit_diagnostic_codes=audit.diagnostic_codes,
        blocking_reason_codes=tuple(case_blockers),
        outcome_accessed=log.outcome_accessed,
        forward_ohlcv_accessed=log.forward_ohlcv_accessed,
        phase3b_published=False,
        phase3e_started=False,
    )
    return CaseFreezeOutputs(
        record=record,
        request=request,
        request_bytes=request_bytes,
        evaluation=evaluation,
        result_bytes=result_bytes,
        metric=metric,
        association=association,
        temporal=temporal,
    )


def freeze_cohort(
    batch05_root: Path,
    *,
    cohort_track: str = "frozen",
    cohort_cases: tuple[CohortCase, ...] | None = None,
    receipt_policy: ReceiptModelingPolicy = (
        ReceiptModelingPolicy.PROVIDER_AVAILABILITY_AS_RECEIPT
    ),
    interpretation: TimestampInterpretation = FROZEN_INTERPRETATION,
    supply_policy: ObservationSupplyPolicy = FROZEN_SUPPLY_POLICY,
    policy_path: Path | None = None,
) -> tuple[CaseFreezeOutputs, ...]:
    """Freeze all cases in the selected cohort track."""
    policy = load_phase3a_policy(policy_path)
    cases = cohort_cases or resolve_cohort_cases(cohort_track)
    batch07 = batch07_readiness(batch05_root, cohort_track=cohort_track)
    log = EvidenceAccessLog()
    return tuple(
        freeze_case(
            symbol=case.symbol,
            case_id=case.case_id,
            boundary=case.boundary,
            batch05_root=batch05_root,
            policy=policy,
            batch07_case=batch07[case.case_id],
            receipt_policy=receipt_policy,
            interpretation=interpretation,
            supply_policy=supply_policy,
            access_log=log,
        )
        for case in cases
    )


__all__ = [
    "DISCOVERY_MANIFEST_ID",
    "FREEZE_POLICY_VERSION",
    "FORWARD_REQUEST",
    "FROZEN_INTERPRETATION",
    "FROZEN_SUPPLY_POLICY",
    "CaseFreezeOutputs",
    "batch07_readiness",
    "freeze_case",
    "freeze_cohort",
    "load_phase3a_policy",
    "rule_records_for",
    "select_supplied_observations",
]

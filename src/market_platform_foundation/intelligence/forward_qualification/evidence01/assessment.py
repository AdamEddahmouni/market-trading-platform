"""EVIDENCE-01 forward evidence qualification assessment engine."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo

from ...contracts.common import Direction, OutcomeResolutionStatus
from ...evaluation.provenance import extract_probabilities, predicted_direction_from_forecast
from ...evaluation.types import ProbabilityView
from ...persistence.repository import IntelligenceRepository
from ..types import EvidenceClass, ForwardIntegrityStatus
from .continuity import maximum_qualifying_gap_ns
from .identity import (
    derive_forward_evidence_assessment_id,
    derive_forward_evidence_report_id,
    derive_source_evidence_fingerprint,
)
from .types import (
    FORWARD_EVIDENCE_QUALIFICATION_IMPLEMENTATION_VERSION,
    FORWARD_EVIDENCE_QUALIFICATION_SCHEMA_VERSION,
    ForwardEvidenceDisposition,
    ForwardEvidenceQualificationAssessmentV1,
    ForwardEvidenceQualificationPolicyV1,
    ForwardEvidenceQualificationReportV1,
    ForwardObservationInputV1,
    ForwardObservationSummaryV1,
    ObservationExclusionReason,
    SettlementRateState,
)

_ET = ZoneInfo("America/New_York")
BUILD26_HISTORICAL_DISPOSITION = "INSUFFICIENT_FORWARD_EVIDENCE"
BUILD26_HISTORICAL_REPORT_REF = (
    "FQREP-ba32338a3b7b5c69f8ce52edfef337995141665e45fe446606218292656b31e5"
)


def trading_day_key(decision_time_ns: int) -> str:
    seconds = decision_time_ns / 1_000_000_000
    dt = datetime.fromtimestamp(seconds, tz=_ET)
    return dt.date().isoformat()


def _session_key(observation: ForwardObservationInputV1) -> str:
    if observation.session_id:
        return observation.session_id
    return trading_day_key(observation.receipt.decision_time_ns)


def _is_settled(
    repository: IntelligenceRepository,
    receipt_id_observation: ForwardObservationInputV1,
    *,
    settlement_cutoff_ns: int,
) -> bool:
    receipt = receipt_id_observation.receipt
    outcomes = repository.get_outcomes_by_forecast(receipt.forecast_id)
    matched = [
        outcome
        for outcome in outcomes
        if outcome.metadata.get("ledger_entry_id") == receipt.ledger_entry_id
    ]
    if not matched:
        return False
    outcome = matched[0]
    if outcome.resolution_status not in {OutcomeResolutionStatus.SETTLED, OutcomeResolutionStatus.PARTIAL}:
        return False
    label_time = outcome.metadata.get("label_available_time_ns")
    if label_time is not None and int(label_time) > settlement_cutoff_ns:
        return False
    return receipt.target_time_ns <= settlement_cutoff_ns


def _direction_bucket(observation: ForwardObservationInputV1) -> str:
    forecast = observation.forecast
    if forecast is None:
        return "ABSTAIN"
    raw, _, operational = extract_probabilities(forecast)
    probability = operational if operational is not None else raw
    if probability is None:
        return "ABSTAIN"
    direction = predicted_direction_from_forecast(forecast, probability)
    if direction == Direction.LONG:
        return "UP"
    if direction == Direction.SHORT:
        return "DOWN"
    return "ABSTAIN"


def _classify_observation(
    observation: ForwardObservationInputV1,
    *,
    observation_cutoff_ns: int,
    settlement_cutoff_ns: int,
    required_quality_states: tuple[str, ...],
    seen_forecast_ids: set[str],
) -> tuple[bool, ObservationExclusionReason | None]:
    receipt = observation.receipt
    if receipt.forecast_id in seen_forecast_ids:
        return False, ObservationExclusionReason.DUPLICATE_FORECAST
    if receipt.evidence_class != EvidenceClass.ACTUAL_FORWARD:
        return False, ObservationExclusionReason.NOT_ACTUAL_FORWARD
    if receipt.forward_integrity_status != ForwardIntegrityStatus.VALID:
        return False, ObservationExclusionReason.INTEGRITY_INVALID
    if receipt.decision_time_ns > observation_cutoff_ns:
        return False, ObservationExclusionReason.AFTER_OBSERVATION_CUTOFF
    if not observation.provider_connected:
        return False, ObservationExclusionReason.PROVIDER_DISCONNECTED
    quality = observation.quality_state or "GOOD"
    if quality not in required_quality_states:
        return False, ObservationExclusionReason.QUALITY_INELIGIBLE
    if observation.ledger_entry is not None:
        anchor = observation.ledger_entry.anchor_observation
        event_time_ns = anchor.get("event_time_ns")
        available_time_ns = anchor.get("available_time_ns")
        if event_time_ns is not None and int(event_time_ns) > receipt.decision_time_ns:
            return False, ObservationExclusionReason.FUTURE_EVENT_TIME
        if available_time_ns is not None and int(available_time_ns) > receipt.decision_time_ns:
            return False, ObservationExclusionReason.FUTURE_AVAILABLE_TIME
    if receipt.target_time_ns > settlement_cutoff_ns:
        return False, ObservationExclusionReason.INSIDE_UNRESOLVED_HORIZON
    return True, None


def build_forward_observation_summary(
    *,
    policy: ForwardEvidenceQualificationPolicyV1,
    observations: tuple[ForwardObservationInputV1, ...],
    repository: IntelligenceRepository,
    observation_cutoff_ns: int,
    settlement_cutoff_ns: int,
) -> ForwardObservationSummaryV1:
    exclusions: dict[str, int] = {}
    seen_forecast_ids: set[str] = set()
    eligible: list[ForwardObservationInputV1] = []
    raw_count = len(observations)

    for observation in observations:
        eligible_flag, reason = _classify_observation(
            observation,
            observation_cutoff_ns=observation_cutoff_ns,
            settlement_cutoff_ns=settlement_cutoff_ns,
            required_quality_states=policy.required_quality_states,
            seen_forecast_ids=seen_forecast_ids,
        )
        if eligible_flag:
            seen_forecast_ids.add(observation.receipt.forecast_id)
            eligible.append(observation)
        elif reason is not None:
            key = reason.value
            exclusions[key] = exclusions.get(key, 0) + 1

    decision_times = sorted(item.receipt.decision_time_ns for item in eligible)
    first_decision = decision_times[0] if decision_times else None
    last_decision = decision_times[-1] if decision_times else None
    elapsed = (last_decision - first_decision) if first_decision is not None and last_decision is not None else 0

    trading_days = {trading_day_key(item.receipt.decision_time_ns) for item in eligible}
    sessions = {_session_key(item) for item in eligible}

    settled = 0
    unsettled = 0
    abstentions = 0
    up_support = 0
    down_support = 0
    for item in eligible:
        bucket = _direction_bucket(item)
        if bucket == "UP":
            up_support += 1
        elif bucket == "DOWN":
            down_support += 1
        else:
            abstentions += 1
        if _is_settled(repository, item, settlement_cutoff_ns=settlement_cutoff_ns):
            settled += 1
        else:
            unsettled += 1

    max_gap = maximum_qualifying_gap_ns(decision_times)

    settlement_rate: float | None
    if eligible:
        settlement_rate = settled / len(eligible)
        settlement_rate_state = SettlementRateState.DEFINED
    else:
        settlement_rate = None
        settlement_rate_state = SettlementRateState.NOT_EVALUABLE
    excluded_total = raw_count - len(eligible)

    return ForwardObservationSummaryV1(
        observation_cutoff_ns=observation_cutoff_ns,
        settlement_cutoff_ns=settlement_cutoff_ns,
        first_eligible_decision_ns=first_decision,
        last_eligible_decision_ns=last_decision,
        elapsed_qualifying_duration_ns=elapsed,
        distinct_trading_days=len(trading_days),
        distinct_sessions=len(sessions),
        raw_observations=raw_count,
        eligible_predictions=len(eligible),
        settled_predictions=settled,
        unsettled_predictions=unsettled,
        abstentions=abstentions,
        excluded_observations=excluded_total,
        exclusions_by_reason=exclusions,
        up_support=up_support,
        down_support=down_support,
        settlement_rate=settlement_rate,
        settlement_rate_state=settlement_rate_state,
        maximum_observation_gap_ns=max_gap,
        provider_disconnected_exclusions=exclusions.get(
            ObservationExclusionReason.PROVIDER_DISCONNECTED.value, 0
        ),
    )


def _remaining_requirements(
    policy: ForwardEvidenceQualificationPolicyV1,
    summary: ForwardObservationSummaryV1,
) -> tuple[str, ...]:
    remaining: list[str] = []
    if summary.eligible_predictions < policy.minimum_eligible_predictions:
        deficit = policy.minimum_eligible_predictions - summary.eligible_predictions
        remaining.append(f"{deficit} additional eligible predictions")
    if summary.settled_predictions < policy.minimum_settled_predictions:
        deficit = policy.minimum_settled_predictions - summary.settled_predictions
        remaining.append(f"{deficit} additional settled eligible predictions")
    if summary.settlement_rate_state == SettlementRateState.DEFINED and summary.settlement_rate is not None:
        if summary.settlement_rate < policy.minimum_settlement_rate:
            pct = int(policy.minimum_settlement_rate * 100)
            remaining.append(f"settlement rate below {pct}%")
    elif summary.eligible_predictions == 0:
        pct = int(policy.minimum_settlement_rate * 100)
        remaining.append(f"settlement rate threshold ({pct}%) not yet evaluable")
    if summary.elapsed_qualifying_duration_ns < policy.minimum_duration_ns:
        deficit_ns = policy.minimum_duration_ns - summary.elapsed_qualifying_duration_ns
        deficit_days = max(1, int(deficit_ns / (24 * 60 * 60 * 1_000_000_000)))
        remaining.append(f"{deficit_days} additional qualifying calendar days of span")
    if summary.distinct_trading_days < policy.minimum_distinct_trading_days:
        deficit = policy.minimum_distinct_trading_days - summary.distinct_trading_days
        remaining.append(f"{deficit} additional qualifying trading days")
    if summary.distinct_sessions < policy.minimum_distinct_sessions:
        deficit = policy.minimum_distinct_sessions - summary.distinct_sessions
        remaining.append(f"{deficit} additional qualifying observation sessions")
    if summary.maximum_observation_gap_ns > policy.maximum_admissible_gap_ns:
        remaining.append("provider/runtime continuity gap exceeds maximum admissible gap")
    return tuple(remaining)


def _derive_disposition(
    policy: ForwardEvidenceQualificationPolicyV1,
    summary: ForwardObservationSummaryV1,
) -> tuple[ForwardEvidenceDisposition, tuple[str, ...], tuple[str, ...], bool]:
    limitations: list[str] = []
    remaining = _remaining_requirements(policy, summary)

    invalid_count = summary.exclusions_by_reason.get(
        ObservationExclusionReason.INTEGRITY_INVALID.value, 0
    )
    if invalid_count > 0 and summary.eligible_predictions == 0:
        return (
            ForwardEvidenceDisposition.INVALID_EVIDENCE,
            ("INTEGRITY_FAILURE",),
            tuple(limitations),
            False,
        )

    quality_excluded = summary.excluded_observations - summary.provider_disconnected_exclusions
    if summary.raw_observations > 0 and summary.eligible_predictions == 0:
        if summary.exclusions_by_reason.get(ObservationExclusionReason.QUALITY_INELIGIBLE.value, 0) > 0:
            return (
                ForwardEvidenceDisposition.DATA_QUALITY_INSUFFICIENT,
                ("QUALITY_INELIGIBLE",),
                tuple(limitations),
                False,
            )

    settlement_rate_ok = (
        summary.settlement_rate_state == SettlementRateState.DEFINED
        and summary.settlement_rate is not None
        and summary.settlement_rate >= policy.minimum_settlement_rate
    )
    sufficiency_gates = (
        summary.eligible_predictions >= policy.minimum_eligible_predictions,
        summary.settled_predictions >= policy.minimum_settled_predictions,
        settlement_rate_ok,
        summary.elapsed_qualifying_duration_ns >= policy.minimum_duration_ns,
        summary.distinct_trading_days >= policy.minimum_distinct_trading_days,
        summary.distinct_sessions >= policy.minimum_distinct_sessions,
        summary.maximum_observation_gap_ns <= policy.maximum_admissible_gap_ns,
    )
    evidence_sufficient = all(sufficiency_gates)

    if not evidence_sufficient:
        if (
            summary.eligible_predictions >= policy.minimum_eligible_predictions
            and summary.settled_predictions < policy.minimum_settled_predictions
        ) or (
            summary.settlement_rate_state == SettlementRateState.DEFINED
            and summary.settlement_rate is not None
            and summary.settlement_rate < policy.minimum_settlement_rate
            and summary.eligible_predictions > 0
        ):
            return (
                ForwardEvidenceDisposition.INCOMPLETE_SETTLEMENT,
                ("SETTLEMENT_INSUFFICIENT",),
                tuple(limitations),
                False,
            )
        return (
            ForwardEvidenceDisposition.INSUFFICIENT_FORWARD_EVIDENCE,
            ("EVIDENCE_SUFFICIENCY_NOT_MET",),
            tuple(limitations),
            False,
        )

    class_support_ok = (
        summary.up_support >= policy.minimum_class_support
        and summary.down_support >= policy.minimum_class_support
    )
    if not class_support_ok:
        limitations.append("INSUFFICIENT_CLASS_SUPPORT")
        return (
            ForwardEvidenceDisposition.QUALIFIED_WITH_LIMITATIONS,
            ("CLASS_SUPPORT_LIMITATION",),
            tuple(limitations),
            True,
        )

    return (
        ForwardEvidenceDisposition.QUALIFIED,
        ("EVIDENCE_SUFFICIENCY_MET",),
        tuple(limitations),
        True,
    )


def assess_forward_evidence_qualification(
    *,
    policy: ForwardEvidenceQualificationPolicyV1,
    observations: tuple[ForwardObservationInputV1, ...],
    repository: IntelligenceRepository,
    observation_cutoff_ns: int,
    settlement_cutoff_ns: int,
) -> ForwardEvidenceQualificationAssessmentV1:
    summary = build_forward_observation_summary(
        policy=policy,
        observations=observations,
        repository=repository,
        observation_cutoff_ns=observation_cutoff_ns,
        settlement_cutoff_ns=settlement_cutoff_ns,
    )
    receipt_ids = tuple(
        sorted(
            item.receipt.receipt_id
            for item in observations
            if item.receipt.decision_time_ns <= observation_cutoff_ns
        )
    )
    source_fingerprint = derive_source_evidence_fingerprint(
        receipt_ids=receipt_ids,
        observation_cutoff_ns=observation_cutoff_ns,
        settlement_cutoff_ns=settlement_cutoff_ns,
    )
    disposition, reason_codes, limitations, evidence_sufficient = _derive_disposition(policy, summary)
    remaining = _remaining_requirements(policy, summary)
    assessment_id = derive_forward_evidence_assessment_id(
        policy_id=policy.policy_id,
        source_evidence_fingerprint=source_fingerprint,
        observation_cutoff_ns=observation_cutoff_ns,
        settlement_cutoff_ns=settlement_cutoff_ns,
        implementation_version=FORWARD_EVIDENCE_QUALIFICATION_IMPLEMENTATION_VERSION,
    )
    return ForwardEvidenceQualificationAssessmentV1(
        assessment_id=assessment_id,
        schema_version=FORWARD_EVIDENCE_QUALIFICATION_SCHEMA_VERSION,
        policy_ref=policy.policy_id,
        observation_cutoff_ns=observation_cutoff_ns,
        settlement_cutoff_ns=settlement_cutoff_ns,
        source_evidence_fingerprint=source_fingerprint,
        observation_summary=summary,
        evidence_sufficiency_passed=evidence_sufficient,
        performance_evaluated=False,
        qualification_disposition=disposition,
        disposition_reason_codes=reason_codes,
        limitations=tuple(limitations),
        remaining_requirements=remaining,
        implementation_version=FORWARD_EVIDENCE_QUALIFICATION_IMPLEMENTATION_VERSION,
        metadata={"mechanism": "EVIDENCE-01"},
    )


def build_forward_evidence_qualification_report(
    *,
    policy: ForwardEvidenceQualificationPolicyV1,
    assessment: ForwardEvidenceQualificationAssessmentV1,
    build26_historical_disposition: str = BUILD26_HISTORICAL_DISPOSITION,
    build26_historical_report_ref: str = BUILD26_HISTORICAL_REPORT_REF,
) -> ForwardEvidenceQualificationReportV1:
    if assessment.qualification_disposition == ForwardEvidenceDisposition.QUALIFIED:
        limitation_status = "CLOSED"
    elif assessment.evidence_sufficiency_passed:
        limitation_status = "PARTIALLY_MATURED"
    else:
        limitation_status = "STILL_OPEN"

    report_id = derive_forward_evidence_report_id(
        policy_id=policy.policy_id,
        assessment_id=assessment.assessment_id,
        build26_historical_report_ref=build26_historical_report_ref,
        implementation_version=FORWARD_EVIDENCE_QUALIFICATION_IMPLEMENTATION_VERSION,
    )
    return ForwardEvidenceQualificationReportV1(
        report_id=report_id,
        schema_version=FORWARD_EVIDENCE_QUALIFICATION_SCHEMA_VERSION,
        policy_ref=policy.policy_id,
        assessment_ref=assessment.assessment_id,
        build26_historical_disposition=build26_historical_disposition,
        build26_historical_report_ref=build26_historical_report_ref,
        evidence01_disposition=assessment.qualification_disposition,
        limitation_status=limitation_status,
        observation_summary=assessment.observation_summary,
        remaining_requirements=assessment.remaining_requirements,
        implementation_version=FORWARD_EVIDENCE_QUALIFICATION_IMPLEMENTATION_VERSION,
        metadata={"prior_limitation": BUILD26_HISTORICAL_DISPOSITION},
    )

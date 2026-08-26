"""EVIDENCE-01 forward evidence qualification policy builder."""

from __future__ import annotations

from .identity import derive_forward_evidence_policy_id
from .types import (
    EVIDENCE01_DEFAULT_HORIZON_NS,
    EVIDENCE01_MAX_ADMISSIBLE_GAP_NS,
    EVIDENCE01_MINIMUM_CLASS_SUPPORT,
    EVIDENCE01_MINIMUM_DISTINCT_SESSIONS,
    EVIDENCE01_MINIMUM_DISTINCT_TRADING_DAYS,
    EVIDENCE01_MINIMUM_DURATION_NS,
    EVIDENCE01_MINIMUM_ELIGIBLE_PREDICTIONS,
    EVIDENCE01_MINIMUM_SETTLED_PREDICTIONS,
    EVIDENCE01_MINIMUM_SETTLEMENT_RATE,
    FORWARD_EVIDENCE_QUALIFICATION_IMPLEMENTATION_VERSION,
    FORWARD_EVIDENCE_QUALIFICATION_SCHEMA_VERSION,
    ForwardEvidenceQualificationPolicyV1,
)

BUILD26_QUALIFICATION_SPEC_ID = (
    "FQSPEC-c64caac4e5b4b0562e92b54d1b1242c1fecca9480255aa9a8bc2c1f75122a9d1"
)
DEFAULT_REQUIRED_QUALITY_STATES: tuple[str, ...] = ("GOOD", "DEGRADED")


def build_forward_evidence_qualification_policy(
    *,
    build26_spec_ref: str = BUILD26_QUALIFICATION_SPEC_ID,
    horizon_ns: int = EVIDENCE01_DEFAULT_HORIZON_NS,
    minimum_eligible_predictions: int = EVIDENCE01_MINIMUM_ELIGIBLE_PREDICTIONS,
    minimum_settled_predictions: int = EVIDENCE01_MINIMUM_SETTLED_PREDICTIONS,
    minimum_settlement_rate: float = EVIDENCE01_MINIMUM_SETTLEMENT_RATE,
    minimum_duration_ns: int = EVIDENCE01_MINIMUM_DURATION_NS,
    minimum_distinct_trading_days: int = EVIDENCE01_MINIMUM_DISTINCT_TRADING_DAYS,
    minimum_distinct_sessions: int = EVIDENCE01_MINIMUM_DISTINCT_SESSIONS,
    minimum_class_support: int = EVIDENCE01_MINIMUM_CLASS_SUPPORT,
    maximum_admissible_gap_ns: int = EVIDENCE01_MAX_ADMISSIBLE_GAP_NS,
    required_quality_states: tuple[str, ...] = DEFAULT_REQUIRED_QUALITY_STATES,
) -> ForwardEvidenceQualificationPolicyV1:
    policy = ForwardEvidenceQualificationPolicyV1(
        policy_id="pending",
        schema_version=FORWARD_EVIDENCE_QUALIFICATION_SCHEMA_VERSION,
        build26_spec_ref=build26_spec_ref,
        horizon_ns=horizon_ns,
        minimum_eligible_predictions=minimum_eligible_predictions,
        minimum_settled_predictions=minimum_settled_predictions,
        minimum_settlement_rate=minimum_settlement_rate,
        minimum_duration_ns=minimum_duration_ns,
        minimum_distinct_trading_days=minimum_distinct_trading_days,
        minimum_distinct_sessions=minimum_distinct_sessions,
        minimum_class_support=minimum_class_support,
        maximum_admissible_gap_ns=maximum_admissible_gap_ns,
        required_quality_states=required_quality_states,
        implementation_version=FORWARD_EVIDENCE_QUALIFICATION_IMPLEMENTATION_VERSION,
        metadata={"milestone": "EVIDENCE-01", "extends": "BUILD26"},
    )
    policy_id = derive_forward_evidence_policy_id(policy)
    return ForwardEvidenceQualificationPolicyV1(
        policy_id=policy_id,
        schema_version=policy.schema_version,
        build26_spec_ref=policy.build26_spec_ref,
        horizon_ns=policy.horizon_ns,
        minimum_eligible_predictions=policy.minimum_eligible_predictions,
        minimum_settled_predictions=policy.minimum_settled_predictions,
        minimum_settlement_rate=policy.minimum_settlement_rate,
        minimum_duration_ns=policy.minimum_duration_ns,
        minimum_distinct_trading_days=policy.minimum_distinct_trading_days,
        minimum_distinct_sessions=policy.minimum_distinct_sessions,
        minimum_class_support=policy.minimum_class_support,
        maximum_admissible_gap_ns=policy.maximum_admissible_gap_ns,
        required_quality_states=policy.required_quality_states,
        implementation_version=policy.implementation_version,
        metadata=policy.metadata,
    )

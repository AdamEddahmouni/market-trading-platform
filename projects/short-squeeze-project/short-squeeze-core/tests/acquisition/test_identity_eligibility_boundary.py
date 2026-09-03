from datetime import UTC, date, datetime

from squeeze_core.acquisition.boundary_freeze import freeze_detection_boundary
from squeeze_core.acquisition.eligibility import decide_eligibility
from squeeze_core.acquisition.identity_resolution import resolve_identity
from squeeze_core.acquisition.models import (
    AcquisitionPlanStatus,
    BoundaryEvidence,
    BoundaryRule,
    EligibilityContext,
    ExclusionCode,
    IdentityClaim,
    IdentityState,
)
def _claim(**changes):
    values = {
        "source_artifact_id": "identity-1",
        "symbol": "BIYA",
        "issuer_name": "Baiya International Group Inc.",
        "exchange": "NASDAQ",
        "security_type": "COMMON_STOCK",
        "provider_identifier": "provider:biya",
        "effective_from": date(2024, 1, 1),
        "effective_to": None,
        "corporate_actions": (),
        "symbol_reuse_risk": False,
    }
    values.update(changes)
    return IdentityClaim(**values)


def test_identity_resolution_preserves_resolved_partial_conflicted_and_unresolved_states():
    resolved = resolve_identity((_claim(),))
    partial = resolve_identity((_claim(provider_identifier=None),))
    conflicted = resolve_identity((_claim(), _claim(source_artifact_id="identity-2", exchange="NYSE")))
    unresolved = resolve_identity(())
    assert resolved.state is IdentityState.RESOLVED
    assert partial.state is IdentityState.PARTIALLY_RESOLVED
    assert conflicted.state is IdentityState.CONFLICTED
    assert len(conflicted.claims) == 2
    assert unresolved.state is IdentityState.UNRESOLVED


def test_symbol_reuse_and_corporate_action_risk_prevent_full_resolution():
    result = resolve_identity((_claim(symbol_reuse_risk=True, corporate_actions=("REVERSE_SPLIT",)),))
    assert result.state is IdentityState.PARTIALLY_RESOLVED
    assert result.risk_codes == ("CORPORATE_ACTION_REVIEW_REQUIRED", "SYMBOL_REUSE_RISK")


def test_eligibility_accepts_missing_short_pressure_but_rejects_draft_and_synthetic():
    identity = resolve_identity((_claim(),))
    included = decide_eligibility(EligibilityContext(
        acquisition_plan_status=AcquisitionPlanStatus.PREREGISTERED,
        within_date_range=True,
        within_population=True,
        discovery_provenance_available=True,
        artifact_validation_passed=True,
        identity_resolution=identity,
        deterministic_boundary_available=True,
        objective_market_evidence_available=True,
        phase_3a_request_constructible=True,
        missing_domains=("SHORT_PRESSURE",),
        synthetic=False,
    ))
    draft = decide_eligibility(EligibilityContext(
        **{**included.context.model_dump(), "acquisition_plan_status": AcquisitionPlanStatus.DRAFT}
    ))
    synthetic = decide_eligibility(EligibilityContext(
        **{**included.context.model_dump(), "synthetic": True}
    ))
    assert included.included and included.exclusion_codes == ()
    assert ExclusionCode.ACQUISITION_PLAN_NOT_PREREGISTERED in draft.exclusion_codes
    assert ExclusionCode.CASE_REQUIRES_FABRICATED_EVIDENCE in synthetic.exclusion_codes


def test_eligibility_never_uses_later_outcome():
    fields = EligibilityContext.model_fields
    assert not any("outcome" in name.lower() or "return" in name.lower() for name in fields)


def test_boundary_freezes_earliest_objective_evidence_and_rejects_outcome_aware_rule():
    later = BoundaryEvidence(
        timestamp=datetime(2024, 5, 14, 12, 5, tzinfo=UTC), source_artifact_id="b", completed_bar=True
    )
    earlier = BoundaryEvidence(
        timestamp=datetime(2024, 5, 14, 12, 0, tzinfo=UTC), source_artifact_id="a", completed_bar=False
    )
    result = freeze_detection_boundary(
        case_attempt_id="attempt-1", symbol="BIYA", evidence=(later, earlier),
        rule=BoundaryRule.FIRST_OBJECTIVE_DISCOVERY_TIMESTAMP,
    )
    bar_result = freeze_detection_boundary(
        case_attempt_id="attempt-1", symbol="BIYA", evidence=(later, earlier),
        rule=BoundaryRule.FIRST_ELIGIBLE_COMPLETED_BAR_AT_OR_AFTER_DISCOVERY,
    )
    rejected = freeze_detection_boundary(
        case_attempt_id="attempt-1", symbol="BIYA", evidence=(later, earlier),
        rule=BoundaryRule.MAXIMUM_LATER_RETURN,
    )
    assert result.boundary_timestamp == earlier.timestamp
    assert bar_result.boundary_timestamp == later.timestamp
    assert result.frozen_before_outcome_access
    assert rejected.boundary_timestamp is None
    assert rejected.diagnostic_codes == ("OUTCOME_AWARE_BOUNDARY_REJECTED",)

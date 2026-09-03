from datetime import UTC, datetime, timedelta

import pytest

from squeeze_core.acquisition.curation import append_attempt, transition_bundle
from squeeze_core.acquisition.leakage_guards import audit_outcome_leakage
from squeeze_core.acquisition.models import (
    AcquisitionLedger,
    CaseAttempt,
    CurationStatus,
    CuratedCaseBundle,
    LeakageAuditRequest,
)


T0 = datetime(2024, 5, 14, 12, 0, tzinfo=UTC)


def _audit(**changes):
    values = {
        "case_attempt_id": "attempt-1",
        "discovery_input_fields": ("symbol", "observed_at"),
        "eligibility_input_fields": ("identity", "artifacts"),
        "boundary_input_fields": ("discovery_timestamp",),
        "evaluation_input_fields": ("market_bars",),
        "plan_frozen_at": T0,
        "boundary_frozen_at": T0 + timedelta(minutes=1),
        "evaluation_request_frozen_at": T0 + timedelta(minutes=2),
        "evaluation_result_frozen_at": T0 + timedelta(minutes=3),
        "outcome_captured_at": T0 + timedelta(minutes=4),
        "discovery_manifest_id": "discovery-manifest",
        "outcome_manifest_id": "outcome-manifest",
        "plan_changed_after_outcome_access": False,
        "outcome_aware_selection_indicator": False,
        "maximum_return_selection_indicator": False,
        "post_event_article_used_as_discovery_source": False,
    }
    values.update(changes)
    return LeakageAuditRequest(**values)


def test_passing_leakage_audit_requires_separate_manifest_and_freeze_order():
    result = audit_outcome_leakage(_audit())
    assert result.passed
    assert result.diagnostic_codes == ("LEAKAGE_AUDIT_PASSED",)


def test_every_prohibited_input_layer_and_early_outcome_are_diagnosed():
    request = _audit(
        discovery_input_fields=("outcome_label",),
        eligibility_input_fields=("later_return",),
        boundary_input_fields=("maximum_observed_move_percent",),
        evaluation_input_fields=("outcome_horizon",),
        outcome_captured_at=T0 + timedelta(seconds=30),
        plan_changed_after_outcome_access=True,
        outcome_aware_selection_indicator=True,
        maximum_return_selection_indicator=True,
        post_event_article_used_as_discovery_source=True,
    )
    result = audit_outcome_leakage(request)
    assert not result.passed and result.publication_blocked
    assert {
        "OUTCOME_DATA_PRESENT_IN_DISCOVERY_INPUT",
        "OUTCOME_DATA_PRESENT_IN_ELIGIBILITY_INPUT",
        "OUTCOME_DATA_PRESENT_IN_BOUNDARY_INPUT",
        "OUTCOME_DATA_PRESENT_IN_EVALUATION_INPUT",
        "OUTCOME_ARTIFACT_CAPTURED_BEFORE_EVALUATION_FREEZE",
        "ACQUISITION_PLAN_CHANGED_AFTER_OUTCOME_ACCESS",
        "OUTCOME_AWARE_SELECTION_INDICATOR",
        "MAXIMUM_RETURN_SELECTION_INDICATOR",
        "POST_EVENT_ARTICLE_USED_AS_DISCOVERY_SOURCE",
        "LEAKAGE_AUDIT_FAILED",
    } <= set(result.diagnostic_codes)


def test_outcome_captured_before_any_upstream_freeze_is_diagnosed():
    plan = audit_outcome_leakage(_audit(outcome_captured_at=T0 - timedelta(minutes=1)))
    boundary = audit_outcome_leakage(_audit(boundary_frozen_at=T0 + timedelta(minutes=5)))
    evaluation_request = audit_outcome_leakage(
        _audit(evaluation_request_frozen_at=T0 + timedelta(minutes=5))
    )
    assert "OUTCOME_ARTIFACT_CAPTURED_BEFORE_PLAN_FREEZE" in plan.diagnostic_codes
    assert "OUTCOME_ARTIFACT_CAPTURED_BEFORE_BOUNDARY_FREEZE" in boundary.diagnostic_codes
    assert (
        "OUTCOME_ARTIFACT_CAPTURED_BEFORE_EVALUATION_FREEZE"
        in evaluation_request.diagnostic_codes
    )
    for result in (plan, boundary, evaluation_request):
        assert not result.passed and result.publication_blocked


def _bundle(status=CurationStatus.DISCOVERED):
    return CuratedCaseBundle(
        curated_case_bundle_id="bundle-1", acquisition_plan_id="plan-1",
        case_attempt_id="attempt-1", symbol="BIYA", curation_status=status,
        fixture_classification="SANITIZED_HISTORICAL_FIXTURE",
    )


def test_lifecycle_is_monotonic_and_rejects_invalid_jumps():
    captured = transition_bundle(_bundle(), CurationStatus.ARTIFACTS_CAPTURED)
    assert captured.curation_status is CurationStatus.ARTIFACTS_CAPTURED
    with pytest.raises(ValueError, match="invalid curation transition"):
        transition_bundle(_bundle(), CurationStatus.PUBLISHED)


def test_ledger_is_append_only_idempotent_and_rejects_conflicting_resume():
    attempt = CaseAttempt(case_attempt_id="attempt-1", acquisition_plan_id="plan-1", symbol="BIYA")
    ledger = append_attempt(AcquisitionLedger(ledger_id="ledger-1", attempts=()), attempt)
    assert append_attempt(ledger, attempt) == ledger
    with pytest.raises(ValueError, match="case attempt ID conflict"):
        append_attempt(ledger, CaseAttempt(
            case_attempt_id="attempt-1", acquisition_plan_id="plan-1", symbol="OTHER"
        ))

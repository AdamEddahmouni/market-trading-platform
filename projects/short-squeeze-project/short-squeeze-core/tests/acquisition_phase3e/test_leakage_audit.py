"""Post-outcome leakage audit for Phase 3E Stage 2."""

from __future__ import annotations

from squeeze_core.acquisition.phase3a_freeze.leakage import ordering_holds
from squeeze_core.acquisition.stage2.leakage import (
    audit_post_outcome_case,
    audit_post_outcome_case_violation,
    build_post_outcome_audit_request,
)
from squeeze_core.acquisition.stage2.outcomes import outcome_manifest_id_for


def test_post_outcome_leakage_audit_passes_for_frozen_ordering():
    case_id = "BATCH01_XNCR_20260718"
    manifest_id = outcome_manifest_id_for(case_id)
    request = build_post_outcome_audit_request(
        case_id=case_id,
        outcome_manifest_id=manifest_id,
    )
    assert ordering_holds(request)
    audit = audit_post_outcome_case(case_id=case_id, outcome_manifest_id=manifest_id)
    assert audit.passed is True
    assert audit.diagnostic_codes == ("LEAKAGE_AUDIT_PASSED",)


def test_post_outcome_leakage_audit_blocks_ordering_violation():
    case_id = "BATCH01_TRVI_20260718"
    manifest_id = outcome_manifest_id_for(case_id)
    audit = audit_post_outcome_case_violation(
        case_id=case_id,
        outcome_manifest_id=manifest_id,
    )
    assert audit.passed is False
    assert "OUTCOME_ARTIFACT_CAPTURED_BEFORE_EVALUATION_FREEZE" in audit.diagnostic_codes


def test_outcome_manifest_id_must_differ_from_discovery_manifest():
    case_id = "BATCH01_SLS_20260718"
    discovery = "BATCH01_DISCOVERY_MANIFEST"
    audit = audit_post_outcome_case(
        case_id=case_id,
        outcome_manifest_id=discovery,
    )
    assert audit.passed is False
    assert "OUTCOME_MANIFEST_NOT_SEPARATE" in audit.diagnostic_codes

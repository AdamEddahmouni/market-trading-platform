import pytest

from squeeze_core.acquisition.policies import POLICY_VERSIONS, load_policy


EXPECTED = {
    "acquisition_plan": "phase_3d_acquisition_plan_policy.v1",
    "candidate_discovery": "phase_3d_candidate_discovery_policy.v1",
    "historical_inclusion": "phase_3d_historical_inclusion_policy.v1",
    "historical_exclusion": "phase_3d_historical_exclusion_policy.v1",
    "identity_resolution": "phase_3d_identity_resolution_policy.v1",
    "detection_boundary": "phase_3d_detection_boundary_policy.v1",
    "outcome_leakage": "phase_3d_outcome_leakage_policy.v1",
    "deduplication": "phase_3d_unique_security_deduplication_policy.v1",
}


def test_all_required_policy_versions_are_exact_and_schema_is_unchanged():
    assert POLICY_VERSIONS == EXPECTED
    for name, version in EXPECTED.items():
        document = load_policy(name)
        assert document["schema_version"] == "1.0.0"
        assert document["policy_version"] == version


def test_unknown_policy_is_rejected():
    with pytest.raises(ValueError, match="unknown Phase 3D policy"):
        load_policy("not-a-policy")

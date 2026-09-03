import json
from pathlib import Path


POLICY_VERSIONS = {
    "acquisition_plan": "phase_3d_acquisition_plan_policy.v1",
    "candidate_discovery": "phase_3d_candidate_discovery_policy.v1",
    "historical_inclusion": "phase_3d_historical_inclusion_policy.v1",
    "historical_exclusion": "phase_3d_historical_exclusion_policy.v1",
    "identity_resolution": "phase_3d_identity_resolution_policy.v1",
    "detection_boundary": "phase_3d_detection_boundary_policy.v1",
    "outcome_leakage": "phase_3d_outcome_leakage_policy.v1",
    "deduplication": "phase_3d_unique_security_deduplication_policy.v1",
}


def load_policy(name: str):
    try:
        version = POLICY_VERSIONS[name]
    except KeyError as error:
        raise ValueError(f"unknown Phase 3D policy: {name}") from error
    path = Path(__file__).with_name("policy_documents") / f"{name}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema_version") != "1.0.0" or document.get("policy_version") != version:
        raise ValueError(f"invalid Phase 3D policy document: {name}")
    return document


__all__ = ["POLICY_VERSIONS", "load_policy"]

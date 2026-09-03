import json
from pathlib import Path

from .models import DetectionPredicatePolicy, OutcomeLabelPolicy


DETECTION_POLICY_VERSION = "phase_3b_research_detection_policy.v1"
OUTCOME_POLICY_VERSION = "phase_3b_outcome_label_policy.v1"
_POLICY_DIR = Path(__file__).with_name("policies")


class ResearchPolicyConfigurationError(ValueError):
    def __init__(self, code: str, value: str):
        self.code = code
        self.value = value
        super().__init__(code, value)


def load_detection_policy(version: str) -> DetectionPredicatePolicy:
    if version != DETECTION_POLICY_VERSION:
        raise ResearchPolicyConfigurationError(
            "RESEARCH_DETECTION_POLICY_UNSUPPORTED", version
        )
    document = json.loads(
        (_POLICY_DIR / "phase_3b_research_detection_policy_v1.json").read_text(
            encoding="utf-8"
        )
    )
    policy = DetectionPredicatePolicy.model_validate(document)
    if policy.policy_version != version:
        raise ResearchPolicyConfigurationError(
            "RESEARCH_DETECTION_POLICY_UNSUPPORTED", version
        )
    return policy


def load_outcome_policy(version: str) -> OutcomeLabelPolicy:
    if version != OUTCOME_POLICY_VERSION:
        raise ResearchPolicyConfigurationError("RESEARCH_OUTCOME_POLICY_UNSUPPORTED", version)
    document = json.loads(
        (_POLICY_DIR / "phase_3b_outcome_label_policy_v1.json").read_text(encoding="utf-8")
    )
    policy = OutcomeLabelPolicy.model_validate(document)
    if policy.policy_version != version:
        raise ResearchPolicyConfigurationError("RESEARCH_OUTCOME_POLICY_UNSUPPORTED", version)
    return policy


__all__ = [
    "DETECTION_POLICY_VERSION", "OUTCOME_POLICY_VERSION", "ResearchPolicyConfigurationError",
    "load_detection_policy", "load_outcome_policy",
]

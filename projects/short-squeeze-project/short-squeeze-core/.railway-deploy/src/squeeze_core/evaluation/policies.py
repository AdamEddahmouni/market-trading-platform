import json
from pathlib import Path

from .models import CandidateEvaluationPolicy, RuleDefinition


DEFAULT_POLICY_PATH = Path(__file__).with_name("policies") / "phase_3a_transparent_candidate_policy_v1.json"


class EvaluationConfigurationError(ValueError):
    code: str

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class UnknownPolicyError(EvaluationConfigurationError):
    def __init__(self, policy_version: str):
        super().__init__("EVALUATION_UNSUPPORTED_POLICY", policy_version)


class UnknownRuleError(EvaluationConfigurationError):
    def __init__(self, rule_id: str):
        super().__init__("EVALUATION_UNKNOWN_RULE", rule_id)


class DuplicateRuleError(EvaluationConfigurationError):
    def __init__(self, rule_id: str):
        super().__init__("EVALUATION_DUPLICATE_RULE", rule_id)


def load_policy(path: str | Path) -> CandidateEvaluationPolicy:
    return CandidateEvaluationPolicy.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def lookup_policy(policy_version: str) -> CandidateEvaluationPolicy:
    policy = load_policy(DEFAULT_POLICY_PATH)
    if policy.policy_version != policy_version:
        raise UnknownPolicyError(policy_version)
    return policy


def lookup_rule(policy: CandidateEvaluationPolicy, rule_id: str) -> RuleDefinition:
    match = next((item for item in policy.rules if item.rule_id == rule_id), None)
    if match is None:
        raise UnknownRuleError(rule_id)
    return match


def validate_enabled_rules(
    policy: CandidateEvaluationPolicy, rule_ids: tuple[str, ...]
) -> tuple[RuleDefinition, ...]:
    seen: set[str] = set()
    for rule_id in rule_ids:
        if rule_id in seen:
            raise DuplicateRuleError(rule_id)
        seen.add(rule_id)
    return tuple(sorted((lookup_rule(policy, item) for item in rule_ids), key=lambda item: item.rule_id))


__all__ = [
    "DEFAULT_POLICY_PATH", "DuplicateRuleError", "EvaluationConfigurationError",
    "UnknownPolicyError", "UnknownRuleError", "load_policy", "lookup_policy",
    "lookup_rule", "validate_enabled_rules",
]


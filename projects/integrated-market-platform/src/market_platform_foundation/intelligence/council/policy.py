"""Immutable council policy for BUILD 12."""

from __future__ import annotations

from dataclasses import dataclass

from ...canonical import canonical_bytes, sha256_bytes

COUNCIL_POLICY_IDENTITY_VERSION = "council-policy-sha256-v1"


@dataclass(frozen=True, slots=True)
class CouncilPolicy:
    blind_first_pass_required: bool = True
    allow_degraded_evidence: bool = True
    min_comparable_evidence_for_conflict: int = 2
    require_source_independence_for_deliberation: bool = False
    deliberation_enabled: bool = True
    deliberation_on_correlated_conflict: bool = True
    max_deliberation_rounds: int = 1
    blackboard_version: str = "1"
    comparison_adapter_version: str = "council-comparison-v1"

    def __post_init__(self) -> None:
        if self.min_comparable_evidence_for_conflict < 2:
            raise ValueError("COUNCIL_POLICY_MIN_COMPARABLE_CONFLICT")
        if self.max_deliberation_rounds < 1:
            raise ValueError("COUNCIL_POLICY_MAX_ROUNDS")

    @property
    def policy_identity(self) -> str:
        payload = {
            "identity_version": COUNCIL_POLICY_IDENTITY_VERSION,
            "schema_version": "1",
            "blind_first_pass_required": self.blind_first_pass_required,
            "allow_degraded_evidence": self.allow_degraded_evidence,
            "min_comparable_evidence_for_conflict": self.min_comparable_evidence_for_conflict,
            "require_source_independence_for_deliberation": self.require_source_independence_for_deliberation,
            "deliberation_enabled": self.deliberation_enabled,
            "deliberation_on_correlated_conflict": self.deliberation_on_correlated_conflict,
            "max_deliberation_rounds": self.max_deliberation_rounds,
            "blackboard_version": self.blackboard_version,
            "comparison_adapter_version": self.comparison_adapter_version,
        }
        return f"CPOL-{sha256_bytes(canonical_bytes(payload))}"


DEFAULT_COUNCIL_POLICY = CouncilPolicy()


__all__ = ["COUNCIL_POLICY_IDENTITY_VERSION", "CouncilPolicy", "DEFAULT_COUNCIL_POLICY"]

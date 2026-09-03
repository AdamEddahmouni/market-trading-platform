"""Immutable hypothesis policies for BUILD 13."""

from __future__ import annotations

from dataclasses import dataclass

from ...canonical import canonical_bytes, sha256_bytes
from .factors import OPTIONAL_SHORT_SQUEEZE_FACTORS, REQUIRED_SHORT_SQUEEZE_FACTORS
from .types import HypothesisEvidencePhasePolicy

SHORT_SQUEEZE_POLICY_IDENTITY_VERSION = "short-squeeze-policy-sha256-v1"


@dataclass(frozen=True, slots=True)
class ShortSqueezeHypothesisPolicy:
    required_factors: tuple[str, ...] = tuple(f.value for f in REQUIRED_SHORT_SQUEEZE_FACTORS)
    optional_factors: tuple[str, ...] = tuple(f.value for f in OPTIONAL_SHORT_SQUEEZE_FACTORS)
    minimum_independent_provenance_groups: int = 2
    minimum_expert_domains: int = 2
    allow_degraded_evidence: bool = True
    allow_contested_emission: bool = True
    evidence_phase_policy: HypothesisEvidencePhasePolicy = HypothesisEvidencePhasePolicy.BLIND_ONLY
    falsification_criteria_version: str = "short-squeeze-falsification-v1"

    def __post_init__(self) -> None:
        if self.minimum_independent_provenance_groups < 1:
            raise ValueError("SHORT_SQUEEZE_POLICY_MIN_PROVENANCE")
        if self.minimum_expert_domains < 1:
            raise ValueError("SHORT_SQUEEZE_POLICY_MIN_DOMAINS")

    @property
    def policy_identity(self) -> str:
        payload = {
            "identity_version": SHORT_SQUEEZE_POLICY_IDENTITY_VERSION,
            "required_factors": list(self.required_factors),
            "optional_factors": list(self.optional_factors),
            "minimum_independent_provenance_groups": self.minimum_independent_provenance_groups,
            "minimum_expert_domains": self.minimum_expert_domains,
            "allow_degraded_evidence": self.allow_degraded_evidence,
            "allow_contested_emission": self.allow_contested_emission,
            "evidence_phase_policy": self.evidence_phase_policy.value,
            "falsification_criteria_version": self.falsification_criteria_version,
        }
        return f"SSPOL-{sha256_bytes(canonical_bytes(payload))}"


DEFAULT_SHORT_SQUEEZE_POLICY = ShortSqueezeHypothesisPolicy()


__all__ = [
    "DEFAULT_SHORT_SQUEEZE_POLICY",
    "SHORT_SQUEEZE_POLICY_IDENTITY_VERSION",
    "ShortSqueezeHypothesisPolicy",
]

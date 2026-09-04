"""Immutable fusion and final-forecast policies for BUILD 14."""

from __future__ import annotations

from dataclasses import dataclass

from ...canonical import canonical_bytes, sha256_bytes
from .identity import FINAL_POLICY_ID_VERSION, FUSION_POLICY_ID_VERSION
from .types import ForecastContributorRole, POOLING_METHOD


@dataclass(frozen=True, slots=True)
class FusionPolicy:
    allowed_roles: frozenset[ForecastContributorRole] = frozenset({ForecastContributorRole.PRODUCTION})
    allow_control_contributors: bool = False
    allow_degraded: bool = False
    allow_unknown_dependence: bool = False
    pooling_method: str = POOLING_METHOD
    dependence_resolver_version: str = "forecast-dependence-resolver-v1"
    contributor_weights: dict[str, float] | None = None
    group_weights: dict[str, float] | None = None

    def __post_init__(self) -> None:
        if self.allow_control_contributors:
            object.__setattr__(
                self,
                "allowed_roles",
                frozenset(set(self.allowed_roles) | {ForecastContributorRole.CONTROL, ForecastContributorRole.RESEARCH}),
            )

    @property
    def policy_identity(self) -> str:
        payload = {
            "identity_version": FUSION_POLICY_ID_VERSION,
            "allowed_roles": sorted(role.value for role in self.allowed_roles),
            "allow_control_contributors": self.allow_control_contributors,
            "allow_degraded": self.allow_degraded,
            "allow_unknown_dependence": self.allow_unknown_dependence,
            "pooling_method": self.pooling_method,
            "dependence_resolver_version": self.dependence_resolver_version,
            "contributor_weights": self.contributor_weights or {},
            "group_weights": self.group_weights or {},
        }
        return f"FPOL-{sha256_bytes(canonical_bytes(payload))}"


@dataclass(frozen=True, slots=True)
class FinalForecastPolicy:
    require_calibration: bool = True
    minimum_independent_groups: int = 1
    required_contributor_families: frozenset[str] = frozenset()
    maximum_inter_group_dispersion: float | None = None
    fail_on_calibration_ood: bool = True
    allow_degraded: bool = False
    allow_unknown_dependence: bool = False
    allow_raw_research_output: bool = False
    research_mode: bool = False

    def __post_init__(self) -> None:
        if self.minimum_independent_groups < 1:
            raise ValueError("FINAL_POLICY_MIN_GROUPS")

    @property
    def policy_identity(self) -> str:
        payload = {
            "identity_version": FINAL_POLICY_ID_VERSION,
            "require_calibration": self.require_calibration,
            "minimum_independent_groups": self.minimum_independent_groups,
            "required_contributor_families": sorted(self.required_contributor_families),
            "maximum_inter_group_dispersion": self.maximum_inter_group_dispersion,
            "fail_on_calibration_ood": self.fail_on_calibration_ood,
            "allow_degraded": self.allow_degraded,
            "allow_unknown_dependence": self.allow_unknown_dependence,
            "allow_raw_research_output": self.allow_raw_research_output,
            "research_mode": self.research_mode,
        }
        return f"FFPOL-{sha256_bytes(canonical_bytes(payload))}"


DEFAULT_PRODUCTION_FUSION_POLICY = FusionPolicy()
DEFAULT_RESEARCH_FUSION_POLICY = FusionPolicy(allow_control_contributors=True)
DEFAULT_PRODUCTION_FINAL_POLICY = FinalForecastPolicy()
DEFAULT_RESEARCH_FINAL_POLICY = FinalForecastPolicy(
    require_calibration=False,
    allow_raw_research_output=True,
    research_mode=True,
)


__all__ = [
    "DEFAULT_PRODUCTION_FINAL_POLICY",
    "DEFAULT_PRODUCTION_FUSION_POLICY",
    "DEFAULT_RESEARCH_FINAL_POLICY",
    "DEFAULT_RESEARCH_FUSION_POLICY",
    "FinalForecastPolicy",
    "FusionPolicy",
]

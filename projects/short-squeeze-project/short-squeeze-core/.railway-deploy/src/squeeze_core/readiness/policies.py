"""Versioned, declarative input-requirement policies for the 17 already-implemented
Phase 2A/2B/2C operations named in the Phase 2D handoff Section 10.2. Every policy is
pure data: no formula logic, no trading threshold (docs/phase-2d-design.md Section
10). Adding a policy for a future operation is additive; this module never generates
a generic "short-squeeze readiness" policy."""

from squeeze_core.evidence import CoverageDomain

from .models import OperationRequirementPolicy

POLICY_VERSION = "phase_2d_readiness_policy.v1"


def _policy(operation: str, **kwargs: object) -> OperationRequirementPolicy:
    return OperationRequirementPolicy(operation=operation, policy_version=POLICY_VERSION, **kwargs)


OPERATION_REQUIREMENT_POLICIES: dict[str, OperationRequirementPolicy] = {
    policy.operation: policy
    for policy in (
        _policy("ABSOLUTE_RETURN", required_domains=(CoverageDomain.MARKET_BARS,)),
        _policy("PERCENTAGE_RETURN", required_domains=(CoverageDomain.MARKET_BARS,)),
        _policy("ABSOLUTE_SESSION_GAP", required_domains=(CoverageDomain.MARKET_BARS,)),
        _policy("PERCENTAGE_SESSION_GAP", required_domains=(CoverageDomain.MARKET_BARS,)),
        _policy("ABSOLUTE_BAR_RANGE", required_domains=(CoverageDomain.MARKET_BARS,)),
        _policy("PERCENTAGE_BAR_RANGE", required_domains=(CoverageDomain.MARKET_BARS,)),
        _policy(
            "MEAN_VOLUME_BASELINE",
            required_domains=(CoverageDomain.MARKET_BARS,),
            requires_trailing_window=True,
        ),
        _policy(
            "RELATIVE_VOLUME",
            required_domains=(CoverageDomain.MARKET_BARS,),
            required_metric_names=("MEAN_VOLUME_BASELINE",),
            requires_trailing_window=True,
        ),
        _policy(
            "VOLUME_Z_SCORE",
            required_domains=(CoverageDomain.MARKET_BARS,),
            requires_trailing_window=True,
        ),
        _policy(
            "PERCENTAGE_RETURN_Z_SCORE",
            required_domains=(CoverageDomain.MARKET_BARS,),
            requires_trailing_window=True,
        ),
        _policy(
            "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE",
            required_domains=(CoverageDomain.PUBLISHED_SHORT_INTEREST,),
        ),
        _policy(
            "PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE",
            required_domains=(CoverageDomain.PUBLISHED_SHORT_INTEREST,),
        ),
        _policy(
            "DAYS_TO_COVER",
            required_domains=(
                CoverageDomain.PUBLISHED_SHORT_INTEREST,
                CoverageDomain.MARKET_BARS,
            ),
            requires_trailing_window=True,
        ),
        _policy("BORROW_FEE_ABSOLUTE_CHANGE", required_domains=(CoverageDomain.BORROW_FEE,)),
        _policy(
            "BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE",
            required_domains=(CoverageDomain.BORROW_FEE,),
        ),
        _policy(
            "BORROW_AVAILABILITY_ABSOLUTE_CHANGE",
            required_domains=(CoverageDomain.BORROW_AVAILABILITY,),
        ),
        _policy(
            "BORROW_AVAILABILITY_PERCENTAGE_CHANGE",
            required_domains=(CoverageDomain.BORROW_AVAILABILITY,),
        ),
    )
}


class UnsupportedOperationError(ValueError):
    pass


class UnsupportedPolicyVersionError(ValueError):
    pass


def lookup_policy(operation: str, policy_version: str | None = None) -> OperationRequirementPolicy:
    """Looks up the requirement policy for a named operation. Raises a stable,
    typed error for an unknown operation or an unsupported policy version -- never
    silently falls back to a default policy."""

    policy = OPERATION_REQUIREMENT_POLICIES.get(operation)
    if policy is None:
        raise UnsupportedOperationError(f"unsupported readiness operation: {operation}")
    if policy_version is not None and policy_version != policy.policy_version:
        raise UnsupportedPolicyVersionError(
            f"unsupported policy version {policy_version!r} for operation {operation}; "
            f"expected {policy.policy_version!r}"
        )
    return policy


__all__ = [
    "OPERATION_REQUIREMENT_POLICIES",
    "POLICY_VERSION",
    "UnsupportedOperationError",
    "UnsupportedPolicyVersionError",
    "lookup_policy",
]

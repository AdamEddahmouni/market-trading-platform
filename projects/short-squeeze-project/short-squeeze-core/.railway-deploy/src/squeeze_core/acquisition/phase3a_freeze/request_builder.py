"""Construct the frozen Phase 3A request for one case.

The request is an ordinary ``RuleEvaluationRequest`` from the existing evaluation
package — no parallel request type is introduced. Only Batch 07-admissible evidence is
attached; every blocked field is simply absent.

``provider_scope`` is deliberately empty. The Phase 3A request contract has request-level
(not per-rule) evidence scoping, and the policy's own ``provider_scope_required`` gate is
the only contract-supported way to keep blocked absolute-price and float evidence out of
``PRICE_RANGE`` / ``FLOAT_MAXIMUM`` while still supplying the admissible availability and
ratio rules their bars. See
docs/batch-08-phase3a-request-result-freeze-plan.md Section 6.1.
"""

from __future__ import annotations

from datetime import datetime

from squeeze_core.contracts import AssetClass, Observation
from squeeze_core.evaluation.models import (
    CandidateEvaluationPolicy,
    RuleEvaluationRequest,
)
from squeeze_core.metrics.models import MetricResult
from squeeze_core.readiness import (
    DomainCoverageSnapshot,
    EvidenceConflictSummary,
    InputSufficiencyResult,
)

from .evidence_adapter import BAR_INTERVAL

#: Frozen: no request-level provider scope (see module docstring).
FROZEN_PROVIDER_SCOPE: tuple[str, ...] = ()

#: Frozen: no market-session scope is declared, because Batch 06 left session
#: completeness unevidenced. Declaring one would assert an unevidenced fact.
FROZEN_MARKET_SESSION: tuple[str, ...] = ()

#: Frozen: no field was ever defaulted, so the substitution list stays empty.
FROZEN_DEFAULT_SUBSTITUTION_FIELDS: tuple[str, ...] = ()


def build_request(
    *,
    symbol: str,
    as_of: datetime,
    policy: CandidateEvaluationPolicy,
    observations: tuple[Observation, ...],
    metric: MetricResult | None,
    readiness: tuple[
        DomainCoverageSnapshot, EvidenceConflictSummary, InputSufficiencyResult
    ],
) -> RuleEvaluationRequest:
    """Build the canonical Phase 3A request from admissible evidence only."""
    return RuleEvaluationRequest(
        symbol=symbol,
        asset_class=AssetClass.EQUITY,
        as_of=as_of,
        policy_version=policy.policy_version,
        enabled_rule_ids=policy.enabled_rule_ids,
        provider_scope=FROZEN_PROVIDER_SCOPE,
        market_interval=BAR_INTERVAL,
        market_session=FROZEN_MARKET_SESSION,
        # Omitted, not defaulted: no volume window, and no short-interest, borrow, or
        # news provider, because no such detection-time evidence exists.
        volume_window=None,
        short_interest_provider=None,
        borrow_provider=None,
        news_provider=None,
        input_observations=observations,
        input_metrics=() if metric is None else (metric,),
        input_readiness_results=readiness,
        default_substitution_fields=FROZEN_DEFAULT_SUBSTITUTION_FIELDS,
    )


__all__ = [
    "FROZEN_DEFAULT_SUBSTITUTION_FIELDS",
    "FROZEN_MARKET_SESSION",
    "FROZEN_PROVIDER_SCOPE",
    "build_request",
]

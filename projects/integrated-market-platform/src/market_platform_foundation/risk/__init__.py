"""Independent risk decision layer."""

from .book_exposure import (
    AssetClassExposure,
    BookExposureReport,
    BookLimitPolicy,
    PositionExposureRow,
    aggregate_book_exposure,
)
from .decision import evaluate_risk
from .g2_g3_handoff import (
    HANDOFF_AUTHORITY,
    RankedOpportunityIntent,
    RiskHandoffReport,
    evaluate_ranked_opportunity_handoff,
    intent_from_ranked_summary,
)
from .kill_switch import KillSwitchState
from .policy import DEFAULT_RISK_POLICY, build_risk_policy

__all__ = [
    "AssetClassExposure",
    "BookExposureReport",
    "BookLimitPolicy",
    "DEFAULT_RISK_POLICY",
    "HANDOFF_AUTHORITY",
    "KillSwitchState",
    "PositionExposureRow",
    "RankedOpportunityIntent",
    "RiskHandoffReport",
    "aggregate_book_exposure",
    "build_risk_policy",
    "evaluate_ranked_opportunity_handoff",
    "evaluate_risk",
    "intent_from_ranked_summary",
]

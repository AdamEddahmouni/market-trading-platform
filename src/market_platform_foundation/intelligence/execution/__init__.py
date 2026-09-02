"""Deterministic paper execution and risk (BUILD 22)."""

from .engine import PaperExecutionOrchestrator, PreTradeRiskEngine, opportunity_side_to_order_side
from .errors import (
    DirectForecastTradeForbidden,
    ExecutionError,
    LiveExecutionForbidden,
    OpportunityGateError,
)
from .identity import (
    derive_execution_policy_id,
    derive_paper_order_idempotency_key,
    derive_portfolio_snapshot_id,
    derive_risk_decision_id,
    derive_trade_proposal_id,
    execution_policy_identity_payload,
)
from .policy import build_execution_policy
from .serialization import (
    execution_policy_v1_from_dict,
    execution_policy_v1_to_dict,
    paper_portfolio_snapshot_v1_from_dict,
    paper_portfolio_snapshot_v1_to_dict,
    risk_decision_v1_from_dict,
    risk_decision_v1_to_dict,
)
from .exposure import compute_exposure, snapshot_exposure
from .snapshot import build_portfolio_snapshot, snapshot_from_paper_ledger
from .types import (
    EXECUTION_IMPLEMENTATION_VERSION,
    ExecutionMode,
    ExecutionPolicyV1,
    ExposureSnapshot,
    MarketQuoteV1,
    PaperExecutionResult,
    PreparedPaperExecution,
    PaperOpenOrderSnapshot,
    PaperPortfolioSnapshotV1,
    PaperPositionSnapshot,
    RiskDecisionKind,
    RiskDecisionV1,
    RiskReasonCode,
    SizingPolicyKind,
)

__all__ = [
    "EXECUTION_IMPLEMENTATION_VERSION",
    "DirectForecastTradeForbidden",
    "ExecutionError",
    "ExecutionMode",
    "ExecutionPolicyV1",
    "ExposureSnapshot",
    "LiveExecutionForbidden",
    "MarketQuoteV1",
    "OpportunityGateError",
    "PaperExecutionOrchestrator",
    "PaperExecutionResult",
    "PreparedPaperExecution",
    "PaperOpenOrderSnapshot",
    "PaperPortfolioSnapshotV1",
    "PaperPositionSnapshot",
    "PreTradeRiskEngine",
    "RiskDecisionKind",
    "RiskDecisionV1",
    "RiskReasonCode",
    "SizingPolicyKind",
    "build_execution_policy",
    "build_portfolio_snapshot",
    "compute_exposure",
    "derive_execution_policy_id",
    "derive_paper_order_idempotency_key",
    "derive_portfolio_snapshot_id",
    "derive_risk_decision_id",
    "derive_trade_proposal_id",
    "execution_policy_identity_payload",
    "execution_policy_v1_from_dict",
    "execution_policy_v1_to_dict",
    "opportunity_side_to_order_side",
    "paper_portfolio_snapshot_v1_from_dict",
    "paper_portfolio_snapshot_v1_to_dict",
    "risk_decision_v1_from_dict",
    "risk_decision_v1_to_dict",
    "snapshot_exposure",
    "snapshot_from_paper_ledger",
]

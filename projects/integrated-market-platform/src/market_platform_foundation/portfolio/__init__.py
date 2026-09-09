"""Portfolio domain: canonical multi-asset model (G2) + legacy fill-driven ledger.

The canonical multi-asset portfolio (``portfolio.canonical``) is the single
authoritative portfolio truth model: account/mode-scoped, instrument-keyed,
with explicit quantity units, per-currency cash, asset-aware valuation, an
explicit FX boundary, and valuation status. The legacy fill-driven equity
ledger (``portfolio.ledger``) remains the Paper execution parity baseline;
``portfolio.paper_adapter`` projects it into the canonical model (dual-run).
"""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes

from .admission import (
    AdmissionResult,
    AdmissionStatus,
    admission_result,
    assert_position_admissible,
    assert_record_admissible,
)
from .canonical import (
    BondPriceBasis,
    CanonicalPortfolio,
    CashBalance,
    MarkDataStatus,
    MarkType,
    PORTFOLIO_SCHEMA_VERSION,
    PortfolioError,
    PortfolioErrorCode,
    PortfolioKey,
    PortfolioPosition,
    PortfolioSnapshot,
    PositionInput,
    PositionValuation,
    QuantityUnit,
    ValuationMark,
    ValuationStatus,
    portfolio_identity_hash,
)
from .fx import FxFactsBundle, FxRate, aggregate_to_base, cash_to_base, convert
from .ledger import apply_fill, build_ledger_state
from .paper_adapter import paper_position_input, paper_snapshot_to_canonical
from .provider_normalization import (
    NormalizationStatus,
    NormalizedPosition,
    ProviderPositionRow,
    normalize_provider_position,
    normalize_provider_snapshot,
)
from .valuation import (
    ValuationContext,
    value_bond_position,
    value_position,
    value_positions,
)
from .attribution import (
    AttributionFill,
    AttributionFillV1,
    AttributionOutcomeKind,
    AttributionRecordV1,
    AttributionValidationError,
    StrategyAllocationSliceV1,
    StrategyAttribution,
    StrategyAttributionV1,
    TradingOutcomeV1,
    VirtualAllocationSliceV1,
    attribution_fill_v1_from_dict,
    attribution_fill_v1_to_dict,
    attribution_v1_canonical_bytes,
    attribution_v1_from_dict,
    attribution_v1_to_dict,
    compute_slice_realized_pnl,
    strategy_attribution_canonical_bytes,
    strategy_attribution_identity_hash,
    strategy_attribution_v1_from_dict,
    strategy_attribution_v1_to_dict,
    validate_attribution_scope,
)
from .reconciliation import reconcile_ledgers
from .attribution_materializer import (
    AttributionMaterializationError,
    COVERAGE_ALGORITHM_VERSION,
    MATERIALIZATION_SEMANTICS,
    get_latest_complete_strategy_attribution,
    materialize_strategy_attribution,
)

__all__ = [
    "AdmissionResult",
    "AdmissionStatus",
    "BondPriceBasis",
    "CanonicalPortfolio",
    "CashBalance",
    "FxFactsBundle",
    "FxRate",
    "MarkDataStatus",
    "MarkType",
    "NormalizationStatus",
    "NormalizedPosition",
    "PORTFOLIO_SCHEMA_VERSION",
    "PortfolioError",
    "PortfolioErrorCode",
    "PortfolioKey",
    "PortfolioPosition",
    "PortfolioSnapshot",
    "PositionInput",
    "PositionValuation",
    "ProviderPositionRow",
    "QuantityUnit",
    "ValuationContext",
    "ValuationMark",
    "ValuationStatus",
    "admission_result",
    "aggregate_to_base",
    "apply_fill",
    "assert_position_admissible",
    "assert_record_admissible",
    "build_ledger_state",
    "cash_to_base",
    "convert",
    "normalize_provider_position",
    "normalize_provider_snapshot",
    "paper_position_input",
    "paper_snapshot_to_canonical",
    "portfolio_identity_hash",
    "reconcile_ledgers",
    "value_bond_position",
    "value_position",
    "value_positions",
    "ledger_root_hash",
    "AttributionFill",
    "AttributionFillV1",
    "AttributionOutcomeKind",
    "AttributionRecordV1",
    "AttributionValidationError",
    "StrategyAllocationSliceV1",
    "StrategyAttribution",
    "StrategyAttributionV1",
    "TradingOutcomeV1",
    "VirtualAllocationSliceV1",
    "attribution_fill_v1_from_dict",
    "attribution_fill_v1_to_dict",
    "attribution_v1_canonical_bytes",
    "attribution_v1_from_dict",
    "attribution_v1_to_dict",
    "compute_slice_realized_pnl",
    "strategy_attribution_canonical_bytes",
    "strategy_attribution_identity_hash",
    "strategy_attribution_v1_from_dict",
    "strategy_attribution_v1_to_dict",
    "validate_attribution_scope",
    "AttributionMaterializationError",
    "COVERAGE_ALGORITHM_VERSION",
    "MATERIALIZATION_SEMANTICS",
    "get_latest_complete_strategy_attribution",
    "materialize_strategy_attribution",
]


def ledger_root_hash(state: dict[str, Any]) -> str:
    body = {
        "cash_minor": state["cash_minor"],
        "position_shares": state["position_shares"],
        "position_cost_basis_minor": state.get("position_cost_basis_minor", 0),
        "realized_pnl_minor": state["realized_pnl_minor"],
        "total_commission_minor": state["total_commission_minor"],
        "total_fees_minor": state["total_fees_minor"],
    }
    return sha256_bytes(canonical_bytes(body))

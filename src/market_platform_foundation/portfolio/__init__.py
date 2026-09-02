"""Fill-driven portfolio ledger, attribution, and reconciliation."""

from __future__ import annotations

from typing import Any

from ..canonical import canonical_bytes, sha256_bytes

from .ledger import apply_fill, build_ledger_state
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
    "apply_fill",
    "build_ledger_state",
    "reconcile_ledgers",
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

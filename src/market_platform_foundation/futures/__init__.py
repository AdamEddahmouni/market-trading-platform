"""Futures lane canonical modules — roll, notional, family models."""

from .basis import basis_observation_from_curve, basis_payload, build_basis_observation
from .carry import (
    CARRY_VERSION,
    CarryObservation,
    carry_from_curve,
    carry_observation_to_dict,
    carry_payload,
)
from .continuous import (
    ContinuousSeriesPoint,
    additive_back_adjusted_series,
    continuous_series_to_dicts,
    ratio_adjusted_series,
    roll_gaps_from_prices,
    unadjusted_continuous_series,
)
from .curve import (
    basis_observation_from_curve,
    build_curve_snapshot_from_chain,
    curve_regime,
    curve_snapshot_payload,
)
from .notional import ES_CONTRACT_SPEC, exposure_summary, notional_exposure, pnl_from_price_change
from .roll import LeadContractSelection, select_lead_contract

__all__ = [
    "CARRY_VERSION",
    "CarryObservation",
    "ContinuousSeriesPoint",
    "ES_CONTRACT_SPEC",
    "LeadContractSelection",
    "additive_back_adjusted_series",
    "basis_observation_from_curve",
    "basis_payload",
    "build_basis_observation",
    "build_curve_snapshot_from_chain",
    "carry_from_curve",
    "carry_observation_to_dict",
    "carry_payload",
    "continuous_series_to_dicts",
    "curve_regime",
    "curve_snapshot_payload",
    "exposure_summary",
    "notional_exposure",
    "pnl_from_price_change",
    "ratio_adjusted_series",
    "roll_gaps_from_prices",
    "select_lead_contract",
    "unadjusted_continuous_series",
]

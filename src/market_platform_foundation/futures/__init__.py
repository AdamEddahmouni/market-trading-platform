"""Futures lane canonical modules — roll, notional, family models."""

from .continuous import (
    ContinuousSeriesPoint,
    additive_back_adjusted_series,
    continuous_series_to_dicts,
    unadjusted_continuous_series,
)
from .notional import ES_CONTRACT_SPEC, exposure_summary, notional_exposure, pnl_from_price_change
from .roll import LeadContractSelection, select_lead_contract

__all__ = [
    "ContinuousSeriesPoint",
    "ES_CONTRACT_SPEC",
    "LeadContractSelection",
    "additive_back_adjusted_series",
    "continuous_series_to_dicts",
    "exposure_summary",
    "notional_exposure",
    "pnl_from_price_change",
    "select_lead_contract",
    "unadjusted_continuous_series",
]

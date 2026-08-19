"""Futures lane canonical modules — roll, notional, family models."""

from .baselines import (
    BASELINES_VERSION,
    MIN_BARS_FOR_BASELINES,
    TREND_DOWN_THRESHOLD,
    TREND_LOOKBACK_1M,
    TREND_LOOKBACK_3M,
    TREND_LOOKBACK_6M,
    TREND_LOOKBACK_12M,
    TREND_UP_THRESHOLD,
    TrendRegime,
    baselines_payload,
    trend_regime,
)
from .basis import basis_observation_from_curve, basis_payload, build_basis_observation
from .carry import (
    CARRY_VERSION,
    CarryObservation,
    carry_from_curve,
    carry_observation_to_dict,
    carry_payload,
)
from .positioning import (
    CROWDED_LONG_THRESHOLD,
    CROWDED_SHORT_THRESHOLD,
    CrowdingRegime,
    OiVelocityHypothesis,
    POSITIONING_VERSION,
    crowding_regime,
    positioning_payload,
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
from .relative_value import (
    RV_VERSION,
    relative_value_payload,
    relative_value_snapshot,
)

__all__ = [
    "BASELINES_VERSION",
    "CARRY_VERSION",
    "CROWDED_LONG_THRESHOLD",
    "CROWDED_SHORT_THRESHOLD",
    "CarryObservation",
    "CrowdingRegime",
    "OiVelocityHypothesis",
    "POSITIONING_VERSION",
    "ContinuousSeriesPoint",
    "ES_CONTRACT_SPEC",
    "LeadContractSelection",
    "MIN_BARS_FOR_BASELINES",
    "TREND_DOWN_THRESHOLD",
    "TREND_LOOKBACK_1M",
    "TREND_LOOKBACK_3M",
    "TREND_LOOKBACK_6M",
    "TREND_LOOKBACK_12M",
    "TREND_UP_THRESHOLD",
    "TrendRegime",
    "baselines_payload",
    "trend_regime",
    "additive_back_adjusted_series",
    "basis_observation_from_curve",
    "basis_payload",
    "build_basis_observation",
    "build_curve_snapshot_from_chain",
    "carry_from_curve",
    "carry_observation_to_dict",
    "carry_payload",
    "crowding_regime",
    "positioning_payload",
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

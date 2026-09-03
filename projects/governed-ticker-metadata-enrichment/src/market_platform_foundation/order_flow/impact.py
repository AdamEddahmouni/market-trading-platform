"""Price-response / absorption / exhaustion from aggression vs mid progress — Order Flow OF7.

Absorption: high aggression + weak price progress + opposing book replenishment.
Exhaustion: aggression persists but price progress fails or momentum decays.

Does NOT mean hidden whale confirmed. Distinct from Short Squeeze lifecycle exhaustion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import ImpactRegime
from .liquidity import compute_liquidity_dynamics
from .ofi import _best_bid_ask, snapshot_pair_book_state_valid

IMPACT_METHOD = "impact_aggression_price_v1"
IMPACT_VERSION = "1"

AGGRESSION_THRESHOLD = 80.0
PROGRESS_SPREAD_FRACTION = 0.5


@dataclass(frozen=True, slots=True)
class ImpactDynamicsResult:
    aggression_signed_volume: float | None
    mid_delta: float
    relative_mid_delta: float
    price_efficiency: float | None
    opposing_replenishment: bool
    absorption_score: float | None
    exhaustion_score: float | None
    impact_regime: ImpactRegime
    impact_method: str
    impact_version: str
    book_state_valid: bool
    quality_flags: tuple[str, ...] = ()


def _mid_price(snapshot: dict[str, Any]) -> tuple[float, float] | None:
    bbo = _best_bid_ask(snapshot)
    if bbo is None:
        return None
    bid_price, _, ask_price, _ = bbo
    mid = (bid_price + ask_price) / 2.0
    spread = ask_price - bid_price
    return mid, spread


def _weak_progress(mid_delta: float, spread: float) -> bool:
    if spread <= 0:
        return abs(mid_delta) <= 1e-9
    return abs(mid_delta) / spread <= PROGRESS_SPREAD_FRACTION + 1e-9


def _absorption_score(
    *,
    aggression: float,
    mid_delta: float,
    spread: float,
    opposing_replenishment: bool,
) -> float:
    if not opposing_replenishment:
        return 0.0
    aggression_component = min(abs(aggression) / (AGGRESSION_THRESHOLD * 2), 1.0)
    progress_gap = 1.0 - min(abs(mid_delta) / max(spread, 1e-9), 1.0)
    score = 0.55 * progress_gap + 0.45 * aggression_component
    return round(min(max(score, 0.0), 1.0), 6)


def _exhaustion_score(
    *,
    aggression: float,
    prev_aggression: float | None,
    mid_delta: float,
    spread: float,
) -> float:
    if prev_aggression is None:
        return 0.0
    decay = 0.0
    if aggression > 0 and prev_aggression > aggression:
        decay = min((prev_aggression - aggression) / max(prev_aggression, 1.0), 1.0)
    elif aggression < 0 and prev_aggression < aggression:
        decay = min((aggression - prev_aggression) / max(abs(prev_aggression), 1.0), 1.0)
    if decay <= 0:
        return 0.0
    progress_fail = 1.0 if _weak_progress(mid_delta, spread) else 0.0
    if aggression > 0 and mid_delta > 0:
        progress_fail = max(progress_fail, 0.5)
    if aggression < 0 and mid_delta < 0:
        progress_fail = max(progress_fail, 0.5)
    score = 0.6 * decay + 0.4 * progress_fail
    return round(min(max(score, 0.0), 1.0), 6)


def compute_impact_dynamics(
    prev_snapshot: dict[str, Any],
    curr_snapshot: dict[str, Any],
    *,
    bar_delta: float | None = None,
    buying_volume: float | None = None,
    selling_volume: float | None = None,
    prev_bar_delta: float | None = None,
    level_count: int = 10,
    trajectory_resiliency: float | None = None,
    aggression_threshold: float = AGGRESSION_THRESHOLD,
) -> ImpactDynamicsResult:
    """Pair-wise absorption/exhaustion between book snapshots with optional trade bar."""
    if not snapshot_pair_book_state_valid(prev_snapshot, curr_snapshot):
        return ImpactDynamicsResult(
            aggression_signed_volume=None,
            mid_delta=0.0,
            relative_mid_delta=0.0,
            price_efficiency=None,
            opposing_replenishment=False,
            absorption_score=None,
            exhaustion_score=None,
            impact_regime=ImpactRegime.NEUTRAL,
            impact_method=IMPACT_METHOD,
            impact_version=IMPACT_VERSION,
            book_state_valid=False,
            quality_flags=("BOOK_STATE_INVALID",),
        )

    prev_mid_metrics = _mid_price(prev_snapshot)
    curr_mid_metrics = _mid_price(curr_snapshot)
    if prev_mid_metrics is None or curr_mid_metrics is None:
        return ImpactDynamicsResult(
            aggression_signed_volume=bar_delta,
            mid_delta=0.0,
            relative_mid_delta=0.0,
            price_efficiency=None,
            opposing_replenishment=False,
            absorption_score=None,
            exhaustion_score=None,
            impact_regime=ImpactRegime.NEUTRAL,
            impact_method=IMPACT_METHOD,
            impact_version=IMPACT_VERSION,
            book_state_valid=False,
            quality_flags=("BOOK_STATE_INVALID",),
        )

    prev_mid, prev_spread = prev_mid_metrics
    curr_mid, _ = curr_mid_metrics
    mid_delta = round(curr_mid - prev_mid, 8)
    relative_mid_delta = round(mid_delta / prev_mid if prev_mid > 0 else 0.0, 8)

    liquidity = compute_liquidity_dynamics(
        prev_snapshot,
        curr_snapshot,
        level_count=level_count,
        trajectory_resiliency=trajectory_resiliency,
    )

    quality_flags: list[str] = []
    aggression = bar_delta
    if aggression is None:
        quality_flags.append("MISSING_TRADE_FLOW")
        return ImpactDynamicsResult(
            aggression_signed_volume=None,
            mid_delta=mid_delta,
            relative_mid_delta=relative_mid_delta,
            price_efficiency=None,
            opposing_replenishment=False,
            absorption_score=None,
            exhaustion_score=None,
            impact_regime=ImpactRegime.NEUTRAL,
            impact_method=IMPACT_METHOD,
            impact_version=IMPACT_VERSION,
            book_state_valid=True,
            quality_flags=tuple(quality_flags),
        )

    price_efficiency: float | None = None
    if aggression != 0:
        price_efficiency = round(mid_delta / aggression, 8)

    ask_replenishment = liquidity.ask_depth_delta > 0
    bid_replenishment = liquidity.bid_depth_delta > 0
    opposing_replenishment = False
    if aggression > 0:
        opposing_replenishment = ask_replenishment or (
            liquidity.depth_replenishment > 0 and liquidity.ask_depth_delta >= 0
        )
    elif aggression < 0:
        opposing_replenishment = bid_replenishment or (
            liquidity.depth_replenishment > 0 and liquidity.bid_depth_delta >= 0
        )

    absorption_score = _absorption_score(
        aggression=aggression,
        mid_delta=mid_delta,
        spread=prev_spread,
        opposing_replenishment=opposing_replenishment,
    )
    exhaustion_score = _exhaustion_score(
        aggression=aggression,
        prev_aggression=prev_bar_delta,
        mid_delta=mid_delta,
        spread=prev_spread,
    )

    regime = ImpactRegime.NEUTRAL
    weak = _weak_progress(mid_delta, prev_spread)
    buy_aggression = aggression > aggression_threshold
    sell_aggression = aggression < -aggression_threshold

    if buy_aggression and weak and opposing_replenishment:
        regime = ImpactRegime.BUY_ABSORPTION
    elif sell_aggression and weak and opposing_replenishment:
        regime = ImpactRegime.SELL_ABSORPTION
    elif (
        aggression > 0
        and prev_bar_delta is not None
        and prev_bar_delta > aggression
        and (mid_delta <= 0 or weak)
    ):
        regime = ImpactRegime.BUY_EXHAUSTION
        exhaustion_score = max(exhaustion_score, 0.35)
    elif (
        aggression < 0
        and prev_bar_delta is not None
        and prev_bar_delta < aggression
        and (mid_delta >= 0 or weak)
    ):
        regime = ImpactRegime.SELL_EXHAUSTION
        exhaustion_score = max(exhaustion_score, 0.35)

    if regime in (ImpactRegime.BUY_ABSORPTION, ImpactRegime.SELL_ABSORPTION):
        absorption_score = max(absorption_score, 0.35)

    return ImpactDynamicsResult(
        aggression_signed_volume=round(aggression, 4),
        mid_delta=mid_delta,
        relative_mid_delta=relative_mid_delta,
        price_efficiency=price_efficiency,
        opposing_replenishment=opposing_replenishment,
        absorption_score=absorption_score if regime in (
            ImpactRegime.BUY_ABSORPTION,
            ImpactRegime.SELL_ABSORPTION,
        ) else (absorption_score if absorption_score > 0 else None),
        exhaustion_score=exhaustion_score if regime in (
            ImpactRegime.BUY_EXHAUSTION,
            ImpactRegime.SELL_EXHAUSTION,
        ) else (exhaustion_score if exhaustion_score > 0 else None),
        impact_regime=regime,
        impact_method=IMPACT_METHOD,
        impact_version=IMPACT_VERSION,
        book_state_valid=True,
        quality_flags=tuple(quality_flags),
    )


def impact_dynamics_to_dict(result: ImpactDynamicsResult) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "mid_delta": result.mid_delta,
        "relative_mid_delta": result.relative_mid_delta,
        "opposing_replenishment": result.opposing_replenishment,
        "impact_regime": result.impact_regime.value,
        "impact_method": result.impact_method,
        "impact_version": result.impact_version,
        "book_state_valid": result.book_state_valid,
        "quality_flags": list(result.quality_flags),
    }
    if result.aggression_signed_volume is not None:
        payload["aggression_signed_volume"] = result.aggression_signed_volume
    if result.price_efficiency is not None:
        payload["price_efficiency"] = result.price_efficiency
    if result.absorption_score is not None:
        payload["absorption_score"] = result.absorption_score
    if result.exhaustion_score is not None:
        payload["exhaustion_score"] = result.exhaustion_score
    return payload


__all__ = [
    "AGGRESSION_THRESHOLD",
    "IMPACT_METHOD",
    "IMPACT_VERSION",
    "PROGRESS_SPREAD_FRACTION",
    "ImpactDynamicsResult",
    "compute_impact_dynamics",
    "impact_dynamics_to_dict",
]

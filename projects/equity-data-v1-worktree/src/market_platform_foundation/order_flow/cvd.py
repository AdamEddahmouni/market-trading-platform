"""CVD computation with classification-confidence awareness."""

from __future__ import annotations

from collections.abc import Sequence

from ..donor_patterns.cvd_formulas import cumulative_delta
from .aggressor import classify_bar_delta
from .contracts import AggressorSource, ClassifiedTrade, CVDState


def compute_cvd_series(deltas: Sequence[float]) -> list[float]:
    return cumulative_delta(deltas)


def cvd_slope(cvd_series: Sequence[float], *, window: int = 1) -> float | None:
    if len(cvd_series) < window + 1:
        return None
    return cvd_series[-1] - cvd_series[-(window + 1)]


def cvd_acceleration(cvd_series: Sequence[float]) -> float | None:
    if len(cvd_series) < 3:
        return None
    slope_now = cvd_series[-1] - cvd_series[-2]
    slope_prev = cvd_series[-2] - cvd_series[-3]
    return slope_now - slope_prev


def _is_native_source(source: AggressorSource) -> bool:
    return source in {AggressorSource.EXCHANGE_NATIVE, AggressorSource.PROVIDER_NATIVE}


def _is_inferred_source(source: AggressorSource) -> bool:
    return source in {
        AggressorSource.BVC,
        AggressorSource.LEE_READY,
        AggressorSource.QUOTE_MATCH,
        AggressorSource.TICK_RULE,
        AggressorSource.OTHER_INFERENCE,
    }


def compute_cvd_state(
    bars: Sequence[dict[str, object]],
    *,
    rolling_window: int | None = None,
) -> CVDState | None:
    """Aggregate bar-level signed flow into CVD with provenance-weighted confidence."""
    if not bars:
        return None

    classified: list[ClassifiedTrade] = []
    for bar in bars:
        if not isinstance(bar, dict):
            continue
        delta = float(bar.get("delta", 0.0))
        volume = float(bar.get("volume", abs(delta)))
        quality = str(bar.get("quality", bar.get("aggressor_provenance", "bvc")))
        if "aggressor_provenance" in bar and "quality" not in bar:
            prov = str(bar.get("aggressor_provenance", "unknown"))
            quality = "tick" if prov == "known" else ("neutral" if prov == "unknown" else "bvc")
        classified.append(
            classify_bar_delta(
                bar_time=str(bar.get("bar_time", bar.get("date", ""))),
                delta=delta,
                volume=volume,
                quality=quality,
                source=str(bar.get("source", "")),
            )
        )

    if not classified:
        return None

    deltas = [trade.signed_volume for trade in classified]
    cvd_series = compute_cvd_series(deltas)
    session_cvd = cvd_series[-1]

    rolling_cvd: float | None = None
    if rolling_window is not None and rolling_window > 0 and len(deltas) >= rolling_window:
        rolling_cvd = sum(deltas[-rolling_window:])

    total = len(classified)
    native_count = sum(1 for t in classified if _is_native_source(t.aggressor_source))
    inferred_count = sum(1 for t in classified if _is_inferred_source(t.aggressor_source))
    unknown_count = sum(1 for t in classified if t.aggressor_source == AggressorSource.UNKNOWN)

    native_frac = native_count / total
    inferred_frac = inferred_count / total
    unknown_frac = unknown_count / total
    cvd_confidence = max(0.0, min(1.0, native_frac + 0.5 * inferred_frac))

    buy_vol = sum(t.quantity for t in classified if t.signed_volume > 0)
    sell_vol = sum(t.quantity for t in classified if t.signed_volume < 0)

    return CVDState(
        session_cvd=session_cvd,
        rolling_cvd=rolling_cvd,
        cvd_slope=cvd_slope(cvd_series),
        cvd_acceleration=cvd_acceleration(cvd_series),
        native_classification_fraction=round(native_frac, 4),
        inferred_classification_fraction=round(inferred_frac, 4),
        unknown_fraction=round(unknown_frac, 4),
        cvd_confidence=round(cvd_confidence, 4),
        aggressive_buy_volume=buy_vol,
        aggressive_sell_volume=sell_vol,
    )


def provenance_fractions_from_bars(bars: Sequence[dict[str, object]]) -> dict[str, float]:
    """Helper for workspace projections from whale ledger bar summaries."""
    state = compute_cvd_state(bars)
    if state is None:
        return {
            "native_classification_fraction": 0.0,
            "inferred_classification_fraction": 0.0,
            "unknown_fraction": 1.0,
            "cvd_confidence": 0.0,
        }
    return {
        "native_classification_fraction": state.native_classification_fraction,
        "inferred_classification_fraction": state.inferred_classification_fraction,
        "unknown_fraction": state.unknown_fraction,
        "cvd_confidence": state.cvd_confidence,
    }


def map_whale_provenance_to_source(provenance: str) -> AggressorSource:
    """Map ADR-WHALE-003 whale provenance strings to canonical AggressorSource."""
    mapping = {
        "known": AggressorSource.PROVIDER_NATIVE,
        "inferred": AggressorSource.OTHER_INFERENCE,
        "unknown": AggressorSource.UNKNOWN,
    }
    return mapping.get(str(provenance).lower(), AggressorSource.UNKNOWN)


__all__ = [
    "compute_cvd_series",
    "compute_cvd_state",
    "cvd_acceleration",
    "cvd_slope",
    "map_whale_provenance_to_source",
    "provenance_fractions_from_bars",
]

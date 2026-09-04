"""Deterministic derived macro features — PIT-compatible only."""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import MacroIndicatorValue, MacroObservation
from .pit import macro_as_of
from .quality import FredQualityFlag

DERIVED_VERSION = "fred_derived_v1"


@dataclass(frozen=True, slots=True)
class DerivedSpread:
    canonical_indicator_id: str
    value: float | None
    components: tuple[str, ...]
    layer: str = "DETERMINISTIC_DERIVED"
    quality_flags: tuple[str, ...] = ()


def derive_spread(
    observations: list[MacroObservation],
    *,
    left_id: str,
    right_id: str,
    output_id: str,
    decision_time: str,
) -> DerivedSpread:
    left = macro_as_of(observations, canonical_indicator_id=left_id, decision_time=decision_time)
    right = macro_as_of(observations, canonical_indicator_id=right_id, decision_time=decision_time)
    flags: list[str] = []
    if left.value is None or right.value is None:
        flags.append(FredQualityFlag.PIT_UNAVAILABLE.value)
        return DerivedSpread(output_id, None, (left_id, right_id), quality_flags=tuple(flags))
    if left.available_time > decision_time or right.available_time > decision_time:
        flags.append("LOOKAHEAD_REJECTED")
    return DerivedSpread(
        output_id,
        left.value - right.value,
        (left_id, right_id),
        quality_flags=tuple(flags),
    )


def derive_us_2s10s(observations: list[MacroObservation], *, decision_time: str) -> DerivedSpread:
    return derive_spread(
        observations,
        left_id="US_10Y_TREASURY_YIELD",
        right_id="US_2Y_TREASURY_YIELD",
        output_id="US_2S10S",
        decision_time=decision_time,
    )


def derive_us_3m10y(observations: list[MacroObservation], *, decision_time: str) -> DerivedSpread:
    return derive_spread(
        observations,
        left_id="US_10Y_TREASURY_YIELD",
        right_id="US_3M_TREASURY_YIELD",
        output_id="US_3M10Y",
        decision_time=decision_time,
    )


def revision_delta(initial: MacroObservation | None, latest: MacroObservation | None) -> dict[str, object]:
    if initial is None or latest is None:
        return {"revision_delta": None, "revision_pct": None, "revision_direction": None, "revision_count": 0}
    if initial.normalized_value is None or latest.normalized_value is None:
        return {"revision_delta": None, "revision_pct": None, "revision_direction": None, "revision_count": 0}
    delta = latest.normalized_value - initial.normalized_value
    pct = (delta / initial.normalized_value * 100.0) if initial.normalized_value else None
    direction = "UP" if delta > 0 else "DOWN" if delta < 0 else "FLAT"
    return {
        "revision_delta": delta,
        "revision_pct": pct,
        "revision_direction": direction,
        "revision_count": latest.revision_number,
    }


__all__ = [
    "DERIVED_VERSION",
    "DerivedSpread",
    "derive_spread",
    "derive_us_2s10s",
    "derive_us_3m10y",
    "revision_delta",
]

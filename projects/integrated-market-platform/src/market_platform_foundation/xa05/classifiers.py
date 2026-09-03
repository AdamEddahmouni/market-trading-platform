"""Versioned deterministic XA-05 state classifiers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .enums import EpistemicClass, EvidenceAvailabilityStatus, StateDimensionId


@dataclass(frozen=True, slots=True)
class YieldCurveClassifierConfig:
  version: str = "imp-xa05-yield-curve-v1"
  steep_spread_points: float = 0.50
  flat_spread_points: float = 0.25
  short_indicator_id: str = "US_2Y_TREASURY_YIELD"
  long_indicator_id: str = "US_10Y_TREASURY_YIELD"


@dataclass(frozen=True, slots=True)
class PolicyRateClassifierConfig:
  version: str = "imp-xa05-policy-rate-v1"
  restrictive_min_percent: float = 4.0
  accommodative_max_percent: float = 2.0
  indicator_id: str = "US_EFFECTIVE_FED_FUNDS_RATE"


@dataclass(frozen=True, slots=True)
class PositioningClassifierConfig:
    version: str = "imp-xa05-positioning-v1"
    long_bias_ratio: float = 0.10
    short_bias_ratio: float = -0.10
    market_report_id: str = "CFTC_MARKET:020601:TFF:FUTURES_ONLY"


@dataclass(frozen=True, slots=True)
class FreshnessClassifierConfig:
  version: str = "imp-xa05-freshness-v1"
  fresh_hours: int = 24 * 7
  stale_hours: int = 24 * 30


CLASSIFIER_REGISTRY: Mapping[str, object] = {
  "imp-xa05-yield-curve-v1": YieldCurveClassifierConfig(),
  "imp-xa05-policy-rate-v1": PolicyRateClassifierConfig(),
  "imp-xa05-positioning-v1": PositioningClassifierConfig(),
  "imp-xa05-freshness-v1": FreshnessClassifierConfig(),
}


def resolve_classifier_version(version: str) -> object:
  try:
    return CLASSIFIER_REGISTRY[version]
  except KeyError as exc:
    raise ValueError(f"unknown classifier version: {version}") from exc


def classify_yield_curve(
  yields: Mapping[str, float | None],
  *,
  config: YieldCurveClassifierConfig | None = None,
) -> tuple[str, EvidenceAvailabilityStatus, dict[str, float | None]]:
  active = config or YieldCurveClassifierConfig()
  short_value = yields.get(active.short_indicator_id)
  long_value = yields.get(active.long_indicator_id)
  features = {
    "short_yield": short_value,
    "long_yield": long_value,
    "spread_points": None,
  }
  if short_value is None or long_value is None:
    return "UNKNOWN", EvidenceAvailabilityStatus.INSUFFICIENT, features
  spread = long_value - short_value
  features["spread_points"] = spread
  if spread >= active.steep_spread_points:
    return "STEEP", EvidenceAvailabilityStatus.AVAILABLE, features
  if spread <= -active.flat_spread_points:
    return "INVERTED", EvidenceAvailabilityStatus.AVAILABLE, features
  if abs(spread) <= active.flat_spread_points:
    return "FLAT", EvidenceAvailabilityStatus.AVAILABLE, features
  return "TRANSITIONAL", EvidenceAvailabilityStatus.AVAILABLE, features


def classify_policy_rate(
  value: float | None,
  *,
  config: PolicyRateClassifierConfig | None = None,
) -> tuple[str, EvidenceAvailabilityStatus, dict[str, float | None]]:
  active = config or PolicyRateClassifierConfig()
  features = {"policy_rate_percent": value}
  if value is None:
    return "UNKNOWN", EvidenceAvailabilityStatus.MISSING, features
  if value >= active.restrictive_min_percent:
    return "RESTRICTIVE", EvidenceAvailabilityStatus.AVAILABLE, features
  if value <= active.accommodative_max_percent:
    return "ACCOMMODATIVE", EvidenceAvailabilityStatus.AVAILABLE, features
  return "NEUTRAL", EvidenceAvailabilityStatus.AVAILABLE, features


def classify_positioning_concentration(
  *,
  long_positions: int | None,
  short_positions: int | None,
  open_interest: int | None,
  config: PositioningClassifierConfig | None = None,
) -> tuple[str, EvidenceAvailabilityStatus, dict[str, float | None]]:
  _ = config or PositioningClassifierConfig()
  features: dict[str, float | None] = {
    "long_positions": None if long_positions is None else float(long_positions),
    "short_positions": None if short_positions is None else float(short_positions),
    "open_interest": None if open_interest is None else float(open_interest),
    "net_ratio": None,
  }
  if long_positions is None or short_positions is None:
    return "UNKNOWN", EvidenceAvailabilityStatus.MISSING, features
  if open_interest is None or open_interest == 0:
    return "UNKNOWN", EvidenceAvailabilityStatus.INSUFFICIENT, features
  net_ratio = (long_positions - short_positions) / float(open_interest)
  features["net_ratio"] = net_ratio
  if net_ratio >= PositioningClassifierConfig().long_bias_ratio:
    return "LONG_BIAS", EvidenceAvailabilityStatus.AVAILABLE, features
  if net_ratio <= PositioningClassifierConfig().short_bias_ratio:
    return "SHORT_BIAS", EvidenceAvailabilityStatus.AVAILABLE, features
  return "BALANCED", EvidenceAvailabilityStatus.AVAILABLE, features


def classify_data_freshness(
  *,
  decision_time: str,
  latest_available_time: str | None,
  config: FreshnessClassifierConfig | None = None,
) -> tuple[str, EvidenceAvailabilityStatus, dict[str, float | None]]:
  active = config or FreshnessClassifierConfig()
  features: dict[str, float | None] = {"age_hours": None}
  if not latest_available_time:
    return "UNKNOWN", EvidenceAvailabilityStatus.MISSING, features
  age_hours = _hours_between(latest_available_time, decision_time)
  features["age_hours"] = age_hours
  if age_hours < 0:
    return "UNKNOWN", EvidenceAvailabilityStatus.INSUFFICIENT, features
  if age_hours <= active.fresh_hours:
    return "FRESH", EvidenceAvailabilityStatus.AVAILABLE, features
  if age_hours >= active.stale_hours:
    return "STALE", EvidenceAvailabilityStatus.STALE, features
  return "AGING", EvidenceAvailabilityStatus.AVAILABLE, features


def dimension_id_for_classifier(version: str) -> StateDimensionId:
  if version.startswith("imp-xa05-yield-curve"):
    return StateDimensionId.RATES_CURVE_CONFIGURATION
  if version.startswith("imp-xa05-policy-rate"):
    return StateDimensionId.POLICY_RATE_LEVEL
  if version.startswith("imp-xa05-positioning"):
    return StateDimensionId.POSITIONING_CONCENTRATION
  if version.startswith("imp-xa05-freshness"):
    return StateDimensionId.DATA_FRESHNESS
  raise ValueError(f"unknown classifier version: {version}")


def _hours_between(earlier: str, later: str) -> float:
    from datetime import datetime, timezone

    def _parse(value: str) -> datetime:
        text = value.replace("Z", "+00:00")
        if len(text) == 10:
            parsed = datetime.fromisoformat(text)
            return parsed.replace(tzinfo=timezone.utc)
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    left = _parse(earlier)
    right = _parse(later)
    return (right - left).total_seconds() / 3600.0

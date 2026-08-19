"""SS P6 borrow normalization fixture adapter — fail-closed."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_LENDING_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "squeeze"
    / "lending_normalization_slice.json"
)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_lending_cross_lane_fields(
    fixture_path: Path | None = None,
) -> dict[str, Any]:
    """Map PIT lending fixture to borrow_normalization_score for donor cross_lane."""
    path = fixture_path or DEFAULT_LENDING_FIXTURE
    if not path.is_file():
        return {}

    payload = json.loads(path.read_text(encoding="utf-8"))
    current = payload.get("current")
    prior = payload.get("prior")
    if not isinstance(current, dict) or not isinstance(prior, dict):
        return {}

    try:
        from squeeze_core.intelligence.fuel import estimate_borrow_normalization
    except ImportError:
        return {}

    score = estimate_borrow_normalization(
        current_utilization=_optional_float(current.get("utilization_rate")),
        prior_utilization=_optional_float(prior.get("utilization_rate")),
        current_fee=_optional_float(current.get("fee_rate")),
        prior_fee=_optional_float(prior.get("fee_rate")),
    )
    if score is None:
        return {}
    return {"borrow_normalization_score": score}


__all__ = [
    "DEFAULT_LENDING_FIXTURE",
    "build_lending_cross_lane_fields",
]

"""Deterministic causal transition stream replay for SS P4/P6 fixture tests."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from ..normalization.equity_bars import iso_to_epoch_ns

DEFAULT_TRANSITION_STREAM_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "squeeze"
    / "causal_transition_stream.json"
)


@lru_cache(maxsize=1)
def _default_transition_payload_bytes() -> bytes:
    """Read the repository-pinned default fixture once as immutable bytes."""

    return DEFAULT_TRANSITION_STREAM_FIXTURE.read_bytes()


def replay_transition_stream(
    fixture_path: Path | None = None,
    *,
    as_of_time_ns: int | None = None,
) -> list[dict[str, Any]]:
    """Return causal transitions visible at as_of_time_ns (PIT-filtered, oldest first)."""
    raw = (
        _default_transition_payload_bytes()
        if fixture_path is None
        else Path(fixture_path).read_bytes()
    )
    payload = json.loads(raw.decode("utf-8"))
    transitions = payload.get("causal_state_transitions", [])
    if not isinstance(transitions, list):
        return []
    visible: list[dict[str, Any]] = []
    for item in transitions:
        if not isinstance(item, dict):
            continue
        changed_at = str(item.get("changed_at", ""))
        if not changed_at:
            continue
        if as_of_time_ns is not None and iso_to_epoch_ns(changed_at) > as_of_time_ns:
            continue
        visible.append(dict(item))
    return list(reversed(visible))


def extract_fuel_history(transitions: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract prior fuel/CVD metrics from the most recent transition with fuel fields."""
    for item in reversed(transitions):
        if not isinstance(item, dict):
            continue
        if not any(
            key in item
            for key in ("remaining_fuel", "cvd_slope", "reflexivity_strength")
        ):
            continue
        history: dict[str, Any] = {}
        if item.get("remaining_fuel") is not None:
            history["previous_remaining_fuel"] = item.get("remaining_fuel")
        if item.get("cvd_slope") is not None:
            history["previous_cvd_slope"] = item.get("cvd_slope")
        if item.get("reflexivity_strength") is not None:
            history["previous_reflexivity"] = item.get("reflexivity_strength")
        return history
    return {}


def extract_prior_cross_lane(transitions: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract prior cross-lane options snapshot hints from transition stream."""
    for item in reversed(transitions):
        if not isinstance(item, dict):
            continue
        prior = item.get("prior_cross_lane")
        if isinstance(prior, dict):
            return dict(prior)
    return {}


__all__ = [
    "DEFAULT_TRANSITION_STREAM_FIXTURE",
    "extract_fuel_history",
    "extract_prior_cross_lane",
    "replay_transition_stream",
]

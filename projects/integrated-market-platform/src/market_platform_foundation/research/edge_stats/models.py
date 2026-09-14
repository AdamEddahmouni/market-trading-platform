"""Frozen query and outcome models for edge-stats evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes

EDGE_STATS_QUERY_SCHEMA_VERSION = "1.0.0"
PIT_CLASS_HISTORICAL_BAR_END = "HISTORICAL_BAR_END_PIT"


@dataclass(frozen=True, slots=True)
class EdgeStatsOutcomeV1:
    """Declared outcome target for a historical match."""

    metric: str
    horizon_bars: int
    cost_model_version: str = "execution_book_aware_v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "cost_model_version": self.cost_model_version,
            "horizon_bars": self.horizon_bars,
            "metric": self.metric,
        }


@dataclass(frozen=True, slots=True)
class EdgeStatsQueryV1:
    """Version-hashed, immutable edge-stats query specification."""

    squeeze_states: tuple[str, ...]
    outcome: EdgeStatsOutcomeV1
    instrument_id: str = "BIYA"
    sample_cap: int | None = None
    pit_max_decision_time_ns: int | None = None
    schema_version: str = EDGE_STATS_QUERY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "outcome": self.outcome.to_dict(),
            "pit_max_decision_time_ns": self.pit_max_decision_time_ns,
            "sample_cap": self.sample_cap,
            "schema_version": self.schema_version,
            "squeeze_states": list(self.squeeze_states),
        }

    def version_hash(self) -> str:
        return sha256_bytes(canonical_bytes(self.to_dict()))


DEFAULT_EDGE_STATS_QUERY = EdgeStatsQueryV1(
    squeeze_states=("ACTIVE_SQUEEZE", "LIVE_CONFIRMATION"),
    outcome=EdgeStatsOutcomeV1(metric="mean_forward_return_bps", horizon_bars=30),
    sample_cap=500,
)

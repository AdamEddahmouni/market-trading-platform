"""Frozen replay query for options-flow evidence artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ...canonical import canonical_bytes, sha256_bytes

OPTIONS_FLOW_REPLAY_QUERY_SCHEMA_VERSION = "1.0.0"
PIT_CLASS_REPLAY_FIXTURE_AVAILABLE_TIME = "REPLAY_FIXTURE_AVAILABLE_TIME_PIT"
REPLAY_MODE_SYNTHETIC_FIXTURE_ONLY = "SYNTHETIC_FIXTURE_ONLY"


@dataclass(frozen=True, slots=True)
class OptionsFlowReplayQueryV1:
    """Version-hashed replay slice selector (fixture-bound, not live)."""

    admission_id: str
    instrument_id: str
    include_trade_classes: tuple[str, ...] = ("sweep", "block", "unclassified_print")
    schema_version: str = OPTIONS_FLOW_REPLAY_QUERY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "admission_id": self.admission_id,
            "include_trade_classes": list(self.include_trade_classes),
            "instrument_id": self.instrument_id,
            "schema_version": self.schema_version,
        }

    def version_hash(self) -> str:
        return sha256_bytes(canonical_bytes(self.to_dict()))


DEFAULT_OPTIONS_FLOW_REPLAY_QUERY = OptionsFlowReplayQueryV1(
    admission_id="ADMITTED-OPTIONS-FLOW-REPLAY-NVDA-001",
    instrument_id="NVDA",
)

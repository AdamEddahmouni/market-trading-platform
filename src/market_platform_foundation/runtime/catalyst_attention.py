"""Platform P1 catalyst and attention runtime interfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PRODUCER_VERSION = "platform_catalyst_attention_runtime_v1"


@dataclass(frozen=True, slots=True)
class CatalystAttentionSnapshot:
    instrument_id: str
    catalyst_count: int
    gated_catalyst_count: int
    max_catalyst_strength: float | None
    bullish_catalyst_count: int
    attention_velocity: float | None
    attention_acceleration: float | None
    runtime_available: bool
    provenance_ref: str = PRODUCER_VERSION


def catalyst_attention_snapshot_to_dict(item: CatalystAttentionSnapshot) -> dict[str, Any]:
    return {
        "instrument_id": item.instrument_id,
        "catalyst_count": item.catalyst_count,
        "gated_catalyst_count": item.gated_catalyst_count,
        "max_catalyst_strength": item.max_catalyst_strength,
        "bullish_catalyst_count": item.bullish_catalyst_count,
        "attention_velocity": item.attention_velocity,
        "attention_acceleration": item.attention_acceleration,
        "runtime_available": item.runtime_available,
        "provenance_ref": item.provenance_ref,
    }


class CatalystAttentionRuntime:
    """Derive platform-level catalyst/attention snapshot from MC8 summaries."""

    def build_snapshot(
        self,
        catalyst_summaries: list[dict[str, Any]],
        *,
        instrument_id: str,
    ) -> CatalystAttentionSnapshot:
        gated = [
            row
            for row in catalyst_summaries
            if isinstance(row, dict) and row.get("gate_ok") is True
        ]
        strengths = [
            float(row["catalyst_strength"])
            for row in gated
            if row.get("catalyst_strength") is not None
        ]
        bullish = [row for row in gated if str(row.get("lean", "")).upper() == "BULLISH"]
        confidences = strengths[:]
        attention_velocity = None
        attention_acceleration = None
        if len(confidences) >= 2:
            attention_velocity = confidences[-1] - confidences[-2]
        if len(confidences) >= 3:
            prior_velocity = confidences[-2] - confidences[-3]
            attention_acceleration = attention_velocity - prior_velocity if attention_velocity is not None else None
        elif len(confidences) == 1:
            attention_velocity = confidences[0] * 0.5
            attention_acceleration = attention_velocity

        return CatalystAttentionSnapshot(
            instrument_id=instrument_id.upper(),
            catalyst_count=len(catalyst_summaries),
            gated_catalyst_count=len(gated),
            max_catalyst_strength=max(strengths) if strengths else None,
            bullish_catalyst_count=len(bullish),
            attention_velocity=round(attention_velocity, 6) if attention_velocity is not None else None,
            attention_acceleration=round(attention_acceleration, 6)
            if attention_acceleration is not None
            else None,
            runtime_available=bool(gated),
        )


__all__ = [
    "CatalystAttentionRuntime",
    "CatalystAttentionSnapshot",
    "PRODUCER_VERSION",
    "catalyst_attention_snapshot_to_dict",
]

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
    max_attention_level: float | None
    max_information_value: float | None
    max_reflexive_impact: float | None
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
        "max_attention_level": item.max_attention_level,
        "max_information_value": item.max_information_value,
        "max_reflexive_impact": item.max_reflexive_impact,
        "runtime_available": item.runtime_available,
        "provenance_ref": item.provenance_ref,
    }


class CatalystAttentionRuntime:
    """Derive platform-level catalyst/attention snapshot from MC9 attention summaries."""

    def build_snapshot(
        self,
        attention_summaries: list[dict[str, Any]],
        *,
        instrument_id: str,
        catalyst_summaries: list[dict[str, Any]] | None = None,
    ) -> CatalystAttentionSnapshot:
        catalyst_rows = catalyst_summaries or []
        gated_catalyst = [
            row
            for row in catalyst_rows
            if isinstance(row, dict) and row.get("gate_ok") is True
        ]
        catalyst_strengths = [
            float(row["catalyst_strength"])
            for row in gated_catalyst
            if row.get("catalyst_strength") is not None
        ]
        bullish = [row for row in gated_catalyst if str(row.get("lean", "")).upper() == "BULLISH"]

        attention_rows = [
            row for row in attention_summaries if isinstance(row, dict) and row.get("attention_available")
        ]
        levels = [
            float(row["attention_level"])
            for row in attention_rows
            if row.get("attention_level") is not None
        ]
        velocities = [
            float(row["attention_velocity"])
            for row in attention_rows
            if row.get("attention_velocity") is not None
        ]
        accelerations = [
            float(row["attention_acceleration"])
            for row in attention_rows
            if row.get("attention_acceleration") is not None
        ]
        information_values = [
            float(row["information_value"])
            for row in attention_rows
            if row.get("information_value") is not None
        ]
        reflexive_impacts = [
            float(row["reflexive_impact"])
            for row in attention_rows
            if row.get("reflexive_impact") is not None
        ]

        return CatalystAttentionSnapshot(
            instrument_id=instrument_id.upper(),
            catalyst_count=len(catalyst_rows),
            gated_catalyst_count=len(gated_catalyst),
            max_catalyst_strength=max(catalyst_strengths) if catalyst_strengths else None,
            bullish_catalyst_count=len(bullish),
            attention_velocity=velocities[-1] if velocities else None,
            attention_acceleration=accelerations[-1] if accelerations else None,
            max_attention_level=max(levels) if levels else None,
            max_information_value=max(information_values) if information_values else None,
            max_reflexive_impact=max(reflexive_impacts) if reflexive_impacts else None,
            runtime_available=bool(attention_rows or gated_catalyst),
        )


__all__ = [
    "CatalystAttentionRuntime",
    "CatalystAttentionSnapshot",
    "PRODUCER_VERSION",
    "catalyst_attention_snapshot_to_dict",
]

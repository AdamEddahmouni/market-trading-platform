"""UI timing policy for deterministic detection vs async agent enrichment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class IntelligenceSurfacePhase(StrEnum):
    """Lifecycle phases for opportunity intelligence surfaces."""

    DETECTION_ONLY = "DETECTION_ONLY"
    AGENT_ENRICHMENT_PENDING = "AGENT_ENRICHMENT_PENDING"
    AGENT_ENRICHMENT_PARTIAL = "AGENT_ENRICHMENT_PARTIAL"
    AGENT_ENRICHMENT_COMPLETE = "AGENT_ENRICHMENT_COMPLETE"


@dataclass(frozen=True, slots=True)
class UiIntelligenceRenderGate:
    """Result of the non-blocking UI readiness check."""

    allowed: bool
    phase: IntelligenceSurfacePhase
    reason_code: str


def evaluate_ui_intelligence_render_gate(
    *,
    deterministic_detection: dict[str, Any] | None,
    wait_for_agent_enrichment: bool,
    agent_enrichment_count: int = 0,
    agent_enrichment_expected: bool = False,
) -> UiIntelligenceRenderGate:
    """Deterministic detection must be sufficient to render; agents enrich later.

    Raises ValueError when callers attempt to block the UI on agent workers.
    """
    if wait_for_agent_enrichment:
        raise ValueError("UI_BLOCKED_ON_AGENT_ENRICHMENT")
    if deterministic_detection is None:
        return UiIntelligenceRenderGate(
            allowed=False,
            phase=IntelligenceSurfacePhase.DETECTION_ONLY,
            reason_code="DETERMINISTIC_DETECTION_MISSING",
        )
    if agent_enrichment_count <= 0:
        phase = (
            IntelligenceSurfacePhase.AGENT_ENRICHMENT_PENDING
            if agent_enrichment_expected
            else IntelligenceSurfacePhase.DETECTION_ONLY
        )
        return UiIntelligenceRenderGate(
            allowed=True,
            phase=phase,
            reason_code="DETECTION_READY",
        )
    phase = (
        IntelligenceSurfacePhase.AGENT_ENRICHMENT_COMPLETE
        if not agent_enrichment_expected
        else IntelligenceSurfacePhase.AGENT_ENRICHMENT_PARTIAL
    )
    return UiIntelligenceRenderGate(
        allowed=True,
        phase=phase,
        reason_code="DETECTION_READY_WITH_ENRICHMENT",
    )


__all__ = [
    "IntelligenceSurfacePhase",
    "UiIntelligenceRenderGate",
    "evaluate_ui_intelligence_render_gate",
]

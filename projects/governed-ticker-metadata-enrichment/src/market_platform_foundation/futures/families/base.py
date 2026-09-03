"""FuturesFamilyModel protocol — per-family interpretation branches (F6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from ...contracts.futures import FuturesFamily

FAMILY_MODEL_VERSION = "futures_family_v1"


@dataclass(frozen=True, slots=True)
class FamilyContextSnapshot:
    """Structured family interpretation — not a directional forecast."""

    family: FuturesFamily
    model_version: str
    curve_read: str
    positioning_read: str
    event_context_read: str
    risk_context: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    provenance_ref: str = "futures:family_model_v1"


def family_context_to_dict(snapshot: FamilyContextSnapshot) -> dict[str, Any]:
    return {
        "family": snapshot.family.value,
        "model_version": snapshot.model_version,
        "curve_read": snapshot.curve_read,
        "positioning_read": snapshot.positioning_read,
        "event_context_read": snapshot.event_context_read,
        "risk_context": snapshot.risk_context,
        "quality_flags": list(snapshot.quality_flags),
        "provenance_ref": snapshot.provenance_ref,
    }


class FuturesFamilyModel(Protocol):
    """Per-family plugin interface per FUTURES_TARGET_ARCHITECTURE §7."""

    family: FuturesFamily
    model_version: str

    def required_capabilities(self) -> tuple[str, ...]:
        """Capabilities required before family interpretation proceeds."""
        ...

    def curve_interpretation(self, workspace_context: dict[str, Any]) -> str:
        """Human-readable curve/carry read for this family."""
        ...

    def positioning_interpretation(self, workspace_context: dict[str, Any]) -> str:
        """Human-readable positioning read for this family."""
        ...

    def event_context(self, macro_snapshot: dict[str, Any] | None) -> str:
        """Family-specific macro/event sensitivity read."""
        ...

    def risk_features(self, leverage_snapshot: dict[str, Any] | None) -> str:
        """Family-specific leverage/liquidation context read."""
        ...

    def build_context_snapshot(
        self,
        workspace_context: dict[str, Any],
        *,
        macro_snapshot: dict[str, Any] | None = None,
        leverage_snapshot: dict[str, Any] | None = None,
    ) -> FamilyContextSnapshot:
        """Compose full family context from upstream workspace fields."""
        ...

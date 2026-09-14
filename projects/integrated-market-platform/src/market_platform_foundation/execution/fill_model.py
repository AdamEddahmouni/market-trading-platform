"""Shared fill-model contract, provenance, and Live fail-closed.

IMP simulation fills are Layer B (hypothetical Paper). They are never market
ground truth. Stamp identity after fill_id hashing so deterministic replay
keeps a stable fill_id.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..git_ref import read_git_head

SIMULATION_EVIDENCE_LAYER = "IMP_EXECUTION_SIMULATION"
FILL_CLOCK_KIND_BAR_AVAILABLE = "bar_available_time"
ORDER_CREATED_CLOCK_KIND = "intent_created_time"
NOT_MARKET_TRUTH_STATEMENT = (
    "IMP internal simulation fills, rejects, and P&L are hypothetical. "
    "They are not market ground truth and must not be labeled calibrated "
    "or validated from software tests alone."
)
LIVE_EXECUTION_FORBIDDEN = "SIM_LIVE_EXECUTION_FORBIDDEN"


class FillModelLiveForbidden(ValueError):
    """Live execution is unreachable from IMP fill models."""


class FillModel(Protocol):
    """Bar, book-aware, and other IMP simulators share this simulate shape."""

    registry_id: str

    def simulate(
        self,
        *,
        intent: dict[str, Any],
        risk_decision: dict[str, Any],
        bars: list[dict[str, Any]],
        squeeze_context: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        ...


def resolve_simulation_execution_mode(raw: Any) -> str:
    mode = str(raw or "INTERNAL_SIMULATION").strip().upper()
    if not mode:
        return "INTERNAL_SIMULATION"
    return mode


def assert_simulation_execution_allowed(execution_mode: Any) -> str:
    """Paper/Demo simulation only. Live orders remain forbidden."""

    mode = resolve_simulation_execution_mode(execution_mode)
    if mode == "LIVE":
        raise FillModelLiveForbidden(LIVE_EXECUTION_FORBIDDEN)
    return mode


def simulation_provenance_envelope(
    *,
    simulator_version: str,
    source_capability: str,
    registry_id: str,
    execution_mode: str,
    git_sha: str | None = None,
) -> dict[str, Any]:
    return {
        "simulator_version": simulator_version,
        "source_capability": source_capability,
        "fill_model_registry_id": registry_id,
        "evidence_layer": SIMULATION_EVIDENCE_LAYER,
        "is_market_truth": False,
        "not_market_truth_statement": NOT_MARKET_TRUTH_STATEMENT,
        "execution_mode": execution_mode,
        "fill_clock_kind": FILL_CLOCK_KIND_BAR_AVAILABLE,
        "order_created_clock_kind": ORDER_CREATED_CLOCK_KIND,
        "git_sha": git_sha or read_git_head() or "UNAVAILABLE",
    }


def stamp_fill_model_provenance(
    *,
    order: dict[str, Any],
    fill: dict[str, Any] | None,
    simulator_version: str,
    source_capability: str,
    registry_id: str,
    execution_mode: str,
    git_sha: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Attach reconstructable fill-model identity without changing fill_id."""

    envelope = simulation_provenance_envelope(
        simulator_version=simulator_version,
        source_capability=source_capability,
        registry_id=registry_id,
        execution_mode=execution_mode,
        git_sha=git_sha,
    )
    order.update(envelope)
    if not order.get("allocation_model"):
        order["allocation_model"] = simulator_version
    if fill is not None:
        fill.update(envelope)
        if fill.get("submit_time_ns") is None and order.get("created_time") is not None:
            fill["submit_time_ns"] = order.get("created_time")
    return order, fill


__all__ = [
    "FILL_CLOCK_KIND_BAR_AVAILABLE",
    "FillModel",
    "FillModelLiveForbidden",
    "LIVE_EXECUTION_FORBIDDEN",
    "NOT_MARKET_TRUTH_STATEMENT",
    "ORDER_CREATED_CLOCK_KIND",
    "SIMULATION_EVIDENCE_LAYER",
    "assert_simulation_execution_allowed",
    "resolve_simulation_execution_mode",
    "simulation_provenance_envelope",
    "stamp_fill_model_provenance",
]

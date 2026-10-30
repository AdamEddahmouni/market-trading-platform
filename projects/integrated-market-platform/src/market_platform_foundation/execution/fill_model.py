"""Shared fill-model contract, provenance, and Live fail-closed.

IMP simulation fills are Layer B (hypothetical Paper). They are never market
ground truth. Stamp identity after fill_id hashing so deterministic replay
keeps a stable fill_id.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol

from ..build_identity import UNAVAILABLE, provenance_fields

SIMULATION_EVIDENCE_LAYER = "IMP_EXECUTION_SIMULATION"
FILL_CLOCK_KIND_BAR_AVAILABLE = "bar_available_time"
ORDER_CREATED_CLOCK_KIND = "intent_created_time"
NOT_MARKET_TRUTH_STATEMENT = (
    "IMP internal simulation fills, rejects, and P&L are hypothetical. "
    "They are not market ground truth and must not be labeled calibrated "
    "or validated from software tests alone."
)
LIVE_EXECUTION_FORBIDDEN = "SIM_LIVE_EXECUTION_FORBIDDEN"
# The build fields every stamped order and fill carries: the source revision (``git_sha``, kept for existing
# readers), the release build id and where the revision came from (build_identity.py). A deployed tree without git
# metadata reads them from its BUILD-IDENTITY.json; nothing here guesses a revision (AUD-037).
BUILD_PROVENANCE_KEYS = ("git_sha", "build_id", "revision_source")
REVISION_SOURCE_CALLER = "CALLER_SUPPLIED"


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
    build_provenance: Mapping[str, Any] | None = None,
    price_source: str | None = None,
    bar_construction: str | None = None,
) -> dict[str, Any]:
    envelope = {
        "simulator_version": simulator_version,
        "source_capability": source_capability,
        "fill_model_registry_id": registry_id,
        "evidence_layer": SIMULATION_EVIDENCE_LAYER,
        "is_market_truth": False,
        "not_market_truth_statement": NOT_MARKET_TRUTH_STATEMENT,
        "execution_mode": execution_mode,
        "fill_clock_kind": FILL_CLOCK_KIND_BAR_AVAILABLE,
        "order_created_clock_kind": ORDER_CREATED_CLOCK_KIND,
    }
    envelope.update(_build_fields(git_sha, build_provenance))
    # AUD-014: which events actually priced the fill. ``source_capability`` stays the simulator's contract value
    # (fill_model_id and experiment identities depend on it); these additive fields say what the bars were built
    # from, e.g. LIVE_L1_SNAPSHOT quotes rather than vendor one-minute bars.
    if price_source:
        envelope["price_source"] = price_source
    if bar_construction:
        envelope["bar_construction"] = bar_construction
    return envelope


def _build_fields(git_sha: str | None, build_provenance: Mapping[str, Any] | None) -> dict[str, Any]:
    if build_provenance:
        return {key: build_provenance.get(key) or UNAVAILABLE for key in BUILD_PROVENANCE_KEYS}
    if git_sha:
        return {"git_sha": git_sha, "build_id": UNAVAILABLE, "revision_source": REVISION_SOURCE_CALLER}
    return provenance_fields()


def build_provenance_of(record: Mapping[str, Any]) -> dict[str, Any] | None:
    """The build fields already stamped on ``record``, for a restamp that must not re-resolve them."""
    if not record.get("revision_source"):
        return None
    return {key: record.get(key) for key in BUILD_PROVENANCE_KEYS}


def stamp_fill_model_provenance(
    *,
    order: dict[str, Any],
    fill: dict[str, Any] | None,
    simulator_version: str,
    source_capability: str,
    registry_id: str,
    execution_mode: str,
    git_sha: str | None = None,
    build_provenance: Mapping[str, Any] | None = None,
    price_source: str | None = None,
    bar_construction: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Attach reconstructable fill-model identity without changing fill_id."""

    envelope = simulation_provenance_envelope(
        simulator_version=simulator_version,
        source_capability=source_capability,
        registry_id=registry_id,
        execution_mode=execution_mode,
        git_sha=git_sha,
        build_provenance=build_provenance,
        price_source=price_source,
        bar_construction=bar_construction,
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
    "BUILD_PROVENANCE_KEYS",
    "FILL_CLOCK_KIND_BAR_AVAILABLE",
    "FillModel",
    "FillModelLiveForbidden",
    "LIVE_EXECUTION_FORBIDDEN",
    "NOT_MARKET_TRUTH_STATEMENT",
    "ORDER_CREATED_CLOCK_KIND",
    "SIMULATION_EVIDENCE_LAYER",
    "assert_simulation_execution_allowed",
    "build_provenance_of",
    "resolve_simulation_execution_mode",
    "simulation_provenance_envelope",
    "stamp_fill_model_provenance",
]

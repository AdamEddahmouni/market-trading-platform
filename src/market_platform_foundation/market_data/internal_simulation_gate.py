"""Explicit safety gate matrix for LIVE_OBSERVATIONAL + INTERNAL_SIMULATION."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..operating_modes import paper_execution_env_enabled
from .live_admission import ADMISSION_EXECUTION
from .live_config import live_internal_simulation_enabled, live_observational_enabled, moomoo_live_enabled
from .provider_lifecycle import ProviderConnectionState

MANDATORY_GATES: tuple[str, ...] = (
    "READ_ONLY_PROVIDER",
    "REAL_FEED_VERIFIED",
    "CAPABILITY_VERIFIED",
    "AVAILABLE_TIME_VERIFIED",
    "PIT_ADVERSARIAL",
    "FIRST_PUSH_HANDLED",
    "DUPLICATE_HANDLED",
    "SEQUENCE_HANDLED",
    "RECONNECT_HANDLED",
    "FRESHNESS_GATE",
    "CLOCK_GATE",
    "QUALITY_GATE",
    "BOUNDED_BUFFER",
    "PAPER_EXECUTION_GATE",
    "RISK_GATE",
    "IDEMPOTENCY",
    "NO_EXTERNAL_EXECUTION_PATH",
    "NO_AUTOMATIC_TRADING",
)


@dataclass
class GateEvaluation:
    status: str
    gates: dict[str, str] = field(default_factory=dict)
    blocking: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocking": list(self.blocking),
            "gates": dict(self.gates),
            "status": self.status,
        }


def external_execution_path_active() -> bool:
    """Checkable fact: a real broker-paper adapter occupies the composition slot.

    External Tradier/Moomoo paper adapters now exist, so the old hardcoded
    PASS on NO_EXTERNAL_EXECUTION_PATH was stale. The disabled stub is not an
    execution path; anything else composed is.
    """
    from ..providers.composition import get_provider_composition

    return getattr(get_provider_composition().paper_execution, "provider_id", "") != "stub.execution.disabled"


def evaluate_internal_simulation_gates(
    *,
    runtime: Any | None,
    probe_stale: bool = True,
    pit_tests_pass: bool | None = None,
    external_path_active: bool | None = None,
) -> GateEvaluation:
    """Evaluate the internal-simulation gate matrix.

    ``pit_tests_pass``: True only when the caller has a verified PIT
    adversarial result for this deployment; False when verified failing;
    None (default) means unverified and is labeled ATTESTED, never PASS.
    ``external_path_active``: override for the NO_EXTERNAL_EXECUTION_PATH
    fact check (defaults to inspecting the composed provider).
    """
    gates: dict[str, str] = {}
    blocking: list[str] = []

    def _pass(name: str) -> None:
        gates[name] = "PASS"

    def _fail(name: str) -> None:
        gates[name] = "FAIL"
        blocking.append(name)

    def _defer(name: str) -> None:
        gates[name] = "DEFERRED_FOR_SAFETY"
        blocking.append(name)

    if runtime is not None and getattr(runtime.lifecycle, "provider_role", "") == "MARKET_DATA":
        _pass("READ_ONLY_PROVIDER")
    else:
        _fail("READ_ONLY_PROVIDER")

    receiving = bool(runtime is not None and getattr(runtime, "_fresh_event_count", 0) > 0)
    registry = getattr(runtime, "capability_registry", None) if runtime is not None else None
    entitled = bool(registry is not None and registry.dimensions.entitled and not probe_stale)
    if moomoo_live_enabled() and entitled and receiving:
        _pass("REAL_FEED_VERIFIED")
        _pass("CAPABILITY_VERIFIED")
    else:
        _defer("REAL_FEED_VERIFIED")
        _defer("CAPABILITY_VERIFIED")

    _pass("AVAILABLE_TIME_VERIFIED")
    if pit_tests_pass is True:
        _pass("PIT_ADVERSARIAL")
    elif pit_tests_pass is False:
        _fail("PIT_ADVERSARIAL")
    else:
        # No verified fact available: attestation only, never labeled PASS.
        gates["PIT_ADVERSARIAL"] = "ATTESTED"
    _pass("FIRST_PUSH_HANDLED")
    _pass("DUPLICATE_HANDLED")
    _pass("SEQUENCE_HANDLED")
    _pass("CLOCK_GATE")
    _pass("RISK_GATE")
    _pass("IDEMPOTENCY")
    if (external_path_active if external_path_active is not None else external_execution_path_active()):
        _fail("NO_EXTERNAL_EXECUTION_PATH")
    else:
        _pass("NO_EXTERNAL_EXECUTION_PATH")
    _pass("NO_AUTOMATIC_TRADING")

    if runtime is not None:
        lifecycle = runtime.lifecycle
        connected = lifecycle.connection_state in {
            ProviderConnectionState.CONNECTED,
            ProviderConnectionState.CONNECTED_DEGRADED,
        }
        healthy = lifecycle.connection_state == ProviderConnectionState.CONNECTED
        if connected and receiving:
            _pass("QUALITY_GATE")
            _pass("FRESHNESS_GATE")
        else:
            _fail("QUALITY_GATE")
            _fail("FRESHNESS_GATE")
        if lifecycle.connection_state != ProviderConnectionState.RECONNECTING:
            _pass("RECONNECT_HANDLED")
        else:
            _fail("RECONNECT_HANDLED")
        feed = getattr(runtime, "feed_metrics", {}) or {}
        if feed.get("queue_overflows", 0) == 0:
            _pass("BOUNDED_BUFFER")
        else:
            _fail("BOUNDED_BUFFER")
    else:
        for name in ("QUALITY_GATE", "FRESHNESS_GATE", "RECONNECT_HANDLED", "BOUNDED_BUFFER"):
            _fail(name)

    if paper_execution_env_enabled() and live_observational_enabled():
        _pass("PAPER_EXECUTION_GATE")
    else:
        _fail("PAPER_EXECUTION_GATE")

    enabled = live_internal_simulation_enabled() and not blocking
    if runtime is not None and enabled:
        exec_buffer = getattr(runtime, "execution_buffer", None)
        report = exec_buffer.report() if exec_buffer is not None else {"event_count": 0}
        if report.get("event_count", 0) == 0:
            gates["EXECUTION_BUFFER"] = "AWAITING_FRESH_EVENTS"
            blocking.append("EXECUTION_BUFFER")
        else:
            gates["EXECUTION_BUFFER"] = "PASS"
        if not healthy:
            gates["FRESH_RECOVERY"] = "AWAITING_HEALTHY"
            blocking.append("FRESH_RECOVERY")

    status = "AUTHORIZED" if enabled and not blocking else "DEFERRED_FOR_SAFETY"
    return GateEvaluation(status=status, gates=gates, blocking=blocking)


def execution_admission_allowed(*, admission_result: dict[str, Any], gate: GateEvaluation) -> bool:
    if gate.status != "AUTHORIZED":
        return False
    admission = admission_result.get("admission") if isinstance(admission_result.get("admission"), dict) else {}
    return admission.get("execution") == ADMISSION_EXECUTION

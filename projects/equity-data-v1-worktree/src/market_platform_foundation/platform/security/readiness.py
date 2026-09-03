"""Deterministic health/readiness payload builder (Platformization P5).

Pure aggregation of operating mode and safety-gate state into a readiness
document. Mirrors the *shape* of the ``safety`` block in
``ui_api/operator_projections.py`` (gate-name → boolean map) without
importing UI internals, so it can serve a future hosted ``/healthz`` or
``/readyz`` surface without coupling to the localhost UI API.

Determinism contract: the payload is a pure function of its arguments — no
wall clock, no environment reads. Identical inputs produce byte-identical
JSON via :func:`render_readiness_json`.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

READINESS_SCHEMA = "platform/readiness/1.0.0"

STATUS_READY = "READY"
STATUS_NOT_READY = "NOT_READY"
READYNESS_STATUSES: tuple[str, ...] = (STATUS_READY, STATUS_NOT_READY)


def collect_default_gates(env: Mapping[str, str]) -> dict[str, bool]:
    """Snapshot the platform's fail-closed env gates from an env mapping.

    Kept as an explicit-mapping function (not ``os.environ``) so the core
    stays deterministic; callers that want live env pass ``os.environ``.
    Gate names intentionally match the operator ``safety`` projection shape.
    """

    def flag(name: str) -> bool:
        return env.get(name) == "1"

    return {
        "IMP_BROKER_PAPER_EXECUTION": flag("IMP_BROKER_PAPER_EXECUTION"),
        "IMP_LIVE_EXECUTION": flag("IMP_LIVE_EXECUTION"),
        "IMP_LIVE_INTERNAL_SIMULATION": flag("IMP_LIVE_INTERNAL_SIMULATION"),
        "IMP_LIVE_OBSERVATIONAL": flag("IMP_LIVE_OBSERVATIONAL"),
        "IMP_MOOMOO_LIVE": flag("IMP_MOOMOO_LIVE"),
        "IMP_PAPER_EXECUTION": flag("IMP_PAPER_EXECUTION"),
    }


def build_readiness_payload(
    *,
    gates: Mapping[str, bool],
    mode_context: Mapping[str, Any] | None = None,
    checks: Mapping[str, str] | None = None,
    schema: str = READINESS_SCHEMA,
) -> dict[str, Any]:
    """Build the deterministic readiness document.

    ``gates`` — gate-name → satisfied boolean; any false gate makes the
    overall status ``NOT_READY`` with the sorted failing list.
    ``mode_context`` — optional operating-mode fields (data_mode /
    execution_mode / execution_authority) carried through verbatim.
    ``checks`` — optional component name → status string (e.g.
    ``"OK"`` / ``"DEGRADED"``), reported but not folded into status.
    """

    ordered_gates = {key: bool(gates[key]) for key in sorted(gates)}
    failing_gates = [key for key, ok in ordered_gates.items() if not ok]
    return {
        "checks": {key: str(checks[key]) for key in sorted(checks)} if checks else {},
        "failing_gates": failing_gates,
        "gates": ordered_gates,
        "mode": dict(sorted(mode_context.items())) if mode_context else {},
        "schema": schema,
        "status": STATUS_READY if not failing_gates else STATUS_NOT_READY,
    }


def render_readiness_json(payload: Mapping[str, Any]) -> str:
    """Canonical compact JSON rendering (sorted keys)."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)

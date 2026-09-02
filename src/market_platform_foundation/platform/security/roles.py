"""Operator roles model with enforceable capability matrix (Platformization P5, TD-005).

Records the minimal role/capability matrix enforced when auth enforcement mode is
``ENFORCED``. Under default ``LOOPBACK_TRUST``, the UI API grants implicit local ADMIN
without session validation (roadmap decision 6 preserved for loopback).

Enforcement status is carried via :func:`role_enforcement_status` and must be
surfaced wherever this matrix is consumed.
"""

from __future__ import annotations

from enum import Enum

ROLE_MODEL_SCHEMA = "platform/roles/1.0.0"

ROLE_ENFORCEMENT_LOOPBACK_TRUST = "LOOPBACK_TRUST"
ROLE_ENFORCEMENT_ENFORCED = "ENFORCED"
# Default at import reflects loopback-trust posture; use role_enforcement_status() for runtime value.
ROLE_ENFORCEMENT_STATUS = ROLE_ENFORCEMENT_LOOPBACK_TRUST


class OperatorRole(str, Enum):
    """Minimal operator roles for a future hosted surface."""

    VIEWER = "VIEWER"
    OPERATOR = "OPERATOR"
    ADMIN = "ADMIN"


OPERATOR_ROLES: tuple[OperatorRole, ...] = (
    OperatorRole.VIEWER,
    OperatorRole.OPERATOR,
    OperatorRole.ADMIN,
)

CAPABILITIES: tuple[str, ...] = (
    "state.read",
    "state.write",
    "paper.order.submit",
    "paper.order.cancel",
    "audit.read",
    "security.config.read",
    "security.config.write",
    "operator.lifecycle.write",
    "role.manage",
)

_CAPABILITY_SET: frozenset[str] = frozenset(CAPABILITIES)


def _froze(*names: str) -> frozenset[str]:
    unknown = set(names) - _CAPABILITY_SET
    if unknown:
        raise ValueError(f"unknown capabilities: {sorted(unknown)}")
    return frozenset(names)


ROLE_CAPABILITY_MATRIX: dict[OperatorRole, frozenset[str]] = {
    OperatorRole.VIEWER: _froze(
        "state.read",
        "audit.read",
        "security.config.read",
    ),
    OperatorRole.OPERATOR: _froze(
        "state.read",
        "state.write",
        "paper.order.submit",
        "paper.order.cancel",
        "audit.read",
        "security.config.read",
        "operator.lifecycle.write",
    ),
    # ADMIN holds every capability by construction (invariant-checked below).
    OperatorRole.ADMIN: _CAPABILITY_SET,
}


class RoleModelError(ValueError):
    """Raised when the capability matrix violates its structural invariants."""


def assert_matrix_invariants() -> None:
    """Fail loudly if the matrix stops being a monotone total order.

    Invariants: every entry uses known capabilities only; VIEWER ⊆ OPERATOR ⊆
    ADMIN; ADMIN is total (holds all capabilities).
    """

    for role, caps in ROLE_CAPABILITY_MATRIX.items():
        unknown = set(caps) - _CAPABILITY_SET
        if unknown:
            raise RoleModelError(f"{role} carries unknown capabilities: {sorted(unknown)}")
    viewer = ROLE_CAPABILITY_MATRIX[OperatorRole.VIEWER]
    operator = ROLE_CAPABILITY_MATRIX[OperatorRole.OPERATOR]
    admin = ROLE_CAPABILITY_MATRIX[OperatorRole.ADMIN]
    if not viewer <= operator:
        raise RoleModelError("VIEWER capabilities must be a subset of OPERATOR")
    if not operator <= admin:
        raise RoleModelError("OPERATOR capabilities must be a subset of ADMIN")
    if admin != _CAPABILITY_SET:
        raise RoleModelError("ADMIN must hold every declared capability")


assert_matrix_invariants()


def capabilities_for_role(role: OperatorRole) -> frozenset[str]:
    """Return the capability set for a role."""

    return ROLE_CAPABILITY_MATRIX[role]


def role_allows(role: OperatorRole, capability: str) -> bool:
    """Pure capability check against the operator role matrix."""

    return capability in ROLE_CAPABILITY_MATRIX[role]


def role_enforcement_status() -> str:
    """Return enforcement sentinel for the active auth configuration."""

    from .access_control import role_enforcement_status as _runtime_status

    return _runtime_status()

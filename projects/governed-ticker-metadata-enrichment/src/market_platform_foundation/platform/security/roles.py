"""Operator roles model — data only, no enforcement (Platformization P5).

Records, as plain data, the minimal role/capability matrix a future hosted
deployment would enforce. NOTHING in the platform enforces these roles
today: the localhost UI API is unauthenticated by design (roadmap decision 6,
"No custom JWT, no hosted auth" — P0-locked). This module exists so the
future enforcement conversation starts from a written model instead of
ad-hoc role strings.

Enforcement status is carried in :data:`ROLE_ENFORCEMENT_STATUS` and must be
surfaced wherever this matrix is consumed, so the model can never be mistaken
for an active control.
"""

from __future__ import annotations

from enum import Enum

ROLE_MODEL_SCHEMA = "platform/roles/1.0.0"

ROLE_ENFORCEMENT_STATUS = "MODEL_ONLY_NOT_ENFORCED"


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
    """Pure capability check. NOT wired to any request path (see module docstring)."""

    return capability in ROLE_CAPABILITY_MATRIX[role]

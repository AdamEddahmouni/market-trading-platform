"""XA-05 authority and ownership audit matrix."""

from __future__ import annotations

AUTHORITY_AUDIT_MATRIX: tuple[dict[str, str], ...] = (
    {
        "boundary": "execution_transport",
        "xa05_action": "no broker or order imports in xa05 package",
        "authority_granted": "no",
    },
    {
        "boundary": "risk_limits",
        "xa05_action": "state objects are informational only",
        "authority_granted": "no",
    },
    {
        "boundary": "xa04_catalog",
        "xa05_action": "read-only catalog queries; no catalog mutation",
        "authority_granted": "no",
    },
    {
        "boundary": "xa01_identity",
        "xa05_action": "preserve canonical references; no identity mutation",
        "authority_granted": "no",
    },
    {
        "boundary": "persistence",
        "xa05_action": "ephemeral reconstructable snapshots only",
        "authority_granted": "no",
    },
)


def audit_matrix() -> list[dict[str, str]]:
    return [dict(row) for row in AUTHORITY_AUDIT_MATRIX]

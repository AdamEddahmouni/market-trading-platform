"""Canonical Finviz Elite API-token environment names.

Prospective news ingress and the screener credential manager both read this
tuple. Login username/password is a different credential type used only for
screener token recovery.

Precedence is list order: the first present, non-placeholder value wins.
``FINVIZ_ELITE_AUTH``, ``FINVIZ_AUTH``, and ``IMP_FINVIZ_ELITE_AUTH`` are
not recognized.
"""

from __future__ import annotations

FINVIZ_TOKEN_NAMES = (
    "FINVIZ_API_KEY",
    "FINVIZ_AUTH_TOKEN",
    "FINVIZ_API_TOKEN",
    "FINVIZ_ELITE_TOKEN",
    "IMP_FINVIZ_ELITE_TOKEN",
    "IMP_FINVIZ_TOKEN",
)

_PLACEHOLDERS = frozenset({"", "CHANGEME", "EXAMPLE", "PLACEHOLDER", "NOT_A_SECRET"})


def token_value_present(value: str | None) -> bool:
    return str(value or "").strip().upper() not in _PLACEHOLDERS

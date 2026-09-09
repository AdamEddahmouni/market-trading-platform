"""G12 — runtime domain status vocabulary.

Distinct from provider capability state and portfolio valuation status.
Do not collapse AVAILABLE / EMPTY / UNAVAILABLE / NOT_ENTITLED / DELAYED /
STALE / INVALID / UNSUPPORTED_INSTRUMENT into bare None or [].
"""

from __future__ import annotations

from enum import StrEnum


class RuntimeDomainStatus(StrEnum):
    """Product/runtime projection status for a canonical instrument domain."""

    AVAILABLE = "AVAILABLE"
    EMPTY = "EMPTY"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_ENTITLED = "NOT_ENTITLED"
    DELAYED = "DELAYED"
    STALE = "STALE"
    INVALID = "INVALID"
    UNSUPPORTED_INSTRUMENT = "UNSUPPORTED_INSTRUMENT"


__all__ = ["RuntimeDomainStatus"]

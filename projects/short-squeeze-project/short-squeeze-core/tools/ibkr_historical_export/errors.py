"""Deterministic IBKR error-code classification (ibapi-free, unit-testable).

Maps provider numeric error codes to the tool's historical-status taxonomy. Farm/
connectivity notifications are treated as diagnostics, not request failures. A code-162
"query returned no data" response is an empty *successful* window, never a fabricated
error.
"""

from __future__ import annotations

from .statuses import HistoricalStatus

# System/connectivity notifications -- never end a request by themselves.
_NON_ENDING_CODES: frozenset[int] = frozenset(range(2100, 2200)) | {1100, 1101, 1102}

# Missing market-data permission / subscription.
PERMISSION_CODES: frozenset[int] = frozenset({354, 10167, 10168, 10187, 10197, 10225})

# Historical series genuinely unavailable / bad query.
DATA_UNAVAILABLE_CODES: frozenset[int] = frozenset({162, 165, 166, 200, 320, 321, 322, 366, 430})


def is_request_ending(code: int) -> bool:
    """True when an error code terminates the associated request."""
    return code not in _NON_ENDING_CODES


def is_no_data_empty(code: int, message: str) -> bool:
    """True when a code-162 response indicates a genuinely empty (not failed) window."""
    return code == 162 and "no data" in (message or "").lower()


def classify_historical_error(code: int, message: str = "") -> HistoricalStatus:
    """Classify a request-ending historical error code into a status."""
    if is_no_data_empty(code, message):
        return HistoricalStatus.SUCCESS_EMPTY
    if code in PERMISSION_CODES:
        return HistoricalStatus.HISTORICAL_PERMISSION_DENIED
    if code in DATA_UNAVAILABLE_CODES:
        return HistoricalStatus.HISTORICAL_DATA_UNAVAILABLE
    return HistoricalStatus.HISTORICAL_REQUEST_ERROR


# Transient connectivity/farm conditions that justify at most one retry.
TRANSIENT_RETRY_CODES: frozenset[int] = frozenset({1100, 1101, 1102, 2103, 2105, 2157})


def is_transient(code: int) -> bool:
    return code in TRANSIENT_RETRY_CODES


# Socket-level or TWS connectivity loss — the session must reconnect before new requests.
DISCONNECT_CODES: frozenset[int] = frozenset({1100, 2110})


def is_disconnect(code: int) -> bool:
    return code in DISCONNECT_CODES


__all__ = [
    "PERMISSION_CODES",
    "DATA_UNAVAILABLE_CODES",
    "TRANSIENT_RETRY_CODES",
    "DISCONNECT_CODES",
    "is_request_ending",
    "is_no_data_empty",
    "classify_historical_error",
    "is_transient",
    "is_disconnect",
]

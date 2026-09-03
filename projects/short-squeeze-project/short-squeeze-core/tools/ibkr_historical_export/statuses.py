"""Deterministic status vocabulary for the IBKR collection tool.

These string enums are the only status values written to private artifacts and the
sanitized committed summary. They never carry bar values or account data.
"""

from __future__ import annotations

from enum import StrEnum


class CollectionStatus(StrEnum):
    """Connection-level status."""

    CONNECTION_SUCCESS = "CONNECTION_SUCCESS"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    OFFICIAL_API_CLIENT_MISSING = "OFFICIAL_API_CLIENT_MISSING"


class ContractStatus(StrEnum):
    """Outcome-blind contract-resolution status."""

    CONTRACT_RESOLVED = "CONTRACT_RESOLVED"
    CONTRACT_NOT_RESOLVED = "CONTRACT_NOT_RESOLVED"
    CONTRACT_AMBIGUOUS = "CONTRACT_AMBIGUOUS"


class HistoricalStatus(StrEnum):
    """Per-request historical-bar status."""

    HISTORICAL_REQUEST_SUCCESS = "HISTORICAL_REQUEST_SUCCESS"
    SUCCESS_EMPTY = "SUCCESS_EMPTY"
    HISTORICAL_REQUEST_TIMEOUT = "HISTORICAL_REQUEST_TIMEOUT"
    HISTORICAL_PERMISSION_DENIED = "HISTORICAL_PERMISSION_DENIED"
    HISTORICAL_DATA_UNAVAILABLE = "HISTORICAL_DATA_UNAVAILABLE"
    HISTORICAL_REQUEST_ERROR = "HISTORICAL_REQUEST_ERROR"


class PreflightStatus(StrEnum):
    """Batch 04 preflight status as surfaced by this tool."""

    PREFLIGHT_READY = "PREFLIGHT_READY"
    PREFLIGHT_QUARANTINED = "PREFLIGHT_QUARANTINED"
    PREFLIGHT_REJECTED = "PREFLIGHT_REJECTED"
    PREFLIGHT_NOT_APPLICABLE_EMPTY = "PREFLIGHT_NOT_APPLICABLE_EMPTY"


# Recorded whenever the fractional-second boundary is truncated to whole seconds for
# the IBKR request (which accepts second precision only).
REQUEST_TIME_PRECISION_TRUNCATED_TO_SECOND = "REQUEST_TIME_PRECISION_TRUNCATED_TO_SECOND"


__all__ = [
    "CollectionStatus",
    "ContractStatus",
    "HistoricalStatus",
    "PreflightStatus",
    "REQUEST_TIME_PRECISION_TRUNCATED_TO_SECOND",
]

"""Outcome settlement error hierarchy (BUILD 15)."""

from __future__ import annotations


class OutcomeSettlementError(Exception):
    """Base error for outcome settlement subsystem."""

    def __init__(self, code: str, message: str = "", *, details: dict | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(message or code)


class OutcomeRegistrationError(OutcomeSettlementError):
    """Forecast registration or ledger creation failed."""


class OutcomeIntegrityError(OutcomeSettlementError):
    """Integrity or tamper violation during settlement."""


class OutcomeObservationError(OutcomeSettlementError):
    """Observation resolution failed unexpectedly."""


class OutcomeAdjudicationError(OutcomeSettlementError):
    """Pure adjudication failure."""


__all__ = [
    "OutcomeAdjudicationError",
    "OutcomeIntegrityError",
    "OutcomeObservationError",
    "OutcomeRegistrationError",
    "OutcomeSettlementError",
]

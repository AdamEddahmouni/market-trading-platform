"""Normalization error taxonomy (BUILD 03)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class NormalizationErrorCode(StrEnum):
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    UNKNOWN_TIMESTAMP_UNIT = "UNKNOWN_TIMESTAMP_UNIT"
    INVALID_INSTRUMENT = "INVALID_INSTRUMENT"
    UNSUPPORTED_EVENT_TYPE = "UNSUPPORTED_EVENT_TYPE"
    INVALID_NUMERIC_VALUE = "INVALID_NUMERIC_VALUE"
    INVALID_PROVIDER_IDENTIFIER = "INVALID_PROVIDER_IDENTIFIER"
    INSUFFICIENT_PROVENANCE = "INSUFFICIENT_PROVENANCE"
    UNDETERMINABLE_AVAILABILITY = "UNDETERMINABLE_AVAILABILITY"
    MALFORMED_PAYLOAD = "MALFORMED_PAYLOAD"
    UNSUPPORTED_PROVIDER_RECORD = "UNSUPPORTED_PROVIDER_RECORD"


@dataclass(frozen=True, slots=True)
class NormalizationDiagnostic:
    code: NormalizationErrorCode
    message: str
    field: str | None = None
    details: dict[str, Any] | None = None


class NormalizationError(Exception):
    """Structured normalization failure for strict paths."""

    def __init__(
        self,
        *,
        code: NormalizationErrorCode,
        message: str,
        diagnostics: tuple[NormalizationDiagnostic, ...] = (),
        provider_id: str | None = None,
        source_record_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.diagnostics = diagnostics
        self.provider_id = provider_id
        self.source_record_type = source_record_type

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


__all__ = [
    "NormalizationDiagnostic",
    "NormalizationError",
    "NormalizationErrorCode",
]

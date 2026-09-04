"""Numeric normalization helpers (BUILD 03)."""

from __future__ import annotations

import math
from typing import Any

from .errors import NormalizationDiagnostic, NormalizationErrorCode


_MISSING_SENTINELS = frozenset({"N/A", "NA", "--", "-", "", "NULL", "NONE"})


def normalize_optional_float(
    value: object,
    *,
    field_name: str,
    missing_sentinels: frozenset[str] = _MISSING_SENTINELS,
) -> tuple[float | None, NormalizationDiagnostic | None]:
    if value is None:
        return None, None
    text = str(value).strip().upper()
    if text in missing_sentinels:
        return None, None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None, NormalizationDiagnostic(
            code=NormalizationErrorCode.INVALID_NUMERIC_VALUE,
            message=f"Invalid numeric value for {field_name}: {value!r}",
            field=field_name,
        )
    if not math.isfinite(numeric):
        return None, NormalizationDiagnostic(
            code=NormalizationErrorCode.INVALID_NUMERIC_VALUE,
            message=f"Non-finite numeric value for {field_name}",
            field=field_name,
        )
    return numeric, None


def normalize_optional_int(
    value: object,
    *,
    field_name: str,
    missing_sentinels: frozenset[str] = _MISSING_SENTINELS,
) -> tuple[int | None, NormalizationDiagnostic | None]:
    if value is None:
        return None, None
    text = str(value).strip().upper()
    if text in missing_sentinels:
        return None, None
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, NormalizationDiagnostic(
            code=NormalizationErrorCode.INVALID_NUMERIC_VALUE,
            message=f"Invalid integer value for {field_name}: {value!r}",
            field=field_name,
        )


def normalize_required_float(value: object, *, field_name: str) -> tuple[float | None, NormalizationDiagnostic | None]:
    parsed, diag = normalize_optional_float(value, field_name=field_name)
    if diag is not None:
        return None, diag
    if parsed is None:
        return None, NormalizationDiagnostic(
            code=NormalizationErrorCode.MISSING_REQUIRED_FIELD,
            message=f"{field_name} is required",
            field=field_name,
        )
    return parsed, None


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-serializable copy of normalized payload facts."""
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            if isinstance(value, float) and not math.isfinite(value):
                continue
            clean[str(key)] = value
        elif isinstance(value, dict):
            clean[str(key)] = sanitize_payload(value)
        elif isinstance(value, (list, tuple)):
            clean[str(key)] = [
                item
                for item in value
                if isinstance(item, (str, int, float, bool)) or item is None
            ]
    return clean


__all__ = [
    "normalize_optional_float",
    "normalize_optional_int",
    "normalize_required_float",
    "sanitize_payload",
]

"""Shared parsing and ratio reconciliation helpers."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .contracts import RatioReconciliationStatus


def parse_int(value: object) -> int | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.upper() in {"N/A", "NA", "-", "--"}:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text.upper() in {"N/A", "NA", "-", "--"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_ratio(value: object) -> float | None:
    parsed = parse_float(value)
    if parsed is None:
        return None
    if parsed < 0:
        return None
    return parsed


def reconcile_ratio(
    *,
    call_value: int | None,
    put_value: int | None,
    source_ratio: float | None,
    tolerance: float = 0.02,
) -> tuple[float | None, RatioReconciliationStatus]:
    """Recompute put/call ratio when denominator allows; compare to source."""

    if call_value is None or put_value is None:
        if source_ratio is not None:
            return source_ratio, RatioReconciliationStatus.SOURCE_ONLY
        return None, RatioReconciliationStatus.UNDEFINED_DENOMINATOR

    if call_value == 0:
        if source_ratio is not None and source_ratio == 0.0:
            return 0.0, RatioReconciliationStatus.MATCH
        if source_ratio is not None:
            return None, RatioReconciliationStatus.MISMATCH
        return None, RatioReconciliationStatus.UNDEFINED_DENOMINATOR

    derived = put_value / call_value
    if source_ratio is None:
        return derived, RatioReconciliationStatus.SOURCE_ONLY

    if abs(derived - source_ratio) <= tolerance:
        return derived, RatioReconciliationStatus.MATCH
    return derived, RatioReconciliationStatus.MISMATCH


def parse_iso_timestamp(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.endswith("Z"):
        return text[:-1] + "+00:00"
    return text


def parse_trade_date(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    if match:
        return match.group(1)
    match = re.match(r"(\d{1,2}/\d{1,2}/\d{4})", text)
    if match:
        month, day, year = match.group(1).split("/")
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return text[:10]


def parse_decimal_strike(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return format(Decimal(text.replace(",", "")), "f")
    except (InvalidOperation, ValueError):
        return text


def normalize_option_type(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in {"c", "call", "calls"}:
        return "call"
    if text in {"p", "put", "puts"}:
        return "put"
    return text or "unknown"


__all__ = [
    "normalize_option_type",
    "parse_decimal_strike",
    "parse_float",
    "parse_int",
    "parse_iso_timestamp",
    "parse_ratio",
    "parse_trade_date",
    "reconcile_ratio",
]

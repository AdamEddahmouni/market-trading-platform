"""Timestamp and numeric helpers for equity bar normalization."""

from __future__ import annotations

from datetime import datetime, timezone


def iso_to_epoch_ns(value: str) -> int:
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1_000_000_000)


def decimal_price_to_rational_string(value: str) -> str:
    return str(value)

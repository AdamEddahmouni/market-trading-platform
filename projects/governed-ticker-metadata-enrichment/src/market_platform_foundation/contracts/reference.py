"""Bitemporal reference-data contracts (Platform P0 / ADR-REF-001)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ReferenceKind(StrEnum):
    FUTURES_SPEC = "FUTURES_SPEC"
    SYMBOL_MAPPING = "SYMBOL_MAPPING"
    EARNINGS_CALENDAR = "EARNINGS_CALENDAR"
    DIVIDEND_ASSUMPTION = "DIVIDEND_ASSUMPTION"
    OPTIONS_OI = "OPTIONS_OI"
    SHORT_INTEREST = "SHORT_INTEREST"
    SHORT_SALE_VOLUME = "SHORT_SALE_VOLUME"
    THRESHOLD_STATUS = "THRESHOLD_STATUS"
    FAILS_TO_DELIVER = "FAILS_TO_DELIVER"
    COT_POSITIONING = "COT_POSITIONING"
    MACRO_OBSERVATION = "MACRO_OBSERVATION"
    ENERGY_FUNDAMENTAL = "ENERGY_FUNDAMENTAL"
    WEATHER_FORECAST = "WEATHER_FORECAST"
    WEATHER_REALIZATION = "WEATHER_REALIZATION"
    WEATHER_REFERENCE = "WEATHER_REFERENCE"


class ReferenceQualityFlag(StrEnum):
    REFERENCE_UNAVAILABLE = "REFERENCE_UNAVAILABLE"
    REFERENCE_SUPERSEDED = "REFERENCE_SUPERSEDED"
    LOOKAHEAD_REJECTED = "LOOKAHEAD_REJECTED"


@dataclass(frozen=True, slots=True)
class ReferenceRecord:
    kind: ReferenceKind
    entity_key: str
    record_id: str
    record_version: int
    valid_from: str
    known_from: str
    payload: dict[str, Any]
    valid_to: str = ""
    known_to: str = ""
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


__all__ = [
    "ReferenceKind",
    "ReferenceQualityFlag",
    "ReferenceRecord",
]

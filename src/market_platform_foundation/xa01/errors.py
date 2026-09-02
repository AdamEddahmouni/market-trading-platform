"""XA-01 error types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class Xa01ErrorCode(StrEnum):
    INVALID_ASSET_CLASS = "INVALID_ASSET_CLASS"
    INVALID_INSTRUMENT_KIND = "INVALID_INSTRUMENT_KIND"
    INVALID_DOMAIN = "INVALID_DOMAIN"
    INVALID_RELATIONSHIP = "INVALID_RELATIONSHIP"
    INVALID_ALIAS = "INVALID_ALIAS"
    INVALID_CURRENCY_PAIR = "INVALID_CURRENCY_PAIR"
    UNKNOWN_INSTRUMENT = "UNKNOWN_INSTRUMENT"
    DUPLICATE_IDENTITY = "DUPLICATE_IDENTITY"
    ALIAS_CONFLICT = "ALIAS_CONFLICT"
    SELF_RELATIONSHIP = "SELF_RELATIONSHIP"
    CYCLIC_RELATIONSHIP = "CYCLIC_RELATIONSHIP"
    REGISTRY_INVALID = "REGISTRY_INVALID"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"


@dataclass(frozen=True, slots=True)
class Xa01Error(Exception):
    code: Xa01ErrorCode
    message: str
    details: Mapping[str, Any]

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"

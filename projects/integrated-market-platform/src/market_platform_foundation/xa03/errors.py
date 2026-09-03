"""XA-03 error types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class Xa03ErrorCode(StrEnum):
    UNKNOWN_SOURCE = "UNKNOWN_SOURCE"
    UNKNOWN_OBSERVATION = "UNKNOWN_OBSERVATION"
    UNKNOWN_RELATIONSHIP = "UNKNOWN_RELATIONSHIP"
    UNKNOWN_XA_TARGET = "UNKNOWN_XA_TARGET"
    OBSERVATION_CONFLICT = "OBSERVATION_CONFLICT"
    RELATIONSHIP_CONFLICT = "RELATIONSHIP_CONFLICT"
    UNSUPPORTED_RELATIONSHIP = "UNSUPPORTED_RELATIONSHIP"
    UNSUPPORTED_UNIT = "UNSUPPORTED_UNIT"
    INVALID_FIXTURE = "INVALID_FIXTURE"
    NOT_ADMITTED_MARKET = "NOT_ADMITTED_MARKET"
    REGISTRY_INVALID = "REGISTRY_INVALID"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"


@dataclass(frozen=True, slots=True)
class Xa03Error(Exception):
    code: Xa03ErrorCode
    message: str
    details: Mapping[str, Any]

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"

"""XA-02 error types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class Xa02ErrorCode(StrEnum):
    UNKNOWN_INDICATOR = "UNKNOWN_INDICATOR"
    UNKNOWN_OBSERVATION = "UNKNOWN_OBSERVATION"
    UNKNOWN_RELATIONSHIP = "UNKNOWN_RELATIONSHIP"
    UNKNOWN_XA_TARGET = "UNKNOWN_XA_TARGET"
    DUPLICATE_OBSERVATION = "DUPLICATE_OBSERVATION"
    OBSERVATION_CONFLICT = "OBSERVATION_CONFLICT"
    RELATIONSHIP_CONFLICT = "RELATIONSHIP_CONFLICT"
    UNSUPPORTED_RELATIONSHIP = "UNSUPPORTED_RELATIONSHIP"
    UNSUPPORTED_UNIT = "UNSUPPORTED_UNIT"
    INVALID_FIXTURE = "INVALID_FIXTURE"
    NOT_ADMITTED_SERIES = "NOT_ADMITTED_SERIES"
    REGISTRY_INVALID = "REGISTRY_INVALID"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"


@dataclass(frozen=True, slots=True)
class Xa02Error(Exception):
    code: Xa02ErrorCode
    message: str
    details: Mapping[str, Any]

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"

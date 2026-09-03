"""OF-03 errors. Registry inspection never grants authority."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping


class OF03ErrorCode(StrEnum):
    REGISTRY_INVALID = "REGISTRY_INVALID"
    UNKNOWN_DEFINITION = "UNKNOWN_DEFINITION"
    VERSION_REQUIRED = "VERSION_REQUIRED"
    UNSAFE_BINDING = "UNSAFE_BINDING"
    REGISTRY_DOES_NOT_GRANT_AUTHORITY = "REGISTRY_DOES_NOT_GRANT_AUTHORITY"
    AGENT_USE_DENIED = "AGENT_USE_DENIED"
    IMPLICIT_LATEST_PROHIBITED = "IMPLICIT_LATEST_PROHIBITED"
    UNKNOWN_CAPABILITY = "UNKNOWN_CAPABILITY"
    INVALID_COMMAND = "INVALID_COMMAND"


class OF03Error(Exception):
    def __init__(self, code: OF03ErrorCode, message: str, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"

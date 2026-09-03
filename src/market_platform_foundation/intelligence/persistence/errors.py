"""Backend-independent persistence error taxonomy (BUILD 04.5)."""

from __future__ import annotations

from typing import Any


class RepositoryError(Exception):
    """Base persistence failure."""

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


class RepositoryUnavailableError(RepositoryError):
    """Persistence backend is unreachable or not ready."""


class RepositoryConflictError(RepositoryError):
    """Immutable record identity conflict — same ID, different semantic content."""


class RepositorySerializationError(RepositoryError):
    """Record cannot be encoded for persistence (e.g. BSON range)."""


class RepositoryValidationError(RepositoryError):
    """Stored or incoming record failed domain deserialization/validation."""


class RepositorySchemaError(RepositoryError):
    """Mongo schema/index bootstrap detected incompatible drift."""


__all__ = [
    "RepositoryConflictError",
    "RepositoryError",
    "RepositorySchemaError",
    "RepositorySerializationError",
    "RepositoryUnavailableError",
    "RepositoryValidationError",
]

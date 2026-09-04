"""Intelligence persistence architecture (BUILD 04.5)."""

from .errors import (
    RepositoryConflictError,
    RepositoryError,
    RepositorySchemaError,
    RepositorySerializationError,
    RepositoryUnavailableError,
    RepositoryValidationError,
)
from .memory import InMemoryIntelligenceRepository
from .repository import IntelligenceRepository, RepositoryPutResult

__all__ = [
    "InMemoryIntelligenceRepository",
    "IntelligenceRepository",
    "RepositoryConflictError",
    "RepositoryError",
    "RepositoryPutResult",
    "RepositorySchemaError",
    "RepositorySerializationError",
    "RepositoryUnavailableError",
    "RepositoryValidationError",
]

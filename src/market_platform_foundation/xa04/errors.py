"""XA-04 persistence errors — shared taxonomy with intelligence persistence."""

from market_platform_foundation.intelligence.persistence.errors import (
    RepositoryConflictError,
    RepositoryError,
    RepositorySchemaError,
    RepositorySerializationError,
    RepositoryUnavailableError,
    RepositoryValidationError,
)

__all__ = [
    "RepositoryConflictError",
    "RepositoryError",
    "RepositorySchemaError",
    "RepositorySerializationError",
    "RepositoryUnavailableError",
    "RepositoryValidationError",
]

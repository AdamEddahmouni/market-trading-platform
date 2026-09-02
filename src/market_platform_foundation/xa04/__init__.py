"""XA-04 durable cross-asset catalog persistence."""

from .errors import (
    RepositoryConflictError,
    RepositoryError,
    RepositorySchemaError,
    RepositorySerializationError,
    RepositoryUnavailableError,
    RepositoryValidationError,
)
from .memory import InMemoryCrossAssetCatalogRepository
from .repository import CrossAssetCatalogRepository, RepositoryPutResult

__all__ = [
    "CrossAssetCatalogRepository",
    "InMemoryCrossAssetCatalogRepository",
    "RepositoryConflictError",
    "RepositoryError",
    "RepositoryPutResult",
    "RepositorySchemaError",
    "RepositorySerializationError",
    "RepositoryUnavailableError",
    "RepositoryValidationError",
]

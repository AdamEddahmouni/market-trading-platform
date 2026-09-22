"""Intelligence persistence architecture (BUILD 04.5)."""

from .errors import (
    RepositoryConflictError,
    RepositoryError,
    RepositorySchemaError,
    RepositorySerializationError,
    RepositoryUnavailableError,
    RepositoryValidationError,
)
from .local_state_book import (
    LocalStateIntelligenceRepository,
    open_local_state_intelligence_repository,
    opportunity_book_health,
    opportunity_book_storage,
    reset_local_state_intelligence_repository_for_tests,
)
from .memory import InMemoryIntelligenceRepository
from .repository import IntelligenceRepository, RepositoryPutResult

__all__ = [
    "InMemoryIntelligenceRepository",
    "LocalStateIntelligenceRepository",
    "IntelligenceRepository",
    "RepositoryConflictError",
    "RepositoryError",
    "RepositoryPutResult",
    "RepositorySchemaError",
    "RepositorySerializationError",
    "RepositoryUnavailableError",
    "RepositoryValidationError",
    "open_local_state_intelligence_repository",
    "opportunity_book_health",
    "opportunity_book_storage",
    "reset_local_state_intelligence_repository_for_tests",
]

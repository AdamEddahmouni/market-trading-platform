"""Process-local and durable trade review repository resolution."""

from __future__ import annotations

import threading

from ...local_state.paths import persistence_enabled
from ...local_state.startup import open_local_state
from .repository import InMemoryTradeReviewRepository, TradeReviewRepository
from .sqlite_repository import SqliteTradeReviewRepository

_MEMORY = InMemoryTradeReviewRepository()
_LOCK = threading.Lock()
_SQLITE: SqliteTradeReviewRepository | None = None


def open_trade_review_repository() -> TradeReviewRepository:
    if not persistence_enabled():
        return _MEMORY
    repo = open_local_state()
    if repo is None:
        return _MEMORY
    global _SQLITE
    with _LOCK:
        if _SQLITE is None or _SQLITE._connection is not repo.connection:
            _SQLITE = SqliteTradeReviewRepository(repo.connection)
        return _SQLITE


def reset_trade_review_repository_for_tests() -> None:
    global _SQLITE
    with _LOCK:
        _SQLITE = None
    _MEMORY.reset_for_tests()


__all__ = ["open_trade_review_repository", "reset_trade_review_repository_for_tests"]

"""Trade review persistence — in-memory foundation; durable store deferred."""

from __future__ import annotations

import threading
from typing import Protocol, runtime_checkable

from ..persistence.repository import RepositoryPutResult
from .contracts import TradeReviewV1


@runtime_checkable
class TradeReviewRepository(Protocol):
    """Typed persistence for canonical trade review records."""

    def put_trade_review(self, review: TradeReviewV1) -> RepositoryPutResult: ...

    def get_trade_review(self, review_id: str) -> TradeReviewV1 | None: ...

    def list_trade_reviews_by_opportunity(
        self, opportunity_id: str
    ) -> tuple[TradeReviewV1, ...]: ...


class InMemoryTradeReviewRepository:
    """Fixture repository aligned with inference/evaluation in-memory patterns."""

    def __init__(self) -> None:
        self._reviews: dict[str, TradeReviewV1] = {}
        self._by_opportunity: dict[str, list[str]] = {}
        self._lock = threading.Lock()

    def put_trade_review(self, review: TradeReviewV1) -> RepositoryPutResult:
        with self._lock:
            if review.review_id in self._reviews:
                return RepositoryPutResult.ALREADY_PRESENT
            self._reviews[review.review_id] = review
            if review.opportunity_id:
                self._by_opportunity.setdefault(review.opportunity_id, []).append(review.review_id)
            return RepositoryPutResult.INSERTED

    def get_trade_review(self, review_id: str) -> TradeReviewV1 | None:
        with self._lock:
            return self._reviews.get(review_id)

    def list_trade_reviews_by_opportunity(self, opportunity_id: str) -> tuple[TradeReviewV1, ...]:
        with self._lock:
            ids = self._by_opportunity.get(opportunity_id, [])
            return tuple(self._reviews[review_id] for review_id in ids if review_id in self._reviews)


__all__ = ["InMemoryTradeReviewRepository", "TradeReviewRepository"]

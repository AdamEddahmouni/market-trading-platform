"""Trade review persistence — in-memory and SQLite-backed durable store."""

from __future__ import annotations

import threading
from typing import Any, Protocol, runtime_checkable

from ..persistence.repository import RepositoryPutResult
from .contracts import TradeReviewV1
from .operator_edits import (
    TradeReviewOperatorEdit,
    canonicalize_for_persist,
    merge_operator_edits,
)
from .serialization import trade_review_v1_to_dict


@runtime_checkable
class TradeReviewRepository(Protocol):
    """Typed persistence for canonical trade review records."""

    def put_trade_review(self, review: TradeReviewV1) -> RepositoryPutResult: ...

    def get_trade_review(self, review_id: str) -> TradeReviewV1 | None: ...

    def list_trade_reviews_by_opportunity(
        self, opportunity_id: str
    ) -> tuple[TradeReviewV1, ...]: ...

    def append_operator_edit(self, edit: TradeReviewOperatorEdit) -> int: ...

    def get_trade_review_projection(self, review_id: str) -> dict[str, Any] | None: ...


class InMemoryTradeReviewRepository:
    """Fixture repository aligned with inference/evaluation in-memory patterns."""

    def __init__(self) -> None:
        self._reviews: dict[str, TradeReviewV1] = {}
        self._by_opportunity: dict[str, list[str]] = {}
        self._edits: dict[str, list[TradeReviewOperatorEdit]] = {}
        self._lock = threading.Lock()
        self._next_edit_id = 1

    def reset_for_tests(self) -> None:
        with self._lock:
            self._reviews.clear()
            self._by_opportunity.clear()
            self._edits.clear()
            self._next_edit_id = 1

    def put_trade_review(self, review: TradeReviewV1) -> RepositoryPutResult:
        canonical = canonicalize_for_persist(review)
        with self._lock:
            if canonical.review_id in self._reviews:
                if self._reviews[canonical.review_id] == canonical:
                    return RepositoryPutResult.ALREADY_PRESENT
                raise ValueError("TRADE_REVIEW_IMMUTABLE_CONFLICT")
            self._reviews[canonical.review_id] = canonical
            if canonical.opportunity_id:
                self._by_opportunity.setdefault(canonical.opportunity_id, []).append(canonical.review_id)
            return RepositoryPutResult.INSERTED

    def _canonical(self, review_id: str) -> TradeReviewV1 | None:
        return self._reviews.get(review_id)

    def get_trade_review(self, review_id: str) -> TradeReviewV1 | None:
        with self._lock:
            canonical = self._canonical(review_id)
            if canonical is None:
                return None
            merged, _ = merge_operator_edits(canonical, tuple(self._edits.get(review_id, ())))
            return merged

    def get_trade_review_projection(self, review_id: str) -> dict[str, Any] | None:
        with self._lock:
            canonical = self._canonical(review_id)
            if canonical is None:
                return None
            merged, derived = merge_operator_edits(canonical, tuple(self._edits.get(review_id, ())))
        body = trade_review_v1_to_dict(merged)
        body["derived_reflections"] = list(derived)
        body["canonical_immutable"] = True
        return body

    def list_trade_reviews_by_opportunity(self, opportunity_id: str) -> tuple[TradeReviewV1, ...]:
        with self._lock:
            ids = list(self._by_opportunity.get(opportunity_id, ()))
        return tuple(
            review
            for review_id in ids
            if (review := self.get_trade_review(review_id)) is not None
        )

    def append_operator_edit(self, edit: TradeReviewOperatorEdit) -> int:
        with self._lock:
            if edit.review_id not in self._reviews:
                raise ValueError("TRADE_REVIEW_NOT_FOUND")
            edit_id = self._next_edit_id
            self._next_edit_id += 1
            stored = TradeReviewOperatorEdit(
                edit_id=edit_id,
                review_id=edit.review_id,
                edit_kind=edit.edit_kind,
                payload=dict(edit.payload),
                created_at_ns=edit.created_at_ns,
                source_kind=edit.source_kind,
                model_identity=edit.model_identity,
            )
            self._edits.setdefault(edit.review_id, []).append(stored)
            return edit_id


__all__ = ["InMemoryTradeReviewRepository", "TradeReviewRepository"]

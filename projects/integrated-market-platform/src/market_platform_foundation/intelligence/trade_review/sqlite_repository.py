"""SQLite-backed trade review repository (local_state schema v8)."""

from __future__ import annotations

import json
from typing import Any

from ...clock import monotonic_wall_ns
from ...local_state.connection import LocalStateConnection
from ..persistence.repository import RepositoryPutResult
from .contracts import TradeReviewV1
from .operator_edits import (
    TradeReviewEditKind,
    TradeReviewEditSourceKind,
    TradeReviewOperatorEdit,
    canonicalize_for_persist,
    merge_operator_edits,
)
from .serialization import trade_review_v1_from_dict, trade_review_v1_to_dict


class SqliteTradeReviewRepository:
    def __init__(self, connection: LocalStateConnection) -> None:
        self._connection = connection

    def _run_write(self, callback):
        if self._connection.in_transaction:
            return callback()
        with self._connection.transaction():
            return callback()

    def put_trade_review(self, review: TradeReviewV1) -> RepositoryPutResult:
        canonical = canonicalize_for_persist(review)
        payload = json.dumps(trade_review_v1_to_dict(canonical), sort_keys=True, separators=(",", ":"))
        persist_time_ns = monotonic_wall_ns()

        def _write() -> RepositoryPutResult:
            row = self._connection.execute(
                "SELECT review_json FROM trade_reviews WHERE review_id = ?",
                (canonical.review_id,),
            ).fetchone()
            if row is not None:
                prior = json.loads(str(row["review_json"]))
                if prior == json.loads(payload):
                    return RepositoryPutResult.ALREADY_PRESENT
                raise ValueError("TRADE_REVIEW_IMMUTABLE_CONFLICT")
            self._connection.execute(
                """
                INSERT INTO trade_reviews(
                    review_id, opportunity_id, review_mode, decision,
                    decision_time_ns, created_at_ns, execution_decision_trace_id,
                    review_json, persist_time_ns
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    canonical.review_id,
                    canonical.opportunity_id,
                    canonical.review_mode.value,
                    canonical.decision,
                    canonical.decision_time_ns,
                    canonical.created_at_ns,
                    canonical.execution_decision_trace_id,
                    payload,
                    persist_time_ns,
                ),
            )
            return RepositoryPutResult.INSERTED

        return self._run_write(_write)

    def _load_canonical(self, review_id: str) -> TradeReviewV1 | None:
        row = self._connection.execute(
            "SELECT review_json FROM trade_reviews WHERE review_id = ?",
            (str(review_id),),
        ).fetchone()
        if row is None:
            return None
        return trade_review_v1_from_dict(json.loads(str(row["review_json"])))

    def _list_edits(self, review_id: str) -> tuple[TradeReviewOperatorEdit, ...]:
        rows = self._connection.execute(
            """
            SELECT edit_id, review_id, edit_kind, payload_json, created_at_ns,
                   source_kind, model_identity
            FROM trade_review_operator_edits
            WHERE review_id=?
            ORDER BY created_at_ns ASC, edit_id ASC
            """,
            (str(review_id),),
        ).fetchall()
        edits: list[TradeReviewOperatorEdit] = []
        for row in rows:
            edits.append(
                TradeReviewOperatorEdit(
                    edit_id=int(row["edit_id"]),
                    review_id=str(row["review_id"]),
                    edit_kind=TradeReviewEditKind(str(row["edit_kind"])),
                    payload=json.loads(str(row["payload_json"])),
                    created_at_ns=int(row["created_at_ns"]),
                    source_kind=TradeReviewEditSourceKind(str(row["source_kind"])),
                    model_identity=row["model_identity"],
                )
            )
        return tuple(edits)

    def get_trade_review(self, review_id: str) -> TradeReviewV1 | None:
        canonical = self._load_canonical(review_id)
        if canonical is None:
            return None
        merged, _ = merge_operator_edits(canonical, self._list_edits(review_id))
        return merged

    def get_trade_review_projection(self, review_id: str) -> dict[str, Any] | None:
        canonical = self._load_canonical(review_id)
        if canonical is None:
            return None
        merged, derived = merge_operator_edits(canonical, self._list_edits(review_id))
        body = trade_review_v1_to_dict(merged)
        body["derived_reflections"] = list(derived)
        body["canonical_immutable"] = True
        return body

    def list_trade_reviews_by_opportunity(self, opportunity_id: str) -> tuple[TradeReviewV1, ...]:
        rows = self._connection.execute(
            """
            SELECT review_id FROM trade_reviews
            WHERE opportunity_id=?
            ORDER BY created_at_ns ASC
            """,
            (str(opportunity_id),),
        ).fetchall()
        reviews: list[TradeReviewV1] = []
        for row in rows:
            review = self.get_trade_review(str(row["review_id"]))
            if review is not None:
                reviews.append(review)
        return tuple(reviews)

    def append_operator_edit(self, edit: TradeReviewOperatorEdit) -> int:
        if self._load_canonical(edit.review_id) is None:
            raise ValueError("TRADE_REVIEW_NOT_FOUND")
        if edit.edit_kind == TradeReviewEditKind.DERIVED_REFLECTION:
            if edit.source_kind != TradeReviewEditSourceKind.DERIVED_MODEL:
                raise ValueError("TRADE_REVIEW_DERIVED_SOURCE_INVALID")
            if not edit.model_identity:
                raise ValueError("TRADE_REVIEW_DERIVED_MODEL_REQUIRED")

        payload = json.dumps(edit.payload, sort_keys=True, separators=(",", ":"))

        def _write() -> int:
            cursor = self._connection.execute(
                """
                INSERT INTO trade_review_operator_edits(
                    review_id, edit_kind, payload_json, created_at_ns,
                    source_kind, model_identity
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    edit.review_id,
                    edit.edit_kind.value,
                    payload,
                    edit.created_at_ns,
                    edit.source_kind.value,
                    edit.model_identity,
                ),
            )
            return int(cursor.lastrowid)

        return self._run_write(_write)


__all__ = ["SqliteTradeReviewRepository"]

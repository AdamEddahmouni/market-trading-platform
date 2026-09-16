"""HTTP projections for durable trade review learning records."""

from __future__ import annotations

from typing import Any

from ..clock import monotonic_wall_ns
from ..intelligence.trade_review.operator_edits import (
    TradeReviewEditKind,
    TradeReviewEditSourceKind,
    TradeReviewOperatorEdit,
)
from ..intelligence.trade_review.store import open_trade_review_repository
from .store import ReplayStore


def _is_live(store: ReplayStore) -> bool:
    return store.data_mode == "LIVE_OBSERVATIONAL" or str(store.mode).upper() == "LIVE"


def _live_blocks_trade_review_mutation(store: ReplayStore) -> bool:
    return _is_live(store)


def build_trade_reviews_for_opportunity_payload(
    store: ReplayStore,
    opportunity_id: str,
    *,
    alternate_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    repo = open_trade_review_repository()
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    lookup_ids = (str(opportunity_id),) + tuple(str(item) for item in alternate_ids if item)
    for lookup_id in lookup_ids:
        for review in repo.list_trade_reviews_by_opportunity(lookup_id):
            if review.review_id in seen:
                continue
            seen.add(review.review_id)
            projection = repo.get_trade_review_projection(review.review_id)
            if projection is not None:
                items.append(projection)
    payload: dict[str, Any] = {
        "opportunity_id": opportunity_id,
        "acceptance_label": "TRADE_REVIEW_DURABLE_LOOP_READY",
        "items": items,
    }
    if _is_live(store) and not items:
        payload["reason"] = "LIVE_OBSERVATIONAL_NO_TRADE_REVIEW"
    return payload


def build_trade_review_detail_payload(store: ReplayStore, review_id: str) -> dict[str, Any]:
    repo = open_trade_review_repository()
    projection = repo.get_trade_review_projection(str(review_id))
    if projection is None:
        raise KeyError(review_id)
    return projection


def apply_trade_review_operator_patch(
    store: ReplayStore,
    review_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    if _live_blocks_trade_review_mutation(store):
        raise PermissionError("LIVE_OBSERVATIONAL_NO_TRADE_REVIEW")
    repo = open_trade_review_repository()
    if repo.get_trade_review_projection(review_id) is None:
        raise KeyError(review_id)
    created_at_ns = int(body.get("created_at_ns") or monotonic_wall_ns())
    if "notes" in body:
        repo.append_operator_edit(
            TradeReviewOperatorEdit(
                review_id=review_id,
                edit_kind=TradeReviewEditKind.NOTES,
                payload={"notes": str(body.get("notes") or "")},
                created_at_ns=created_at_ns,
            )
        )
    if "reflection" in body:
        if body.get("derived") or body.get("model_identity"):
            repo.append_operator_edit(
                TradeReviewOperatorEdit(
                    review_id=review_id,
                    edit_kind=TradeReviewEditKind.DERIVED_REFLECTION,
                    payload={
                        "reflection": str(body.get("reflection") or ""),
                        "generated_at_ns": created_at_ns,
                    },
                    created_at_ns=created_at_ns,
                    source_kind=TradeReviewEditSourceKind.DERIVED_MODEL,
                    model_identity=str(body.get("model_identity") or ""),
                )
            )
        else:
            repo.append_operator_edit(
                TradeReviewOperatorEdit(
                    review_id=review_id,
                    edit_kind=TradeReviewEditKind.REFLECTION,
                    payload={"reflection": str(body.get("reflection") or "")},
                    created_at_ns=created_at_ns,
                )
            )
    if "tags" in body:
        tags = body.get("tags") or []
        if not isinstance(tags, list):
            raise ValueError("TRADE_REVIEW_TAGS_INVALID")
        repo.append_operator_edit(
            TradeReviewOperatorEdit(
                review_id=review_id,
                edit_kind=TradeReviewEditKind.TAGS,
                payload={"tags": [str(v) for v in tags]},
                created_at_ns=created_at_ns,
            )
        )
    if "mistakes" in body:
        mistakes = body.get("mistakes") or []
        if not isinstance(mistakes, list):
            raise ValueError("TRADE_REVIEW_MISTAKES_INVALID")
        repo.append_operator_edit(
            TradeReviewOperatorEdit(
                review_id=review_id,
                edit_kind=TradeReviewEditKind.MISTAKES,
                payload={"mistakes": [str(v) for v in mistakes]},
                created_at_ns=created_at_ns,
            )
        )
    projection = repo.get_trade_review_projection(review_id)
    assert projection is not None
    return projection


def overlay_trade_reviews_on_detail(store: ReplayStore, detail: dict[str, Any]) -> dict[str, Any]:
    opportunity_id = str(detail.get("opportunity_id") or detail.get("summary_id") or "")
    if not opportunity_id:
        return detail
    alternates: list[str] = []
    summary_id = detail.get("summary_id")
    if summary_id and str(summary_id) != opportunity_id:
        alternates.append(str(summary_id))
    opp = detail.get("opportunity_id")
    if opp and str(opp) != opportunity_id:
        alternates.append(str(opp))
    payload = build_trade_reviews_for_opportunity_payload(
        store, opportunity_id, alternate_ids=tuple(alternates)
    )
    merged = dict(detail)
    merged["trade_reviews"] = payload.get("items") or []
    merged["trade_review_acceptance_label"] = payload.get("acceptance_label")
    return merged


__all__ = [
    "apply_trade_review_operator_patch",
    "build_trade_review_detail_payload",
    "build_trade_reviews_for_opportunity_payload",
    "overlay_trade_reviews_on_detail",
]

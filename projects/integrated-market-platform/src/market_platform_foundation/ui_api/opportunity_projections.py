"""HTTP serializers for the Opportunity Engine operator loop."""

from __future__ import annotations

from typing import Any

from ..intelligence.opportunity.ingest import assemble_opportunity_review_rows
from ..intelligence.opportunity.ranking import comparison_vectors_from_repository, rank_review_rows
from . import projections
from .operator_opportunity_state import dismissed_ids, list_operator_acks, record_operator_ack
from .store import ReplayStore


def decision_support_overlay() -> dict[str, Any]:
    """Downstream risk context. Must not rank or include order identity."""

    return {
        "authority": "DOWNSTREAM_RISK_NOT_RANKING",
        "kill_switch": "UNAVAILABLE",
        "gross_exposure": {"status": "UNAVAILABLE"},
        "concentration": {"status": "UNAVAILABLE"},
        "risk_decision": {"status": "UNAVAILABLE"},
        "reason_codes": [],
    }


def _serialize_review_row(row: Any) -> dict[str, Any]:
    body = row.to_dict()
    body.pop("rank_score", None)
    body["decision_support"] = decision_support_overlay()
    if row.opportunity_id:
        body["explanation_ref"] = f"explain:opportunity:{row.opportunity_id}"
    else:
        body["explanation_ref"] = f"explain:summary:{row.summary_id}"
    return body


def _is_live(store: ReplayStore) -> bool:
    return store.data_mode == "LIVE_OBSERVATIONAL" or str(store.mode).upper() == "LIVE"


def _paper_mutations_allowed(store: ReplayStore) -> bool:
    return store.execution_mode == "INTERNAL_SIMULATION" and not _is_live(store)


def _attention_rows(store: ReplayStore) -> tuple[dict[str, Any], ...]:
    page = projections.build_attention_page(store, limit=50)
    items = page.get("items") or []
    rows: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "attention_id": item.get("attention_id"),
                "instrument_id": item.get("instrument_id"),
                "symbol": item.get("instrument_id"),
                "headline": item.get("headline"),
                "catalyst_ids": tuple(
                    str(reason.get("code"))
                    for reason in (item.get("reasons") or [])
                    if isinstance(reason, dict) and reason.get("code")
                ),
            }
        )
    return tuple(rows)


def _feed_status(store: ReplayStore, ranked_count: int) -> tuple[str, str | None]:
    quality = projections.build_quality_summary(store)
    if _is_live(store):
        return "UNAVAILABLE", "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE"
    state = str(quality.get("state") or "")
    if state and state not in {"HEALTHY", "GOOD", "AVAILABLE"}:
        return "UNREADY", "QUALITY_SUMMARY_NOT_HEALTHY"
    if ranked_count == 0:
        return "EMPTY", None
    return "READY", None


def build_ranked_rows(store: ReplayStore) -> tuple[Any, ...]:
    repository = getattr(store, "strategy_repository", None)
    assembled = assemble_opportunity_review_rows(
        attention_rows=_attention_rows(store),
        repository=repository,
        source="REPLAY" if store.data_mode != "LIVE_OBSERVATIONAL" else "LIVE_OBSERVATIONAL",
    )
    return rank_review_rows(
        assembled,
        comparison_vectors=comparison_vectors_from_repository(repository),
        dismissed_ids=dismissed_ids(),
    )


def build_opportunities_summary_payload(
    store: ReplayStore,
    *,
    cursor: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    if _is_live(store):
        return {
            "as_of_context": projections.build_as_of_context(store),
            "quality_summary": projections.build_quality_summary(store),
            "feed_status": "UNAVAILABLE",
            "reason": "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE",
            "items": [],
            "next_cursor": None,
        }
    ranked = build_ranked_rows(store)
    page_size = limit or store.page_size
    start = 0
    if cursor:
        for index, row in enumerate(ranked):
            if row.summary_id == cursor or row.opportunity_id == cursor:
                start = index + 1
                break
    page = ranked[start : start + page_size]
    next_cursor = page[-1].summary_id if len(page) == page_size and start + page_size < len(ranked) else None
    status, unready_reason = _feed_status(store, len(ranked))
    payload: dict[str, Any] = {
        "as_of_context": projections.build_as_of_context(store),
        "quality_summary": projections.build_quality_summary(store),
        "feed_status": status,
        "items": [_serialize_review_row(row) for row in page],
        "next_cursor": next_cursor,
    }
    if status == "UNREADY":
        payload["unready_reason"] = unready_reason
        payload["next_action"] = "/control"
    return payload


def build_opportunity_detail_payload(store: ReplayStore, row_id: str) -> dict[str, Any]:
    if _is_live(store):
        raise KeyError("LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")
    ranked = build_ranked_rows(store)
    acks = list_operator_acks()
    for row in ranked:
        if row.summary_id == row_id or row.opportunity_id == row_id:
            body = _serialize_review_row(row)
            if row.instrument_id:
                body["preview_href"] = f"/workspace/{row.instrument_id}"
            matching = [ack for ack in acks if row.summary_id == ack["summary_id"] or row.opportunity_id == ack.get("opportunity_id")]
            if matching:
                body["lifecycle_state"] = matching[-1]["action"]
            return body
    dismissed = [ack for ack in acks if row_id in {ack["summary_id"], ack.get("opportunity_id")}]
    if dismissed:
        last = dismissed[-1]
        return {
            "summary_id": last["summary_id"],
            "opportunity_id": last.get("opportunity_id"),
            "lifecycle_state": last["action"],
            "feed_status": "DISMISSED",
        }
    raise KeyError(row_id)


def build_opportunity_evidence_payload(store: ReplayStore, row_id: str) -> dict[str, Any]:
    detail = build_opportunity_detail_payload(store, row_id)
    lineage = detail.get("lineage_refs") or []
    copy = "not OpportunityV1" if detail.get("identity_kind") == "NOT_OPPORTUNITY_V1" else None
    return {"items": lineage, "copy": copy}


def build_opportunity_explain_body(store: ReplayStore, ref: str) -> dict[str, Any]:
    if _is_live(store):
        raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
    if ref.startswith("explain:opportunity:"):
        row_id = ref.removeprefix("explain:opportunity:")
    elif ref.startswith("explain:summary:"):
        row_id = ref.removeprefix("explain:summary:")
    else:
        raise ValueError("UI_EXPLAIN_REF_NOT_FOUND")
    try:
        detail = build_opportunity_detail_payload(store, row_id)
    except KeyError as exc:
        raise ValueError("UI_EXPLAIN_REF_NOT_FOUND") from exc
    identity = detail.get("identity_kind")
    why = "not OpportunityV1" if identity == "NOT_OPPORTUNITY_V1" else str(detail.get("headline") or "OpportunityV1 review row")
    return {
        "alignment_summary": str(detail.get("lifecycle_state") or "UNAVAILABLE"),
        "level": 2,
        "meaning": str(detail.get("headline") or row_id),
        "ref": ref,
        "why": why,
        "lineage_refs": detail.get("lineage_refs") or [],
    }


def apply_opportunity_ack(
    store: ReplayStore,
    *,
    row_id: str,
    action: str,
) -> dict[str, Any]:
    if _is_live(store):
        raise PermissionError("LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")
    if not _paper_mutations_allowed(store):
        raise PermissionError("DEMO_MUTATIONS_PROHIBITED")
    ranked = list(build_ranked_rows(store))
    target = None
    for row in ranked:
        if row.summary_id == row_id or row.opportunity_id == row_id:
            target = row
            break
    if target is None:
        raise KeyError(row_id)
    as_of = projections.build_as_of_context(store)
    created_at_ns = int(as_of.get("as_of_time_ns") or 0)
    account_id = getattr(store.paper_ledger, "paper_account_id", None) or "paper-default"
    return record_operator_ack(
        summary_id=target.summary_id,
        opportunity_id=target.opportunity_id,
        paper_account_id=str(account_id),
        action=action,
        created_at_ns=created_at_ns,
    )

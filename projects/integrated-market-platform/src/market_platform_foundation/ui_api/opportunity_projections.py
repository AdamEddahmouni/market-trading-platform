"""HTTP serializers for the Opportunity Engine operator loop."""

from __future__ import annotations

from typing import Any

from ..intelligence.contracts.opportunity import OpportunityV1
from ..intelligence.opportunity.ingest import assemble_opportunity_review_rows
from ..intelligence.opportunity.ranking import comparison_vectors_from_repository, rank_review_rows
from . import projections
from ..rt01.execution_decision_trace.runtime import (
    record_opportunity_surface_trace,
    record_operator_lifecycle_trace,
)
from .operator_opportunity_state import dismissed_ids, list_operator_acks, record_operator_ack
from .agent_enrichment_ingest import overlay_agent_enrichment_on_detail
from .research_artifact_evidence import overlay_research_artifact_evidence_on_detail
from .trade_review_projections import overlay_trade_reviews_on_detail
from .store import ReplayStore
from ..intelligence.trade_review.materialize import (
    _refs_from_lineage,
    materialize_trade_review_for_operator_ack,
)

try:
    from ..hot_path_telemetry.collector import HotPathClockCollector
    from ..rt01.clock import monotonic_process_ns
except ImportError:  # pragma: no cover
    HotPathClockCollector = None  # type: ignore[misc, assignment]
    monotonic_process_ns = None  # type: ignore[assignment]

_REVIEW_METADATA_PROJECTION = (
    "evidence_promotion_reason",
    "family_admission_status",
    "family_admission_reason",
    "family_admission_kind",
    "supersession_reason",
    "duplicate_reason",
)

_INGEST_TIMESTAMP_METADATA_KEYS = frozenset(
    {"decision_time_ns", "created_at_ns", "opportunity_decision_time_ns"}
)


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


def _persist_opportunity(store: ReplayStore | None, opportunity_id: str | None) -> OpportunityV1 | None:
    """Read-only persist lookup for HTTP projection. Does not mutate review-row metadata."""

    if store is None or not opportunity_id:
        return None
    getter = getattr(getattr(store, "strategy_repository", None), "get_opportunity", None)
    if not callable(getter):
        return None
    try:
        record = getter(str(opportunity_id))
    except (TypeError, ValueError, KeyError):
        return None
    return record if isinstance(record, OpportunityV1) else None


def _append_unavailable(fields: list[str], name: str) -> None:
    if name not in fields:
        fields.append(name)


def _serialize_review_row(row: Any, store: ReplayStore | None = None) -> dict[str, Any]:
    body = row.to_dict()
    body.pop("rank_score", None)
    metadata = dict(body.get("metadata") or {}) if isinstance(body.get("metadata"), dict) else {}
    for key in _INGEST_TIMESTAMP_METADATA_KEYS:
        metadata.pop(key, None)
    body["metadata"] = metadata
    for key in _REVIEW_METADATA_PROJECTION:
        if key in metadata and key not in body:
            body[key] = metadata[key]
    instrument_id = str(body.get("instrument_id") or "")
    body["instrument_key"] = instrument_id or None
    persist = _persist_opportunity(store, row.opportunity_id)
    unavailable = [str(item) for item in (body.get("unavailable_fields") or [])]
    if persist is not None:
        body["created_at_ns"] = persist.created_at_ns
        if persist.expected_return is not None:
            body["expected_return"] = persist.expected_return
            unavailable = [item for item in unavailable if item != "expected_return"]
        else:
            _append_unavailable(unavailable, "expected_return")
        if persist.expected_net_edge is not None:
            body["expected_net_edge"] = persist.expected_net_edge
            unavailable = [item for item in unavailable if item != "expected_net_edge"]
        else:
            _append_unavailable(unavailable, "expected_net_edge")
    else:
        body["created_at_ns"] = None
        _append_unavailable(unavailable, "created_at_ns")
    if not instrument_id:
        _append_unavailable(unavailable, "instrument_key")
    body["unavailable_fields"] = unavailable
    body["decision_support"] = decision_support_overlay()
    if row.opportunity_id:
        body["explanation_ref"] = f"explain:opportunity:{row.opportunity_id}"
    else:
        body["explanation_ref"] = f"explain:summary:{row.summary_id}"
    return body


def _is_live(store: ReplayStore) -> bool:
    """Observational data-mode tripwire. Keep for mutations and fixture quarantine.

    P12 (`review/live-oe-diagnosis-20260915` @ ``5f965f32``): today's
    ``LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE`` on ``/opportunities/summary``
    was returned *before* ``build_ranked_rows``. Do not use this helper to skip
    ranked reads. Do not delete it before fixture attention is quarantined
    (live ``_attention_rows`` is empty). Finviz→EventV1 is a helper, not a
    ``UiApiHandler`` request-path admission.
    """

    return projections.is_live_observational(store)


def _paper_mutations_allowed(store: ReplayStore) -> bool:
    return store.execution_mode == "INTERNAL_SIMULATION" and not _is_live(store)


def _attention_rows(store: ReplayStore) -> tuple[dict[str, Any], ...]:
    # Live ranked reads must not ingest fixture/replay attention. Deleting the
    # read gate without this quarantine would rank July BIYA/MC9/ES cards.
    if _is_live(store):
        return ()
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


def _live_as_of_unavailable(store: ReplayStore) -> bool:
    return str(projections.display_as_of_time(store)) == projections.LIVE_AS_OF_UNAVAILABLE


def _feed_status(store: ReplayStore, ranked_count: int) -> tuple[str, str | None]:
    if _is_live(store):
        # Observational ranked READ: never LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE.
        # A current book is READY only when a live clock exists and rows rank.
        if _live_as_of_unavailable(store):
            if ranked_count == 0:
                return "EMPTY", None
            return "UNREADY", "LIVE_AS_OF_UNAVAILABLE"
        if ranked_count == 0:
            return "EMPTY", None
        return "READY", None
    quality = projections.build_quality_summary(store)
    state = str(quality.get("state") or "")
    if state and state not in {"HEALTHY", "GOOD", "AVAILABLE"}:
        return "UNREADY", "QUALITY_SUMMARY_NOT_HEALTHY"
    if ranked_count == 0:
        return "EMPTY", None
    return "READY", None


def _opportunity_source(store: ReplayStore) -> str:
    if _is_live(store):
        return "LIVE_OBSERVATIONAL"
    explicit = getattr(store, "opportunity_source", None)
    if explicit:
        return str(explicit)
    if store.data_mode in {"DELAYED_PROSPECTIVE", "PAPER_OBSERVATIONAL"}:
        return store.data_mode
    return "REPLAY"


def build_ranked_rows(store: ReplayStore) -> tuple[Any, ...]:
    repository = getattr(store, "strategy_repository", None)
    assembled = assemble_opportunity_review_rows(
        attention_rows=_attention_rows(store),
        repository=repository,
        source=_opportunity_source(store),
        as_of_time_ns=getattr(store, "as_of_time_ns", None),
        last_source_time_ns=getattr(store, "last_source_time_ns", None),
        runtime_capability=getattr(store, "runtime_capability", None),
        session_state=getattr(store, "session_state", None),
        book_validity=getattr(store, "book_validity", None),
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
    hot_path_collector: HotPathClockCollector | None = None,
) -> dict[str, Any]:
    ranked = build_ranked_rows(store)
    if _is_live(store) and _live_as_of_unavailable(store):
        ranked = ()
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
    items: list[dict[str, Any]] = []
    for row in page:
        serialized = _serialize_review_row(row, store)
        items.append(serialized)
        if hot_path_collector is not None and row.opportunity_id and monotonic_process_ns is not None:
            hot_path_collector.note_operator_surfaced(str(row.opportunity_id), monotonic_process_ns())
    payload: dict[str, Any] = {
        "as_of_context": projections.build_as_of_context(store),
        "quality_summary": projections.build_quality_summary(store),
        "feed_status": status,
        "items": items,
        "next_cursor": next_cursor,
    }
    if status == "UNREADY":
        payload["unready_reason"] = unready_reason
        payload["next_action"] = "/control"
    return payload


def build_opportunity_detail_payload(store: ReplayStore, row_id: str) -> dict[str, Any]:
    if _is_live(store) and _live_as_of_unavailable(store):
        raise KeyError(row_id)
    ranked = build_ranked_rows(store)
    acks = list_operator_acks()
    for row in ranked:
        if row.summary_id == row_id or row.opportunity_id == row_id:
            body = _serialize_review_row(row, store)
            if row.instrument_id:
                body["preview_href"] = f"/workspace/{row.instrument_id}"
            matching = [ack for ack in acks if row.summary_id == ack["summary_id"] or row.opportunity_id == ack.get("opportunity_id")]
            if matching:
                body["lifecycle_state"] = matching[-1]["action"]
            body = overlay_agent_enrichment_on_detail(store, body)
            body = overlay_research_artifact_evidence_on_detail(store, body)
            record_opportunity_surface_trace(
                store,
                row,
                decision_time_ns=int(getattr(store, "as_of_time_ns", None) or 0) or None,
            )
            return overlay_trade_reviews_on_detail(store, body)
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
    identity = detail.get("identity_kind")
    ranking_vector = detail.get("ranking_vector") if isinstance(detail.get("ranking_vector"), dict) else {}
    copy = "not OpportunityV1" if identity == "NOT_OPPORTUNITY_V1" else None
    payload: dict[str, Any] = {
        "identity_kind": identity,
        "evidence_class": detail.get("evidence_class"),
        "evidence_promotion_reason": detail.get("evidence_promotion_reason"),
        "family_admission_status": detail.get("family_admission_status"),
        "family_admission_reason": detail.get("family_admission_reason"),
        "data_quality": detail.get("data_quality"),
        "ranking_basis": ranking_vector.get("basis"),
        "created_at_ns": detail.get("created_at_ns"),
        "duplicates": detail.get("duplicates") or [],
        "supersession_reason": detail.get("supersession_reason"),
        "unavailable_fields": detail.get("unavailable_fields") or [],
        "lineage_refs": lineage,
        "items": lineage,
        "copy": copy,
    }
    if detail.get("research_artifact_evidence") is not None:
        payload["research_artifact_evidence"] = detail["research_artifact_evidence"]
    return payload


def build_opportunity_explain_body(store: ReplayStore, ref: str) -> dict[str, Any]:
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
    ack = record_operator_ack(
        summary_id=target.summary_id,
        opportunity_id=target.opportunity_id,
        paper_account_id=str(account_id),
        action=action,
        created_at_ns=created_at_ns,
    )
    record_operator_lifecycle_trace(
        store,
        target,
        action=action,
        decision_time_ns=created_at_ns,
    )
    row_dict = target.to_dict() if hasattr(target, "to_dict") else {}
    metadata = dict(row_dict.get("metadata") or {}) if isinstance(row_dict.get("metadata"), dict) else {}
    lineage = row_dict.get("lineage_refs") or metadata.get("lineage_refs") or ()
    review = materialize_trade_review_for_operator_ack(
        action=action,
        opportunity_id=target.opportunity_id or target.summary_id,
        strategy_id=row_dict.get("strategy_family") or metadata.get("strategy_family"),
        decision_time_ns=created_at_ns,
        created_at_ns=created_at_ns,
        evidence_snapshot_refs=_refs_from_lineage(tuple(lineage) if isinstance(lineage, (list, tuple)) else ()),
        metadata={"operator_ack": ack},
    )
    if review is not None:
        ack = dict(ack)
        ack["trade_review_id"] = review.review_id
    return ack

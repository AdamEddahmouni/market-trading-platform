"""UiApiHandler request-path for already-fetched Finviz/news → EventV1 admission.

Second hop of already-fetched JSON: FTEP ``--live-ingress`` POSTs #207 rows here after
Finviz fetch; ingestion is labeled ``HISTORICAL_RECONSTRUCTED`` (not ``LIVE_OBSERVED``)
because the CLI carried provider JSON — server still stamps ``received_time_ns`` and rejects
forged ``server_received_time_ns`` in the body. Does not auto-fetch providers.
"""

from __future__ import annotations

from typing import Any

from ..clock import monotonic_wall_ns
from ..intelligence.normalization.models import IngestionMode
from ..news.observational_admit import admit_finviz_export_item_for_observation
from ..news.observational_opportunity import observational_news_opportunity_id
from .live_intelligence import bind_ui_api_intelligence
from .store import ReplayStore

NEWS_INGEST_MAX_BODY_BYTES = 65_536
NEWS_INGEST_ROUTE = "/intelligence/ingest/news"


def enforce_news_ingest_body_limit(content_length: int) -> None:
    if content_length < 0:
        raise ValueError("NEWS_INGEST_CONTENT_LENGTH_INVALID")
    if content_length > NEWS_INGEST_MAX_BODY_BYTES:
        raise ValueError("NEWS_INGEST_BODY_TOO_LARGE")


def handle_news_ingest_post(store: ReplayStore, body: dict[str, Any]) -> dict[str, Any]:
    """Admit already-fetched news rows through ObservationIngressRouter.put_event."""

    bind_ui_api_intelligence(store)
    router = getattr(store, "observation_ingress_router", None)
    if router is None:
        raise ValueError("NEWS_INGEST_ROUTER_UNAVAILABLE")
    articles_raw = body.get("articles")
    if articles_raw is None:
        raise ValueError("NEWS_INGEST_ARTICLES_REQUIRED")
    if not isinstance(articles_raw, list):
        raise ValueError("NEWS_INGEST_ARTICLES_INVALID")
    retrieved_time = str(body.get("retrieved_time") or "").strip()
    if body.get("server_received_time_ns") is not None:
        raise ValueError("NEWS_INGEST_FORGED_SERVER_RECEIVE_TIME")
    server_received_time_ns = int(monotonic_wall_ns())
    admitted: list[dict[str, Any]] = []
    opportunity_ids: list[str] = []
    skipped: list[dict[str, str]] = []
    repository = getattr(store, "strategy_repository", None)
    for item in articles_raw:
        if not isinstance(item, dict):
            skipped.append({"reason": "NEWS_INGEST_ITEM_NOT_OBJECT"})
            continue
        item_retrieved = str(item.get("retrieved_time") or retrieved_time).strip()
        if not item_retrieved:
            skipped.append({"reason": "NEWS_RETRIEVED_TIME_REQUIRED"})
            continue
        outcome = admit_finviz_export_item_for_observation(
            item,
            retrieved_time=item_retrieved,
            router=router,
            store=store,
            server_received_time_ns=server_received_time_ns,
            ingestion_mode=IngestionMode.HISTORICAL_RECONSTRUCTED,
        )
        if not outcome.accepted or outcome.event is None:
            skipped.append(
                {
                    "reason": str(outcome.reason_code or "NEWS_ADMIT_REJECTED"),
                    "detail": str(outcome.detail or ""),
                }
            )
            continue
        event = outcome.event
        receipt = outcome.receipt
        detector_detail = None
        if receipt is not None:
            for row in receipt.outcomes:
                if str(row.kind) != "DETECTOR":
                    continue
                if row.consumer_id == "ingress.observational_news_detector":
                    detector_detail = row.detail
                    break
            if detector_detail is None:
                for row in receipt.outcomes:
                    if str(row.kind) == "DETECTOR":
                        detector_detail = row.detail
                        break
        opportunity_id = observational_news_opportunity_id(event.event_id)
        persisted = None
        getter = getattr(repository, "get_opportunity", None)
        if callable(getter):
            persisted = getter(opportunity_id)
        if persisted is None:
            opportunity_id = None
        else:
            opportunity_ids.append(opportunity_id)
        admitted.append(
            {
                "event_id": event.event_id,
                "opportunity_id": opportunity_id,
                "detector_detail": detector_detail,
                "event_time_ns": event.event_time_ns,
                "available_time_ns": event.available_time_ns,
                "received_time_ns": event.received_time_ns,
                "provider_time_ns": event.provider_time_ns,
            }
        )
    return {
        "admitted_count": len(admitted),
        "opportunity_count": len(opportunity_ids),
        "zero_qualifying_count": len(admitted) - len(opportunity_ids),
        "skipped_count": len(skipped),
        "events": admitted,
        "opportunity_ids": opportunity_ids,
        "skipped": skipped,
        "live_authority": False,
        "auto_fetch": False,
        "news_event_build09": "INACTIVE",
    }


__all__ = [
    "NEWS_INGEST_MAX_BODY_BYTES",
    "NEWS_INGEST_ROUTE",
    "enforce_news_ingest_body_limit",
    "handle_news_ingest_post",
]

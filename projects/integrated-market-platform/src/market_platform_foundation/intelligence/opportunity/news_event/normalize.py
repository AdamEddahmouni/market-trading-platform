"""Accept and normalize NEWS_ARTICLE EventV1 into CanonicalNewsInput."""

from __future__ import annotations

from typing import Any, Mapping

from ....news.catalysts import DEFAULT_CATALYST_REGISTRY, CatalystRegistry
from ....news.observational_opportunity import instrument_id_from_news_event
from ...contracts import EventV1
from .constants import CANONICAL_NEWS_ARTICLE_EVENT_TYPE, NORMALIZATION_VERSION
from .facts import CanonicalNewsInput


def accepts_canonical_news_article_event(event: EventV1) -> bool:
    """True only for the canonical NEWS_ARTICLE EventV1 lane."""

    return str(event.event_type).upper().replace(" ", "_") == CANONICAL_NEWS_ARTICLE_EVENT_TYPE


def _enabled_catalyst_ids() -> frozenset[str]:
    return frozenset(entry.catalyst_id for entry in DEFAULT_CATALYST_REGISTRY if entry.enabled)


def _payload_text(payload: Mapping[str, Any]) -> str:
    return " ".join(
        [str(payload.get("headline") or ""), str(payload.get("summary") or "")]
    ).strip()


def _asset_class_from_payload(payload: Mapping[str, Any], instrument_id: str) -> str:
    linkages = payload.get("instrument_linkages") or []
    if isinstance(linkages, list) and linkages and isinstance(linkages[0], dict):
        asset = str(linkages[0].get("asset_class") or "").strip().upper()
        if asset:
            return asset
    raw = str(payload.get("asset_class") or "").strip().upper()
    if raw:
        return raw
    # Bare US equity tickers and US:/EQUITY: prefixes default to EQUITY.
    upper = instrument_id.strip().upper()
    if upper.startswith("US:") or upper.startswith("EQUITY:"):
        return "EQUITY"
    if upper and ":" not in upper:
        return "EQUITY"
    return ""


def normalize_news_article_event(event: EventV1) -> CanonicalNewsInput | None:
    """Map NEWS_ARTICLE EventV1 payload into canonical detector input.

    Returns None when the event is not a canonical news article. Missing
    symbol / clocks / catalyst are left for validation to fail closed.
    """

    if not accepts_canonical_news_article_event(event):
        return None
    payload = event.payload if isinstance(event.payload, Mapping) else {}
    instrument_id = instrument_id_from_news_event(event) or ""
    headline = str(payload.get("headline") or "").strip()
    summary = str(payload.get("summary") or "").strip()
    source_id = str(payload.get("source_id") or event.source.source_type or "").strip()
    provider_id = str(event.source.provider_id or payload.get("provider_id") or "").strip()
    catalysts = CatalystRegistry().match(
        _payload_text(payload),
        enabled_catalyst_ids=_enabled_catalyst_ids(),
    )
    flags = tuple(str(flag) for flag in (event.quality.flags or ()))
    return CanonicalNewsInput(
        event_id=event.event_id,
        instrument_id=instrument_id,
        headline=headline,
        summary=summary,
        published_time_ns=int(event.event_time_ns),
        available_time_ns=int(event.available_time_ns),
        provider_id=provider_id,
        source_id=source_id,
        matched_catalyst_ids=catalysts,
        asset_class=_asset_class_from_payload(payload, instrument_id),
        normalization_version=NORMALIZATION_VERSION,
        quality_flags=flags,
    )


__all__ = [
    "accepts_canonical_news_article_event",
    "normalize_news_article_event",
]

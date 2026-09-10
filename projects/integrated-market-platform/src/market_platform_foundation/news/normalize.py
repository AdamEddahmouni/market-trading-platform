"""Normalize raw provider payloads into canonical NewsArticleEvent records."""

from __future__ import annotations

import hashlib
from typing import Any

from ..canonical import sha256_bytes
from .contracts import InstrumentLinkage, NewsArticleEvent, PublicationTimeQuality
from .timestamps import classify_publication_time, to_utc_iso
from .timestamps import parse_utc_iso


NORMALIZATION_VERSION = "news/normalize/1.0.0"


def _build_event_id(
    *,
    provider_id: str,
    provider_native_id: str,
    url: str,
    headline: str,
    source_id: str,
) -> str:
    payload = {
        "provider_id": provider_id,
        "provider_native_id": provider_native_id,
        "url": url,
        "headline": headline,
        "source_id": source_id,
    }
    return sha256_bytes(repr(sorted(payload.items())).encode("utf-8"))[:32]


def _linkages_from_raw(item: dict[str, Any]) -> tuple[InstrumentLinkage, ...]:
    linkages: list[InstrumentLinkage] = []
    instrument_ids = item.get("instrument_ids") or []
    if isinstance(instrument_ids, list):
        for instrument_id in instrument_ids:
            text = str(instrument_id).strip()
            if text:
                linkages.append(InstrumentLinkage(instrument_id=text))
    tickers = item.get("tickers") or []
    if isinstance(tickers, list):
        for ticker in tickers:
            symbol = str(ticker).strip().upper()
            if not symbol:
                continue
            linkages.append(
                InstrumentLinkage(
                    instrument_id=symbol,
                    provider_symbol=symbol,
                    asset_class=str(item.get("asset_class") or "EQUITY"),
                    linkage_method="PROVIDER_SYMBOL",
                )
            )
    if not linkages and item.get("instrument_id"):
        instrument_id = str(item["instrument_id"]).strip()
        linkages.append(InstrumentLinkage(instrument_id=instrument_id))
    return tuple(linkages)


def normalize_raw_item(
    item: dict[str, Any],
    *,
    provider_id: str,
    source_id: str,
    retrieved_time: str,
) -> NewsArticleEvent:
    raw_published = str(item.get("published_time") or item.get("publishedAt") or "")
    published, quality, quality_flags = classify_publication_time(
        raw_published,
        retrieved_time=retrieved_time,
    )
    retrieved = retrieved_time
    parsed_retrieved = parse_utc_iso(retrieved_time)
    if parsed_retrieved is not None:
        retrieved = to_utc_iso(parsed_retrieved)
    provider_native_id = str(
        item.get("provider_native_id")
        or item.get("provider_news_id")
        or item.get("id")
        or ""
    )
    headline = str(item.get("headline") or item.get("title") or "")
    url = str(item.get("url") or "")
    all_flags = tuple(quality_flags)
    event_id = _build_event_id(
        provider_id=provider_id,
        provider_native_id=provider_native_id,
        url=url,
        headline=headline,
        source_id=source_id,
    )
    return NewsArticleEvent(
        event_id=event_id,
        provider_id=provider_id,
        provider_native_id=provider_native_id,
        source_id=source_id,
        published_time=published,
        published_time_quality=quality,
        retrieved_time=retrieved,
        headline=headline,
        summary=str(item.get("summary") or item.get("description") or ""),
        url=url,
        language=str(item.get("language") or "en"),
        instrument_linkages=_linkages_from_raw(item),
        publisher_source=str(item.get("publisher_source") or item.get("source") or ""),
        raw_reference=hashlib.sha256(str(item.get("raw_fields", item)).encode("utf-8")).hexdigest()[:16],
        quality_flags=all_flags,
        normalization_version=NORMALIZATION_VERSION,
    )


__all__ = ["NORMALIZATION_VERSION", "normalize_raw_item"]

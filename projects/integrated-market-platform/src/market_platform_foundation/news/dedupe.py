"""Deterministic news event deduplication."""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

from .contracts import DuplicateRelationship, NewsArticleEvent


def _canonical_url(url: str) -> str:
    text = (url or "").strip().lower()
    if not text:
        return ""
    parsed = urlparse(text)
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _normalize_headline(headline: str) -> str:
    text = " ".join(str(headline or "").lower().split())
    text = re.sub(r"[^\w\s]", "", text)
    return text.strip()


def dedupe_identity_key(event: NewsArticleEvent) -> tuple[str, ...]:
    if event.provider_native_id:
        return ("provider_native", event.provider_id, event.provider_native_id)
    url = _canonical_url(event.url)
    if url:
        return ("url", url)
    headline = _normalize_headline(event.headline)
    if headline:
        return ("headline", event.source_id, headline)
    return ("event_id", event.event_id)


def content_fingerprint(event: NewsArticleEvent) -> str:
    payload = "|".join(
        [
            _canonical_url(event.url),
            _normalize_headline(event.headline),
            event.source_id,
            event.published_time,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def classify_duplicate(
    existing: NewsArticleEvent,
    candidate: NewsArticleEvent,
) -> DuplicateRelationship:
    if dedupe_identity_key(existing) == dedupe_identity_key(candidate):
        return DuplicateRelationship.EXACT_DUPLICATE
    if content_fingerprint(existing) == content_fingerprint(candidate):
        return DuplicateRelationship.LIKELY_SYNDICATED
    return DuplicateRelationship.DISTINCT


def dedupe_events(events: list[NewsArticleEvent]) -> tuple[list[NewsArticleEvent], dict[str, str]]:
    """Return unique events in stable input order and a map duplicate_id -> canonical_id."""
    unique: list[NewsArticleEvent] = []
    key_to_index: dict[tuple[str, ...], int] = {}
    fingerprint_to_index: dict[str, int] = {}
    duplicate_map: dict[str, str] = {}
    for event in events:
        key = dedupe_identity_key(event)
        if key in key_to_index:
            canonical = unique[key_to_index[key]]
            duplicate_map[event.event_id] = canonical.event_id
            continue
        fingerprint = content_fingerprint(event)
        if fingerprint in fingerprint_to_index:
            canonical = unique[fingerprint_to_index[fingerprint]]
            duplicate_map[event.event_id] = canonical.event_id
            continue
        key_to_index[key] = len(unique)
        fingerprint_to_index[fingerprint] = len(unique)
        unique.append(event)
    return unique, duplicate_map


__all__ = [
    "classify_duplicate",
    "content_fingerprint",
    "dedupe_events",
    "dedupe_identity_key",
]

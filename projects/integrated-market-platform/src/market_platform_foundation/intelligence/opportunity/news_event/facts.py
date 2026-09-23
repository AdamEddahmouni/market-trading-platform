"""Canonical news input facts extracted from NEWS_ARTICLE EventV1."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CanonicalNewsInput:
    """Provider-agnostic news facts for the BUILD 09 NEWS_EVENT detector.

    Built only from EventV1 (NEWS_ARTICLE) — never from raw Finviz rows.
    """

    event_id: str
    instrument_id: str
    headline: str
    summary: str
    published_time_ns: int
    available_time_ns: int
    provider_id: str
    source_id: str
    matched_catalyst_ids: tuple[str, ...]
    asset_class: str
    normalization_version: str
    quality_flags: tuple[str, ...] = ()


__all__ = ["CanonicalNewsInput"]

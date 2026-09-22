"""Project authoritative provider-linkage quality flags into operator phrases.

Translation lives **here** (backend). The UI must render
``provider_linkage_warnings`` as supplied and must not invent a second map
or infer ticker contradictions from headlines.

Source of truth: ``OpportunityV1.quality.flags`` (and event flags only when
those already projected onto the opportunity). Only flags emitted by
``news.provider_linkage_quality`` are included. ``PUBLICATION_*`` and other
non-linkage flags are excluded. This projection is separate from
``data_quality`` freshness — linkage warnings must not set STALE/UNKNOWN or
inflate freshness metrics.

Allowed operator phrases (never ``wrong ticker``):
- uncorroborated
- low confidence
- source mismatch
- contextual concern
- source URL missing
"""

from __future__ import annotations

from typing import Iterable

from ...news.provider_linkage_quality import (
    FLAG_ALTERNATE_ENTITY_PROMINENT,
    FLAG_LOW_CONTEXTUAL_CONFIDENCE,
    FLAG_MULTIPLE_CONTRADICTORY,
    FLAG_SOURCE_URL_MISSING,
    FLAG_TICKER_NOT_IN_TEXT,
)

# Authoritative flag → operator phrase. Keys are exactly the tokens
# ``assess_provider_linkage_quality`` emits (no guessed prefixes).
PROVIDER_LINKAGE_FLAG_PHRASES: dict[str, str] = {
    FLAG_TICKER_NOT_IN_TEXT: "uncorroborated",
    FLAG_LOW_CONTEXTUAL_CONFIDENCE: "low confidence",
    FLAG_MULTIPLE_CONTRADICTORY: "source mismatch",
    FLAG_ALTERNATE_ENTITY_PROMINENT: "contextual concern",
    FLAG_SOURCE_URL_MISSING: "source URL missing",
}

PROVIDER_LINKAGE_WARNING_FLAGS: frozenset[str] = frozenset(PROVIDER_LINKAGE_FLAG_PHRASES)


def project_provider_linkage_warnings(flags: Iterable[str] | None) -> tuple[str, ...]:
    """Map linkage quality flags to operator phrases; preserve first-seen order."""

    phrases: list[str] = []
    seen: set[str] = set()
    for raw in flags or ():
        flag = str(raw or "").strip()
        phrase = PROVIDER_LINKAGE_FLAG_PHRASES.get(flag)
        if phrase is None or phrase in seen:
            continue
        seen.add(phrase)
        phrases.append(phrase)
    return tuple(phrases)


__all__ = [
    "PROVIDER_LINKAGE_FLAG_PHRASES",
    "PROVIDER_LINKAGE_WARNING_FLAGS",
    "project_provider_linkage_warnings",
]

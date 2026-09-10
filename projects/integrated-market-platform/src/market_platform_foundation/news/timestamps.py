"""Timezone-aware timestamp normalization and observability semantics."""

from __future__ import annotations

from datetime import datetime, timezone
from ..normalization.equity_bars import iso_to_epoch_ns
from .contracts import NewsArticleEvent, PublicationTimeQuality

UTC = timezone.utc


def parse_utc_iso(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        text = text + "T00:00:00Z"
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def to_utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def epoch_ns_from_iso(value: str) -> int | None:
    if not value:
        return None
    try:
        return iso_to_epoch_ns(value)
    except (ValueError, TypeError, OverflowError):
        return None


def classify_publication_time(
    raw: str | None,
    *,
    retrieved_time: str = "",
) -> tuple[str, PublicationTimeQuality, tuple[str, ...]]:
    """Never silently assign retrieval time as publication time."""
    flags: list[str] = []
    if not raw or not str(raw).strip():
        return "", PublicationTimeQuality.UNKNOWN, ("PUBLICATION_TIME_MISSING",)
    parsed = parse_utc_iso(str(raw))
    if parsed is None:
        return "", PublicationTimeQuality.UNKNOWN, ("PUBLICATION_TIME_MALFORMED",)
    published = to_utc_iso(parsed)
    if len(str(raw).strip()) == 10:
        flags.append("PUBLICATION_TIME_DATE_ONLY")
        quality = PublicationTimeQuality.INFERRED_LOW_CONFIDENCE
    else:
        quality = PublicationTimeQuality.KNOWN
    retrieved_ns = epoch_ns_from_iso(retrieved_time)
    published_ns = epoch_ns_from_iso(published)
    if retrieved_ns is not None and published_ns is not None:
        if published_ns > retrieved_ns:
            flags.append("PUBLICATION_AFTER_RETRIEVAL")
        future_now = int(datetime.now(UTC).timestamp() * 1_000_000_000)
        if published_ns > future_now + 300_000_000_000:
            flags.append("PUBLICATION_TIME_FUTURE_DATED")
    return published, quality, tuple(flags)


def observable_time_iso(event: NewsArticleEvent) -> str:
    """When IMP could have known about the event (retrieval/observation time)."""
    return event.retrieved_time


def observable_time_ns(event: NewsArticleEvent) -> int | None:
    return epoch_ns_from_iso(observable_time_iso(event))


def is_observable_at(event: NewsArticleEvent, as_of_ns: int) -> bool:
    observed = observable_time_ns(event)
    if observed is None:
        return False
    return observed <= as_of_ns


def age_reference_time(event: NewsArticleEvent) -> tuple[str, str]:
    """Return (iso_time, basis) for recency age — never conflates semantics."""
    if event.published_time and event.published_time_quality != PublicationTimeQuality.UNKNOWN:
        return event.published_time, "PUBLISHED_TIME"
    return event.retrieved_time, "RETRIEVED_TIME_AGE_PROXY"


def age_seconds_at(event: NewsArticleEvent, as_of_ns: int) -> int | None:
    basis_iso, _ = age_reference_time(event)
    basis_ns = epoch_ns_from_iso(basis_iso)
    if basis_ns is None:
        return None
    return max(0, (as_of_ns - basis_ns) // 1_000_000_000)


__all__ = [
    "age_reference_time",
    "age_seconds_at",
    "classify_publication_time",
    "epoch_ns_from_iso",
    "is_observable_at",
    "observable_time_iso",
    "observable_time_ns",
    "parse_utc_iso",
    "to_utc_iso",
]

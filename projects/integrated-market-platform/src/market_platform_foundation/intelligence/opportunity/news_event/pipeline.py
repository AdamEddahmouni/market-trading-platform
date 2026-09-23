"""Canonical NEWS_ARTICLE EventV1 → NEWS_EVENT DetectionV1 (BUILD 09).

Does not call OpportunityEngine.assess (ForecastV1 + champion still required).
Evidence class for fixture/software proofs: SOFTWARE_CONTROLLED / FIXTURE_REPLAY.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...contracts import DetectionV1, EventV1, SnapshotV1
from .detector import build_news_event_detection
from .normalize import accepts_canonical_news_article_event, normalize_news_article_event
from .validation import NewsEventValidation, validate_news_event_inputs


@dataclass(frozen=True, slots=True)
class NewsEventVerticalResult:
    ok: bool
    reason_codes: tuple[str, ...] = ()
    detection: DetectionV1 | None = None


def run_news_event_vertical(
    *,
    event: EventV1,
    snapshot: SnapshotV1,
    allow_degraded_inputs: bool = False,
) -> NewsEventVerticalResult:
    validated: NewsEventValidation = validate_news_event_inputs(
        event=event,
        snapshot=snapshot,
        allow_degraded_inputs=allow_degraded_inputs,
    )
    if not validated.ok or validated.facts is None:
        return NewsEventVerticalResult(False, validated.reason_codes)
    detection = build_news_event_detection(
        event=event,
        snapshot=snapshot,
        facts=validated.facts,
    )
    return NewsEventVerticalResult(True, (), detection=detection)


__all__ = [
    "NewsEventVerticalResult",
    "accepts_canonical_news_article_event",
    "normalize_news_article_event",
    "run_news_event_vertical",
    "validate_news_event_inputs",
]

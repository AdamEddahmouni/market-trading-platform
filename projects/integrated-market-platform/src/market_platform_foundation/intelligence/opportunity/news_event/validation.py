"""Fail-closed validation for BUILD 09 NEWS_EVENT detection."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ....news.contracts import PipelineConfig
from ...contracts import EventV1, QualityState, SnapshotV1
from .facts import CanonicalNewsInput
from .normalize import accepts_canonical_news_article_event, normalize_news_article_event


class NewsEventFailureCode(StrEnum):
    EVENT_NOT_ACCEPTED = "NEWS_EVENT_NOT_ACCEPTED"
    MISSING_SYMBOL = "MISSING_SYMBOL"
    UNSUPPORTED_INSTRUMENT = "UNSUPPORTED_INSTRUMENT"
    EVENT_CLOCKS_INVALID = "EVENT_CLOCKS_INVALID"
    SNAPSHOT_BEFORE_AVAILABILITY = "SNAPSHOT_BEFORE_AVAILABILITY"
    STALE_PIT_INVALID = "STALE_PIT_INVALID"
    EVENT_QUALITY_INVALID = "EVENT_QUALITY_INVALID"
    NO_CATALYST_MATCH = "NO_CATALYST_MATCH"
    INPUT_QUALITY_REJECTED = "INPUT_QUALITY_REJECTED"


@dataclass(frozen=True, slots=True)
class NewsEventValidation:
    ok: bool
    reason_codes: tuple[str, ...] = ()
    facts: CanonicalNewsInput | None = None


def _instrument_supported(instrument_id: str, snapshot: SnapshotV1, asset_class: str) -> bool:
    text = str(instrument_id or "").strip()
    if not text:
        return False
    scope_ids = set(snapshot.scope.instrument_ids)
    if scope_ids and text not in scope_ids:
        # Allow bare ticker vs US:TICKER equivalence within the snapshot scope.
        bare = text.split(":")[-1]
        scope_bares = {item.split(":")[-1] for item in scope_ids}
        if bare not in scope_bares:
            return False
    asset = str(asset_class or "").strip().upper()
    if asset and asset not in {"EQUITY", "US_EQUITY", "STOCK", "REGULATORY"}:
        return False
    upper = text.upper()
    if ":" in upper and not (upper.startswith("US:") or upper.startswith("EQUITY:")):
        return False
    return True


def validate_news_event_inputs(
    *,
    event: EventV1,
    snapshot: SnapshotV1,
    allow_degraded_inputs: bool = False,
    pipeline_config: PipelineConfig | None = None,
) -> NewsEventValidation:
    """Validate NEWS_ARTICLE EventV1 for NEWS_EVENT DetectionV1 emission."""

    if not accepts_canonical_news_article_event(event):
        return NewsEventValidation(False, (NewsEventFailureCode.EVENT_NOT_ACCEPTED.value,))
    if event.quality.state == QualityState.INVALID:
        return NewsEventValidation(False, (NewsEventFailureCode.EVENT_QUALITY_INVALID.value,))
    if event.quality.state in {QualityState.DEGRADED, QualityState.UNKNOWN} and not allow_degraded_inputs:
        return NewsEventValidation(False, (NewsEventFailureCode.INPUT_QUALITY_REJECTED.value,))
    if event.event_time_ns <= 0 or event.available_time_ns <= 0:
        return NewsEventValidation(False, (NewsEventFailureCode.EVENT_CLOCKS_INVALID.value,))
    if event.event_time_ns > event.available_time_ns:
        return NewsEventValidation(False, (NewsEventFailureCode.EVENT_CLOCKS_INVALID.value,))
    if snapshot.decision_time_ns < event.available_time_ns:
        return NewsEventValidation(
            False,
            (NewsEventFailureCode.SNAPSHOT_BEFORE_AVAILABILITY.value,),
        )

    facts = normalize_news_article_event(event)
    if facts is None:
        return NewsEventValidation(False, (NewsEventFailureCode.EVENT_NOT_ACCEPTED.value,))
    if not facts.instrument_id.strip():
        return NewsEventValidation(False, (NewsEventFailureCode.MISSING_SYMBOL.value,))
    if not _instrument_supported(facts.instrument_id, snapshot, facts.asset_class):
        return NewsEventValidation(False, (NewsEventFailureCode.UNSUPPORTED_INSTRUMENT.value,))

    config = pipeline_config or PipelineConfig()
    age_ns = int(snapshot.decision_time_ns) - int(facts.published_time_ns)
    max_age_ns = int(config.recency_max_age_seconds) * 1_000_000_000
    future_tol_ns = int(config.recency_reject_future_seconds) * 1_000_000_000
    if facts.published_time_ns > snapshot.decision_time_ns + future_tol_ns:
        return NewsEventValidation(False, (NewsEventFailureCode.STALE_PIT_INVALID.value,))
    if age_ns > max_age_ns:
        return NewsEventValidation(False, (NewsEventFailureCode.STALE_PIT_INVALID.value,))

    if config.require_catalyst_match and not facts.matched_catalyst_ids:
        return NewsEventValidation(False, (NewsEventFailureCode.NO_CATALYST_MATCH.value,))

    return NewsEventValidation(True, (), facts)


__all__ = [
    "NewsEventFailureCode",
    "NewsEventValidation",
    "validate_news_event_inputs",
]

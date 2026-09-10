"""Event-time-safe feature snapshot construction."""

from __future__ import annotations

from market_platform_foundation.intelligence.inference.contracts import InferenceRecord
from market_platform_foundation.news.catalysts import CatalystRegistry
from market_platform_foundation.news.contracts import NewsArticleEvent, PipelineEventResult
from market_platform_foundation.news.sources import SourceTrustCatalog
from market_platform_foundation.news.timestamps import age_seconds_at, epoch_ns_from_iso, is_observable_at

from .contracts import (
    DeterministicNewsFeatures,
    IntelligenceFeatures,
    MarketFeatures,
    StrategyFeatureSnapshot,
)
from .errors import EvaluationError, EvaluationErrorCode
from .hashing import feature_snapshot_hash
from .market_data import FixtureMarketDataProvider


def assert_events_observable_at(events: list[NewsArticleEvent], as_of: str) -> None:
    as_of_ns = epoch_ns_from_iso(as_of)
    if as_of_ns is None:
        raise EvaluationError(EvaluationErrorCode.CONFIG_INVALID, f"invalid as_of: {as_of}")
    for event in events:
        if not is_observable_at(event, as_of_ns):
            raise EvaluationError(
                EvaluationErrorCode.FUTURE_NEWS_LEAK,
                f"event {event.event_id} not observable at {as_of}",
            )


def assert_inference_observable_at(record: InferenceRecord, as_of: str) -> None:
    as_of_ns = epoch_ns_from_iso(as_of)
    completed_ns = epoch_ns_from_iso(record.result.completed_time if record.result else "")
    if as_of_ns is None:
        raise EvaluationError(EvaluationErrorCode.CONFIG_INVALID, f"invalid as_of: {as_of}")
    if completed_ns is not None and completed_ns > as_of_ns:
        raise EvaluationError(
            EvaluationErrorCode.FUTURE_INFERENCE_LEAK,
            f"inference {record.record_id} completed after as_of",
        )
    if record.result and epoch_ns_from_iso(record.result.as_of):
        result_as_of_ns = epoch_ns_from_iso(record.result.as_of)
        if result_as_of_ns is not None and result_as_of_ns > as_of_ns:
            raise EvaluationError(
                EvaluationErrorCode.FUTURE_INFERENCE_LEAK,
                f"inference result as_of after evaluation as_of",
            )


def _catalyst_ids_for_events(
    events: list[NewsArticleEvent],
    pipeline_results: list[PipelineEventResult] | None,
) -> tuple[str, ...]:
    if pipeline_results:
        ids: list[str] = []
        for result in pipeline_results:
            for decision in result.decisions:
                ids.extend(decision.matched_catalyst_ids)
        return tuple(sorted(set(ids)))
    registry = CatalystRegistry()
    found: set[str] = set()
    for event in events:
        text = f"{event.headline} {event.summary}".lower()
        matches = registry.match(text, enabled_catalyst_ids=frozenset())
        found.update(matches)
    return tuple(sorted(found))


def _source_tiers(source_ids: tuple[str, ...]) -> tuple[str, ...]:
    catalog = SourceTrustCatalog()
    tiers: list[str] = []
    for source_id in source_ids:
        entry = catalog.get(source_id)
        tiers.append(str(entry.tier) if entry else "UNKNOWN")
    return tuple(tiers)


def build_feature_snapshot(
    *,
    as_of: str,
    instrument_id: str,
    asset_class: str,
    events: list[NewsArticleEvent],
    market_provider: FixtureMarketDataProvider,
    inference_record: InferenceRecord | None = None,
    pipeline_results: list[PipelineEventResult] | None = None,
    overlap_sample_ids: tuple[str, ...] = (),
    overlap_flags: tuple[str, ...] = (),
) -> StrategyFeatureSnapshot:
    assert_events_observable_at(events, as_of)
    if inference_record is not None:
        assert_inference_observable_at(inference_record, as_of)

    as_of_ns = epoch_ns_from_iso(as_of)
    if as_of_ns is None:
        raise EvaluationError(EvaluationErrorCode.CONFIG_INVALID, f"invalid as_of: {as_of}")

    ages = [age_seconds_at(event, as_of_ns) for event in events]
    ages_valid = [age for age in ages if age is not None]
    source_ids = tuple(sorted({event.source_id for event in events}))
    catalyst_ids = _catalyst_ids_for_events(events, pipeline_results)

    deterministic = DeterministicNewsFeatures(
        event_count=len(events),
        catalyst_ids=catalyst_ids,
        source_ids=source_ids,
        source_trust_tiers=_source_tiers(source_ids),
        youngest_event_age_seconds=min(ages_valid) if ages_valid else None,
        oldest_event_age_seconds=max(ages_valid) if ages_valid else None,
        publication_times=tuple(event.published_time for event in events),
        retrieval_times=tuple(event.retrieved_time for event in events),
    )

    series = market_provider.get_series(instrument_id)
    if series is None:
        raise EvaluationError(EvaluationErrorCode.MARKET_DATA_MISSING, instrument_id)
    series.assert_observable_at(as_of)
    price, bar_time = market_provider.price_at_as_of(instrument_id, as_of)
    prior_bar = series.bar_at_or_before(as_of)
    return_1 = None
    if prior_bar and price is not None:
        bars = series.bars
        idx = next((i for i, b in enumerate(bars) if b.event_time == prior_bar.event_time), None)
        if idx is not None and idx > 0:
            prev_close = bars[idx - 1].close
            if prev_close:
                return_1 = (price - prev_close) / prev_close

    market = MarketFeatures(
        instrument_id=instrument_id,
        asset_class=asset_class,
        price_at_as_of=price,
        return_1_bar=return_1,
        bar_event_time=bar_time,
        market_data_ref=series.series_ref,
    )

    intelligence: IntelligenceFeatures | None = None
    if inference_record and inference_record.result and inference_record.result.output:
        output = inference_record.result.output
        intelligence = IntelligenceFeatures(
            inference_record_id=inference_record.record_id,
            sentiment_label=output.sentiment_label.value if output.sentiment_label else None,
            sentiment_score=output.sentiment_score,
            market_impact_level=output.market_impact_level.value if output.market_impact_level else None,
            impact_horizon=output.impact_horizon.value if output.impact_horizon else None,
            model_confidence=output.model_confidence,
            confidence_kind=output.confidence_kind.value,
            catalyst_interpretation=output.catalyst_interpretation,
            prompt_id=inference_record.result.prompt_id,
            prompt_version=inference_record.result.prompt_version,
            model_id=inference_record.result.model_id,
        )

    provisional = StrategyFeatureSnapshot(
        snapshot_id="",
        as_of=as_of,
        instrument_id=instrument_id,
        asset_class=asset_class,
        news_event_ids=tuple(sorted(event.event_id for event in events)),
        deterministic=deterministic,
        market=market,
        intelligence=intelligence,
        overlap_sample_ids=overlap_sample_ids,
        overlap_flags=overlap_flags,
    )
    snap_hash = feature_snapshot_hash(provisional)
    return StrategyFeatureSnapshot(
        snapshot_id=f"FTRSNAP-{snap_hash[:16]}",
        as_of=provisional.as_of,
        instrument_id=provisional.instrument_id,
        asset_class=provisional.asset_class,
        news_event_ids=provisional.news_event_ids,
        deterministic=provisional.deterministic,
        market=provisional.market,
        intelligence=provisional.intelligence,
        overlap_sample_ids=provisional.overlap_sample_ids,
        overlap_flags=provisional.overlap_flags,
        snapshot_hash=snap_hash,
    )


__all__ = [
    "assert_events_observable_at",
    "assert_inference_observable_at",
    "build_feature_snapshot",
]

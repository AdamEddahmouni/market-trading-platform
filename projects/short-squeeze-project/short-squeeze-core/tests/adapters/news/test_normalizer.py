from datetime import UTC, datetime

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.diagnostics import DiagnosticCode
from squeeze_core.adapters.news import normalize_news_record, normalize_news_records
from squeeze_core.contracts import (
    EntitlementState,
    EventType,
    IngestionMethod,
    NewsItemPayload,
    ObservationKind,
    QualityState,
)


RECEIVED = datetime(2026, 1, 15, 14, 2, tzinfo=UTC)


def context(**overrides: object) -> AdapterContext:
    values: dict[str, object] = {
        "ingested_at": RECEIVED,
        "source_timezone": "-05:00",
        "provider": "FINVIZ_SHAPED_REPRESENTATIVE",
        "adapter_version": "news-offline-v1",
        "normalization_version": "news-normalization-v1",
        "entitlement_status": EntitlementState.UNKNOWN,
        "collection_method": IngestionMethod.LOADED_FIXTURE,
        "source_endpoint_name": "representative-news-file",
    }
    values.update(overrides)
    return AdapterContext.model_validate(values)


def raw_record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "news-case-original",
        "provider_schema": "NEWS_ITEM_V1",
        "record_type": "NEWS_ITEM",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "source_shape": "FINVIZ",
        "provider": "FINVIZ_SHAPED_REPRESENTATIVE",
        "provider_record_id": "provider-news-001",
        "Title": "TESTA announces café expansion",
        "Date": "2026-01-15T09:00:00-05:00",
        "Url": "https://news.example.invalid/a?id=7&utm_source=feed#fragment",
        "Ticker": "TESTA,TESTB",
        "summary": "Provider supplied summary.",
        "publisher": "Example Wire",
        "author": "A. Reporter",
        "provider_available_at": "2026-01-15T09:01:00-05:00",
        "capture_timestamp": "2026-01-15T09:01:30-05:00",
        "language": "en",
        "content_type": "article",
    }
    value.update(overrides)
    return value


def codes(result) -> set[DiagnosticCode]:
    return {item.code for item in result.diagnostics}


def test_complete_record_maps_to_unchanged_canonical_payload_and_metadata() -> None:
    result = normalize_news_record(raw_record(), context())
    assert result.accepted
    assert len(result.observations) == 1
    observation = result.observations[0]

    assert observation.event_type is EventType.NEWS_ITEM
    assert observation.symbol is None
    assert observation.source_record_id == "provider-news-001"
    assert observation.source_timestamp == datetime(2026, 1, 15, 14, 1, tzinfo=UTC)
    assert observation.received_timestamp == RECEIVED
    assert observation.effective_timestamp == RECEIVED
    assert observation.observation_kind is ObservationKind.PROVIDER_PUBLISHED
    assert observation.quality.state is QualityState.KNOWN_VALUE
    assert isinstance(observation.payload, NewsItemPayload)
    assert observation.payload.headline == "TESTA announces café expansion"
    assert observation.payload.summary == "Provider supplied summary."
    assert observation.payload.url == "https://news.example.invalid/a?id=7"
    assert observation.payload.publisher == "Example Wire"
    assert observation.payload.published_at == datetime(2026, 1, 15, 14, tzinfo=UTC)
    assert observation.payload.associated_symbols == ("TESTA", "TESTB")

    metadata = observation.provenance.provider_metadata
    assert metadata["author"] == "A. Reporter"
    assert metadata["language"] == "en"
    assert metadata["content_type"] == "article"
    assert metadata["canonical_url"] == observation.payload.url
    assert metadata["url_policy_version"] == "news-url-v1"
    assert metadata["provider_availability"] == observation.source_timestamp
    assert metadata["capture_timestamp"] == datetime(2026, 1, 15, 14, 1, 30, tzinfo=UTC)
    assert DiagnosticCode.NEWS_URL_FRAGMENT_REMOVED in codes(result)
    assert DiagnosticCode.NEWS_TRACKING_PARAMETER_REMOVED in codes(result)


def test_missing_optional_metadata_remains_missing_and_is_diagnosed() -> None:
    result = normalize_news_record(
        raw_record(summary=None, publisher=None, author=None, Url=None), context()
    )
    observation = result.observations[0]
    assert observation.payload.summary is None
    assert observation.payload.publisher is None
    assert observation.payload.url is None
    assert {
        DiagnosticCode.NEWS_MISSING_SUMMARY,
        DiagnosticCode.NEWS_MISSING_PUBLISHER,
        DiagnosticCode.NEWS_MISSING_AUTHOR,
        DiagnosticCode.NEWS_MISSING_URL,
        DiagnosticCode.NEWS_PARTIAL_RECORD,
    } <= codes(result)
    assert observation.quality.state is QualityState.MISSING


def test_provider_availability_can_support_missing_publication() -> None:
    result = normalize_news_record(raw_record(Date=None), context())
    assert result.accepted
    assert result.observations[0].payload.published_at is None
    assert result.observations[0].source_timestamp == datetime(2026, 1, 15, 14, 1, tzinfo=UTC)
    assert DiagnosticCode.NEWS_MISSING_PUBLICATION_TIMESTAMP in codes(result)


def test_missing_availability_rejects_strict_but_uncertain_uses_receipt() -> None:
    strict = normalize_news_record(
        raw_record(Date=None, provider_available_at=None, capture_timestamp=None), context()
    )
    assert not strict.accepted
    assert strict.rejection.code is DiagnosticCode.NEWS_UNKNOWN_AVAILABILITY

    uncertain = normalize_news_record(
        raw_record(
            Date=None,
            provider_available_at=None,
            capture_timestamp=None,
            date_only_policy="UNCERTAIN_PLACEHOLDER",
        ),
        context(),
    )
    assert uncertain.accepted
    assert uncertain.observations[0].source_timestamp == RECEIVED
    assert DiagnosticCode.NEWS_UNCERTAIN_AVAILABILITY in codes(uncertain)


def test_explicit_empty_and_missing_symbol_associations_remain_distinct_in_metadata() -> None:
    missing = raw_record()
    missing.pop("Ticker")
    empty = raw_record(Ticker="")
    missing_result = normalize_news_record(missing, context())
    empty_result = normalize_news_record(empty, context())

    assert missing_result.observations[0].payload.associated_symbols == ()
    assert empty_result.observations[0].payload.associated_symbols == ()
    assert missing_result.observations[0].provenance.provider_metadata["symbol_association_status"] == "MISSING"
    assert empty_result.observations[0].provenance.provider_metadata["symbol_association_status"] == "EXPLICIT_EMPTY"
    assert DiagnosticCode.NEWS_MISSING_SYMBOL_ASSOCIATION in codes(missing_result)
    assert DiagnosticCode.NEWS_EMPTY_SYMBOL_ASSOCIATION in codes(empty_result)


def test_invalid_headline_and_unsupported_type_reject_with_typed_codes() -> None:
    invalid = normalize_news_record(raw_record(Title="   "), context())
    unsupported = normalize_news_record(raw_record(record_type="ARTICLE"), context())
    assert invalid.rejection.code is DiagnosticCode.NEWS_INVALID_HEADLINE
    assert unsupported.rejection.code is DiagnosticCode.NEWS_UNSUPPORTED_RECORD_TYPE


def test_update_preserves_original_publication_and_links_immutable_observations() -> None:
    original = raw_record()
    update = raw_record(
        source_record_id="news-case-updated",
        provider_record_id="provider-news-002",
        status="UPDATED",
        supersedes_provider_record_id="provider-news-001",
        updated_at="2026-01-15T09:20:00-05:00",
        provider_available_at="2026-01-15T09:20:30-05:00",
        Title="TESTA announces café expansion — updated",
    )
    batch = normalize_news_records([update, original], context(ingested_at=datetime(2026, 1, 15, 14, 21, tzinfo=UTC)))
    first, second = batch.observations

    assert first.payload.published_at == second.payload.published_at
    assert first.parent_observation_ids == ()
    assert second.parent_observation_ids == (first.observation_id,)
    assert first.correlation_id == second.correlation_id
    assert second.provenance.provider_metadata["updated_at"] == datetime(2026, 1, 15, 14, 20, tzinfo=UTC)
    assert DiagnosticCode.NEWS_UPDATED_RECORD in codes(batch)


def test_batch_suppresses_exact_duplicate_and_preserves_same_id_conflict() -> None:
    duplicate_batch = normalize_news_records([raw_record(), raw_record()], context())
    assert len(duplicate_batch.observations) == 1
    assert DiagnosticCode.NEWS_DUPLICATE_RECORD in codes(duplicate_batch)

    changed = raw_record(source_record_id="news-case-conflict", Title="Changed headline")
    conflict_batch = normalize_news_records([raw_record(), changed], context())
    assert len(conflict_batch.observations) == 2
    assert all(item.quality.state is QualityState.CONFLICTED for item in conflict_batch.observations)
    assert len({item.observation_id for item in conflict_batch.observations}) == 2
    assert len({item.correlation_id for item in conflict_batch.observations}) == 1
    assert DiagnosticCode.NEWS_CONFLICTING_RECORD in codes(conflict_batch)


def test_normalization_is_byte_stable_for_identical_inputs() -> None:
    first = normalize_news_records([raw_record()], context())
    second = normalize_news_records([raw_record()], context())
    assert first == second
    assert first.observations[0].raw_payload_hash == second.observations[0].raw_payload_hash
    assert first.observations[0].observation_id == second.observations[0].observation_id

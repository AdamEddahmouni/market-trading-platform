from datetime import UTC, datetime

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.news import normalize_news_record
from squeeze_core.contracts import EntitlementState, EventType, IngestionMethod
from squeeze_core.evidence import (
    CoverageDomain,
    CoverageState,
    EvidenceDiagnosticCode,
    PointInTimeEvidencePolicy,
    build_point_in_time_evidence,
)
from squeeze_core.serialization import canonical_json_bytes


def raw(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "news-original",
        "provider_schema": "NEWS_ITEM_V1",
        "record_type": "NEWS_ITEM",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "source_shape": "PROVIDER_NEUTRAL",
        "provider": "SYNTHETIC_NEWS",
        "provider_record_id": "news-001",
        "headline": "TESTA objective update",
        "summary": "Source supplied summary.",
        "publisher": "Example Wire",
        "author": "Reporter",
        "url": "https://news.example.invalid/testa/1",
        "published_at": "2026-01-15T14:00:00Z",
        "provider_available_at": "2026-01-15T14:01:00Z",
        "capture_timestamp": "2026-01-15T14:01:30Z",
        "symbols": ["TESTA", "TESTB"],
        "status": "ORIGINAL",
    }
    value.update(overrides)
    return value


def normalized(received: str, **overrides: object):
    context = AdapterContext(
        ingested_at=datetime.fromisoformat(received.replace("Z", "+00:00")),
        source_timezone="UTC",
        provider="SYNTHETIC_NEWS",
        adapter_version="news-offline-v1",
        normalization_version="news-normalization-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
    )
    return normalize_news_record(raw(**overrides), context).observations[0]


def policy(as_of: str, **overrides: object) -> PointInTimeEvidencePolicy:
    values: dict[str, object] = {
        "as_of": datetime.fromisoformat(as_of.replace("Z", "+00:00")),
        "include_news_domain": True,
    }
    values.update(overrides)
    return PointInTimeEvidencePolicy.model_validate(values)


def coverage(bundle):
    return next(item for item in bundle.source_coverage if item.domain is CoverageDomain.NEWS)


def codes(bundle) -> set[EvidenceDiagnosticCode]:
    return {item.code for item in bundle.diagnostics}


def test_before_provider_availability_news_is_excluded() -> None:
    item = normalized("2026-01-15T14:02:00Z")
    bundle = build_point_in_time_evidence("TESTA", [item], policy("2026-01-15T14:00:30Z"))
    assert item not in bundle.observations
    assert coverage(bundle).state is CoverageState.MISSING
    assert EvidenceDiagnosticCode.EVIDENCE_NEWS_NOT_YET_AVAILABLE in codes(bundle)


def test_after_availability_but_before_receipt_news_is_excluded() -> None:
    item = normalized("2026-01-15T14:02:00Z")
    bundle = build_point_in_time_evidence("TESTA", [item], policy("2026-01-15T14:01:30Z"))
    assert item not in bundle.observations
    assert EvidenceDiagnosticCode.EVIDENCE_NEWS_NOT_YET_RECEIVED in codes(bundle)


def test_after_receipt_news_is_eligible_with_distinct_ages() -> None:
    item = normalized("2026-01-15T14:02:00Z")
    bundle = build_point_in_time_evidence("TESTA", [item], policy("2026-01-15T14:05:00Z"))
    assert item in bundle.observations
    assert coverage(bundle).state is CoverageState.PRESENT
    age = next(value for value in bundle.observation_ages if value.observation_id == item.observation_id)
    assert age.publication_age_ms == 300_000
    assert age.availability_age_ms == 180_000
    assert age.capture_age_ms == 210_000
    assert age.update_age_ms is None


def test_multi_symbol_association_uses_payload_without_observation_duplication() -> None:
    item = normalized("2026-01-15T14:02:00Z")
    testa = build_point_in_time_evidence("TESTA", [item], policy("2026-01-15T14:05:00Z"))
    testb = build_point_in_time_evidence("TESTB", [item], policy("2026-01-15T14:05:00Z"))
    assert testa.observations == (item,)
    assert testb.observations == (item,)
    assert item.symbol is None


def test_missing_empty_and_different_association_are_excluded() -> None:
    missing = normalized("2026-01-15T14:02:00Z", symbols=None, provider_record_id="missing")
    empty = normalized("2026-01-15T14:02:00Z", symbols=[], provider_record_id="empty")
    other = normalized("2026-01-15T14:02:00Z", symbols=["TESTC"], provider_record_id="other")
    bundle = build_point_in_time_evidence(
        "TESTA", [missing, empty, other], policy("2026-01-15T14:05:00Z")
    )
    assert not bundle.observations
    assert EvidenceDiagnosticCode.EVIDENCE_NEWS_SYMBOL_NOT_ASSOCIATED in codes(bundle)


def test_update_after_as_of_does_not_rewrite_earlier_bundle() -> None:
    original = normalized("2026-01-15T14:02:00Z")
    update = normalized(
        "2026-01-15T14:21:00Z",
        source_record_id="news-update",
        provider_record_id="news-002",
        status="UPDATED",
        supersedes_provider_record_id="news-001",
        headline="TESTA objective update — revised",
        updated_at="2026-01-15T14:20:00Z",
        provider_available_at="2026-01-15T14:20:30Z",
    )
    observations = [original, update]
    before = build_point_in_time_evidence("TESTA", observations, policy("2026-01-15T14:05:00Z"))
    rebuilt = build_point_in_time_evidence("TESTA", observations, policy("2026-01-15T14:05:00Z"))
    after = build_point_in_time_evidence("TESTA", observations, policy("2026-01-15T14:30:00Z"))

    assert before.bundle_hash == rebuilt.bundle_hash
    assert canonical_json_bytes(before) == canonical_json_bytes(rebuilt)
    assert before.observations == (original,)
    assert after.observations == (original, update)
    update_age = next(value for value in after.observation_ages if value.observation_id == update.observation_id)
    assert update_age.update_age_ms == 600_000


def test_news_coverage_is_independent_and_missing_is_not_interpreted() -> None:
    bundle = build_point_in_time_evidence("TESTA", [], policy("2026-01-15T14:05:00Z"))
    assert coverage(bundle).state is CoverageState.MISSING
    assert EvidenceDiagnosticCode.EVIDENCE_MISSING_NEWS in codes(bundle)
    serialized = canonical_json_bytes(bundle).decode("utf-8").lower()
    assert "neutral" not in serialized
    assert "positive" not in serialized
    assert "negative" not in serialized
    assert EventType.NEWS_ITEM not in policy("2026-01-15T14:05:00Z").maximum_age_ms_by_event_type

from datetime import UTC, datetime

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.news import normalize_news_record, normalize_news_records
from squeeze_core.contracts import EntitlementState, IngestionMethod
from squeeze_core.evidence import (
    CoverageDomain,
    CoverageState,
    EvidenceDiagnosticCode,
    NewsRelationshipKind,
    PointInTimeEvidencePolicy,
    build_point_in_time_evidence,
)


def raw(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "news-original",
        "provider_schema": "NEWS_ITEM_V1",
        "record_type": "NEWS_ITEM",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "source_shape": "PROVIDER_NEUTRAL",
        "provider": "PROVIDER_A",
        "provider_record_id": "provider-a-001",
        "headline": "TESTA objective announcement",
        "summary": "Source supplied summary.",
        "publisher": "Example Wire",
        "author": "Reporter",
        "url": "https://news.example.invalid/shared?id=1",
        "published_at": "2026-01-15T14:00:00Z",
        "provider_available_at": "2026-01-15T14:01:00Z",
        "symbols": ["TESTA"],
        "status": "ORIGINAL",
    }
    value.update(overrides)
    return value


def context(provider: str = "PROVIDER_A", received: str = "2026-01-15T14:02:00Z"):
    return AdapterContext(
        ingested_at=datetime.fromisoformat(received.replace("Z", "+00:00")),
        source_timezone="UTC",
        provider=provider,
        adapter_version="news-offline-v1",
        normalization_version="news-normalization-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
    )


def policy() -> PointInTimeEvidencePolicy:
    return PointInTimeEvidencePolicy(
        as_of=datetime(2026, 1, 15, 15, tzinfo=UTC), include_news_domain=True
    )


def bundle(items):
    return build_point_in_time_evidence("TESTA", items, policy())


def test_explicit_update_correction_withdrawal_and_deletion_relationships() -> None:
    original = normalize_news_record(raw(), context()).observations[0]
    lifecycle = []
    for index, status in enumerate(("UPDATED", "CORRECTED", "WITHDRAWN", "DELETED"), 2):
        lifecycle.append(
            normalize_news_record(
                raw(
                    source_record_id=f"news-{status.lower()}",
                    provider_record_id=f"provider-a-00{index}",
                    status=status,
                    supersedes_provider_record_id=(
                        "provider-a-001" if index == 2 else f"provider-a-00{index - 1}"
                    ),
                    headline=f"TESTA objective announcement — {status.lower()}",
                    updated_at=f"2026-01-15T14:{index}0:00Z",
                    provider_available_at=f"2026-01-15T14:{index}0:30Z",
                ),
                context(received=f"2026-01-15T14:{index}1:00Z"),
            ).observations[0]
        )
    value = bundle([original, *lifecycle])

    assert [item.kind for item in value.news_relationships] == [
        NewsRelationshipKind.REVISION,
        NewsRelationshipKind.CORRECTION,
        NewsRelationshipKind.WITHDRAWAL,
        NewsRelationshipKind.DELETION,
    ]
    assert all(len(item.observation_ids) == 2 for item in value.news_relationships)
    assert EvidenceDiagnosticCode.EVIDENCE_NEWS_UPDATE_AVAILABLE in {
        item.code for item in value.diagnostics
    }
    assert EvidenceDiagnosticCode.EVIDENCE_NEWS_WITHDRAWAL_AVAILABLE in {
        item.code for item in value.diagnostics
    }


def test_same_url_across_providers_is_syndicated_without_merging() -> None:
    first = normalize_news_record(raw(), context("PROVIDER_A")).observations[0]
    second = normalize_news_record(
        raw(
            source_record_id="provider-b-case",
            provider="PROVIDER_B",
            provider_record_id="provider-b-001",
        ),
        context("PROVIDER_B", "2026-01-15T14:03:00Z"),
    ).observations[0]
    value = bundle([first, second])

    syndicated = [
        item for item in value.news_relationships if item.kind is NewsRelationshipKind.SYNDICATED
    ]
    assert len(value.observations) == 2
    assert len(syndicated) == 1
    assert syndicated[0].canonical_url == "https://news.example.invalid/shared?id=1"
    assert EvidenceDiagnosticCode.EVIDENCE_NEWS_SYNDICATION in {
        item.code for item in value.diagnostics
    }


def test_same_provider_id_changed_content_is_conflicted_without_winner() -> None:
    batch = normalize_news_records(
        [raw(), raw(source_record_id="changed-case", headline="Changed objective headline")],
        context(),
    )
    value = bundle(batch.observations)
    fields = {item.semantic_field for item in value.conflicts}
    news_coverage = next(
        item for item in value.source_coverage if item.domain is CoverageDomain.NEWS
    )

    assert "news_headline" in fields
    assert len(value.observations) == 2
    assert news_coverage.state is CoverageState.CONFLICTED
    assert EvidenceDiagnosticCode.EVIDENCE_NEWS_CONFLICT in {
        item.code for item in value.diagnostics
    }


def test_same_url_changed_publication_or_symbols_is_structurally_conflicted() -> None:
    first = normalize_news_record(raw(), context()).observations[0]
    changed = normalize_news_record(
        raw(
            source_record_id="changed-url-metadata",
            provider_record_id="provider-a-099",
            published_at="2026-01-15T14:00:30Z",
            symbols=["TESTA", "TESTB"],
        ),
        context(received="2026-01-15T14:03:00Z"),
    ).observations[0]
    fields = {item.semantic_field for item in bundle([first, changed]).conflicts}
    assert {"news_publication_timestamp", "news_associated_symbols"} <= fields


def test_same_headline_different_urls_and_similar_headlines_remain_independent() -> None:
    first = normalize_news_record(raw(), context()).observations[0]
    different_url = normalize_news_record(
        raw(
            source_record_id="different-url",
            provider_record_id="provider-a-002",
            url="https://news.example.invalid/other?id=2",
        ),
        context(received="2026-01-15T14:03:00Z"),
    ).observations[0]
    similar = normalize_news_record(
        raw(
            source_record_id="similar-headline",
            provider_record_id="provider-a-003",
            headline="TESTA objective announcement!",
            url="https://news.example.invalid/third?id=3",
        ),
        context(received="2026-01-15T14:04:00Z"),
    ).observations[0]
    value = bundle([first, different_url, similar])

    assert len(value.observations) == 3
    assert value.news_relationships == ()
    assert not [item for item in value.conflicts if item.semantic_field.startswith("news_")]


def test_relationship_and_conflict_identifiers_are_deterministic() -> None:
    first = normalize_news_record(raw(), context("PROVIDER_A")).observations[0]
    second = normalize_news_record(
        raw(
            source_record_id="provider-b-case",
            provider="PROVIDER_B",
            provider_record_id="provider-b-001",
            headline="Provider B headline",
        ),
        context("PROVIDER_B", "2026-01-15T14:03:00Z"),
    ).observations[0]
    left = bundle([first, second])
    right = bundle([second, first])
    assert left.news_relationships == right.news_relationships
    assert left.conflicts == right.conflicts
    assert left.bundle_hash == right.bundle_hash

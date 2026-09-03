from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from squeeze_core.adapters.diagnostics import DiagnosticCode
from squeeze_core.adapters.news import (
    NewsDateOnlyPolicy,
    NewsLifecycleStatus,
    NewsParseError,
    NewsRecord,
    NewsSourceShape,
    parse_news_timestamp,
    sanitize_news_url,
)


def base_record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "news-fixture-001",
        "provider_schema": "NEWS_ITEM_V1",
        "record_type": "NEWS_ITEM",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "source_shape": "FINVIZ",
        "provider": "FINVIZ_SHAPED_REPRESENTATIVE",
        "provider_record_id": "provider-news-001",
        "Title": "  TESTA   announces café expansion  ",
        "Date": "2026-01-15T09:00:00-05:00",
        "Url": "HTTPS://News.Example.Invalid/a?id=7&utm_source=feed#section",
        "Ticker": " testa, TESTB, testa ",
        "provider_available_at": "2026-01-15T09:01:00-05:00",
        "capture_timestamp": "2026-01-15T09:01:30-05:00",
    }
    value.update(overrides)
    return value


def test_finviz_aliases_normalize_objective_fields() -> None:
    record = NewsRecord.model_validate(base_record())

    assert record.source_shape is NewsSourceShape.FINVIZ
    assert record.headline == "TESTA announces café expansion"
    assert record.published_at == "2026-01-15T09:00:00-05:00"
    assert record.url.endswith("utm_source=feed#section")
    assert record.symbols == ("TESTA", "TESTB")
    assert record.status is NewsLifecycleStatus.ORIGINAL


def test_yahoo_nested_shape_preserves_summary_and_does_not_infer_symbols() -> None:
    raw = base_record(
        source_shape="YAHOO",
        Title=None,
        Date=None,
        Url=None,
        Ticker=None,
        content={
            "title": "TESTA files an update",
            "summary": "Provider supplied summary.",
            "pubDate": "2026-01-15T14:00:00Z",
            "canonicalUrl": {"url": "https://news.example.invalid/yahoo/1"},
        },
    )
    for key in ("Title", "Date", "Url", "Ticker"):
        raw.pop(key)
    record = NewsRecord.model_validate(raw)

    assert record.headline == "TESTA files an update"
    assert record.summary == "Provider supplied summary."
    assert record.symbols is None


def test_newsapi_nested_shape_maps_documented_fields_only() -> None:
    raw = base_record(
        source_shape="NEWSAPI",
        title="TESTA publishes results",
        description="Source description.",
        author="A. Reporter",
        source={"name": "Example Wire"},
        url="https://news.example.invalid/newsapi/1",
        publishedAt="2026-01-15T14:00:00Z",
        symbols=["TESTA"],
    )
    for key in ("Title", "Date", "Url", "Ticker"):
        raw.pop(key)
    record = NewsRecord.model_validate(raw)

    assert record.publisher == "Example Wire"
    assert record.author == "A. Reporter"
    assert record.symbols == ("TESTA",)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("provider_schema", "NEWS_ITEM_V2"),
        ("record_type", "ARTICLE"),
        ("fixture_origin", "RECORDED"),
        ("source_shape", "RSS"),
    ],
)
def test_unsupported_structure_rejects(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        NewsRecord.model_validate(base_record(**{field: value}))


def test_alias_collision_rejects_instead_of_selecting_a_winner() -> None:
    with pytest.raises(ValidationError):
        NewsRecord.model_validate(base_record(headline="Different headline"))


def test_url_policy_removes_only_fragment_and_documented_tracking() -> None:
    parsed = sanitize_news_url(
        "HTTPS://News.Example.Invalid:443/a?id=7&utm_source=feed&fbclid=x#section"
    )
    assert parsed.url == "https://news.example.invalid/a?id=7"
    assert parsed.fragment_removed
    assert parsed.removed_tracking_parameters == ("utm_source", "fbclid")
    assert parsed.policy_version == "news-url-v1"


@pytest.mark.parametrize(
    ("value", "code"),
    [
        ("ftp://news.example.invalid/a", DiagnosticCode.NEWS_INVALID_URL),
        ("https:///missing-host", DiagnosticCode.NEWS_INVALID_URL),
        ("https://user:pass@news.example.invalid/a", DiagnosticCode.NEWS_INVALID_URL),
        ("https://news.example.invalid/a?token=secret", DiagnosticCode.NEWS_SENSITIVE_URL),
    ],
)
def test_invalid_or_sensitive_urls_reject(value: str, code: DiagnosticCode) -> None:
    with pytest.raises(NewsParseError) as raised:
        sanitize_news_url(value)
    assert raised.value.code is code


def test_exact_timestamp_normalizes_to_utc() -> None:
    parsed = parse_news_timestamp(
        "2026-01-15T09:00:00-05:00",
        timezone_name=None,
        policy=NewsDateOnlyPolicy.STRICT,
        field="published_at",
        received_at=datetime(2026, 1, 15, 15, tzinfo=UTC),
    )
    assert parsed.timestamp == datetime(2026, 1, 15, 14, tzinfo=UTC)
    assert not parsed.uncertain


def test_date_only_policies_are_explicit_and_conservative() -> None:
    received = datetime(2026, 1, 16, 15, tzinfo=UTC)
    with pytest.raises(NewsParseError) as raised:
        parse_news_timestamp(
            "2026-01-15",
            timezone_name="-05:00",
            policy=NewsDateOnlyPolicy.STRICT,
            field="published_at",
            received_at=received,
        )
    assert raised.value.code is DiagnosticCode.NEWS_DATE_ONLY_PUBLICATION

    end_of_day = parse_news_timestamp(
        "2026-01-15",
        timezone_name="-05:00",
        policy=NewsDateOnlyPolicy.CONSERVATIVE_END_OF_DAY,
        field="published_at",
        received_at=received,
    )
    assert end_of_day.timestamp == datetime(2026, 1, 16, 4, 59, 59, 999999, tzinfo=UTC)
    assert not end_of_day.uncertain

    uncertain = parse_news_timestamp(
        "2026-01-15",
        timezone_name=None,
        policy=NewsDateOnlyPolicy.UNCERTAIN_PLACEHOLDER,
        field="published_at",
        received_at=received,
    )
    assert uncertain.timestamp == received
    assert uncertain.uncertain


def test_naive_timestamp_without_timezone_rejects() -> None:
    with pytest.raises(NewsParseError) as raised:
        parse_news_timestamp(
            "2026-01-15T09:00:00",
            timezone_name=None,
            policy=NewsDateOnlyPolicy.STRICT,
            field="published_at",
            received_at=datetime(2026, 1, 15, 15, tzinfo=UTC),
        )
    assert raised.value.code is DiagnosticCode.NEWS_UNKNOWN_PUBLICATION_TIMEZONE

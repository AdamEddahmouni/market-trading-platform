import json
from datetime import UTC, datetime
from decimal import Decimal

from squeeze_core.contracts import EventType
from squeeze_core.validation.outcome_acquisition import (
    AcquisitionDataType,
    AcquisitionResultState,
    build_acquisition_manifest,
)
from squeeze_core.validation.outcome_context import (
    EvidenceAvailability,
    NewsTiming,
    build_unavailable_context,
    normalize_yahoo_news,
    parse_finra_short_sale_volume,
    parse_yahoo_corporate_actions,
)


RETRIEVED = datetime(2026, 7, 21, 21, tzinfo=UTC)


def manifest(data_type, raw):
    return build_acquisition_manifest(
        symbol="BIYA",
        provider="test-provider",
        data_type=data_type,
        requested_start=datetime(2026, 7, 16, tzinfo=UTC),
        requested_end=RETRIEVED,
        retrieved_at=RETRIEVED,
        request_timezone="America/New_York",
        result_state=AcquisitionResultState.SUCCESS,
        raw_bytes=raw,
        raw_relative_path="raw/test.json",
        record_count=1,
    )


def test_news_preserves_publication_and_retrieval_time_and_classifies_timing():
    raw = json.dumps({"news": [{
        "uuid": "news-1", "title": "BIYA update", "publisher": "Wire",
        "providerPublishTime": 1784200000, "relatedTickers": ["BIYA"],
    }]}).encode()
    result = normalize_yahoo_news(manifest(AcquisitionDataType.NEWS, raw), raw)
    assert len(result.observations) == 1
    assert result.observations[0].event_type is EventType.NEWS_ITEM
    assert result.observations[0].received_timestamp == RETRIEVED
    assert result.items[0].timing is NewsTiming.BEFORE_EARLIEST_BOUNDARY
    assert result.items[0].publication_time != RETRIEVED
    assert result.items[0].sanitized_url is None


def test_finra_volume_is_a_distinct_context_not_short_interest():
    raw = b"Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n20260717|BIYA|10.5|1|20.5|Q,N\n"
    result = parse_finra_short_sale_volume(
        manifest(AcquisitionDataType.FINRA_SHORT_SALE_VOLUME, raw), raw
    )
    assert result.data_type == "FINRA_SHORT_SALE_VOLUME"
    assert result.records[0].short_volume == Decimal("10.5")
    assert "short interest" in result.limitations[0].lower()


def test_corporate_action_preserves_split_ratio_and_adjustment_warning():
    raw = json.dumps({"chart": {"result": [{"events": {"splits": {"1": {
        "date": 1783949400, "numerator": 1.0, "denominator": 10.0,
        "splitRatio": "1:10"
    }}}}]}}).encode()
    result = parse_yahoo_corporate_actions(
        manifest(AcquisitionDataType.CORPORATE_ACTIONS, raw), raw
    )
    assert result.observations[0].event_type is EventType.CORPORATE_ACTION
    assert result.actions[0].split_ratio == "1:10"
    assert result.actions[0].effective_date.isoformat() == "2026-07-13"


def test_unavailable_domain_stays_explicit_and_has_no_records():
    result = build_unavailable_context("BORROW", "manifest-1")
    assert result.availability is EvidenceAvailability.UNAVAILABLE
    assert result.evidence_ids == ()

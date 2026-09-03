from datetime import datetime

from squeeze_core.adapters.trades_quotes import normalize_trade_quote_record
from squeeze_core.contracts import EventType
from squeeze_core.evidence import (
    CoverageDomain,
    CoverageState,
    PointInTimeEvidencePolicy,
    build_point_in_time_evidence,
)
from squeeze_core.serialization import canonical_json_bytes

from tests.adapters.trades_quotes.test_models_and_parsing import record_values
from tests.adapters.trades_quotes.test_quote_normalizer import quote_values
from tests.adapters.trades_quotes.test_trade_normalizer import context


def _observation(raw, receipt):
    return normalize_trade_quote_record(raw, context(receipt)).observations[0]


def lifecycle_observations():
    trade = _observation(record_values(provider_record_id="trade-original"), "2026-01-15T14:30:00.300000Z")
    quote = _observation(quote_values(provider_record_id="quote-original"), "2026-01-15T14:30:00.300000Z")
    corrected_trade = _observation(
        record_values(
            provider_record_id="trade-corrected",
            status="CORRECTED",
            revision_number=1,
            supersedes_provider_record_id="trade-original",
            price="10.26",
            event_timestamp="2026-01-15T09:30:00.100000-05:00",
            publication_timestamp="2026-01-15T09:31:00-05:00",
            capture_timestamp="2026-01-15T09:31:00.500000-05:00",
        ),
        "2026-01-15T14:31:01Z",
    )
    cancelled_quote = _observation(
        quote_values(
            provider_record_id="quote-cancelled",
            status="CANCELLED",
            revision_number=1,
            supersedes_provider_record_id="quote-original",
            publication_timestamp="2026-01-15T09:32:00-05:00",
            capture_timestamp="2026-01-15T09:32:00.500000-05:00",
        ),
        "2026-01-15T14:32:01Z",
    )
    return trade, quote, corrected_trade, cancelled_quote


def _bundle(as_of, observations=None):
    return build_point_in_time_evidence(
        "TESTA",
        lifecycle_observations() if observations is None else observations,
        PointInTimeEvidencePolicy(
            as_of=datetime.fromisoformat(as_of.replace("Z", "+00:00")),
            include_trades_domain=True,
            include_quotes_domain=True,
        ),
    )


def test_publication_receipt_correction_and_cancellation_timeline_is_immutable():
    checkpoints = {
        "2026-01-15T14:30:00.150000Z": [],
        "2026-01-15T14:30:00.250000Z": [],
        "2026-01-15T14:30:00.300000Z": ["quote-original", "trade-original"],
        "2026-01-15T14:31:00.500000Z": ["quote-original", "trade-original"],
        "2026-01-15T14:31:01Z": ["quote-original", "trade-corrected", "trade-original"],
        "2026-01-15T14:32:00.500000Z": ["quote-original", "trade-corrected", "trade-original"],
        "2026-01-15T14:32:01Z": ["quote-cancelled", "quote-original", "trade-corrected", "trade-original"],
    }
    for as_of, expected in checkpoints.items():
        bundle = _bundle(as_of)
        assert sorted(item.source_record_id for item in bundle.observations) == expected


def test_trade_and_quote_coverage_are_independent_and_partial_visible():
    trade, _, _, _ = lifecycle_observations()
    bundle = _bundle("2026-01-15T14:30:01Z", (trade,))
    coverage = {item.domain: item for item in bundle.source_coverage}
    assert coverage[CoverageDomain.TRADES].state is CoverageState.PRESENT
    assert coverage[CoverageDomain.QUOTES].state is CoverageState.MISSING

    partial_trade = _observation(record_values(provider_record_id="partial", size=None), "2026-01-15T14:30:00.300000Z")
    partial = _bundle("2026-01-15T14:30:01Z", (partial_trade,))
    states = {item.domain: item.state for item in partial.source_coverage}
    assert states[CoverageDomain.TRADES] is CoverageState.PARTIAL


def test_future_event_is_excluded_even_when_published_and_received():
    future = _observation(
        record_values(
            provider_record_id="future-event",
            event_timestamp="2026-01-15T10:00:00-05:00",
        ),
        "2026-01-15T14:30:00.300000Z",
    )
    bundle = _bundle("2026-01-15T14:31:00Z", (future,))
    assert bundle.observations == ()
    assert "EVIDENCE_TRADE_QUOTE_FUTURE_EVENT" in {item.code.value for item in bundle.diagnostics}


def test_trade_quote_ages_are_separate_and_correction_age_is_conditional():
    bundle = _bundle("2026-01-15T14:32:01Z")
    ages = {item.observation_id: item for item in bundle.observation_ages}
    corrected = next(item for item in bundle.observations if item.source_record_id == "trade-corrected")
    original = next(item for item in bundle.observations if item.source_record_id == "trade-original")
    corrected_age = ages[corrected.observation_id]
    assert corrected_age.event_age_ms == 120900
    assert corrected_age.publication_age_ms == 61000
    assert corrected_age.availability_age_ms == 60000
    assert corrected_age.capture_age_ms == 60500
    assert corrected_age.correction_age_ms == 60000
    assert ages[original.observation_id].correction_age_ms is None


def test_revision_relationships_appear_only_when_both_versions_are_eligible():
    before = _bundle("2026-01-15T14:31:00.500000Z")
    after = _bundle("2026-01-15T14:32:01Z")
    assert before.revision_relationships == ()
    assert {item.status for item in after.revision_relationships} == {"CORRECTED", "CANCELLED"}


def test_historical_rebuild_is_byte_identical_after_later_records_exist():
    observations = lifecycle_observations()
    first = _bundle("2026-01-15T14:30:00.300000Z", observations)
    second = _bundle("2026-01-15T14:30:00.300000Z", tuple(reversed(observations)))
    assert canonical_json_bytes(first) == canonical_json_bytes(second)

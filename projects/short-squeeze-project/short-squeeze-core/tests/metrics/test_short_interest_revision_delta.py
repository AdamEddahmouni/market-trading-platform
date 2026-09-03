from datetime import UTC, datetime

from squeeze_core.contracts import AssetClass, QualityState
from squeeze_core.metrics import MetricUnit
from squeeze_core.metrics.short_interest_changes import (
    ShortInterestRevisionRequest,
    build_short_interest_revision_delta_result,
)

from .conftest import make_short_interest_records, short_interest_record

AS_OF = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
PROVIDER = "finra-provider-test"


def _request(reporting_period, **overrides):
    values = dict(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider=PROVIDER,
        reporting_period=reporting_period,
    )
    values.update(overrides)
    return ShortInterestRevisionRequest(**values)


def _revision_pair(original_shares, revised_shares, *, revision_status="REVISED"):
    records = [
        short_interest_record(
            source_record_id="rev-orig", settlement_date="2026-01-15", publication_date="2026-01-25",
            short_shares=str(original_shares),
        ),
        short_interest_record(
            source_record_id="rev-new", settlement_date="2026-01-15", publication_date="2026-02-05",
            short_shares=str(revised_shares), revision_status=revision_status, revision_number=1,
            supersedes_source_record_id="rev-orig",
        ),
    ]
    return make_short_interest_records(records)


def test_positive_revision_delta():
    observations = _revision_pair(900_000, 950_000)
    request = _request(observations[0].payload.settlement_date)
    result = build_short_interest_revision_delta_result(observations, request)
    assert result.value == 50_000
    assert result.unit is MetricUnit.SHARES
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_negative_revision_delta():
    observations = _revision_pair(950_000, 900_000)
    request = _request(observations[0].payload.settlement_date)
    result = build_short_interest_revision_delta_result(observations, request)
    assert result.value == -50_000


def test_zero_revision_delta():
    observations = _revision_pair(900_000, 900_000)
    request = _request(observations[0].payload.settlement_date)
    result = build_short_interest_revision_delta_result(observations, request)
    assert result.value == 0
    assert result.quality.state is QualityState.KNOWN_VALUE


def test_revision_unavailable_before_publication():
    observations = list(_revision_pair(900_000, 950_000))
    revision_obs = next(o for o in observations if o.provenance.provider_metadata.get("revision_number"))
    original_obs = next(o for o in observations if o is not revision_obs)
    # Simulate the original having been received well before the revision (the batch helper
    # shares one ingested_at) so an as_of between the two only sees the original.
    early_received = datetime(2026, 1, 26, tzinfo=UTC)
    adjusted_original = original_obs.model_copy(
        update={"received_timestamp": early_received, "effective_timestamp": early_received}
    )
    observations = [adjusted_original if o is original_obs else o for o in observations]
    early_as_of = datetime(2026, 1, 27, tzinfo=UTC)
    request = _request(adjusted_original.payload.settlement_date, as_of=early_as_of)
    result = build_short_interest_revision_delta_result(observations, request)
    assert result.value is None
    assert any(d.code.value == "SHORT_INTEREST_REVISION_NOT_FOUND" for d in result.diagnostics)


def test_revision_unavailable_before_receipt():
    records = [
        short_interest_record(
            source_record_id="rev-orig", settlement_date="2026-01-15", publication_date="2026-01-25",
            short_shares="900000",
        ),
        short_interest_record(
            source_record_id="rev-new", settlement_date="2026-01-15", publication_date="2026-01-26",
            short_shares="950000", revision_status="REVISED", revision_number=1,
            supersedes_source_record_id="rev-orig",
        ),
    ]
    observations = make_short_interest_records(records, ingested_at="2026-06-01T00:00:00Z")
    request = _request(observations[0].payload.settlement_date, as_of=datetime(2026, 1, 27, tzinfo=UTC))
    result = build_short_interest_revision_delta_result(observations, request)
    assert result.value is None


def test_original_and_revision_same_reporting_period():
    observations = _revision_pair(900_000, 950_000)
    assert observations[0].payload.settlement_date == observations[1].payload.settlement_date


def test_explicit_revision_link_present():
    observations = _revision_pair(900_000, 950_000)
    revision_obs = max(observations, key=lambda o: o.provenance.provider_metadata.get("revision_number") or 0)
    assert revision_obs.parent_observation_ids


def test_missing_revision_link_when_original_not_in_batch():
    revised_only = short_interest_record(
        source_record_id="rev-new", settlement_date="2026-01-15", publication_date="2026-02-05",
        short_shares="950000", revision_status="REVISED", revision_number=1,
        supersedes_source_record_id="rev-orig-not-present",
    )
    observations = make_short_interest_records([revised_only])
    request = _request(observations[0].payload.settlement_date)
    result = build_short_interest_revision_delta_result(observations, request)
    assert result.value is None
    assert any(d.code.value == "SHORT_INTEREST_REVISION_NOT_FOUND" for d in result.diagnostics)


def test_cancellation_is_not_a_revision():
    records = [
        short_interest_record(
            source_record_id="rev-orig", settlement_date="2026-01-15", publication_date="2026-01-25",
            short_shares="900000",
        ),
        short_interest_record(
            source_record_id="rev-cancel", settlement_date="2026-01-15", publication_date="2026-02-05",
            short_shares="900000", revision_status="CANCELLED", revision_number=1,
            supersedes_source_record_id="rev-orig",
        ),
    ]
    observations = make_short_interest_records(records)
    request = _request(observations[0].payload.settlement_date)
    result = build_short_interest_revision_delta_result(observations, request)
    assert result.value is None
    assert any(d.code.value == "SHORT_INTEREST_CANCELLED_INPUT" for d in result.diagnostics)


def test_same_id_changed_content_is_a_conflict_not_a_revision():
    records = [
        short_interest_record(
            source_record_id="dup-a", settlement_date="2026-01-15", publication_date="2026-01-25",
            short_shares="900000",
        ),
        short_interest_record(
            source_record_id="dup-b", settlement_date="2026-01-15", publication_date="2026-01-25",
            short_shares="999999",
        ),
    ]
    observations = make_short_interest_records(records)
    request = _request(observations[0].payload.settlement_date)
    result = build_short_interest_revision_delta_result(observations, request)
    assert result.value is None
    assert result.quality.state is QualityState.CONFLICTED


def test_historical_metric_before_revision_unchanged():
    observations = _revision_pair(900_000, 950_000)
    revision_obs = max(observations, key=lambda o: o.provenance.provider_metadata.get("revision_number") or 0)
    before = revision_obs.effective_timestamp.replace(day=1)
    request = _request(observations[0].payload.settlement_date, as_of=before)
    result_before = build_short_interest_revision_delta_result(observations, request)
    result_before_again = build_short_interest_revision_delta_result(observations, request)
    assert result_before.deterministic_id == result_before_again.deterministic_id
    assert result_before.value is None


def test_metric_after_revision_uses_eligible_revised_record():
    observations = _revision_pair(900_000, 950_000)
    request = _request(observations[0].payload.settlement_date, as_of=AS_OF)
    result = build_short_interest_revision_delta_result(observations, request)
    assert result.value == 50_000


def test_stable_deterministic_id():
    observations = _revision_pair(900_000, 950_000)
    request = _request(observations[0].payload.settlement_date)
    first = build_short_interest_revision_delta_result(observations, request)
    second = build_short_interest_revision_delta_result(list(reversed(observations)), request)
    assert first.deterministic_id == second.deterministic_id


def test_stable_serialization():
    from squeeze_core.metrics import pressure_metric_result_hash

    observations = _revision_pair(900_000, 950_000)
    request = _request(observations[0].payload.settlement_date)
    first = build_short_interest_revision_delta_result(observations, request)
    second = build_short_interest_revision_delta_result(observations, request)
    assert pressure_metric_result_hash(first) == pressure_metric_result_hash(second)

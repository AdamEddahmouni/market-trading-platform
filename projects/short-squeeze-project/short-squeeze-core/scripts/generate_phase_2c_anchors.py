"""Regenerates tests/fixtures/metrics/expected_phase_2c_metric_metadata.json and the Phase 2C
CLI demonstration fixtures (phase_2c_cli_demo_observations.jsonl / phase_2c_metric_cases.json).

Not part of the runtime package. Builds the required Phase 2C anchor results (handoff section
30) directly through squeeze_core.metrics, hashes each with the same canonical_hash used
everywhere else in the repository, and writes the result set plus the raw CLI-output hash to
the metadata file. Mirrors scripts/generate_phase_2b_anchors.py's structure and conventions.

Deterministic: no wall clock, no randomness. Run with the project's .venv:

    .venv/Scripts/python.exe scripts/generate_phase_2c_anchors.py
"""

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from squeeze_core.adapters import AdapterContext  # noqa: E402
from squeeze_core.adapters.finra import normalize_finra_short_interest_records  # noqa: E402
from squeeze_core.adapters.ibkr import normalize_ibkr_borrow_records  # noqa: E402
from squeeze_core.adapters.market_bars import BarInterval, normalize_market_bar_record  # noqa: E402
from squeeze_core.contracts import AssetClass, EntitlementState, EventType, IngestionMethod  # noqa: E402
from squeeze_core.metrics import (  # noqa: E402
    BorrowAvailabilityComparisonRequest,
    BorrowComparisonRequest,
    DaysToCoverRequest,
    MetricName,
    ShortInterestComparisonRequest,
    ShortInterestRevisionRequest,
    TrailingWindow,
    build_borrow_availability_change_result,
    build_borrow_fee_change_result,
    build_days_to_cover_components,
    build_days_to_cover_result,
    build_short_interest_change_result,
    build_short_interest_revision_delta_result,
    days_to_cover_components_hash,
    pressure_metric_result_hash,
    serialize_days_to_cover_components,
    serialize_pressure_metric_result,
)
from squeeze_core.serialization import canonical_hash, serialize_observation  # noqa: E402

AS_OF = datetime(2026, 3, 15, 12, 0, tzinfo=UTC)
OUT_PATH = ROOT / "tests" / "fixtures" / "metrics" / "expected_phase_2c_metric_metadata.json"
CLI_INPUT = ROOT / "tests" / "fixtures" / "metrics" / "phase_2c_cli_demo_observations.jsonl"
CLI_SPEC = ROOT / "tests" / "fixtures" / "metrics" / "phase_2c_metric_cases.json"

SI_PROVIDER = "FINRA-PROVIDER"
BORROW_PROVIDER = "IBKR-PROVIDER"
VOL_PROVIDER = "SIM-VOLUME-PROVIDER"


def _si_context(at: str) -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(at.replace("Z", "+00:00")),
        source_timezone="UTC",
        provider=SI_PROVIDER,
        adapter_version="1.0.0",
        normalization_version="phase-2c-anchor-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="phase-2c-anchor-fixture",
    )


def _borrow_context(at: str) -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(at.replace("Z", "+00:00")),
        source_timezone="UTC",
        provider=BORROW_PROVIDER,
        adapter_version="1.0.0",
        normalization_version="phase-2c-anchor-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="phase-2c-anchor-fixture",
    )


def _bar_context(at: str) -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.fromisoformat(at.replace("Z", "+00:00")),
        source_timezone="UTC",
        provider=VOL_PROVIDER,
        adapter_version="1.0.0",
        normalization_version="phase-2c-anchor-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="phase-2c-anchor-fixture",
    )


def _si_record(**overrides) -> dict:
    values = {
        "source_record_id": "si-anchor-1",
        "provider_schema": "FINRA_SHORT_INTEREST_V1",
        "record_type": "PUBLISHED_SHORT_INTEREST",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "symbol": "TESTC",
        "short_shares": "1000000",
        "settlement_date": "2026-01-15",
        "publication_date": "2026-01-25",
        "publication_timezone": "UTC",
        "date_only_publication_policy": "END_OF_PUBLICATION_DATE",
        "float_shares": "10000000",
        "short_float_percent": "10",
        "short_float_percent_unit": "PERCENT_POINTS",
        "days_to_cover": "2.5",
    }
    values.update(overrides)
    return values


def _si_pair(period, start_shares, end_shares, tag, ingested_at="2026-02-20T00:00:00Z"):
    records = [
        _si_record(
            source_record_id=f"si-{tag}-start", settlement_date=period[0], publication_date=period[0],
            short_shares=str(start_shares),
        ),
        _si_record(
            source_record_id=f"si-{tag}-end", settlement_date=period[1], publication_date=period[1],
            short_shares=str(end_shares),
        ),
    ]
    result = normalize_finra_short_interest_records(records, _si_context(ingested_at))
    assert result.accepted, result.rejection
    return result.observations


def _borrow_record(**overrides) -> dict:
    values = {
        "source_record_id": "ib-anchor-1",
        "symbol": "TESTC",
        "fee_rate": "5.0",
        "fee_rate_unit": "PERCENT_POINTS",
        "available_shares": "100000",
        "lender_count": "10",
        "hard_to_borrow": False,
        "provider_timestamp": "2026-01-10T00:00:00Z",
        "provider_timezone": "UTC",
        "delay_status": "NOT_DELAYED",
    }
    values.update(overrides)
    return values


def _borrow_pair(tag, start_fee, end_fee, start_available, end_available, ingested_at="2026-02-20T00:00:00Z"):
    records = [
        _borrow_record(
            source_record_id=f"ib-{tag}-start", provider_timestamp="2026-01-10T00:00:00Z",
            fee_rate=str(start_fee), available_shares=str(start_available),
        ),
        _borrow_record(
            source_record_id=f"ib-{tag}-end", provider_timestamp="2026-01-20T00:00:00Z",
            fee_rate=str(end_fee), available_shares=str(end_available),
        ),
    ]
    result = normalize_ibkr_borrow_records(records, _borrow_context(ingested_at))
    assert result.accepted, result.rejection
    return result.observations


def _bar_record(day: int, volume: str, **overrides) -> dict:
    values = {
        "source_record_id": f"anchor-bar-{day}",
        "provider_schema": "MARKET_BAR_V1",
        "record_type": "MARKET_BAR",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "provider": VOL_PROVIDER,
        "provider_record_id": None,
        "symbol": "TESTC",
        "asset_class": "EQUITY",
        "exchange": "XNAS",
        "interval": "1_DAY",
        "bar_start": f"2026-02-{day:02d}T00:00:00Z",
        "bar_end": f"2026-02-{day + 1:02d}T00:00:00Z",
        "open": "10.00",
        "high": "1000.00",
        "low": "0.01",
        "close": "10.00",
        "volume": volume,
        "trade_count": "500",
        "vwap": "10.00",
        "volume_unit": "SHARES",
        "session": "REGULAR",
        "session_date": f"2026-02-{day:02d}",
        "timezone": "UTC",
        "status": "COMPLETED",
        "publication_timestamp": f"2026-02-{day:02d}T20:01:00Z",
    }
    values.update(overrides)
    context = _bar_context(f"2026-02-{day:02d}T21:02:00Z")
    result = normalize_market_bar_record(values, context)
    assert result.accepted, result.rejection
    return result.observations[0]


def build_anchor_results() -> dict[str, object]:
    results: dict[str, object] = {}

    # 1-4: short-interest absolute/percentage change
    pos = _si_pair(("2026-01-15", "2026-01-31"), 1_000_000, 1_250_000, "pos")
    request = ShortInterestComparisonRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider=SI_PROVIDER,
        starting_reporting_period=pos[0].payload.settlement_date, ending_reporting_period=pos[1].payload.settlement_date,
    )
    results["positive_short_interest_absolute_change"] = build_short_interest_change_result(
        pos, request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    results["positive_short_interest_percentage_change"] = build_short_interest_change_result(
        pos, request, MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE
    )

    neg = _si_pair(("2026-01-15", "2026-01-31"), 1_250_000, 1_000_000, "neg")
    neg_request = ShortInterestComparisonRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider=SI_PROVIDER,
        starting_reporting_period=neg[0].payload.settlement_date, ending_reporting_period=neg[1].payload.settlement_date,
    )
    results["negative_short_interest_absolute_change"] = build_short_interest_change_result(
        neg, neg_request, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE
    )
    results["negative_short_interest_percentage_change"] = build_short_interest_change_result(
        neg, neg_request, MetricName.PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE
    )

    # 5-6: revision delta
    pos_rev_records = [
        _si_record(source_record_id="si-rev-pos-orig", settlement_date="2026-01-15", publication_date="2026-01-25", short_shares="900000"),
        _si_record(
            source_record_id="si-rev-pos-new", settlement_date="2026-01-15", publication_date="2026-02-05",
            short_shares="950000", revision_status="REVISED", revision_number=1, supersedes_source_record_id="si-rev-pos-orig",
        ),
    ]
    pos_rev = normalize_finra_short_interest_records(pos_rev_records, _si_context("2026-02-20T00:00:00Z"))
    assert pos_rev.accepted, pos_rev.rejection
    rev_request = ShortInterestRevisionRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider=SI_PROVIDER,
        reporting_period=pos_rev.observations[0].payload.settlement_date,
    )
    results["positive_short_interest_revision_delta"] = build_short_interest_revision_delta_result(
        pos_rev.observations, rev_request
    )

    neg_rev_records = [
        _si_record(source_record_id="si-rev-neg-orig", settlement_date="2026-01-15", publication_date="2026-01-25", short_shares="950000"),
        _si_record(
            source_record_id="si-rev-neg-new", settlement_date="2026-01-15", publication_date="2026-02-05",
            short_shares="900000", revision_status="REVISED", revision_number=1, supersedes_source_record_id="si-rev-neg-orig",
        ),
    ]
    neg_rev = normalize_finra_short_interest_records(neg_rev_records, _si_context("2026-02-20T00:00:00Z"))
    assert neg_rev.accepted, neg_rev.rejection
    neg_rev_request = ShortInterestRevisionRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider=SI_PROVIDER,
        reporting_period=neg_rev.observations[0].payload.settlement_date,
    )
    results["negative_short_interest_revision_delta"] = build_short_interest_revision_delta_result(
        neg_rev.observations, neg_rev_request
    )

    # 7-9: days to cover
    dtc_si = _si_pair(("2026-01-15", "2026-01-31"), 1_000_000, 1_250_000, "dtc")
    three_bars = [_bar_record(d, "500000") for d in (10, 11, 12)]
    five_bars = [_bar_record(d, str(v)) for d, v in zip((20, 21, 22, 23, 24), (400000, 500000, 600000, 500000, 500000))]
    three_window = TrailingWindow(requested_count=3, minimum_samples=3)
    five_window = TrailingWindow(requested_count=5, minimum_samples=5)
    three_request = DaysToCoverRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF,
        short_interest_provider=SI_PROVIDER, short_interest_reporting_period=dtc_si[1].payload.settlement_date,
        volume_provider=VOL_PROVIDER, volume_interval=BarInterval.ONE_DAY, volume_window=three_window,
    )
    results["three_sample_days_to_cover"] = build_days_to_cover_result([*dtc_si, *three_bars], three_request)
    results["days_to_cover_components"] = build_days_to_cover_components([*dtc_si, *three_bars], three_request)
    five_request = DaysToCoverRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF,
        short_interest_provider=SI_PROVIDER, short_interest_reporting_period=dtc_si[1].payload.settlement_date,
        volume_provider=VOL_PROVIDER, volume_interval=BarInterval.ONE_DAY, volume_window=five_window,
    )
    results["five_sample_days_to_cover"] = build_days_to_cover_result([*dtc_si, *five_bars], five_request)

    # 10-13: borrow fee changes
    pos_fee = _borrow_pair("fee-pos", 5.0, 8.0, 100_000, 100_000)
    pos_fee_only = [o for o in pos_fee if o.event_type is EventType.BORROW_FEE]
    fee_request = BorrowComparisonRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider=BORROW_PROVIDER,
        starting_effective_timestamp=pos_fee_only[0].effective_timestamp,
        ending_effective_timestamp=pos_fee_only[1].effective_timestamp,
    )
    results["positive_borrow_fee_absolute_change"] = build_borrow_fee_change_result(
        pos_fee_only, fee_request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE
    )
    results["positive_borrow_fee_relative_change"] = build_borrow_fee_change_result(
        pos_fee_only, fee_request, MetricName.BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE
    )

    neg_fee = _borrow_pair("fee-neg", 8.0, 5.0, 100_000, 100_000)
    neg_fee_only = [o for o in neg_fee if o.event_type is EventType.BORROW_FEE]
    neg_fee_request = BorrowComparisonRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider=BORROW_PROVIDER,
        starting_effective_timestamp=neg_fee_only[0].effective_timestamp,
        ending_effective_timestamp=neg_fee_only[1].effective_timestamp,
    )
    results["negative_borrow_fee_absolute_change"] = build_borrow_fee_change_result(
        neg_fee_only, neg_fee_request, MetricName.BORROW_FEE_ABSOLUTE_CHANGE
    )
    results["negative_borrow_fee_relative_change"] = build_borrow_fee_change_result(
        neg_fee_only, neg_fee_request, MetricName.BORROW_FEE_RELATIVE_PERCENTAGE_CHANGE
    )

    # 14-17: borrow availability changes
    pos_avail = _borrow_pair("avail-pos", 5.0, 5.0, 100_000, 150_000)
    pos_avail_only = [o for o in pos_avail if o.event_type is EventType.BORROW_AVAILABILITY]
    avail_request = BorrowAvailabilityComparisonRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider=BORROW_PROVIDER,
        starting_effective_timestamp=pos_avail_only[0].effective_timestamp,
        ending_effective_timestamp=pos_avail_only[1].effective_timestamp,
    )
    results["positive_borrow_availability_absolute_change"] = build_borrow_availability_change_result(
        pos_avail_only, avail_request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE
    )
    results["positive_borrow_availability_percentage_change"] = build_borrow_availability_change_result(
        pos_avail_only, avail_request, MetricName.BORROW_AVAILABILITY_PERCENTAGE_CHANGE
    )

    neg_avail = _borrow_pair("avail-neg", 5.0, 5.0, 150_000, 100_000)
    neg_avail_only = [o for o in neg_avail if o.event_type is EventType.BORROW_AVAILABILITY]
    neg_avail_request = BorrowAvailabilityComparisonRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider=BORROW_PROVIDER,
        starting_effective_timestamp=neg_avail_only[0].effective_timestamp,
        ending_effective_timestamp=neg_avail_only[1].effective_timestamp,
    )
    results["negative_borrow_availability_absolute_change"] = build_borrow_availability_change_result(
        neg_avail_only, neg_avail_request, MetricName.BORROW_AVAILABILITY_ABSOLUTE_CHANGE
    )
    results["negative_borrow_availability_percentage_change"] = build_borrow_availability_change_result(
        neg_avail_only, neg_avail_request, MetricName.BORROW_AVAILABILITY_PERCENTAGE_CHANGE
    )

    # 18-21: before/after revision and cancellation
    rev_records = [
        _si_record(source_record_id="si-lifecycle-orig", settlement_date="2026-01-15", publication_date="2026-01-25", short_shares="900000"),
        _si_record(
            source_record_id="si-lifecycle-rev", settlement_date="2026-01-15", publication_date="2026-02-05",
            short_shares="950000", revision_status="REVISED", revision_number=1, supersedes_source_record_id="si-lifecycle-orig",
        ),
    ]
    rev_lifecycle = normalize_finra_short_interest_records(rev_records, _si_context("2026-02-20T00:00:00Z"))
    assert rev_lifecycle.accepted, rev_lifecycle.rejection
    lifecycle_period = rev_lifecycle.observations[0].payload.settlement_date
    before_rev_as_of = datetime(2026, 1, 26, tzinfo=UTC)
    results["before_short_interest_revision_result"] = build_short_interest_revision_delta_result(
        rev_lifecycle.observations,
        ShortInterestRevisionRequest(
            symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=before_rev_as_of, provider=SI_PROVIDER,
            reporting_period=lifecycle_period,
        ),
    )
    results["after_short_interest_revision_result"] = build_short_interest_revision_delta_result(
        rev_lifecycle.observations,
        ShortInterestRevisionRequest(
            symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider=SI_PROVIDER,
            reporting_period=lifecycle_period,
        ),
    )

    cancel_records = [
        _si_record(source_record_id="si-cancel-orig", settlement_date="2026-01-15", publication_date="2026-01-25", short_shares="900000"),
        _si_record(
            source_record_id="si-cancel-new", settlement_date="2026-01-15", publication_date="2026-02-05",
            short_shares="900000", revision_status="CANCELLED", revision_number=1, supersedes_source_record_id="si-cancel-orig",
        ),
    ]
    cancel_lifecycle = normalize_finra_short_interest_records(cancel_records, _si_context("2026-02-20T00:00:00Z"))
    assert cancel_lifecycle.accepted, cancel_lifecycle.rejection
    cancel_period = cancel_lifecycle.observations[0].payload.settlement_date
    before_cancel_as_of = datetime(2026, 1, 26, tzinfo=UTC)
    other_period_si = _si_record(
        source_record_id="si-cancel-other", settlement_date="2025-12-15", publication_date="2025-12-25", short_shares="800000",
    )
    other_period_result = normalize_finra_short_interest_records([other_period_si], _si_context("2026-02-20T00:00:00Z"))
    assert other_period_result.accepted, other_period_result.rejection
    cancel_change_request_before = ShortInterestComparisonRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=before_cancel_as_of, provider=SI_PROVIDER,
        starting_reporting_period=other_period_result.observations[0].payload.settlement_date,
        ending_reporting_period=cancel_period,
    )
    results["before_short_interest_cancellation_result"] = build_short_interest_change_result(
        [*cancel_lifecycle.observations, *other_period_result.observations],
        cancel_change_request_before, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE,
    )
    cancel_change_request_after = ShortInterestComparisonRequest(
        symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=AS_OF, provider=SI_PROVIDER,
        starting_reporting_period=other_period_result.observations[0].payload.settlement_date,
        ending_reporting_period=cancel_period,
    )
    results["after_short_interest_cancellation_result"] = build_short_interest_change_result(
        [*cancel_lifecycle.observations, *other_period_result.observations],
        cancel_change_request_after, MetricName.PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE,
    )

    # 22-23: before/after borrow update (no revision concept -- ordinary point-in-time exclusion)
    borrow_update = _borrow_pair("update", 5.0, 8.0, 100_000, 100_000, ingested_at="2026-01-21T00:00:00Z")
    borrow_update_fee = [o for o in borrow_update if o.event_type is EventType.BORROW_FEE]
    before_update_as_of = borrow_update_fee[0].effective_timestamp
    after_update_as_of = AS_OF
    results["before_borrow_update_result"] = build_borrow_fee_change_result(
        borrow_update_fee,
        BorrowComparisonRequest(
            symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=before_update_as_of, provider=BORROW_PROVIDER,
            starting_effective_timestamp=borrow_update_fee[0].effective_timestamp,
            ending_effective_timestamp=borrow_update_fee[1].effective_timestamp,
        ),
        MetricName.BORROW_FEE_ABSOLUTE_CHANGE,
    )
    results["after_borrow_update_result"] = build_borrow_fee_change_result(
        borrow_update_fee,
        BorrowComparisonRequest(
            symbol="TESTC", asset_class=AssetClass.EQUITY, as_of=after_update_as_of, provider=BORROW_PROVIDER,
            starting_effective_timestamp=borrow_update_fee[0].effective_timestamp,
            ending_effective_timestamp=borrow_update_fee[1].effective_timestamp,
        ),
        MetricName.BORROW_FEE_ABSOLUTE_CHANGE,
    )

    return results


def _cli_fixture_observations() -> list:
    si = _si_pair(("2026-01-15", "2026-01-31"), 1_000_000, 1_250_000, "cli")
    fee = _borrow_pair("cli-fee", 5.0, 8.0, 100_000, 150_000)
    bars = [_bar_record(d, "500000") for d in (10, 11, 12)]
    return [*si, *fee, *bars]


def _cli_spec(si_obs, fee_obs) -> dict:
    fee_only = [o for o in fee_obs if o.event_type is EventType.BORROW_FEE]
    availability_only = [o for o in fee_obs if o.event_type is EventType.BORROW_AVAILABILITY]
    return {
        "schema_version": "1.0.0",
        "description": "Phase 2C CLI demonstration cases for tests/fixtures/metrics/phase_2c_cli_demo_observations.jsonl. Fixture provenance: SYNTHETIC_EDGE_CASE.",
        "cases": [
            {
                "metric_name": "PUBLISHED_SHORT_INTEREST_ABSOLUTE_CHANGE",
                "symbol": "TESTC",
                "provider": SI_PROVIDER,
                "starting_reporting_period": str(si_obs[0].payload.settlement_date),
                "ending_reporting_period": str(si_obs[1].payload.settlement_date),
            },
            {
                "metric_name": "PUBLISHED_SHORT_INTEREST_PERCENTAGE_CHANGE",
                "symbol": "TESTC",
                "provider": SI_PROVIDER,
                "starting_reporting_period": str(si_obs[0].payload.settlement_date),
                "ending_reporting_period": str(si_obs[1].payload.settlement_date),
            },
            {
                "metric_name": "DAYS_TO_COVER",
                "symbol": "TESTC",
                "short_interest_provider": SI_PROVIDER,
                "short_interest_reporting_period": str(si_obs[1].payload.settlement_date),
                "volume_provider": VOL_PROVIDER,
                "volume_interval": "1_DAY",
                "volume_window": {"requested_count": 3, "minimum_samples": 3},
            },
            {
                "metric_name": "BORROW_FEE_ABSOLUTE_CHANGE",
                "symbol": "TESTC",
                "provider": BORROW_PROVIDER,
                "starting_effective_timestamp": fee_only[0].effective_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ending_effective_timestamp": fee_only[1].effective_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            {
                "metric_name": "BORROW_AVAILABILITY_ABSOLUTE_CHANGE",
                "symbol": "TESTC",
                "provider": BORROW_PROVIDER,
                "starting_effective_timestamp": availability_only[0].effective_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ending_effective_timestamp": availability_only[1].effective_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        ],
    }


def main() -> None:
    results = build_anchor_results()
    anchors: dict[str, str] = {}
    for name, result in results.items():
        if name == "days_to_cover_components":
            anchors[name] = days_to_cover_components_hash(result)
        else:
            anchors[name] = pressure_metric_result_hash(result)

    ordered_names = sorted(results)
    collection = [results[name] for name in ordered_names]
    anchors["mixed_phase_2c_metric_output"] = canonical_hash(list(collection))

    def _serialize(item):
        return serialize_days_to_cover_components(item) if isinstance(item, type(results["days_to_cover_components"])) else serialize_pressure_metric_result(item)

    anchors["serialized_phase_2c_metric_collection"] = hashlib.sha256(
        b"[" + b",".join(_serialize(item) for item in collection) + b"]"
    ).hexdigest()

    observations = _cli_fixture_observations()
    with CLI_INPUT.open("w", encoding="utf-8", newline="\n") as handle:
        for observation in observations:
            handle.write(serialize_observation(observation).decode("utf-8"))
            handle.write("\n")

    si_obs = [o for o in observations if o.event_type.value == "PUBLISHED_SHORT_INTEREST"]
    fee_obs = [o for o in observations if o.event_type.value in ("BORROW_FEE", "BORROW_AVAILABILITY")]
    spec = _cli_spec(si_obs, fee_obs)
    CLI_SPEC.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")

    cli = subprocess.run(
        [
            sys.executable, "-m", "squeeze_core", "build-market-metrics",
            "--input", str(CLI_INPUT), "--symbol", "TESTC", "--as-of", "2026-03-15T12:00:00Z",
            "--spec", str(CLI_SPEC),
        ],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    anchors["phase_2c_cli_output"] = hashlib.sha256(cli.stdout.encode("utf-8")).hexdigest()

    metadata = {
        "schema_version": "1.0.0",
        "description": "Phase 2C anchor hashes (handoff section 30). Each PressureMetricResult value is pressure_metric_result_hash(); days_to_cover_components is days_to_cover_components_hash(); mixed_phase_2c_metric_output is canonical_hash() of the sorted-by-name result list; serialized_phase_2c_metric_collection is sha256 of the concatenated per-result canonical JSON bytes; phase_2c_cli_output is sha256 of build-market-metrics stdout for phase_2c_cli_demo_observations.jsonl + phase_2c_metric_cases.json at as_of=2026-03-15T12:00:00Z. This is a Phase 2C-only anchor manifest, separate from tests/fixtures/compatibility/phase_1_anchor_manifest.json and the Phase 2A/2B metadata files; none of those files is written by this script.",
        "anchor_result_order": ordered_names,
        "anchors": dict(sorted(anchors.items())),
    }
    OUT_PATH.write_text(json.dumps(metadata, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")
    print(f"wrote {CLI_INPUT}")
    print(f"wrote {CLI_SPEC}")


if __name__ == "__main__":
    main()

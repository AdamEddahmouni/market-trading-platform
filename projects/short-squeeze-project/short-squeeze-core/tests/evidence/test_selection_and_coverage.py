from datetime import UTC, datetime, timedelta

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.finviz import normalize_finviz_snapshot_record
from squeeze_core.adapters.ibkr import normalize_ibkr_borrow_record
from squeeze_core.contracts import EntitlementState, EventType, IngestionMethod, Observation
from squeeze_core.evidence import (
    CoverageDomain,
    CoverageState,
    EvidenceDiagnosticCode,
    PointInTimeEvidencePolicy,
    build_point_in_time_evidence,
)
from squeeze_core.serialization import canonical_hash, serialize_observation


AS_OF = datetime(2026, 1, 15, 15, 30, tzinfo=UTC)


def context(provider: str = "FINVIZ_REPRESENTATIVE") -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime(2026, 1, 15, 15, 5, tzinfo=UTC),
        source_timezone="America/New_York",
        provider=provider,
        adapter_version="offline-v1",
        normalization_version="normalization-v1",
        entitlement_status=EntitlementState.UNKNOWN,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="representative-shape",
    )


def finviz_record(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "finviz-evidence-001",
        "provider_schema": "FINVIZ_SCREENER_V1",
        "record_type": "CANDIDATE_SNAPSHOT",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "Ticker": "TESTA",
        "Price": "5.25",
        "Prev Close": "4.75",
        "Change": "10.5%",
        "change_percent_unit": "FORMATTED_PERCENT_STRING",
        "Volume": "125000",
        "Avg Volume": "25000",
        "Relative Volume": "5.0",
        "Shares Float": "8000000",
        "Short Float": "12.5%",
        "short_float_percent_unit": "FORMATTED_PERCENT_STRING",
        "provider_timestamp": "2026-01-15T10:00:00-05:00",
        "capture_timestamp": "2026-01-15T10:01:00-05:00",
        "delay_status": "UNKNOWN",
    }
    value.update(overrides)
    return value


def ibkr_record() -> dict[str, object]:
    return {
        "source_record_id": "ibkr-evidence-001",
        "symbol": "TESTA",
        "fee_rate": "3.25",
        "fee_rate_unit": "PERCENT_POINTS",
        "available_shares": "12000",
        "provider_timestamp": "2026-01-15T10:02:00-05:00",
        "provider_timezone": "-05:00",
        "delay_status": "NOT_DELAYED",
    }


def observations() -> tuple[Observation, ...]:
    snapshot = normalize_finviz_snapshot_record(finviz_record(), context()).observations
    borrow = normalize_ibkr_borrow_record(
        ibkr_record(), context("INTERACTIVE_BROKERS")
    ).observations
    return snapshot + borrow


def policy(**overrides: object) -> PointInTimeEvidencePolicy:
    values: dict[str, object] = {
        "as_of": AS_OF,
        "maximum_future_skew_ms": 0,
        "maximum_age_ms_by_event_type": {
            EventType.MARKET_SNAPSHOT: 3_600_000,
            EventType.BORROW_FEE: 3_600_000,
            EventType.BORROW_AVAILABILITY: 3_600_000,
        },
        "allow_stale": True,
        "allow_delayed": True,
        "allow_unknown_freshness": True,
        "conflict_tolerance": {},
        "source_priority_metadata": {"finviz-screener-snapshot": 1},
    }
    values.update(overrides)
    return PointInTimeEvidencePolicy.model_validate(values)


def rebuild(observation: Observation, **updates: object) -> Observation:
    values = observation.model_dump(mode="python")
    values.update(updates)
    values["observation_id"] = None
    return Observation.model_validate(values)


def coverage(bundle) -> dict[CoverageDomain, CoverageState]:
    return {item.domain: item.state for item in bundle.source_coverage}


def diagnostic_codes(bundle) -> set[EvidenceDiagnosticCode]:
    return {item.code for item in bundle.diagnostics}


def test_bundle_contains_each_phase_1c_domain_without_changing_observations() -> None:
    source = observations()
    before = tuple(serialize_observation(item) for item in source)
    bundle = build_point_in_time_evidence("TESTA", source, policy())

    assert tuple(serialize_observation(item) for item in bundle.observations) == before
    assert coverage(bundle) == {
        CoverageDomain.CANDIDATE_SNAPSHOT: CoverageState.UNKNOWN_FRESHNESS,
        CoverageDomain.BORROW_FEE: CoverageState.UNKNOWN_FRESHNESS,
        CoverageDomain.BORROW_AVAILABILITY: CoverageState.UNKNOWN_FRESHNESS,
    }
    assert bundle.completeness_summary.included_observation_count == 3
    assert bundle.completeness_summary.excluded_observation_count == 0
    assert bundle.bundle_hash == canonical_hash(bundle.hash_content())
    assert bundle.bundle_id.startswith("evidence-")


def test_bundle_membership_order_and_hash_are_stable_for_shuffled_input() -> None:
    source = observations()
    first = build_point_in_time_evidence("TESTA", source, policy())
    second = build_point_in_time_evidence("TESTA", tuple(reversed(source)), policy())

    assert first == second
    assert [item.event_type for item in first.observations] == [
        EventType.MARKET_SNAPSHOT,
        EventType.BORROW_FEE,
        EventType.BORROW_AVAILABILITY,
    ]


def test_future_effective_observation_is_excluded_unless_within_explicit_skew() -> None:
    snapshot = observations()[0]
    future = rebuild(
        snapshot,
        source_timestamp=AS_OF + timedelta(seconds=1),
        effective_timestamp=AS_OF + timedelta(seconds=1),
    )
    excluded = build_point_in_time_evidence("TESTA", [future], policy())
    included = build_point_in_time_evidence(
        "TESTA", [future], policy(maximum_future_skew_ms=1_000)
    )

    assert excluded.observations == ()
    assert EvidenceDiagnosticCode.EVIDENCE_EXCLUDED_AFTER_AS_OF in diagnostic_codes(excluded)
    assert included.observations == (future,)


def test_received_after_as_of_is_excluded_even_when_effective_skew_is_allowed() -> None:
    snapshot = observations()[0]
    late = rebuild(snapshot, received_timestamp=AS_OF + timedelta(microseconds=1))
    bundle = build_point_in_time_evidence(
        "TESTA", [late], policy(maximum_future_skew_ms=60_000)
    )

    assert bundle.observations == ()
    assert EvidenceDiagnosticCode.EVIDENCE_EXCLUDED_RECEIVED_AFTER_AS_OF in diagnostic_codes(
        bundle
    )


def test_symbol_mismatch_is_excluded_and_diagnosed() -> None:
    other = rebuild(observations()[0], symbol="TESTB")
    bundle = build_point_in_time_evidence("TESTA", [other], policy())

    assert bundle.observations == ()
    assert EvidenceDiagnosticCode.EVIDENCE_SYMBOL_MISMATCH in diagnostic_codes(bundle)


def test_stale_delayed_and_unknown_freshness_are_policy_controlled() -> None:
    snapshot, fee, availability = observations()
    stale_policy = policy(
        maximum_age_ms_by_event_type={
            EventType.MARKET_SNAPSHOT: 1_000,
            EventType.BORROW_FEE: 3_600_000,
            EventType.BORROW_AVAILABILITY: 3_600_000,
        }
    )
    retained = build_point_in_time_evidence("TESTA", [snapshot], stale_policy)
    rejected_stale = build_point_in_time_evidence(
        "TESTA", [snapshot], stale_policy.model_copy(update={"allow_stale": False})
    )
    rejected_unknown = build_point_in_time_evidence(
        "TESTA", [fee], policy(allow_unknown_freshness=False)
    )
    delayed = rebuild(
        availability,
        data_freshness="DELAYED",
        quality={
            "state": "DELAYED",
            "reasons": ["synthetic delayed case"],
            "evaluated_at": availability.quality.evaluated_at,
        },
    )
    rejected_delayed = build_point_in_time_evidence(
        "TESTA", [delayed], policy(allow_delayed=False)
    )

    assert retained.observations == (snapshot,)
    assert coverage(retained)[CoverageDomain.CANDIDATE_SNAPSHOT] is CoverageState.STALE
    assert rejected_stale.observations == ()
    assert rejected_unknown.observations == ()
    assert rejected_delayed.observations == ()


def test_missing_domains_are_explicit_and_never_zero_evidence() -> None:
    bundle = build_point_in_time_evidence("TESTA", observations()[:1], policy())

    assert coverage(bundle)[CoverageDomain.CANDIDATE_SNAPSHOT] is CoverageState.UNKNOWN_FRESHNESS
    assert coverage(bundle)[CoverageDomain.BORROW_FEE] is CoverageState.MISSING
    assert coverage(bundle)[CoverageDomain.BORROW_AVAILABILITY] is CoverageState.MISSING
    assert EvidenceDiagnosticCode.EVIDENCE_MISSING_SOURCE_DOMAIN in diagnostic_codes(bundle)
    assert EvidenceDiagnosticCode.EVIDENCE_PARTIAL_COVERAGE in diagnostic_codes(bundle)

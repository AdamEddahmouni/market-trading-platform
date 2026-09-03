from datetime import datetime

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.halts import normalize_trading_halt_record
from squeeze_core.contracts import EntitlementState, IngestionMethod
from squeeze_core.evidence import (
    CoverageDomain,
    CoverageState,
    EvidenceDiagnosticCode,
    HaltState,
    PointInTimeEvidencePolicy,
    build_point_in_time_evidence,
)
from squeeze_core.serialization import canonical_json_bytes


def raw(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "source_record_id": "halt-announce",
        "provider_schema": "TRADING_HALT_V1",
        "record_type": "TRADING_HALT",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "symbol": "TESTA",
        "exchange": "XTEST",
        "provider_halt_id": "testa-halt-20260115-1",
        "halt_code": "T1",
        "reason_text": "News pending",
        "announcement_at": "2026-01-15T15:01:00Z",
        "halt_at": "2026-01-15T15:00:00Z",
        "publication_at": "2026-01-15T15:01:00Z",
        "session_date": "2026-01-15",
        "timezone": "UTC",
        "status": "HALT_ACTIVE",
    }
    value.update(overrides)
    return value


def observation(value: dict[str, object], received: str):
    context = AdapterContext(
        ingested_at=datetime.fromisoformat(received.replace("Z", "+00:00")),
        source_timezone="UTC",
        provider="exchange-shaped-offline-fixture",
        adapter_version="1.0.0",
        normalization_version="trading-halts-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
    )
    return normalize_trading_halt_record(value, context).observations[0]


def policy(as_of: str) -> PointInTimeEvidencePolicy:
    return PointInTimeEvidencePolicy(
        as_of=datetime.fromisoformat(as_of.replace("Z", "+00:00")),
        include_trading_halts_domain=True,
    )


def coverage(bundle):
    return next(
        item for item in bundle.source_coverage if item.domain is CoverageDomain.TRADING_HALTS
    )


def codes(bundle) -> set[EvidenceDiagnosticCode]:
    return {item.code for item in bundle.diagnostics}


def lifecycle():
    return [
        observation(raw(), "2026-01-15T15:01:00Z"),
        observation(
            raw(
                source_record_id="quote-scheduled",
                status="QUOTE_RESUMPTION_SCHEDULED",
                quote_resumption_scheduled_at="2026-01-15T15:25:00Z",
                publication_at="2026-01-15T15:20:00Z",
                announcement_at="2026-01-15T15:20:00Z",
            ),
            "2026-01-15T15:20:00Z",
        ),
        observation(
            raw(
                source_record_id="quotes-resumed",
                status="QUOTE_RESUMED",
                quote_resumed_at="2026-01-15T15:30:00Z",
                publication_at="2026-01-15T15:30:00Z",
                announcement_at="2026-01-15T15:30:00Z",
            ),
            "2026-01-15T15:30:00Z",
        ),
        observation(
            raw(
                source_record_id="trade-scheduled",
                status="TRADE_RESUMPTION_SCHEDULED",
                trade_resumption_scheduled_at="2026-01-15T15:40:00Z",
                publication_at="2026-01-15T15:35:00Z",
                announcement_at="2026-01-15T15:35:00Z",
            ),
            "2026-01-15T15:35:00Z",
        ),
        observation(
            raw(
                source_record_id="trading-resumed",
                status="TRADING_RESUMED",
                trading_resumed_at="2026-01-15T15:40:00Z",
                publication_at="2026-01-15T15:40:00Z",
                announcement_at="2026-01-15T15:40:00Z",
            ),
            "2026-01-15T15:40:00Z",
        ),
    ]


def test_halt_effective_before_publication_is_not_eligible() -> None:
    halt = observation(raw(publication_at="2026-01-15T15:05:00Z"), "2026-01-15T15:05:00Z")
    bundle = build_point_in_time_evidence(
        "TESTA", [halt], policy("2026-01-15T15:02:00Z")
    )
    assert bundle.observations == ()
    assert coverage(bundle).state is CoverageState.MISSING
    assert bundle.halt_state.state is HaltState.NOT_OBSERVED
    assert EvidenceDiagnosticCode.EVIDENCE_HALT_NOT_YET_PUBLISHED in codes(bundle)


def test_published_before_receipt_is_not_eligible() -> None:
    halt = observation(raw(), "2026-01-15T15:05:00Z")
    bundle = build_point_in_time_evidence(
        "TESTA", [halt], policy("2026-01-15T15:02:00Z")
    )
    assert bundle.observations == ()
    assert EvidenceDiagnosticCode.EVIDENCE_HALT_NOT_YET_RECEIVED in codes(bundle)


def test_lifecycle_state_uses_only_eligible_explicit_updates() -> None:
    observations = lifecycle()
    expected = {
        "2026-01-15T15:10:00Z": HaltState.HALTED,
        "2026-01-15T15:22:00Z": HaltState.QUOTE_RESUMPTION_SCHEDULED,
        "2026-01-15T15:32:00Z": HaltState.QUOTES_RESUMED,
        "2026-01-15T15:37:00Z": HaltState.TRADE_RESUMPTION_SCHEDULED,
        "2026-01-15T15:41:00Z": HaltState.TRADING_RESUMED,
    }
    for as_of, state in expected.items():
        bundle = build_point_in_time_evidence("TESTA", observations, policy(as_of))
        assert bundle.halt_state.state is state
        assert bundle.halt_state.supporting_observation_ids
        assert coverage(bundle).state is CoverageState.PRESENT


def test_scheduled_resumption_never_becomes_actual_without_later_observation() -> None:
    observations = lifecycle()[:2]
    bundle = build_point_in_time_evidence(
        "TESTA", observations, policy("2026-01-15T16:00:00Z")
    )
    assert bundle.halt_state.state is HaltState.QUOTE_RESUMPTION_SCHEDULED
    assert EvidenceDiagnosticCode.EVIDENCE_QUOTE_RESUMPTION_SCHEDULED in codes(bundle)


def test_halt_ages_are_distinct_and_conditional() -> None:
    halt = lifecycle()[0]
    bundle = build_point_in_time_evidence(
        "TESTA", [halt], policy("2026-01-15T15:11:00Z")
    )
    age = bundle.observation_ages[0]
    assert age.announcement_age_ms == 600_000
    assert age.availability_age_ms == 600_000
    assert age.halt_event_age_ms == 660_000
    assert age.resumption_event_age_ms is None


def test_later_updates_do_not_change_earlier_historical_bundle() -> None:
    observations = lifecycle()
    before = build_point_in_time_evidence(
        "TESTA", observations, policy("2026-01-15T15:22:00Z")
    )
    rebuilt = build_point_in_time_evidence(
        "TESTA", list(reversed(observations)), policy("2026-01-15T15:22:00Z")
    )
    after = build_point_in_time_evidence(
        "TESTA", observations, policy("2026-01-15T15:41:00Z")
    )
    assert before.bundle_hash == rebuilt.bundle_hash
    assert canonical_json_bytes(before) == canonical_json_bytes(rebuilt)
    assert before.halt_state.state is HaltState.QUOTE_RESUMPTION_SCHEDULED
    assert after.halt_state.state is HaltState.TRADING_RESUMED


def test_policy_can_require_missing_halt_domain_without_input() -> None:
    bundle = build_point_in_time_evidence(
        "TESTA", [], policy("2026-01-15T15:41:00Z")
    )
    assert coverage(bundle).state is CoverageState.MISSING
    assert bundle.halt_state.state is HaltState.NOT_OBSERVED
    assert EvidenceDiagnosticCode.EVIDENCE_MISSING_TRADING_HALTS in codes(bundle)

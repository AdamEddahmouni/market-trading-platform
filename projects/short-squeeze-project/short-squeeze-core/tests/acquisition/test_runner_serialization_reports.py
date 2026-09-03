from datetime import UTC, datetime

from squeeze_core.acquisition.models import (
    ArtifactManifest,
    ArtifactClassification,
    DiscoveryRecord,
    DiscoverySourceClass,
    SourceManifest,
)
from squeeze_core.acquisition.reports import render_acquisition_report
from squeeze_core.acquisition.runner import curate_historical_cases
from squeeze_core.acquisition.serialization import (
    deserialize_acquisition_batch,
    serialize_acquisition_model,
)
from tests.acquisition.helpers import sample_plan


def _discovery(record_id: str, symbol: str, order: int) -> DiscoveryRecord:
    return DiscoveryRecord(
        discovery_record_id=record_id, symbol_as_observed=symbol,
        observed_at=datetime(2024, 5, 14, 12, order, tzinfo=UTC),
        source_class=DiscoverySourceClass.PUBLIC_MARKET_EVENT_FEED,
        source_name="pilot-feed", source_artifact_id=f"artifact-{record_id}",
        provider="PUBLIC", provider_scope="US_EQUITY",
        query_or_filter_definition="fixed-filter-v1", original_order=order,
        platform_surfaced_status="UNKNOWN", discovery_reason="source-defined event",
        fixture_classification=ArtifactClassification.SANITIZED_HISTORICAL_FIXTURE,
    )


def test_runner_is_input_order_invariant_and_retains_duplicate_attempt():
    records = (_discovery("d2", "BIYA", 2), _discovery("d1", "BIYA", 1))
    source_a = SourceManifest(manifest_id="source-1", discovery_records=records,
                              provider_provenance=())
    source_b = SourceManifest(manifest_id="source-1", discovery_records=tuple(reversed(records)),
                              provider_provenance=())
    artifacts = ArtifactManifest(manifest_id="artifacts-1", artifacts=())
    first = curate_historical_cases(sample_plan(), source_a, artifacts)
    second = curate_historical_cases(sample_plan(), source_b, artifacts)
    assert serialize_acquisition_model(first) == serialize_acquisition_model(second)
    assert len(first.ledger.attempts) == 2
    assert sum(item.curation_status.value == "EXCLUDED" for item in first.bundles) == 1


def test_serialization_round_trips_and_contains_no_prohibited_result_fields():
    batch = curate_historical_cases(
        sample_plan(),
        SourceManifest(manifest_id="source-1", discovery_records=(_discovery("d1", "BIYA", 1),),
                       provider_provenance=()),
        ArtifactManifest(manifest_id="artifacts-1", artifacts=()),
    )
    rendered = serialize_acquisition_model(batch)
    assert serialize_acquisition_model(deserialize_acquisition_batch(rendered)) == rendered
    lowered = rendered.decode("utf-8").lower()
    for key in ('"score"', '"rank"', '"recommendation"', '"pnl"', '"optimization"'):
        assert key not in lowered


def test_report_contains_every_required_interpretation_statement():
    batch = curate_historical_cases(
        sample_plan(),
        SourceManifest(manifest_id="source-1", discovery_records=(_discovery("d1", "BIYA", 1),),
                       provider_provenance=()),
        ArtifactManifest(manifest_id="artifacts-1", artifacts=()),
    )
    report = render_acquisition_report(batch).decode("utf-8")
    required = (
        "builds controlled historical acquisition infrastructure",
        "not proof of predictive validity",
        "preregistered criteria, not later outcome",
        "frozen before retrospective outcome capture",
        "retained as missing",
        "not silently treated as historical evidence",
        "Excluded and blocked attempts remain visible",
        "dependent observations",
        "Synthetic fixtures test software behavior only",
        "No Phase 3A threshold was changed",
        "No Phase 3B policy was optimized",
        "No scoring, ranking, recommendation, alert, backtest, P&L, or trading simulation",
    )
    assert all(statement in report for statement in required)

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from squeeze_core.acquisition.models import (
    AcquisitionPlan,
    AcquisitionPlanStatus,
    ArtifactClassification,
    ArtifactRecord,
    DiscoveryRecord,
    DiscoverySourceClass,
    HistoricalOrCurrent,
    ProviderProvenance,
)


def _plan(**changes):
    values = {
        "acquisition_plan_id": "pilot-2024",
        "plan_version": "phase_3d_pilot.v1",
        "created_from_policy_version": "phase_3d_acquisition_plan_policy.v1",
        "research_question": "Can independently discovered cases be reconstructed point in time?",
        "target_population": "US listed common stocks surfaced by the declared feed",
        "date_range": (date(2024, 1, 1), date(2024, 12, 31)),
        "market_session_scope": ("PRE", "REGULAR", "POST"),
        "symbol_universe_definition": "Explicit source-manifest symbols",
        "discovery_source_definitions": ("PUBLIC_MARKET_EVENT_FEED:pilot",),
        "maximum_case_count": 20,
        "minimum_case_count": 0,
        "sampling_method": "SOURCE_ORDER_THEN_IDENTITY_DEDUPLICATION",
        "deduplication_policy": "phase_3d_unique_security_deduplication_policy.v1",
        "boundary_policy": "phase_3d_detection_boundary_policy.v1",
        "inclusion_policy_version": "phase_3d_historical_inclusion_policy.v1",
        "exclusion_policy_version": "phase_3d_historical_exclusion_policy.v1",
        "provider_priority_policy_version": "phase_3d_provider_priority_policy.v1",
        "artifact_requirements": ("DISCOVERY", "MARKET"),
        "allowed_substitutions": (),
        "forbidden_substitutions": ("CURRENT_FOR_HISTORICAL",),
        "outcome_blinding_state": "OUTCOME_BLINDED",
        "plan_status": AcquisitionPlanStatus.PREREGISTERED,
        "informational_created_at": datetime(2026, 7, 22, tzinfo=UTC),
    }
    values.update(changes)
    return AcquisitionPlan(**values)


def test_models_are_frozen_and_reject_extra_fields():
    plan = _plan()
    with pytest.raises(ValidationError):
        plan.plan_status = AcquisitionPlanStatus.ACTIVE
    with pytest.raises(ValidationError):
        _plan(unknown_field="forbidden")


def test_plan_identity_excludes_informational_creation_time():
    first = _plan(informational_created_at=datetime(2026, 7, 22, tzinfo=UTC))
    second = _plan(informational_created_at=datetime(2030, 1, 1, tzinfo=UTC))
    assert first.deterministic_id == second.deterministic_id


def test_plan_semantic_change_alters_identity_and_canonicalizes_sets():
    first = _plan(artifact_requirements=("MARKET", "DISCOVERY"))
    second = _plan(artifact_requirements=("DISCOVERY", "MARKET"))
    changed = _plan(maximum_case_count=21)
    assert first.artifact_requirements == ("DISCOVERY", "MARKET")
    assert first.deterministic_id == second.deterministic_id
    assert first.deterministic_id != changed.deterministic_id


def test_discovery_preserves_manual_and_platform_status_without_inference():
    record = DiscoveryRecord(
        discovery_record_id="lead-1",
        symbol_as_observed="biya",
        observed_at=datetime(2024, 5, 14, 12, 0, tzinfo=UTC),
        source_class=DiscoverySourceClass.MANUAL_RESEARCH_LEAD,
        source_name="review-log",
        source_artifact_id="artifact-1",
        provider="PUBLIC",
        provider_scope="NEWS",
        query_or_filter_definition="explicit lead",
        original_order=1,
        platform_surfaced_status="UNKNOWN",
        discovery_reason="lead recorded for review",
        fixture_classification=ArtifactClassification.SANITIZED_HISTORICAL_FIXTURE,
    )
    assert record.symbol_as_observed == "BIYA"
    assert record.platform_surfaced_status == "UNKNOWN"


def test_provider_time_dimensions_and_historical_state_remain_distinct():
    provenance = ProviderProvenance(
        provider_provenance_id="prov-1",
        provider_name="Example",
        provider_product="Feed",
        provider_dataset="Events",
        provider_scope="US_EQUITY",
        access_method="LOCAL_EXPORT",
        artifact_timestamp=datetime(2024, 5, 14, 12, 5, tzinfo=UTC),
        event_at=datetime(2024, 5, 14, 12, 0, tzinfo=UTC),
        observed_at=datetime(2024, 5, 14, 12, 1, tzinfo=UTC),
        effective_at=datetime(2024, 5, 14, 12, 2, tzinfo=UTC),
        published_at=datetime(2024, 5, 14, 12, 3, tzinfo=UTC),
        received_at=datetime(2024, 5, 14, 12, 4, tzinfo=UTC),
        timezone="UTC",
        latency_status="KNOWN",
        historical_or_current=HistoricalOrCurrent.HISTORICAL,
        revision_status="ORIGINAL",
        terms_or_license_reference="public terms",
        source_artifact_id="artifact-1",
    )
    assert len({provenance.event_at, provenance.observed_at, provenance.effective_at,
                provenance.published_at, provenance.received_at,
                provenance.artifact_timestamp}) == 6


def test_artifact_record_rejects_absolute_paths():
    values = {
        "artifact_id": "artifact-1",
        "file_name": "source.json",
        "relative_path": "raw/source.json",
        "media_type": "application/json",
        "byte_length": 2,
        "sha256": "a" * 64,
        "source_class": DiscoverySourceClass.ARCHIVED_PROVIDER_RESPONSE,
        "provider_provenance_id": "prov-1",
        "fixture_classification": ArtifactClassification.LOCAL_HISTORICAL_ARTIFACT,
        "capture_method": "LOCAL_EXPORT",
        "observed_at": datetime(2024, 5, 14, tzinfo=UTC),
        "effective_at": datetime(2024, 5, 14, tzinfo=UTC),
        "published_at": datetime(2024, 5, 14, tzinfo=UTC),
        "content_status": "CAPTURED",
        "sensitive_content_status": "NONE",
    }
    assert ArtifactRecord(**values).relative_path == "raw/source.json"
    with pytest.raises(ValidationError):
        ArtifactRecord(**{**values, "relative_path": "C:/private/source.json"})

from pathlib import Path

import pytest

from squeeze_core.acquisition.migration import migrate_phase3b_registry
from squeeze_core.acquisition.models import CurationStatus
from squeeze_core.acquisition.publication import (
    build_phase3b_dataset_candidate,
    build_phase3b_registry_candidate,
)
from squeeze_core.research.serialization import (
    deserialize_research_dataset,
    serialize_research_model,
)
from squeeze_core.research.models import CandidateCaseRegistry


FIXTURES = Path(__file__).parents[1] / "fixtures" / "research"


def _registry():
    return CandidateCaseRegistry.model_validate_json(
        (FIXTURES / "phase_3b_case_registry.json").read_text(encoding="utf-8")
    )


def _dataset():
    return deserialize_research_dataset(
        (FIXTURES / "phase_3b_research_dataset.json").read_bytes()
    )


def test_migration_preserves_biya_primary_secondary_dependency_and_artifact_ids():
    bundles = migrate_phase3b_registry(_registry(), acquisition_plan_id="phase-3d-migration")
    by_id = {item.case_attempt_id: item for item in bundles}
    earliest = by_id["BIYA_EARLIEST_BOUNDARY"]
    latest = by_id["BIYA_LATEST_BOUNDARY"]
    assert earliest.curation_status is CurationStatus.PUBLISHED
    assert earliest.dependent_on_bundle_id is None
    assert latest.dependent_on_bundle_id == earliest.curated_case_bundle_id
    assert earliest.source_artifact_ids == ("advisor-meeting-2026-07-17", "archived-app-log")
    assert latest.source_artifact_ids == earliest.source_artifact_ids


def test_incomplete_migrations_remain_visible_without_reinterpretation():
    bundles = migrate_phase3b_registry(_registry(), acquisition_plan_id="phase-3d-migration")
    by_id = {item.case_attempt_id: item for item in bundles}
    assert set(by_id) == {
        "BIYA_EARLIEST_BOUNDARY", "BIYA_LATEST_BOUNDARY", "KLRS_ARTIFACT_DISCOVERY",
        "LBGJ_ARTIFACT_DISCOVERY", "SG_ARTIFACT_DISCOVERY", "TRVI_ARTIFACT_DISCOVERY",
        "SLS_ARTIFACT_DISCOVERY", "KLOS_IDENTITY_CONFLICT",
    }
    assert by_id["KLOS_IDENTITY_CONFLICT"].curation_status is CurationStatus.BLOCKED
    for case_id in (
        "KLRS_ARTIFACT_DISCOVERY",
        "LBGJ_ARTIFACT_DISCOVERY",
        "SG_ARTIFACT_DISCOVERY",
        "TRVI_ARTIFACT_DISCOVERY",
        "SLS_ARTIFACT_DISCOVERY",
    ):
        assert by_id[case_id].curation_status is CurationStatus.PUBLISHED


def test_publication_adapter_returns_valid_unchanged_phase3b_models():
    registry = _registry()
    dataset = _dataset()
    before = serialize_research_model(registry)
    bundles = migrate_phase3b_registry(registry, acquisition_plan_id="phase-3d-migration")
    by_id = {item.case_attempt_id: item for item in bundles}
    entries = {item.case_id: item for item in registry.entries}
    rows = {item.case_id: item for item in dataset.rows}

    registry_candidate = build_phase3b_registry_candidate(
        by_id["KLRS_ARTIFACT_DISCOVERY"], entries["KLRS_ARTIFACT_DISCOVERY"]
    )
    dataset_candidate = build_phase3b_dataset_candidate(
        by_id["BIYA_EARLIEST_BOUNDARY"], rows["BIYA_EARLIEST_BOUNDARY"]
    )
    assert registry_candidate == entries["KLRS_ARTIFACT_DISCOVERY"]
    assert dataset_candidate == rows["BIYA_EARLIEST_BOUNDARY"]
    assert serialize_research_model(registry) == before


def test_dataset_publication_blocks_incomplete_synthetic_and_failed_leakage():
    registry = _registry()
    dataset = _dataset()
    bundles = migrate_phase3b_registry(registry, acquisition_plan_id="phase-3d-migration")
    by_id = {item.case_attempt_id: item for item in bundles}
    rows = {item.case_id: item for item in dataset.rows}
    with pytest.raises(ValueError, match="complete leakage-passing"):
        build_phase3b_dataset_candidate(
            by_id["KLOS_IDENTITY_CONFLICT"], rows["BIYA_EARLIEST_BOUNDARY"]
        )
    failed = by_id["BIYA_EARLIEST_BOUNDARY"].model_copy(update={"leakage_audit_passed": False})
    with pytest.raises(ValueError, match="complete leakage-passing"):
        build_phase3b_dataset_candidate(failed, rows["BIYA_EARLIEST_BOUNDARY"])
    synthetic = by_id["BIYA_EARLIEST_BOUNDARY"].model_copy(
        update={"fixture_classification": "SYNTHETIC_EDGE_CASE"}
    )
    with pytest.raises(ValueError, match="synthetic"):
        build_phase3b_dataset_candidate(synthetic, rows["BIYA_EARLIEST_BOUNDARY"])

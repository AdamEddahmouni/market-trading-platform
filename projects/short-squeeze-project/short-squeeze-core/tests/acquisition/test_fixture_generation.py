import hashlib
import json
from pathlib import Path

from squeeze_core.acquisition.fixture_generation import build_phase3d_fixture_documents


ACQUISITION_FIXTURES = Path(__file__).parents[1] / "fixtures" / "acquisition"
RESEARCH_FIXTURES = Path(__file__).parents[1] / "fixtures" / "research"

REQUIRED_FILES = {
    "phase_3d_acquisition_plan.json",
    "phase_3d_discovery_policy.json",
    "phase_3d_inclusion_policy.json",
    "phase_3d_exclusion_policy.json",
    "phase_3d_identity_resolution_policy.json",
    "phase_3d_boundary_policy.json",
    "phase_3d_leakage_policy.json",
    "phase_3d_deduplication_policy.json",
    "phase_3d_source_manifest.json",
    "phase_3d_artifact_manifest.json",
    "phase_3d_case_attempt_ledger.json",
    "phase_3d_biya_migrated_bundles.json",
    "phase_3d_incomplete_case_migrations.json",
    "phase_3d_leakage_audit.json",
    "phase_3d_phase3b_registry_candidates.json",
    "phase_3d_phase3b_dataset_candidates.json",
    "phase_3d_batch_summary.json",
    "phase_3d_curation_report.md",
    "expected_phase_3d_acquisition_metadata.json",
    "phase_3d_fixture_metadata.json",
}

REQUIRED_ANCHORS = {
    "acquisition_plan", "discovery_policy", "inclusion_policy", "exclusion_policy",
    "identity_resolution_policy", "boundary_policy", "leakage_policy",
    "deduplication_policy", "source_manifest", "artifact_manifest", "case_attempt_ledger",
    "biya_earliest_migration", "biya_latest_migration", "biya_duplicate_group",
    "klrs_migration", "lbgj_migration", "sg_migration", "trvi_migration", "sls_migration",
    "klos_conflict_migration", "valid_identity_resolution", "conflicted_identity_resolution",
    "valid_boundary_freeze", "outcome_aware_boundary_rejection",
    "valid_eligibility_decision", "excluded_eligibility_decision", "valid_leakage_audit",
    "failed_leakage_audit", "complete_curated_bundle", "partial_curated_bundle",
    "blocked_curated_bundle", "rejected_curated_bundle", "phase3b_registry_candidate",
    "phase3b_dataset_candidate", "registry_only_candidate", "batch_summary",
    "curation_report", "phase_3d_cli_output", "phase_3d_leakage_cli_output",
    "serialized_phase_3d_collection",
}


def test_fixture_documents_generate_byte_identically_with_complete_inventory():
    first = build_phase3d_fixture_documents(RESEARCH_FIXTURES)
    second = build_phase3d_fixture_documents(RESEARCH_FIXTURES)
    assert first == second
    assert set(first) == REQUIRED_FILES
    assert all(value.endswith(b"\n") for value in first.values())


def test_committed_fixtures_match_generator_and_metadata_hashes():
    generated = build_phase3d_fixture_documents(RESEARCH_FIXTURES)
    assert {item.name for item in ACQUISITION_FIXTURES.iterdir() if item.is_file()} == REQUIRED_FILES
    for name, content in generated.items():
        assert (ACQUISITION_FIXTURES / name).read_bytes() == content
    metadata = json.loads(generated["phase_3d_fixture_metadata.json"])
    for name, expected in metadata["file_sha256"].items():
        assert hashlib.sha256(generated[name]).hexdigest() == expected


def test_anchor_manifest_contains_every_required_unique_anchor():
    generated = build_phase3d_fixture_documents(RESEARCH_FIXTURES)
    anchors = json.loads(generated["expected_phase_3d_acquisition_metadata.json"])["anchors"]
    assert set(anchors) == REQUIRED_ANCHORS
    assert len(set(anchors.values())) == len(anchors)
    assert all(
        len(value) == 64 and set(value) <= set("0123456789abcdef")
        for value in anchors.values()
    )


def test_batch_summary_matches_discovered_pilot_ledger_state():
    generated = build_phase3d_fixture_documents(RESEARCH_FIXTURES)
    summary = json.loads(generated["phase_3d_batch_summary.json"])
    assert summary["attempted_case_count"] == 1
    assert summary["discovered_case_count"] == 1
    assert summary["partial_case_count"] == 0

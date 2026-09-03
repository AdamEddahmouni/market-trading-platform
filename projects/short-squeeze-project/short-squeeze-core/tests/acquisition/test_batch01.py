import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from squeeze_core.acquisition.batch01 import (
    OUTCOME_MANIFEST_ID, build_batch01_acquisition_plan, build_batch01_documents,
)
from squeeze_core.acquisition.models import (
    AcquisitionPlanStatus, ArtifactManifest, DiscoverySourceClass, ExclusionCode,
    LeakageAuditRequest, SourceManifest,
)
from squeeze_core.acquisition.leakage_guards import audit_outcome_leakage
from squeeze_core.acquisition.runner import curate_historical_cases
from squeeze_core.acquisition.serialization import serialize_acquisition_model
from tests.acquisition.helpers import sample_plan


ROOT = Path(__file__).resolve().parents[2]
ROWS = (
    ROOT / "intake" / "batches" / "phase-3d-historical-source-collection-01"
    / "normalized" / "batch01_discovery_rows.json"
)
FIXTURES = ROOT / "tests" / "fixtures" / "acquisition" / "batch01"

EXPECTED_SYMBOLS = {
    "XNCR", "PESI", "SLS", "ZNTL", "GPRE", "SSPC", "LBGJ",
    "TRVI", "LMNX", "MGNX", "BHVN", "OBE", "AVTX",
}
# Documents whose bytes are independent of the raw row ordering in the source file
# (i.e. not the two artifact-hash-bearing documents that hash the file bytes).
ORDER_INVARIANT_DOCS = {
    "acquisition-plan.json", "source-manifest.json", "case-attempt-ledger.json",
    "identity-review.json", "eligibility-review.json", "boundary-freeze-manifest.json",
    "leakage-audit.json", "phase3b-registry-candidates.json", "curated-case-bundles.jsonl",
    "registry-only-cases.json",
}


def _docs():
    return build_batch01_documents(ROWS)


def test_generator_is_byte_identical_and_matches_committed_fixtures():
    first = _docs()
    second = build_batch01_documents(ROWS)
    assert first == second
    assert all(value.endswith(b"\n") for value in first.values())
    committed = {item.name for item in FIXTURES.iterdir() if item.is_file()}
    assert set(first) == committed
    for name, content in first.items():
        assert (FIXTURES / name).read_bytes() == content


def test_plan_is_preregistered_frozen_and_outcome_blinded():
    plan = build_batch01_acquisition_plan()
    assert plan.plan_status is AcquisitionPlanStatus.PREREGISTERED
    assert plan.outcome_blinding_state == "OUTCOME_BLINDED"
    # Fixed, single-day historical period frozen before any outcome review.
    assert (plan.date_range[0].isoformat(), plan.date_range[1].isoformat()) == (
        "2026-07-18", "2026-07-18",
    )
    assert plan.minimum_case_count == 0
    assert "SCORE_BLIND" in plan.sampling_method
    assert "SYNTHETIC_FOR_HISTORICAL" in plan.forbidden_substitutions


def test_discovery_source_is_archived_scanner_and_outcome_blind():
    manifest = SourceManifest.model_validate_json(_docs()["source-manifest.json"])
    assert len(manifest.discovery_records) == 13
    assert {r.symbol_as_observed for r in manifest.discovery_records} == EXPECTED_SYMBOLS
    assert all(
        r.source_class is DiscoverySourceClass.ARCHIVED_MARKET_SCANNER
        for r in manifest.discovery_records
    )
    assert all(r.platform_surfaced_status == "SURFACED" for r in manifest.discovery_records)
    # A single point-in-time capture -> one shared observed timestamp.
    assert len({r.observed_at for r in manifest.discovery_records}) == 1


def test_artifacts_hashes_validate_and_raw_is_referenced_not_copied():
    docs = _docs()
    manifest = ArtifactManifest.model_validate_json(docs["artifact-manifest.json"])
    verification = json.loads(docs["artifact-verification.json"])
    assert verification["valid"] is True
    raw = next(a for a in manifest.artifacts if a.fixture_classification.value == "RESTRICTED_LOCAL_ARTIFACT")
    assert raw.content_status == "REFERENCED_NOT_COPIED"
    # The sanitized derived artifact hash matches the committed rows bytes.
    normalized = next(a for a in manifest.artifacts if a.artifact_id == "batch01-sanitized-discovery-rows")
    assert normalized.sha256 == hashlib.sha256(ROWS.read_bytes()).hexdigest()
    # No raw provider-embedded artifact is copied into the repository.
    meta = json.loads(docs["batch-01-fixture-metadata.json"])
    assert meta["raw_artifact_copied_into_repository"] is False
    assert meta["sensitive_content_included"] is False


def test_identity_partially_resolved_for_ticker_only_rows():
    resolutions = json.loads(_docs()["identity-review.json"])["resolutions"]
    assert len(resolutions) == 13
    assert {r["state"] for r in resolutions} == {"PARTIALLY_RESOLVED"}


def test_every_symbol_is_unique_with_no_dependent_secondary_boundaries():
    summary = json.loads(_docs()["batch-summary.json"])
    assert summary["attempted_case_count"] == 13
    assert summary["unique_identity_count"] == 13
    assert summary["duplicate_discovery_count"] == 0
    assert summary["dependent_secondary_boundary_count"] == 0
    assert json.loads(_docs()["dependent-secondary-boundaries.json"])["cases"] == []


def test_duplicate_symbol_is_excluded_by_curation():
    # Governs how the batch pipeline would treat a repeated security identity.
    from squeeze_core.acquisition.models import (
        ArtifactClassification, DiscoveryRecord,
    )

    def _record(order):
        return DiscoveryRecord(
            discovery_record_id=f"DUP_{order}", symbol_as_observed="DUP",
            observed_at=datetime(2026, 7, 18, 13, 37, tzinfo=UTC),
            source_class=DiscoverySourceClass.ARCHIVED_MARKET_SCANNER,
            source_name="s", source_artifact_id="a", provider="p",
            provider_scope="US_EQUITY", query_or_filter_definition="q",
            original_order=order, platform_surfaced_status="SURFACED",
            discovery_reason="r",
            fixture_classification=ArtifactClassification.LOCAL_HISTORICAL_ARTIFACT,
        )

    manifest = SourceManifest(
        manifest_id="dup", discovery_records=(_record(1), _record(2)),
        provider_provenance=(),
    )
    batch = curate_historical_cases(
        sample_plan(), manifest, ArtifactManifest(manifest_id="art", artifacts=()),
    )
    excluded = [b for b in batch.bundles if ExclusionCode.DUPLICATE_SYMBOL.value in b.diagnostics]
    assert len(excluded) == 1


def test_boundaries_are_frozen_before_outcome_and_not_outcome_aware():
    boundaries = json.loads(_docs()["boundary-freeze-manifest.json"])["boundaries"]
    assert len(boundaries) == 13
    assert all(b["frozen_before_outcome_access"] is True for b in boundaries)
    assert all(b["review_status"] == "FROZEN" for b in boundaries)
    assert all(b["boundary_rule"] == "ORIGINAL_PLATFORM_SURFACED_TIMESTAMP" for b in boundaries)


def test_no_phase_3a_request_or_result_frozen_registry_only():
    evaluation = json.loads(_docs()["evaluation-freeze-manifest.json"])
    assert evaluation["phase_3a_requests_frozen"] == 0
    assert evaluation["phase_3a_results_frozen"] == 0
    assert evaluation["entries"] == []


def test_outcome_manifest_is_separate_and_uncaptured():
    docs = _docs()
    outcome = json.loads(docs["outcome-manifest.json"])
    assert outcome["captured"] is False
    assert outcome["observations"] == []
    assert outcome["outcome_manifest_id"] == OUTCOME_MANIFEST_ID
    # The outcome manifest id is distinct from the discovery manifest id.
    source = json.loads(docs["source-manifest.json"])
    assert outcome["outcome_manifest_id"] != source["manifest_id"]


def test_all_leakage_audits_pass_for_outcome_blind_inputs():
    audits = json.loads(_docs()["leakage-audit.json"])["audits"]
    assert len(audits) == 13
    assert all(a["passed"] is True for a in audits)
    assert all(a["publication_blocked"] is False for a in audits)


def test_leakage_audit_fails_when_outcome_field_present():
    start = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    request = LeakageAuditRequest(
        case_attempt_id="BATCH01_XNCR_20260718",
        discovery_input_fields=("symbol", "maximum_return"),
        eligibility_input_fields=(), boundary_input_fields=(), evaluation_input_fields=(),
        plan_frozen_at=start, boundary_frozen_at=start + timedelta(minutes=1),
        evaluation_request_frozen_at=start + timedelta(minutes=2),
        evaluation_result_frozen_at=start + timedelta(minutes=3),
        outcome_captured_at=start + timedelta(minutes=4),
        discovery_manifest_id="d", outcome_manifest_id="o",
        plan_changed_after_outcome_access=False,
        outcome_aware_selection_indicator=False,
        maximum_return_selection_indicator=False,
        post_event_article_used_as_discovery_source=False,
    )
    result = audit_outcome_leakage(request)
    assert result.passed is False
    assert result.publication_blocked is True


def test_publication_is_registry_only_no_dataset_candidates():
    docs = _docs()
    registry = json.loads(docs["phase3b-registry-candidates.json"])
    assert registry["registry_version"] == "phase_3d_batch_01_registry.v1"
    assert len(registry["entries"]) == 13
    assert all(e["case_status"] == "ARTIFACT_DISCOVERY_ONLY" for e in registry["entries"])
    assert all(e["case_type"] == "ORIGINAL_PLATFORM_SURFACED" for e in registry["entries"])
    assert all(e["fixture_classification"] == "SANITIZED_LOCAL_ARTIFACT" for e in registry["entries"])
    assert all(e["evaluation_result_path"] is None for e in registry["entries"])
    dataset = json.loads(docs["phase3b-dataset-candidates.json"])
    assert dataset["candidates"] == []


def test_excluded_partial_blocked_sets_present_but_empty_and_all_retained():
    docs = _docs()
    for name in ("excluded-cases.json", "partial-cases.json", "blocked-cases.json",
                 "failed-leakage-cases.json"):
        assert json.loads(docs[name])["cases"] == []
    registry_only = json.loads(docs["registry-only-cases.json"])["case_ids"]
    assert len(registry_only) == 13  # every attempted case retained as registry-only


def test_eligibility_declines_fabrication_and_retains_cases():
    decisions = json.loads(_docs()["eligibility-review.json"])["decisions"]
    assert len(decisions) == 13
    assert all(d["included"] is False for d in decisions)
    assert all(
        d["exclusion_codes"] == ["CASE_REQUIRES_FABRICATED_EVIDENCE"] for d in decisions
    )


def test_outputs_have_no_dropped_platform_prediction_leakage():
    # The platform's own predictions (score / tier / target / sentiment) were dropped
    # upstream and must never surface in any generated batch document. Generic words
    # like "score" or "recommendation" appear only inside negation prose in the
    # curation report ("no scoring, ranking, recommendation ... was performed") and
    # are intentionally not treated as leakage here.
    dropped = ("squeeze_score", "setup_tier", "subprime", "target_percent",
               "stop_loss", "sentiment", "corroborat", "squeeze_confirmed")
    for name, content in _docs().items():
        text = content.decode("utf-8").lower()
        for token in dropped:
            assert token not in text, f"{token} leaked into {name}"


def test_input_order_invariance_for_curation_documents(tmp_path):
    document = json.loads(ROWS.read_text(encoding="utf-8"))
    document["rows"] = list(reversed(document["rows"]))
    reordered = tmp_path / "reordered.json"
    reordered.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    baseline = _docs()
    shuffled = build_batch01_documents(reordered)
    for name in ORDER_INVARIANT_DOCS:
        assert baseline[name] == shuffled[name], f"{name} depends on row order"


def test_anchor_manifest_is_unique_and_hex():
    anchors = json.loads(_docs()["expected-batch-01-anchors.json"])["anchors"]
    assert len(anchors) == len(set(anchors.values()))
    assert all(
        len(value) == 64 and set(value) <= set("0123456789abcdef")
        for value in anchors.values()
    )


def test_plan_cannot_curate_before_preregistration():
    draft = build_batch01_acquisition_plan().model_copy(
        update={"plan_status": AcquisitionPlanStatus.DRAFT, "deterministic_id": None}
    )
    try:
        curate_historical_cases(
            draft, SourceManifest(manifest_id="s", discovery_records=(), provider_provenance=()),
            ArtifactManifest(manifest_id="a", artifacts=()),
        )
    except ValueError as error:
        assert "ACQUISITION_PLAN_NOT_PREREGISTERED" in str(error)
    else:  # pragma: no cover
        raise AssertionError("draft plan must not curate")


def test_serialized_plan_round_trips():
    plan = build_batch01_acquisition_plan()
    assert serialize_acquisition_model(plan) == serialize_acquisition_model(plan)

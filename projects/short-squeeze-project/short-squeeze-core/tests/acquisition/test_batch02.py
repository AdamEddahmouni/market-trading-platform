import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from squeeze_core.acquisition.batch02 import (
    OUTCOME_MANIFEST_ID, OUTCOME_SOURCE_BARRIER_CODE,
    build_batch02_acquisition_plan, build_batch02_documents,
)
from squeeze_core.acquisition.models import (
    AcquisitionPlanStatus, ArtifactManifest, DiscoverySourceClass, LeakageAuditRequest,
    SourceManifest,
)
from squeeze_core.acquisition.leakage_guards import audit_outcome_leakage
from squeeze_core.acquisition.runner import curate_historical_cases
from squeeze_core.acquisition.serialization import serialize_acquisition_model


ROOT = Path(__file__).resolve().parents[2]
ROWS = (
    ROOT / "intake" / "batches" / "phase-3d-historical-source-collection-01"
    / "normalized" / "batch01_discovery_rows.json"
)
FIXTURES = ROOT / "tests" / "fixtures" / "acquisition" / "batch02"
BATCH01_FIXTURES = ROOT / "tests" / "fixtures" / "acquisition" / "batch01"

EXPECTED_SYMBOLS = {
    "XNCR", "PESI", "SLS", "ZNTL", "GPRE", "SSPC", "LBGJ",
    "TRVI", "LMNX", "MGNX", "BHVN", "OBE", "AVTX",
}
# Documents whose bytes are independent of the raw row ordering in the source file.
ORDER_INVARIANT_DOCS = {
    "acquisition-plan.json", "source-manifest.json", "case-attempt-ledger.json",
    "identity-review.json", "eligibility-review.json", "boundary-freeze-manifest.json",
    "leakage-audit.json", "phase3b-registry-candidates.json", "curated-case-bundles.jsonl",
    "registry-only-cases.json", "outcome-manifest.json", "outcome-source-search.json",
}
# Case-level detection facts inherited from batch 01 that batch 02 must not alter.
INHERITED_UNCHANGED_DOCS = {
    "boundary-freeze-manifest.json", "identity-review.json", "eligibility-review.json",
    "sufficiency-review.json", "registry-only-cases.json",
}


def _docs():
    return build_batch02_documents(ROWS)


def test_generator_is_byte_identical_and_matches_committed_fixtures():
    first = _docs()
    second = build_batch02_documents(ROWS)
    assert first == second
    assert all(value.endswith(b"\n") for value in first.values())
    committed = {item.name for item in FIXTURES.iterdir() if item.is_file()}
    assert set(first) == committed
    for name, content in first.items():
        assert (FIXTURES / name).read_bytes() == content


def test_plan_is_preregistered_outcome_blinded_and_forbids_current_for_historical():
    plan = build_batch02_acquisition_plan()
    assert plan.plan_status is AcquisitionPlanStatus.PREREGISTERED
    assert plan.outcome_blinding_state == "OUTCOME_BLINDED"
    # Detection day through the forward 24h window, frozen before any outcome access.
    assert (plan.date_range[0].isoformat(), plan.date_range[1].isoformat()) == (
        "2026-07-18", "2026-07-19",
    )
    assert plan.minimum_case_count == 0
    # The substitutions that would let a current value stand in for a historical one
    # -- or a synthetic bar stand in for a real one -- are forbidden.
    assert "CURRENT_FOR_HISTORICAL" in plan.forbidden_substitutions
    assert "SYNTHETIC_FOR_HISTORICAL" in plan.forbidden_substitutions
    assert "OUTCOME" in plan.artifact_requirements


def test_cases_boundaries_and_identity_are_inherited_unchanged_from_batch01():
    docs = _docs()
    for name in INHERITED_UNCHANGED_DOCS:
        assert docs[name] == (BATCH01_FIXTURES / name).read_bytes(), (
            f"{name} must be byte-identical to batch 01 (cases/boundaries unchanged)"
        )
    # Case IDs are exactly the batch-01 case IDs.
    registry = json.loads(docs["phase3b-registry-candidates.json"])
    batch01_registry = json.loads(
        (BATCH01_FIXTURES / "phase3b-registry-candidates.json").read_bytes()
    )
    assert {e["case_id"] for e in registry["entries"]} == {
        e["case_id"] for e in batch01_registry["entries"]
    }


def test_discovery_source_is_archived_scanner_and_outcome_blind():
    manifest = SourceManifest.model_validate_json(_docs()["source-manifest.json"])
    assert len(manifest.discovery_records) == 13
    assert {r.symbol_as_observed for r in manifest.discovery_records} == EXPECTED_SYMBOLS
    assert all(
        r.source_class is DiscoverySourceClass.ARCHIVED_MARKET_SCANNER
        for r in manifest.discovery_records
    )
    assert len({r.observed_at for r in manifest.discovery_records}) == 1


def test_boundaries_frozen_before_outcome_and_not_outcome_aware():
    boundaries = json.loads(_docs()["boundary-freeze-manifest.json"])["boundaries"]
    assert len(boundaries) == 13
    assert all(b["frozen_before_outcome_access"] is True for b in boundaries)
    assert all(b["review_status"] == "FROZEN" for b in boundaries)
    assert all(b["boundary_rule"] == "ORIGINAL_PLATFORM_SURFACED_TIMESTAMP" for b in boundaries)


def test_no_phase_3a_request_or_result_frozen_without_fabrication():
    evaluation = json.loads(_docs()["evaluation-freeze-manifest.json"])
    assert evaluation["phase_3a_requests_frozen"] == 0
    assert evaluation["phase_3a_results_frozen"] == 0
    assert evaluation["entries"] == []


def test_eligibility_declines_fabrication_and_retains_all_cases():
    decisions = json.loads(_docs()["eligibility-review.json"])["decisions"]
    assert len(decisions) == 13
    assert all(d["included"] is False for d in decisions)
    assert all(
        d["exclusion_codes"] == ["CASE_REQUIRES_FABRICATED_EVIDENCE"] for d in decisions
    )


def test_outcome_manifest_is_empty_and_marks_source_unavailable():
    docs = _docs()
    outcome = json.loads(docs["outcome-manifest.json"])
    assert outcome["captured"] is False
    assert outcome["observations"] == []
    assert outcome["status"] == "UNAVAILABLE_NO_LAWFUL_PUBLIC_SOURCE"
    assert outcome["outcome_manifest_id"] == OUTCOME_MANIFEST_ID
    # Explicit, testable guarantees against substitution/fabrication.
    assert outcome["current_values_used_as_historical"] is False
    assert outcome["fabricated_bars_used"] is False
    # The outcome manifest id is distinct from the discovery manifest id.
    source = json.loads(docs["source-manifest.json"])
    assert outcome["outcome_manifest_id"] != source["manifest_id"]


def test_outcome_source_search_records_barrier_for_every_candidate():
    search = json.loads(_docs()["outcome-source-search.json"])
    assert search["conclusion"]["acceptable_source_found"] is False
    assert search["conclusion"]["code"] == "NO_ACCEPTABLE_LAWFUL_NONAUTHENTICATED_SOURCE"
    candidates = search["candidate_sources"]
    assert len(candidates) >= 10
    # No evaluated source is acceptable, and each carries a concrete disposition.
    assert all(c["acceptable"] is False for c in candidates)
    assert all(c["disposition_code"] for c in candidates)
    dispositions = {c["disposition_code"] for c in candidates}
    # The three distinct barrier classes are all represented.
    assert "AUTHENTICATION_REQUIRED" in dispositions
    assert {"ROBOTS_DISALLOWS_NON_WHITELISTED_AGENTS", "TERMS_PROHIBIT_AUTOMATED_ACCESS"} & dispositions
    assert "PERMISSIVE_BUT_NO_PRICE_BARS" in dispositions


def test_no_fabricated_or_substituted_outcome_values_anywhere():
    # No document may carry captured outcome bars: there must be no OHLC/return
    # numeric payload, and the machine-readable fabrication guards must read false.
    forbidden_value_keys = (
        "open_price", "high_price", "low_price", "close_price", "bar_close",
        "later_return", "maximum_observed_move", "maximum_return", "realized_return",
        "forward_price", "outcome_price",
    )
    for name, content in _docs().items():
        text = content.decode("utf-8")
        for key in forbidden_value_keys:
            assert f'"{key}"' not in text, f"{key} appeared in {name}"
    meta = json.loads(_docs()["batch-02-fixture-metadata.json"])
    assert meta["outcome_window_captured"] is False
    assert meta["outcome_values_fabricated"] is False


def test_all_leakage_audits_pass_for_outcome_blind_inputs():
    audits = json.loads(_docs()["leakage-audit.json"])["audits"]
    assert len(audits) == 13
    assert all(a["passed"] is True for a in audits)
    assert all(a["publication_blocked"] is False for a in audits)


def test_leakage_audit_fails_when_outcome_field_present():
    start = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
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


def test_publication_is_registry_only_with_source_barrier_limitation():
    docs = _docs()
    registry = json.loads(docs["phase3b-registry-candidates.json"])
    assert registry["registry_version"] == "phase_3d_batch_02_registry.v1"
    assert len(registry["entries"]) == 13
    assert all(e["case_status"] == "ARTIFACT_DISCOVERY_ONLY" for e in registry["entries"])
    assert all(e["evaluation_result_path"] is None for e in registry["entries"])
    assert all(
        OUTCOME_SOURCE_BARRIER_CODE in e["limitations"] for e in registry["entries"]
    )
    dataset = json.loads(docs["phase3b-dataset-candidates.json"])
    assert dataset["candidates"] == []


def test_excluded_partial_blocked_sets_present_but_empty_and_all_retained():
    docs = _docs()
    for name in ("excluded-cases.json", "partial-cases.json", "blocked-cases.json",
                 "failed-leakage-cases.json"):
        assert json.loads(docs[name])["cases"] == []
    registry_only = json.loads(docs["registry-only-cases.json"])["case_ids"]
    assert len(registry_only) == 13


def test_summary_reports_zero_complete_cases_and_source_barrier():
    summary = json.loads(_docs()["batch-summary.json"])
    assert summary["attempted_case_count"] == 13
    assert summary["registry_only_case_count"] == 13
    assert summary["complete_dataset_candidate_count"] == 0
    assert summary["phase_3b_dataset_candidate_count"] == 0
    assert summary["outcome_windows_captured_count"] == 0
    assert summary["outcome_source_acceptable"] is False
    assert summary["outcome_source_conclusion_code"] == "NO_ACCEPTABLE_LAWFUL_NONAUTHENTICATED_SOURCE"


def test_outputs_have_no_dropped_platform_prediction_leakage():
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
    shuffled = build_batch02_documents(reordered)
    for name in ORDER_INVARIANT_DOCS:
        assert baseline[name] == shuffled[name], f"{name} depends on row order"


def test_anchor_manifest_is_unique_hex_and_distinct_from_batch01():
    anchors = json.loads(_docs()["expected-batch-02-anchors.json"])["anchors"]
    assert len(anchors) == len(set(anchors.values()))
    assert all(
        len(value) == 64 and set(value) <= set("0123456789abcdef")
        for value in anchors.values()
    )
    batch01_anchors = json.loads(
        (BATCH01_FIXTURES / "expected-batch-01-anchors.json").read_bytes()
    )["anchors"]
    # The batch-level anchors (plan/batch/registry/summary) must differ between batches.
    for key in ("acquisition_plan", "acquisition_batch", "phase3b_registry", "batch_summary"):
        assert anchors[key] != batch01_anchors[key]


def test_plan_cannot_curate_before_preregistration():
    draft = build_batch02_acquisition_plan().model_copy(
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
    plan = build_batch02_acquisition_plan()
    assert serialize_acquisition_model(plan) == serialize_acquisition_model(plan)

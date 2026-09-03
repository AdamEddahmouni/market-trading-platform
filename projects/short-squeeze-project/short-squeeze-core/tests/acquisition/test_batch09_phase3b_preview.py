"""Batch 09 coverage: the Phase 3B registry revision preview is a legal, honest dry run.

Every test here runs offline against committed fixtures. Tests that need the private Batch 05
/ Batch 08 tree are skipped when it is absent, so the suite is green on a clean checkout, and
the private-tree assertions still run on the machine that holds the data.

Nothing in this file reads a forward bar, an outcome, or a market value.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from squeeze_core.acquisition.phase3b_preview import (
    ALLOWED_MUTABLE_FIELDS,
    IMMUTABLE_FIELDS,
    FieldChangeKind,
    PreviewDecision,
    audit_phase3b_contract,
    build_field_change_frequency,
    build_preview_entry,
    build_registry_field_diff,
    build_registry_revision_preview,
)
from squeeze_core.acquisition.phase3b_preview.cli import (
    CANONICAL_REGISTRY_PATHS,
    DEFAULT_FREEZE_ROOT,
    DEFAULT_OUT_ROOT,
    DEFAULT_SOURCE_REGISTRY,
    PREVIEW_REGISTRY_FILENAME,
    PreviewOutputError,
    generate,
)
from squeeze_core.acquisition.phase3b_preview.contract import (
    ADDED_LIMITATIONS,
    PREVIEW_REGISTRY_VERSION,
    RETIRED_LIMITATION,
)
from squeeze_core.acquisition.phase3b_preview.diff import RegistryDiffError
from squeeze_core.acquisition.phase3b_preview.preview import (
    SOURCE_CASE_IDS,
    SOURCE_ORDER,
    PreviewInputError,
)
from squeeze_core.acquisition.phase3b_preview.publication import (
    check_phase3c_structural_compatibility,
    simulate_phase3b_publication,
)
from squeeze_core.evaluation import RuleOutcome
from squeeze_core.evaluation.serialization import deserialize_candidate_evaluation
from squeeze_core.research.batch import run_research_batch
from squeeze_core.research.dataset import build_research_dataset
from squeeze_core.research.detection import evaluate_research_detection
from squeeze_core.research.io import load_case_registry, load_phase_3a_result
from squeeze_core.research.models import (
    BatchEvaluationRequest,
    CandidateCaseStatus,
    DetectionStatus,
    OrderingPolicy,
)
from squeeze_core.research.policies import (
    DETECTION_POLICY_VERSION,
    OUTCOME_POLICY_VERSION,
    load_detection_policy,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "acquisition" / "batch09"
SYNTHETIC_REGISTRY = (
    FIXTURES / "synthetic-preview" / "registry" / "synthetic-preview-registry.json"
)
BATCH01_REGISTRY = REPO_ROOT / DEFAULT_SOURCE_REGISTRY
FREEZE_ROOT = REPO_ROOT / DEFAULT_FREEZE_ROOT
PRIVATE_PREVIEW = REPO_ROOT / DEFAULT_OUT_ROOT

FROZEN_BOUNDARY_TEXT = "2026-07-18T13:37:55.017661Z"

#: Recorded at the Batch 09 baseline. A change here means a canonical artifact moved.
CANONICAL_REGISTRY_SHA256 = {
    "tests/fixtures/acquisition/batch01/phase3b-registry-candidates.json":
        "c16b49386f96705d43bb110fa76796ce998299599a49528dc799e1a17e678c73",
    "tests/fixtures/acquisition/batch02/phase3b-registry-candidates.json":
        "af691a27e5568dc4aca9fe94adb07f4efe8ceabe490cb7d88ad9c7ddff9656a2",
    "tests/fixtures/acquisition/phase_3d_phase3b_registry_candidates.json":
        "28d5b14cb7be31665174121011a353eea6afb182c22c43e388fc9e162ba72b07",
    "tests/fixtures/research/phase_3b_case_registry.json":
        "5684ecd6e9f9e5b194379be411654cb5f15f5b24b638339605a2cc232bcb9b79",
}

requires_private_tree = pytest.mark.skipif(
    not (FREEZE_ROOT / "batch-summary.json").exists(),
    reason="private Batch 05/08 tree is absent on this checkout",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def preview_fixture() -> dict:
    return json.loads(
        (FIXTURES / "registry-revision-preview.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def freeze_summary() -> dict:
    return json.loads((FREEZE_ROOT / "batch-summary.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------------------
# Cohort and prior-artifact integrity
# --------------------------------------------------------------------------------------


def test_source_order_is_the_exact_frozen_thirteen():
    assert SOURCE_ORDER == (
        "XNCR", "PESI", "SLS", "ZNTL", "GPRE", "SSPC", "LBGJ",
        "TRVI", "LMNX", "MGNX", "BHVN", "OBE", "AVTX",
    )
    assert SOURCE_CASE_IDS == tuple(
        f"BATCH01_{symbol}_20260718" for symbol in SOURCE_ORDER
    )
    assert len(SOURCE_CASE_IDS) == 13


@pytest.mark.parametrize("relative,expected", sorted(CANONICAL_REGISTRY_SHA256.items()))
def test_canonical_phase3b_registries_remain_byte_identical(relative, expected):
    assert _sha256(REPO_ROOT / relative) == expected


def test_batch01_registry_entries_are_still_registry_only():
    registry = load_case_registry(BATCH01_REGISTRY)
    assert registry.registry_version == "phase_3d_batch_01_registry.v1"
    assert len(registry.entries) == 13
    for entry in registry.entries:
        assert entry.evaluation_request_path is None
        assert entry.evaluation_result_path is None
        assert entry.outcome_observation_path is None
        assert entry.evaluation_as_of is None
        assert entry.case_status is CandidateCaseStatus.ARTIFACT_DISCOVERY_ONLY
        assert RETIRED_LIMITATION in entry.limitations


# --------------------------------------------------------------------------------------
# Batch 08 freeze integrity
# --------------------------------------------------------------------------------------


@requires_private_tree
def test_all_thirteen_frozen_requests_and_results_exist(freeze_summary):
    assert len(freeze_summary["cases"]) == 13
    for case_id in SOURCE_CASE_IDS:
        assert (FREEZE_ROOT / "requests" / f"{case_id}.json").is_file()
        assert (FREEZE_ROOT / "results" / f"{case_id}.json").is_file()
        assert (FREEZE_ROOT / "leakage" / f"{case_id}.json").is_file()


@requires_private_tree
def test_batch08_artifact_hashes_verify(freeze_summary):
    mismatches = []
    for record in freeze_summary["cases"]:
        case_id = record["case_id"]
        for key, subdir in (
            ("phase3a_request_artifact", "requests"),
            ("phase3a_result_artifact", "results"),
        ):
            payload = (FREEZE_ROOT / subdir / f"{case_id}.json").read_bytes()
            declared = record[key]
            if (
                hashlib.sha256(payload).hexdigest() != declared["sha256"]
                or len(payload) != declared["byte_length"]
            ):
                mismatches.append((case_id, key))
    assert mismatches == []


@requires_private_tree
def test_all_thirteen_leakage_audits_passed(freeze_summary):
    for record in freeze_summary["cases"]:
        assert record["leakage_audit_status"] == "LEAKAGE_AUDIT_PASSED"
        assert record["freeze_status"] == "REQUEST_AND_RESULT_FROZEN"
        assert record["forward_ohlcv_accessed"] is False
        assert record["outcome_accessed"] is False


# --------------------------------------------------------------------------------------
# Contract audit
# --------------------------------------------------------------------------------------


def test_contract_audit_permits_evaluation_without_outcome():
    audit = audit_phase3b_contract()
    assert audit.evaluation_reference_without_outcome_supported is True
    assert audit.evaluation_as_of_required is True
    assert audit.candidate_identity_changes is True
    assert audit.downstream_skips_incomplete_case is True
    assert audit.downstream_classification_suppressed is True
    assert audit.conclusion is PreviewDecision.PREVIEW_COMPATIBLE_WITH_LIMITATIONS
    assert audit.registry_schema_version == "1.0.0"


def test_allowed_and_immutable_field_sets_do_not_overlap():
    assert set(ALLOWED_MUTABLE_FIELDS).isdisjoint(IMMUTABLE_FIELDS)
    assert "outcome_observation_path" in IMMUTABLE_FIELDS
    assert "case_id" in IMMUTABLE_FIELDS
    assert "symbol" in IMMUTABLE_FIELDS


# --------------------------------------------------------------------------------------
# Preview entry construction and diff
# --------------------------------------------------------------------------------------


def _first_batch01_entry():
    return load_case_registry(BATCH01_REGISTRY).entries[0]


def test_preview_entry_moves_only_allowed_fields():
    current = _first_batch01_entry()
    preview = build_preview_entry(
        current,
        evaluation_as_of=current.model_copy().evaluation_as_of or _boundary(),
        request_path="../phase3a/batch-08/requests/x.json",
        result_path="../phase3a/batch-08/results/x.json",
    )
    diff = build_registry_field_diff(current, preview)
    moved = {
        change.field_name for change in diff.changes
        if change.change_kind in {FieldChangeKind.ADDED, FieldChangeKind.CHANGED}
    }
    assert moved <= set(ALLOWED_MUTABLE_FIELDS)
    for name in IMMUTABLE_FIELDS:
        assert getattr(current, name) == getattr(preview, name)


def _boundary():
    from datetime import datetime

    return datetime.fromisoformat(FROZEN_BOUNDARY_TEXT.replace("Z", "+00:00"))


def test_preview_entry_keeps_outcome_absent_and_retires_the_stale_limitation():
    current = _first_batch01_entry()
    preview = build_preview_entry(
        current,
        evaluation_as_of=_boundary(),
        request_path="../phase3a/batch-08/requests/x.json",
        result_path="../phase3a/batch-08/results/x.json",
    )
    assert preview.outcome_observation_path is None
    assert preview.case_status is CandidateCaseStatus.EVALUATION_ONLY
    assert RETIRED_LIMITATION not in preview.limitations
    for added in ADDED_LIMITATIONS:
        assert added in preview.limitations
    # Every Batch 01 limitation other than the retired one survives.
    survivors = set(current.limitations) - {RETIRED_LIMITATION}
    assert survivors <= set(preview.limitations)


def test_preview_entry_refuses_a_source_entry_that_already_has_an_outcome():
    current = _first_batch01_entry()
    tainted = current.model_copy(
        update={"outcome_observation_path": "outcome.json", "deterministic_id": None}
    )
    with pytest.raises(PreviewInputError):
        build_preview_entry(
            tainted,
            evaluation_as_of=_boundary(),
            request_path="a.json",
            result_path="b.json",
        )


def test_diff_refuses_a_change_to_a_forbidden_field():
    current = _first_batch01_entry()
    mutated = current.model_copy(
        update={"symbol": "OTHER", "deterministic_id": None}
    )
    with pytest.raises(RegistryDiffError):
        build_registry_field_diff(current, mutated)

    renamed = current.model_copy(
        update={"detection_time_evidence_id": "CHANGED", "deterministic_id": None}
    )
    with pytest.raises(RegistryDiffError):
        build_registry_field_diff(current, renamed)


def test_diff_is_deterministic():
    current = _first_batch01_entry()
    preview = build_preview_entry(
        current,
        evaluation_as_of=_boundary(),
        request_path="../phase3a/batch-08/requests/x.json",
        result_path="../phase3a/batch-08/results/x.json",
    )
    first = build_registry_field_diff(current, preview)
    second = build_registry_field_diff(current, preview)
    assert str(first.deterministic_id) == str(second.deterministic_id)
    assert build_field_change_frequency((first,)) == build_field_change_frequency((second,))


# --------------------------------------------------------------------------------------
# The committed 13-case preview
# --------------------------------------------------------------------------------------


def test_preview_fixture_covers_exactly_thirteen_cases_in_source_order(preview_fixture):
    assert tuple(preview_fixture["source_order"]) == SOURCE_CASE_IDS
    assert len(preview_fixture["candidates"]) == 13
    assert tuple(item["case_id"] for item in preview_fixture["candidates"]) == SOURCE_CASE_IDS
    assert preview_fixture["preview_registry_version"] == PREVIEW_REGISTRY_VERSION
    assert preview_fixture["source_registry_version"] == "phase_3d_batch_01_registry.v1"


def test_preview_fixture_reports_no_publication_and_no_phase_3e(preview_fixture):
    assert preview_fixture["phase3b_published"] is False
    assert preview_fixture["phase3e_started"] is False
    for candidate in preview_fixture["candidates"]:
        assert candidate["phase3b_published"] is False
        assert candidate["phase3e_started"] is False
        assert candidate["forward_ohlcv_accessed"] is False
        assert candidate["outcome_accessed"] is False


def test_preview_outcome_path_is_null_and_outcome_stays_incomplete(preview_fixture):
    for candidate in preview_fixture["candidates"]:
        assert candidate["outcome_path"] is None
        assert candidate["outcome_status"] == (
            "OUTCOME_INCOMPLETE_NO_VALID_FORWARD_EVIDENCE"
        )
        assert candidate["research_classification_status"] == (
            "NOT_PRODUCED_OUTCOME_INCOMPLETE"
        )
    assert preview_fixture["outcome_status_counts"] == [
        ["OUTCOME_INCOMPLETE_NO_VALID_FORWARD_EVIDENCE", 13]
    ]
    assert preview_fixture["classification_status_counts"] == [
        ["NOT_PRODUCED_OUTCOME_INCOMPLETE", 13]
    ]


def test_preview_detection_is_unevaluable_because_price_range_is_unknown(preview_fixture):
    assert preview_fixture["detection_status_counts"] == [["UNEVALUABLE", 13]]
    for candidate in preview_fixture["candidates"]:
        outcomes = dict(tuple(pair) for pair in candidate["required_rule_outcomes"])
        assert outcomes["PRICE_RANGE"] == "UNKNOWN"
        assert outcomes["MARKET_DATA_AVAILABLE"] == "PASS"
        assert outcomes["COMPLETED_BAR_AVAILABLE"] == "PASS"
        assert candidate["research_detection_status"] == "UNEVALUABLE"
        assert candidate["research_detection_reason"] == ["REQUIRED_RULE_UNKNOWN:PRICE_RANGE"]
        assert candidate["research_detection_policy_version"] == DETECTION_POLICY_VERSION


def test_preview_never_substitutes_percentage_change_for_price_range(preview_fixture):
    for candidate in preview_fixture["candidates"]:
        rules = {pair[0] for pair in candidate["required_rule_outcomes"]}
        assert rules == {"PRICE_RANGE", "MARKET_DATA_AVAILABLE", "COMPLETED_BAR_AVAILABLE"}
        assert "PERCENTAGE_CHANGE_MINIMUM" not in rules


def test_preview_candidate_identity_changes_deterministically(preview_fixture):
    current_ids = {
        entry.case_id: str(entry.deterministic_id)
        for entry in load_case_registry(BATCH01_REGISTRY).entries
    }
    preview_ids = set()
    for candidate in preview_fixture["candidates"]:
        assert candidate["candidate_identity_changed"] is True
        assert candidate["current_registry_candidate_id"] == current_ids[candidate["case_id"]]
        assert (
            candidate["preview_registry_candidate_id"]
            != candidate["current_registry_candidate_id"]
        )
        preview_ids.add(candidate["preview_registry_candidate_id"])
    assert len(preview_ids) == 13


def test_preview_changed_and_unchanged_field_sets_match_the_plan(preview_fixture):
    for candidate in preview_fixture["candidates"]:
        assert set(candidate["changed_fields"]) == set(ALLOWED_MUTABLE_FIELDS)
        assert set(IMMUTABLE_FIELDS) <= set(candidate["unchanged_fields"])
        assert candidate["discovery_provenance_unchanged"] is True
        assert candidate["compatibility_status"] == "PREVIEW_COMPATIBLE_WITH_LIMITATIONS"
        assert candidate["publication_ready_if_approved"] is True


def test_preview_field_change_frequency_is_thirteen_for_every_field(preview_fixture):
    for record in preview_fixture["field_change_frequency"]:
        assert record["case_count"] == 13
    changed = {
        record["field_name"] for record in preview_fixture["field_change_frequency"]
        if record["change_kind"] in {"ADDED", "CHANGED"}
    }
    assert changed == set(ALLOWED_MUTABLE_FIELDS)


def test_preview_fixture_contains_no_market_value_field_names(preview_fixture):
    banned = (
        "open", "high", "low", "close", "volume", "price_value", "return", "ohlcv",
        "score", "rank", "recommend", "pnl", "outcome_label", "move_percent",
    )
    # Explicit negative-assertion flags: they record that nothing was read, so their names
    # are allowed to mention the thing they deny.
    negative_assertions = {"forward_ohlcv_accessed", "outcome_accessed"}
    text = json.dumps(preview_fixture["candidates"], sort_keys=True)
    keys = {key for record in preview_fixture["candidates"] for key in record}
    for key in keys - negative_assertions:
        assert not any(token in key.lower() for token in banned), key
    assert "SUBSTANTIAL_UPWARD_MOVE" not in text


@pytest.mark.parametrize(
    "classification", ["TRUE_POSITIVE", "FALSE_POSITIVE", "TRUE_NEGATIVE", "FALSE_NEGATIVE"]
)
def test_preview_fabricates_no_research_classification(preview_fixture, classification):
    assert classification not in json.dumps(preview_fixture, sort_keys=True)


# --------------------------------------------------------------------------------------
# Detection policy is executed, not restated
# --------------------------------------------------------------------------------------


def test_detection_policy_file_is_unchanged():
    policy = load_detection_policy(DETECTION_POLICY_VERSION)
    assert policy.required_rule_ids == (
        "PRICE_RANGE", "MARKET_DATA_AVAILABLE", "COMPLETED_BAR_AVAILABLE"
    )
    assert policy.policy_version == "phase_3b_research_detection_policy.v1"


def test_detection_resolves_unevaluable_when_price_range_is_unknown():
    evaluation = deserialize_candidate_evaluation(
        (
            FIXTURES / "synthetic-preview" / "evaluation"
            / "synthetic_unevaluable_evaluation.json"
        ).read_bytes()
    )
    by_rule = {item.rule_id: item.outcome for item in evaluation.rule_results}
    assert by_rule["PRICE_RANGE"] is RuleOutcome.UNKNOWN
    assert by_rule["MARKET_DATA_AVAILABLE"] is RuleOutcome.PASS
    assert by_rule["COMPLETED_BAR_AVAILABLE"] is RuleOutcome.PASS

    detection = evaluate_research_detection(
        evaluation, load_detection_policy(DETECTION_POLICY_VERSION)
    )
    assert detection.status is DetectionStatus.UNEVALUABLE


# --------------------------------------------------------------------------------------
# Synthetic Phase 3B / Phase 3C compatibility
# --------------------------------------------------------------------------------------


def test_synthetic_registry_is_evaluation_present_and_outcome_absent():
    registry = load_case_registry(SYNTHETIC_REGISTRY)
    assert len(registry.entries) == 1
    entry = registry.entries[0]
    assert entry.evaluation_result_path is not None
    assert entry.outcome_observation_path is None
    assert entry.case_status is CandidateCaseStatus.EVALUATION_ONLY


def test_synthetic_evaluation_reference_resolves_through_the_existing_loader():
    registry = load_case_registry(SYNTHETIC_REGISTRY)
    evaluation = load_phase_3a_result(registry.entries[0], SYNTHETIC_REGISTRY)
    assert evaluation.symbol == registry.entries[0].symbol
    assert evaluation.as_of == registry.entries[0].evaluation_as_of


def test_batch_runner_skips_rather_than_fails_an_outcome_absent_candidate():
    registry = load_case_registry(SYNTHETIC_REGISTRY)
    request = BatchEvaluationRequest(
        batch_version="phase_3d_batch_09_synthetic.v1",
        phase_3a_policy_version="phase_3a_transparent_candidate_policy.v1",
        research_detection_policy_version=DETECTION_POLICY_VERSION,
        outcome_label_policy_version=OUTCOME_POLICY_VERSION,
        case_ids=tuple(entry.case_id for entry in registry.entries),
        case_registry_version=registry.registry_version,
        ordering_policy=OrderingPolicy.REQUEST_ORDER,
        fail_fast=False,
    )
    batch = run_research_batch(request, SYNTHETIC_REGISTRY)
    assert batch.case_results == ()
    assert len(batch.skipped_cases) == 1

    codes = {
        diagnostic.code.value
        for case in batch.skipped_cases
        for diagnostic in case.diagnostics
    }
    assert "RESEARCH_CASE_OUTCOME_MISSING" in codes
    # The evaluation reference is recognised, so this diagnostic must be absent.
    assert "RESEARCH_CASE_EVALUATION_MISSING" not in codes

    dataset = build_research_dataset(batch)
    assert dataset.rows == ()


def test_phase3c_structural_loader_accepts_the_synthetic_preview():
    report = check_phase3c_structural_compatibility(SYNTHETIC_REGISTRY)
    assert report["registry_loaded"] is True
    assert report["loader_raised"] is False
    assert report["included_case_count"] == 1
    assert report["excluded_case_count"] == 0
    assert report["evaluation_present_count"] == 1
    assert report["outcome_absent_count"] == 1
    assert report["outcome_presence_assumed"] is False
    assert report["unknown_interpreted_as_zero"] is False
    assert report["unevaluable_interpreted_as_not_detected"] is False


def test_synthetic_publication_dry_run_serializes_all_three_formats():
    registry = load_case_registry(SYNTHETIC_REGISTRY)
    case_ids = tuple(entry.case_id for entry in registry.entries)
    first = simulate_phase3b_publication(SYNTHETIC_REGISTRY, case_ids)
    second = simulate_phase3b_publication(SYNTHETIC_REGISTRY, case_ids)

    assert first.case_result_count == 0
    assert first.skipped_case_count == 1
    assert first.dataset_row_count == 0
    assert first.canonical_registry_mutated is False

    for name in (
        "registry_json", "registry_jsonl", "registry_csv",
        "dataset_json", "dataset_jsonl", "dataset_csv", "batch_json",
    ):
        assert getattr(first, name) == getattr(second, name), name
    assert first.registry_json.endswith(b"\n")
    assert first.registry_csv.startswith(b"case_id,symbol,")
    # An empty dataset still produces a valid, parseable JSON document.
    assert json.loads(first.dataset_json)["rows"] == []
    assert first.dataset_jsonl == b""


# --------------------------------------------------------------------------------------
# The real dry run (private tree)
# --------------------------------------------------------------------------------------


@requires_private_tree
def test_real_preview_regenerates_byte_identically():
    # The output root must sit one level under the Batch 05 root for the relative Phase 3A
    # references to resolve, so regeneration is checked in place against the private root.
    private = PRIVATE_PREVIEW
    before = {
        path.name: path.read_bytes() for path in sorted(private.iterdir()) if path.is_file()
    }
    generate(BATCH01_REGISTRY, FREEZE_ROOT, private)
    after = {
        path.name: path.read_bytes() for path in sorted(private.iterdir()) if path.is_file()
    }
    assert before == after


@requires_private_tree
def test_real_preview_matches_the_committed_fixture(preview_fixture, freeze_summary):
    source_registry = load_case_registry(BATCH01_REGISTRY)
    preview, preview_registry = build_registry_revision_preview(
        source_registry=source_registry,
        freeze_root=FREEZE_ROOT,
        freeze_summary=freeze_summary,
    )
    assert str(preview.deterministic_id) == preview_fixture["deterministic_id"]
    assert preview_registry.registry_version == PREVIEW_REGISTRY_VERSION
    assert str(preview_registry.deterministic_id) == preview_fixture["preview_registry_id"]


@requires_private_tree
def test_real_preview_references_the_frozen_request_and_result_ids(
    preview_fixture, freeze_summary
):
    by_case = {record["case_id"]: record for record in freeze_summary["cases"]}
    for candidate in preview_fixture["candidates"]:
        record = by_case[candidate["case_id"]]
        assert candidate["preview_evaluation_request_id"] == record["phase3a_request_id"]
        assert candidate["preview_evaluation_result_id"] == record["phase3a_result_id"]
        assert (
            candidate["preview_evaluation_request_sha256"]
            == record["phase3a_request_artifact"]["sha256"]
        )
        assert (
            candidate["preview_evaluation_result_sha256"]
            == record["phase3a_result_artifact"]["sha256"]
        )
        assert candidate["frozen_boundary_id"] == record["boundary_id"]
        assert candidate["global_preflight_status"] == "PREFLIGHT_REJECTED"
        assert candidate["phase3a_freeze_status"] == "REQUEST_AND_RESULT_FROZEN"
        assert candidate["phase3a_leakage_status"] == "LEAKAGE_AUDIT_PASSED"


@requires_private_tree
def test_real_preview_registry_loads_all_thirteen_evaluations():
    registry_path = PRIVATE_PREVIEW / PREVIEW_REGISTRY_FILENAME
    registry = load_case_registry(registry_path)
    assert len(registry.entries) == 13
    for entry in registry.entries:
        evaluation = load_phase_3a_result(entry, registry_path)
        assert evaluation.symbol == entry.symbol
        assert evaluation.as_of == entry.evaluation_as_of
        assert entry.outcome_observation_path is None


@requires_private_tree
def test_real_dry_run_publication_produces_an_empty_dataset():
    registry_path = PRIVATE_PREVIEW / PREVIEW_REGISTRY_FILENAME
    artifacts = simulate_phase3b_publication(registry_path, SOURCE_CASE_IDS)
    assert artifacts.case_result_count == 0
    assert artifacts.skipped_case_count == 13
    assert artifacts.dataset_row_count == 0
    assert set(artifacts.skipped_diagnostic_codes) == {
        "RESEARCH_CASE_OUTCOME_MISSING", "RESEARCH_CASE_STATUS_INCOMPLETE"
    }


# --------------------------------------------------------------------------------------
# Safety guards
# --------------------------------------------------------------------------------------


def test_output_root_cannot_collide_with_a_canonical_registry_directory():
    for canonical in CANONICAL_REGISTRY_PATHS:
        target = REPO_ROOT / canonical
        if not target.exists():
            continue
        with pytest.raises(PreviewOutputError):
            generate(BATCH01_REGISTRY, FREEZE_ROOT, target.parent)


def _import_lines(text: str) -> tuple[str, ...]:
    """Executable import statements only, so prose in a docstring cannot trip a guard."""
    return tuple(
        line.strip() for line in text.splitlines()
        if line.strip().startswith(("import ", "from "))
    )


def test_preview_package_never_imports_ibapi_or_a_network_client():
    package = REPO_ROOT / "src" / "squeeze_core" / "acquisition" / "phase3b_preview"
    banned = ("ibapi", "socket", "urllib", "requests", "httpx", "http.client", "ssl")
    for path in sorted(package.glob("*.py")):
        for line in _import_lines(path.read_text(encoding="utf-8")):
            for token in banned:
                assert token not in line, f"{path.name}: {line}"


def test_no_real_ohlcv_is_committed_under_the_batch09_fixtures():
    for path in sorted(FIXTURES.rglob("*")):
        if not path.is_file() or path.suffix not in {".json", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        # Real bar payloads would carry these OHLCV keys; the preview carries none.
        for banned in ('"open":', '"high":', '"low":', '"close":', '"wap":'):
            assert banned not in text, f"{path.name} contains {banned}"


def test_preview_module_declares_no_forbidden_field_name():
    from squeeze_core.acquisition.phase3b_preview import models

    banned = ("score", "rank", "recommend", "pnl", "target_price")
    for name, member in vars(models).items():
        fields = getattr(member, "model_fields", None)
        if not isinstance(fields, dict):
            continue
        for field_name in fields:
            assert not any(token in field_name.lower() for token in banned), (
                f"{name}.{field_name}"
            )

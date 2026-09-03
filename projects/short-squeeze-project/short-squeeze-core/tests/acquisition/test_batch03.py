"""Batch 03 canonical-document, determinism, and prior-artifact-integrity tests."""

import hashlib
import json
from pathlib import Path

from squeeze_core.acquisition.batch03 import build_batch03_documents
from squeeze_core.acquisition.local_bar_intake.semantics import CREDENTIAL_LIKE_TOKENS


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "acquisition" / "batch03"
BATCH01_FIXTURES = ROOT / "tests" / "fixtures" / "acquisition" / "batch01"
BATCH02_FIXTURES = ROOT / "tests" / "fixtures" / "acquisition" / "batch02"

# Directory digests recorded before batch 03 began (stop-condition / no-regression
# guard). If either changes, batch 03 has touched prior sealed evidence.
BATCH01_DIGEST = "a4a6ece91800e215baeb197a6f178505c526d49c672f3274365bde4f624b407a"
BATCH02_DIGEST = "eefed973fb1c7e709c52060c274bf57b6d641993ac96e9e08687e75e818e30c4"


def _dir_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(p for p in path.iterdir() if p.is_file()):
        digest.update(item.name.encode())
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def test_generator_is_byte_identical_and_matches_committed_fixtures():
    first = build_batch03_documents()
    second = build_batch03_documents()
    assert first == second
    committed = {item.name for item in FIXTURES.iterdir() if item.is_file()}
    assert set(first) == committed
    for name, content in first.items():
        assert (FIXTURES / name).read_bytes() == content, name


def test_all_generated_documents_use_lf_line_endings():
    for name, content in build_batch03_documents().items():
        assert b"\r" not in content, name


def test_valid_manifest_normalizes_to_six_bars_accepted():
    docs = build_batch03_documents()
    diagnostics = json.loads(docs["normalization-diagnostics.json"])
    assert diagnostics["status"] == "ACCEPTED"
    assert diagnostics["normalized_count"] == 6
    summary = json.loads(docs["intake-summary.json"])
    assert summary["normalized_bar_count"] == 6
    assert summary["artifact_validation_status"] == "ACCEPTED"


def test_summary_keeps_event_time_separate_from_retrieval_and_export():
    summary = json.loads(build_batch03_documents()["intake-summary.json"])
    assert summary["retrieval_time"] != summary["export_time"]
    assert summary["event_start_min"] != summary["retrieval_time"]
    assert summary["event_start_min"] != summary["export_time"]
    assert summary["event_start_min"].startswith("2026-07-18")
    assert summary["retrieval_time"].startswith("2026-07-20")


def test_normalized_bars_preserve_provenance_and_semantics():
    lines = build_batch03_documents()["normalized-bars.jsonl"].splitlines()
    bars = [json.loads(line) for line in lines]
    assert len(bars) == 6
    assert [b["source_row_number"] for b in bars] == [2, 3, 4, 5, 6, 7]
    for bar in bars:
        assert bar["price_adjustment_semantics"] == "RAW_UNADJUSTED"
        assert bar["value_authenticity"] == "SYNTHETIC_FIXTURE"
        assert bar["session"] == "REGULAR"
        assert bar["source_artifact_id"] == "demo-zzaa-5m-2026-07-18::raw"


def test_rejected_examples_cover_every_barrier_class():
    examples = json.loads(
        build_batch03_documents()["rejected-intake-examples.json"]
    )["examples"]
    by_scenario = {e["scenario"]: e for e in examples}
    expected = {
        "artifact_sha256_mismatch": "ARTIFACT_SHA256_MISMATCH",
        "artifact_byte_length_mismatch": "ARTIFACT_BYTE_LENGTH_MISMATCH",
        "invalid_ohlc_relationship": "INVALID_OHLC_RELATIONSHIP",
        "negative_volume": "NEGATIVE_VOLUME",
        "malformed_decimal": "MALFORMED_DECIMAL",
        "non_finite_value": "NAN_OR_INFINITY",
        "missing_ohlc_value": "MISSING_OHLC_VALUE",
        "event_time_outside_coverage": "EVENT_TIME_OUTSIDE_COVERAGE",
        "symbol_mismatch": "SYMBOL_MISMATCH",
        "conflicting_duplicate_bar": "CONFLICTING_DUPLICATE_BAR",
        "overlapping_bars": "OVERLAPPING_BARS",
        "coverage_gap": "COVERAGE_GAP",
        "current_value_as_historical": "CURRENT_VALUE_AS_HISTORICAL",
        "synthetic_value_as_historical": "SYNTHETIC_VALUE_AS_HISTORICAL",
        "missing_timestamp_semantics": "MISSING_TIMESTAMP_SEMANTICS",
        "contradictory_adjustment_semantics": "CONTRADICTORY_ADJUSTMENT_SEMANTICS",
        "unknown_timezone": "UNKNOWN_TIMEZONE",
    }
    for scenario, code in expected.items():
        assert scenario in by_scenario, scenario
        assert by_scenario[scenario]["normalization_status"] == "REJECTED"
        assert code in by_scenario[scenario]["bundle_reason_codes"], scenario


def test_case_association_example_validates_without_outcome_work():
    docs = build_batch03_documents()
    result = json.loads(docs["case-association-validation.json"])
    assert result["valid"] is True
    assert result["outcome_computed"] is False
    assert result["phase_3a_or_3b_record_created"] is False


def test_contract_declares_no_outcome_or_phase_work():
    contract = json.loads(build_batch03_documents()["intake-contract.json"])
    assert contract["supported_artifact_formats_for_normalization"] == ["CSV"]
    # The scope explicitly disclaims acquisition, outcome work, and Phase 3A/3B/3E.
    scope = contract["scope"].lower()
    assert "no outcome work" in scope
    assert "no phase 3a/3b records" in scope
    assert "no phase 3e" in scope
    assert "no outcome value enters any pre-outcome identity" in " ".join(
        contract["guarantees"]
    )


def test_determinism_anchors_are_unique_hex():
    anchors = json.loads(build_batch03_documents()["determinism-anchors.json"])["anchors"]
    assert len(anchors) == len(set(anchors.values()))
    assert all(
        len(value) == 64 and set(value) <= set("0123456789abcdef")
        for value in anchors.values()
    )


def test_no_credential_like_values_in_any_fixture():
    for item in FIXTURES.iterdir():
        if not item.is_file():
            continue
        text = item.read_text(encoding="utf-8", errors="strict").lower()
        for token in CREDENTIAL_LIKE_TOKENS:
            assert token not in text, f"{token} appeared in {item.name}"


def test_fixture_metadata_declares_no_real_data_or_outcome_work():
    meta = json.loads(build_batch03_documents()["batch-03-fixture-metadata.json"])
    assert meta["real_market_data_committed"] is False
    assert meta["outcome_work_performed"] is False
    assert meta["sensitive_content_included"] is False


def test_batch01_and_batch02_fixtures_are_unchanged():
    assert _dir_digest(BATCH01_FIXTURES) == BATCH01_DIGEST
    assert _dir_digest(BATCH02_FIXTURES) == BATCH02_DIGEST


def test_no_outcome_or_prediction_tokens_leak_into_outputs():
    forbidden = (
        "squeeze_score", "setup_tier", "target_percent", "stop_loss", "pnl",
        "backtest", "buy", "sell", "recommendation", "ranking", "forward_return",
        "realized_return", "outcome_price",
    )
    for name, content in build_batch03_documents().items():
        text = content.decode("utf-8").lower()
        for token in forbidden:
            assert token not in text, f"{token} leaked into {name}"

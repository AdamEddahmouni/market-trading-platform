"""Lane H — edge-stats EvidenceArtifact (evidence, not prediction authority)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from market_platform_foundation.adapters.equity_intraday_jsonl import PINNED_SHA256
from market_platform_foundation.canonical import canonical_bytes, load_json_strict
from market_platform_foundation.research.edge_stats import (
    AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION,
    evidence_artifact_content_sha256,
    run_edge_stats_pipeline,
)
from market_platform_foundation.research.edge_stats.dataset import verify_and_load_biya_bars
from market_platform_foundation.research.edge_stats.matching import build_candidate_examples
from market_platform_foundation.research.edge_stats.models import (
    DEFAULT_EDGE_STATS_QUERY,
    EdgeStatsOutcomeV1,
    EdgeStatsQueryV1,
)
from market_platform_foundation.research.edge_stats.pipeline import _ci_payload
from market_platform_foundation.research.wave1.statistics import DEFAULT_WAVE1_STATISTICAL_PLAN

FIXTURE = ROOT / "tests" / "fixtures" / "research" / "edge_stats_golden_artifact.json"
GOLDEN_GENERATED_AT = "2026-09-14T22:00:00.000000Z"
EXPECTED_CONTENT_SHA256 = "4808F8F9F724FDC3E16B737A1EE33CC96F6EAE431BA6C12D2B7E2575ECA2E62A"


class EdgeStatsEvidenceArtifactTests(unittest.TestCase):
    def test_golden_artifact_matches_pipeline(self) -> None:
        built = run_edge_stats_pipeline(generated_at=GOLDEN_GENERATED_AT)
        expected = load_json_strict(FIXTURE)
        self.assertEqual(canonical_bytes(built), FIXTURE.read_bytes())
        self.assertEqual(built["content_sha256"], EXPECTED_CONTENT_SHA256)
        self.assertEqual(expected["n"], 124)
        self.assertEqual(built["dataset"]["source_sha256"], PINNED_SHA256)

    def test_authority_is_evidence_not_prediction(self) -> None:
        artifact = run_edge_stats_pipeline(generated_at=GOLDEN_GENERATED_AT)
        self.assertEqual(artifact["authority_class"], AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION)

    def test_pit_fail_closed_on_temporal_violation(self) -> None:
        bars, _dataset = verify_and_load_biya_bars()
        matched = build_candidate_examples(bars, DEFAULT_EDGE_STATS_QUERY)
        self.assertGreater(len(matched), 0)
        bad = dict(matched[0])
        features = [dict(f) for f in bad["features"]]
        features[0]["available_time_ns"] = int(bad["decision_time_ns"]) + 1
        bad["features"] = features
        with patch(
            "market_platform_foundation.research.edge_stats.matching.build_short_squeeze_examples",
            return_value=[bad],
        ):
            with self.assertRaises(ValueError) as ctx:
                build_candidate_examples(bars, DEFAULT_EDGE_STATS_QUERY)
        self.assertIn("PIT_VALIDATION_FAILED", str(ctx.exception))

    def test_pit_gate_rejects_injected_violation_in_single_row(self) -> None:
        from market_platform_foundation.research.decision_research.pit_gate import validate_temporal_example

        bars, _ = verify_and_load_biya_bars()
        matched = build_candidate_examples(bars, DEFAULT_EDGE_STATS_QUERY)
        bad = dict(matched[0])
        features = [dict(f) for f in bad["features"]]
        features[0]["available_time_ns"] = int(bad["decision_time_ns"]) + 1
        bad["features"] = features
        ok, reasons = validate_temporal_example(bad)
        self.assertFalse(ok)
        self.assertTrue(any("FEATURE_AFTER_DECISION" in r for r in reasons))

    def test_deterministic_ci_with_fixed_seed(self) -> None:
        bars, _ = verify_and_load_biya_bars()
        matched = build_candidate_examples(bars, DEFAULT_EDGE_STATS_QUERY)
        from market_platform_foundation.research.edge_stats.matching import extract_outcome_values

        values = extract_outcome_values(matched, "mean_forward_return_bps")
        first = _ci_payload(values, "mean_forward_return_bps", DEFAULT_WAVE1_STATISTICAL_PLAN)
        second = _ci_payload(values, "mean_forward_return_bps", DEFAULT_WAVE1_STATISTICAL_PLAN)
        self.assertEqual(first, second)
        self.assertEqual(first["seed"], 20260914)

    def test_source_hash_mismatch_fails_closed(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as handle:
            handle.write('{"event_type":"BAR"}\n')
            temp_path = Path(handle.name)
        try:
            with self.assertRaises(ValueError) as ctx:
                verify_and_load_biya_bars(bar_source=temp_path)
            self.assertIn("ADMITTED_SOURCE_VERIFICATION_FAILED", str(ctx.exception))
        finally:
            temp_path.unlink(missing_ok=True)

    def test_time_split_marks_insufficient_data_when_thin(self) -> None:
        artifact = run_edge_stats_pipeline(generated_at=GOLDEN_GENERATED_AT)
        self.assertEqual(
            artifact["time_splits"]["utc_morning_before_12"]["status"],
            "INSUFFICIENT_DATA",
        )

    def test_content_hash_recomputed_consistently(self) -> None:
        artifact = run_edge_stats_pipeline(generated_at=GOLDEN_GENERATED_AT)
        self.assertEqual(evidence_artifact_content_sha256(artifact), artifact["content_sha256"])

    def test_pit_max_decision_time_excludes_future_rows(self) -> None:
        bars, _ = verify_and_load_biya_bars()
        full = build_candidate_examples(bars, DEFAULT_EDGE_STATS_QUERY)
        cutoff = int(full[len(full) // 2]["decision_time_ns"])
        restricted = EdgeStatsQueryV1(
            squeeze_states=DEFAULT_EDGE_STATS_QUERY.squeeze_states,
            outcome=EdgeStatsOutcomeV1(metric="mean_forward_return_bps", horizon_bars=30),
            sample_cap=500,
            pit_max_decision_time_ns=cutoff,
        )
        subset = build_candidate_examples(bars, restricted)
        self.assertLess(len(subset), len(full))
        self.assertLessEqual(int(subset[-1]["decision_time_ns"]), cutoff)


if __name__ == "__main__":
    unittest.main()

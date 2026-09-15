"""Lane I — options-flow replay EvidenceArtifact (synthetic fixture, not live feed)."""

from __future__ import annotations

import unittest
from pathlib import Path

from market_platform_foundation.canonical import load_json_strict
from market_platform_foundation.research.options_flow_replay import (
    OPTIONS_FLOW_REPLAY_EVIDENCE_READY,
    run_options_flow_replay_pipeline,
)
from market_platform_foundation.research.options_flow_replay.artifact import (
    AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION,
    evidence_artifact_content_sha256,
)
from market_platform_foundation.research.options_flow_replay.classify import (
    classify_sweep_or_block,
    decompose_replay_print,
)
from market_platform_foundation.research.options_flow_replay.precomputed_catalog import (
    list_precomputed_options_flow_replay_artifacts,
)

ROOT = Path(__file__).resolve().parents[1]
_GOLDEN = ROOT / "fixtures" / "research" / "options_flow_replay_golden_artifact.json"
_GOLDEN_SHA = "8396D6B3FF31ECE0743F728F5AA2D753133A8F7C689FD566EBCB3C68CC0EF3BF"
_QUERY_HASH = "0A881C40BAA1C28F725C7A22435DEE1712A2F5589210958C1EC916B036C17126"
_GOLDEN_GENERATED_AT = "2026-09-14T22:30:00.000000Z"


class OptionsFlowReplayEvidenceArtifactTests(unittest.TestCase):
    def test_readiness_marker(self) -> None:
        self.assertEqual(OPTIONS_FLOW_REPLAY_EVIDENCE_READY, "OPTIONS_FLOW_REPLAY_EVIDENCE_READY")

    def test_pipeline_matches_golden_fixture(self) -> None:
        built = run_options_flow_replay_pipeline(generated_at=_GOLDEN_GENERATED_AT)
        golden = load_json_strict(_GOLDEN)
        self.assertEqual(built["content_sha256"], golden["content_sha256"])
        self.assertEqual(built["content_sha256"], _GOLDEN_SHA)

    def test_golden_catalog_sha_binding(self) -> None:
        artifacts = list_precomputed_options_flow_replay_artifacts()
        self.assertEqual(len(artifacts), 1)
        self.assertEqual(str(artifacts[0]["content_sha256"]).upper(), _GOLDEN_SHA)

    def test_transparent_decomposition_excludes_vendor_score(self) -> None:
        artifact = run_options_flow_replay_pipeline(generated_at=_GOLDEN_GENERATED_AT)
        self.assertIn("confirmation_score", artifact["explicit_exclusions"])
        prints = artifact["decomposed_prints"]
        self.assertEqual(len(prints), 3)
        trade_classes = {
            (row.get("trade_classification") or {}).get("trade_class") for row in prints
        }
        self.assertEqual(trade_classes, {"sweep", "block"})
        for row in prints:
            contrib = row.get("evidence_contribution") or {}
            self.assertIsNone(contrib.get("directional_score"))
            self.assertIn("confirmation_score", contrib.get("excluded_vendor_fields") or [])

    def test_classify_sweep_and_block_heuristics(self) -> None:
        sweep = classify_sweep_or_block({"leg_count": 4, "exchange_dispersion": 0.7, "size": 10})
        self.assertEqual(sweep["trade_class"], "sweep")
        block = classify_sweep_or_block({"leg_count": 1, "exchange_dispersion": 0.1, "size": 800, "premium": 2.0})
        self.assertEqual(block["trade_class"], "block")

    def test_missing_data_surfaced_honestly(self) -> None:
        row = decompose_replay_print(
            {
                "event_time": "2026-07-21T19:45:02Z",
                "flow_side": "sell",
                "gex_context": {"regime_label": "negative_gamma_band"},
            },
            index=0,
        )
        self.assertIn("quote_age_ms", row.get("missing_data_fields") or [])
        self.assertIn("REPLAY_FIELD_GAPS", (row.get("evidence_contribution") or {}).get("evidence_against") or [])

    def test_content_sha256_stable(self) -> None:
        artifact = load_json_strict(_GOLDEN)
        self.assertEqual(evidence_artifact_content_sha256(artifact), _GOLDEN_SHA)

    def test_authority_class_not_prediction(self) -> None:
        artifact = load_json_strict(_GOLDEN)
        self.assertEqual(artifact["authority_class"], AUTHORITY_CLASS_EVIDENCE_NOT_PREDICTION)
        self.assertEqual(artifact["live_feed_claim"], "NOT_CLAIMED")

    def test_query_version_hash_for_attachment(self) -> None:
        artifact = load_json_strict(_GOLDEN)
        query = artifact.get("query") or {}
        self.assertEqual(query.get("version_hash"), _QUERY_HASH)


if __name__ == "__main__":
    unittest.main()

"""Tests for MC4 baseline financial sentiment."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import (  # noqa: E402
    SemanticSentimentLabel,
)
from market_platform_foundation.cross_lane.evidence import EvidenceSignal  # noqa: E402
from market_platform_foundation.market_context.entity_resolution import (  # noqa: E402
    build_symbol_mapping_registry,
    load_context_document_records,
)
from market_platform_foundation.market_context.sentiment import (  # noqa: E402
    SENTIMENT_TEXT_MISSING,
    build_fixture_sentiment_pipeline,
    build_sentiment_cross_lane_evidence,
    load_finbert_fixture_labels,
    score_document_sentiment,
    score_keyword_baseline,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.projections import (  # noqa: E402
    build_workspace_market_context_payload,
)

RAW_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_raw_documents_slice.json"
FINBERT_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_finbert_labels_slice.json"
EXPECTED_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_sentiment_expected.json"
CUTOFF = "2026-07-23T00:00:00.000000000Z"
CUTOFF_NS = iso_to_epoch_ns(CUTOFF)


class TestMC4KeywordBaseline(unittest.TestCase):
    def test_keyword_positive_earnings_headline(self) -> None:
        result = score_keyword_baseline(
            "Company beat estimates on revenue",
            "Quarterly profit rose.",
        )
        self.assertEqual(result.label, SemanticSentimentLabel.POSITIVE)
        self.assertGreater(result.confidence or 0.0, 0.5)

    def test_keyword_negative_offering_headline(self) -> None:
        result = score_keyword_baseline(
            "BOXL files shelf offering registration statement",
            "Shelf registration filed with SEC.",
        )
        self.assertEqual(result.label, SemanticSentimentLabel.NEGATIVE)

    def test_tie_produces_mixed_not_neutral(self) -> None:
        result = score_keyword_baseline("upgrade and downgrade cited", None)
        self.assertEqual(result.label, SemanticSentimentLabel.MIXED)
        self.assertEqual(result.confidence, 0.5)

    def test_missing_body_fail_closed(self) -> None:
        result = score_keyword_baseline(None, None)
        self.assertEqual(result.label, SemanticSentimentLabel.UNKNOWN)
        self.assertIn(SENTIMENT_TEXT_MISSING, result.quality_flags)


class TestMC4FixturePipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records = load_context_document_records(
            RAW_FIXTURE,
            symbol_mappings=build_symbol_mapping_registry("BOXL"),
        )
        cls.finbert = load_finbert_fixture_labels(FINBERT_FIXTURE)
        cls.expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    def test_finbert_fixture_labels_load(self) -> None:
        self.assertEqual(len(self.finbert), 8)
        for document_id in (
            "mc-doc-earnings-1",
            "mc-doc-offering-1",
            "mc-doc-macro-1",
        ):
            self.assertIn(document_id, self.finbert)

    def test_boxl_pipeline_matches_golden(self) -> None:
        document_results, events, summaries = build_fixture_sentiment_pipeline(
            self.records,
            prediction_cutoff=CUTOFF,
            finbert_labels=self.finbert,
        )
        self.assertEqual(len(document_results), 8)
        self.assertEqual(len(events), 5)
        self.assertEqual(len(summaries), 5)

        for expected_row, actual_row in zip(
            self.expected["document_sentiments"],
            [
                {
                    "document_id": item.document_id,
                    "keyword_label": item.keyword.label.value if item.keyword else None,
                    "finbert_label": item.finbert.label.value if item.finbert else None,
                }
                for item in document_results
            ],
            strict=True,
        ):
            self.assertEqual(expected_row["document_id"], actual_row["document_id"])
            self.assertEqual(
                expected_row["keyword"]["label"],
                actual_row["keyword_label"],
            )
            self.assertEqual(
                expected_row["finbert"]["label"],
                actual_row["finbert_label"],
            )

        for expected_row, summary in zip(
            self.expected["event_sentiment_summaries"],
            summaries,
            strict=True,
        ):
            self.assertEqual(expected_row["event_id"], summary.event_id)
            self.assertEqual(
                expected_row["keyword"]["label"],
                summary.keyword.label.value if summary.keyword else None,
            )

    def test_pit_cutoff_excludes_future_documents(self) -> None:
        early_cutoff = iso_to_epoch_ns("2026-07-20T00:00:00.000000000Z")
        document_results, events, _ = build_fixture_sentiment_pipeline(
            self.records,
            prediction_cutoff=early_cutoff,
            finbert_labels=self.finbert,
        )
        document_ids = {item.document_id for item in document_results}
        self.assertNotIn("mc-doc-offering-1", document_ids)
        self.assertNotIn("mc-doc-macro-1", document_ids)
        self.assertLess(len(events), 5)

    def test_sentiment_does_not_emit_trade_evidence(self) -> None:
        _, _, summaries = build_fixture_sentiment_pipeline(
            self.records,
            prediction_cutoff=CUTOFF_NS,
            finbert_labels=self.finbert,
        )
        evidence = build_sentiment_cross_lane_evidence(
            summaries,
            symbol="BOXL",
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(evidence)
        p4_signals = {
            EvidenceSignal.CROSS_LANE_OPPORTUNITY_FUSED.value,
            EvidenceSignal.OPPORTUNITY_NO_ACTIONABLE_EDGE.value,
        }
        for row in evidence:
            self.assertEqual(row.get("lane"), "market_context")
            self.assertTrue(row.get("metadata", {}).get("display_only"))
            self.assertNotIn(row.get("signal"), p4_signals)


class TestMC4WorkspaceProjection(unittest.TestCase):
    def test_boxl_workspace_payload_available(self) -> None:
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_mode": "fixture"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(payload.get("available"))
        self.assertTrue(payload.get("baseline_sentiment_available"))
        self.assertEqual(len(payload.get("document_sentiments", [])), 8)
        self.assertEqual(len(payload.get("event_sentiment_summaries", [])), 5)

    def test_unsupported_symbol_fail_closed(self) -> None:
        payload = build_workspace_market_context_payload(
            "NVDA",
            as_of_context={"replay_mode": "fixture"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertFalse(payload.get("available"))
        self.assertEqual(payload.get("reason"), "MARKET_CONTEXT_FIXTURE_SYMBOL_UNSUPPORTED")


if __name__ == "__main__":
    unittest.main()

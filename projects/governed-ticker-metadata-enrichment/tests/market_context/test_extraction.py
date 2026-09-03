"""Tests for MC5 event extraction."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.contracts.market_context import (  # noqa: E402
    CompanyEventType,
    ContextQualityFlag,
    EconomicChannel,
)
from market_platform_foundation.market_context.entity_resolution import (  # noqa: E402
    build_symbol_mapping_registry,
    load_context_document_records,
)
from market_platform_foundation.market_context.extraction import (  # noqa: E402
    extract_metrics_rule_v1,
    infer_economic_channels,
    load_llm_extraction_fixture,
    load_structured_metrics_fixture,
    map_canonical_event_type,
    build_fixture_extraction_pipeline,
    extract_document,
)
from market_platform_foundation.normalization.equity_bars import iso_to_epoch_ns  # noqa: E402
from market_platform_foundation.providers.projections import (  # noqa: E402
    build_workspace_market_context_payload,
)

RAW_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_raw_documents_slice.json"
AMBIGUOUS_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_entity_ambiguous_slice.json"
LLM_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_llm_extraction_slice.json"
METRICS_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_structured_metrics_slice.json"
EXPECTED_FIXTURE = ROOT / "tests" / "fixtures" / "market_context" / "boxl_extraction_expected.json"
CUTOFF = "2026-07-23T00:00:00.000000000Z"
CUTOFF_NS = iso_to_epoch_ns(CUTOFF)


class TestMC5OntologyMapping(unittest.TestCase):
    def test_earnings_beat_maps_to_earnings(self) -> None:
        company, macro = map_canonical_event_type("earnings_beat")
        self.assertEqual(company, CompanyEventType.EARNINGS)
        self.assertIsNone(macro)

    def test_macro_headwind_has_uncertainty_channel(self) -> None:
        channels = infer_economic_channels("macro_headwind")
        self.assertEqual(channels, (EconomicChannel.UNCERTAINTY_UP,))

    def test_offering_risk_channels(self) -> None:
        channels = infer_economic_channels("offering_risk")
        self.assertIn(EconomicChannel.DILUTION_UP, channels)
        self.assertIn(EconomicChannel.LIQUIDITY_RISK_UP, channels)


class TestMC5RuleMetrics(unittest.TestCase):
    def test_price_target_regex(self) -> None:
        metrics = extract_metrics_rule_v1(
            "Analyst raised price target to $12.00",
            None,
            document_id="doc-1",
        )
        self.assertEqual(len(metrics), 1)
        self.assertEqual(metrics[0].metric_name, "price_target")
        self.assertEqual(str(metrics[0].reported_value), "12.00")


class TestMC5FixturePipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.records = load_context_document_records(
            RAW_FIXTURE,
            symbol_mappings=build_symbol_mapping_registry("BOXL"),
        )
        cls.llm = load_llm_extraction_fixture(LLM_FIXTURE)
        cls.structured = load_structured_metrics_fixture(METRICS_FIXTURE)
        cls.expected = json.loads(EXPECTED_FIXTURE.read_text(encoding="utf-8"))

    def test_llm_fixture_loads_eight_documents(self) -> None:
        self.assertEqual(len(self.llm), 8)

    def test_boxl_pipeline_matches_golden(self) -> None:
        document_results, events, summaries = build_fixture_extraction_pipeline(
            self.records,
            prediction_cutoff=CUTOFF,
            llm_labels=self.llm,
            structured_metrics=self.structured,
        )
        self.assertEqual(len(document_results), 8)
        self.assertEqual(len(events), 5)
        self.assertEqual(len(summaries), 5)

        for expected_row, actual_row in zip(
            self.expected["document_extractions"],
            document_results,
            strict=True,
        ):
            self.assertEqual(expected_row["document_id"], actual_row.document_id)
            self.assertEqual(
                expected_row["company_event_type"],
                actual_row.company_event_type.value if actual_row.company_event_type else None,
            )
            self.assertEqual(
                expected_row["economic_channels"],
                [channel.value for channel in actual_row.economic_channels],
            )

        for expected_row, summary in zip(
            self.expected["event_extraction_summaries"],
            summaries,
            strict=True,
        ):
            self.assertEqual(expected_row["event_id"], summary.event_id)
            self.assertEqual(
                expected_row["company_event_type"],
                summary.company_event_type.value if summary.company_event_type else None,
            )
            self.assertEqual(
                expected_row["economic_channels"],
                [channel.value for channel in summary.economic_channels],
            )
            self.assertEqual(
                expected_row["extracted_metrics"],
                [
                    {
                        "metric_name": metric.metric_name,
                        "reported_value": (
                            str(metric.reported_value) if metric.reported_value is not None else None
                        ),
                        "units": metric.units,
                        "period": metric.period,
                        "currency": metric.currency,
                        "comparison_period": metric.comparison_period,
                        "quality_flags": list(metric.quality_flags),
                    }
                    for metric in summary.extracted_metrics
                ],
            )

    def test_enriched_events_carry_metrics(self) -> None:
        _, events, _ = build_fixture_extraction_pipeline(
            self.records,
            prediction_cutoff=CUTOFF,
            llm_labels=self.llm,
            structured_metrics=self.structured,
        )
        earnings = next(
            event for event in events if event.canonical_event_type == "earnings_beat"
        )
        self.assertEqual(earnings.economic_channels, ("REVENUE_UP",))
        self.assertEqual(len(earnings.extracted_metrics), 1)
        self.assertEqual(earnings.extracted_metrics[0].metric_name, "revenue")

    def test_pit_cutoff_excludes_future_documents(self) -> None:
        early_cutoff = iso_to_epoch_ns("2026-07-20T00:00:00.000000000Z")
        document_results, events, summaries = build_fixture_extraction_pipeline(
            self.records,
            prediction_cutoff=early_cutoff,
            llm_labels=self.llm,
            structured_metrics=self.structured,
        )
        document_ids = {item.document_id for item in document_results}
        self.assertNotIn("mc-doc-offering-1", document_ids)
        self.assertNotIn("mc-doc-macro-1", document_ids)
        self.assertLess(len(events), 5)
        self.assertLess(len(summaries), 5)

    def test_pit_cutoff_before_fda_excludes_fda_cluster(self) -> None:
        cutoff = iso_to_epoch_ns("2026-07-17T00:00:00.000000000Z")
        _, events, summaries = build_fixture_extraction_pipeline(
            self.records,
            prediction_cutoff=cutoff,
            llm_labels=self.llm,
            structured_metrics=self.structured,
        )
        event_types = {event.canonical_event_type for event in events}
        self.assertNotIn("fda_clearance", event_types)
        summary_types = {item.canonical_event_type for item in summaries}
        self.assertNotIn("fda_clearance", summary_types)


class TestMC5AmbiguousEntity(unittest.TestCase):
    def test_ambiguous_entity_flags_extraction(self) -> None:
        records = load_context_document_records(
            AMBIGUOUS_FIXTURE,
            symbol_mappings=build_symbol_mapping_registry("BOXL"),
        )
        llm = load_llm_extraction_fixture(LLM_FIXTURE)
        result = extract_document(
            records[0],
            prediction_cutoff=CUTOFF_NS,
            llm_labels=llm,
        )
        self.assertIsNotNone(result)
        self.assertIn(
            ContextQualityFlag.EXTRACTION_ENTITY_AMBIGUOUS.value,
            result.quality_flags,
        )


class TestMC5WorkspacePayload(unittest.TestCase):
    def test_workspace_includes_extraction_block(self) -> None:
        payload = build_workspace_market_context_payload(
            "BOXL",
            as_of_context={"replay_session_id": "test"},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertTrue(payload["available"])
        self.assertTrue(payload["event_extraction_available"])
        self.assertEqual(len(payload["document_extractions"]), 8)
        self.assertEqual(len(payload["event_extraction_summaries"]), 5)

    def test_non_boxl_symbol_fail_closed(self) -> None:
        payload = build_workspace_market_context_payload(
            "NVDA",
            as_of_context={},
            prediction_cutoff=CUTOFF_NS,
        )
        self.assertFalse(payload["available"])
        self.assertFalse(payload["event_extraction_available"])


if __name__ == "__main__":
    unittest.main()

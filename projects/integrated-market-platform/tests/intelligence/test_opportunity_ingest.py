"""Ingest assembler is not a production scanner and does not fabricate MATCHED rows."""

from __future__ import annotations

import inspect
import unittest

from market_platform_foundation.intelligence.opportunity.ingest import assemble_opportunity_review_rows


class OpportunityIngestTests(unittest.TestCase):
    def test_empty_inputs_are_empty(self) -> None:
        self.assertEqual(assemble_opportunity_review_rows(), ())

    def test_discover_dicts_ignored(self) -> None:
        rows = assemble_opportunity_review_rows(
            attention_rows=({"attention_id": "d", "symbol": "MSFT", "headline": "x", "attention_score": 1, "screen_ids": ["s"]},)
        )
        self.assertEqual(rows, ())

    def test_module_does_not_import_scanner(self) -> None:
        import market_platform_foundation.intelligence.opportunity.ingest as ingest

        source = inspect.getsource(ingest)
        self.assertNotIn("UniversalStrategyScanner", source)
        self.assertNotIn("StrategyPaperRuntime", source)


if __name__ == "__main__":
    unittest.main()

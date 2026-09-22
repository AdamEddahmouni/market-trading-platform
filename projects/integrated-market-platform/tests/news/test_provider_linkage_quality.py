"""Provider linkage quality — warn without rewriting provider tickers."""

from __future__ import annotations

import unittest

from market_platform_foundation.news.contracts import InstrumentLinkage
from market_platform_foundation.news.normalize import normalize_finviz_export_item, normalize_raw_item
from market_platform_foundation.news.provider_linkage_quality import (
    CONFIDENCE_EXPLICIT,
    CONFIDENCE_PROVIDER_UNCORROBORATED,
    CONFIDENCE_UNKNOWN,
    FLAG_ALTERNATE_ENTITY_PROMINENT,
    FLAG_LOW_CONTEXTUAL_CONFIDENCE,
    FLAG_MULTIPLE_CONTRADICTORY,
    FLAG_SOURCE_URL_MISSING,
    FLAG_TICKER_NOT_IN_TEXT,
    assess_provider_linkage_quality,
)


class ProviderLinkageQualityTests(unittest.TestCase):
    def test_contradiction_warning_does_not_change_ticker(self) -> None:
        """Provider-tagged mismatch must keep PROVIDER_SYMBOL + original ticker."""

        row = {
            "headline": "MillerKnoll reports quarterly earnings beat",
            "published_time": "2026-09-12T14:30:00Z",
            "url": "",
            "tickers": ["NVDA"],
            "publisher_source": "Wire",
            "provider_native_id": "finviz:test-mismatch",
        }
        event = normalize_finviz_export_item(row, retrieved_time="2026-09-12T14:31:00Z")
        self.assertEqual(len(event.instrument_linkages), 1)
        link = event.instrument_linkages[0]
        self.assertEqual(link.provider_symbol, "NVDA")
        self.assertEqual(link.instrument_id, "NVDA")
        self.assertEqual(link.linkage_method, "PROVIDER_SYMBOL")
        self.assertEqual(link.confidence, CONFIDENCE_PROVIDER_UNCORROBORATED)
        self.assertIn(FLAG_TICKER_NOT_IN_TEXT, event.quality_flags)
        self.assertIn(FLAG_ALTERNATE_ENTITY_PROMINENT, event.quality_flags)
        self.assertIn(FLAG_SOURCE_URL_MISSING, event.quality_flags)
        self.assertIn(FLAG_LOW_CONTEXTUAL_CONFIDENCE, event.quality_flags)
        # Warning path must not invent a replacement ticker.
        self.assertNotIn("MLKN", link.provider_symbol)

    def test_corroborating_headline_does_not_false_flag(self) -> None:
        row = {
            "headline": "NVDA rises after data-center demand update",
            "published_time": "2026-09-12T14:30:00Z",
            "url": "https://example.com/nvda-story",
            "tickers": ["NVDA"],
            "publisher_source": "Wire",
            "provider_native_id": "finviz:test-ok",
        }
        event = normalize_finviz_export_item(row, retrieved_time="2026-09-12T14:31:00Z")
        link = event.instrument_linkages[0]
        self.assertEqual(link.provider_symbol, "NVDA")
        self.assertEqual(link.confidence, CONFIDENCE_EXPLICIT)
        self.assertNotIn(FLAG_TICKER_NOT_IN_TEXT, event.quality_flags)
        self.assertNotIn(FLAG_ALTERNATE_ENTITY_PROMINENT, event.quality_flags)
        self.assertNotIn(FLAG_LOW_CONTEXTUAL_CONFIDENCE, event.quality_flags)
        self.assertNotIn(FLAG_SOURCE_URL_MISSING, event.quality_flags)

    def test_company_name_can_corroborate_without_ticker_token(self) -> None:
        assessment = assess_provider_linkage_quality(
            headline="NVIDIA announces new chip platform",
            url="https://example.com/nvidia",
            linkages=(
                InstrumentLinkage(
                    instrument_id="NVDA",
                    provider_symbol="NVDA",
                    linkage_method="PROVIDER_SYMBOL",
                ),
            ),
            company_names=("NVIDIA",),
        )
        self.assertEqual(assessment.linkages[0].provider_symbol, "NVDA")
        self.assertEqual(assessment.linkages[0].confidence, CONFIDENCE_EXPLICIT)
        self.assertNotIn(FLAG_TICKER_NOT_IN_TEXT, assessment.quality_flags)

    def test_missing_url_is_quality_signal_not_drop(self) -> None:
        row = {
            "headline": "AAPL supplier update lifts shares",
            "published_time": "2026-09-12T14:30:00Z",
            "url": "",
            "tickers": ["AAPL"],
            "publisher_source": "Wire",
            "provider_native_id": "finviz:test-no-url",
        }
        event = normalize_raw_item(
            row,
            provider_id="finviz",
            source_id="finviz_elite",
            retrieved_time="2026-09-12T14:31:00Z",
        )
        self.assertEqual(event.instrument_linkages[0].provider_symbol, "AAPL")
        self.assertIn(FLAG_SOURCE_URL_MISSING, event.quality_flags)
        # Corroborated ticker → missing URL alone must not escalate to contradiction.
        self.assertNotIn(FLAG_TICKER_NOT_IN_TEXT, event.quality_flags)
        self.assertNotIn(FLAG_LOW_CONTEXTUAL_CONFIDENCE, event.quality_flags)
        # Event remains a normal normalized article (not dropped).
        self.assertTrue(event.event_id)
        self.assertEqual(event.headline, row["headline"])

    def test_unknown_stays_unknown_without_assessable_text(self) -> None:
        assessment = assess_provider_linkage_quality(
            headline="",
            summary="",
            url="https://example.com/opaque",
            linkages=(
                InstrumentLinkage(
                    instrument_id="ZZZZ",
                    provider_symbol="ZZZZ",
                    linkage_method="PROVIDER_SYMBOL",
                ),
            ),
        )
        self.assertEqual(assessment.association_confidence, CONFIDENCE_UNKNOWN)
        self.assertEqual(assessment.linkages[0].confidence, CONFIDENCE_UNKNOWN)
        self.assertEqual(assessment.linkages[0].provider_symbol, "ZZZZ")
        self.assertNotIn(FLAG_TICKER_NOT_IN_TEXT, assessment.quality_flags)
        self.assertNotIn(FLAG_ALTERNATE_ENTITY_PROMINENT, assessment.quality_flags)

    def test_multiple_linkages_preserve_all_tickers_and_flag_conflict(self) -> None:
        assessment = assess_provider_linkage_quality(
            headline="MillerKnoll announces furniture line expansion",
            url="",
            linkages=(
                InstrumentLinkage(
                    instrument_id="NVDA",
                    provider_symbol="NVDA",
                    linkage_method="PROVIDER_SYMBOL",
                ),
                InstrumentLinkage(
                    instrument_id="MLKN",
                    provider_symbol="MLKN",
                    linkage_method="PROVIDER_SYMBOL",
                ),
            ),
        )
        symbols = [link.provider_symbol for link in assessment.linkages]
        self.assertEqual(symbols, ["NVDA", "MLKN"])
        self.assertIn(FLAG_MULTIPLE_CONTRADICTORY, assessment.quality_flags)
        self.assertIn(FLAG_TICKER_NOT_IN_TEXT, assessment.quality_flags)
        # Neither ticker is rewritten or dropped.
        by_symbol = {link.provider_symbol: link for link in assessment.linkages}
        self.assertEqual(by_symbol["NVDA"].linkage_method, "PROVIDER_SYMBOL")
        self.assertEqual(by_symbol["MLKN"].linkage_method, "PROVIDER_SYMBOL")


if __name__ == "__main__":
    unittest.main()

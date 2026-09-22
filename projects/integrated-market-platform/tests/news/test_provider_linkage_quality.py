"""Provider linkage quality — warn without rewriting provider tickers."""

from __future__ import annotations

import unittest

from market_platform_foundation.news.contracts import InstrumentLinkage, NewsArticleEvent, PublicationTimeQuality
from market_platform_foundation.news.normalize import normalize_finviz_export_item, normalize_raw_item
from market_platform_foundation.news.observability import FilterPipelineStats
from market_platform_foundation.news.pipeline import NewsPipeline
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


def _finviz_row(*, headline: str, tickers: list[str], url: str = "https://example.com/x") -> dict:
    return {
        "headline": headline,
        "published_time": "2026-09-12T14:30:00Z",
        "url": url,
        "tickers": tickers,
        "publisher_source": "Wire",
        "provider_native_id": f"finviz:test-{tickers[0].lower()}",
    }


class ProviderLinkageQualityTests(unittest.TestCase):
    def test_company_name_headline_corroborates_apple_aapl(self) -> None:
        """Ordinary issuer name must corroborate without ALTERNATE/LOW_CONTEXTUAL."""

        event = normalize_finviz_export_item(
            _finviz_row(headline="Apple unveils new iPhone lineup", tickers=["AAPL"]),
            retrieved_time="2026-09-12T14:31:00Z",
        )
        link = event.instrument_linkages[0]
        self.assertEqual(link.provider_symbol, "AAPL")
        self.assertEqual(link.linkage_method, "PROVIDER_SYMBOL")
        self.assertEqual(link.confidence, CONFIDENCE_EXPLICIT)
        self.assertNotIn(FLAG_ALTERNATE_ENTITY_PROMINENT, event.quality_flags)
        self.assertNotIn(FLAG_LOW_CONTEXTUAL_CONFIDENCE, event.quality_flags)
        self.assertNotIn(FLAG_TICKER_NOT_IN_TEXT, event.quality_flags)
        self.assertTrue(event.event_id)

    def test_company_name_headline_corroborates_nvidia_nvda(self) -> None:
        event = normalize_finviz_export_item(
            _finviz_row(headline="NVIDIA announces new chip platform", tickers=["NVDA"]),
            retrieved_time="2026-09-12T14:31:00Z",
        )
        link = event.instrument_linkages[0]
        self.assertEqual(link.provider_symbol, "NVDA")
        self.assertEqual(link.confidence, CONFIDENCE_EXPLICIT)
        self.assertNotIn(FLAG_ALTERNATE_ENTITY_PROMINENT, event.quality_flags)
        self.assertNotIn(FLAG_LOW_CONTEXTUAL_CONFIDENCE, event.quality_flags)
        self.assertNotIn(FLAG_TICKER_NOT_IN_TEXT, event.quality_flags)

    def test_company_name_headline_corroborates_tesla_and_microsoft(self) -> None:
        for headline, ticker in (
            ("Tesla delivers record vehicles", "TSLA"),
            ("Microsoft cloud growth accelerates", "MSFT"),
        ):
            with self.subTest(ticker=ticker):
                event = normalize_finviz_export_item(
                    _finviz_row(headline=headline, tickers=[ticker]),
                    retrieved_time="2026-09-12T14:31:00Z",
                )
                link = event.instrument_linkages[0]
                self.assertEqual(link.provider_symbol, ticker)
                self.assertEqual(link.confidence, CONFIDENCE_EXPLICIT)
                self.assertNotIn(FLAG_ALTERNATE_ENTITY_PROMINENT, event.quality_flags)
                self.assertNotIn(FLAG_LOW_CONTEXTUAL_CONFIDENCE, event.quality_flags)

    def test_fed_headline_does_not_false_alternate_for_spy(self) -> None:
        """English tokens must not be treated as rival tickers."""

        event = normalize_finviz_export_item(
            _finviz_row(headline="Fed signals rate decision path", tickers=["SPY"]),
            retrieved_time="2026-09-12T14:31:00Z",
        )
        link = event.instrument_linkages[0]
        self.assertEqual(link.provider_symbol, "SPY")
        self.assertNotIn(FLAG_ALTERNATE_ENTITY_PROMINENT, event.quality_flags)
        self.assertNotIn(FLAG_LOW_CONTEXTUAL_CONFIDENCE, event.quality_flags)
        self.assertTrue(event.event_id)

    def test_ordinary_english_short_words_are_not_rival_tickers(self) -> None:
        """Uppercased English scraps (IT/ALL/ON/FOR/...) must not escalate alternate-entity."""

        cases = (
            ("IT spending rises across enterprise buyers", "MSFT"),
            ("ALL eyes remain on chip demand outlook", "NVDA"),
            ("ON pace for record vehicle deliveries", "TSLA"),
            ("FOR investors, valuation remains the key debate", "AAPL"),
            ("NEW data shows broader market tone softens", "SPY"),
            ("Apple stock is ON track FOR ALL time high debate", "AAPL"),
        )
        for headline, ticker in cases:
            with self.subTest(headline=headline, ticker=ticker):
                event = normalize_finviz_export_item(
                    _finviz_row(headline=headline, tickers=[ticker]),
                    retrieved_time="2026-09-12T14:31:00Z",
                )
                link = event.instrument_linkages[0]
                self.assertEqual(link.provider_symbol, ticker)
                self.assertNotIn(FLAG_ALTERNATE_ENTITY_PROMINENT, event.quality_flags)
                self.assertNotIn(FLAG_LOW_CONTEXTUAL_CONFIDENCE, event.quality_flags)

    def test_mismatch_different_company_still_flags_without_rewrite(self) -> None:
        """Headline naming a different company than the provider ticker must warn."""

        event = normalize_finviz_export_item(
            _finviz_row(
                headline="MillerKnoll reports quarterly earnings beat",
                tickers=["NVDA"],
                url="",
            ),
            retrieved_time="2026-09-12T14:31:00Z",
        )
        link = event.instrument_linkages[0]
        self.assertEqual(link.provider_symbol, "NVDA")
        self.assertEqual(link.instrument_id, "NVDA")
        self.assertEqual(link.linkage_method, "PROVIDER_SYMBOL")
        self.assertEqual(link.confidence, CONFIDENCE_PROVIDER_UNCORROBORATED)
        self.assertIn(FLAG_TICKER_NOT_IN_TEXT, event.quality_flags)
        self.assertIn(FLAG_ALTERNATE_ENTITY_PROMINENT, event.quality_flags)
        self.assertIn(FLAG_LOW_CONTEXTUAL_CONFIDENCE, event.quality_flags)
        self.assertIn(FLAG_SOURCE_URL_MISSING, event.quality_flags)
        self.assertNotIn("MLKN", link.provider_symbol)
        self.assertTrue(event.event_id)
        self.assertEqual(event.headline, "MillerKnoll reports quarterly earnings beat")

    def test_ticker_token_present_corroborates(self) -> None:
        event = normalize_finviz_export_item(
            _finviz_row(headline="NVDA rises after data-center demand update", tickers=["NVDA"]),
            retrieved_time="2026-09-12T14:31:00Z",
        )
        link = event.instrument_linkages[0]
        self.assertEqual(link.provider_symbol, "NVDA")
        self.assertEqual(link.confidence, CONFIDENCE_EXPLICIT)
        self.assertNotIn(FLAG_TICKER_NOT_IN_TEXT, event.quality_flags)
        self.assertNotIn(FLAG_ALTERNATE_ENTITY_PROMINENT, event.quality_flags)
        self.assertNotIn(FLAG_LOW_CONTEXTUAL_CONFIDENCE, event.quality_flags)

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
        self.assertEqual(assessment.linkages[0].confidence, CONFIDENCE_UNKNOWN)
        self.assertEqual(assessment.linkages[0].provider_symbol, "ZZZZ")
        self.assertNotIn(FLAG_TICKER_NOT_IN_TEXT, assessment.quality_flags)
        self.assertNotIn(FLAG_ALTERNATE_ENTITY_PROMINENT, assessment.quality_flags)

    def test_missing_url_is_quality_signal_not_drop(self) -> None:
        event = normalize_raw_item(
            _finviz_row(headline="AAPL supplier update lifts shares", tickers=["AAPL"], url=""),
            provider_id="finviz",
            source_id="finviz_elite",
            retrieved_time="2026-09-12T14:31:00Z",
        )
        self.assertEqual(event.instrument_linkages[0].provider_symbol, "AAPL")
        self.assertIn(FLAG_SOURCE_URL_MISSING, event.quality_flags)
        self.assertNotIn(FLAG_TICKER_NOT_IN_TEXT, event.quality_flags)
        self.assertNotIn(FLAG_LOW_CONTEXTUAL_CONFIDENCE, event.quality_flags)
        self.assertTrue(event.event_id)

    def test_multiple_linkages_flag_only_on_mixed_corroboration(self) -> None:
        mixed = assess_provider_linkage_quality(
            headline="MillerKnoll announces furniture line expansion",
            url="https://example.com/x",
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
        self.assertEqual(
            [link.provider_symbol for link in mixed.linkages],
            ["NVDA", "MLKN"],
        )
        self.assertIn(FLAG_MULTIPLE_CONTRADICTORY, mixed.quality_flags)
        self.assertEqual(mixed.linkages[0].provider_symbol, "NVDA")
        self.assertEqual(mixed.linkages[1].provider_symbol, "MLKN")

        all_weak = assess_provider_linkage_quality(
            headline="Broader market tone softens overnight",
            url="https://example.com/x",
            linkages=(
                InstrumentLinkage(
                    instrument_id="AAAA",
                    provider_symbol="AAAA",
                    linkage_method="PROVIDER_SYMBOL",
                ),
                InstrumentLinkage(
                    instrument_id="BBBB",
                    provider_symbol="BBBB",
                    linkage_method="PROVIDER_SYMBOL",
                ),
            ),
        )
        self.assertNotIn(FLAG_MULTIPLE_CONTRADICTORY, all_weak.quality_flags)
        self.assertEqual(
            [link.provider_symbol for link in all_weak.linkages],
            ["AAAA", "BBBB"],
        )

    def test_provider_symbol_unchanged_in_every_case(self) -> None:
        cases = (
            ("Apple unveils new iPhone lineup", ["AAPL"]),
            ("NVIDIA announces new chip platform", ["NVDA"]),
            ("MillerKnoll reports quarterly earnings beat", ["NVDA"]),
            ("Fed signals rate decision path", ["SPY"]),
            ("NVDA rises after data-center demand update", ["NVDA"]),
        )
        for headline, tickers in cases:
            with self.subTest(headline=headline, tickers=tickers):
                event = normalize_finviz_export_item(
                    _finviz_row(headline=headline, tickers=tickers),
                    retrieved_time="2026-09-12T14:31:00Z",
                )
                self.assertEqual(
                    [link.provider_symbol for link in event.instrument_linkages],
                    tickers,
                )
                self.assertTrue(event.event_id)

    def test_linkage_flags_do_not_inflate_timestamp_quality_metric(self) -> None:
        from market_platform_foundation.news.config import default_pipeline_config

        event = normalize_finviz_export_item(
            _finviz_row(
                headline="MillerKnoll reports quarterly earnings beat",
                tickers=["NVDA"],
                url="",
            ),
            retrieved_time="2026-09-12T14:31:00Z",
        )
        self.assertTrue(any(f.startswith("PROVIDER_LINKAGE_") for f in event.quality_flags))
        self.assertFalse(any(f.startswith("PUBLICATION_") for f in event.quality_flags))
        stats = FilterPipelineStats()
        as_of = 1_800_000_000_000_000_000  # far future ns
        NewsPipeline().process(
            [event],
            as_of_ns=as_of,
            config=default_pipeline_config(),
            stats=stats,
        )
        self.assertEqual(stats.timestamp_quality_issues, 0)

        stamped = NewsArticleEvent(
            event_id="ts-1",
            provider_id="finviz",
            provider_native_id="ts-1",
            source_id="finviz_elite",
            published_time="",
            published_time_quality=PublicationTimeQuality.UNKNOWN,
            retrieved_time="2026-09-12T14:31:00Z",
            headline="NVDA rises",
            url="https://example.com/x",
            quality_flags=("PUBLICATION_TIME_MISSING",),
        )
        stats2 = FilterPipelineStats()
        NewsPipeline().process(
            [stamped],
            as_of_ns=as_of,
            config=default_pipeline_config(),
            stats=stats2,
        )
        self.assertEqual(stats2.timestamp_quality_issues, 1)


if __name__ == "__main__":
    unittest.main()

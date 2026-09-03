"""Opt-in live Cboe public options statistics tests."""

from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cboe_options.contracts import (  # noqa: E402
    CboeExchangeCode,
    CoverageScope,
    OptionsStatisticFamily,
    market_statistic_to_dict,
)
from market_platform_foundation.cboe_options.daily import parse_daily_statistics_html  # noqa: E402
from market_platform_foundation.cboe_options.health import capability_report, source_health  # noqa: E402
from market_platform_foundation.cboe_options.intraday import parse_intraday_statistics_html  # noqa: E402
from market_platform_foundation.cboe_options.live import live_enabled, transport_from_env  # noqa: E402
from market_platform_foundation.cboe_options.market_volume import parse_market_volume_csv  # noqa: E402
from market_platform_foundation.cboe_options.quality import CboeOptionsQualityFlag  # noqa: E402
from market_platform_foundation.cboe_options.reference import parse_reference_csv  # noqa: E402
from market_platform_foundation.cboe_options.symbol_data import parse_symbol_data_csv  # noqa: E402
from market_platform_foundation.cboe_options.transport import CboeOptionsTransport  # noqa: E402

LIVE = os.environ.get("IMP_CBOE_OPTIONS_LIVE") == "1" and live_enabled()


@unittest.skipUnless(LIVE, "IMP_CBOE_OPTIONS_LIVE=1 required")
class LiveCboeOptionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = transport_from_env()

    def test_daily_statistics_semantics_not_just_http(self) -> None:
        html = self.transport.fetch_text(self.transport.daily_statistics_url())
        capture = parse_daily_statistics_html(
            html,
            retrieved_time="2026-08-20T12:00:00+00:00",
            ingested_time="2026-08-20T12:00:00+00:00",
        )
        self.assertGreater(len(capture.observations), 0)
        self.assertTrue(capture.trade_date)
        ratios = [
            obs
            for obs in capture.observations
            if obs.statistic_family == OptionsStatisticFamily.PUT_CALL_RATIO
        ]
        self.assertGreater(len(ratios), 0)
        self.assertTrue(all(obs.coverage_scope == CoverageScope.CBOE_EXCHANGES for obs in capture.observations))

    def test_market_volume_delay_and_scope(self) -> None:
        csv_text = self.transport.fetch_text(self.transport.market_volume_url())
        capture = parse_market_volume_csv(
            csv_text,
            retrieved_time="2026-08-20T12:00:00+00:00",
            ingested_time="2026-08-20T12:00:00+00:00",
        )
        self.assertGreater(len(capture.observations), 0)
        self.assertTrue(
            any(CboeOptionsQualityFlag.DELAYED_DATA.value in obs.quality_flags for obs in capture.observations)
        )
        serialized = json.dumps(
            [market_statistic_to_dict(obs) for obs in capture.observations],
            default=str,
        ).upper()
        self.assertNotIn("REAL_TIME", serialized)

    def test_intraday_central_timezone(self) -> None:
        html = self.transport.fetch_text(self.transport.intraday_statistics_url())
        capture = parse_intraday_statistics_html(
            html,
            retrieved_time="2026-08-20T12:00:00+00:00",
            ingested_time="2026-08-20T12:00:00+00:00",
        )
        if capture.cumulative:
            self.assertEqual(capture.timezone, "America/Chicago")

    def test_symbol_data_exchange_identity(self) -> None:
        csv_text = self.transport.fetch_text(self.transport.symbol_data_url("c1"))
        capture = parse_symbol_data_csv(
            csv_text,
            exchange=CboeExchangeCode.C1,
            retrieved_time="2026-08-20T12:00:00+00:00",
            ingested_time="2026-08-20T12:00:00+00:00",
        )
        self.assertGreater(len(capture.snapshots), 0)
        self.assertTrue(all(item.exchange == CboeExchangeCode.C1 for item in capture.snapshots))

    def test_reference_file_characterization(self) -> None:
        url = CboeOptionsTransport.reference_file_url("c1", "all_series")
        body, headers = self.transport.fetch_with_headers(url)
        text = body.decode("utf-8", errors="replace")
        capture = parse_reference_csv(
            text,
            exchange=CboeExchangeCode.C1,
            reference_category="all_series",
            source_url=url,
            retrieved_time="2026-08-20T12:00:00+00:00",
            ingested_time="2026-08-20T12:00:00+00:00",
            http_last_modified=CboeOptionsTransport.last_modified(headers),
        )
        self.assertGreater(capture.observation.row_count, 0)
        self.assertTrue(capture.observation.content_hash)

    def test_capability_report_structure(self) -> None:
        report = capability_report(live=True)
        self.assertEqual(report.get("source"), "cboe_public_options_statistics")
        self.assertIn("daily_statistics", report)
        self.assertIn("pit", report)
        health = source_health(live=True)
        self.assertIn("DAILY_STATISTICS", health)


if __name__ == "__main__":
    unittest.main()

"""Fail-closed Path A quality gates still missing as dedicated tests.

Missing PRODUCTION JSON (absent file, not an empty directory) must stay
``FORECAST_UNAVAILABLE`` and persist nothing. Live CLI is argparse-refused.
Does not redo Yahoo hop-L1 G7 views from #85.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.providers.contracts import ProviderResult  # noqa: E402
from market_platform_foundation.strategy.evaluation import (  # noqa: E402
    default_forecast_momentum_spec,
)
from market_platform_foundation.strategy.path_a_forecast_producer import (  # noqa: E402
    load_paper_demo_contributors,
    produce_paper_demo_forecast,
)
from market_platform_foundation.strategy.path_a_forecast_store import (  # noqa: E402
    load_paper_demo_forecasts,
)
from market_platform_foundation.strategy.path_a_preregistration_store import (  # noqa: E402
    persist_paper_demo_preregistration,
)
from market_platform_foundation.strategy.path_a_prospective import (  # noqa: E402
    PathAProspectiveComposer,
    build_paper_demo_path_a_invoke,
)

T = 1_700_000_000_000_000_000
EARLY_REGISTERED_AT = "2020-01-01T00:00:00.000000000Z"


def _realtime_event() -> dict:
    return {
        "capability": "US_EQUITY_L1",
        "clocks": {
            "event_time_ns": T,
            "provider_time_ns": T,
            "received_time_ns": T + 1_000_000,
        },
        "instrument_id": "AAPL",
        "provider": "test.realtime",
        "provider_symbol": "AAPL",
        "raw_payload": {
            "ask_price": 190.2,
            "ask_vol": 200,
            "bid_price": 190.0,
            "bid_vol": 100,
            "last_price": 190.1,
        },
        "sequence": 7,
        "timeliness": "REAL_TIME",
        "normalization_version": "test/1.0.0",
    }


class _RealtimeQuoteProvider:
    capability = "US_EQUITY_SNAPSHOT"
    provider_id = "test.realtime"

    def fetch_quote(self, symbol: str) -> ProviderResult:
        del symbol
        return ProviderResult(
            status="available",
            events=(_realtime_event(),),
            provider_id="test.realtime",
            capability="US_EQUITY_SNAPSHOT",
        )


class MissingProductionJsonFailClosedTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.store = Path(self._tmp.name)
        self.prereg = self.store / "prereg"
        self.forecasts = self.store / "forecasts"
        self.prereg.mkdir()
        self.forecasts.mkdir()
        self.missing_contributors = self.store / "missing-contributors.json"
        self.missing_calibration = self.store / "missing-calibration.json"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_production_json_does_not_persist(self) -> None:
        self.assertFalse(self.missing_contributors.exists())
        invoke = build_paper_demo_path_a_invoke(
            "AAPL",
            mode="paper",
            as_of_time_ns=T,
        )
        produced = produce_paper_demo_forecast(
            contributors=load_paper_demo_contributors(self.missing_contributors),
            calibration_artifact=None,
            champion=invoke.caller.champion_at_forecast,
            policy=invoke.caller.opportunity_policy,
            destination=self.forecasts,
            account_id=invoke.scan_request.scope.account_id,
            mode="paper",
            as_of_time_ns=T,
        )
        self.assertEqual(produced.status, "FORECAST_UNAVAILABLE")
        self.assertIn("FORECAST_UNAVAILABLE", produced.reason_codes)
        self.assertIn("NO_PRODUCTION_CONTRIBUTORS", produced.reason_codes)
        self.assertIsNone(produced.forecast)
        self.assertFalse(produced.persisted)
        self.assertEqual(load_paper_demo_forecasts(self.forecasts), ())

    def test_composer_missing_production_json_is_forecast_unavailable(self) -> None:
        persist_paper_demo_preregistration(
            default_forecast_momentum_spec(),
            registered_at=EARLY_REGISTERED_AT,
            destination=self.prereg,
        )
        result = PathAProspectiveComposer(
            quote_provider=_RealtimeQuoteProvider(),
            preregistration_path=self.prereg,
            contributor_path=self.missing_contributors,
            calibration_path=self.missing_calibration,
            forecast_path=self.forecasts,
        ).run("AAPL", mode="paper", as_of_time_ns=T + 2_000_000)
        self.assertIsNotNone(result.path_a)
        self.assertEqual(result.path_a.status, "FORECAST_UNAVAILABLE")
        self.assertEqual(result.path_a.opportunities, ())
        self.assertEqual(load_paper_demo_forecasts(self.forecasts), ())

    def test_cli_live_mode_is_argparse_refused(self) -> None:
        from tools.path_a_prospective_run import main as path_a_cli_main

        stderr = StringIO()
        with patch("sys.stderr", stderr):
            with self.assertRaises(SystemExit) as raised:
                path_a_cli_main(["--symbol", "AAPL", "--mode", "live"])
        self.assertNotEqual(raised.exception.code, 0)
        dumped = stderr.getvalue()
        self.assertIn("invalid choice", dumped)
        self.assertIn("live", dumped)
        self.assertNotIn("FORECAST_UNAVAILABLE", dumped)
        self.assertNotIn("yahoo.finance.delayed", dumped)

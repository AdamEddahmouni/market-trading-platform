"""IMP-RESEARCH-VALIDATION-04 Lane B real provider verification tests."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.market_data.historical_development.real_provider_verification import (  # noqa: E402
    build_verification_receipt,
    evaluate_ibkr_historical_trades_gate,
    last_n_us_equity_rth_session_dates,
    verify_moomoo_real_historical,
)
from market_platform_foundation.market_data.historical_development.provider import (  # noqa: E402
    FixtureHistoricalMarketDataProvider,
    ProviderFetchStatus,
)
from market_platform_foundation.market_data.historical_development.provider import (  # noqa: E402
    load_fixture_rows_from_json,
)


FIXTURE = ROOT / "tests/fixtures/historical_development/aapl_2026-09-15_rth_sample.json"


class LastSessionDateTests(unittest.TestCase):
    def test_last_five_before_wednesday_skips_weekend(self) -> None:
        dates = last_n_us_equity_rth_session_dates(5, end_before=date(2026, 9, 17))
        self.assertEqual(
            dates,
            (
                "2026-09-10",
                "2026-09-11",
                "2026-09-14",
                "2026-09-15",
                "2026-09-16",
            ),
        )


class IbkrGateTests(unittest.TestCase):
    def test_unverified_when_live_disabled(self) -> None:
        gate = evaluate_ibkr_historical_trades_gate(
            live_enabled=False,
            transport="tws",
            tws_reachable=True,
        )
        self.assertEqual(gate.status, "PROVIDER_UNVERIFIED")
        self.assertIn("IMP_IBKR_LIVE_NOT_ENABLED", gate.limitations)

    def test_unverified_when_tws_closed(self) -> None:
        gate = evaluate_ibkr_historical_trades_gate(
            live_enabled=True,
            transport="tws",
            tws_reachable=False,
        )
        self.assertEqual(gate.status, "PROVIDER_UNVERIFIED")
        self.assertIn("TWS_LOOPBACK_UNAVAILABLE", gate.limitations)


class MoomooVerificationTests(unittest.TestCase):
    def test_unverified_when_provider_gate_fails(self) -> None:
        class _Stub:
            provider_id = "stub"
            capability_id = "BAR_OHLCV_1M"

            def status(self) -> ProviderFetchStatus:
                return ProviderFetchStatus(
                    verified=False,
                    reason_code="PROVIDER_UNVERIFIED:OPEND_UNAVAILABLE",
                    provider_id="stub",
                )

            def fetch_session_day(self, instrument_id: str, session_date: str):
                return ()

        result = verify_moomoo_real_historical(
            repository_root=ROOT,
            artifact_root=Path("/tmp/unused"),
            provider=_Stub(),
            session_count=1,
            end_before=date(2026, 9, 16),
            perform_rerun_check=False,
        )
        self.assertEqual(result.status, "PROVIDER_UNVERIFIED")

    def test_fixture_provider_verifies_single_day(self) -> None:
        provider = FixtureHistoricalMarketDataProvider(load_fixture_rows_from_json(FIXTURE))
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            result = verify_moomoo_real_historical(
                repository_root=ROOT,
                artifact_root=Path(tmp),
                provider=provider,
                instruments=("AAPL",),
                session_count=1,
                end_before=date(2026, 9, 16),
                perform_rerun_check=False,
            )
        self.assertEqual(result.status, "VERIFIED_BOUNDED")
        self.assertEqual(result.session_dates, ("2026-09-15",))
        self.assertTrue(result.fingerprint)

    def test_receipt_contains_lane_fields(self) -> None:
        provider = FixtureHistoricalMarketDataProvider(load_fixture_rows_from_json(FIXTURE))
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            moomoo = verify_moomoo_real_historical(
                repository_root=ROOT,
                artifact_root=Path(tmp),
                provider=provider,
                instruments=("AAPL",),
                session_count=1,
                end_before=date(2026, 9, 16),
                perform_rerun_check=False,
            )
        ibkr = evaluate_ibkr_historical_trades_gate(
            live_enabled=False,
            transport="tws",
            tws_reachable=False,
        )
        receipt = build_verification_receipt(
            increment_id="IMP-RESEARCH-VALIDATION-04",
            moomoo=moomoo,
            ibkr=ibkr,
        )
        self.assertEqual(receipt["moomoo"]["MOOMOO_REAL_HISTORICAL"], "VERIFIED_BOUNDED")
        self.assertEqual(receipt["ibkr"]["IBKR_HISTORICAL_TRADES"], "PROVIDER_UNVERIFIED")
        self.assertTrue(receipt["receipt_sha256"])


if __name__ == "__main__":
    unittest.main()

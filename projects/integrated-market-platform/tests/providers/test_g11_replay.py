"""G11 query capture/replay determinism tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "providers"))

from market_platform_foundation.providers.ibkr_observational.capture import (
    REDACTED,
    capture_query_record,
    redact,
)
from market_platform_foundation.providers.ibkr_observational.historical_bars import (
    normalize_ibkr_history_payload,
)
from market_platform_foundation.providers.ibkr_observational.query_provider import (
    IbkrObservationalQueryService,
)

from ibkr_observational_support import FakeLookup, FakeQueryProvider, make_record


AAPL = make_record("AAPL")


class G11ReplayTests(unittest.TestCase):
    def test_query_capture_redacts_account_fields(self) -> None:
        record = capture_query_record(
            query_kind="ACCOUNT_READ",
            instrument_id="_ACCOUNT_",
            request={"accountId": "DU1234567"},
            response={"accounts": ["DU1234567"]},
        )
        self.assertEqual(record["request"]["accountId"], REDACTED)

    def test_deterministic_historical_normalization(self) -> None:
        payload = {"data": [{"t": 100, "o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 10}]}
        first = normalize_ibkr_history_payload(
            payload,
            instrument_id="AAPL",
            interval="1h",
            received_time_ns=999,
        )
        second = normalize_ibkr_history_payload(
            payload,
            instrument_id="AAPL",
            interval="1h",
            received_time_ns=999,
        )
        self.assertEqual([bar.to_dict() for bar in first], [bar.to_dict() for bar in second])

    def test_query_service_capture_replay_shape(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.capture import CallbackCapture

        capture = CallbackCapture()
        provider = FakeQueryProvider(
            secdef_rows={
                "AAPL": [
                    {
                        "symbol": "AAPL",
                        "conid": 1,
                        "secType": "STK",
                        "exchange": "SMART",
                        "currency": "USD",
                    }
                ]
            }
        )
        service = IbkrObservationalQueryService(
            provider=provider,
            lookup=FakeLookup(AAPL),
            capture=capture,
        )
        service.fetch_historical_bars("AAPL", con_id=1, received_time_ns=1)
        records = capture.captured_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["callback_kind"], "QUERY")
        self.assertEqual(records[0]["query_kind"], "HISTORICAL_BARS")


if __name__ == "__main__":
    unittest.main()

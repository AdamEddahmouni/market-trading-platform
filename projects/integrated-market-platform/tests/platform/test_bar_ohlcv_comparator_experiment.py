"""Item 9 BAR_OHLCV_1M bounded comparator dry-run tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.adapters.equity_intraday_jsonl import (  # noqa: E402
    COLLECTION_RELATIVE_PATH,
    EquityIntradayJsonlAdapter,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_experiment import (  # noqa: E402
    CLASSIFICATION_CONTRACT_MISMATCH,
    CLASSIFICATION_RUNNABLE,
    CLASSIFICATION_SOURCE_UNAVAILABLE,
    run_bounded_bar_ohlcv_experiment,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_sources import (  # noqa: E402
    ONE_MINUTE_NS,
    first_admissible_post_signal_bar,
    load_moomoo_opend_kline_bars,
    normalize_moomoo_kline_row,
    pit_visible_bars,
)

COLLECTION_ROOT = ROOT.parent
SOURCE_PATH = COLLECTION_ROOT / COLLECTION_RELATIVE_PATH


def _kline_row(
    *,
    time_key: str = "2023-11-14 10:30:00",
    open_: float = 10.0,
    high: float = 10.5,
    low: float = 9.5,
    close: float = 10.2,
    volume: int = 50_000,
) -> dict[str, object]:
    return {
        "close": close,
        "high": high,
        "low": low,
        "open": open_,
        "time_key": time_key,
        "volume": volume,
    }


class BarOhlcvComparatorExperimentTests(unittest.TestCase):
    def test_moomoo_kline_available_time_is_bar_end(self) -> None:
        row = {
            "close": 334.21,
            "high": 334.5,
            "low": 334.0,
            "open": 334.1,
            "time_key": "2023-11-14 10:30:00",
            "volume": 1200,
        }
        probe = normalize_moomoo_kline_row(
            row,
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        assert probe is not None
        fetched_at = int(probe["available_time"]) + 1
        event = normalize_moomoo_kline_row(row, instrument_id="AAPL", fetched_at_ns=fetched_at)
        assert event is not None
        self.assertEqual(event["available_time"], int(event["event_time"]) + ONE_MINUTE_NS)
        self.assertEqual(event["event_type"], "BAR_OHLCV_1M")

    def test_incomplete_kline_rejected_before_bar_end(self) -> None:
        row = {
            "close": 1.0,
            "high": 1.0,
            "low": 1.0,
            "open": 1.0,
            "time_key": "2023-11-14 10:30:00",
            "volume": 1,
        }
        probe = normalize_moomoo_kline_row(
            row,
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        assert probe is not None
        mid_fetch = int(probe["event_time"]) + (ONE_MINUTE_NS // 2)
        self.assertIsNone(
            normalize_moomoo_kline_row(row, instrument_id="AAPL", fetched_at_ns=mid_fetch),
        )

    def test_first_post_signal_requires_available_after_created(self) -> None:
        bars = [
            {"available_time": 100, "instrument_id": "AAPL"},
            {"available_time": 200, "instrument_id": "AAPL"},
        ]
        self.assertIsNone(first_admissible_post_signal_bar(bars, signal_time_ns=200))
        hit = first_admissible_post_signal_bar(bars, signal_time_ns=150)
        self.assertIsNotNone(hit)
        self.assertEqual(int(hit["available_time"]), 200)

    def test_malformed_kline_time_key_rejected(self) -> None:
        self.assertIsNone(
            normalize_moomoo_kline_row(
                _kline_row(time_key="not-a-timestamp"),
                instrument_id="AAPL",
                fetched_at_ns=9_999_999_999_999_999_999,
            ),
        )

    def test_stale_observation_hides_future_bar(self) -> None:
        row = _kline_row()
        probe = normalize_moomoo_kline_row(
            row,
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        assert probe is not None
        bar_end = int(probe["available_time"])
        loaded = load_moomoo_opend_kline_bars(
            instrument_id="AAPL",
            observation_time_ns=bar_end - 1,
            fetched_at_ns=bar_end,
            kline_rows=(row,),
        )
        self.assertFalse(loaded.ok)
        self.assertEqual(loaded.reason_code, CLASSIFICATION_CONTRACT_MISMATCH)

    def test_no_kline_rows_fail_closed(self) -> None:
        loaded = load_moomoo_opend_kline_bars(
            instrument_id="AAPL",
            observation_time_ns=1_700_000_000_000_000_000,
            fetched_at_ns=1_700_000_000_000_000_000,
            kline_rows=(),
        )
        self.assertFalse(loaded.ok)
        self.assertEqual(loaded.reason_code, CLASSIFICATION_CONTRACT_MISMATCH)

    @mock.patch(
        "market_platform_foundation.paper.calibration.bar_ohlcv_sources.opend_reachable",
        return_value=False,
    )
    def test_opend_unavailable_without_injected_rows(self, _reachable: mock.Mock) -> None:
        loaded = load_moomoo_opend_kline_bars(
            instrument_id="AAPL",
            observation_time_ns=1_700_000_000_000_000_000,
        )
        self.assertFalse(loaded.ok)
        self.assertEqual(loaded.reason_code, "OPEND_UNAVAILABLE")

    def test_lawful_first_post_signal_bar_drives_simulator_fill(self) -> None:
        rows = (
            _kline_row(time_key="2023-11-14 10:29:00"),
            _kline_row(time_key="2023-11-14 10:30:00"),
        )
        first = normalize_moomoo_kline_row(
            rows[0],
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        second = normalize_moomoo_kline_row(
            rows[1],
            instrument_id="AAPL",
            fetched_at_ns=9_999_999_999_999_999_999,
        )
        assert first is not None and second is not None
        first_bar_end = int(first["available_time"])
        signal = first_bar_end - 1
        observation = int(second["available_time"])
        result = run_bounded_bar_ohlcv_experiment(
            signal_time_ns=signal,
            observation_time_ns=observation,
            instrument_id="AAPL",
            source="moomoo-opend",
            collection_root=COLLECTION_ROOT,
            kline_rows=rows,
        )
        self.assertEqual(result.classification, CLASSIFICATION_RUNNABLE)
        assert result.first_post_signal_bar is not None
        self.assertEqual(int(result.first_post_signal_bar["available_time"]), first_bar_end)
        self.assertGreater(first_bar_end, signal)
        self.assertEqual(result.sim_order_state, "FILLED")
        self.assertIsNotNone(result.sim_fill)
        self.assertFalse(result.calibrated)
        self.assertFalse(result.orders_placed)

    @mock.patch(
        "market_platform_foundation.paper.calibration.bar_ohlcv_sources.opend_reachable",
        return_value=False,
    )
    def test_experiment_source_unavailable_when_opend_missing(self, _reachable: mock.Mock) -> None:
        result = run_bounded_bar_ohlcv_experiment(
            signal_time_ns=1,
            observation_time_ns=2,
            instrument_id="AAPL",
            source="moomoo-opend",
            collection_root=COLLECTION_ROOT,
        )
        self.assertEqual(result.classification, CLASSIFICATION_SOURCE_UNAVAILABLE)

    def test_admitted_fixture_experiment_runnable_when_signal_before_bar(self) -> None:
        self.assertTrue(
            SOURCE_PATH.is_file(),
            "admitted BIYA bar fixture must be present for Item 9 offline tests",
        )
        adapter = EquityIntradayJsonlAdapter(ingest_run_id="item9-test")
        ingested = adapter.ingest_path(SOURCE_PATH)
        self.assertGreater(len(ingested.canonical_events), 2)
        sample = ingested.canonical_events[1]
        signal = int(sample["event_time"])
        observation = int(sample["available_time"]) + ONE_MINUTE_NS
        result = run_bounded_bar_ohlcv_experiment(
            signal_time_ns=signal,
            observation_time_ns=observation,
            instrument_id=str(sample["instrument_id"]),
            source="admitted-fixture",
            collection_root=COLLECTION_ROOT,
        )
        self.assertEqual(result.classification, CLASSIFICATION_RUNNABLE)
        self.assertIsNotNone(result.first_post_signal_bar)
        self.assertGreater(int(result.first_post_signal_bar["available_time"]), signal)
        self.assertFalse(result.orders_placed)
        self.assertFalse(result.calibrated)

    def test_contract_mismatch_when_signal_after_visible_bars(self) -> None:
        bar_start = 1_700_000_000_000_000_000
        bar_end = bar_start + ONE_MINUTE_NS
        rows = (
            {
                "close": 10.0,
                "high": 10.5,
                "low": 9.5,
                "open": 10.0,
                "time_key": "2023-11-14 10:30:00",
                "volume": 5000,
            },
        )
        loaded = load_moomoo_opend_kline_bars(
            instrument_id="AAPL",
            observation_time_ns=bar_end,
            fetched_at_ns=bar_end,
            kline_rows=rows,
        )
        self.assertTrue(loaded.ok)
        visible = pit_visible_bars(loaded.bars, observation_time_ns=bar_end, instrument_id="AAPL")
        self.assertEqual(len(visible), 1)
        result = run_bounded_bar_ohlcv_experiment(
            signal_time_ns=bar_end,
            observation_time_ns=bar_end,
            instrument_id="AAPL",
            source="moomoo-opend",
            collection_root=COLLECTION_ROOT,
            kline_rows=rows,
        )
        self.assertEqual(result.classification, CLASSIFICATION_CONTRACT_MISMATCH)
        self.assertIn("SIM_NO_POST_SIGNAL_BAR", result.sim_reason_codes)


if __name__ == "__main__":
    unittest.main()

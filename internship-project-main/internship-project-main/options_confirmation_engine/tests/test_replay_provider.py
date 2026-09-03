"""Offline unit tests for the replay snapshot provider."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from options_engine.finviz_screener import resolve_universe
from options_engine.replay_provider import (
    fetch_options_snapshot_replay,
    find_best_snapshot_path,
    list_rich_snapshot_tickers,
    snapshot_from_dict,
)


SAMPLE_SNAPSHOT = {
    "ticker": "DEMO",
    "as_of": "2026-06-20T12:00:00+00:00",
    "spot_price": 100.0,
    "expirations": ["6/22/2026"],
    "contracts": [
        {
            "contract_symbol": "DEMO260622C00100000",
            "side": "call",
            "strike": 100.0,
            "expiration": "6/22/2026",
            "implied_volatility": 0.3,
            "volume": 100.0,
            "open_interest": 200.0,
            "bid": 1.0,
            "ask": 1.2,
            "last_price": 1.1,
            "in_the_money": True,
            "delta": 0.55,
        }
    ]
    + [
        {
            "contract_symbol": f"DEMO260622C{100+i:05d}000",
            "side": "call",
            "strike": float(100 + i),
            "expiration": "6/22/2026",
            "implied_volatility": 0.3,
            "volume": 10.0,
            "open_interest": 20.0,
            "bid": 1.0,
            "ask": 1.2,
            "last_price": 1.1,
            "in_the_money": False,
            "delta": 0.4,
        }
        for i in range(1, 25)
    ],
    "data_quality_flags": [],
}


class ReplayProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.snap_dir = Path(self.tmp.name)
        self.settings = {
            "chain": {"replay": {"snapshot_dir": str(self.snap_dir), "min_contracts": 20}},
            "universe": {"max_tickers": 5, "fallback_tickers": ["ZZZZ"]},
        }

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, name: str, data: dict) -> None:
        (self.snap_dir / name).write_text(json.dumps(data), encoding="utf-8")

    def test_snapshot_from_dict(self) -> None:
        snap = snapshot_from_dict(SAMPLE_SNAPSHOT)
        self.assertEqual(snap.ticker, "DEMO")
        self.assertEqual(snap.spot_price, 100.0)
        self.assertEqual(len(snap.contracts), 25)
        self.assertAlmostEqual(snap.contracts[0].delta, 0.55)

    def test_skips_placeholder_and_picks_richest_recent(self) -> None:
        empty = {"ticker": "DEMO", "as_of": "x", "spot_price": 0, "contracts": []}
        self._write("DEMO_2026-06-18.json", empty)
        self._write("DEMO_2026-06-20.json", SAMPLE_SNAPSHOT)
        path = find_best_snapshot_path("DEMO", self.settings)
        self.assertIsNotNone(path)
        self.assertIn("2026-06-20", str(path))

    def test_fetch_replay_offline(self) -> None:
        self._write("DEMO_2026-06-20.json", SAMPLE_SNAPSHOT)
        snap = fetch_options_snapshot_replay("DEMO", self.settings)
        self.assertEqual(snap.provider, "replay")
        self.assertEqual(len(snap.contracts), 25)
        self.assertNotIn("empty_chain", snap.data_quality_flags)

    def test_list_rich_tickers_and_universe(self) -> None:
        self._write("AAA_2026-06-20.json", SAMPLE_SNAPSHOT)
        other = dict(SAMPLE_SNAPSHOT)
        other["ticker"] = "BBB"
        self._write("BBB_2026-06-19.json", other)
        tickers = list_rich_snapshot_tickers(self.settings)
        self.assertIn("AAA", tickers)
        self.assertIn("BBB", tickers)
        self.settings["universe"]["source"] = "snapshots"
        uni = resolve_universe(self.settings)
        self.assertEqual(uni, ["AAA", "BBB"])


if __name__ == "__main__":
    unittest.main()

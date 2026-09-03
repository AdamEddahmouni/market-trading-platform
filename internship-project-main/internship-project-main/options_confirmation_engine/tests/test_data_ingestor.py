"""Unit tests for options data ingestor behavior."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from options_engine.data_ingestor import fetch_options_snapshot


class DataIngestorTests(unittest.TestCase):
    """Validate ingestor returns snapshot object on failures."""

    def test_ingestor_handles_unknown_ticker(self) -> None:
        settings = {"chain": {"expiries_to_scan": 1, "min_open_interest": 1, "min_contract_volume": 1}}
        result = fetch_options_snapshot("THISLIKELYDOESNOTEXIST123", settings=settings, as_of="2026-06-07T20:00:00+00:00")
        self.assertEqual(result.ticker, "THISLIKELYDOESNOTEXIST123")
        self.assertIsInstance(result.data_quality_flags, list)


if __name__ == "__main__":
    unittest.main()


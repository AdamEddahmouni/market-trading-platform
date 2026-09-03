"""Cboe options reference CSV versioning."""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cboe_options.contracts import CboeExchangeCode  # noqa: E402
from market_platform_foundation.cboe_options.reference import parse_reference_csv  # noqa: E402

sys.path.insert(0, str(ROOT / "tests" / "cboe_options"))
from _helpers import INGESTED_TIME, RETRIEVED_TIME, load_text

REFERENCE_URL = "https://cdn.cboe.com/resources/options/reference_data/c1/all_series.csv"


class CboeReferenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.v1_text = load_text("reference_v1.csv")
        self.v2_text = load_text("reference_v2.csv")
        self.v1_hash = hashlib.sha256(self.v1_text.encode("utf-8")).hexdigest().upper()
        self.v2_hash = hashlib.sha256(self.v2_text.encode("utf-8")).hexdigest().upper()

    def test_reference_parse_preserves_row_count(self) -> None:
        capture = parse_reference_csv(
            self.v1_text,
            exchange=CboeExchangeCode.C1,
            reference_category="all_series",
            source_url=REFERENCE_URL,
            retrieved_time=RETRIEVED_TIME,
            ingested_time=INGESTED_TIME,
        )
        self.assertEqual(capture.observation.row_count, 5)
        self.assertEqual(capture.observation.exchange, CboeExchangeCode.C1)

    def test_same_url_different_hash_is_new_version(self) -> None:
        first = parse_reference_csv(
            self.v1_text,
            exchange=CboeExchangeCode.C1,
            reference_category="all_series",
            source_url=REFERENCE_URL,
            retrieved_time=RETRIEVED_TIME,
            ingested_time="2026-08-19T08:00:00-05:00",
        ).observation
        second = parse_reference_csv(
            self.v2_text,
            exchange=CboeExchangeCode.C1,
            reference_category="all_series",
            source_url=REFERENCE_URL,
            retrieved_time=RETRIEVED_TIME,
            ingested_time="2026-08-20T08:00:00-05:00",
        ).observation
        self.assertEqual(first.source_url, second.source_url)
        self.assertNotEqual(first.content_hash, second.content_hash)
        self.assertNotEqual(first.available_time, second.available_time)


if __name__ == "__main__":
    unittest.main()

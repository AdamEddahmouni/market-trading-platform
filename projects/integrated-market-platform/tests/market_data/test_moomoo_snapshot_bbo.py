"""Runtime SNAPSHOT_BBO assessment (Item 7 upstream).

SOFTWARE/CONTROLLED — synthetic vendor snapshot rows only.
"""

from __future__ import annotations

import unittest

from market_platform_foundation.market_data.moomoo_snapshot_bbo import (
    BboClocks,
    MOOMOO_OPEND_PROVIDER_ID,
    OUTCOME_DERIVED_BBO_DESIGN_REQUIRED,
    OUTCOME_REAL_SNAPSHOT_BBO_VALIDATED,
    SNAPSHOT_BBO_CAPABILITY,
    assess_snapshot_bbo,
)


def _row(**overrides: object) -> dict:
    base = {
        "code": "US.AAPL",
        "last_price": 187.63,
        "bid_price": 187.60,
        "ask_price": 187.65,
        "bid_vol": 100,
        "ask_vol": 200,
        "sec_status": "NORMAL",
    }
    base.update(overrides)
    return base


def _clocks() -> BboClocks:
    return BboClocks(
        request_time_ns=1_000_000_000,
        provider_time_ns=1_100_000_000,
        receive_time_ns=1_200_000_000,
        available_time_ns=1_300_000_000,
    )


class MoomooSnapshotBboTests(unittest.TestCase):
    def test_identity_distinct_from_l1(self) -> None:
        diag = assess_snapshot_bbo(_row(), clocks=_clocks())
        self.assertEqual(diag.capability, SNAPSHOT_BBO_CAPABILITY)
        self.assertEqual(diag.identity, f"{MOOMOO_OPEND_PROVIDER_ID}:{SNAPSHOT_BBO_CAPABILITY}")

    def test_valid_bbo_outcome(self) -> None:
        diag = assess_snapshot_bbo(_row(), clocks=_clocks())
        self.assertEqual(diag.lane_outcome, OUTCOME_REAL_SNAPSHOT_BBO_VALIDATED)
        self.assertIn("BBO_VALID", diag.quality_flags)

    def test_missing_bid_ask_derived_design(self) -> None:
        diag = assess_snapshot_bbo(_row(bid_price=None, ask_price=None), clocks=_clocks())
        self.assertEqual(diag.lane_outcome, OUTCOME_DERIVED_BBO_DESIGN_REQUIRED)


if __name__ == "__main__":
    unittest.main()

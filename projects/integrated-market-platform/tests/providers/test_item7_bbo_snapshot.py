"""Item 7 Lane C — vendor ``get_market_snapshot`` BBO diagnostic (fixture-first)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

_ITEM7_PATH = _ROOT / "tools" / "moomoo" / "item7_bbo_snapshot.py"
_spec = importlib.util.spec_from_file_location("imp_item7_bbo_snapshot_tests", _ITEM7_PATH)
assert _spec is not None and _spec.loader is not None
_item7 = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _item7
_spec.loader.exec_module(_item7)

BboClocks = _item7.BboClocks
MOOMOO_OPEND_PROVIDER_ID = _item7.MOOMOO_OPEND_PROVIDER_ID
OUTCOME_DERIVED = _item7.OUTCOME_DERIVED_BBO_DESIGN_REQUIRED
OUTCOME_REAL = _item7.OUTCOME_REAL_SNAPSHOT_BBO_VALIDATED
SNAPSHOT_BBO_CAPABILITY = _item7.SNAPSHOT_BBO_CAPABILITY
assess_snapshot_bbo = _item7.assess_snapshot_bbo
blocked_diagnostic = _item7.blocked_diagnostic
is_us_equity_rth = _item7.is_us_equity_rth
run_live_probe = _item7.run_live_probe
VendorSnapshotFetch = _item7.VendorSnapshotFetch

_ET = ZoneInfo("America/New_York")


def _row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "code": "US.AAPL",
        "last_price": 187.63,
        "update_time": "2026-09-12 15:59:00.000",
        "bid_price": 187.60,
        "ask_price": 187.65,
        "bid_vol": 100,
        "ask_vol": 200,
        "sec_status": "NORMAL",
    }
    base.update(overrides)
    return base


def _clocks(
    *,
    request: int = 1_000_000_000,
    provider: int = 1_100_000_000,
    receive: int = 1_200_000_000,
    available: int = 1_300_000_000,
) -> BboClocks:
    return BboClocks(
        request_time_ns=request,
        provider_time_ns=provider,
        receive_time_ns=receive,
        available_time_ns=available,
    )


class Item7BboSnapshotTests(unittest.TestCase):
    def test_identity_is_distinct_from_us_equity_l1(self) -> None:
        diag = assess_snapshot_bbo(_row(), clocks=_clocks())
        self.assertEqual(diag.provider_id, MOOMOO_OPEND_PROVIDER_ID)
        self.assertEqual(diag.capability, SNAPSHOT_BBO_CAPABILITY)
        self.assertNotEqual(diag.capability, "US_EQUITY_L1")
        self.assertEqual(diag.identity, f"{MOOMOO_OPEND_PROVIDER_ID}:{SNAPSHOT_BBO_CAPABILITY}")

    def test_valid_bbo_real_snapshot_outcome(self) -> None:
        diag = assess_snapshot_bbo(_row(), clocks=_clocks())
        self.assertIn("BBO_VALID", diag.quality_flags)
        self.assertEqual(diag.lane_outcome, OUTCOME_REAL)
        self.assertIsNone(diag.derived_design_note)
        self.assertNotIn("ITEM7_COMPLETE", diag.to_dict().values())

    def test_missing_bid_ask_derived_design(self) -> None:
        diag = assess_snapshot_bbo(_row(bid_price=None, ask_price=None), clocks=_clocks())
        self.assertIn("BBO_MISSING_BID_ASK", diag.quality_flags)
        self.assertEqual(diag.lane_outcome, OUTCOME_DERIVED)
        self.assertIsNotNone(diag.derived_design_note)
        self.assertIsNone(diag.bid_price)
        self.assertIsNone(diag.ask_price)

    def test_invalid_spread_derived_design(self) -> None:
        diag = assess_snapshot_bbo(_row(bid_price=188.0, ask_price=187.0), clocks=_clocks())
        self.assertIn("BBO_INVALID_SPREAD", diag.quality_flags)
        self.assertEqual(diag.lane_outcome, OUTCOME_DERIVED)

    def test_stale_snapshot_not_validated(self) -> None:
        clocks = _clocks(request=0, provider=0, receive=500_000_000_000, available=500_000_000_000)
        diag = assess_snapshot_bbo(_row(), clocks=clocks, stale_threshold_ns=1_000_000_000)
        self.assertIn("BBO_STALE", diag.quality_flags)
        self.assertNotIn("BBO_VALID", diag.quality_flags)
        self.assertEqual(diag.lane_outcome, OUTCOME_DERIVED)

    def test_delayed_sec_status(self) -> None:
        diag = assess_snapshot_bbo(_row(sec_status="DELAYED_QUOTE"), clocks=_clocks())
        self.assertIn("BBO_DELAYED", diag.quality_flags)
        self.assertEqual(diag.lane_outcome, OUTCOME_DERIVED)

    def test_temporal_order_violation(self) -> None:
        clocks = _clocks(request=5_000, provider=4_000, receive=3_000, available=2_000)
        diag = assess_snapshot_bbo(_row(), clocks=clocks)
        self.assertIn("TEMPORAL_ORDER_VIOLATION", diag.quality_flags)
        self.assertFalse(diag.temporal_order_valid)

    def test_entitlement_failure_live_probe_blocked(self) -> None:
        def _fail_fetch(*_a: Any, **_k: Any) -> VendorSnapshotFetch:
            return VendorSnapshotFetch("MOOMOO_AUTH_FAILURE", None)

        diag = run_live_probe(
            require_rth=False,
            fetcher=_fail_fetch,
        )
        self.assertEqual(diag.probe_status, "BLOCKED")
        self.assertEqual(diag.block_reason, "MOOMOO_AUTH_FAILURE")
        self.assertIn("ENTITLEMENT_FAILURE", diag.quality_flags)
        self.assertEqual(diag.lane_outcome, "")

    def test_opend_down_honest_block(self) -> None:
        diag = run_live_probe(host="127.0.0.1", port=19, require_rth=False)
        self.assertEqual(diag.probe_status, "BLOCKED")
        self.assertEqual(diag.block_reason, "OPEND_UNAVAILABLE")

    def test_rth_gate_blocks_outside_session(self) -> None:
        wednesday_noon = datetime(2026, 9, 16, 12, 0, tzinfo=_ET)
        self.assertTrue(is_us_equity_rth(wednesday_noon))
        sunday = datetime(2026, 9, 13, 12, 0, tzinfo=_ET)
        self.assertFalse(is_us_equity_rth(sunday))
        diag = run_live_probe(require_rth=True, fetcher=lambda *_a, **_k: VendorSnapshotFetch(None, _row()))
        if not is_us_equity_rth():
            self.assertEqual(diag.probe_status, "BLOCKED")
            self.assertEqual(diag.block_reason, "OUTSIDE_US_EQUITY_RTH")

    def test_blocked_diagnostic_has_raw_hash_only_when_row_present(self) -> None:
        diag = assess_snapshot_bbo(_row(), clocks=_clocks())
        self.assertIsNotNone(diag.raw_hash)
        self.assertEqual(len(diag.raw_hash or ""), 64)

    def test_never_labels_item7_complete(self) -> None:
        for case in (
            assess_snapshot_bbo(_row(), clocks=_clocks()),
            assess_snapshot_bbo(_row(bid_price=None), clocks=_clocks()),
            blocked_diagnostic(symbol="US.AAPL", block_reason="OPEND_UNAVAILABLE"),
        ):
            blob = str(case.to_dict())
            self.assertNotIn("ITEM7_COMPLETE", blob)


if __name__ == "__main__":
    unittest.main()

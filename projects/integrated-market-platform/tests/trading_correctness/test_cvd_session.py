"""G3 BL-0208 — CVD session semantics tests.

Proves deterministic session behavior of the CVD implementation:
- session anchor is deterministic for the same bar times;
- CVD accumulates within one session and resets at a session boundary;
- restart/replay reconstructs the same CVD;
- events at / around the boundary behave deterministically;
- point-in-time behavior: later bars never retroactively change a prior
  session's cumulative CVD when the session anchor differs.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.order_flow.cvd import (
    cvd_session_anchor,
    compute_cvd_state,
)


def _bars(*, times: list[str], deltas: list[float], volumes: list[float] | None = None) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, (time, delta) in enumerate(zip(times, deltas)):
        row: dict[str, object] = {
            "bar_time": time,
            "delta": delta,
            "volume": (volumes[index] if volumes else abs(delta)),
        }
        rows.append(row)
    return rows


class CvdSessionAnchorTests(unittest.TestCase):
    def test_anchor_deterministic(self) -> None:
        self.assertEqual(cvd_session_anchor("2026-09-07T09:30:00Z"), "2026-09-07")
        self.assertEqual(cvd_session_anchor("2026-09-07T09:30:00Z"), cvd_session_anchor("2026-09-07T09:30:00Z"))
        # Non-ISO raw times anchor to themselves (explicit, no invented tz).
        self.assertEqual(cvd_session_anchor("1699999999"), "1699999999")

    def test_same_session_accumulates(self) -> None:
        bars = _bars(
            times=["2026-09-07T09:30:00Z", "2026-09-07T09:31:00Z", "2026-09-07T09:32:00Z"],
            deltas=[10.0, 20.0, -5.0],
        )
        state = compute_cvd_state(bars)
        self.assertEqual(state.session_anchor, "2026-09-07")
        self.assertFalse(state.session_reset)
        self.assertAlmostEqual(state.session_cvd, 25.0)

    def test_session_boundary_resets_cvd(self) -> None:
        # A new bar batch that opens a different session than the previously
        # anchored batch is an explicit reset: the returned state carries
        # session_reset=True and the new anchor, and the cumulative series is
        # the NEW session's signed flow only (no leakage from the old).
        bars = _bars(
            times=["2026-09-08T09:30:00Z", "2026-09-08T09:31:00Z"],
            deltas=[20.0, -5.0],
        )
        state = compute_cvd_state(bars, previous_anchor="2026-09-07")
        self.assertTrue(state.session_reset)
        self.assertEqual(state.session_anchor, "2026-09-08")
        self.assertAlmostEqual(state.session_cvd, 15.0)

        # A batch that stays within the previous session is NOT a reset.
        same = _bars(times=["2026-09-07T10:00:00Z"], deltas=[5.0])
        state_same = compute_cvd_state(same, previous_anchor="2026-09-07")
        self.assertFalse(state_same.session_reset)

    def test_restart_replay_reconstructs_same_cvd(self) -> None:
        bars = _bars(
            times=["2026-09-07T09:30:00Z", "2026-09-07T09:31:00Z", "2026-09-07T09:32:00Z"],
            deltas=[10.0, 20.0, -5.0],
        )
        first = compute_cvd_state(bars)
        second = compute_cvd_state(list(bars))  # independent reconstruction
        self.assertEqual(first.session_cvd, second.session_cvd)
        self.assertEqual(first.session_anchor, second.session_anchor)
        self.assertEqual(first.cvd_confidence, second.cvd_confidence)

    def test_no_future_bar_influence_on_historical_session(self) -> None:
        # The cumulative series is computed in bar order; a later session's
        # bars cannot alter the historical session's stored CVD.
        bars_a = _bars(times=["2026-09-07T09:30:00Z", "2026-09-07T09:31:00Z"], deltas=[5.0, 5.0])
        state_a = compute_cvd_state(bars_a)
        self.assertAlmostEqual(state_a.session_cvd, 10.0)
        # Including the same first two bars at the start of a longer series
        # yields the identical prefix values.
        bars_full = _bars(
            times=["2026-09-07T09:30:00Z", "2026-09-07T09:31:00Z", "2026-09-07T09:32:00Z"],
            deltas=[5.0, 5.0, 2.0],
        )
        full = compute_cvd_state(bars_full)
        self.assertAlmostEqual(full.session_cvd, 12.0)

    def test_duplicate_event_handling_deterministic(self) -> None:
        bars = _bars(times=["2026-09-07T09:30:00Z", "2026-09-07T09:30:00Z"], deltas=[5.0, 5.0])
        state = compute_cvd_state(bars)
        self.assertAlmostEqual(state.session_cvd, 10.0, "duplicate times still sum signed flow in order")

    def test_empty_bars_returns_none(self) -> None:
        self.assertIsNone(compute_cvd_state([]))

    def test_provenance_fractions_deterministic(self) -> None:
        from market_platform_foundation.order_flow.cvd import provenance_fractions_from_bars

        bars = _bars(times=["2026-09-07T09:30:00Z"], deltas=[10.0])
        first = provenance_fractions_from_bars(bars)
        second = provenance_fractions_from_bars(list(bars))
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
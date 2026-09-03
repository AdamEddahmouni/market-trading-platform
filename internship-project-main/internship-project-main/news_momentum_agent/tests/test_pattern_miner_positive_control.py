"""Positive-control test: miner + OOS gate must detect a planted edge.

If this fails, real-data "0 survivors" results cannot be trusted — fix the miner
before interpreting market findings. Does not touch live decision code.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path
from typing import Any, Dict, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.pattern_miner import (  # noqa: E402
    DEFAULT_MIN_N,
    DISCOVERY_FRAC,
    chronological_split,
    run_pattern_pipeline,
)

PANEL_PATH = PROJECT_ROOT / "state" / "learning" / "research_panel_spy_qqq.json"
PLANTED_FEATURE = "would_be_side"
PLANTED_VALUE = "put"
TARGET_WIN_RATE = 0.80


def _stable_unit(key: str) -> float:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _dates_spanning_chrono_split(n_days: int = 100) -> List[str]:
    """Return ISO dates that chronological_split(0.7) will divide into both halves."""
    # Weekdays-ish calendar covering Jan–Jun 2026 so discovery/validation both nonempty.
    days: List[str] = []
    for month, count in ((1, 20), (2, 20), (3, 20), (4, 20), (5, 20)):
        for d in range(1, count + 1):
            days.append(f"2026-{month:02d}-{d:02d}")
            if len(days) >= n_days:
                return days
    return days


def build_synthetic_base_panel(*, n_days: int = 100) -> List[Dict[str, Any]]:
    """Balanced call/put panel with ~45% base win rate and no planted edge."""
    rows: List[Dict[str, Any]] = []
    for i, day in enumerate(_dates_spanning_chrono_split(n_days)):
        for side in ("call", "put"):
            # Mild, non-edge win process (~45%) identical for both sides.
            win = _stable_unit(f"base:{day}:{side}") < 0.45
            rows.append(
                {
                    "id": f"synth:{day}:{side}",
                    "ticker": "SPY" if side == "call" else "QQQ",
                    "session_date": day,
                    "timestamp": f"{day}T20:00:00+00:00",
                    "outcome": "win" if win else "loss",
                    "would_be_side": side,
                    "options_bias": "bullish" if side == "call" else "bearish",
                    "lean": "WAIT",
                    "decision": "LOG",
                    "confidence_pct": 40.0,
                    "options_score": 50.0,
                    "lean_pct": 55.0,
                    "n_dir": 1,
                    "source_kind": "backtest_replay",
                    "signal_source": "expiry",
                    "pnl_pct": 0.40 if win else -0.30,
                }
            )
    return rows


def inject_planted_edge(
    rows: Sequence[Dict[str, Any]],
    *,
    feature: str = PLANTED_FEATURE,
    value: str = PLANTED_VALUE,
    target_win_rate: float = TARGET_WIN_RATE,
) -> List[Dict[str, Any]]:
    """Copy panel and force ``feature=value`` rows to ``target_win_rate`` wins.

    Assignment is deterministic and applied uniformly across all dates so both
    chronological halves receive the planted effect.
    """
    out = [copy.deepcopy(r) for r in rows]
    targets = [
        r
        for r in out
        if str(r.get(feature) or "").lower() == str(value).lower()
        and str(r.get("outcome") or "").lower() in {"win", "loss", "unknown", "flat", ""}
    ]
    # Force win/loss labels on the planted cohort.
    for r in targets:
        key = str(r.get("id") or f"{r.get('session_date')}:{r.get('ticker')}:{feature}")
        r["outcome"] = "win" if _stable_unit(f"plant:{key}") < float(target_win_rate) else "loss"
        r["pnl_pct"] = 0.40 if r["outcome"] == "win" else -0.30
        r["_positive_control_planted"] = True
    return out


def _find_survivor(result: Dict[str, Any], feature: str, value: str) -> Dict[str, Any] | None:
    for pat in result.get("survivors") or []:
        if pat.get("feature") == feature and str(pat.get("value")) == str(value):
            return pat
    return None


def _find_discovery(result: Dict[str, Any], feature: str, value: str) -> Dict[str, Any] | None:
    for pat in result.get("discovery_patterns_passing_n") or []:
        if pat.get("feature") == feature and str(pat.get("value")) == str(value):
            return pat
    return None


class PositiveControlMinerTests(unittest.TestCase):
    def test_planted_put_edge_discovered_and_survives_oos(self) -> None:
        base = build_synthetic_base_panel(n_days=100)
        planted = inject_planted_edge(base)

        # Sanity: planted cohort has high win rate in BOTH chrono halves.
        disc, val, disc_days, val_days = chronological_split(planted, discovery_frac=DISCOVERY_FRAC)
        self.assertTrue(disc_days and val_days)
        self.assertLess(max(disc_days), min(val_days))

        def _put_rate(rows: Sequence[Dict[str, Any]]) -> float:
            puts = [
                r
                for r in rows
                if str(r.get("would_be_side")) == "put"
                and str(r.get("outcome")).lower() in {"win", "loss"}
            ]
            self.assertGreaterEqual(len(puts), DEFAULT_MIN_N // 2)
            return sum(1 for r in puts if r["outcome"] == "win") / len(puts)

        disc_rate = _put_rate(disc)
        val_rate = _put_rate(val)
        self.assertGreaterEqual(disc_rate, 0.70, f"discovery put win_rate too low: {disc_rate}")
        self.assertGreaterEqual(val_rate, 0.70, f"validation put win_rate too low: {val_rate}")

        # Same miner / OOS gate as production research pipeline.
        result = run_pattern_pipeline(planted, min_n=DEFAULT_MIN_N, discovery_frac=DISCOVERY_FRAC)

        discovered = _find_discovery(result, PLANTED_FEATURE, PLANTED_VALUE)
        self.assertIsNotNone(
            discovered,
            msg=(
                "Planted put edge missing from discovery candidates. "
                f"patterns={[ (p.get('feature'), p.get('value'), p.get('lift')) for p in (result.get('discovery_patterns_passing_n') or []) ]}"
            ),
        )
        assert discovered is not None
        self.assertGreaterEqual(discovered["n"], DEFAULT_MIN_N)
        self.assertGreaterEqual(float(discovered["lift"] or 0), 1.08)
        self.assertEqual(discovered["kind"], "favorable")

        survivor = _find_survivor(result, PLANTED_FEATURE, PLANTED_VALUE)
        self.assertIsNotNone(
            survivor,
            msg=(
                "Planted put edge failed OOS validation — miner/gate bug likely. "
                f"failed={[ (f.get('feature'), f.get('value'), f.get('fail_reason')) for f in (result.get('found_but_did_not_replicate') or []) ]}"
            ),
        )
        assert survivor is not None
        val = survivor.get("validation") or {}
        self.assertGreaterEqual(float(val.get("lift") or 0), 1.0)
        self.assertEqual(survivor.get("status"), "survived_oos")

    def test_real_panel_copy_injection_survives_when_available(self) -> None:
        """If a real research panel exists, plant on a copy (never mutate disk)."""
        if not PANEL_PATH.exists():
            self.skipTest(f"No research panel at {PANEL_PATH}")

        payload = json.loads(PANEL_PATH.read_text(encoding="utf-8"))
        raw_rows = list(payload.get("rows") or [])
        if len(raw_rows) < 60:
            self.skipTest("Research panel too small for positive-control injection")

        # Work only on win/loss + force outcomes on put cohort via injection helper.
        wl = [r for r in raw_rows if str(r.get("outcome") or "").lower() in {"win", "loss"}]
        if len(wl) < 80:
            # Fall back to all rows; injector will assign win/loss on puts.
            wl = raw_rows

        planted = inject_planted_edge(wl)
        # Ensure put N is adequate in both halves after injection.
        disc, val, _, _ = chronological_split(planted, discovery_frac=DISCOVERY_FRAC)
        put_disc = sum(1 for r in disc if str(r.get("would_be_side")) == "put" and r.get("outcome") in {"win", "loss"})
        put_val = sum(1 for r in val if str(r.get("would_be_side")) == "put" and r.get("outcome") in {"win", "loss"})
        if put_disc < DEFAULT_MIN_N or put_val < max(15, DEFAULT_MIN_N // 2):
            self.skipTest(
                f"Real panel put counts too thin after split (disc={put_disc}, val={put_val}); "
                "synthetic test remains authoritative"
            )

        result = run_pattern_pipeline(planted, min_n=DEFAULT_MIN_N, discovery_frac=DISCOVERY_FRAC)
        discovered = _find_discovery(result, PLANTED_FEATURE, PLANTED_VALUE)
        survivor = _find_survivor(result, PLANTED_FEATURE, PLANTED_VALUE)
        self.assertIsNotNone(discovered, "Real-panel copy: planted put not discovered")
        self.assertIsNotNone(
            survivor,
            msg=(
                "Real-panel copy: planted put failed OOS. "
                f"failed={[ (f.get('feature'), f.get('value'), f.get('fail_reason')) for f in (result.get('found_but_did_not_replicate') or []) ]}"
            ),
        )


if __name__ == "__main__":
    unittest.main()

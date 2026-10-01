"""S3 Quick Preview: current bars, AUTO_SR_V1, Why, contextual futures, preview API."""

from __future__ import annotations

import json
import math
import random
import re
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.features.auto_support_resistance import (
    METHOD, MIN_BARS, MIN_REJECTION_ATR, MIN_STRENGTH, PIVOT_SPAN, Structure, Zone, build_structure, classify,
    confirmed_pivots,
)
from market_platform_foundation.finviz.screener import FinvizScreenerRow
from market_platform_foundation.market_data.current_bars import (
    MINUTE_NS, Bar, BarSeries, CurrentBarsService, aggregate, freshness, normalize_vendor_1m, scope_filter,
)
from market_platform_foundation.platform.security.route_policy import policy_for_route
from market_platform_foundation.ui_api.screener_config import (
    DEFAULT_PREVIEW, ScreenerConfigRepository, validate_preview_layout,
)
from market_platform_foundation.ui_api.screener_filters import apply_filters, builtin_presets, validate_filters
from market_platform_foundation.ui_api.screener_futures_context import (
    FuturesContextService, related_futures, resolve_contract,
)
from market_platform_foundation.ui_api.screener_preview import (
    ScreenerPreviewService, explain_matches, explain_movement, move_window_start,
)
from market_platform_foundation.ui_api.screener_projections import ScreenerService

ET = ZoneInfo("America/New_York")
CAUSAL = re.compile(r"\b(caused|causing|drove|driving|driven|due to|because|triggered|squeeze is)\b", re.I)


def ns(year, month, day, hour, minute) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=ET).timestamp()) * 1_000_000_000


# Friday 2026-09-25, regular session.
T0 = ns(2026, 9, 25, 10, 0)


def bars_from_closes(closes, *, start=T0, minutes=5, spread=0.05, volume=1000.0):
    result, previous = [], closes[0]
    for index, close in enumerate(closes):
        begin = start + index * minutes * MINUTE_NS
        high, low = max(previous, close) + spread, min(previous, close) - spread
        result.append(Bar(begin, begin + minutes * MINUTE_NS, previous, high, low, close, volume, "REGULAR"))
        previous = close
    return result


def oscillation(cycles=6, low=10.0, high=11.0, steps=8):
    closes = []
    for _ in range(cycles):
        closes += [low + (high - low) * i / steps for i in range(steps)]
        closes += [high - (high - low) * i / steps for i in range(steps)]
    return closes


def vendor_row(end: datetime, o, h, l, c, v=100.0):
    return {"time_key": end.strftime("%Y-%m-%d %H:%M:%S"), "open": o, "high": h, "low": l, "close": c, "volume": v}


class AutoSupportResistanceTests(unittest.TestCase):
    def test_normal_support_and_resistance_detection(self):
        structure = build_structure(bars_from_closes(oscillation()))
        self.assertIsNone(structure.reason)
        result = classify(structure, 10.5)
        self.assertEqual(result["state"], "AVAILABLE")
        self.assertLess(result["support"]["upper"], 10.5)
        self.assertAlmostEqual(result["support"]["center"], 9.95, delta=0.15)
        self.assertGreater(result["resistance"]["lower"], 10.5)
        self.assertAlmostEqual(result["resistance"]["center"], 11.05, delta=0.15)
        self.assertGreaterEqual(result["support"]["touches"], 3)

    def test_only_support_and_only_resistance(self):
        structure = build_structure(bars_from_closes(oscillation()))
        above = classify(structure, 13.0)
        self.assertIsNotNone(above["support"])
        self.assertIsNone(above["resistance"])
        self.assertEqual(above["reasons"], ["NO_RESISTANCE_ZONE"])
        below = classify(structure, 8.0)
        self.assertIsNone(below["support"])
        self.assertIsNotNone(below["resistance"])
        self.assertEqual(below["reasons"], ["NO_SUPPORT_ZONE"])

    def test_no_valid_zones_on_monotonic_series(self):
        structure = build_structure(bars_from_closes([10 + i * 0.1 for i in range(40)], spread=0.01))
        self.assertIsNone(structure.reason)
        self.assertEqual(structure.zones, ())
        result = classify(structure, 20.0)
        self.assertEqual(result["state"], "NO_ZONES")
        self.assertEqual(result["reasons"], ["NO_SUPPORT_ZONE", "NO_RESISTANCE_ZONE"])

    def test_insufficient_and_malformed_bars(self):
        self.assertEqual(build_structure(bars_from_closes(oscillation()[:MIN_BARS - 1])).reason, "INSUFFICIENT_BARS")
        bars = bars_from_closes(oscillation())
        bad = list(bars)
        bad[5] = Bar(bad[5].start_ns, bad[5].end_ns, 10, 9, 11, 10, 1, "REGULAR")
        self.assertEqual(build_structure(bad).reason, "MALFORMED_BARS")
        self.assertEqual(build_structure([bars[1], bars[0], *bars[2:]]).reason, "MALFORMED_BARS")
        nan = list(bars)
        nan[3] = Bar(nan[3].start_ns, nan[3].end_ns, math.nan, 11, 9, 10, 1, "REGULAR")
        self.assertEqual(build_structure(nan).reason, "MALFORMED_BARS")
        self.assertEqual(classify(build_structure(bad), 10)["reason"], "MALFORMED_BARS")

    def test_invalid_price_is_explicit(self):
        structure = build_structure(bars_from_closes(oscillation()))
        for price in (None, 0, -1, math.inf, math.nan):
            self.assertEqual(classify(structure, price)["reason"], "INVALID_PRICE")

    def test_exact_zone_clustering_and_no_overlap(self):
        # Swing lows at 10.00, 10.01, 10.02 cluster together; a swing low at 12 is separate.
        closes = [11.5, 11, 10.5, 10.0, 10.5, 11, 11.5, 11, 10.5, 10.01, 10.5, 11, 11.5, 11, 10.5, 10.02, 10.5, 11,
                  11.5, 12.5, 13, 12.5, 12.0, 12.5, 13, 13.5, 13, 12.5]
        structure = build_structure(bars_from_closes(closes, spread=0.0))
        lows = [zone for zone in structure.zones if "LOW" in zone.kinds and zone.center < 10.5]
        self.assertEqual(len(lows), 1)
        self.assertEqual(lows[0].touches, 3)
        self.assertLessEqual(lows[0].lower, 10.0)
        self.assertGreaterEqual(lows[0].upper, 10.02)
        ordered = sorted(structure.zones, key=lambda zone: zone.lower)
        for left, right in zip(ordered, ordered[1:]):
            self.assertLessEqual(left.upper, right.lower)

    def test_nearest_zone_selection_and_distance(self):
        structure = Structure(None, 40, 1, 0.1, 0.025, (), tuple(
            Zone(lower, upper, (lower + upper) / 2, 2, strength, 1, ("LOW",))
            for lower, upper, strength in ((5.0, 5.1, 80), (6.08, 6.13, 55), (6.55, 6.6, 61), (7.0, 7.1, 90))))
        result = classify(structure, 6.42)
        self.assertEqual((result["support"]["lower"], result["support"]["upper"]), (6.08, 6.13))
        self.assertEqual((result["resistance"]["lower"], result["resistance"]["upper"]), (6.55, 6.6))
        self.assertAlmostEqual(result["support"]["distance_pct"], (6.42 - 6.13) / 6.42 * 100, places=3)
        self.assertAlmostEqual(result["resistance"]["distance_pct"], (6.55 - 6.42) / 6.42 * 100, places=3)

    def test_shared_classification_cases_match_frontend_fixture(self):
        cases = json.loads((ROOT / "tests" / "fixtures" / "screener" / "auto_sr_classify_cases.json").read_text())
        self.assertEqual(cases["min_strength"], MIN_STRENGTH)
        for case in cases["cases"]:
            zones = tuple(Zone(z["lower"], z["upper"], z["center"], 1, z["strength"], 1, ("LOW",)) for z in case["zones"])
            result = classify(Structure(None, 30, 1, 1.0, 0.1, (), zones), case["price"])
            for side in ("support", "resistance", "testing"):
                expected = case[f"{side}_center"]
                self.assertEqual(result[side]["center"] if result[side] else None, expected, case["name"])
            for side in ("support", "resistance"):
                expected = case[f"{side}_distance_pct"]
                observed = result[side]["distance_pct"] if result[side] else None
                if expected is None:
                    self.assertIsNone(observed)
                else:
                    self.assertAlmostEqual(observed, expected, places=3, msg=case["name"])

    def test_strength_is_deterministic_bounded_and_filters_weak_zones(self):
        bars = bars_from_closes(oscillation())
        first, second = build_structure(bars), build_structure(list(bars))
        self.assertEqual(first, second)
        self.assertTrue(all(0 <= zone.strength <= 100 for zone in first.zones))
        weak = Structure(None, 30, 1, 1.0, 0.1, (), (Zone(9, 9.1, 9.05, 1, MIN_STRENGTH - 1, 1, ("LOW",)),))
        self.assertIsNone(classify(weak, 10)["support"])

    def test_volume_absence_contributes_zero_not_fabricated(self):
        with_volume = build_structure(bars_from_closes(oscillation()))
        without = build_structure(bars_from_closes(oscillation(), volume=None))
        self.assertTrue(all(a.strength >= b.strength for a, b in zip(with_volume.zones, without.zones)))

    def test_no_lookahead_pivot_waits_for_confirming_bars(self):
        closes = [10, 10.2, 10.4, 10.6, 11.0, 10.7, 10.5, 10.3] + [10.3 - 0.01 * i for i in range(20)]
        bars = bars_from_closes(closes, spread=0.0)
        peak = 4
        before = confirmed_pivots(bars[:peak + PIVOT_SPAN])  # one confirming bar short
        self.assertFalse(any(p.index == peak and p.kind == "HIGH" for p in before))
        after = confirmed_pivots(bars[:peak + PIVOT_SPAN + 1])
        pivot = next(p for p in after if p.index == peak and p.kind == "HIGH")
        self.assertEqual(pivot.confirmed_end_ns, bars[peak + PIVOT_SPAN].end_ns)
        self.assertEqual(pivot.price, bars[peak].high)
        # A later bar that would have made the peak a non-pivot cannot exist before confirmation.
        self.assertEqual(confirmed_pivots(bars[:peak + PIVOT_SPAN + 1]),
                         [p for p in confirmed_pivots(bars) if p.confirmed_end_ns <= bars[peak + PIVOT_SPAN].end_ns])

    def test_quiet_extended_tail_does_not_collapse_tolerance(self):
        regular = bars_from_closes(oscillation(), spread=0.05)
        start = regular[-1].end_ns
        quiet = [Bar(start + i * 5 * MINUTE_NS, start + (i + 1) * 5 * MINUTE_NS, 10.5, 10.501, 10.499, 10.5, 10.0, "AFTER_HOURS")
                 for i in range(60)]
        structure = build_structure(regular + quiet)
        self.assertEqual(structure.volatility_basis, "REGULAR_MEAN_TRUE_RANGE")
        self.assertGreater(structure.tolerance, 0.05)
        wilder_only = build_structure([Bar(b.start_ns, b.end_ns, b.open, b.high, b.low, b.close, b.volume, "AFTER_HOURS") for b in regular + quiet])
        self.assertEqual(wilder_only.volatility_basis, "WILDER_ATR_14")
        self.assertLess(wilder_only.tolerance, structure.tolerance)

    def test_insignificant_pivots_are_filtered(self):
        closes = oscillation() + [10.5, 10.52, 10.51, 10.5, 10.49, 10.5, 10.51, 10.5]
        structure = build_structure(bars_from_closes(closes, spread=0.0))
        self.assertTrue(all(p.rejection >= MIN_REJECTION_ATR * structure.atr for p in structure.pivots))
        self.assertLess(len(structure.pivots), len(confirmed_pivots(bars_from_closes(closes, spread=0.0))))

    def test_no_lookahead_every_prefix_is_point_in_time(self):
        rng = random.Random(7)
        closes, price = [], 20.0
        for _ in range(160):
            price = max(1.0, price + rng.uniform(-0.3, 0.3))
            closes.append(round(price, 2))
        bars = bars_from_closes(closes, spread=0.04)
        full = confirmed_pivots(bars)
        for cut in range(MIN_BARS, len(bars) + 1):
            prefix_end = bars[cut - 1].end_ns
            prefix = confirmed_pivots(bars[:cut])
            self.assertEqual(prefix, [p for p in full if p.confirmed_end_ns <= prefix_end])
            self.assertTrue(all(p.confirmed_end_ns <= prefix_end for p in prefix))
            structure = build_structure(bars[:cut])
            self.assertEqual(structure.latest_bar_end_ns, prefix_end)


class CurrentBarsTests(unittest.TestCase):
    def test_vendor_time_key_is_bar_end_and_forming_bar_is_separate(self):
        as_of = datetime(2026, 9, 25, 10, 2, 30, tzinfo=ET)
        rows = [vendor_row(datetime(2026, 9, 25, 10, m, tzinfo=ET), 10, 10.2, 9.9, 10.1) for m in (1, 2, 3)]
        complete, forming, rejected = normalize_vendor_1m(rows, as_of_ns=int(as_of.timestamp() * 1e9))
        self.assertEqual([bar.end_ns for bar in complete], [ns(2026, 9, 25, 10, 1), ns(2026, 9, 25, 10, 2)])
        self.assertEqual(complete[0].start_ns, ns(2026, 9, 25, 10, 0))
        self.assertEqual(forming.end_ns, ns(2026, 9, 25, 10, 3))
        self.assertEqual(rejected, 0)

    def test_malformed_overnight_future_and_duplicate_rows(self):
        as_of = ns(2026, 9, 25, 12, 0)
        good = datetime(2026, 9, 25, 11, 0, tzinfo=ET)
        rows = [
            vendor_row(good, 10, 10.2, 9.9, 10.1),
            vendor_row(good, 10, 10.3, 9.9, 10.2),  # duplicate end: last wins
            vendor_row(datetime(2026, 9, 25, 11, 1, tzinfo=ET), 10, 9.0, 9.5, 9.2),  # high < low
            vendor_row(datetime(2026, 9, 25, 11, 2, tzinfo=ET), "x", 10, 9, 9.5),
            vendor_row(datetime(2026, 9, 25, 11, 3, tzinfo=ET), 10, 10, 10, 10, -5),
            vendor_row(datetime(2026, 9, 25, 2, 0, tzinfo=ET), 10, 10, 10, 10),  # overnight
            vendor_row(datetime(2026, 9, 25, 13, 0, tzinfo=ET), 10, 10, 10, 10),  # future
            {"time_key": "garbage", "open": 1, "high": 1, "low": 1, "close": 1},
        ]
        complete, forming, rejected = normalize_vendor_1m(rows, as_of_ns=as_of)
        self.assertEqual(len(complete), 1)
        self.assertEqual(complete[0].high, 10.3)
        self.assertIsNone(forming)
        self.assertEqual(rejected, 6)

    def test_session_classification_and_ordering(self):
        rows = [vendor_row(datetime(2026, 9, 25, 16, 1, tzinfo=ET), 1, 1, 1, 1),
                vendor_row(datetime(2026, 9, 25, 9, 31, tzinfo=ET), 1, 1, 1, 1),
                vendor_row(datetime(2026, 9, 25, 9, 30, tzinfo=ET), 1, 1, 1, 1)]
        complete, _forming, _rejected = normalize_vendor_1m(rows, as_of_ns=ns(2026, 9, 25, 20, 0))
        self.assertEqual([bar.session for bar in complete], ["PREMARKET", "REGULAR", "AFTER_HOURS"])
        self.assertEqual([bar.session for bar in scope_filter(complete, "RTH")], ["REGULAR"])

    def test_aggregation_ohlcv_and_session_boundary(self):
        minutes = [Bar(ns(2026, 9, 25, 9, m) - MINUTE_NS, ns(2026, 9, 25, 9, m), 10 + m / 100, 10.5 + m / 100,
                       9.5 + m / 100, 10.1 + m / 100, 10.0, "PREMARKET" if m <= 30 else "REGULAR")
                   for m in range(26, 36)]
        complete, forming = aggregate(minutes, 5, as_of_ns=ns(2026, 9, 25, 9, 35))
        self.assertIsNone(forming)
        self.assertEqual([(b.session, b.start_ns, b.end_ns) for b in complete], [
            ("PREMARKET", ns(2026, 9, 25, 9, 25), ns(2026, 9, 25, 9, 30)),
            ("REGULAR", ns(2026, 9, 25, 9, 30), ns(2026, 9, 25, 9, 35))])
        first = complete[0]
        self.assertEqual((first.open, first.close, first.volume), (10.26, 10.4, 50.0))
        self.assertAlmostEqual(first.high, 10.8)
        self.assertAlmostEqual(first.low, 9.76)

    def test_incomplete_bucket_is_forming_not_complete(self):
        minutes = bars_from_closes([10, 10.1, 10.2], start=ns(2026, 9, 25, 10, 0), minutes=1)
        complete, forming = aggregate(minutes, 5, as_of_ns=ns(2026, 9, 25, 10, 3))
        self.assertEqual(complete, [])
        self.assertEqual(forming.end_ns, ns(2026, 9, 25, 10, 5))

    def test_freshness_states(self):
        open_now = ns(2026, 9, 25, 11, 0) + 20 * 1_000_000_000
        self.assertEqual(freshness(ns(2026, 9, 25, 10, 59), now_ns=open_now, scope="RTH"), ("CURRENT", None))
        self.assertEqual(freshness(ns(2026, 9, 25, 10, 40), now_ns=open_now, scope="RTH"), ("STALE", "STALE_BAR_SOURCE"))
        sunday = ns(2026, 9, 27, 1, 0)
        self.assertEqual(freshness(ns(2026, 9, 25, 20, 0), now_ns=sunday, scope="EXTENDED"), ("SESSION_CLOSED", None))
        self.assertEqual(freshness(ns(2026, 9, 18, 20, 0), now_ns=sunday, scope="EXTENDED"), ("STALE", "STALE_BAR_SOURCE"))
        premarket = ns(2026, 9, 25, 8, 0)
        self.assertEqual(freshness(ns(2026, 9, 24, 16, 0), now_ns=premarket, scope="RTH"), ("SESSION_CLOSED", None))
        self.assertEqual(freshness(None, now_ns=premarket, scope="RTH"), ("UNAVAILABLE", "INSUFFICIENT_BARS"))


class FakeKline:
    def __init__(self, rows=None, reason=None):
        self.rows, self.reason, self.calls = rows or {}, reason, []

    def fetch_current_kline_1m(self, code):
        self.calls.append(code)
        if self.reason:
            return {"reason_code": self.reason, "rows": None}
        return {"reason_code": None, "rows": self.rows.get(code, [])}


def session_rows(start: datetime, count: int, base=10.0):
    rows = []
    for i in range(count):
        end = start + timedelta(minutes=i + 1)
        close = base + math.sin(i / 3) * 0.5
        rows.append(vendor_row(end, close, close + 0.05, close - 0.05, close, 500 + i))
    return rows


class CurrentBarsServiceTests(unittest.TestCase):
    def make(self, transport, now):
        clock = {"now": now, "mono": 0.0}
        service = CurrentBarsService(transport_factory=lambda: transport, reachable=lambda: True,
                                     now_ns=lambda: clock["now"], monotonic=lambda: clock["mono"])
        return service, clock

    def test_provider_failure_is_unavailable_without_fallback(self):
        service, _ = self.make(FakeKline(reason="MOOMOO_SDK_MISSING"), ns(2026, 9, 25, 11, 0))
        series = service.read("AAPL")
        self.assertEqual((series.state, series.reason, series.provider_reason), ("UNAVAILABLE", "BAR_SOURCE_UNAVAILABLE", "MOOMOO_SDK_MISSING"))
        self.assertEqual(series.bars, ())
        unreachable = CurrentBarsService(transport_factory=lambda: None, reachable=lambda: False, now_ns=lambda: ns(2026, 9, 25, 11, 0))
        self.assertEqual(unreachable.read("AAPL").provider_reason, "OPEND_UNAVAILABLE")

    def test_current_series_timeframes_and_instrument_isolation(self):
        now = ns(2026, 9, 25, 11, 0) + 5 * 1_000_000_000
        rows = {"US.AAPL": session_rows(datetime(2026, 9, 25, 9, 30, tzinfo=ET), 90),
                "US.NVDA": session_rows(datetime(2026, 9, 25, 9, 30, tzinfo=ET), 90, base=100.0)}
        transport = FakeKline(rows)
        service, _ = self.make(transport, now)
        one, five, fifteen = (service.read("AAPL", timeframe=tf) for tf in ("1m", "5m", "15m"))
        self.assertEqual((one.state, len(one.bars), len(five.bars), len(fifteen.bars)), ("CURRENT", 90, 18, 6))
        self.assertEqual(transport.calls, ["US.AAPL"])  # cached 1m reused across timeframes
        nvda = service.read("NVDA")
        self.assertTrue(all(bar.close > 90 for bar in nvda.bars))
        self.assertTrue(all(bar.close < 20 for bar in service.read("AAPL").bars))
        payload = five.to_dict()
        self.assertEqual((payload["provider"], payload["source_id"], payload["timeframe"]), ("MOOMOO_OPEND", "MOOMOO_OPEND_CUR_KLINE_1M", "5m"))
        self.assertEqual(payload["bars"], sorted(payload["bars"], key=lambda bar: bar["end"]))

    def test_stale_series_during_open_session(self):
        now = ns(2026, 9, 25, 14, 0)
        service, _ = self.make(FakeKline({"US.AAPL": session_rows(datetime(2026, 9, 25, 9, 30, tzinfo=ET), 60)}), now)
        self.assertEqual(service.read("AAPL").state, "STALE")

    def test_cache_refreshes_after_ttl(self):
        transport = FakeKline({"US.AAPL": session_rows(datetime(2026, 9, 25, 9, 30, tzinfo=ET), 60)})
        service, clock = self.make(transport, ns(2026, 9, 25, 10, 31))
        service.read("AAPL")
        service.read("AAPL")
        clock["mono"] = 6.0
        service.read("AAPL")
        self.assertEqual(len(transport.calls), 2)

    def test_invalid_timeframe_and_scope(self):
        service, _ = self.make(FakeKline(), ns(2026, 9, 25, 11, 0))
        with self.assertRaises(ValueError):
            service.read("AAPL", timeframe="2m")
        with self.assertRaises(ValueError):
            service.read("AAPL", scope="OVERNIGHT")


# ------------------------------------------------------------ preview fixtures
class Source:
    def fetch_export(self, *, filter_expr, columns):
        return {"success": True, "received_at": "2026-09-25T15:00:00Z", "rows": [
            FinvizScreenerRow(ticker="RGTI", company="Rigetti Computing", sector="Technology", industry="Computer Hardware",
                              price=6.42, change_pct=28.4, volume=18_200_000, rel_volume=5.8, float_shares=7_400_000,
                              short_float_pct=23.1, market_cap=1_500_000_000),
            FinvizScreenerRow(ticker="XOM", company="Exxon Mobil", sector="Energy", industry="Oil & Gas Integrated",
                              price=110.0, change_pct=0.5, volume=9_000_000, rel_volume=0.9, market_cap=450_000_000_000),
        ]}


class Quote(SimpleNamespace):
    pass


class Runtime:
    def __init__(self, quotes):
        self.state = SimpleNamespace(quote_for=lambda symbol: quotes.get(symbol))
        self.lifecycle = SimpleNamespace(connection_state="CONNECTED")


def live_quote(price):
    import time as _time

    now = _time.time_ns()
    return Quote(received_ns=now, available_time_ns=now, quality="PASS", admission="ADMITTED", provider="moomoo",
                 bid_price=price - 0.01, ask_price=price + 0.01, last_price=price, volume=18_300_000)


class StaticBars:
    def __init__(self, series_by_key):
        self.series_by_key, self.reads = series_by_key, []

    def read(self, instrument_id, *, timeframe="5m", scope="EXTENDED"):
        self.reads.append((instrument_id, timeframe, scope))
        return self.series_by_key[(instrument_id, timeframe)]

    def transport(self):
        return None


class StaticFutures:
    def __init__(self, payload=None):
        self.payload = payload or {"schema_version": "x", "items": [], "causal_note": "Context only"}

    def read(self, **_kwargs):
        return self.payload


def series(instrument="RGTI", timeframe="5m", closes=None, state="CURRENT", reason=None, provider_reason=None):
    bars = tuple(bars_from_closes(closes if closes is not None else [6 + v / 2 for v in oscillation(low=0.2, high=1.4)]))
    return BarSeries(instrument, timeframe, "EXTENDED", state, reason, provider_reason, T0, bars if state != "UNAVAILABLE" else (), None)


NEWS = {"success": True, "items": [
    {"headline": "Rigetti announces quantum contract", "tickers": ["RGTI"], "publisher_source": "PR Newswire",
     "raw_fields": {"Date": "2026-09-25 08:15:00"}, "url": "https://example.com/a"},
    {"headline": "Old item", "tickers": ["RGTI"], "raw_fields": {"Date": "2026-09-20 08:15:00"}},
    {"headline": "Future item", "tickers": ["RGTI"], "raw_fields": {"Date": "2026-09-26 08:15:00"}},
    {"headline": "Other ticker", "tickers": ["XOM"], "raw_fields": {"Date": "2026-09-25 09:00:00"}},
]}


def preview_service(*, quotes=None, bars=None, news=None, futures=None, now=ns(2026, 9, 25, 11, 0)):
    screener = ScreenerService(source_factory=Source, runtime_getter=lambda **_: Runtime(quotes or {}))
    return ScreenerPreviewService(screener=screener, bars=bars or StaticBars({("RGTI", "5m"): series(), ("XOM", "5m"): series("XOM"),
                                                                             ("RGTI", "15m"): series(timeframe="15m")}),
                                  futures=futures or StaticFutures(), news=lambda: news if news is not None else NEWS,
                                  now_ns=lambda: now)


class PreviewApiTests(unittest.TestCase):
    def test_preview_route_is_state_read(self):
        self.assertEqual(policy_for_route("GET", "/screener/preview").capability, "state.read")

    def test_identity_quote_bars_key_data_and_clocks(self):
        payload = preview_service(quotes={"RGTI": live_quote(6.5)}).read("RGTI")
        self.assertEqual(payload["schema_version"], "screener-preview/1.0.0")
        self.assertEqual((payload["instrument"]["instrument_id"], payload["instrument"]["company"]), ("RGTI", "Rigetti Computing"))
        self.assertEqual(payload["quote"]["state"], "LIVE")
        self.assertEqual(payload["bars"]["state"], "CURRENT")
        self.assertEqual(payload["levels"]["method"], METHOD)
        self.assertEqual(payload["levels"]["price"]["source"], "L1_QUOTE")
        key = {item["field"]: item for item in payload["key_data"]}
        self.assertEqual((key["price"]["value"], key["price"]["state"]), (6.5, "LIVE"))
        self.assertEqual((key["float_shares"]["value"], key["float_shares"]["state"]), (7_400_000, "SNAPSHOT"))
        self.assertEqual(key["rsi_14"]["state"], "UNAVAILABLE")
        self.assertIsNotNone(payload["levels"]["calculated_at"])
        self.assertIsNotNone(payload["bars"]["received_at"])

    def test_unknown_instrument_and_invalid_filters(self):
        service = preview_service()
        self.assertIsNone(service.read("NOPE"))
        with self.assertRaises(ValueError):
            service.read("RGTI", filters=[{"id": "x", "field": "sh_relvol_o2", "operator": "gt", "value": 2}])

    def test_bar_provider_failure_keeps_other_sections(self):
        bars = StaticBars({("RGTI", "5m"): series(state="UNAVAILABLE", reason="BAR_SOURCE_UNAVAILABLE", provider_reason="OPEND_UNAVAILABLE")})
        payload = preview_service(bars=bars).read("RGTI")
        self.assertEqual(payload["bars"]["bars"], [])
        self.assertEqual((payload["levels"]["state"], payload["levels"]["reason"]), ("UNAVAILABLE", "BAR_SOURCE_UNAVAILABLE"))
        self.assertEqual(payload["levels"]["zones"], [])
        self.assertEqual(payload["quote"]["state"], "UNAVAILABLE")
        self.assertTrue(payload["why"]["moving"]["items"])

    def test_stale_bars_degrade_levels(self):
        bars = StaticBars({("RGTI", "5m"): series(state="STALE", reason="STALE_BAR_SOURCE")})
        levels = preview_service(bars=bars).read("RGTI")["levels"]
        self.assertEqual((levels["state"], levels["reason"], levels["zones"]), ("UNAVAILABLE", "STALE_BAR_SOURCE", []))

    def test_no_quote_uses_labelled_last_bar_close(self):
        levels = preview_service().read("RGTI")["levels"]
        self.assertEqual(levels["price"]["source"], "LAST_BAR_CLOSE")

    def test_preview_module_has_no_fixture_or_replay_source(self):
        for name in ("screener_preview.py", "screener_futures_context.py"):
            text = (ROOT / "src" / "market_platform_foundation" / "ui_api" / name).read_text(encoding="utf-8")
            self.assertNotRegex(text, r"import.*(fixture|replay|calibration)")
        text = (ROOT / "src" / "market_platform_foundation" / "market_data" / "current_bars.py").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"import.*(fixture|replay|calibration)")


class LevelUpdateTests(unittest.TestCase):
    def test_live_price_moves_without_recomputing_zones(self):
        service = preview_service()
        first = service.levels(series(), {"state": "LIVE", "fields": {"price": {"value": 6.5, "as_of_ns": T0}}})
        second = service.levels(series(), {"state": "LIVE", "fields": {"price": {"value": 7.2, "as_of_ns": T0}}})
        self.assertEqual(first["zones"], second["zones"])
        self.assertEqual(first["calculated_at"], second["calculated_at"])
        self.assertNotEqual(first["support"], second["support"])

    def test_new_completed_bar_recalculates(self):
        clock = {"now": ns(2026, 9, 25, 11, 0)}
        service = ScreenerPreviewService(screener=ScreenerService(source_factory=Source, runtime_getter=lambda **_: None),
                                         bars=StaticBars({}), futures=StaticFutures(), news=lambda: NEWS, now_ns=lambda: clock["now"])
        base = series()
        first = service.levels(base, {})
        clock["now"] += MINUTE_NS
        extended = BarSeries("RGTI", "5m", "EXTENDED", "CURRENT", None, None, T0,
                             base.bars + tuple(bars_from_closes([6.9, 6.2], start=base.bars[-1].end_ns)), None)
        second = service.levels(extended, {})
        self.assertNotEqual(first["calculated_at"], second["calculated_at"])
        self.assertEqual(second["input_bar_count"], first["input_bar_count"] + 2)
        self.assertEqual(service.levels(base, {})["calculated_at"], first["calculated_at"])

    def test_quote_never_mutates_bars_and_instruments_do_not_leak(self):
        bars = StaticBars({("RGTI", "5m"): series(), ("XOM", "5m"): series("XOM", closes=[100 + v for v in oscillation()])})
        service = preview_service(bars=bars, quotes={"RGTI": live_quote(99.0)})
        before = [bar.close for bar in bars.series_by_key[("RGTI", "5m")].bars]
        rgti = service.read("RGTI")
        self.assertEqual([bar["close"] for bar in rgti["bars"]["bars"]], before)
        xom = service.read("XOM")
        self.assertTrue(all(zone["center"] > 90 for zone in xom["levels"]["zones"]))
        self.assertTrue(all(zone["center"] < 20 for zone in service.read("RGTI")["levels"]["zones"]))

    def test_timeframe_switch_recomputes(self):
        service = preview_service()
        five, fifteen = service.read("RGTI", timeframe="5m"), service.read("RGTI", timeframe="15m")
        self.assertEqual((five["levels"]["timeframe"], fifteen["levels"]["timeframe"]), ("5m", "15m"))


class WhyMatchedTests(unittest.TestCase):
    def row(self):
        return ScreenerService(source_factory=Source, runtime_getter=lambda **_: None).row_for("RGTI")[0]

    def test_numeric_between_greater_and_missing(self):
        result = explain_matches(self.row(), [
            {"id": "p", "field": "price", "operator": "between", "value": [2, 20]},
            {"id": "c", "field": "change_pct", "operator": "gt", "value": 10},
            {"id": "f", "field": "float_shares", "operator": "lt", "value": 20_000_000},
            {"id": "r", "field": "rel_volume", "operator": "gt", "value": 2},
        ])
        self.assertEqual(result["state"], "MATCHED")
        texts = [item["text"] for item in result["items"]]
        self.assertEqual(texts, ["Price $6.42 is within $2.00–$20.00", "Change % +28.40% is above +10.00%",
                                 "Float 7.4M is below 20M", "Relative Volume 5.80× is above 2.00×"])
        missing = explain_matches(self.row(), [{"id": "rsi", "field": "rsi_14", "operator": "gt", "value": 50}])
        self.assertEqual(missing["state"], "NOT_MATCHED")
        self.assertTrue(missing["items"][0]["missing"])
        self.assertIn("unavailable", missing["items"][0]["text"])

    def test_text_rules(self):
        result = explain_matches(self.row(), [{"id": "s", "field": "sector", "operator": "eq", "value": "technology"},
                                              {"id": "i", "field": "industry", "operator": "in", "value": ["Computer Hardware", "Software"]}])
        self.assertEqual([item["passed"] for item in result["items"]], [True, True])
        self.assertEqual(result["items"][1]["text"], "Industry Computer Hardware is one of Computer Hardware, Software")

    def test_no_filters_and_no_provider_tokens(self):
        self.assertEqual(explain_matches(self.row(), []), {"state": "NO_ACTIVE_FILTERS", "items": []})
        preset = next(p for p in builtin_presets() if p["id"] == "MOMENTUM_IGNITION_DISCOVERY")
        result = explain_matches(self.row(), preset["filters"])
        self.assertEqual(result["state"], "MATCHED")
        blob = json.dumps(result)
        self.assertNotRegex(blob, r"sh_|ta_|fa_")
        modified = [dict(preset["filters"][0], value=50)] + preset["filters"][1:]
        self.assertEqual(explain_matches(self.row(), modified)["state"], "NOT_MATCHED")

    def test_explanation_agrees_with_screen_execution(self):
        service = ScreenerService(source_factory=Source, runtime_getter=lambda **_: None)
        rows = [service.row_for(symbol)[0] for symbol in ("RGTI", "XOM")]
        rng = random.Random(3)
        fields = ["price", "change_pct", "rel_volume", "market_cap", "short_float_pct", "rsi_14"]
        for _ in range(200):
            rules = [{"id": f"r{i}", "field": rng.choice(fields), "operator": rng.choice(["gt", "lt", "gte", "lte"]),
                      "value": rng.choice([0, 1, 5, 10, 25, 100, 1e9])} for i in range(rng.randint(1, 3))]
            matched = {row["symbol"] for row in apply_filters(rows, validate_filters(rules))}
            for row in rows:
                self.assertEqual(explain_matches(row, rules)["state"] == "MATCHED", row["symbol"] in matched)


class WhyMovingTests(unittest.TestCase):
    def setUp(self):
        self.row = ScreenerService(source_factory=Source, runtime_getter=lambda **_: None).row_for("RGTI")[0]
        self.now = datetime(2026, 9, 25, 11, 0, tzinfo=ET)
        self.levels = {"timeframe": "5m", "calculated_at": "x", "testing": None,
                       "support": {"lower": 6.08, "upper": 6.13, "distance_pct": 4.52},
                       "resistance": {"lower": 6.55, "upper": 6.6, "distance_pct": 2.02}}
        self.futures = {"items": [{"root": "NQ", "contract": {"contract_id": "NQZ26"}, "relationship_reason": "Technology/growth index context.",
                                   "quote": {"state": "LIVE", "change_pct": 1.1, "provider": "MOOMOO_OPEND", "as_of": "t"}},
                                  {"root": "ES", "contract": {"contract_id": "ESZ26"}, "relationship_reason": "Broad US equity market context.",
                                   "quote": None}]}

    def classes(self, result):
        return {(item["class"], item["kind"]) for item in result["items"]}

    def test_observed_derived_catalyst_and_futures(self):
        result = explain_movement(row=self.row, quote={}, levels=self.levels, futures=self.futures, news=NEWS, now=self.now)
        classes = self.classes(result)
        for expected in (("OBSERVED", "PRICE_MOVE"), ("OBSERVED", "VOLUME"), ("OBSERVED", "HEADLINE"),
                         ("DERIVED", "RELATIVE_VOLUME"), ("DERIVED", "SHORT_INTEREST"), ("DERIVED", "SR_PROXIMITY"),
                         ("DERIVED", "FUTURES_CONTEXT"), ("INSUFFICIENT_EVIDENCE", "CAUSATION")):
            self.assertIn(expected, classes)
        headlines = [item for item in result["items"] if item["kind"] == "HEADLINE"]
        self.assertEqual(len(headlines), 1)  # old, future, and other-ticker items excluded
        self.assertIn("Rigetti announces quantum contract", headlines[0]["text"])
        futures = [item for item in result["items"] if item["kind"] == "FUTURES_CONTEXT"]
        self.assertEqual(len(futures), 1)  # unavailable ES price is not an evidence item
        self.assertIn("not evidence of causation", futures[0]["text"])
        self.assertIsNone(result["ai_synthesis"])

    def test_no_catalyst_and_unavailable_news(self):
        none = explain_movement(row=self.row, quote={}, levels={}, futures={}, news={"success": True, "items": []}, now=self.now)
        self.assertIn("No verified catalyst or causal driver identified from currently available evidence",
                      [item["text"] for item in none["items"]])
        unavailable = explain_movement(row=self.row, quote={}, levels={}, futures={}, news={"success": False, "items": []}, now=self.now)
        self.assertIn(("UNAVAILABLE", "CATALYST"), self.classes(unavailable))
        self.assertIn(("INSUFFICIENT_EVIDENCE", "CAUSATION"), self.classes(unavailable))

    def test_no_unsupported_causal_language(self):
        for news in (NEWS, {"success": True, "items": []}, {"success": False}):
            result = explain_movement(row=self.row, quote={}, levels=self.levels, futures=self.futures, news=news, now=self.now)
            for item in result["items"]:
                self.assertNotRegex(item["text"], CAUSAL)
                self.assertIn(item["class"], {"OBSERVED", "DERIVED", "UNAVAILABLE", "INSUFFICIENT_EVIDENCE"})

    def test_move_window_rolls_back_over_weekend(self):
        self.assertEqual(move_window_start(datetime(2026, 9, 27, 1, 0, tzinfo=ET)), datetime(2026, 9, 24, 16, 0, tzinfo=ET))
        self.assertEqual(move_window_start(datetime(2026, 9, 28, 3, 0, tzinfo=ET)), datetime(2026, 9, 24, 16, 0, tzinfo=ET))
        self.assertEqual(move_window_start(datetime(2026, 9, 28, 9, 0, tzinfo=ET)), datetime(2026, 9, 25, 16, 0, tzinfo=ET))


class FuturesTransport:
    def __init__(self, *, entitled=False, last_trade="2026-12-18", mains=None, fail=None):
        self.entitled, self.last_trade, self.fail = entitled, last_trade, fail
        self.mains = mains or {"ES": "E-mini S&P 500 Futures (DEC6)", "NQ": "E-mini NASDAQ 100 Futures (DEC6)",
                               "RTY": "E-mini Russell 2000 Index Futures (DEC6)", "CL": "Crude Oil Futures (NOV6)",
                               "NG": "Henry Hub Natural Gas Futures (NOV6)", "GC": "Gold Futures (DEC6)",
                               "SI": "Silver Futures (DEC6)", "HG": "Copper Futures (DEC6)", "ZN": "10-Year T-Note Futures (DEC6)"}
        self.quote_calls = 0

    def fetch_future_contracts(self, codes):
        if self.fail:
            return {"reason_code": self.fail, "rows": None}
        rows = []
        for code in codes:
            root = code[3:].removesuffix("main")
            if code.endswith("main") and root in self.mains:
                rows.append({"code": code, "name": self.mains[root], "last_trade_time": ""})
            elif not code.endswith("main"):
                rows.append({"code": code, "name": code, "last_trade_time": self.last_trade, "exchange_type": "US_CME"})
        return {"reason_code": None, "rows": rows}

    def fetch_future_quotes(self, codes):
        self.quote_calls += 1
        if not self.entitled:
            return {"reason_code": "MOOMOO_QUOTE_NOT_ENTITLED", "rows": None}
        return {"reason_code": None, "rows": [{"code": code, "last_price": 6155.25, "prev_close_price": 6129.5,
                                                "update_time": "2026-09-25 10:59:55"} for code in codes if "ES" in code]}


def futures_service(transport, *, bridge=lambda: None, today=date(2026, 9, 25), now_s=None):
    now = now_s if now_s is not None else datetime(2026, 9, 25, 11, 0, tzinfo=ET).timestamp()
    return FuturesContextService(transport_getter=lambda: transport, bridge=bridge, today=lambda: today, now_s=lambda: now)


class ContextualFuturesTests(unittest.TestCase):
    def test_deterministic_relationship_mapping(self):
        roots = lambda **kw: [r.root for r in related_futures(**kw)]  # noqa: E731
        self.assertEqual(roots(sector="Technology", industry="Semiconductors", market_cap=1e9), ["NQ", "RTY", "ES"])
        self.assertEqual(roots(sector="Energy", industry="Oil & Gas E&P", market_cap=5e10), ["CL", "NG", "ES"])
        self.assertEqual(roots(sector="Basic Materials", industry="Gold", market_cap=5e9), ["GC", "ES"])
        self.assertEqual(roots(sector="Basic Materials", industry="Silver", market_cap=1e9), ["SI", "RTY", "ES"])
        self.assertEqual(roots(sector="Healthcare", industry="Biotechnology", market_cap=5e10), ["ES"])
        self.assertEqual(roots(sector="Financial", industry="Banks - Regional", market_cap=None), ["ZN", "ES"])
        for relation in related_futures(sector="Energy", industry="Oil & Gas E&P", market_cap=1e9):
            self.assertTrue(relation.reason.endswith("context."))
            self.assertIn(relation.relationship_type, {"BROAD_MARKET", "SECTOR", "UNDERLYING", "MACRO_FACTOR", "STYLE_FACTOR"})

    def test_contract_identity_resolution_and_expiry(self):
        main = {"name": "E-mini S&P 500 Futures (DEC6)"}
        current = resolve_contract("ES", main, {"US.ES2612": {"last_trade_time": "2026-12-18"}}, date(2026, 9, 25))
        self.assertEqual((current["state"], current["contract_id"], current["provider_code"]), ("CURRENT", "ESZ26", "US.ES2612"))
        expired = resolve_contract("CL", {"name": "Crude Oil Futures (OCT6)"}, {"US.CL2610": {"last_trade_time": "2026-09-22"}}, date(2026, 9, 25))
        self.assertEqual((expired["state"], expired["reason"]), ("EXPIRED", "CONTRACT_EXPIRED"))
        self.assertEqual(resolve_contract("ES", {"name": "E-mini"}, {}, date(2026, 9, 25))["state"], "UNRESOLVED")
        self.assertEqual(resolve_contract("ES", main, {}, date(2026, 9, 25))["reason"], "CONTRACT_REFERENCE_UNAVAILABLE")
        decade = resolve_contract("ES", {"name": "E-mini S&P 500 Futures (MAR0)"}, {"US.ES3003": {"last_trade_time": "2030-03-15"}}, date(2029, 12, 20))
        self.assertEqual(decade["contract_id"], "ESH30")

    def test_expired_contract_never_shown_as_current(self):
        result = futures_service(FuturesTransport(last_trade="2026-09-22")).read(sector="Energy", industry="Oil & Gas Integrated", market_cap=1e11)
        self.assertTrue(all(item["contract"]["state"] == "EXPIRED" for item in result["items"]))
        self.assertTrue(all(item["quote"] is None and item["unavailable_reason"] == "CONTRACT_EXPIRED" for item in result["items"]))

    def test_a_delayed_second_source_prices_unentitled_contracts_and_is_never_live(self):
        now = datetime(2026, 9, 25, 11, 0, tzinfo=ET).timestamp()
        asked = []

        class Delayed:
            def quotes(self, refs):
                asked.extend(refs)
                return {ref.key: {"last": 100.0, "prev_close": 99.0, "updated_s": now - 3} for ref in refs if ref.root == "NQ"}

        service = FuturesContextService(transport_getter=lambda: FuturesTransport(), bridge=lambda: None,
                                        today=lambda: date(2026, 9, 25), now_s=lambda: now, delayed_source=Delayed)
        nq, es = service.read(sector="Technology", industry="Software", market_cap=5e10)["items"]
        self.assertEqual([(ref.key, ref.root, ref.contract_month, ref.expiry) for ref in asked],
                         [("NQZ26", "NQ", "202612", "2026-12-18"), ("ESZ26", "ES", "202612", "2026-12-18")])
        self.assertEqual((nq["availability"], nq["quote"]["state"], nq["quote"]["provider"], nq["quote"]["price"]),
                         ("AVAILABLE", "DELAYED", "IBKR_DELAYED", 100.0))
        self.assertEqual((es["availability"], es["unavailable_reason"], es["quote"]), ("UNAVAILABLE", "NOT_ENTITLED", None))
        # An entitled primary quote is used as is; the second source is not asked about it.
        asked.clear()
        entitled = FuturesContextService(transport_getter=lambda: FuturesTransport(entitled=True), bridge=lambda: None,
                                         today=lambda: date(2026, 9, 25), now_s=lambda: now, delayed_source=Delayed)
        items = {item["root"]: item for item in entitled.read(sector="Technology", industry="Software", market_cap=5e10)["items"]}
        self.assertEqual(items["ES"]["quote"]["provider"], "MOOMOO_OPEND")
        self.assertEqual([ref.root for ref in asked], ["NQ"])

    def test_not_entitled_is_truthful_and_cached(self):
        transport = FuturesTransport()
        service = futures_service(transport)
        result = service.read(sector="Technology", industry="Software", market_cap=5e10)
        self.assertEqual([item["root"] for item in result["items"]], ["NQ", "ES"])
        for item in result["items"]:
            self.assertEqual((item["availability"], item["unavailable_reason"], item["quote"]), ("UNAVAILABLE", "NOT_ENTITLED", None))
            self.assertEqual(item["contract"]["state"], "CURRENT")
            self.assertTrue(item["relationship_reason"])
        service.read(sector="Technology", industry="Software", market_cap=5e10)
        self.assertEqual(transport.quote_calls, 1)
        self.assertIn("not evidence", result["causal_note"])

    def test_partial_current_data(self):
        result = futures_service(FuturesTransport(entitled=True)).read(sector="Technology", industry="Software", market_cap=5e10)
        items = {item["root"]: item for item in result["items"]}
        self.assertEqual(items["ES"]["quote"]["state"], "LIVE")
        self.assertAlmostEqual(items["ES"]["quote"]["change_pct"], (6155.25 - 6129.5) / 6129.5 * 100, places=3)
        self.assertEqual(items["NQ"]["availability"], "UNAVAILABLE")

    def test_rates_only_with_live_data(self):
        banks = futures_service(FuturesTransport()).read(sector="Financial", industry="Banks - Regional", market_cap=5e10)
        self.assertEqual([item["root"] for item in banks["items"]], ["ES"])

    def test_provider_unavailable(self):
        result = futures_service(FuturesTransport(fail="OPEND_UNAVAILABLE")).read(sector="Healthcare", industry="Biotechnology", market_cap=5e10)
        self.assertEqual(result["items"][0]["contract"]["state"], "UNRESOLVED")
        self.assertEqual(result["items"][0]["availability"], "UNAVAILABLE")
        none = FuturesContextService(transport_getter=lambda: None, bridge=lambda: None).read(sector=None, industry=None, market_cap=None)
        self.assertEqual(none["items"][0]["unavailable_reason"], "PROVIDER_UNAVAILABLE")

    def test_bridge_used_only_for_same_es_contract(self):
        now = datetime(2026, 9, 25, 11, 0, tzinfo=ET).timestamp()
        snapshot = {"bids": [{"price": 6155.0, "size": 5}], "asks": [{"price": 6155.5, "size": 4}],
                    "event_time": datetime.fromtimestamp(now - 1, tz=ET).isoformat()}
        same = futures_service(FuturesTransport(), bridge=lambda: {"available": True, "contract_month": "202612", "snapshot": snapshot})
        es = same.read(sector="Healthcare", industry="Biotechnology", market_cap=5e10)["items"][0]
        self.assertEqual((es["quote"]["provider"], es["quote"]["price"], es["quote"]["price_basis"], es["quote"]["state"]),
                         ("FUTURESX_BRIDGE", 6155.25, "MID", "LIVE"))
        other = futures_service(FuturesTransport(), bridge=lambda: {"available": True, "contract_month": "202609", "snapshot": snapshot})
        self.assertIsNone(other.read(sector="Healthcare", industry="Biotechnology", market_cap=5e10)["items"][0]["quote"])

    def test_no_futures_universe_or_fixture_sources(self):
        text = (ROOT / "src" / "market_platform_foundation" / "ui_api" / "screener_futures_context.py").read_text(encoding="utf-8")
        self.assertNotIn("fixture_futures", text)
        self.assertNotRegex(text, r"ESZ4|NQZ4")


class PreviewLayoutPersistenceTests(unittest.TestCase):
    class Store:
        def __init__(self):
            self.values = {}

        def get_preferences(self):
            return dict(self.values)

        def set_preference(self, key, value):
            self.values[key] = value

    def test_layout_round_trip_bounds_and_default(self):
        store = self.Store()
        repository = ScreenerConfigRepository(store)
        self.assertEqual(repository.get_preview_layout(), DEFAULT_PREVIEW)
        self.assertEqual(repository.save_preview_layout({"open": False, "width": 480}), {"version": 1, "open": False, "width": 480})
        self.assertEqual(ScreenerConfigRepository(store).get_preview_layout()["width"], 480)
        for bad in ({"open": True, "width": 100}, {"open": "yes", "width": 400}, {"open": True, "width": 400.5}, None):
            with self.assertRaises(ValueError):
                validate_preview_layout(bad)
        store.values["screener.s3.preview"] = {"open": True, "width": 9999}
        self.assertEqual(repository.get_preview_layout(), DEFAULT_PREVIEW)
        self.assertNotIn("screener.s2.screens", store.values)


if __name__ == "__main__":
    unittest.main()

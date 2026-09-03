from __future__ import annotations

import json
import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cboe_regsho.threshold import normalize_threshold_file as normalize_cboe
from market_platform_foundation.cboe_regsho.threshold import parse_threshold_file as parse_cboe
from market_platform_foundation.finra.otc_threshold import normalize_otc_threshold_row, normalize_otc_threshold_rows
from market_platform_foundation.nasdaq_regsho.threshold import normalize_threshold_file as normalize_nasdaq
from market_platform_foundation.nasdaq_regsho.threshold import parse_threshold_file as parse_nasdaq
from market_platform_foundation.nyse_regsho.threshold import normalize_threshold_file as normalize_nyse
from market_platform_foundation.nyse_regsho.threshold import parse_threshold_file as parse_nyse
from market_platform_foundation.short_intelligence.contracts import ThresholdAuthority, ThresholdCoverageStatus
from market_platform_foundation.short_intelligence.identity import SymbolMap
from market_platform_foundation.short_intelligence.store import ShortIntelligenceStore
from market_platform_foundation.short_intelligence.threshold_coverage import (
    resolve_listing_authority,
    threshold_coverage_as_of,
    threshold_state_as_of,
)

FIXTURES = ROOT / "tests" / "fixtures" / "short_intelligence"


def _map() -> SymbolMap:
    return SymbolMap.from_path(FIXTURES / "threshold_symbol_map.json")


class ProviderNormalizationTests(unittest.TestCase):
    def test_nyse_american_threshold(self) -> None:
        raw = (FIXTURES / "nyse_american_amze_20260819.txt").read_bytes()
        parsed = parse_nyse(raw, trade_date="2026-08-19", source_market="NYSE American")
        rows = normalize_nyse(
            parsed,
            symbol_map=_map(),
            observed_time="2026-08-20T01:00:00Z",
            retrieved_time="2026-08-20T01:00:00Z",
            requested_symbols=("AMZE",),
        )
        self.assertTrue(rows[0].currently_threshold)
        self.assertEqual(rows[0].source_sro, "NYSE_GROUP")
        self.assertEqual(rows[0].source_market, "NYSE American")

    def test_nyse_arca_threshold(self) -> None:
        raw = (FIXTURES / "nyse_arca_bmnz_20260819.txt").read_bytes()
        parsed = parse_nyse(raw, trade_date="2026-08-19", source_market="NYSE Arca")
        rows = normalize_nyse(
            parsed,
            symbol_map=_map(),
            observed_time="2026-08-20T01:00:00Z",
            retrieved_time="2026-08-20T01:00:00Z",
            requested_symbols=("BMNZ",),
        )
        self.assertTrue(rows[0].currently_threshold)
        self.assertEqual(rows[0].listing_coverage, "NYSE_ARCA")

    def test_cboe_bzx_threshold(self) -> None:
        raw = (FIXTURES / "cboe_bzx_gmeu_20250617.txt").read_bytes()
        parsed = parse_cboe(raw, trade_date="2025-06-17")
        rows = normalize_cboe(
            parsed,
            symbol_map=_map(),
            observed_time="2025-06-17T10:00:00Z",
            retrieved_time="2025-06-17T10:00:00Z",
            requested_symbols=("GMEU",),
        )
        self.assertTrue(rows[0].currently_threshold)
        self.assertEqual(rows[0].source_sro, "CBOE_BZX")

    def test_finra_otc_rule_flags_distinct(self) -> None:
        rows = json.loads((FIXTURES / "finra_otc_threshold_slice.json").read_text(encoding="utf-8"))
        map_ = _map()
        reg = normalize_otc_threshold_row(
            rows[0],
            symbol_map=map_,
            observed_time="2026-08-19T12:00:00Z",
            retrieved_time="2026-08-19T12:00:00Z",
        )
        rule4320 = normalize_otc_threshold_row(
            rows[1],
            symbol_map=map_,
            observed_time="2026-08-19T12:00:00Z",
            retrieved_time="2026-08-19T12:00:00Z",
        )
        self.assertEqual(reg.reg_sho_threshold_flag, "Y")
        self.assertEqual(reg.rule_4320_flag, "N")
        self.assertEqual(rule4320.reg_sho_threshold_flag, "N")
        self.assertEqual(rule4320.rule_4320_flag, "Y")
        self.assertNotEqual(reg.reg_sho_threshold_flag, reg.rule_4320_flag)


class PitTests(unittest.TestCase):
    def test_nyse_publication_not_backdated(self) -> None:
        raw = (FIXTURES / "nyse_american_amze_20260819.txt").read_bytes()
        parsed = parse_nyse(raw, trade_date="2026-08-19", source_market="NYSE American")
        rows = normalize_nyse(
            parsed,
            symbol_map=_map(),
            observed_time="2026-08-20T01:00:00Z",
            retrieved_time="2026-08-20T01:00:00Z",
            requested_symbols=("AMZE",),
        )
        store = ShortIntelligenceStore()
        store.add_threshold(rows[0])
        self.assertIsNone(store.latest_threshold("AMZE", "2026-08-19T12:00:00Z"))
        self.assertIsNotNone(store.latest_threshold("AMZE", rows[0].clocks["available_time"]))

    def test_cboe_publication_not_backdated(self) -> None:
        raw = (FIXTURES / "cboe_bzx_gmeu_20250617.txt").read_bytes()
        parsed = parse_cboe(raw, trade_date="2025-06-17")
        rows = normalize_cboe(
            parsed,
            symbol_map=_map(),
            observed_time="2025-06-17T10:00:00Z",
            retrieved_time="2025-06-17T10:00:00Z",
            requested_symbols=("GMEU",),
        )
        store = ShortIntelligenceStore()
        store.add_threshold(rows[0])
        self.assertIsNone(store.latest_threshold("GMEU", "2025-06-17T08:00:00Z"))
        self.assertIsNotNone(store.latest_threshold("GMEU", rows[0].clocks["available_time"]))

    def test_finra_amendment_versions(self) -> None:
        map_ = _map()
        v1_rows = json.loads((FIXTURES / "finra_otc_threshold_slice.json").read_text(encoding="utf-8"))[:1]
        v2_rows = json.loads((FIXTURES / "finra_otc_threshold_amended_v2.json").read_text(encoding="utf-8"))
        v1 = normalize_otc_threshold_row(
            v1_rows[0],
            symbol_map=map_,
            observed_time="2026-08-19T12:00:00Z",
            retrieved_time="2026-08-19T12:00:00Z",
        )
        v2 = normalize_otc_threshold_row(
            v2_rows[0],
            symbol_map=map_,
            observed_time="2026-08-19T18:00:00Z",
            retrieved_time="2026-08-19T18:00:00Z",
            record_version=2,
        )
        store = ShortIntelligenceStore()
        store.add_threshold(v1)
        store.add_threshold(v2)
        mid = store.threshold_as_of("OTCR", "2026-08-19T15:00:00Z")
        later = store.threshold_as_of("OTCR", "2026-08-19T19:00:00Z")
        self.assertEqual(mid[-1].record_version, 1)
        self.assertEqual(later[-1].record_version, 2)


class CoverageRoutingTests(unittest.TestCase):
    def test_nasdaq_absence_is_not_global_negative_for_nyse_listed(self) -> None:
        map_ = _map()
        store = ShortIntelligenceStore()
        raw = (FIXTURES / "nyse_american_amze_20260819.txt").read_bytes()
        parsed = parse_nyse(raw, trade_date="2026-08-19", source_market="NYSE American")
        nyse_rows = normalize_nyse(
            parsed,
            symbol_map=map_,
            observed_time="2026-08-20T01:00:00Z",
            retrieved_time="2026-08-20T01:00:00Z",
            requested_symbols=("AMZE",),
        )
        store.add_threshold(nyse_rows[0])
        state = threshold_state_as_of(
            store,
            map_,
            instrument_id="AMZE",
            provider_symbol="AMZE",
            as_of="2026-08-20T03:00:00Z",
        )
        self.assertEqual(state["authority"], ThresholdAuthority.NYSE_GROUP.value)
        self.assertTrue(state["currently_threshold"])
        routing = resolve_listing_authority(map_, "AMZE", as_of="2026-08-19")
        self.assertEqual(routing.authority, ThresholdAuthority.NYSE_GROUP)
        self.assertNotEqual(routing.authority, ThresholdAuthority.NASDAQ)

    def test_listing_transfer_routes_historically(self) -> None:
        map_ = _map()
        before = resolve_listing_authority(map_, "MOVER", as_of="2024-01-01")
        after = resolve_listing_authority(map_, "MOVER", as_of="2025-01-01")
        self.assertEqual(before.authority, ThresholdAuthority.NASDAQ)
        self.assertEqual(after.authority, ThresholdAuthority.NYSE_GROUP)

    def test_source_outage_is_not_not_threshold(self) -> None:
        state = threshold_state_as_of(
            ShortIntelligenceStore(),
            _map(),
            instrument_id="AMZE",
            provider_symbol="AMZE",
            as_of="2026-08-20T03:00:00Z",
            source_outage={ThresholdAuthority.NYSE_GROUP: True},
        )
        self.assertEqual(state["status"], "SOURCE_UNAVAILABLE")
        self.assertIsNone(state["currently_threshold"])

    def test_holiday_is_not_outage(self) -> None:
        state = threshold_state_as_of(
            ShortIntelligenceStore(),
            _map(),
            instrument_id="AMZE",
            provider_symbol="AMZE",
            as_of="2026-08-20T03:00:00Z",
            holiday=True,
        )
        self.assertEqual(state["status"], "NOT_APPLICABLE")

    def test_confirmed_absence_with_coverage(self) -> None:
        map_ = _map()
        store = ShortIntelligenceStore()
        raw = (FIXTURES / "cboe_bzx_empty_20260819.txt").read_bytes()
        parsed = parse_cboe(raw, trade_date="2026-08-19")
        rows = normalize_cboe(
            parsed,
            symbol_map=map_,
            observed_time="2026-08-20T01:00:00Z",
            retrieved_time="2026-08-20T01:00:00Z",
            requested_symbols=("GMEU",),
        )
        store.add_threshold(rows[0])
        coverage = threshold_coverage_as_of(
            store,
            map_,
            instrument_id="GMEU",
            provider_symbol="GMEU",
            as_of="2026-08-20T03:00:00Z",
            trade_date="2026-08-19",
        )
        self.assertEqual(coverage.status, ThresholdCoverageStatus.COVERED)
        state = threshold_state_as_of(
            store,
            map_,
            instrument_id="GMEU",
            provider_symbol="GMEU",
            as_of="2026-08-20T03:00:00Z",
        )
        self.assertFalse(state["currently_threshold"])


class FinraAbsentMembershipTests(unittest.TestCase):
    def test_requested_symbol_absent_from_finra_list(self) -> None:
        rows = json.loads((FIXTURES / "finra_otc_threshold_slice.json").read_text(encoding="utf-8"))
        normalized = normalize_otc_threshold_rows(
            rows,
            symbol_map=_map(),
            observed_time="2026-08-19T12:00:00Z",
            retrieved_time="2026-08-19T12:00:00Z",
            requested_symbols=("OTCR", "ZZZZ"),
        )
        absent = next(row for row in normalized if row.provider_symbol == "ZZZZ")
        self.assertFalse(absent.currently_threshold)
        self.assertIn("SOURCE_COVERAGE_CONFIRMED_ABSENT", absent.quality_flags)


if __name__ == "__main__":
    unittest.main()

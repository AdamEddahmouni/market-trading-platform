from __future__ import annotations

import io
import sys
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.sec_ftd.normalize import normalize_ftd_archive, parse_sec_price
from market_platform_foundation.sec_ftd.parser import parse_archive_bytes, parse_text_rows
from market_platform_foundation.sec_ftd.periods import parse_period_key
from market_platform_foundation.short_intelligence.clocks import visible_at
from market_platform_foundation.short_intelligence.contracts import (
    FailsToDeliverObservation,
    ObservationFamily,
    ShortInterestObservation,
    ShortSaleVolumeObservation,
    ThresholdStatusObservation,
)
from market_platform_foundation.short_intelligence.features import (
    cross_source_features,
    ftd_balance_features,
    sum_of_daily_balance_observations,
)
from market_platform_foundation.short_intelligence.identity import SymbolMap
from market_platform_foundation.short_intelligence.pressure import pressure_state
from market_platform_foundation.short_intelligence.store import ShortIntelligenceStore

FIXTURES = ROOT / "tests" / "fixtures" / "sec_ftd"
MAP_FIXTURES = ROOT / "tests" / "fixtures" / "short_intelligence"


def _map() -> SymbolMap:
    return SymbolMap.from_path(MAP_FIXTURES / "symbol_map.json")


def _period() -> object:
    return parse_period_key("cnsfails202607b")


def _load_observations() -> tuple[FailsToDeliverObservation, ...]:
    text = (FIXTURES / "synthetic_slice.txt").read_text(encoding="utf-8")
    rows = parse_text_rows(text)
    from market_platform_foundation.sec_ftd.parser import FtdParsedArchive

    parsed = FtdParsedArchive(
        period_key="cnsfails202607b",
        member_name="cnsfails202607b.txt",
        content_hash="FIXTURE",
        record_count=len(rows),
        rows=tuple(rows),
    )
    return normalize_ftd_archive(
        parsed,
        period=_period(),
        symbol_map=_map(),
        observed_time="2026-08-15T12:00:00Z",
        retrieved_time="2026-08-15T12:00:00Z",
    )


class SemanticSeparationTests(unittest.TestCase):
    def test_families_are_distinct(self) -> None:
        self.assertEqual(ObservationFamily.FAILS_TO_DELIVER.value, "FAILS_TO_DELIVER")
        ftd_fields = set(FailsToDeliverObservation.__dataclass_fields__)
        si_fields = set(ShortInterestObservation.__dataclass_fields__)
        ssv_fields = set(ShortSaleVolumeObservation.__dataclass_fields__)
        th_fields = set(ThresholdStatusObservation.__dataclass_fields__)
        self.assertIn("ftd_balance_quantity", ftd_fields)
        self.assertNotIn("ftd_balance_quantity", si_fields | ssv_fields | th_fields)
        self.assertIn("current_short_position_quantity", si_fields)
        self.assertIn("short_sale_volume", ssv_fields)
        self.assertIn("currently_threshold", th_fields)

    def test_no_naked_short_fields(self) -> None:
        fields = set(FailsToDeliverObservation.__dataclass_fields__)
        forbidden = {"naked_short", "short_generated_ftd", "illegal_short_score"}
        self.assertTrue(forbidden.isdisjoint(fields))


class ParserTests(unittest.TestCase):
    def test_pipe_delimited_and_dot_price(self) -> None:
        rows = parse_text_rows((FIXTURES / "synthetic_slice.txt").read_text(encoding="utf-8"))
        aapl = next(row for row in rows if row.symbol == "AAPL")
        self.assertEqual(aapl.previous_day_price_raw, ".")
        self.assertIsNone(parse_sec_price("."))
        self.assertEqual(aapl.cusip, "037833100")

    def test_zip_parsing(self) -> None:
        text = (FIXTURES / "synthetic_slice.txt").read_text(encoding="utf-8")
        text += "Trailer record count 7\nTrailer total quantity of shares 999\n"
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("cnsfails202607b.txt", text)
        parsed = parse_archive_bytes(buffer.getvalue(), period_key="cnsfails202607b")
        self.assertEqual(parsed.record_count, 7)
        self.assertTrue(parsed.content_hash)


class BalanceNotFlowTests(unittest.TestCase):
    def test_balance_change_is_not_cumulative_flow(self) -> None:
        observations = _load_observations()
        biya = [row for row in observations if row.raw_symbol == "BIYA"]
        features = ftd_balance_features(tuple(biya))
        self.assertEqual(features["ftd_balance_quantity"], 431)
        self.assertEqual(features["ftd_balance_change"], 431 - 97797)
        summed = sum_of_daily_balance_observations(tuple(biya))
        self.assertNotEqual(summed, features["ftd_balance_change"])
        self.assertGreater(summed, features["ftd_balance_quantity"])


class PitTests(unittest.TestCase):
    def test_publication_lag_blocks_visibility(self) -> None:
        observations = _load_observations()
        biya = next(row for row in observations if row.settlement_date == "2026-07-28")
        store = ShortIntelligenceStore()
        store.add_ftd(biya)
        self.assertIsNone(store.latest_ftd("BIYA", "2026-07-29T00:00:00Z"))
        self.assertIsNotNone(store.latest_ftd("BIYA", biya.clocks["available_time"]))
        self.assertFalse(visible_at(biya.clocks, "2026-07-28T23:59:59Z"))

    def test_delay_before_short_pressure_exposes_ftd(self) -> None:
        observations = _load_observations()
        biya = next(row for row in observations if row.settlement_date == "2026-07-28")
        store = ShortIntelligenceStore()
        store.add_ftd(biya)
        before = pressure_state(store, "BIYA", "2026-07-29T12:00:00Z")
        after = pressure_state(store, "BIYA", biya.clocks["available_time"])
        self.assertEqual(before.fails_to_deliver, "UNKNOWN")
        self.assertIn("FTD_QUANTITY_UNKNOWN", before.quality_flags)
        self.assertEqual(after.fails_to_deliver, "KNOWN")
        self.assertEqual(after.ftd_balance_quantity, 395128)
        self.assertNotIn("FTD_QUANTITY_UNKNOWN", after.quality_flags)

    def test_source_version_correction(self) -> None:
        observations = _load_observations()
        base = next(row for row in observations if row.settlement_date == "2026-07-28")
        v1 = replace(
            base,
            ftd_balance_quantity=300000,
            content_hash="HASH_V1",
            clocks={**base.clocks, "available_time": "2026-08-15T12:00:00Z"},
        )
        v2 = replace(
            base,
            ftd_balance_quantity=395128,
            content_hash="HASH_V2",
            clocks={**base.clocks, "available_time": "2026-08-16T12:00:00Z"},
        )
        store = ShortIntelligenceStore()
        store.add_ftd(v1)
        store.add_ftd(v2)
        mid = store.latest_ftd("BIYA", "2026-08-15T18:00:00Z")
        later = store.latest_ftd("BIYA", "2026-08-16T18:00:00Z")
        assert mid is not None and later is not None
        self.assertEqual(mid.ftd_balance_quantity, 300000)
        self.assertEqual(later.ftd_balance_quantity, 395128)


class IdentityAndQualityTests(unittest.TestCase):
    def test_cusip_retained_and_unknown_identity(self) -> None:
        observations = _load_observations()
        unknown = next(row for row in observations if row.raw_symbol == "ZZZZ")
        self.assertEqual(unknown.cusip, "ZZZZZZZZZ")
        self.assertIn("IDENTITY_UNRESOLVED", unknown.quality_flags)
        self.assertEqual(unknown.instrument_id, "")

    def test_notional_only_when_price_valid(self) -> None:
        observations = _load_observations()
        aapl = next(row for row in observations if row.raw_symbol == "AAPL")
        nvda = next(row for row in observations if row.raw_symbol == "NVDA")
        self.assertIsNone(aapl.approx_ftd_notional_sec_price)
        self.assertIn("PRICE_UNAVAILABLE", aapl.quality_flags)
        self.assertEqual(nvda.approx_ftd_notional_sec_price, 85000 * 180.25)


class StoreAndDuplicateTests(unittest.TestCase):
    def test_duplicate_ingestion_suppressed(self) -> None:
        observations = _load_observations()
        row = observations[0]
        store = ShortIntelligenceStore()
        store.add_ftd(row)
        store.add_ftd(row)
        self.assertEqual(len(store.ftd_as_of(row.instrument_id, row.clocks["available_time"])), 1)

    def test_outage_is_not_zero(self) -> None:
        store = ShortIntelligenceStore()
        self.assertIsNone(store.latest_ftd("BIYA", "2026-08-20T00:00:00Z"))
        features = cross_source_features(store, "BIYA", "2026-08-20T00:00:00Z")
        self.assertEqual(features["fails_to_deliver"]["status"], "UNKNOWN")
        self.assertIsNone(features["fails_to_deliver"]["ftd_balance_quantity"])


class PeriodTests(unittest.TestCase):
    def test_half_month_period(self) -> None:
        period = parse_period_key("cnsfails202607b")
        self.assertEqual(period.source_period_start, "2026-07-16")
        self.assertEqual(period.source_period_end, "2026-07-31")
        self.assertIn("cnsfails202607b.zip", period.download_url)


class FailureBehaviorTests(unittest.TestCase):
    def test_bad_zip(self) -> None:
        with self.assertRaises(Exception):
            parse_archive_bytes(b"not-a-zip", period_key="cnsfails202607b")

    def test_malformed_header(self) -> None:
        with self.assertRaises(ValueError):
            parse_text_rows("BAD|HEADER\n20260701|123456789|TEST|1|X|1.0\n")

    def test_transport_404(self) -> None:
        from market_platform_foundation.sec_edgar.transport import SecTransport
        from market_platform_foundation.sec_ftd.transport import FtdTransport

        def requester(url: str, headers: dict[str, str], timeout: float) -> bytes:
            raise HTTPError(url, 404, "missing", {}, None)

        transport = FtdTransport(
            SecTransport(user_agent="IntegratedMarketPlatform research contact@example.com", requester=requester)
        )
        with self.assertRaises(OSError):
            transport.fetch_archive(
                parse_period_key("cnsfails209901a"),
                retrieved_time="2026-08-20T00:00:00Z",
            )


if __name__ == "__main__":
    unittest.main()

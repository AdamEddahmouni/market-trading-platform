"""Screener S14 point-in-time campaign: no disclosure family is visible before it was public.

Covers every family the Screener serves: House PTRs, Senate eFD reports (synthetic
fixtures), 13F holdings (synthetic data sets through the managed index), Schedule
13D/13G and Form 4 filing clocks. Transaction/event dates are never availability;
retrieval time never moves publication time; amendments are visible only from their
own availability, and the earlier record is never erased.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "sec_edgar"))

import test_s14_thirteen_f_lifecycle as data13f  # noqa: E402  (synthetic SEC-layout data sets)
from market_platform_foundation.congressional_ptr import house, normalized, senate  # noqa: E402
from market_platform_foundation.sec_edgar import thirteen_f_lifecycle as lc  # noqa: E402
from market_platform_foundation.ui_api.screener_participants import ScreenerParticipantService  # noqa: E402

SENATE = ROOT / "tests" / "fixtures" / "congressional_disclosure" / "senate_efd"


def utc(*parts: int) -> datetime:
    return datetime(*parts, tzinfo=UTC)


def house_items(filed: date, *, traded: date, retrieved: datetime | None, status: str | None = None,
                doc_id: str = "30000001") -> list[normalized.CongressionalDisclosure]:
    filing = house.HouseFiling(doc_id=doc_id, year=filed.year, filing_type="P", prefix="Hon.", first="Jane",
                               last="Example", suffix="", state_district="EX01", filing_date=filed)
    txn = house.PtrTransaction(owner="SELF", asset_description="Example Corp (EXC)", asset_type_code="ST",
                               disclosed_ticker="EXC", transaction_type="PURCHASE", transaction_type_code="P",
                               transaction_date=traded, notification_date=traded + timedelta(days=3),
                               amount=house.parse_amount_range("$1,001 - $15,000"), row_index=0, filing_status=status)
    document = house.PtrDocument(doc_id, "PARSED", None, (txn,), "0" * 64)
    return normalized.from_house(filing, document, retrieved)


class HousePitTests(unittest.TestCase):
    """Scenario A: transaction Jan 5, filed Jan 30."""

    def setUp(self):
        self.items = house_items(date(2026, 1, 30), traded=date(2026, 1, 5), retrieved=utc(2026, 1, 31, 15))

    def test_not_visible_before_filing_visible_after(self):
        self.assertEqual(normalized.visible_as_of(self.items, utc(2026, 1, 20)), [])
        self.assertEqual(len(normalized.visible_as_of(self.items, utc(2026, 1, 31, 12))), 1)

    def test_transaction_date_is_never_availability(self):
        self.assertEqual(normalized.visible_as_of(self.items, utc(2026, 1, 5, 23, 59)), [])
        row = normalized.to_rows(self.items)[0]
        self.assertEqual((row["transaction_date"], row["filing_date"]), ("2026-01-05", "2026-01-30"))
        self.assertGreater(row["available_at"], "2026-01-30")

    def test_eastern_filing_day_bound(self):
        # 23:00 UTC on Jan 30 is 18:00 ET — still inside the ET filing day, so not yet provably public.
        self.assertEqual(normalized.visible_as_of(self.items, utc(2026, 1, 30, 23)), [])
        self.assertEqual(self.items[0].available_at, utc(2026, 1, 31, 4, 59, 59))
        self.assertEqual(self.items[0].date_quality, "DATE_ONLY")

    def test_retrieval_is_a_separate_clock(self):
        late = house_items(date(2026, 1, 30), traded=date(2026, 1, 5), retrieved=utc(2026, 3, 1))[0]
        self.assertEqual(late.available_at, utc(2026, 1, 31, 4, 59, 59))          # publication is not rewritten
        self.assertEqual(late.imp_known_at, utc(2026, 3, 1))
        self.assertEqual(normalized.visible_as_of([late], utc(2026, 2, 1)), [late])
        self.assertEqual(normalized.visible_as_of([late], utc(2026, 2, 1), clock="imp"), [])
        with self.assertRaises(ValueError):
            normalized.visible_as_of([late], utc(2026, 2, 1), clock="transaction")

    def test_amended_row_is_visible_only_from_its_own_filing(self):
        original = self.items
        amended = house_items(date(2026, 2, 20), traded=date(2026, 1, 5), retrieved=None, status="Amended", doc_id="30000002")
        both = original + amended
        self.assertEqual([item.source_document for item in normalized.visible_as_of(both, utc(2026, 2, 10))], ["30000001"])
        later = normalized.visible_as_of(both, utc(2026, 2, 21, 12))
        self.assertEqual([item.source_document for item in later], ["30000001", "30000002"])  # the original is kept
        self.assertEqual(amended[0].amendment, {"row_filing_status": "Amended", "linked_to": None})


class SenatePitTests(unittest.TestCase):
    def setUp(self):
        self.original = normalized.from_senate(senate.parse_report((SENATE / "ptr_electronic.html").read_text()))
        self.amendment = normalized.from_senate(senate.parse_report((SENATE / "ptr_amendment.html").read_text()))

    def test_filed_timestamp_minute_precision(self):
        # Filed 01/30/2026 @ 3:45 PM ET = 20:45 UTC.
        self.assertEqual(normalized.visible_as_of(self.original, utc(2026, 1, 30, 20, 44)), [])
        self.assertEqual(len(normalized.visible_as_of(self.original, utc(2026, 1, 30, 20, 45))), 4)
        self.assertEqual(normalized.visible_as_of(self.original, utc(2026, 1, 20)), [])     # scenario A for the Senate

    def test_original_then_amendment(self):
        items = self.original + self.amendment
        before = normalized.versions_as_of(items, utc(2026, 2, 1))
        after = normalized.versions_as_of(items, utc(2026, 2, 10, 15))
        key = next(iter(before))
        self.assertTrue(before[key]["current"].endswith("a001"))
        self.assertTrue(after[key]["current"].endswith("a002"))
        self.assertEqual(len(normalized.visible_as_of(items, utc(2026, 2, 1))), 4)   # the amendment is not yet known
        self.assertEqual(len(normalized.visible_as_of(items, utc(2026, 2, 10, 15))), 5)

    def test_versioned_rows_pass_the_response_secret_audit(self):
        # Rows with version state go straight into API responses; a credential-shaped field name blocks the whole panel.
        from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload
        rows = normalized.to_rows(self.original + self.amendment, now=utc(2026, 2, 10, 15))
        self.assertTrue(any("version" in row for row in rows))
        assert_no_secrets_in_payload({"transactions": rows})


class ThirteenFPitTests(unittest.TestCase):
    """Scenario B: period Jun 30, filed Aug 14 — through the managed index."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        harness = data13f.Harness(Path(cls.tmp.name) / "13f", (data13f.W1, data13f.W2, data13f.W3))
        payload = data13f.data_set([("Z-2", "14-AUG-2026", "13F-HR", "9", "30-JUN-2026")],
                                   [("Z-2", "", "Zeta Holdings", data13f.HR)], [("Z-2", "12345678X", 10, 1, "SH", "")])
        harness.payloads[data13f.BASE + data13f.W2] = payload
        harness.names = [data13f.W2]
        assert harness.lifecycle(datasets=1).refresh()["outcome"] == "PUBLISHED"
        cls.index = lc.ManagedIndex(Path(cls.tmp.name) / "13f", clock=harness.clock)

    @classmethod
    def tearDownClass(cls):
        cls.index._index.close()
        cls.tmp.cleanup()

    def test_not_public_before_filing(self):
        self.assertEqual(self.index.section(["12345678X"], now=utc(2026, 7, 20))["state"], "NO_DISCLOSURES")
        self.assertEqual(self.index.section(["12345678X"], now=utc(2026, 8, 14, 20))["state"], "NO_DISCLOSURES")

    def test_available_after_filing(self):
        section = self.index.section(["12345678X"], now=utc(2026, 8, 15, 0, 30))
        self.assertEqual((section["period"], section["holders"][0]["available_at"]), ("2026-06-30", "2026-08-15T00:00:00Z"))

    def test_restatement_versions(self):
        # Covered with the real multi-generation lifecycle in tests/sec_edgar/test_s14_thirteen_f_lifecycle.py
        # (test_refresh_never_reveals_later_filings_to_a_historical_query); asserted here for the campaign index.
        harness = data13f.Harness(Path(self.tmp.name) / "13f-b", (data13f.W1, data13f.W2, data13f.W3))
        self.assertEqual(harness.lifecycle(datasets=3).refresh()["outcome"], "PUBLISHED")
        index, _ = lc.load_current_index(Path(self.tmp.name) / "13f-b")
        try:
            beta = lambda moment: {h["manager"]: h["shares"] for h in index.section([data13f.CUSIP], now=moment)["holders"]}["Beta Advisors"]  # noqa: E731
            self.assertEqual(beta(utc(2026, 9, 15)), 999)     # original, before the Sep 20 restatement
            self.assertEqual(beta(utc(2026, 9, 21, 1)), 400)  # restatement, after it was filed
        finally:
            index.close()


class SecOwnershipPitTests(unittest.TestCase):
    """Form 4 and Schedule 13D/13G: availability is EDGAR acceptance, never the transaction or event date."""

    def test_acceptance_time_is_availability(self):
        filing = SimpleNamespace(acceptance_datetime="2026-09-25T21:30:12.000Z", filing_date="2026-09-25", report_date="2026-09-23")
        clock = ScreenerParticipantService._filing_clock(filing)
        self.assertEqual((clock["available_at"], clock["available_basis"]), ("2026-09-25T21:30:12Z", "SEC_ACCEPTANCE_TIME"))
        self.assertGreater(clock["available_at"], clock["report_date"])        # the event date is earlier and never used

    def test_filing_date_fallback_is_end_of_day(self):
        filing = SimpleNamespace(acceptance_datetime="", filing_date="2026-09-25", report_date="2026-09-20")
        clock = ScreenerParticipantService._filing_clock(filing)
        self.assertEqual((clock["available_at"], clock["available_basis"]), ("2026-09-25T23:59:59Z", "SEC_FILING_DATE_END_OF_DAY"))


class CrossFamilyInvariantTests(unittest.TestCase):
    def test_no_congressional_row_is_available_before_its_filing_date(self):
        items = (house_items(date(2026, 1, 30), traded=date(2026, 1, 5), retrieved=None)
                 + normalized.from_senate(senate.parse_report((SENATE / "ptr_electronic.html").read_text()))
                 + normalized.from_senate(senate.parse_report((SENATE / "ptr_amendment.html").read_text())))
        for item in items:
            with self.subTest(item=item.id):
                self.assertGreaterEqual(item.available_at.date(), item.filing_date)
                if item.transaction_date is not None:
                    self.assertGreater(item.available_at.date(), item.transaction_date)
                self.assertGreaterEqual(item.imp_known_at, item.available_at)


if __name__ == "__main__":
    unittest.main()

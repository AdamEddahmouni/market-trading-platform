"""S12 House Periodic Transaction Reports: official index + PDF text layer, amounts, owners, clocks.

Fixtures are real House Clerk documents (2026 filing index excerpt and four PTR
PDFs: three electronic filings and one scanned paper filing).
"""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.congressional_ptr import house  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "congressional_disclosure" / "house_ptr"


def document(doc_id: str) -> house.PtrDocument:
    return house.parse_ptr_pdf(doc_id, (FIXTURES / f"{doc_id}.pdf").read_bytes())


class FilingIndexTests(unittest.TestCase):
    def setUp(self):
        self.filings = house.parse_filing_index((FIXTURES / "2026FD.sample.xml").read_bytes(), year=2026)

    def test_malformed_members_are_skipped_and_ptrs_selected(self):
        self.assertEqual(len(self.filings), 6)  # the member with an unparseable filing date is dropped
        ptrs = house.periodic_transaction_reports(self.filings)
        self.assertEqual([item.doc_id for item in ptrs], ["20035420", "20035455", "9116331", "20035408"])

    def test_identity_and_urls(self):
        filing = next(item for item in self.filings if item.doc_id == "20035455")
        self.assertEqual(filing.member_name, "Josh Gottheimer")
        self.assertEqual(filing.member_id, "HOUSE:GOTTHEIMER:JOSH:NJ05")
        self.assertEqual(filing.filing_date, date(2026, 9, 14))
        self.assertEqual(filing.document_url, "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/20035455.pdf")

    def test_zip_payload_without_xml(self):
        import io
        import zipfile

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("2026FD.txt", "not xml")
        with self.assertRaises(ValueError):
            house.parse_filing_index(buffer.getvalue(), year=2026)


class PtrDocumentTests(unittest.TestCase):
    def test_joint_account_options_and_stock(self):
        doc = document("20035455")
        self.assertEqual((doc.state, len(doc.transactions)), ("PARSED", 7))
        first, option = doc.transactions[0], doc.transactions[1]
        self.assertEqual((first.owner, first.disclosed_ticker, first.asset_type_code, first.transaction_type),
                         ("JOINT", "AMAT", "ST", "PURCHASE"))
        self.assertEqual((first.transaction_date, first.notification_date), (date(2026, 8, 6), date(2026, 9, 14)))
        self.assertEqual((first.amount.min_amount, first.amount.max_amount), (1_001, 15_000))
        self.assertEqual((option.asset_type_code, option.disclosed_ticker), ("OP", "MSFT"))
        self.assertEqual((option.amount.min_amount, option.amount.max_amount), (250_001, 500_000))
        self.assertFalse(any(item.quality_flags for item in doc.transactions))

    def test_self_and_spouse_partial_sales(self):
        doc = document("20035420")
        self.assertEqual(len(doc.transactions), 6)
        self.assertEqual([item.owner for item in doc.transactions[:2]], ["SELF", "SPOUSE"])
        self.assertEqual(doc.transactions[0].transaction_type, "SALE_PARTIAL")

    def test_multi_page_report_keeps_every_row(self):
        doc = document("20035408")
        self.assertEqual(len(doc.transactions), 78)
        self.assertEqual({item.owner for item in doc.transactions}, {"DEPENDENT_CHILD"})
        self.assertEqual(doc.transactions[-1].disclosed_ticker, "WAB")
        self.assertEqual([item.row_index for item in doc.transactions], list(range(78)))
        self.assertFalse(any(item.quality_flags for item in doc.transactions))

    def test_scanned_paper_filing_is_not_machine_readable(self):
        doc = document("9116331")
        self.assertEqual((doc.state, doc.reason, doc.transactions),
                         ("TRANSACTIONS_NOT_MACHINE_READABLE", "NO_TEXT_LAYER_SCANNED_FILING", ()))

    def test_garbage_and_oversize(self):
        self.assertEqual(house.parse_ptr_pdf("1", b"not a pdf").state, "PARSE_ERROR")
        self.assertEqual(house.parse_ptr_pdf("1", b"%PDF" + b"0" * (house.MAX_PDF_BYTES + 1)).reason, "PDF_TOO_LARGE")

    def test_matchable_ticker_only_for_stock_etf_option(self):
        doc = document("20035455")
        self.assertEqual(doc.transactions[0].matchable_ticker, "AMAT")
        other = house.PtrTransaction(owner="SELF", asset_description="US Treasury Bill [GS]", asset_type_code="GS",
                                     disclosed_ticker=None, transaction_type_code="P", transaction_type="PURCHASE",
                                     transaction_date=None, notification_date=None, amount=None, row_index=0)
        self.assertIsNone(other.matchable_ticker)


class AmountTests(unittest.TestCase):
    def test_ranges_are_never_points(self):
        band = house.parse_amount_range("$1,001 - $15,000")
        self.assertEqual((band.min_amount, band.max_amount), (1_001, 15_000))
        self.assertFalse(band.to_dict()["exact_value_disclosed"])
        self.assertEqual(band.to_dict()["class"], "OBSERVED")

    def test_open_ended_and_spouse_bands(self):
        over = house.parse_amount_range("Over $50,000,000")
        self.assertEqual((over.min_amount, over.max_amount), (50_000_001, None))
        spouse = house.parse_amount_range("Spouse/DC Over $1,000,000")
        self.assertTrue(spouse.display.startswith("Spouse/DC"))

    def test_invalid(self):
        self.assertIsNone(house.parse_amount_range("$15,000 - $1,001"))
        self.assertIsNone(house.parse_amount_range("n/a"))

    def test_a_band_never_becomes_a_point(self):
        # S12 boundary: a disclosed range is not an exact amount, and no helper turns one into a value.
        self.assertFalse(hasattr(house, "derived_midpoint_estimate"))
        band = house.parse_amount_range("$1,001 - $15,000")
        self.assertFalse(band.to_dict()["exact_value_disclosed"])


class ClockTests(unittest.TestCase):
    def test_availability_is_never_the_transaction_date(self):
        # S14 supersedes S12 here: the Clerk's filing date is an Eastern date, so availability is the end
        # of that ET day (S12 used the end of the UTC day, 4-5 hours early), and IMP's retrieval is a
        # separate clock that no longer moves public availability (see test_s14_pit.py).
        available, basis = house.filing_available_at(date(2026, 9, 14), retrieved_at=None)
        self.assertEqual(available, datetime(2026, 9, 15, 3, 59, 59, tzinfo=UTC))
        self.assertEqual(basis, "house_index.filing_date_end_of_et_day")
        later = datetime(2026, 9, 20, 12, tzinfo=UTC)
        self.assertEqual(house.filing_available_at(date(2026, 9, 14), retrieved_at=later)[0], available)
        self.assertEqual(house.imp_known_at(available, later), later)
        early = datetime(2026, 9, 14, 12, tzinfo=UTC)
        self.assertEqual(house.imp_known_at(available, early), available)

    def test_disclosure_lag(self):
        self.assertEqual(house.disclosure_lag_days(date(2026, 8, 6), date(2026, 9, 14)), 39)
        self.assertIsNone(house.disclosure_lag_days(None, date(2026, 9, 14)))


if __name__ == "__main__":
    unittest.main()

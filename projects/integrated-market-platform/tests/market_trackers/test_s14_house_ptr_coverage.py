"""S14 House PTR coverage: document classes, parse states, row annotations, scanned boundary.

Real Clerk fixtures (three electronic PTRs, one scanned paper PTR) cover the layouts
S12 met; synthetic PDFs written below (same text-layer mechanics: ToUnicode font,
positioned cells joined per line) cover states the real fixtures do not: empty tables,
unrecognized rows, malformed bands, mixed text/image documents, amended rows.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.congressional_ptr import house  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "congressional_disclosure" / "house_ptr"
HEADER = [["I D", "O w n e r", "A sse t", "T ran sac t i o n"], ["T y p e"], ["D at e", "N o t i fi c at i o n"],
          ["D at e"], ["A mo u n t", "Cap ."], ["G ai n s >"]]


def real(doc_id: str) -> house.PtrDocument:
    return house.parse_ptr_pdf(doc_id, (FIXTURES / f"{doc_id}.pdf").read_bytes())


def make_pdf(pages: list[list[list[str]]], *, image_pages: int = 0) -> bytes:
    """A minimal text-layer PDF: each line is a list of cells printed at one baseline."""

    objects: dict[int, bytes] = {}
    cmap = b"begincmap\n1 beginbfrange\n<0020> <007E> <0020>\nendbfrange\nendcmap\n"
    objects[3] = b"<< /Length %d >>\nstream\n" % len(cmap) + cmap + b"\nendstream"
    objects[4] = b"<< /Type /Font /Subtype /Type0 /BaseFont /Synthetic /ToUnicode 3 0 R >>"
    kids = []
    number = 10
    for page in pages + [[] for _ in range(image_pages)]:
        ops = [b"BT /F1 9 Tf"]
        y = 760
        for line in page:
            for column, cell in enumerate(line):
                hex_text = "".join(f"{ord(char):04X}" for char in cell).encode()
                ops.append(b"1 0 0 1 %d %d Tm <%s> Tj" % (40 + 90 * column, y, hex_text))
            y -= 12
        ops.append(b"ET")
        content = b"\n".join(ops) if page else b""
        objects[number] = b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"
        resources = b"/Resources << /Font << /F1 4 0 R >> >>"
        if not page:
            objects[number + 2] = b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /Length 1 >>\nstream\n\xff\nendstream"
            resources = b"/Resources << /XObject << /Im1 %d 0 R >> >>" % (number + 2)
        objects[number + 1] = b"<< /Type /Page /Parent 2 0 R %s /Contents %d 0 R >>" % (resources, number)
        kids.append(number + 1)
        number += 3
    objects[2] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (b" ".join(b"%d 0 R" % kid for kid in kids), len(kids))
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    body = b"%PDF-1.4\n" + b"".join(b"%d 0 obj\n%s\nendobj\n" % (key, value) for key, value in sorted(objects.items()))
    return body + b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"


def row(owner: str, asset: str, code: str, traded: str, notified: str, amount: str) -> list[list[str]]:
    return [[owner, asset], [code, traded, notified, amount]]


class RealDocumentTests(unittest.TestCase):
    def test_text_documents_are_classified_and_parsed(self):
        for doc_id, rows in (("20035455", 7), ("20035420", 6), ("20035408", 78)):
            with self.subTest(doc_id=doc_id):
                doc = real(doc_id)
                self.assertEqual((doc.document_class, doc.parse_state, doc.state), ("TEXT_PDF", "PARSED", "PARSED"))
                self.assertEqual(len(doc.transactions), rows)
                self.assertEqual(doc.text_pages, doc.page_count)
                self.assertEqual(doc.unrecognized_rows, 0)

    def test_multi_page_rows_keep_their_page(self):
        doc = real("20035408")
        self.assertEqual(doc.page_count, 8)
        self.assertEqual(doc.transactions[0].source_page, 1)
        self.assertGreater(doc.transactions[-1].source_page, 1)
        pages = [item.source_page for item in doc.transactions]
        self.assertEqual(pages, sorted(pages))

    def test_scan_is_scanned_unparsed_not_no_transactions(self):
        doc = real("9116331")
        self.assertEqual((doc.document_class, doc.parse_state, doc.reason),
                         ("SCANNED_PDF", "SCANNED_UNPARSED", "NO_TEXT_LAYER_SCANNED_FILING"))
        self.assertNotEqual(doc.parse_state, "NO_TRANSACTIONS")
        self.assertEqual(doc.state, "TRANSACTIONS_NOT_MACHINE_READABLE")   # S12 consumers still see the legacy state
        self.assertEqual(doc.extraction["status"], "ENGINE_NOT_CONFIGURED")

    def test_row_labels_are_kept_verbatim(self):
        doc = real("20035455")
        first, option = doc.transactions[0], doc.transactions[1]
        self.assertEqual(first.filing_status, "New")
        self.assertEqual(first.subholding_of, "Morgan Stanley - Select UMA Account # 1")
        self.assertIsNone(first.description)
        self.assertEqual(option.description, "Call options; Strike price $340; Expires 10/16/2026")
        self.assertEqual(option.asset_type_code, "OP")

    def test_coverage_metrics(self):
        docs = [real(doc_id) for doc_id in ("20035455", "20035420", "20035408", "9116331")]
        metrics = house.coverage_metrics(docs, loading=2, document_errors=1)
        self.assertEqual(metrics["documents_total"], 7)
        self.assertEqual((metrics["machine_readable"], metrics["scanned"], metrics["parsed"]), (3, 1, 3))
        self.assertEqual((metrics["scanned_unparsed"], metrics["failed"], metrics["no_transactions"]), (1, 0, 0))
        self.assertEqual((metrics["loading"], metrics["document_errors"], metrics["transaction_count"]), (2, 1, 91))


class SyntheticDocumentTests(unittest.TestCase):
    def test_writer_round_trips_through_the_parser(self):
        pdf = make_pdf([HEADER + row("SP", "Apple Inc. (AAPL) [ST]", "P", "08/06/2026", "09/14/2026", "$1,001 - $15,000")])
        doc = house.parse_ptr_pdf("1", pdf)
        self.assertEqual((doc.document_class, doc.parse_state), ("TEXT_PDF", "PARSED"))
        txn = doc.transactions[0]
        self.assertEqual((txn.owner, txn.disclosed_ticker, txn.transaction_date), ("SPOUSE", "AAPL", date(2026, 8, 6)))

    def test_empty_table_is_no_transactions(self):
        doc = house.parse_ptr_pdf("2", make_pdf([[["Filing ID #2"]] + HEADER]))
        self.assertEqual((doc.parse_state, doc.reason, doc.state), ("NO_TRANSACTIONS", "TRANSACTION_TABLE_EMPTY", "PARSED"))

    def test_text_without_table_is_parse_failed(self):
        doc = house.parse_ptr_pdf("3", make_pdf([[["Periodic Transaction Report"], ["Name:", "Hon. Example"]]]))
        self.assertEqual((doc.parse_state, doc.reason), ("PARSE_FAILED", "TRANSACTION_TABLE_NOT_FOUND"))

    def test_only_unrecognized_rows_is_parse_failed(self):
        doc = house.parse_ptr_pdf("4", make_pdf([HEADER + row("", "Apple Inc. (AAPL) [ST]", "Q", "08/06/2026", "09/14/2026",
                                                               "$1,001 - $15,000")]))
        self.assertEqual((doc.parse_state, doc.reason, doc.unrecognized_rows), ("PARSE_FAILED", "TRANSACTION_ROWS_UNRECOGNIZED", 1))

    def test_partial_parse_keeps_good_rows_and_counts_the_rest(self):
        pdf = make_pdf([HEADER
                        + row("JT", "Apple Inc. (AAPL) [ST]", "P", "08/06/2026", "09/14/2026", "$1,001 - $15,000")
                        + row("", "Bad Code Corp (BAD) [ST]", "Q", "08/07/2026", "09/14/2026", "$1,001 - $15,000")
                        + row("DC", "Broken Band Inc (BRK) [ST]", "S", "08/08/2026", "09/14/2026", "$15,000 - $1,001")])
        doc = house.parse_ptr_pdf("5", pdf)
        self.assertEqual(doc.parse_state, "PARTIALLY_PARSED")
        self.assertEqual(doc.reason, "SOME_ROWS_UNRECOGNIZED;SOME_ROW_FIELDS_UNPARSED")
        self.assertEqual([item.owner for item in doc.transactions], ["JOINT", "DEPENDENT_CHILD"])
        self.assertIn("AMOUNT_RANGE_UNPARSED", doc.transactions[1].quality_flags)
        self.assertIsNone(doc.transactions[1].amount)      # a malformed band is never turned into a number

    def test_wrapped_asset_and_amount_across_a_page_break(self):
        page1 = HEADER + [["SP", "Lamar Advertising Company Class A"], ["S", "08/06/2026", "09/14/2026", "$15,001 -"]]
        page2 = [["Filing ID #6"]] + HEADER + [["Common Stock (LAMR)", "[ST]", "$50,000"]]
        doc = house.parse_ptr_pdf("6", make_pdf([page1, page2]))
        self.assertEqual(doc.parse_state, "PARSED", doc.reason)
        txn = doc.transactions[0]
        self.assertEqual((txn.disclosed_ticker, txn.asset_type_code), ("LAMR", "ST"))
        self.assertEqual((txn.amount.min_amount, txn.amount.max_amount), (15_001, 50_000))

    def test_missing_ticker_and_unknown_asset_code(self):
        pdf = make_pdf([HEADER + row("", "Municipal Bond Fund", "P", "08/06/2026", "09/14/2026", "$1,001 - $15,000")])
        txn = house.parse_ptr_pdf("7", pdf).transactions[0]
        self.assertIsNone(txn.disclosed_ticker)
        self.assertIsNone(txn.matchable_ticker)
        self.assertIn("ASSET_TYPE_CODE_MISSING", txn.quality_flags)

    def test_amended_row_and_option_description(self):
        pdf = make_pdf([HEADER + row("", "Microsoft Corp (MSFT) [OP]", "P", "08/14/2026", "09/14/2026", "$250,001 - $500,000")
                        + [["F        S     :", "A m en d ed"], ["D          :", "C a l l   o pt io ns;  S t r ik e  $ 34 0"]]])
        doc = house.parse_ptr_pdf("8", pdf)
        txn = doc.transactions[0]
        self.assertEqual((txn.filing_status, txn.description), ("Amended", "Call options; Strike $340"))
        self.assertEqual(doc.amended_rows, 1)

    def test_invalid_dates_are_flagged_not_guessed(self):
        pdf = make_pdf([HEADER + row("", "Apple Inc. (AAPL) [ST]", "P", "13/45/2026", "09/14/2026", "$1,001 - $15,000")])
        doc = house.parse_ptr_pdf("9", pdf)
        self.assertIsNone(doc.transactions[0].transaction_date)
        self.assertEqual(doc.parse_state, "PARTIALLY_PARSED")
        self.assertIn("TRANSACTION_DATE_UNPARSED", doc.transactions[0].quality_flags)

    def test_mixed_text_and_image_pages(self):
        pdf = make_pdf([HEADER + row("", "Apple Inc. (AAPL) [ST]", "P", "08/06/2026", "09/14/2026", "$1,001 - $15,000")],
                       image_pages=1)
        doc = house.parse_ptr_pdf("10", pdf)
        self.assertEqual((doc.document_class, doc.parse_state, doc.reason), ("MIXED", "PARTIALLY_PARSED", "IMAGE_ONLY_PAGES_UNPARSED"))
        self.assertEqual((doc.page_count, doc.text_pages), (2, 1))

    def test_malformed_and_unsupported(self):
        self.assertEqual(house.parse_ptr_pdf("11", b"<html>not a pdf").document_class, "MALFORMED")
        empty = house.parse_ptr_pdf("12", b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF")
        self.assertEqual((empty.document_class, empty.parse_state, empty.reason),
                         ("MALFORMED", "PARSE_FAILED", "NO_TEXT_LAYER_AND_NO_IMAGES"))
        encrypted = b"%PDF-1.6\n1 0 obj\n<< /Filter /Standard /V 4 /R 4 >>\nendobj\ntrailer << /Encrypt 1 0 R >>"
        doc = house.parse_ptr_pdf("13", encrypted)
        self.assertEqual((doc.document_class, doc.reason), ("UNSUPPORTED", "UNSUPPORTED_PDF_ENCRYPTION"))
        big = house.parse_ptr_pdf("14", b"%PDF" + b"0" * (house.MAX_PDF_BYTES + 1))
        self.assertEqual((big.document_class, big.reason), ("UNSUPPORTED", "PDF_TOO_LARGE"))


class _Engine(house.ScannedPtrExtractor):
    engine = "synthetic-engine/1"

    def __init__(self, confidences: list[float], status: str = "EXTRACTED") -> None:
        self.confidences = confidences
        self.status = status

    def extract(self, doc_id, data):
        rows = []
        for index, confidence in enumerate(self.confidences):
            txn = house.PtrTransaction(
                owner="SELF", asset_description=f"Example {index} (EX{index})", asset_type_code="ST",
                disclosed_ticker=f"EX{index}", transaction_type="PURCHASE", transaction_type_code="P",
                transaction_date=date(2026, 8, 1), notification_date=date(2026, 8, 2),
                amount=house.parse_amount_range("$1,001 - $15,000"), row_index=index)
            rows.append(house.ExtractedRow(txn, page=1, raw_text=f"P 08/01/2026 Example {index}", confidence=confidence,
                                           bbox=(10.0, 20.0, 300.0, 32.0), field_text={"amount": "$1,001 - $15,000"}))
        return house.ScannedExtraction(self.status, tuple(rows), min(self.confidences or [0.0]), self.engine)


class ScannedBoundaryTests(unittest.TestCase):
    def scan(self, engine: house.ScannedPtrExtractor) -> house.PtrDocument:
        return house.parse_ptr_pdf("9116331", (FIXTURES / "9116331.pdf").read_bytes(), scanned=engine)

    def test_confident_extraction_is_extracted_not_observed(self):
        doc = self.scan(_Engine([0.995, 0.99]))
        self.assertEqual((doc.document_class, doc.parse_state), ("SCANNED_PDF", "PARSED"))
        txn = doc.transactions[0]
        self.assertEqual(txn.evidence_class, "EXTRACTED")
        self.assertIn("EXTRACTED_FROM_SCAN", txn.quality_flags)
        self.assertEqual((txn.extraction["page"], txn.extraction["engine"]), (1, "synthetic-engine/1"))
        self.assertEqual(txn.extraction["raw_text"], "P 08/01/2026 Example 0")
        self.assertEqual(txn.extraction["bbox"], [10.0, 20.0, 300.0, 32.0])

    def test_low_confidence_rows_are_withheld(self):
        doc = self.scan(_Engine([0.995, 0.5]))
        self.assertEqual((doc.parse_state, doc.withheld_rows, len(doc.transactions)), ("PARTIALLY_PARSED", 1, 1))
        none = self.scan(_Engine([0.4]))
        self.assertEqual((none.parse_state, none.reason, none.transactions), ("SCANNED_UNPARSED", "EXTRACTION_BELOW_CONFIDENCE", ()))

    def test_failed_engine_fails_closed(self):
        doc = self.scan(_Engine([], status="FAILED"))
        self.assertEqual((doc.parse_state, doc.reason), ("SCANNED_UNPARSED", "SCANNED_EXTRACTION_FAILED"))

    def test_default_extractor_has_no_engine(self):
        self.assertIsNone(house.ScannedPtrExtractor.engine)
        self.assertEqual(house.ScannedPtrExtractor().extract("x", b"").status, "ENGINE_NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()

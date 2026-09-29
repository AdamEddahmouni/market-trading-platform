"""S14 Senate eFD boundary: attestation gate, import directory, parser, normalized contract.

All Senate fixtures are SYNTHETIC (tests/fixtures/congressional_disclosure/senate_efd):
authored to mirror the eFD PTR page layout, with fictitious names and ids. They prove
the parser and the boundary, not live Senate access. No test touches the network.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.congressional_ptr import normalized, senate  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "congressional_disclosure" / "senate_efd"
ATTESTATION = {"accepted_by": "operator", "accepted_at": "2026-09-29T12:00:00Z",
               "statement": "I accepted the eFD terms in my own browser session."}


def parse(name: str) -> senate.SenateReport:
    return senate.parse_report((FIXTURES / name).read_text(encoding="utf-8"), file_name=name)


class ParserTests(unittest.TestCase):
    def test_electronic_report(self):
        report = parse("ptr_electronic.html")
        self.assertEqual((report.parse_state, report.report_kind), ("PARSED", "ptr"))
        self.assertEqual(report.report_id, "5f3a1c2e-0000-4000-8000-00000000a001")
        self.assertEqual((report.filer_name, report.filer_alternate), ("Jane Q Example", "Example, Jane"))
        self.assertEqual(report.report_for, date(2026, 1, 29))
        self.assertEqual(report.filed_at, datetime(2026, 1, 30, 20, 45, tzinfo=UTC))   # 3:45 PM EST
        available, basis, quality = report.available_at
        self.assertEqual((available, basis, quality), (report.filed_at, "senate_efd.filed_timestamp_et", "SOURCE_TIMESTAMP_MINUTE"))
        self.assertFalse(report.is_amendment)
        self.assertEqual(len(report.transactions), 4)

    def test_rows_owner_asset_type_and_bands(self):
        rows = parse("ptr_electronic.html").transactions
        self.assertEqual([item.owner for item in rows], ["SELF", "SPOUSE", "JOINT", "DEPENDENT_CHILD"])
        self.assertEqual([item.transaction_type for item in rows], ["PURCHASE", "SALE", "SALE_PARTIAL", "EXCHANGE"])
        self.assertEqual([item.disclosed_ticker for item in rows], ["AAPL", None, "MSFT", "NVDA"])
        self.assertEqual([item.asset_type_code for item in rows], ["ST", None, "OP", "ST"])
        self.assertEqual([item.matchable_ticker for item in rows], ["AAPL", None, "MSFT", "NVDA"])
        self.assertEqual(rows[1].asset_type, "Other Securities")
        self.assertEqual(rows[2].comment, "Call options; strike $400; expires 03/20/2026")
        self.assertIsNone(rows[0].comment)                               # "--" means none
        self.assertEqual((rows[3].amount.min_amount, rows[3].amount.max_amount), (1_000_001, 5_000_000))
        self.assertFalse(rows[0].amount.to_dict()["exact_value_disclosed"])
        self.assertEqual(rows[0].transaction_date, date(2026, 1, 5))

    def test_amendment(self):
        report = parse("ptr_amendment.html")
        self.assertEqual((report.amendment_number, report.is_amendment), (1, True))
        self.assertEqual(report.transactions[0].amount.display, "$15,001 – $50,000")

    def test_paper_filing_is_scanned_unparsed(self):
        report = parse("paper_filing.html")
        self.assertEqual((report.report_kind, report.parse_state, report.reason), ("paper", "SCANNED_UNPARSED", "PAPER_FILING_IMAGES"))
        self.assertEqual(report.transactions, ())
        # A date-only filing is bounded at the end of its Eastern day, never given an invented time.
        self.assertEqual(report.available_at, (datetime(2025, 12, 21, 4, 59, 59, tzinfo=UTC),
                                               "senate_efd.filed_date_end_of_et_day", "DATE_ONLY"))

    def test_malformed_input_fails_closed(self):
        report = parse("malformed.html")
        self.assertEqual((report.parse_state, report.reason), ("PARSE_FAILED", "TRANSACTION_TABLE_NOT_FOUND"))
        garbage = senate.parse_report("<html><body>nothing here</body></html>")
        self.assertEqual(garbage.parse_state, "PARSE_FAILED")
        self.assertEqual(garbage.reason, "REPORT_ID_UNKNOWN")
        self.assertTrue(garbage.report_id.startswith("sha256:"))

    def test_unknown_type_and_bad_band_rows(self):
        html = (FIXTURES / "ptr_electronic.html").read_text().replace("<td>Exchange</td>", "<td>Gift</td>").replace(
            "$1,001 - $15,000", "$15,000 - $1,001")
        report = senate.parse_report(html)
        self.assertEqual(report.parse_state, "PARTIALLY_PARSED")
        self.assertEqual(report.reason, "SOME_ROWS_UNRECOGNIZED;SOME_ROW_FIELDS_UNPARSED")
        self.assertEqual(len(report.transactions), 3)
        self.assertIsNone(report.transactions[0].amount)
        self.assertIn("AMOUNT_RANGE_UNPARSED", report.transactions[0].quality_flags)

    def test_columns_are_found_by_header_not_position(self):
        header = ["Amount", "Type", "Asset Type", "Asset Name", "Ticker", "Owner", "Transaction Date", "#"]
        cells = ["$1,001 - $15,000", "Purchase", "Stock", "Apple Inc.", "AAPL", "Self", "01/05/2026", "1"]
        html = ('<!-- saved from url=(0086)https://efdsearch.senate.gov/search/view/ptr/5f3a1c2e-0000-4000-8000-00000000e001/ -->'
                "<h1>Periodic Transaction Report for 01/29/2026</h1><h2>The Honorable Jane Q Example</h2>"
                "<p>Filed 01/30/2026 @ 3:45 PM</p><table><thead><tr>" + "".join(f"<th>{item}</th>" for item in header)
                + "</tr></thead><tbody><tr>" + "".join(f"<td>{item}</td>" for item in cells) + "</tr></tbody></table>")
        report = senate.parse_report(html)
        self.assertEqual(report.parse_state, "PARSED")                      # no Comment column: still parsed
        txn = report.transactions[0]
        reference = parse("ptr_electronic.html").transactions[0]
        for name in ("owner", "disclosed_ticker", "asset_description", "asset_type_code", "transaction_type",
                     "transaction_date", "amount"):
            self.assertEqual(getattr(txn, name), getattr(reference, name), name)

    def test_no_transactions_statement(self):
        html = ('<!-- saved from url=(0086)https://efdsearch.senate.gov/search/view/ptr/5f3a1c2e-0000-4000-8000-00000000d001/ -->'
                "<h1>Periodic Transaction Report for 01/02/2026</h1><h2>The Honorable Jane Q Example</h2>"
                "<p>Filed 01/03/2026 @ 8:00 AM</p><p>No transactions to report.</p>")
        report = senate.parse_report(html)
        self.assertEqual((report.parse_state, report.reason), ("NO_TRANSACTIONS", "REPORT_STATES_NO_TRANSACTIONS"))


class ImportBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "senate"
        self.dir.mkdir()
        for item in FIXTURES.glob("*.html"):
            shutil.copy(item, self.dir / item.name)

    def attest(self) -> None:
        (self.dir / senate.ATTESTATION_FILE).write_text(json.dumps({**ATTESTATION, "browser_session": "not-kept"}))

    def test_not_configured_means_terms_acceptance_required(self):
        state = senate.scan_import(None)
        self.assertEqual((state.state, state.reason), ("TERMS_ACCEPTANCE_REQUIRED", senate.TERMS_REASON))
        missing = senate.scan_import(self.dir / "nope")
        self.assertEqual((missing.state, missing.reason), ("NOT_CONFIGURED", "SENATE_EFD_IMPORT_DIR_MISSING"))

    def test_nothing_is_read_without_the_operators_attestation(self):
        state = senate.scan_import(self.dir)
        self.assertEqual((state.state, state.reason, state.reports), ("TERMS_ACCEPTANCE_REQUIRED", "OPERATOR_ATTESTATION_MISSING", []))
        (self.dir / senate.ATTESTATION_FILE).write_text(json.dumps({"accepted_by": "operator"}))  # incomplete
        self.assertEqual(senate.scan_import(self.dir).state, "TERMS_ACCEPTANCE_REQUIRED")

    def test_import_with_attestation(self):
        self.attest()
        state = senate.scan_import(self.dir)
        self.assertEqual((state.state, state.reason), ("PARTIAL", "SOME_REPORTS_FAILED"))   # malformed.html
        self.assertEqual(state.attestation, ATTESTATION)                                     # nothing else is kept
        coverage = state.coverage()
        self.assertEqual((coverage["reports_total"], coverage["parsed"], coverage["scanned_unparsed"], coverage["failed"]),
                         (4, 2, 1, 1))
        self.assertEqual((coverage["transaction_count"], coverage["amendments"]), (5, 1))
        (self.dir / "malformed.html").unlink()
        self.assertEqual(senate.scan_import(self.dir).state, "READY")

    def test_duplicate_saves_count_once_and_conflicts_fail_closed(self):
        self.attest()
        shutil.copy(self.dir / "ptr_electronic.html", self.dir / "ptr_electronic (1).html")
        state = senate.scan_import(self.dir)
        self.assertEqual(state.duplicates, 1)
        self.assertEqual(sum(1 for report in state.reports if report.report_id.endswith("a001")), 1)
        tampered = (self.dir / "ptr_electronic.html").read_text().replace("$1,001 - $15,000", "$100,001 - $250,000")
        (self.dir / "ptr_electronic (2).html").write_text(tampered)
        conflicted = senate.scan_import(self.dir)
        report = next(item for item in conflicted.reports if item.report_id.endswith("a001"))
        self.assertEqual((report.parse_state, report.reason, report.transactions), ("PARSE_FAILED", "DUPLICATE_REPORT_CONFLICT", ()))
        self.assertEqual(conflicted.conflicts, ["5f3a1c2e-0000-4000-8000-00000000a001"])

    def test_retrieval_clock_from_operator_sidecar(self):
        self.attest()
        (self.dir / "ptr_electronic.html.json").write_text(json.dumps({"retrieved_at": "2026-02-01T10:00:00Z"}))
        report = next(item for item in senate.scan_import(self.dir).reports if item.report_id.endswith("a001"))
        self.assertEqual((report.retrieved_at, report.retrieved_basis),
                         (datetime(2026, 2, 1, 10, tzinfo=UTC), "operator_sidecar.retrieved_at"))


class NormalizedContractTests(unittest.TestCase):
    def test_senate_rows_share_the_house_contract(self):
        report = parse("ptr_electronic.html")
        items = normalized.from_senate(report)
        rows = normalized.to_rows(items)
        first = rows[0]
        for key in ("id", "chamber", "member", "owner", "asset_description", "disclosed_ticker", "asset_type_code",
                    "transaction_type", "transaction_date", "notification_date", "filing_date", "available_at",
                    "available_basis", "date_quality", "retrieved_at", "imp_known_at", "amount", "parse_state",
                    "source_url", "source_provider", "evidence_class", "quality_flags"):
            self.assertIn(key, first)
        self.assertEqual((first["chamber"], first["source_provider"], first["notification_date"]), ("SENATE", "senate_efd", None))
        self.assertEqual((first["filing_date"], first["filed_at"], first["available_at"]),
                         ("2026-01-30", "2026-01-30T20:45:00Z", "2026-01-30T20:45:00Z"))
        self.assertEqual(first["member"]["source_name"], "Jane Q Example")
        self.assertEqual(first["member"]["resolution"], "UNRESOLVED")    # a filer name alone is not identity evidence
        self.assertEqual(first["source_specific"]["transaction_type_text"], "Purchase")
        self.assertNotIn("value", first["amount"])
        self.assertEqual(first["disclosure_lag_days"], 25)

    def test_amendment_versions_as_of(self):
        items = normalized.from_senate(parse("ptr_electronic.html")) + normalized.from_senate(parse("ptr_amendment.html"))
        before = normalized.versions_as_of(items, datetime(2026, 2, 5, tzinfo=UTC))
        (key, state), = before.items()
        self.assertEqual((state["current"], state["superseded"]), ("5f3a1c2e-0000-4000-8000-00000000a001", []))
        after = normalized.versions_as_of(items, datetime(2026, 2, 11, tzinfo=UTC))
        self.assertEqual(after[key]["current"], "5f3a1c2e-0000-4000-8000-00000000a002")
        self.assertEqual(after[key]["superseded"], ["5f3a1c2e-0000-4000-8000-00000000a001"])
        rows = normalized.to_rows(items, now=datetime(2026, 2, 11, tzinfo=UTC))
        original = [row for row in rows if row["doc_id"].endswith("a001")]
        self.assertEqual(len(original), 4)                          # the earlier public record is never erased
        self.assertTrue(all(row["version"]["superseded"] for row in original))


if __name__ == "__main__":
    unittest.main()

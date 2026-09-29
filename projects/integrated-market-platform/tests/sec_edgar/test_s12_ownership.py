"""S12 SEC ownership evidence: Form 4, Schedule 13D/13G, 13F, EDGAR daily index, 13F data-set index.

Fixtures are real EDGAR documents (NVIDIA Form 4, a live 13G) and the SEC's own
published technical-specification samples (13D, 13F information table).
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.news.sec_filings_news import EVENT_FORMS, is_issuer_event  # noqa: E402
from market_platform_foundation.sec_edgar import ownership as o  # noqa: E402
from market_platform_foundation.sec_edgar.filing import FilingEvent  # noqa: E402
from market_platform_foundation.sec_edgar.thirteen_f_index import (  # noqa: E402
    ThirteenFIndex, build_index, parse_sec_date, select_reports,
)

FIXTURES = ROOT / "tests" / "fixtures" / "sec_edgar" / "ownership"


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class Form4Tests(unittest.TestCase):
    def test_real_form4(self):
        filing = o.parse_form4(fixture("form4_nvda.xml"))
        self.assertEqual((filing.issuer_cik, filing.issuer_symbol, filing.period_of_report),
                         ("0001045810", "NVDA", "2026-09-21"))
        self.assertEqual(filing.owners[0]["roles"], ["Officer"])
        self.assertTrue(filing.rule_10b5_1)
        first = filing.transactions[0]
        self.assertEqual((first.code, first.acquired_disposed, first.shares, first.price_per_share, first.direct_or_indirect),
                         ("S", "D", 12483.0, 222.1932, "I"))
        self.assertEqual(first.code_label, "Open market or private sale")
        self.assertEqual(first.shares_owned_after, 2705637.0)

    def test_wrong_root_rejected(self):
        with self.assertRaises(ValueError):
            o.parse_form4(b"<edgarSubmission/>")

    def test_raw_xml_document_strips_xsl_rendering(self):
        self.assertEqual(o.raw_xml_document("xslF345X06/wk-form4_1.xml"), "wk-form4_1.xml")
        with self.assertRaises(ValueError):
            o.raw_xml_document("d12345.txt")


class BeneficialOwnershipTests(unittest.TestCase):
    def test_live_13g_joint_filers_are_flagged_not_additive(self):
        filing = o.parse_schedule_13dg(fixture("schedule13g_live.xml"))
        self.assertEqual((filing.schedule, filing.is_amendment, filing.event_date), ("13G", False, "2026-09-18"))
        self.assertEqual(filing.issuer_cusips, ("05589G102",))
        self.assertEqual([person.percent_of_class for person in filing.reporting_persons], [5.35, 5.35])
        self.assertIn("JOINT_FILERS_REPORT_SAME_POSITION_NOT_ADDITIVE", filing.quality_flags)

    def test_official_13d_sample(self):
        filing = o.parse_schedule_13dg(fixture("sample_schedule13d.xml"))
        self.assertEqual(filing.schedule, "13D")
        self.assertEqual(filing.issuer_cik, "0001118676")
        self.assertEqual(filing.event_date, "2023-06-07")
        self.assertEqual(len(filing.issuer_cusips), 3)
        self.assertEqual(filing.reporting_persons[1].percent_of_class, 23.6)


class ThirteenFTests(unittest.TestCase):
    def test_information_table_and_share_aggregation_excludes_options(self):
        holdings = o.parse_13f_information_table(fixture("sample_13f_information_table.xml"))
        self.assertEqual(len(holdings), 169)
        self.assertEqual(holdings[0].cusip, "00206R102")
        option = o.ThirteenFHolding("X", "COM", "00206R102", None, 10.0, 999.0, "SH", "Call", "SOLE")
        position = o.aggregate_13f_position(holdings + [option], "00206r102")
        self.assertEqual(position["shares"], 79296.0)
        self.assertIsNone(o.aggregate_13f_position(holdings, "000000000"))

    def test_change_classes(self):
        self.assertEqual(o.classify_reported_change(None, 100)["change"], "NEW")
        self.assertEqual(o.classify_reported_change(100, 0)["change"], "EXITED")
        self.assertEqual(o.classify_reported_change(100, 150)["change"], "INCREASED")
        self.assertEqual(o.classify_reported_change(100, 50)["change"], "DECREASED")
        self.assertEqual(o.classify_reported_change(100, 100)["change"], "UNCHANGED")
        split = o.classify_reported_change(100, 400)
        self.assertEqual((split["change"], split["flags"]), ("INCREASED", ["SPLIT_LIKE_RATIO"]))
        missing = o.classify_reported_change(None, 100, prior_available=False)
        self.assertEqual((missing["class"], missing["change"]), ("INSUFFICIENT_EVIDENCE", None))
        self.assertIn("not a purchase or sale", o.CHANGE_METHOD)


class DailyIndexTests(unittest.TestCase):
    def entries(self):
        return o.parse_daily_form_index(fixture("form.20260925.sample.idx").decode("latin-1"),
                                        forms=o.INSIDER_FORMS | o.BENEFICIAL_FORMS)

    def test_parse_and_filter(self):
        entries = self.entries()
        self.assertEqual(len(entries), 17)  # the two 10-Q rows are filtered out
        self.assertEqual(entries[0].accession, "0001535264-26-000053")
        self.assertEqual(entries[0].date_filed, date(2026, 9, 25))

    def test_self_submitted_13d_filer_is_never_the_subject(self):
        # Howard Amster submitted a 13D under his own CIK about Redwood Trust: only Redwood is a subject.
        issuers = {"0000904853": "AMSTER", "0000930236": "RWT"}
        grouped = o.group_index_filings(self.entries(), issuers)
        rows = [row for row in grouped if row["accession"] == "0000904853-26-000006"]
        self.assertEqual([(row["issuer_cik"], row["role_basis"]) for row in rows], [("0000930236", "SINGLE_CANDIDATE")])
        self.assertEqual(rows[0]["filers"], ["Amster Howard"])

    def test_two_listed_companies_mark_role_unverified(self):
        # Berkshire (and Buffett) reported Lennar shares; both companies are listed.
        listed = {"0001067983", "0000920760"}
        grouped = o.group_index_filings(self.entries(), {"0001067983": "BRK-B"}, listed_ciks=listed)
        row = next(row for row in grouped if row["accession"] == "0001193125-26-403089")
        self.assertEqual(row["role_basis"], "ROLE_UNVERIFIED")
        alone = o.group_index_filings(self.entries(), {"0000920760": "LEN"}, listed_ciks={"0000920760"})
        self.assertEqual(next(r for r in alone if r["accession"] == "0001193125-26-403089")["role_basis"], "SINGLE_CANDIDATE")

    def test_filing_with_no_universe_issuer_is_dropped(self):
        self.assertEqual(o.group_index_filings(self.entries(), {}), [])
        self.assertTrue(o.filing_index_url("0000930236", "0000904853-26-000006").endswith(
            "/930236/000090485326000006/0000904853-26-000006-index.html"))


class SecNewsIssuerEventTests(unittest.TestCase):
    """S11 regression found in S12: a company's own 13G stake in another issuer is not its news."""

    def filing(self, form: str, accession: str) -> FilingEvent:
        return FilingEvent(cik="0001045810", entity_name="NVIDIA CORP", form_type=form, family="", raw_accession=accession,
                           normalized_accession=accession, filing_date="2026-07-20", report_date="",
                           acceptance_datetime="2026-07-20T21:00:07.000Z", observed_time="", primary_document="primary_doc.xml",
                           items=(), item_labels={}, is_amendment=False, amends_accession="", is_xbrl=False,
                           available_time="", available_time_ns=0)

    def test_new_schedule_form_names_are_events(self):
        for form in ("SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A"):
            self.assertIn(form, EVENT_FORMS)

    def test_self_submitted_13g_is_excluded(self):
        self.assertFalse(is_issuer_event(self.filing("SCHEDULE 13G", "0001045810-26-000062"), "0001045810"))
        self.assertTrue(is_issuer_event(self.filing("SCHEDULE 13G", "0000932471-26-000001"), "0001045810"))
        self.assertTrue(is_issuer_event(self.filing("8-K", "0001045810-26-000063"), "0001045810"))
        self.assertFalse(is_issuer_event(self.filing("S-8", "0001045810-26-000064"), "0001045810"))


def data_set(submissions: list[tuple], covers: list[tuple], lines: list[tuple]) -> bytes:
    def tsv(header: str, rows: list[tuple]) -> str:
        return header + "\n" + "".join("\t".join(str(value) for value in row) + "\n" for row in rows)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("SUBMISSION.tsv", tsv("ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT", submissions))
        archive.writestr("COVERPAGE.tsv", tsv("ACCESSION_NUMBER\tAMENDMENTTYPE\tFILINGMANAGER_NAME\tREPORTTYPE", covers))
        archive.writestr("INFOTABLE.tsv", tsv("ACCESSION_NUMBER\tCUSIP\tVALUE\tSSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL", lines))
    return buffer.getvalue()


CUSIP = "67066G104"
HR, NT = "13F HOLDINGS REPORT", "13F NOTICE REPORT"


class ThirteenFIndexTests(unittest.TestCase):
    """Built from synthetic data sets in the SEC's own TSV layout."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        q1 = data_set(
            [("A-1", "14-MAY-2026", "13F-HR", "1", "31-MAR-2026"), ("B-1", "15-MAY-2026", "13F-HR", "2", "31-MAR-2026"),
             ("C-1", "10-MAY-2026", "13F-HR", "3", "31-MAR-2026"), ("D-1", "12-MAY-2026", "13F-HR", "4", "31-MAR-2026")],
            [("A-1", "", "Alpha Capital", HR), ("B-1", "", "Beta Advisors", HR), ("C-1", "", "Gamma LP", HR),
             ("D-1", "", "Delta Mgmt", HR)],
            [("A-1", CUSIP, 1000, 100, "SH", ""), ("B-1", CUSIP, 2000, 200, "SH", ""), ("C-1", CUSIP, 500, 50, "SH", ""),
             ("D-1", CUSIP, 300, 30, "SH", "")])
        q2 = data_set(
            [("A-2", "07-AUG-2026", "13F-HR", "1", "30-JUN-2026"), ("B-2", "13-AUG-2026", "13F-HR", "2", "30-JUN-2026"),
             ("B-3", "20-AUG-2026", "13F-HR/A", "2", "30-JUN-2026"), ("C-2", "12-AUG-2026", "13F-HR", "3", "30-JUN-2026"),
             ("E-2", "01-AUG-2026", "13F-HR", "5", "30-JUN-2026"), ("N-2", "01-AUG-2026", "13F-NT", "6", "30-JUN-2026"),
             ("A-3", "21-AUG-2026", "13F-HR/A", "1", "30-JUN-2026")],
            [("A-2", "", "Alpha Capital", HR), ("B-2", "", "Beta Advisors", HR),
             ("B-3", "RESTATEMENT", "Beta Advisors", HR), ("C-2", "", "Gamma LP", HR), ("E-2", "", "Epsilon", HR),
             ("N-2", "", "Notice Only", NT), ("A-3", "NEW HOLDINGS", "Alpha Capital", HR)],
            [("A-2", CUSIP, 1500, 150, "SH", ""), ("A-2", CUSIP, 99, 999, "SH", "Put"),
             ("B-2", CUSIP, 9999, 999, "SH", ""), ("B-3", CUSIP, 4000, 400, "SH", ""),
             ("C-2", "000000000", 1, 1, "SH", ""), ("E-2", CUSIP, 700, 70, "SH", ""), ("E-2", CUSIP, 5, 5, "PRN", ""),
             ("A-3", CUSIP, 100, 10, "SH", "")])
        (root / "q1.zip").write_bytes(q1)
        (root / "q2.zip").write_bytes(q2)
        self.stats = build_index([root / "q1.zip", root / "q2.zip"], root / "index.sqlite")
        self.index = ThirteenFIndex.load(root / "index.sqlite")
        self.addCleanup(self.index._db.close)

    def test_dates(self):
        self.assertEqual(parse_sec_date("31-JUL-2026"), date(2026, 7, 31))
        self.assertIsNone(parse_sec_date("2026-07-31"))

    def test_amendments_restatement_replaces_new_holdings_adds(self):
        subs = {"X": {"cik": "1", "period": date(2026, 6, 30), "filing_date": date(2026, 8, 1), "report_type": HR,
                      "amendment_type": ""},
                "Y": {"cik": "1", "period": date(2026, 6, 30), "filing_date": date(2026, 8, 5), "report_type": HR,
                      "amendment_type": "RESTATEMENT"},
                "Z": {"cik": "1", "period": date(2026, 6, 30), "filing_date": date(2026, 8, 9), "report_type": HR,
                      "amendment_type": "NEW HOLDINGS"}}
        self.assertEqual(sorted(select_reports(subs)), ["Y", "Z"])

    def test_section_after_the_filing_window(self):
        section = self.index.section([CUSIP], now=datetime(2026, 9, 28, tzinfo=UTC))
        self.assertEqual((section["state"], section["period"], section["prior_period"]),
                         ("CURRENT_AS_FILED", "2026-06-30", "2026-03-31"))
        holders = {item["manager"]: item for item in section["holders"]}
        # Beta: restatement (400) replaces the original (999). Alpha: 150 + NEW HOLDINGS 10; the put line is excluded.
        self.assertEqual(holders["Beta Advisors"]["shares"], 400)
        self.assertEqual(holders["Alpha Capital"]["shares"], 160)
        self.assertEqual(holders["Alpha Capital"]["change"]["change"], "INCREASED")
        self.assertEqual(holders["Epsilon"]["change"]["class"], "INSUFFICIENT_EVIDENCE")  # no prior filing loaded
        self.assertEqual(holders["Epsilon"]["shares"], 70)  # PRN principal is not shares
        # Gamma filed Q2 without the CUSIP -> EXITED; Delta has not filed Q2 -> not counted.
        self.assertEqual(section["change_counts"]["EXITED"], 1)
        self.assertNotIn("Delta Mgmt", holders)
        self.assertEqual(section["holders"][0]["manager"], "Beta Advisors")
        self.assertEqual(holders["Beta Advisors"]["available_at"], "2026-08-21T00:00:00Z")

    def test_no_lookahead_before_filings_are_public(self):
        early = self.index.section([CUSIP], now=datetime(2026, 8, 8, 12, tzinfo=UTC))
        self.assertEqual((early["state"], early["reason"]), ("PARTIAL", "FILING_WINDOW_OPEN"))
        self.assertEqual({item["manager"] for item in early["holders"]}, {"Alpha Capital", "Epsilon"})
        self.assertEqual(next(i for i in early["holders"] if i["manager"] == "Alpha Capital")["shares"], 150)
        before = self.index.section([CUSIP], now=datetime(2026, 5, 11, 12, tzinfo=UTC))  # only Gamma (filed 5/10) is public
        self.assertEqual((before["period"], before["prior_period"]), ("2026-03-31", None))
        self.assertEqual([(item["manager"], item["shares"]) for item in before["holders"]], [("Gamma LP", 50)])
        none = self.index.section([CUSIP], now=datetime(2026, 5, 1, tzinfo=UTC))
        self.assertEqual(none["state"], "NO_DISCLOSURES")

    def test_report_counts(self):
        self.assertEqual(self.stats["holdings_reports"], 10)  # the notice report carries no holdings

    def test_restatement_is_not_visible_before_it_was_filed(self):
        mid = self.index.section([CUSIP], now=datetime(2026, 8, 15, tzinfo=UTC))
        beta = next(item for item in mid["holders"] if item["manager"] == "Beta Advisors")
        self.assertEqual(beta["shares"], 999)  # the original, as public before the 8/20 restatement

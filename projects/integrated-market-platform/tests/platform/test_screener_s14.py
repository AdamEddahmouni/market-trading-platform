"""Screener S14 service integration: disclosure coverage, identity, and refresh state on S12 surfaces.

Reuses the S12 service harness (real House Clerk fixtures, fake SEC). Senate reports
are the SYNTHETIC eFD fixtures, re-dated into the test window. 13F generations are
built by the S14 lifecycle from synthetic data sets. Nothing touches the network.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_screener_s12 as s12  # noqa: E402  (the S12 service harness and fixtures)
from market_platform_foundation.congressional_ptr import senate  # noqa: E402
from market_platform_foundation.public_records.http import PublicRecordsHttp  # noqa: E402
from market_platform_foundation.sec_edgar import thirteen_f_lifecycle as lc  # noqa: E402
from market_platform_foundation.ui_api.screener_participants import HousePtrLoader, ScreenerParticipantService  # noqa: E402
from market_platform_foundation.ui_api.screener_squeeze_sources import BackgroundCache  # noqa: E402

SENATE_FIXTURES = ROOT / "tests" / "fixtures" / "congressional_disclosure" / "senate_efd"
HOUSE_FIXTURES = ROOT / "tests" / "fixtures" / "congressional_disclosure" / "house_ptr"
NVDA_CUSIP = "05589G102"   # the issuer CUSIP the S12 13D fixture carries
W1, W2 = "01mar2026-31may2026_form13f.zip", "01jun2026-31aug2026_form13f.zip"


def senate_dir(root: Path, *, attest: bool = True, malformed: bool = False) -> Path:
    target = root / "senate"
    target.mkdir()
    for item in SENATE_FIXTURES.glob("*.html"):
        if item.name == "malformed.html" and not malformed:
            continue
        text = item.read_text(encoding="utf-8").replace("Filed 01/30/2026", "Filed 09/20/2026").replace(
            "Filed 02/10/2026", "Filed 09/25/2026")
        (target / item.name).write_text(text, encoding="utf-8")
    if attest:
        (target / senate.ATTESTATION_FILE).write_text(json.dumps({"accepted_by": "operator", "accepted_at": "2026-09-27T12:00:00Z"}))
    return target


def custom_index(members: list[tuple[str, str, str, str, str]]) -> bytes:
    """A House filing index (Clerk XML layout) mapping synthetic names/seats onto the real PTR PDFs."""

    body = "".join(f"<Member><Prefix>{prefix}</Prefix><Last>{last}</Last><First>{first}</First><Suffix>{suffix}</Suffix>"
                   f"<FilingType>P</FilingType><StateDst>{seat}</StateDst><Year>2026</Year>"
                   f"<FilingDate>9/14/2026</FilingDate><DocID>{doc}</DocID></Member>"
                   for prefix, first, last, suffix, seat, doc in members)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("2026FD.xml", f'<?xml version="1.0" encoding="utf-8"?><FinancialDisclosure>{body}</FinancialDisclosure>')
    return buffer.getvalue()


class CustomRequester(s12.HouseRequester):
    def __init__(self, index: bytes) -> None:
        super().__init__()
        self.index = index

    def __call__(self, url, body, headers, timeout):
        if url.endswith("FD.zip"):
            self.urls.append(url)
            return 200, self.index
        return super().__call__(url, body, headers, timeout)


def service(env: dict, *, requester=None, thirteen_f=None, house_fail=False):
    if requester is None and not house_fail:
        return s12.service(env, thirteen_f=thirteen_f)
    sync = lambda job: job()  # noqa: E731
    clock = lambda: s12.NOW  # noqa: E731
    requester = requester or s12.HouseRequester(fail_index=True)
    public = PublicRecordsHttp(requester=requester, min_interval_s=0.0)
    return ScreenerParticipantService(
        catalog=lambda universe: (s12.CATALOG.get(universe, []), None), row_for=s12.row_for,
        sec_transport_factory=lambda: s12.FakeSec(), public_http=public, cot_query=s12.cot_query, cot_last_report=s12.cot_last_report,
        house_loader=HousePtrLoader(http=public, clock=clock, spawn=sync), usaspending=s12.FakeSpending(),
        lobbying=s12.FakeLobbying(), thirteen_f=thirteen_f, cache=BackgroundCache(clock=clock, spawn=sync), clock=clock,
        wait_s=0.0, env=env.get)


class SenateOnScreenerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def env(self, **extra):
        return {**s12.SEC_ENV, **extra}

    def test_default_is_terms_acceptance_required_on_every_surface(self):
        svc = service(self.env())
        view = svc.congress_view(universe="US_EQUITIES")
        senate_provider = view["providers"][1]
        self.assertEqual((senate_provider["id"], senate_provider["state"], senate_provider["reason"]),
                         ("senate_efd", "TERMS_ACCEPTANCE_REQUIRED", senate.TERMS_REASON))
        self.assertEqual(view["coverage"]["chambers"], ["HOUSE"])
        panel = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AMAT", lens="congress_gov")
        self.assertIn("accept its terms", panel["sections"]["congressional"]["note"])
        self.assertEqual([item["state"] for item in panel["sections"]["congressional"]["sources"]],
                         ["PUBLICATION_CURRENT", "TERMS_ACCEPTANCE_REQUIRED"])

    def test_imported_senate_reports_join_house_rows(self):
        svc = service(self.env(IMP_SENATE_EFD_IMPORT_DIR=str(senate_dir(self.root))))
        view = svc.congress_view(universe="US_EQUITIES", window="60d")
        self.assertEqual({item["id"]: item["state"] for item in view["providers"]},
                         {"house_ptr": "PUBLICATION_CURRENT", "senate_efd": "READY"})
        self.assertEqual((view["state"], view["reason"]), ("PUBLICATION_CURRENT", None))
        self.assertEqual(view["coverage"]["chambers"], ["HOUSE", "SENATE"])
        senate_rows = [row for row in view["rows"] if row["chamber"] == "SENATE"]
        self.assertEqual({row["instrument"]["symbol"] for row in senate_rows}, {"NVDA", "MSFT"})   # AAPL is not in the universe
        msft = next(row for row in senate_rows if row["instrument"]["symbol"] == "MSFT")
        self.assertTrue(msft["instrument"]["is_option"])
        self.assertEqual(msft["available_basis"], "senate_efd.filed_timestamp_et")
        self.assertEqual(view["coverage"]["senate"]["amendments"], 1)
        panel = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:NVDA", lens="congress_gov")
        section = panel["sections"]["congressional"]
        self.assertEqual(section["chambers"], ["HOUSE", "SENATE"])
        self.assertEqual({row["chamber"] for row in section["transactions"]}, {"SENATE"})

    def test_window_counts_separate_house_filings_from_each_chambers_transactions(self):
        # Final closure: the coverage sentence used to start from the House *filing* count of the loaded window but
        # count "no ticker" *transactions* of both chambers in the selected window. Counts are now per chamber and
        # per selected window, and every transaction lands in exactly one bucket.
        env = self.env(IMP_SENATE_EFD_IMPORT_DIR=str(senate_dir(self.root)))
        view = service(env).congress_view(universe="US_EQUITIES", window="60d")
        coverage, counts = view["coverage"], view["coverage"]["window_counts"]
        self.assertTrue(counts["senate_in_view"])
        self.assertGreater(counts["senate_transactions"], 0)
        self.assertEqual(counts["house_transactions"] + counts["senate_transactions"], coverage["transactions_in_window"])
        self.assertEqual(coverage["matched"] + coverage["ticker_outside_universe"] + coverage["no_disclosed_ticker"],
                         coverage["transactions_in_window"])
        self.assertEqual(counts["house_filings"], counts["house_machine_readable"] + counts["house_scanned"]
                         + counts["house_unreadable"] + counts["house_loading"])
        self.assertLessEqual(counts["house_filings"], coverage["filings"])
        # A window after every fixture filing: the loaded House figure stays, the window figures are zero.
        later = service(env)
        later._clock = lambda: datetime(2027, 3, 1, tzinfo=UTC).timestamp()
        empty = later.congress_view(universe="US_EQUITIES", window="30d")["coverage"]["window_counts"]
        self.assertEqual((empty["house_filings"], empty["house_transactions"], empty["senate_transactions"]), (0, 0, 0))

    def test_one_failing_source_never_erases_the_other(self):
        svc = service(self.env(IMP_SENATE_EFD_IMPORT_DIR=str(senate_dir(self.root))), house_fail=True)
        view = svc.congress_view(universe="US_EQUITIES")
        self.assertEqual({item["id"]: item["state"] for item in view["providers"]},
                         {"house_ptr": "SOURCE_ERROR", "senate_efd": "READY"})
        self.assertEqual((view["state"], view["reason"]), ("PARTIAL", "HOUSE_SOURCE_ERROR"))
        self.assertTrue(view["rows"])
        self.assertEqual({row["chamber"] for row in view["rows"]}, {"SENATE"})

    def test_partial_import_is_reported(self):
        svc = service(self.env(IMP_SENATE_EFD_IMPORT_DIR=str(senate_dir(self.root, malformed=True))))
        view = svc.congress_view(universe="US_EQUITIES")
        self.assertEqual(view["providers"][1]["state"], "PARTIAL")
        self.assertEqual(view["providers"][1]["coverage"]["failed"], 1)
        self.assertEqual((view["state"], view["reason"]), ("PARTIAL", "SENATE_PARTIAL"))

    def test_unattested_directory_is_not_read(self):
        svc = service(self.env(IMP_SENATE_EFD_IMPORT_DIR=str(senate_dir(self.root, attest=False))))
        view = svc.congress_view(universe="US_EQUITIES")
        self.assertEqual((view["providers"][1]["state"], view["providers"][1]["reason"]),
                         ("TERMS_ACCEPTANCE_REQUIRED", "OPERATOR_ATTESTATION_MISSING"))
        self.assertFalse([row for row in view["rows"] if row["chamber"] == "SENATE"])


class IdentityOnScreenerTests(unittest.TestCase):
    def view(self):
        # Synthetic index: the same NJ05 seat under two spellings, plus a suffix variant and another seat.
        index = custom_index([("Hon.", "Josh", "Gottheimer", "", "NJ05", "20035455"),
                              ("", "Josh Mr", "Gottheimer", "", "NJ05", "20035420"),
                              ("Hon.", "Josh", "Gottheimer", "Jr", "NJ05", "20035408"),
                              ("Hon.", "Josh", "Gottheimer", "", "NJ06", "9116331")])
        svc = service(s12.SEC_ENV, requester=CustomRequester(index))
        return svc, svc.congress_view(universe="US_EQUITIES", window="60d")

    def test_filter_lists_a_resolved_member_once_and_keeps_rows_distinct(self):
        svc, view = self.view()
        members = view["filters"]["members"]
        nj05 = [item for item in members if item["id"] == "HOUSE-SEAT:NJ05:GOTTHEIMER:JOSH"]
        self.assertEqual(len(nj05), 1)
        self.assertEqual(nj05[0]["filed_as"], ["Josh Gottheimer", "Josh Mr Gottheimer"])
        self.assertEqual(nj05[0]["resolution"], "SEAT_AND_NAME")
        rows, _providers, _coverage, _filing_states = svc._congress()
        suffix_variant = {row["member"]["canonical_member_id"] for row in rows if row["doc_id"] == "20035408"}
        self.assertEqual(suffix_variant, {"HOUSE-SEAT:NJ05:GOTTHEIMER:JOSH:JR"})   # a suffix variant stays apart
        only = svc.congress_view(universe="US_EQUITIES", member="HOUSE-SEAT:NJ05:GOTTHEIMER:JOSH", limit=200)
        docs = {row["doc_id"] for row in only["rows"]}
        self.assertEqual(docs, {"20035455", "20035420"})
        self.assertEqual(len({row["id"] for row in only["rows"]}), only["result_count"])   # disclosures never collapse

    def test_raw_filed_name_is_kept(self):
        _svc, view = self.view()
        row = next(item for item in view["rows"] if item["doc_id"] == "20035420")
        member = row["member"]
        self.assertEqual((member["name"], member["source_name"]), ("Josh Gottheimer", "Josh Mr Gottheimer"))
        self.assertEqual(member["aliases"], ["Josh Gottheimer", "Josh Mr Gottheimer"])
        self.assertEqual(member["resolution"], "SEAT_AND_NAME")
        self.assertEqual(view["coverage"]["identity"]["resolutions"]["SEAT_AND_NAME"] > 0, True)

    def test_house_coverage_metrics_on_the_view(self):
        _svc, view = self.view()
        metrics = view["coverage"]["house"]
        self.assertEqual((metrics["documents_total"], metrics["scanned"], metrics["scanned_unparsed"]), (4, 1, 1))
        self.assertEqual(metrics["parsed"], 3)
        self.assertEqual(view["providers"][0]["coverage"], metrics)


class ManagedThirteenFTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "13f"
        sys.path.insert(0, str(ROOT / "tests" / "sec_edgar"))
        import test_s14_thirteen_f_lifecycle as data  # noqa: PLC0415

        self.data = data
        self.clock = data.Clock(datetime(2026, 9, 28, 14, tzinfo=UTC))
        base = data.BASE
        payloads = {
            base + W1: data.data_set([("A-1", "14-MAY-2026", "13F-HR", "1", "31-MAR-2026")],
                                     [("A-1", "", "Alpha Capital", data.HR)], [("A-1", NVDA_CUSIP, 1000, 100, "SH", "")]),
            base + W2: data.data_set([("A-2", "07-AUG-2026", "13F-HR", "1", "30-JUN-2026")],
                                     [("A-2", "", "Alpha Capital", data.HR)], [("A-2", NVDA_CUSIP, 1500, 150, "SH", "")]),
        }
        self.harness = data.Harness(self.root, (W1, W2), payloads=payloads)
        self.harness.clock = self.clock
        self.harness.store = lc.ThirteenFStore(self.root, clock=self.clock)
        result = self.harness.lifecycle().refresh()
        self.assertEqual(result["outcome"], "PUBLISHED")
        self.generation = result["generation"]

    def managed(self) -> lc.ManagedIndex:
        index = lc.ManagedIndex(self.root, clock=self.clock, recheck_s=0.0)
        self.addCleanup(lambda: index._index and index._index.close())
        return index

    def test_panel_shows_index_freshness_not_liveness(self):
        svc = s12.service(thirteen_f=self.managed())
        panel = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:NVDA", lens="institutional")
        section = panel["sections"]["holdings_13f"]
        self.assertEqual((section["state"], section["period"]), ("CURRENT_AS_FILED", "2026-06-30"))
        self.assertEqual(section["index"]["refresh_state"], "CURRENT_AS_FILED")
        self.assertEqual((section["index"]["indexed_through"], section["index"]["generation"]), ("2026-08-31", self.generation))
        provider = next(item for item in panel["providers"] if item["id"] == "thirteen_f")
        self.assertEqual((provider["published"], provider["refresh_state"]), ("data sets through 2026-08-31", "CURRENT_AS_FILED"))
        self.assertNotIn("live", json.dumps(section).lower())

    def test_refresh_available_is_a_refresh_state_not_a_data_failure(self):
        self.harness.names.append("01sep2026-30nov2026_form13f.zip")
        self.harness.lifecycle().check()
        section = s12.service(thirteen_f=self.managed()).instrument(
            universe="US_EQUITIES", instrument_id="EQ:NVDA", lens="institutional")["sections"]["holdings_13f"]
        self.assertEqual((section["state"], section["index"]["refresh_state"]), ("CURRENT_AS_FILED", "REFRESH_AVAILABLE"))

    def test_serves_previous_generation_while_refreshing_then_switches(self):
        managed = self.managed()
        store = lc.ThirteenFStore(self.root, clock=self.clock)
        store.acquire()
        during = managed.section([NVDA_CUSIP], now=datetime(2026, 9, 28, tzinfo=UTC))
        self.assertEqual((during["state"], during["index"]["refresh_state"]), ("CURRENT_AS_FILED", "REFRESHING"))
        self.assertEqual(during["index"]["generation"], self.generation)
        store.release()
        self.clock.advance(60)
        new = self.harness.lifecycle().refresh(force=True)
        after = managed.section([NVDA_CUSIP], now=datetime(2026, 9, 28, tzinfo=UTC))
        self.assertEqual(after["index"]["generation"], new["generation"])
        self.assertNotEqual(new["generation"], self.generation)

    def test_no_index_and_invalid_index_states(self):
        empty = lc.ManagedIndex(Path(self.tmp.name) / "none", clock=self.clock)
        self.assertEqual(empty.section([NVDA_CUSIP], now=datetime(2026, 9, 28, tzinfo=UTC))["state"], "NOT_CONFIGURED")
        manifest = lc.ThirteenFStore(self.root).generation_dir(self.generation) / "manifest.json"
        payload = json.loads(manifest.read_text())
        payload["index_bytes"] = 1
        manifest.write_text(json.dumps(payload))
        broken = lc.ManagedIndex(self.root, clock=self.clock)
        section = broken.section([NVDA_CUSIP], now=datetime(2026, 9, 28, tzinfo=UTC))
        self.assertEqual((section["state"], section["reason"]), ("INDEX_INVALID", "INDEX_SIZE_MISMATCH"))

    def test_request_path_never_discovers_or_downloads(self):
        before = sorted(path.name for path in self.root.iterdir())
        managed = self.managed()
        for _ in range(3):
            managed.section([NVDA_CUSIP], now=datetime(2026, 9, 28, tzinfo=UTC))
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), before)   # no check, no lock, no download


class RegressionGuardTests(unittest.TestCase):
    def test_no_evaluative_member_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = service({**s12.SEC_ENV, "IMP_SENATE_EFD_IMPORT_DIR": str(senate_dir(Path(tmp)))})
            text = json.dumps(svc.congress_view(universe="US_EQUITIES")).lower()
        for banned in ('"party', '"score', '"rank', "alpha", "performance", "smart money", "information advantage"):
            self.assertNotIn(banned, text)

    def test_fixture_house_pdfs_unchanged(self):
        # S14 adds no new House PDFs to the repository; the four S12 fixtures remain the only ones.
        self.assertEqual(sorted(path.name for path in HOUSE_FIXTURES.glob("*.pdf")),
                         ["20035408.pdf", "20035420.pdf", "20035455.pdf", "9116331.pdf"])


if __name__ == "__main__":
    unittest.main()

"""S12 Institutional, Whale, Congressional & Government intelligence: views, panels, preview, gates.

All sources are injected fakes over real fixtures (House Clerk PDFs, EDGAR documents
and daily index, CFTC rows, USAspending and LDA responses). No network.
"""

from __future__ import annotations

import io
import json
import sys
import unittest
import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.platform.security.route_policy import policy_for_route  # noqa: E402
from market_platform_foundation.public_records.http import PublicRecordsError, PublicRecordsHttp  # noqa: E402
from market_platform_foundation.public_records.lobbying import parse_filings  # noqa: E402
from market_platform_foundation.public_records.usaspending import parse_transactions  # noqa: E402
from market_platform_foundation.ui_api.screener_config import validate_panel_layout  # noqa: E402
from market_platform_foundation.ui_api.screener_participants import (  # noqa: E402
    EVIDENCE_BOUNDARIES, VIEWS, HousePtrLoader, ScreenerParticipantService,
)
from market_platform_foundation.ui_api.screener_squeeze_sources import BackgroundCache  # noqa: E402
from market_platform_foundation.ui_api.screener_universes import UNIVERSES, universe_payload, universe_spec  # noqa: E402

FIX = ROOT / "tests" / "fixtures"
NOW = datetime(2026, 9, 28, 14, 0, tzinfo=UTC).timestamp()
SEC_ENV = {"IMP_EDGAR_LIVE": "1", "SEC_USER_AGENT": "IMP Tests tests@example.test", "IMP_PUBLIC_RECORDS_LIVE": "1"}


def row(prefix, symbol, **extra):
    return {"instrument": {"instrument_id": f"{prefix}:{symbol}"}, "symbol": symbol, **extra}


CATALOG = {
    "US_EQUITIES": [row("EQ", "NVDA", company="NVIDIA Corporation"), row("EQ", "MSFT", company="Microsoft Corporation"),
                    row("EQ", "AMAT", company="Applied Materials, Inc."), row("EQ", "HWM", company="Howmet Aerospace Inc."),
                    row("EQ", "RWT", company="Redwood Trust, Inc."), row("EQ", "LMT", company="Lockheed Martin Corporation"),
                    row("EQ", "META", company="Meta Platforms, Inc."), row("EQ", "TGT", company="Target Corporation")],
    "US_ETFS": [row("ETF", "SPY", company="SPDR S&P 500 ETF Trust"), row("ETF", "QQQ", company="Invesco QQQ Trust")],
    "FUTURES": [row("FUT", "ESZ6", root="ES", company="E-mini S&P 500"), row("FUT", "CLX6", root="CL", company="Crude Oil"),
                row("FUT", "ZZZ6", root="ZZZ", company="Unmapped")],
    "BONDS": [row("UST", "91282CRF0")],
    "CRYPTO": [row("CR", "BTC/USD")],
}
ROWS = {item["instrument"]["instrument_id"]: (universe, item) for universe, items in CATALOG.items() for item in items}


def row_for(instrument_id, universe):
    found = ROWS.get(instrument_id)
    return found[1] if found and found[0] == universe else None


def house_index_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("2026FD.xml", (FIX / "congressional_disclosure" / "house_ptr" / "2026FD.sample.xml").read_bytes())
    return buffer.getvalue()


class HouseRequester:
    def __init__(self, fail_index=False):
        self.fail_index = fail_index
        self.urls = []

    def __call__(self, url, body, headers, timeout):
        self.urls.append(url)
        if url.endswith("FD.zip"):
            return (503, b"") if self.fail_index else (200, house_index_zip())
        doc = url.rsplit("/", 1)[-1]
        path = FIX / "congressional_disclosure" / "house_ptr" / doc
        return (200, path.read_bytes()) if path.exists() else (404, b"")


def submissions(cik: str, rows: list[tuple]) -> bytes:
    keys = ("accessionNumber", "form", "filingDate", "reportDate", "acceptanceDateTime", "primaryDocument")
    recent = {key: [item[index] for item in rows] for index, key in enumerate(keys)}
    return json.dumps({"cik": cik, "name": "NVIDIA CORP", "filings": {"recent": recent}}).encode()


class FakeSec:
    def __init__(self):
        self.urls = []
        own = FIX / "sec_edgar" / "ownership"
        self.docs = {
            "wk-form4.xml": (own / "form4_nvda.xml").read_bytes(),
            # The live 13G re-pointed at NVIDIA as the subject issuer, and an unmodified one (another issuer).
            "primary_doc.xml": (own / "schedule13g_live.xml").read_bytes().replace(b"0001781755", b"0001045810"),
            "other_issuer.xml": (own / "schedule13g_live.xml").read_bytes(),
        }

    def get(self, url, immutable=False):
        self.urls.append(url)
        if url.endswith("company_tickers.json"):
            return json.dumps({"0": {"cik_str": 1045810, "ticker": "NVDA"}, "1": {"cik_str": 930236, "ticker": "RWT"},
                               "2": {"cik_str": 1067983, "ticker": "BRK-B"}, "3": {"cik_str": 920760, "ticker": "LEN"},
                               "4": {"cik_str": 789019, "ticker": "MSFT"}}).encode()
        if url.endswith("form.20260925.idx"):
            return (FIX / "sec_edgar" / "ownership" / "form.20260925.sample.idx").read_bytes()
        if "/daily-index/" in url:
            raise OSError("SEC_HTTP_404")
        if url.endswith("CIK0001045810.json"):
            return submissions("1045810", [
                ("0001696841-26-000014", "4", "2026-09-23", "2026-09-21", "2026-09-23T20:56:28.000Z", "xslF345X06/wk-form4.xml"),
                ("0000932471-26-000001", "SCHEDULE 13G", "2026-09-10", "", "2026-09-10T16:00:00.000Z",
                 "xslSCHEDULE_13G_X01/primary_doc.xml"),
                ("0001045810-26-000062", "SCHEDULE 13G", "2026-07-20", "", "2026-07-20T21:00:07.000Z",
                 "xslSCHEDULE_13G_X01/other_issuer.xml"),
                ("0000932471-24-000002", "SC 13G/A", "2024-02-13", "", "2024-02-13T10:00:00.000Z", "d123.txt"),
                ("0001045810-26-000063", "8-K", "2026-09-01", "", "2026-09-01T20:00:00.000Z", "d8k.htm")])
        if url.endswith("CIK0000789019.json"):
            raise OSError("SEC_HTTP_503")
        name = url.rsplit("/", 1)[-1]
        if name in self.docs:
            return self.docs[name]
        raise OSError("SEC_HTTP_404")


class FakeSpending:
    def __init__(self):
        self.calls = 0

    def recipient_transactions(self, name, *, today, window_days):
        self.calls += 1
        contracts = parse_transactions(json.loads((FIX / "public_records" / "usaspending_transactions_contracts.json").read_text()),
                                       family="CONTRACT")
        grants = parse_transactions(json.loads((FIX / "public_records" / "usaspending_transactions_grants.json").read_text()),
                                    family="GRANT")
        return {"CONTRACT": {"rows": contracts, "has_more": True}, "GRANT": {"rows": grants, "has_more": False}}

    def last_updated(self):
        return "2026-09-28"


class FakeLobbying:
    def client_filings(self, name, *, today):
        return parse_filings(json.loads((FIX / "public_records" / "lda_filings.json").read_text())), 34


def cot_query(dataset, where):
    name = "s12_tff_futures_only_es.json" if dataset.name.startswith("TFF") else "s12_disaggregated_futures_only_cl.json"
    return json.loads((FIX / "cftc" / name).read_text())


#: Final closure: newest report date per market code (offline stand-in for the grouped CFTC query).
LAST_REPORTS = {"004603": "2026-07-14T00:00:00.000"}   # ZO (oats): known market, no report in the recent window


def cot_last_report(dataset, codes):
    return [{"cftc_contract_market_code": code, "last_report": LAST_REPORTS[code]} for code in codes if code in LAST_REPORTS]


class FakeThirteenF:
    def section(self, cusips, *, now):
        return {"state": "CURRENT_AS_FILED", "reason": None, "cusips": cusips, "holders": [], "period": "2026-06-30"}


def service(env=SEC_ENV, *, house_fail=False, thirteen_f=None, catalog=CATALOG):
    sync = lambda job: job()  # noqa: E731 — run background jobs inline for determinism
    clock = lambda: NOW  # noqa: E731
    requester = HouseRequester(fail_index=house_fail)
    public = PublicRecordsHttp(requester=requester, min_interval_s=0.0)
    sec = FakeSec()
    spending = FakeSpending()
    svc = ScreenerParticipantService(
        catalog=lambda universe: (catalog.get(universe, []), None), row_for=row_for, sec_transport_factory=lambda: sec,
        public_http=public, cot_query=cot_query, cot_last_report=cot_last_report, house_loader=HousePtrLoader(http=public, clock=clock, spawn=sync),
        usaspending=spending, lobbying=FakeLobbying(), thirteen_f=thirteen_f,
        cache=BackgroundCache(clock=clock, spawn=sync), clock=clock, wait_s=0.0, env=env.get)
    svc.fakes = {"sec": sec, "house": requester, "spending": spending}
    return svc


# ------------------------------------------------------------------ architecture
class ArchitectureTests(unittest.TestCase):
    def test_intelligence_is_not_a_universe(self):
        self.assertEqual(list(UNIVERSES), ["US_EQUITIES", "FUTURES", "US_ETFS", "BONDS", "CRYPTO"])
        for name in ("INSTITUTIONAL", "WHALES", "CONGRESS", "GOVERNMENT"):
            self.assertNotIn(name, UNIVERSES)

    def test_panels_and_views_by_universe(self):
        self.assertTrue({"institutional", "congress_gov"} <= set(universe_spec("US_EQUITIES").panels))
        self.assertTrue({"institutional", "congress_gov"} <= set(universe_spec("US_ETFS").panels))
        self.assertIn("institutional", universe_spec("FUTURES").panels)
        self.assertNotIn("congress_gov", universe_spec("FUTURES").panels)
        for universe in ("BONDS", "CRYPTO"):
            self.assertFalse({"institutional", "congress_gov"} & set(universe_spec(universe).panels))
        self.assertEqual(VIEWS, {"US_EQUITIES": ("ownership", "congress"), "FUTURES": ("positioning",),
                                 "US_ETFS": ("congress",)})
        payload = {item["id"]: item for item in universe_payload()}
        self.assertEqual(payload["BONDS"]["intelligence_views"], [])
        self.assertEqual(payload["US_EQUITIES"]["intelligence_views"], ["ownership", "congress"])

    def test_panel_layout_accepts_new_panels(self):
        layout = validate_panel_layout({"version": 1, "open_panels": ["institutional", "congress_gov"],
                                        "active_panel": "congress_gov", "dock_height": 300, "dockview_layout": None})
        self.assertEqual(layout["open_panels"], ["institutional", "congress_gov"])

    def test_routes_are_read_only(self):
        for path in ("/screener/participants/ownership", "/screener/participants/positioning",
                     "/screener/participants/congress", "/screener/participants/instrument"):
            self.assertEqual(policy_for_route("GET", path).capability, "state.read")


# ------------------------------------------------------------------ gates
class GateTests(unittest.TestCase):
    def test_live_disabled_makes_no_requests(self):
        svc = service(env={})
        view = svc.ownership_view(universe="US_EQUITIES")
        self.assertEqual((view["state"], view["reason"]), ("LIVE_DISABLED", "IMP_EDGAR_LIVE_NOT_SET"))
        congress = svc.congress_view(universe="US_EQUITIES")
        self.assertEqual(congress["state"], "LIVE_DISABLED")
        positioning = svc.positioning_view(universe="FUTURES")
        self.assertEqual(positioning["state"], "LIVE_DISABLED")
        self.assertEqual((svc.fakes["sec"].urls, svc.fakes["house"].urls), ([], []))

    def test_sec_user_agent_required(self):
        view = service(env={"IMP_EDGAR_LIVE": "1"}).ownership_view(universe="US_EQUITIES")
        self.assertEqual((view["state"], view["reason"]), ("NOT_CONFIGURED", "SEC_USER_AGENT_NOT_SET"))

    def test_views_only_where_universe_complete(self):
        svc = service()
        for universe, view in (("BONDS", "congress_view"), ("CRYPTO", "ownership_view"), ("FUTURES", "congress_view"),
                               ("US_ETFS", "ownership_view"), ("US_EQUITIES", "positioning_view")):
            with self.assertRaisesRegex(ValueError, "VIEW_UNAVAILABLE_FOR_UNIVERSE"):
                getattr(svc, view)(universe=universe)
        with self.assertRaisesRegex(ValueError, "UNKNOWN_UNIVERSE"):
            svc.congress_view(universe="WHALES")

    def test_invalid_parameters(self):
        svc = service()
        with self.assertRaisesRegex(ValueError, "INVALID_WINDOW"):
            svc.congress_view(universe="US_EQUITIES", window="7d")
        with self.assertRaisesRegex(ValueError, "INVALID_AMOUNT"):
            svc.congress_view(universe="US_EQUITIES", min_amount=12)
        with self.assertRaisesRegex(ValueError, "INVALID_TRANSACTION_TYPE"):
            svc.congress_view(universe="US_EQUITIES", transaction_type="BUY")
        with self.assertRaisesRegex(ValueError, "INVALID_PAGE"):
            svc.ownership_view(universe="US_EQUITIES", limit=1000)
        with self.assertRaisesRegex(ValueError, "INVALID_FAMILY"):
            svc.ownership_view(universe="US_EQUITIES", family="WHALE")
        with self.assertRaisesRegex(ValueError, "LENS_UNAVAILABLE_FOR_UNIVERSE"):
            svc.instrument(universe="BONDS", instrument_id="UST:91282CRF0", lens="institutional")
        with self.assertRaisesRegex(ValueError, "INVALID_LENS"):
            svc.instrument(universe="US_EQUITIES", instrument_id="EQ:NVDA", lens="whale_score")
        self.assertIsNone(svc.instrument(universe="US_EQUITIES", instrument_id="ETF:SPY", lens="institutional"))


# ------------------------------------------------------------------ Congress
class CongressViewTests(unittest.TestCase):
    def setUp(self):
        self.svc = service()
        self.view = self.svc.congress_view(universe="US_EQUITIES", window="60d")

    def test_rows_are_disclosures_matched_by_disclosed_ticker(self):
        view = self.view
        self.assertEqual(view["state"], "PARTIAL")      # House only: no Senate import (S14: terms acceptance required)
        self.assertEqual(view["reason"], "HOUSE_ONLY")
        self.assertEqual({item["id"]: item["state"] for item in view["providers"]},
                         {"house_ptr": "PUBLICATION_CURRENT", "senate_efd": "TERMS_ACCEPTANCE_REQUIRED"})
        symbols = {item["instrument"]["symbol"] for item in view["rows"]}
        self.assertEqual(symbols, {"AMAT", "MSFT", "HWM"})
        amat = next(item for item in view["rows"] if item["instrument"]["symbol"] == "AMAT")
        self.assertEqual(amat["instrument"]["confidence"], "MATCH_EXACT")
        self.assertEqual((amat["transaction_date"], amat["filing_date"], amat["disclosure_lag_days"]),
                         ("2026-08-06", "2026-09-14", 39))
        # S14: availability is the end of the (Eastern) filing day; IMP's later first retrieval is its own clock.
        self.assertEqual(amat["available_at"], "2026-09-15T03:59:59Z")
        self.assertEqual((amat["retrieved_at"], amat["imp_known_at"]), ("2026-09-28T14:00:00Z", "2026-09-28T14:00:00Z"))
        self.assertFalse(amat["amount"]["exact_value_disclosed"])
        msft_options = [item for item in view["rows"] if item["instrument"]["symbol"] == "MSFT"]
        self.assertTrue(all(item["instrument"]["is_option"] for item in msft_options))

    def test_coverage_counts_scanned_and_unmatched(self):
        coverage = self.view["coverage"]
        self.assertEqual((coverage["filings"], coverage["parsed"], coverage["not_machine_readable"]), (4, 3, 1))
        self.assertGreater(coverage["ticker_outside_universe"], 0)
        self.assertEqual(coverage["chambers"], ["HOUSE"])

    def test_filters_sorts_and_neutrality(self):
        view = self.svc.congress_view(universe="US_EQUITIES", transaction_type="PURCHASE", min_amount=250_001, sort="amount")
        self.assertTrue(view["rows"])
        self.assertTrue(all(item["transaction_type"] == "PURCHASE" and item["amount"]["min_amount"] >= 250_001
                            for item in view["rows"]))
        self.assertEqual(view["rows"][0]["amount"]["max_amount"], 1_000_000)
        member = self.view["filters"]["members"][0]["id"]
        only = self.svc.congress_view(universe="US_EQUITIES", member=member)
        # S14: member filter ids are canonical; an S12 source id still selects the same member.
        self.assertEqual({item["member"]["canonical_member_id"] for item in only["rows"]}, {member})
        legacy = only["rows"][0]["member"]["member_id"]
        self.assertEqual(self.svc.congress_view(universe="US_EQUITIES", member=legacy)["result_count"], only["result_count"])
        text = json.dumps(self.view).lower()
        for banned in ("party", "score", "rank", "smart money"):
            self.assertNotIn(f'"{banned}', text)
        self.assertIn("No member is scored, ranked", self.view["neutrality_note"])

    def test_etf_universe_matches_only_fund_rows(self):
        view = self.svc.congress_view(universe="US_ETFS")
        self.assertEqual(view["state"], "NO_DISCLOSURES")   # no fixture filer disclosed SPY or QQQ
        self.assertEqual(view["rows"], [])
        self.assertEqual(view["coverage"]["matched"], 0)

    def test_window_by_filing_date(self):
        clock_later = datetime(2026, 11, 20, tzinfo=UTC).timestamp()
        svc = service()
        svc._clock = lambda: clock_later
        view = svc.congress_view(universe="US_EQUITIES", window="30d")
        self.assertEqual(view["rows"], [])

    def test_house_index_failure_is_source_error(self):
        view = service(house_fail=True).congress_view(universe="US_EQUITIES")
        self.assertEqual((view["state"], view["reason"]), ("SOURCE_ERROR", "HTTP_503"))

    def test_documents_are_fetched_once(self):
        before = len(self.svc.fakes["house"].urls)
        self.svc.congress_view(universe="US_EQUITIES")
        self.svc.congress_view(universe="US_ETFS")
        self.assertEqual(len(self.svc.fakes["house"].urls), before)


# ------------------------------------------------------------------ Ownership / positioning
class OwnershipViewTests(unittest.TestCase):
    def test_daily_index_rows_with_roles(self):
        view = service().ownership_view(universe="US_EQUITIES", window="3d")
        self.assertEqual(view["state"], "CURRENT_AS_FILED")
        self.assertEqual(view["coverage"]["days"], ["2026-09-28", "2026-09-25", "2026-09-24"])
        rows = view["rows"]
        self.assertEqual([(item["instrument"]["symbol"], item["family"]) for item in rows], [("RWT", "BENEFICIAL_13D")])
        self.assertEqual(rows[0]["filers"], ["Amster Howard"])
        self.assertEqual(rows[0]["match"]["confidence"], "MATCH_EXACT")
        self.assertEqual(rows[0]["filed_date"], "2026-09-25")
        self.assertIn("date only", view["time_note"])

    def test_no_disclosures(self):
        catalog = {**CATALOG, "US_EQUITIES": [row("EQ", "MSFT", company="Microsoft")]}
        view = service(catalog=catalog).ownership_view(universe="US_EQUITIES", window="3d")
        self.assertEqual(view["state"], "NO_DISCLOSURES")


class PositioningViewTests(unittest.TestCase):
    def test_groups_and_unmapped_roots(self):
        view = service().positioning_view(universe="FUTURES")
        self.assertEqual(view["state"], "PARTIAL")
        self.assertEqual(view["coverage"]["unmapped_roots"], ["ZZZ"])
        groups = {group["report"]: group["rows"] for group in view["groups"]}
        self.assertEqual([item["root"] for item in groups["TFF"]], ["ES"])
        self.assertEqual([item["root"] for item in groups["DISAGGREGATED"]], ["CL"])
        self.assertEqual(groups["TFF"][0]["report_date"], "2026-09-22")
        self.assertIn("not a price forecast", view["boundaries"][0])


# ------------------------------------------------------------------ Instrument panels
class InstrumentPanelTests(unittest.TestCase):
    def test_institutional_equity(self):
        svc = service()
        panel = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:NVDA", lens="institutional")
        sections = panel["sections"]
        insiders = sections["insiders"]
        self.assertEqual(insiders["state"], "CURRENT_AS_FILED")
        self.assertEqual(insiders["filings"][0]["owners"][0]["roles"], ["Officer"])
        self.assertEqual(insiders["filings"][0]["available_basis"], "SEC_ACCEPTANCE_TIME")
        self.assertEqual(insiders["code_counts"]["S"], 3)
        beneficial = sections["beneficial_ownership"]["filings"]
        # The company's own 13G on another issuer and the legacy text filing's issuer are never shown as its holders.
        self.assertEqual([item["accession"] for item in beneficial], ["0000932471-26-000001", "0000932471-24-000002"])
        self.assertEqual(beneficial[0]["reporting_persons"][0]["percent_of_class"], 5.35)
        self.assertEqual(beneficial[1]["state"], "UNAVAILABLE")
        self.assertEqual(beneficial[1]["reason"], "LEGACY_TEXT_FILING_NOT_PARSED")
        recent = [item["accession"] for item in sections["recent_filings"]["filings"]]
        self.assertNotIn("0001045810-26-000062", recent)
        self.assertEqual(sections["holdings_13f"]["state"], "NOT_CONFIGURED")
        self.assertEqual(sections["large_activity"]["participant_identity"], "UNKNOWN")
        self.assertEqual(panel["identity"]["cusips"], ["05589G102"])
        self.assertIn(EVIDENCE_BOUNDARIES[0], panel["boundaries"])

    def test_thirteen_f_section_uses_filing_cusip(self):
        panel = service(thirteen_f=FakeThirteenF()).instrument(universe="US_EQUITIES", instrument_id="EQ:NVDA",
                                                               lens="institutional")
        self.assertEqual(panel["sections"]["holdings_13f"]["cusips"], ["05589G102"])
        no_cusip = service(thirteen_f=FakeThirteenF()).instrument(universe="US_EQUITIES", instrument_id="EQ:META",
                                                                  lens="institutional")
        self.assertEqual(no_cusip["sections"]["holdings_13f"]["state"], "NO_MATCH")

    def test_sec_source_error_is_isolated(self):
        panel = service().instrument(universe="US_EQUITIES", instrument_id="EQ:MSFT", lens="institutional")
        self.assertEqual(panel["sections"]["insiders"]["state"], "SOURCE_ERROR")
        self.assertEqual(panel["sections"]["large_activity"]["state"], "SEE_ORDER_FLOW")

    def test_futures_positioning(self):
        panel = service().instrument(universe="FUTURES", instrument_id="FUT:ESZ6", lens="institutional")
        section = panel["sections"]["futures_positioning"]
        self.assertEqual((section["state"], section["report"]["root"]), ("PUBLICATION_CURRENT", "ES"))
        self.assertNotIn("holdings_13f", panel["sections"])
        unmapped = service().instrument(universe="FUTURES", instrument_id="FUT:ZZZ6", lens="institutional")
        self.assertEqual(unmapped["sections"]["futures_positioning"]["state"], "NO_MATCH")

    def test_congress_and_government(self):
        svc = service()
        panel = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:LMT", lens="congress_gov")
        sections = panel["sections"]
        self.assertEqual(sections["congressional"]["state"], "NO_DISCLOSURES")
        awards = sections["awards"]
        self.assertEqual(awards["state"], "PUBLICATION_CURRENT")
        self.assertIsNone(awards["families"]["contract"]["obligation_sum"])  # truncated page: never summed
        self.assertTrue(awards["families"]["contract"]["has_more"])
        self.assertIsNotNone(awards["families"]["grant"]["obligation_sum"])
        self.assertIn("SIKORSKY AIRCRAFT CORPORATION", awards["families"]["contract"]["recipients"])
        self.assertEqual(awards["match"]["confidence"], "MATCH_ENTITY")
        self.assertEqual(sections["lobbying"]["total_filings"], 34)
        self.assertIn(EVIDENCE_BOUNDARIES[2], panel["boundaries"])
        amat = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AMAT", lens="congress_gov")
        self.assertEqual(amat["sections"]["congressional"]["total"], 1)

    def test_generic_names_do_not_query_government_sources(self):
        svc = service()
        panel = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:TGT", lens="congress_gov")
        self.assertEqual(panel["sections"]["awards"]["state"], "NO_MATCH")
        self.assertEqual(svc.fakes["spending"].calls, 0)

    def test_etf_government_panel_has_no_company_records(self):
        panel = service().instrument(universe="US_ETFS", instrument_id="ETF:SPY", lens="congress_gov")
        self.assertEqual(set(panel["sections"]), {"congressional"})

    def test_compact_preview_is_bounded(self):
        svc = service()
        panel = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:LMT", lens="congress_gov", compact=True)
        self.assertEqual(panel["sections"]["lobbying"]["state"], "NOT_LOADED")
        self.assertLessEqual(len(panel["sections"]["awards"]["families"]["contract"]["rows"]), 2)
        inst = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:NVDA", lens="institutional", compact=True)
        self.assertLessEqual(len(inst["sections"]["recent_filings"]["filings"]), 3)

    def test_overall_state_names_the_evidence_state(self):
        svc = service(thirteen_f=FakeThirteenF())
        self.assertEqual(svc.instrument(universe="US_EQUITIES", instrument_id="EQ:NVDA", lens="institutional")["state"],
                         "CURRENT_AS_FILED")
        # Without the local 13F index that section is a source state, so the panel is partial, not current.
        self.assertEqual(service().instrument(universe="US_EQUITIES", instrument_id="EQ:NVDA", lens="institutional")["state"],
                         "PARTIAL")
        self.assertEqual(svc.instrument(universe="US_EQUITIES", instrument_id="EQ:LMT", lens="congress_gov")["state"],
                         "PUBLICATION_CURRENT")
        self.assertEqual(svc.instrument(universe="FUTURES", instrument_id="FUT:ESZ6", lens="institutional")["state"],
                         "PUBLICATION_CURRENT")

    def test_government_sources_start_before_any_wait(self):
        # A cold panel waits for the slowest government source, not the sum of them.
        svc = service()
        events: list[str] = []
        cache_get, await_ = svc._cache.get, svc._await

        def recording_get(key, job, *, ttl_s):
            events.append(f"get:{key[0]}")
            return cache_get(key, job, ttl_s=ttl_s)

        def recording_await(key, job, ttl_s):
            events.append(f"await:{key[0]}")
            return await_(key, job, ttl_s)

        svc._cache.get, svc._await = recording_get, recording_await
        svc.instrument(universe="US_EQUITIES", instrument_id="EQ:LMT", lens="congress_gov")
        government = ("await:usaspending", "await:usaspending_updated", "await:lobbying")
        first_wait = next(index for index, event in enumerate(events) if event in government)
        self.assertLessEqual({"get:usaspending", "get:usaspending_updated", "get:lobbying"}, set(events[:first_wait]))

    def test_payloads_carry_no_secrets(self):
        # Every S12 payload passes the server's secret-leak audit with rows present: a field name
        # the audit reads as secret-shaped (e.g. ``*_key``) would otherwise block the route live.
        svc = service(thirteen_f=FakeThirteenF())
        payloads = {
            "congress": svc.congress_view(universe="US_EQUITIES", window="60d"),
            "ownership": svc.ownership_view(universe="US_EQUITIES", window="3d"),
            "positioning": svc.positioning_view(universe="FUTURES"),
            "institutional": svc.instrument(universe="US_EQUITIES", instrument_id="EQ:NVDA", lens="institutional"),
            "congress_gov": svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AMAT", lens="congress_gov"),
            "government": svc.instrument(universe="US_EQUITIES", instrument_id="EQ:LMT", lens="congress_gov"),
            "futures": svc.instrument(universe="FUTURES", instrument_id="FUT:ESZ6", lens="institutional"),
            "compact": svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AMAT", lens="congress_gov", compact=True),
        }
        payloads["no_cik"] = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:HWM", lens="institutional")
        payloads["house_error"] = service(house_fail=True).congress_view(universe="US_EQUITIES")
        # Every state in every payload (overall, sections, providers, filings) is an S12 state: never a generic "CURRENT".
        allowed = {"PUBLICATION_CURRENT", "CURRENT_AS_FILED", "STALE", "PARTIAL", "NOT_CONFIGURED", "UNAVAILABLE",
                   "SOURCE_ERROR", "NO_MATCH", "NO_DISCLOSURES", "PENDING", "LIVE_DISABLED", "NOT_APPLICABLE",
                   "NOT_LOADED", "SEE_ORDER_FLOW",
                   # S14 (narrow): Senate eFD access boundary and managed 13F index states.
                   "TERMS_ACCEPTANCE_REQUIRED", "READY", "INDEX_INVALID", "REFRESHING"}

        def states(value, path="$"):
            if isinstance(value, dict):
                for key, item in value.items():
                    if key == "state" and isinstance(item, str):
                        yield path, item
                    yield from states(item, f"{path}.{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    yield from states(item, f"{path}[{index}]")

        for name, payload in payloads.items():
            for path, state in states(payload):
                with self.subTest(payload=name, path=path):
                    self.assertIn(state, allowed)

        self.assertTrue(payloads["congress"]["rows"])
        self.assertTrue(payloads["ownership"]["rows"])
        self.assertTrue(payloads["congress_gov"]["sections"]["congressional"]["transactions"])
        self.assertTrue(payloads["government"]["sections"]["lobbying"]["filings"])
        for name, payload in payloads.items():
            with self.subTest(name):
                assert_no_secrets_in_payload(payload)
                self.assertNotIn("tests@example.test", json.dumps(payload))


class UniverseIndexTests(unittest.TestCase):
    def test_catalog_still_loading_is_pending_never_no_disclosures(self):
        svc = service()
        svc._cache = BackgroundCache(clock=lambda: NOW, spawn=lambda job: None)   # background jobs never finish
        for view in (svc.congress_view(universe="US_EQUITIES"), svc.ownership_view(universe="US_EQUITIES"),
                     svc.positioning_view(universe="FUTURES")):
            with self.subTest(view["view"]):
                self.assertEqual((view["state"], view["reason"]), ("PENDING", "UNIVERSE_INDEX_LOADING"))
        panel = svc.instrument(universe="US_EQUITIES", instrument_id="EQ:AMAT", lens="congress_gov")
        self.assertEqual(panel["sections"]["congressional"]["state"], "PENDING")

    def test_catalog_failure_is_a_source_error(self):
        svc = service()
        svc._catalog = lambda universe: ([], "OPEND_UNAVAILABLE")
        view = svc.positioning_view(universe="FUTURES")
        self.assertEqual((view["state"], view["reason"]), ("SOURCE_ERROR", "OPEND_UNAVAILABLE"))
        congress = svc.congress_view(universe="US_EQUITIES")
        self.assertEqual((congress["state"], congress["reason"]), ("SOURCE_ERROR", "OPEND_UNAVAILABLE"))

        def raises(universe):
            raise OSError("catalog down")

        svc = service()
        svc._catalog = raises
        self.assertEqual(svc.ownership_view(universe="US_EQUITIES")["state"], "SOURCE_ERROR")


class LoaderTests(unittest.TestCase):
    def test_loader_is_off_request_and_progressive(self):
        jobs = []
        public = PublicRecordsHttp(requester=HouseRequester(), min_interval_s=0.0)
        loader = HousePtrLoader(http=public, clock=lambda: NOW, spawn=jobs.append)
        loader.ensure()
        loader.ensure()
        self.assertEqual(len(jobs), 1)            # one background job; the request thread never downloads
        self.assertTrue(loader.snapshot()["running"])
        jobs[0]()
        snap = loader.snapshot()
        self.assertEqual((len(snap["filings"]), len(snap["documents"])), (4, 4))
        loader.ensure()
        self.assertEqual(len(jobs), 1)            # fresh within the index TTL

    def test_document_errors_are_isolated(self):
        class Flaky(HouseRequester):
            def __call__(self, url, body, headers, timeout):
                if url.endswith("20035420.pdf"):
                    raise PublicRecordsError("HTTP_500")
                return super().__call__(url, body, headers, timeout)

        public = PublicRecordsHttp(requester=Flaky(), min_interval_s=0.0)
        loader = HousePtrLoader(http=public, clock=lambda: NOW, spawn=lambda job: job())
        loader.ensure()
        snap = loader.snapshot()
        self.assertEqual(snap["doc_errors"], {"20035420": "HTTP_500"})
        self.assertEqual(len(snap["documents"]), 3)


if __name__ == "__main__":
    unittest.main()

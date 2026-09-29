"""S13 universe integrity: deterministic, evidence-based membership for all five Screener universes.

The observed defect (S12 live acceptance): the ETF universe contained EQIX and
WY (equity REITs) and AIO (a closed-end fund) because Moomoo's ``ETF``
security type is a broad fund/trust bucket. These fixtures are regression
examples, not the rule: the classifier admits by provider type AND the
reference ``Exchange Traded Fund`` industry, and every rejection has a reason.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.finviz.screener import FinvizScreenerRow  # noqa: E402
from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.ui_api import screener_admission as admission  # noqa: E402
from market_platform_foundation.ui_api.screener_admission import (  # noqa: E402
    ClassificationReference, admit_equity, admit_etf, integrity_report, listing_key, reference_category,
)
from market_platform_foundation.ui_api.screener_config import validate_screen  # noqa: E402
from market_platform_foundation.ui_api.screener_crypto import project_catalog as project_crypto_catalog  # noqa: E402
from market_platform_foundation.ui_api.screener_filters import filter_catalog  # noqa: E402
from market_platform_foundation.ui_api.screener_multi import (  # noqa: E402
    MultiUniverseScreener, project_etf_admission, project_futures_catalog,
)
from market_platform_foundation.ui_api.screener_projections import FILTER, ScreenerService  # noqa: E402
from market_platform_foundation.ui_api.screener_universes import (  # noqa: E402
    BONDS, CRYPTO, FUTURES, UNIVERSES, US_EQUITIES, US_ETFS,
)
from tests.platform.test_screener_s9 import read as bond_read  # noqa: E402
from tests.platform.test_screener_s9 import service as bond_service  # noqa: E402
from tests.platform.test_screener_s12 import CATALOG as S12_CATALOG  # noqa: E402
from tests.platform.test_screener_s12 import service as participant_service  # noqa: E402

TODAY = date(2026, 9, 29)
AS_OF = "2026-09-29T13:00:00Z"
FINVIZ_AS_OF = "2026-09-29T12:58:00Z"

ETF = "Exchange Traded Fund"
#: Finviz export rows (ticker, sector, industry), covering every category S13 decides.
FINVIZ = (
    # Valid ETFs across structures: UIT broad equity, bond, commodity grantor trust,
    # leveraged, inverse, actively managed, spot-bitcoin grantor trust, Treasury bond.
    ("SPY", "Financial", ETF), ("AGG", "Financial", ETF), ("GLD", "Financial", ETF),
    ("TQQQ", "Financial", ETF), ("SH", "Financial", ETF), ("JEPI", "Financial", ETF),
    ("IBIT", "Financial", ETF), ("TLT", "Financial", ETF),
    # Observed contamination and the categories it represents.
    ("EQIX", "Real Estate", "REIT - Specialty"), ("WY", "Real Estate", "REIT - Specialty"),
    ("AIO", "Financial", "Closed-End Fund - Equity"), ("NLY", "Real Estate", "REIT - Mortgage"),
    ("ARCC", "Financial", "Asset Management"),          # BDC: a listed equity
    ("PBT", "Energy", "Oil & Gas E&P"),                   # royalty trust: a listed equity
    ("SPAC", "Financial", "Shell Companies"),
    ("AAPL", "Technology", "Consumer Electronics"),     # US common equity
    ("BRK-B", "Financial", "Insurance - Diversified"),
    ("NOIND", "", ""),                                    # an export row Finviz leaves unclassified
)
#: Moomoo ``get_stock_basicinfo(US, ETF)``: every row is provider-typed "ETF".
PROVIDER_ETF_TYPED = ("SPY", "AGG", "GLD", "TQQQ", "SH", "JEPI", "IBIT", "TLT",
                      "EQIX", "WY", "AIO", "NLY", "ARCC", "PBT", "SPAC", "NOIND", "ZZNEW")
VALID_ETFS = ["AGG", "GLD", "IBIT", "JEPI", "SH", "SPY", "TLT", "TQQQ"]


def finviz_rows(rows=FINVIZ) -> list[FinvizScreenerRow]:
    return [FinvizScreenerRow(ticker=ticker, company=f"{ticker} company", sector=sector, industry=industry,
                              country="USA", price=10.0, volume=1_000) for ticker, sector, industry in rows]


def provider_etf(symbol: str, **extra) -> dict:
    return {"code": f"US.{symbol}", "name": f"{symbol} name", "stock_type": "ETF", "stock_child_type": "N/A",
            "exchange_type": "US_NYSE", "delisting": False, "listing_date": "2000-01-01", **extra}


def reference(rows=FINVIZ) -> ClassificationReference:
    return ClassificationReference.build(finviz_rows(rows), as_of=FINVIZ_AS_OF)


class Finviz:
    def __init__(self, rows=FINVIZ, *, success: bool = True) -> None:
        self.rows, self.success, self.filters = rows, success, []

    def fetch_export(self, *, filter_expr: str, columns: str) -> dict:
        self.filters.append(filter_expr)
        return {"success": self.success, "error": None if self.success else "NOT_CONFIGURED",
                "received_at": FINVIZ_AS_OF, "rows": finviz_rows(self.rows) if self.success else []}


class Moomoo:
    def __init__(self, symbols=PROVIDER_ETF_TYPED) -> None:
        self.symbols = symbols

    def fetch_etf_catalog(self) -> dict:
        return {"rows": [provider_etf(symbol) for symbol in self.symbols], "reason_code": None}


def services(finviz: Finviz | None = None, moomoo: Moomoo | None = None) -> tuple[ScreenerService, MultiUniverseScreener]:
    equities = ScreenerService(source_factory=lambda: finviz or Finviz(), runtime_getter=lambda **_: None)
    source = moomoo or Moomoo()
    multi = MultiUniverseScreener(transport_getter=lambda: source, reference_getter=equities.classification_reference,
                                  today=lambda: TODAY, now=lambda: AS_OF, clock=lambda: 1.0)
    return equities, multi


def symbols(result: dict) -> list[str]:
    return [row["symbol"] for row in result["rows"]]


# ------------------------------------------------------------------ classifier
class ClassificationRuleTests(unittest.TestCase):
    def test_reference_categories_follow_the_industry_not_the_ticker(self):
        self.assertEqual(reference_category("Exchange Traded Fund"), admission.EXCHANGE_TRADED_FUND)
        for industry in ("REIT - Specialty", "REIT - Mortgage", "REIT - Residential"):
            self.assertEqual(reference_category(industry), admission.REIT)
        for industry in ("Closed-End Fund - Equity", "Closed-End Fund - Debt", "Closed-End Fund - Foreign"):
            self.assertEqual(reference_category(industry), admission.CLOSED_END_FUND)
        self.assertEqual(reference_category("Shell Companies"), admission.SHELL_COMPANY)
        self.assertEqual(reference_category("Asset Management"), admission.LISTED_EQUITY)
        self.assertEqual(reference_category(""), admission.UNCLASSIFIED)
        self.assertEqual(reference_category(None), admission.UNCLASSIFIED)

    def test_known_defects_are_rejected_with_their_category(self):
        ref = reference()
        expected = {"EQIX": admission.REIT, "WY": admission.REIT, "AIO": admission.CLOSED_END_FUND}
        for symbol, reason in expected.items():
            decision = admit_etf(provider_etf(symbol), ref)
            self.assertFalse(decision.admitted, symbol)
            self.assertEqual(decision.reason, reason, symbol)
            self.assertEqual(decision.classification["provider"]["stock_type"], "ETF")  # provider evidence kept
            self.assertEqual(decision.classification["reference"]["source"], "FINVIZ_ELITE")

    def test_classifier_generalizes_beyond_the_regression_examples(self):
        ref = reference()
        reasons = {symbol: admit_etf(provider_etf(symbol), ref).reason for symbol in ("NLY", "ARCC", "PBT", "SPAC")}
        self.assertEqual(reasons, {"NLY": admission.REIT, "ARCC": admission.NOT_ETF, "PBT": admission.NOT_ETF,
                                   "SPAC": admission.NOT_ETF})

    def test_valid_etf_structures_are_admitted(self):
        ref = reference()
        for symbol in VALID_ETFS:
            decision = admit_etf(provider_etf(symbol), ref)
            self.assertTrue(decision.admitted, symbol)
            self.assertEqual(decision.category, admission.EXCHANGE_TRADED_FUND)
            self.assertEqual(decision.classification["basis"], "PROVIDER_SECURITY_TYPE+REFERENCE_INDUSTRY")

    def test_unknown_is_fail_closed(self):
        ref = reference()
        self.assertEqual(admit_etf(provider_etf("ZZNEW"), ref).reason, admission.UNRESOLVED_SECURITY_TYPE)
        self.assertEqual(admit_etf(provider_etf("NOIND"), ref).reason, admission.UNRESOLVED_SECURITY_TYPE)
        unavailable = ClassificationReference(None, {}, "NOT_CONFIGURED")
        self.assertEqual(admit_etf(provider_etf("SPY"), unavailable).reason, admission.CLASSIFICATION_UNAVAILABLE)

    def test_provider_type_market_and_status_are_checked_before_the_reference(self):
        ref = reference()
        self.assertEqual(admit_etf(provider_etf("SPY", stock_type="STOCK"), ref).reason, admission.WRONG_PRODUCT_TYPE)
        self.assertEqual(admit_etf({**provider_etf("SPY"), "code": "HK.02800"}, ref).reason, admission.WRONG_MARKET)
        self.assertEqual(admit_etf(provider_etf("SPY", delisting=True), ref).reason, admission.DELISTED)
        self.assertEqual(admit_etf(provider_etf("BAD$"), ref).reason, admission.INVALID_SYMBOL)

    def test_listing_key_joins_provider_share_class_spellings(self):
        self.assertEqual(listing_key("BRK.B"), listing_key("BRK-B"))
        self.assertIsNotNone(reference().get("BRK.B"))

    def test_equity_admission_keeps_listed_equity_categories_and_excludes_etfs(self):
        rows = {row.ticker: admit_equity(row, as_of=FINVIZ_AS_OF) for row in finviz_rows()}
        self.assertEqual(rows["EQIX"].category, admission.REIT)
        self.assertEqual(rows["AIO"].category, admission.CLOSED_END_FUND)
        self.assertTrue(all(rows[symbol].admitted for symbol in ("EQIX", "WY", "AIO", "NLY", "ARCC", "PBT", "SPAC",
                                                                 "AAPL", "NOIND")))
        self.assertEqual(rows["NOIND"].category, admission.UNCLASSIFIED)
        for symbol in VALID_ETFS:
            self.assertFalse(rows[symbol].admitted, symbol)
            self.assertEqual(rows[symbol].reason, admission.ETF_BELONGS_TO_US_ETFS)


# ------------------------------------------------------------------ pipeline
class EtfUniversePipelineTests(unittest.TestCase):
    def test_etf_universe_contains_only_exchange_traded_funds(self):
        _equities, multi = services()
        result = multi.read(universe=US_ETFS, sort="symbol", descending=False, limit=500)
        self.assertEqual(symbols(result), VALID_ETFS)
        self.assertEqual((result["result_count"], result["unfiltered_count"]), (8, 8))  # accepted, not provider raw
        self.assertTrue(all(row["instrument"]["asset_class"] == "ETF_FUND" for row in result["rows"]))
        row = result["rows"][0]
        self.assertEqual(row["classification"]["category"], admission.EXCHANGE_TRADED_FUND)
        self.assertEqual(row["classification"]["reference"]["industry"], ETF)
        self.assertEqual(row["classification"]["provider"]["stock_type"], "ETF")
        health = {item["role"]: item for item in result["provider_health"]}
        self.assertEqual(health["CLASSIFICATION_SOURCE"]["state"], "HEALTHY")
        assert_no_secrets_in_payload(result)

    def test_admission_counts_expose_the_correction(self):
        _equities, multi = services()
        multi.read(universe=US_ETFS)
        audit = multi.admission_audit(US_ETFS)
        self.assertEqual((audit["provider_raw_count"], audit["accepted"], audit["rejected"]),
                         (len(PROVIDER_ETF_TYPED), 8, 9))
        self.assertEqual(audit["rejection_reasons"], {admission.REIT: 3, admission.NOT_ETF: 3,
                                                      admission.UNRESOLVED_SECURITY_TYPE: 2,
                                                      admission.CLOSED_END_FUND: 1})
        self.assertEqual(audit["reference"]["as_of"], FINVIZ_AS_OF)

    def test_search_obeys_the_corrected_universes(self):
        equities, multi = services()
        self.assertEqual(multi.read(universe=US_ETFS, search="EQIX")["result_count"], 0)
        self.assertEqual(symbols(equities.read(search="EQIX")), ["EQIX"])
        self.assertEqual(symbols(multi.read(universe=US_ETFS, search="SPY")), ["SPY"])
        self.assertEqual(equities.read(search="SPY")["result_count"], 0)

    def test_classification_unavailable_fails_closed_and_says_so(self):
        _equities, multi = services(finviz=Finviz(success=False))
        result = multi.read(universe=US_ETFS)
        self.assertEqual((result["rows"], result["result_count"]), ([], 0))
        self.assertEqual(result["source_error"], admission.CLASSIFICATION_UNAVAILABLE)
        health = {item["role"]: item for item in result["provider_health"]}
        self.assertEqual((health["CLASSIFICATION_SOURCE"]["state"], health["CLASSIFICATION_SOURCE"]["reason"]),
                         ("UNAVAILABLE", "NOT_CONFIGURED"))
        self.assertEqual(health["IDENTITY_SOURCE"]["state"], "HEALTHY")

    def test_failed_reference_refresh_keeps_the_last_good_classification(self):
        finviz = Finviz()
        equities, multi = services(finviz=finviz)
        first = multi.read(universe=US_ETFS)
        finviz.success = False
        equities.read(force_refresh=True)
        again = multi.read(universe=US_ETFS)
        self.assertEqual(symbols(again), symbols(first))
        self.assertEqual(again["result_set_id"], first["result_set_id"])

    def test_pages_are_pinned_to_the_classification_they_started_from(self):
        _equities, multi = services()
        first = multi.read(universe=US_ETFS, sort="symbol", descending=False, limit=3)
        self.assertIn("~" + reference().fingerprint, first["result_set_id"])
        second = multi.read(universe=US_ETFS, sort="symbol", descending=False, limit=3, offset=3,
                            result_set=first["result_set_id"])
        self.assertEqual(symbols(first) + symbols(second), VALID_ETFS[:6])
        with self.assertRaisesRegex(ValueError, "RESULT_SET_CHANGED"):
            multi.read(universe=US_ETFS, limit=3, offset=3, result_set=f"{AS_OF}~2026-01-01T00:00:00Z|")

    def test_unchanged_reclassification_keeps_page_chains_and_a_changed_one_starts_a_new_set(self):
        finviz = Finviz()
        equities, multi = services(finviz=finviz)
        first = multi.read(universe=US_ETFS, sort="symbol", descending=False, limit=3)
        equities.read(force_refresh=True)  # same classification, new export
        self.assertEqual(multi.read(universe=US_ETFS, limit=3)["result_set_id"], first["result_set_id"])
        finviz.rows = tuple(row for row in FINVIZ if row[0] != "JEPI")  # a listing loses its ETF evidence
        equities.read(force_refresh=True)
        changed = multi.read(universe=US_ETFS, sort="symbol", descending=False, limit=500)
        self.assertNotEqual(changed["result_set_id"], first["result_set_id"])
        self.assertNotIn("JEPI", symbols(changed))
        # The earlier chain still finishes on the rows it started from (current + previous retained).
        tail = multi.read(universe=US_ETFS, sort="symbol", descending=False, limit=3, offset=3,
                          result_set=first["result_set_id"])
        self.assertEqual(symbols(tail), ["JEPI", "SH", "SPY"])

    def test_removed_rows_are_unknown_to_windows_and_rows(self):
        _equities, multi = services()
        ids = {row["symbol"]: row["instrument"]["instrument_id"] for row in multi.read(universe=US_ETFS)["rows"]}
        self.assertNotIn("EQIX", ids)
        from market_platform_foundation.xa01.compatibility import register_etf_fund

        with self.assertRaisesRegex(ValueError, "UNKNOWN_OR_DUPLICATE_INSTRUMENT"):
            multi.window("client", [register_etf_fund(symbol="EQIX")], universe=US_ETFS)
        self.assertIsNone(multi.row_for(register_etf_fund(symbol="WY"), universe=US_ETFS)[0])

    def test_projection_is_catalog_time_work_not_per_query(self):
        calls = []
        equities = ScreenerService(source_factory=lambda: Finviz(), runtime_getter=lambda **_: None)

        def counted() -> ClassificationReference:
            calls.append(1)
            return equities.classification_reference()

        multi = MultiUniverseScreener(transport_getter=Moomoo, reference_getter=counted, today=lambda: TODAY,
                                      now=lambda: AS_OF, clock=lambda: 1.0)
        with patch("market_platform_foundation.ui_api.screener_multi.admit_etf",
                   wraps=admission.admit_etf) as admit:
            for search in ("", "S", "SPY", "Q", "T"):
                multi.read(universe=US_ETFS, search=search)
        self.assertEqual(admit.call_count, len(PROVIDER_ETF_TYPED))  # one classification per catalog load
        self.assertEqual(len(calls), 5)  # a cached in-memory reference read, never a remote call per row


class EquityUniversePipelineTests(unittest.TestCase):
    def test_equities_admit_listed_equities_and_never_etfs(self):
        finviz = Finviz()
        equities, _multi = services(finviz=finviz)
        result = equities.read(sort="symbol", descending=False, limit=500)
        self.assertEqual(finviz.filters, ["geo_usa"])
        self.assertEqual(FILTER, "geo_usa")
        self.assertEqual(symbols(result), ["AAPL", "AIO", "ARCC", "BRK-B", "EQIX", "NLY", "NOIND", "PBT", "SPAC", "WY"])
        categories = {row["symbol"]: row["classification"]["category"] for row in result["rows"]}
        self.assertEqual((categories["EQIX"], categories["AIO"], categories["AAPL"]),
                         (admission.REIT, admission.CLOSED_END_FUND, admission.LISTED_EQUITY))
        audit = result["admission"]
        self.assertEqual((audit["provider_raw_count"], audit["accepted"], audit["rejected"], audit["ambiguous"]),
                         (len(FINVIZ), 10, 8, 1))
        self.assertEqual(audit["rejection_reasons"], {admission.ETF_BELONGS_TO_US_ETFS: 8})


# ------------------------------------------------------------------ five universes
class CrossUniverseTests(unittest.TestCase):
    def five_catalogs(self) -> dict[str, list[dict]]:
        equities, multi = services()

        class FuturesTransport:
            def fetch_future_contracts(self, codes):
                rows = []
                for root, ym, expiry in (("ES", "2612", "2026-12-18"), ("ZN", "2612", "2026-12-21")):
                    rows += [{"code": f"US.{root}main", "name": f"{root} (DEC6)", "stock_type": "FUTURE",
                              "delisting": False},
                             {"code": f"US.{root}{ym}", "name": f"{root} {ym}", "stock_type": "FUTURE",
                              "delisting": False, "last_trade_time": f"{expiry} 16:00:00", "exchange_type": "CME"}]
                # Non-futures products a provider could return next to contracts.
                rows += [{"code": "US.ESmain", "stock_type": "IDX"}, {"code": "US.SPX2612", "stock_type": "DRVT"}]
                return {"rows": rows, "reason_code": None}

        futures = MultiUniverseScreener(transport_getter=FuturesTransport, today=lambda: TODAY,
                                        now=lambda: AS_OF, clock=lambda: 1.0)
        crypto = project_crypto_catalog({"error": [], "result": {
            "BTC/USD": {"base": "BTC", "quote": "USD", "aclass_base": "currency", "aclass_quote": "currency",
                        "status": "online"},
            # Tokenized equities and delisted pairs are provider metadata exclusions, never name heuristics.
            "AAPLx/USD": {"base": "AAPLx", "quote": "USD", "aclass_base": "tokenized_asset",
                          "aclass_quote": "currency", "status": "online"},
            "ETH/USD": {"base": "ETH", "quote": "USD", "aclass_base": "currency", "aclass_quote": "currency",
                        "status": "delisted"}}}, as_of=AS_OF)
        return {
            US_EQUITIES: equities.read(limit=500)["rows"],
            US_ETFS: multi.read(universe=US_ETFS, limit=500)["rows"],
            FUTURES: futures.read(universe=FUTURES, limit=500)["rows"],
            BONDS: bond_read(bond_service(), limit=500)["rows"],
            CRYPTO: crypto,
        }

    def test_five_universes_are_clean_and_disjoint(self):
        self.assertEqual(list(UNIVERSES), [US_EQUITIES, FUTURES, US_ETFS, BONDS, CRYPTO])
        catalogs = self.five_catalogs()
        report = integrity_report(catalogs)
        self.assertEqual(report["violations"], [])
        self.assertEqual(report["cross_universe_duplicates"], [])
        self.assertTrue(report["clean"])
        self.assertEqual(sorted(row["symbol"] for row in catalogs[FUTURES]), ["ESZ26", "ZNZ26"])
        self.assertEqual([row["symbol"] for row in catalogs[CRYPTO]], ["BTC/USD"])
        self.assertTrue(catalogs[BONDS])

    def test_exact_classification_by_category(self):
        catalogs = self.five_catalogs()
        where = {}
        for universe, rows in catalogs.items():
            for row in rows:
                where.setdefault(row["symbol"], set()).add(universe)
        self.assertEqual(where["EQIX"], {US_EQUITIES})     # REIT -> US Equities
        self.assertEqual(where["AIO"], {US_EQUITIES})      # CEF  -> US Equities, category CLOSED_END_FUND
        self.assertEqual(where["SPY"], {US_ETFS})          # ETF  -> US ETFs
        self.assertEqual(where["TLT"], {US_ETFS})          # bond ETF -> US ETFs, never BONDS
        self.assertEqual(where["ZNZ26"], {FUTURES})        # Treasury future -> Futures, never BONDS
        self.assertEqual(where["BTC/USD"], {CRYPTO})       # spot pair -> Crypto
        self.assertNotIn("AAPLx/USD", where)               # tokenized/derivative product excluded
        self.assertEqual(where["AAPL"], {US_EQUITIES})     # common equity -> US Equities
        treasury = next(row for row in catalogs[BONDS] if row["cusip"] == "91282CRF0")
        self.assertEqual(where[treasury["symbol"]], {BONDS})  # cash Treasury (CUSIP) -> Bonds
        self.assertEqual(treasury["reference_tenor"], "10Y")  # 10Y CMT is a reference, not the identity
        self.assertNotEqual(treasury["instrument"]["instrument_id"], "10Y")

    def test_audit_detects_misplaced_rows_and_duplicate_listings(self):
        catalogs = self.five_catalogs()
        tlt = next(row for row in catalogs[US_ETFS] if row["symbol"] == "TLT")
        zn = next(row for row in catalogs[FUTURES] if row["root"] == "ZN")
        eqix = next(row for row in catalogs[US_EQUITIES] if row["symbol"] == "EQIX")
        contaminated_etf = {**tlt, "symbol": "EQIX",
                            "classification": {**tlt["classification"], "category": admission.REIT}}
        perp = {**catalogs[CRYPTO][0], "product_type": "PERPETUAL"}
        report = integrity_report({US_EQUITIES: [eqix], US_ETFS: [contaminated_etf], BONDS: [tlt, zn],
                                   CRYPTO: [perp]})
        problems = {(item["universe"], item["symbol"], item["problem"]) for item in report["violations"]}
        self.assertIn((BONDS, "TLT", "WRONG_ASSET_CLASS"), problems)      # TLT != Treasury bond
        self.assertIn((BONDS, "ZNZ26", "WRONG_ASSET_CLASS"), problems)    # ZN != cash Treasury
        self.assertIn((US_ETFS, "EQIX", admission.NOT_ETF), problems)
        self.assertIn((CRYPTO, "BTC/USD", "NOT_VENUE_SPOT_PAIR"), problems)
        self.assertIn({"key": "EQIX", "kind": "LISTING", "universes": [US_EQUITIES, US_ETFS]},
                      report["cross_universe_duplicates"])
        self.assertFalse(report["clean"])

    def test_futures_catalog_admits_only_lead_futures_contracts(self):
        rows = project_futures_catalog([
            {"code": "US.CLmain", "stock_type": "FUTURE", "name": "CL (NOV6)"},
            {"code": "US.CL2611", "stock_type": "FUTURE", "last_trade_time": "2026-10-20 14:30:00"},
            {"code": "US.CL2612", "stock_type": "OPTION", "last_trade_time": "2026-11-17 14:30:00"},
            {"code": "US.SPXmain", "stock_type": "IDX"},
        ], today=TODAY, as_of=AS_OF)
        self.assertEqual([(row["symbol"], row["instrument"]["asset_class"], row["instrument"]["instrument_kind"])
                          for row in rows], [("CLX26", "FUTURE", "FUTURE_CONTRACT")])


# ------------------------------------------------------------------ downstream
class DownstreamTests(unittest.TestCase):
    def test_news_and_congress_catalogs_follow_the_corrected_universe(self):
        from market_platform_foundation.ui_api import screener_news, screener_participants

        equities, multi = services()
        with patch("market_platform_foundation.ui_api.screener_multi.multi_screener_service", return_value=multi):
            etf_rows, error = screener_news._default_catalog(US_ETFS)
            participant_rows, _error = screener_participants._default_catalog(US_ETFS)
        self.assertIsNone(error)
        self.assertEqual(sorted(row["symbol"] for row in etf_rows), VALID_ETFS)
        self.assertEqual(sorted(row["symbol"] for row in participant_rows), VALID_ETFS)
        self.assertIn("EQIX", {row["symbol"] for row in equities.read(limit=500)["rows"]})

    def test_congress_disclosure_matches_only_the_admitting_universe(self):
        # HWM has a House PTR in the S12 fixture. Even if a provider typed it "ETF",
        # the corrected ETF universe never admits it, so the ETF view has no match.
        finviz = Finviz(FINVIZ + (("HWM", "Industrials", "Aerospace & Defense"),))
        equities, multi = services(finviz=finviz, moomoo=Moomoo(PROVIDER_ETF_TYPED + ("HWM",)))
        etfs = multi.read(universe=US_ETFS, limit=500)["rows"]
        self.assertNotIn("HWM", {row["symbol"] for row in etfs})
        catalog = {**S12_CATALOG, US_ETFS: etfs}
        svc = participant_service(catalog=catalog)
        self.assertEqual(svc.congress_view(universe=US_ETFS)["rows"], [])
        naive = participant_service(catalog={**S12_CATALOG, US_ETFS: etfs + [
            {"instrument": {"instrument_id": "ETF:HWM"}, "symbol": "HWM", "company": "Howmet"}]})
        self.assertIn("HWM", {row["instrument"]["symbol"] for row in naive.congress_view(universe=US_ETFS)["rows"]})
        self.assertIn("HWM", {row["instrument"]["symbol"]
                              for row in participant_service().congress_view(universe=US_EQUITIES)["rows"]})
        self.assertIn("HWM", {row["symbol"] for row in equities.read(limit=500)["rows"]})

    def test_saved_etf_screen_still_loads_and_removed_rows_simply_no_longer_match(self):
        screen = {"name": "REIT hunt", "universe": US_ETFS, "view": "Overview",
                  "filters": [{"id": "f1", "field": "symbol", "operator": "contains", "value": "EQIX"}],
                  "sort": {"field": "symbol", "descending": False},
                  "columns": {"visible": ["symbol", "company"], "order": ["symbol", "company"], "widths": {},
                              "pinned": ["symbol"]}}
        validated = validate_screen(screen)
        self.assertEqual(validated["filters"], screen["filters"])  # no migration rewrites the filter
        _equities, multi = services()
        result = multi.read(universe=US_ETFS, filters=validated["filters"])
        self.assertEqual((result["rows"], result["result_count"], result["source_error"]), ([], 0, None))
        self.assertEqual(result["unfiltered_count"], 8)

    def test_etf_filters_are_unchanged_and_fund_scoped(self):
        fields = {entry["field"] for entry in filter_catalog(US_ETFS)}
        self.assertTrue({"symbol", "exchange", "price"} <= fields)
        self.assertTrue({"short_float_pct", "float_shares", "pe"}.isdisjoint(fields))


# ------------------------------------------------------------------ audit command
def _audit_tool():
    import importlib.util

    spec = importlib.util.spec_from_file_location("s13_universe_audit", ROOT / "tools" / "screener" / "universe_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AuditCommandTests(unittest.TestCase):
    def read_for(self, equities, multi):
        def read(**kwargs):
            universe = kwargs.pop("universe")
            if universe == US_EQUITIES:
                return equities.read(**kwargs)
            if universe == US_ETFS:
                return multi.read(universe=universe, **kwargs)
            return {"rows": [], "has_more": False, "source_error": None}
        return read

    def test_audit_reports_counts_samples_and_a_clean_integrity_result(self):
        tool = _audit_tool()
        equities, multi = services()
        report = tool.audit(self.read_for(equities, multi), equities=equities, multi=multi,
                            sample=["EQIX", "AIO", "SPY", "ZZNEW", "AAPL"])
        self.assertTrue(report["integrity"]["clean"])
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["universes"][US_ETFS]["accepted"], 8)
        self.assertEqual(report["universes"][US_ETFS]["admission"]["rejection_reasons"][admission.REIT], 3)
        samples = report["samples"]
        self.assertEqual((samples["EQIX"]["universes"], samples["EQIX"]["etf_decision"]["reason"]),
                         ([US_EQUITIES], admission.REIT))
        self.assertEqual(samples["AIO"]["etf_decision"]["reason"], admission.CLOSED_END_FUND)
        self.assertEqual((samples["SPY"]["universes"], samples["SPY"]["etf_decision"]["status"]),
                         ([US_ETFS], "ADMITTED"))
        self.assertEqual(samples["ZZNEW"]["universes"], [])
        self.assertIsNone(samples["AAPL"]["etf_decision"])  # never provider-typed "ETF"
        self.assertEqual(set(report["universes"][US_ETFS]["latency_ms"]),
                         {"cold_catalog_all_pages", "warm_first_page", "warm_search"})

    def test_audit_flags_a_reference_without_the_etf_industry(self):
        tool = _audit_tool()
        renamed = tuple((ticker, sector, "Exchange-Traded Fund" if industry == ETF else industry)
                        for ticker, sector, industry in FINVIZ)
        equities, multi = services(finviz=Finviz(renamed))
        report = tool.audit(self.read_for(equities, multi), equities=equities, multi=multi, sample=[])
        self.assertEqual(report["findings"], ["REFERENCE_HAS_NO_ETF_INDUSTRY"])
        self.assertEqual(report["universes"][US_ETFS]["accepted"], 0)  # fail-closed, never admitted as unknown


if __name__ == "__main__":
    unittest.main()

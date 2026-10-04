"""S9 Screener Bonds / Fixed Income universe: registry, identity, query, truth states, preview, Rates & Curve.

Fixtures are real excerpts of official U.S. Treasury publications (test-only);
the normal Screener path never reads them.
"""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.fixed_income.http import FixedIncomeSourceError  # noqa: E402
from market_platform_foundation.fixed_income.treasury_catalog import build_catalog  # noqa: E402
from market_platform_foundation.fixed_income.treasury_market import TreasuryMarketData  # noqa: E402
from market_platform_foundation.fixed_income.treasury_rates import (  # noqa: E402
    NOMINAL, REAL, TreasuryRates, parse_bills, parse_curve,
)
from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.platform.security.route_policy import policy_for_route  # noqa: E402
from market_platform_foundation.ui_api.screener_bonds import BondScreener, canonical_treasury_id  # noqa: E402
from market_platform_foundation.ui_api.screener_config import validate_panel_layout, validate_screen  # noqa: E402
from market_platform_foundation.ui_api.screener_filters import filter_catalog, validate_filters  # noqa: E402
from market_platform_foundation.ui_api.screener_query import field_capabilities, is_sortable, parse_query  # noqa: E402
from market_platform_foundation.ui_api.screener_universes import (  # noqa: E402
    BONDS, FUTURES, UNIVERSES, US_EQUITIES, US_ETFS, universe_payload, universe_spec,
)
from market_platform_foundation.xa01.compatibility import (  # noqa: E402
    register_bond, register_etf_fund, register_future_contract_reference,
)
from market_platform_foundation.xa01.enums import InstrumentKind, Tradability  # noqa: E402
from market_platform_foundation.xa01.identity import derive_canonical_id, sovereign_identity_key  # noqa: E402
from market_platform_foundation.xa01.enums import XaAssetClass  # noqa: E402
from market_platform_foundation.xa01.registry import InstrumentRegistry  # noqa: E402
from market_platform_foundation.xa01.tradability import is_executable  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "fixed_income"
TODAY = date(2026, 9, 27)
LIVE = {"IMP_TREASURY_LIVE": "1"}
EQUITY_ONLY = ("float", "short", "p/e", "pe_", "eps", "market cap", "squeeze", "option")


def _json(name: str) -> list[dict]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))["data"]


def fixture_catalog(today: date, fetched_at: str):
    return build_catalog(_json("auctions_excerpt.json"), _json("mspd_excerpt.json"), today=today,
                         fetched_at=fetched_at, mspd_record_date=date(2026, 8, 31))


def fixture_rates(today: date, fetched_at: str) -> TreasuryRates:
    read = lambda name: (FIXTURES / f"{name}_202609_excerpt.xml").read_bytes()  # noqa: E731
    return TreasuryRates(tuple(parse_curve(read("nominal"), NOMINAL)), tuple(parse_curve(read("real"), REAL)),
                         tuple(parse_bills(read("bill"))), {}, fetched_at)


class Clock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value


def no_market(today: date, fetched_at: str) -> TreasuryMarketData:
    return TreasuryMarketData({}, {}, {}, {}, fetched_at)


def service(env=LIVE, *, catalog_loader=fixture_catalog, rates_loader=fixture_rates, today=TODAY, clock=None,
            fred=None, finra=None, market_loader=no_market) -> BondScreener:
    """The S9 service with every S16 source injected empty: no network, no N-PORT catalog."""

    day = [today]
    svc = BondScreener(
        env=env, catalog_loader=catalog_loader, rates_loader=rates_loader,
        market_loader=market_loader, nport=None,
        nyfed_rates_loader=lambda: {"state": "UNAVAILABLE", "reason": "TEST", "items": []},
        soma_loader=lambda: None,
        breadth_loader=lambda **_: {"source": "FINRA_TRACE_AGGREGATES", "state": "NOT_CONFIGURED",
                                    "reason": "IMP_FINRA_LIVE_NOT_SET", "categories": {}},
        fred_loader=fred or (lambda **_: {"state": "NOT_CONFIGURED", "reason": "FRED_API_KEY_MISSING", "items": []}),
        finra_loader=finra or (lambda **_: {"source": "FINRA_TRACE_AGGREGATES", "state": "NOT_CONFIGURED",
                                            "reason": "IMP_FINRA_LIVE_NOT_SET", "trade_date": None, "rows": []}),
        clock=clock or Clock(), today=lambda: day[0], now=lambda: "2026-09-27T20:00:00Z")
    svc.set_today = lambda value: day.__setitem__(0, value)  # type: ignore[attr-defined]
    return svc


def read(svc: BondScreener, **kwargs) -> dict:
    return svc.read(parse_query(universe=BONDS, **kwargs))


def by_cusip(payload: dict) -> dict[str, dict]:
    return {row["cusip"]: row for row in payload["rows"]}


# --------------------------------------------------------------- architecture
class UniverseArchitectureTests(unittest.TestCase):
    def test_bonds_is_the_fourth_universe_and_crypto_is_the_fifth(self):
        self.assertEqual(list(UNIVERSES), [US_EQUITIES, FUTURES, US_ETFS, BONDS, "CRYPTO"])
        for forbidden in ("COMMODITIES", "OPTIONS", "WHALES", "INSTITUTIONS", "NEWS", "TREASURIES", "CORPORATE_BONDS"):
            self.assertNotIn(forbidden, UNIVERSES)

    def test_spec_declares_identity_sources_views_panels_and_reference_only(self):
        spec = universe_spec(BONDS)
        self.assertEqual((spec.label, spec.default_sort, spec.session_model), ("Bonds", "maturity", "PUBLICATION"))
        self.assertEqual(spec.admitted_asset_classes, ("SOVEREIGN_DEBT", "BOND"))
        self.assertEqual(spec.admitted_instrument_kinds, ("SOVEREIGN_SECURITY", "BOND"))
        self.assertEqual(spec.identity_fields, ("cusip", "isin"))
        self.assertEqual(spec.tradability, "REFERENCE_ONLY")
        # S16 adds the fund-held (Credit & Munis) and dated-observation views.
        self.assertEqual(list(spec.views), ["Overview", "Treasuries", "Rates & Curve", "Credit & Munis", "Observed", "Custom"])
        self.assertEqual(spec.panels, ("rates_curve", "news", "connectivity", "ai_screener"))
        payload = next(item for item in universe_payload() if item["id"] == BONDS)
        self.assertEqual(payload["view_order"], ["Overview", "Treasuries", "Rates & Curve", "Credit & Munis", "Observed", "Custom"])
        self.assertEqual(payload["quote_capability"], "NO_STREAMING_QUOTE")
        for other in (US_EQUITIES, FUTURES, US_ETFS):
            self.assertNotIn("rates_curve", universe_spec(other).panels)
            self.assertEqual(next(item for item in universe_payload() if item["id"] == other)["tradability"], "PER_INSTRUMENT")

    def test_bond_universe_offers_no_equity_or_market_fields(self):
        spec = universe_spec(BONDS)
        for field in ("price", "change_pct", "volume", "float_shares", "short_float_pct", "market_cap", "pe", "bid", "ask"):
            self.assertNotIn(field, spec.columns)
        filters = {entry["field"] for entry in filter_catalog(BONDS)}
        self.assertEqual(filters, {"security_type", "issuer", "term", "tips", "frn", "callable", "coupon", "maturity_bucket",
                                   "years_to_maturity", "days_to_maturity", "maturity_year", "outstanding",
                                   "auction_yield", "auction_real_yield", "bid_to_cover",
                                   # S16: category and fund-reported terms/holdings
                                   "category", "isin", "coupon_type", "in_default", "convertible", "pik",
                                   "fund_count", "fund_par_held", "fund_value_pct"})
        capabilities = field_capabilities(BONDS)
        self.assertTrue(all(capabilities[field]["execution"] == "CATALOG" for field in filters))
        for field in ("reference_rate", "reference_tenor", "indicative_rate", "observed_price", "observed_yield",
                      "benchmark_spread"):
            self.assertEqual(capabilities[field], {"execution": "REFERENCE", "sortable": False, "filterable": False})
        for equity in (US_EQUITIES, US_ETFS, FUTURES):
            self.assertFalse({"coupon", "maturity_bucket", "security_type"} & {e["field"] for e in filter_catalog(equity)})


# ------------------------------------------------------------------- identity
class BondIdentityTests(unittest.TestCase):
    def test_rows_carry_cusip_keyed_reference_only_sovereign_identity(self):
        rows = by_cusip(read(service(), limit=500))
        row = rows["91282CRF0"]
        expected = derive_canonical_id(instrument_kind=InstrumentKind.SOVEREIGN_SECURITY, asset_class=XaAssetClass.SOVEREIGN_DEBT,
                                       identity_key=sovereign_identity_key(cusip="91282CRF0"))
        self.assertEqual(row["instrument"], {"instrument_id": expected, "venue_id": "US_TREASURY", "asset_class": "SOVEREIGN_DEBT",
                                             "instrument_kind": "SOVEREIGN_SECURITY", "tradability": "REFERENCE_ONLY"})
        self.assertEqual((row["symbol"], row["cusip"], row["identity_source"]), ("91282CRF0", "91282CRF0", "CUSIP"))
        self.assertEqual(row["company"], "U.S. Treasury Note 4.625% Aug 2036")
        self.assertFalse(is_executable(instrument_kind=InstrumentKind.SOVEREIGN_SECURITY))
        self.assertEqual(len({r["instrument"]["instrument_id"] for r in rows.values()}), len(rows))

    def test_identity_is_stable_across_catalog_refreshes(self):
        first = by_cusip(read(service(), limit=500))
        other = service(catalog_loader=lambda today, fetched_at: fixture_catalog(today, "2026-09-28T01:00:00Z"))
        second = by_cusip(read(other, limit=500))
        self.assertEqual({k: v["instrument"]["instrument_id"] for k, v in first.items()},
                         {k: v["instrument"]["instrument_id"] for k, v in second.items()})

    def test_bond_is_distinct_from_etf_future_and_curve_tenor(self):
        registry = InstrumentRegistry()
        treasury = next(item for item in fixture_catalog(TODAY, "t").securities if item.cusip == "91282CRF0")
        bond_id = canonical_treasury_id(treasury)
        etf_id = register_etf_fund(symbol="IEF", registry=registry)
        future_id = register_future_contract_reference(contract_id="ZNZ26", family_root="ZN", contract_month="2026-12",
                                                       expiration="2026-12-19", registry=registry)
        self.assertEqual(len({bond_id, etf_id, future_id}), 3)
        row = by_cusip(read(service(), limit=500))["91282CRF0"]
        # The 10Y curve point is a reference observation attached to the row, never its identity.
        self.assertEqual(row["reference_tenor"], "10Y")
        self.assertNotEqual(row["instrument"]["instrument_id"], "10Y")
        self.assertEqual(row["fields"]["reference_rate"]["basis"], "NOMINAL_PAR_10Y")

    def test_corporate_identity_prefers_cusip_then_isin_and_terms_disambiguate(self):
        registry = InstrumentRegistry()
        by_cusip_id = register_bond(issuer="ISSUER A", maturity_date="2031-05-15", coupon="5.0", cusip="037833DX5", registry=registry)
        self.assertEqual(registry.get(by_cusip_id).descriptor.tradability, Tradability.REFERENCE_ONLY)
        by_isin_id = register_bond(issuer="ISSUER A", maturity_date="2031-05-15", coupon="5.0", isin="US037833DX52", registry=registry)
        other_maturity = register_bond(issuer="ISSUER A", maturity_date="2033-05-15", coupon="5.0", registry=registry)
        other_coupon = register_bond(issuer="ISSUER A", maturity_date="2033-05-15", coupon="5.5", registry=registry)
        self.assertEqual(len({by_cusip_id, by_isin_id, other_maturity, other_coupon}), 4)


# ---------------------------------------------------------------------- query
class BondQueryTests(unittest.TestCase):
    def setUp(self):
        self.svc = service()

    def test_default_query_lists_outstanding_treasuries_by_maturity(self):
        payload = read(self.svc, descending=False)  # the UI's Bonds default: maturity ascending
        cusips = [row["cusip"] for row in payload["rows"]]
        self.assertEqual(payload["result_count"], 8)
        self.assertEqual(payload["unfiltered_count"], 8)
        self.assertEqual(cusips[0], "91282CDC2")  # nearest maturity first (2026-10-15)
        self.assertNotIn("91282CHY0", cusips)  # matured
        self.assertNotIn("912797WJ2", cusips)  # announced, not issued
        self.assertEqual(payload["market_session"], "PUBLICATION_BASED")
        self.assertEqual(payload["evaluation"], "CATALOG")
        self.assertEqual(payload["coverage"]["TREASURY"], {"state": "CURRENT", "count": 8})
        # S16: without an N-PORT catalog the fund-held categories say so; never a folded zero.
        self.assertEqual(payload["coverage"]["CORPORATE"]["state"], "NOT_CONFIGURED")
        self.assertIsNone(payload["coverage"]["CORPORATE"]["count"])

    def test_search_by_cusip_description_type_and_maturity(self):
        self.assertEqual([r["cusip"] for r in read(self.svc, search="912810us5")["rows"]], ["912810US5"])
        self.assertEqual(read(self.svc, search="treasury")["result_count"], 8)
        self.assertEqual({r["cusip"] for r in read(self.svc, search="tips")["rows"]}, {"91282CDC2", "912810US5"})
        self.assertEqual([r["cusip"] for r in read(self.svc, search="2036-08")["rows"]], ["91282CRF0"])
        self.assertEqual(read(self.svc, search="ACME")["result_count"], 0)

    def test_type_maturity_coupon_and_flag_filters(self):
        def cusips(*rules):
            return {r["cusip"] for r in read(self.svc, filters=[{"id": str(i), **rule} for i, rule in enumerate(rules)], limit=500)["rows"]}

        self.assertEqual(cusips({"field": "security_type", "operator": "in", "value": ["Bill"]}), {"912797VN4", "912797WA1"})
        self.assertEqual(cusips({"field": "tips", "operator": "eq", "value": "Yes"}), {"91282CDC2", "912810US5"})
        self.assertEqual(cusips({"field": "frn", "operator": "eq", "value": "yes"}), {"91282CRD5"})
        self.assertEqual(cusips({"field": "years_to_maturity", "operator": "gt", "value": 20}), {"912810UW6", "912810US5"})
        self.assertEqual(cusips({"field": "maturity_bucket", "operator": "eq", "value": "<1Y"}), {"912797VN4", "91282CDC2", "912797WA1"})
        self.assertEqual(cusips({"field": "maturity_year", "operator": "between", "value": [2036, 2046]}), {"91282CRF0", "912810UX4"})
        self.assertEqual(cusips({"field": "coupon", "operator": "gte", "value": 5}), {"912810UW6", "912810UX4"})
        self.assertEqual(cusips({"field": "outstanding", "operator": "gt", "value": 60}), {"91282CRD5", "912797VN4"})

    def test_sorting_is_stable_with_missing_values_last(self):
        rows = read(self.svc, sort="coupon", descending=True, limit=500)["rows"]
        coupons = [row["fields"]["coupon"]["value"] for row in rows]
        present = [value for value in coupons if value is not None]
        self.assertEqual(present, sorted(present, reverse=True))
        self.assertEqual(coupons[len(present):], [None] * (len(coupons) - len(present)))  # bills and the FRN last
        missing = [row["instrument"]["instrument_id"] for row in rows[len(present):]]
        self.assertEqual(missing, sorted(missing))  # canonical id tie-break
        ascending = read(self.svc, sort="coupon", descending=False, limit=500)["rows"]
        self.assertIsNone(ascending[-1]["fields"]["coupon"]["value"])

    def test_pages_are_disjoint_complete_and_pinned(self):
        first = read(self.svc, limit=3)
        self.assertEqual((first["returned"], first["has_more"], first["result_set_id"]), (3, True, "2026-09-27T20:00:00Z"))
        seen = [row["cusip"] for row in first["rows"]]
        offset = 3
        while True:
            page = read(self.svc, limit=3, offset=offset, result_set=first["result_set_id"])
            seen += [row["cusip"] for row in page["rows"]]
            offset += page["returned"]
            if not page["has_more"]:
                break
        self.assertEqual(len(seen), 8)
        self.assertEqual(len(set(seen)), 8)
        with self.assertRaises(ValueError) as raised:
            read(self.svc, limit=3, offset=3, result_set="2026-01-01T00:00:00Z")
        self.assertEqual(str(raised.exception), "RESULT_SET_CHANGED")

    def test_missing_sort_uses_the_universe_default(self):
        self.assertEqual(parse_query(universe=BONDS).sort, "maturity")

    def test_invalid_requests_are_rejected(self):
        with self.assertRaises(ValueError) as raised:
            parse_query(universe=BONDS, filters=[{"id": "a", "field": "float_shares", "operator": "lt", "value": 1}])
        self.assertEqual(str(raised.exception), "FILTER_UNIVERSE_MISMATCH")
        for sort in ("reference_rate", "indicative_rate", "price"):
            with self.assertRaises(ValueError):
                parse_query(universe=BONDS, sort=sort)
        with self.assertRaises(ValueError):
            validate_filters([{"id": "a", "field": "coupon", "operator": "contains", "value": "5"}], universe=BONDS)
        self.assertTrue(is_sortable(BONDS, "maturity"))
        self.assertTrue(is_sortable(BONDS, "outstanding"))

    def test_date_change_revalidates_outstanding(self):
        self.assertIn("91282CDC2", by_cusip(read(self.svc)))
        self.svc.set_today(date(2026, 10, 15))  # the TIPS matures today
        payload = read(self.svc, limit=500)
        self.assertNotIn("91282CDC2", by_cusip(payload))
        self.assertEqual(payload["result_count"], 7)


# ----------------------------------------------------------- row truth states
class BondRowTruthTests(unittest.TestCase):
    def setUp(self):
        self.rows = by_cusip(read(service(), limit=500))

    def test_terms_and_auction_facts_keep_their_own_clocks(self):
        note = self.rows["91282CRF0"]["fields"]
        self.assertEqual((note["coupon"]["value"], note["coupon"]["state"]), (4.625, "CURRENT_METADATA"))
        self.assertEqual((note["auction_yield"]["value"], note["auction_yield"]["as_of"], note["auction_yield"]["basis"]),
                         (4.834, "2026-09-09", "HIGH_YIELD"))
        self.assertEqual((note["outstanding"]["value"], note["outstanding"]["as_of"]), (52.623, "2026-08-31"))
        self.assertEqual(note["reference_rate"]["as_of"], "2026-09-25")
        self.assertEqual(note["reference_rate"]["state"], "REFERENCE")

    def test_bill_tips_and_frn_semantics(self):
        bill = self.rows["912797WA1"]
        self.assertIsNone(bill["fields"]["coupon"]["value"])
        self.assertEqual(bill["fields"]["coupon"]["state"], "UNAVAILABLE")
        self.assertEqual(bill["fields"]["auction_yield"]["basis"], "HIGH_INVESTMENT_RATE")
        tips = self.rows["912810US5"]
        self.assertIsNone(tips["fields"]["auction_yield"]["value"])  # a real yield never sorts with nominal yields
        self.assertEqual(tips["fields"]["auction_real_yield"]["value"], 2.973)
        self.assertEqual((tips["reference_tenor"], tips["fields"]["reference_rate"]["basis"]), ("30Y real", "REAL_PAR_30Y"))
        frn = self.rows["91282CRD5"]
        self.assertIsNone(frn["fields"]["reference_rate"]["value"])
        self.assertEqual(frn["reference_reason"], "FRN_INDEXED_TO_13_WEEK_BILL")
        self.assertEqual(frn["fields"]["auction_discount_margin"]["value"], 0.04)

    def test_closing_bill_bid_attaches_only_to_the_named_cusip(self):
        self.assertEqual(self.rows["912797VN4"]["fields"]["indicative_rate"]["value"], 3.97)
        self.assertEqual(self.rows["912797VN4"]["fields"]["indicative_rate"]["basis"], "CLOSING_BID_COUPON_EQUIVALENT")
        self.assertEqual(self.rows["912797WA1"]["fields"]["indicative_rate"]["value"], 4.48)  # on-the-run 52-week on 2026-09-25
        self.assertIsNone(self.rows["912810UW6"]["fields"]["indicative_rate"]["value"])  # a bond is never in the bill feed
        self.assertIsNone(self.rows["91282CRF0"]["fields"]["indicative_rate"]["value"])

    def test_missing_values_are_null_never_zero(self):
        for row in self.rows.values():
            for name, field in row["fields"].items():
                if field["value"] is None:
                    self.assertEqual(field["state"], "UNAVAILABLE", (row["cusip"], name))
                    self.assertIsNone(field["as_of"])


# ------------------------------------------------------------- source states
class BondSourceStateTests(unittest.TestCase):
    def test_not_configured_without_the_treasury_flag(self):
        svc = service(env={})
        payload = read(svc)
        self.assertEqual((payload["source_error"], payload["rows"], payload["result_count"]), ("TREASURY_NOT_CONFIGURED", [], 0))
        self.assertEqual(payload["provider_health"][0]["state"], "NOT_CONFIGURED")
        self.assertEqual(payload["coverage"]["TREASURY"], {"state": "UNAVAILABLE", "count": None})  # never a count of 0
        self.assertEqual(svc.catalog_loads, 0)
        self.assertIsNone(svc.row_for("XA01:0000000000000000")[0])

    def test_catalog_failure_then_last_good_catalog_is_degraded(self):
        clock, calls = Clock(), []

        def loader(today, fetched_at):
            calls.append(1)
            if len(calls) > 1:
                raise FixedIncomeSourceError("HTTP_503")
            return fixture_catalog(today, fetched_at)

        svc = service(catalog_loader=loader, clock=clock)
        self.assertEqual(read(svc)["result_count"], 8)
        clock.value += 7 * 3600
        payload = read(svc)
        self.assertEqual((payload["result_count"], payload["provider_health"][0]["state"],
                          payload["provider_health"][0]["reason"]), (8, "DEGRADED", "HTTP_503"))

    def test_first_catalog_failure_is_unavailable_not_empty_truth(self):
        def down(today, fetched_at):
            raise FixedIncomeSourceError("SOURCE_UNREACHABLE")

        payload = read(service(catalog_loader=down))
        self.assertEqual((payload["source_error"], payload["provider_health"][0]["state"]), ("SOURCE_UNREACHABLE", "UNAVAILABLE"))

    def test_curve_failure_keeps_the_catalog(self):
        def no_curve(today, fetched_at):
            return TreasuryRates((), (), (), {NOMINAL: "HTTP_500", REAL: "HTTP_500"}, fetched_at)

        payload = read(service(rates_loader=no_curve), limit=500)
        self.assertEqual(payload["result_count"], 8)
        health = {item["provider"]: item for item in payload["provider_health"]}
        self.assertEqual((health["US_TREASURY_DAILY_RATES"]["state"], health["US_TREASURY_DAILY_RATES"]["reason"]),
                         ("UNAVAILABLE", "HTTP_500"))
        self.assertTrue(all(row["fields"]["reference_rate"]["value"] is None for row in payload["rows"]))
        self.assertTrue(all(row["reference_reason"] in ("CURVE_UNAVAILABLE", "FRN_INDEXED_TO_13_WEEK_BILL") for row in payload["rows"]))

    def test_sources_are_cached_at_source_level_not_per_row(self):
        clock = Clock()
        svc = service(clock=clock)
        for _ in range(3):
            read(svc, limit=500)
        for row in read(svc, limit=500)["rows"]:
            svc.preview(row["instrument"]["instrument_id"], [])
        self.assertEqual((svc.catalog_loads, svc.rates_loads), (1, 1))
        clock.value += 31 * 60
        read(svc)
        self.assertEqual((svc.catalog_loads, svc.rates_loads), (1, 2))  # curve refreshes; immutable terms do not

    def test_no_streaming_quotes_for_bonds(self):
        svc = service()
        window = svc.window(["XA01:A"])
        self.assertEqual(window["quotes"]["XA01:A"]["reason"], "NO_STREAMING_BOND_QUOTES")
        self.assertEqual(window["market_session"], "PUBLICATION_BASED")

    def test_payloads_pass_the_secret_leak_audit(self):
        svc = service()
        payload = read(svc, limit=500)
        assert_no_secrets_in_payload(payload, context="screener bonds")
        instrument = payload["rows"][0]["instrument"]["instrument_id"]
        assert_no_secrets_in_payload(svc.preview(instrument, []), context="bond preview")
        assert_no_secrets_in_payload(svc.rates_curve(instrument), context="rates curve")


# ---------------------------------------------------------------- preview
class BondPreviewTests(unittest.TestCase):
    def setUp(self):
        self.svc = service()
        self.ids = {row["cusip"]: row["instrument"]["instrument_id"] for row in read(self.svc, limit=500)["rows"]}

    def items(self, cusip: str, filters=()) -> tuple[dict, dict[str, dict]]:
        preview = self.svc.preview(self.ids[cusip], list(filters))
        return preview, {f"{section['id']}.{item['id']}": item for section in preview["sections"] for item in section["items"]}

    def test_note_preview_has_terms_auction_analytics_and_reference(self):
        preview, items = self.items("91282CRF0")
        self.assertEqual(preview["schema_version"], "screener-bond-preview/1.0.0")
        self.assertEqual(preview["instrument"]["tradability"], "REFERENCE_ONLY")
        self.assertEqual(items["identity.cusip"]["value"], "91282CRF0")
        self.assertEqual(items["terms.coupon"]["value"], 4.625)
        self.assertEqual(items["terms.par"]["value"], "Per 100 of par")
        self.assertEqual(items["auction.price"]["value"], 98.361116)
        self.assertEqual(items["market.price"]["class"], "UNAVAILABLE")
        self.assertEqual(items["market.latest_trade"]["source"], "FINRA_TRACE")
        self.assertAlmostEqual(items["analytics.modified"]["value"], 7.8274, places=3)
        self.assertEqual(items["analytics.modified"]["class"], "DERIVED")
        self.assertIn("not a current market measure", items["analytics.modified"]["note"])
        self.assertEqual(items["analytics.ytm"]["class"], "UNAVAILABLE")
        self.assertEqual((items["rates.reference"]["value"], items["rates.reference"]["class"]), (5.17, "REFERENCE"))
        self.assertIn("not this security's yield", items["rates.reference"]["note"])
        self.assertEqual(items["rates.reference_change"]["value"], -1.0)
        self.assertEqual(items["rates.spread"]["class"], "UNAVAILABLE")
        self.assertEqual(items["auction.bid_to_cover"]["note"], "An auction fact; not a directional signal")

    def test_bill_tips_frn_previews_branch_by_type(self):
        _, bill = self.items("912797VN4")
        self.assertIsNone(bill["terms.coupon"]["value"])
        self.assertIn("discount instruments", bill["terms.coupon"]["note"])
        self.assertEqual(bill["market.closing_ce"]["value"], 3.97)
        self.assertEqual(bill["terms.frequency"]["value"], "None (discount instrument)")
        self.assertEqual(bill["auction.direct"]["unit"], "share_percent")
        self.assertAlmostEqual(bill["analytics.macaulay"]["value"], 30 / 365, places=4)
        self.assertEqual(bill["analytics.modified"]["class"], "UNAVAILABLE")
        _, tips = self.items("912810US5")
        self.assertEqual(tips["auction.high_yield"]["label"], "High yield (real)")
        self.assertEqual((tips["auction.unadjusted_price"]["value"], tips["auction.adjusted_price"]["value"]), (88.31705, 91.015136))
        self.assertIn("(real)", tips["analytics.modified"]["label"])
        self.assertIn("30Y real", tips["rates.reference"]["label"])
        _, frn = self.items("91282CRD5")
        self.assertEqual(frn["analytics.duration"]["class"], "UNAVAILABLE")
        self.assertIn("floating-rate", frn["analytics.duration"]["note"])
        self.assertEqual(frn["auction.margin"]["value"], 0.04)

    def test_no_equity_concepts_and_capabilities_are_truthful(self):
        preview, items = self.items("91282CRF0")
        labels = " ".join(item["label"].lower() for item in items.values())
        for word in EQUITY_ONLY:
            self.assertNotIn(word, labels)
        capabilities = {item["panel"]: item["state"] for item in preview["capabilities"]}
        self.assertEqual(capabilities["rates_curve"], "SUPPORTED")
        self.assertEqual(capabilities["options"], "NOT_APPLICABLE")
        self.assertEqual(capabilities["short_squeeze"], "NOT_APPLICABLE")
        self.assertEqual({capabilities[p] for p in ("charts", "order_flow", "cvd", "level2")}, {"UNAVAILABLE"})
        clocks = {source["id"]: source["clock"] for source in preview["sources"]}
        self.assertEqual(clocks["TREASURY_CATALOG"], "EVENT_REFERENCE")
        self.assertEqual(clocks["TREASURY_CURVE"], "DAILY_PUBLICATION")
        self.assertEqual(clocks["FINRA_TRACE"], "TRANSACTION")
        self.assertNotIn("LIVE", {source["state"] for source in preview["sources"]})

    def test_why_it_matched_uses_the_bond_predicate(self):
        preview, _ = self.items("91282CRF0", [{"id": "c", "field": "coupon", "operator": "gt", "value": 4}])
        item = preview["why"]["matched"]["items"][0]
        self.assertEqual(item["text"], "Coupon 4.625% is above 4.000%")
        self.assertTrue(item["passed"])

    def test_unknown_instrument_has_no_preview(self):
        self.assertIsNone(self.svc.preview("XA01:0000000000000000", []))


# -------------------------------------------------------------- Rates & Curve
class RatesCurvePanelTests(unittest.TestCase):
    def setUp(self):
        self.svc = service()
        self.ids = {row["cusip"]: row["instrument"]["instrument_id"] for row in read(self.svc, limit=500)["rows"]}

    def test_curve_spreads_shape_breakevens_and_history(self):
        payload = self.svc.rates_curve(None)
        self.assertEqual(payload["schema_version"], "screener-rates-curve/1.0.0")
        self.assertEqual((payload["nominal"]["publication_date"], payload["nominal"]["state"]), ("2026-09-25", "PUBLICATION_CURRENT"))
        self.assertEqual(len(payload["nominal"]["points"]), 14)
        self.assertEqual(payload["nominal"]["previous"]["publication_date"], "2026-09-24")
        self.assertIsNone(payload["nominal"]["month_ago"])  # the excerpt has no publication ≥ 28 days earlier
        self.assertEqual({s["id"]: s["value_bp"] for s in payload["spreads"]}, {"2s10s": 36.0, "3m10y": 93.0, "5s30s": 51.0, "10s30s": 32.0})
        self.assertEqual(payload["shape"]["state"], "UPWARD_SLOPING")
        self.assertEqual(len(payload["breakevens"]["items"]), 5)
        self.assertIsNone(payload["selected"])

    def test_selected_bond_reference_without_a_fabricated_spread(self):
        payload = self.svc.rates_curve(self.ids["91282CRF0"])
        selected = payload["selected"]
        self.assertEqual((selected["cusip"], selected["reference"]["tenor"], selected["reference"]["value"]), ("91282CRF0", "10Y", 5.17))
        self.assertEqual(selected["spread"]["state"], "UNAVAILABLE")
        self.assertEqual(payload["credit"]["state"], "NOT_CONFIGURED")
        self.assertEqual(payload["finra"]["trace"]["state"], "FINRA_TERMS_REQUIRED")
        self.assertEqual(payload["finra"]["aggregates"]["state"], "NOT_CONFIGURED")
        states = {source["id"]: source["state"] for source in payload["sources"]}
        self.assertEqual(states["FRED_RATES"], "NOT_CONFIGURED")
        self.assertEqual(states["FINRA_AGGREGATES"], "NOT_CONFIGURED")
        self.assertIsNone(self.svc.rates_curve("XA01:0000000000000000"))

    def test_fred_credit_context_is_broad_context_only(self):
        fred = {"state": "PUBLICATION_CURRENT", "reason": None, "items": [
            {"group": "CREDIT", "id": "US_IG_SPREAD", "value": 0.82, "observation_date": "2026-09-24"},
            {"group": "POLICY", "id": "US_POLICY_RATE_UPPER", "value": 4.5, "observation_date": "2026-09-25"}]}
        payload = service(fred=lambda **_: fred).rates_curve(self.ids["91282CRF0"])
        self.assertEqual([item["id"] for item in payload["credit"]["items"]], ["US_IG_SPREAD"])
        self.assertEqual([item["id"] for item in payload["policy"]["items"]], ["US_POLICY_RATE_UPPER"])
        self.assertIn("never an individual bond's spread", payload["credit"]["note"])
        self.assertEqual(payload["selected"]["spread"]["state"], "UNAVAILABLE")

    def test_route_is_read_scoped(self):
        self.assertEqual(policy_for_route("GET", "/screener/rates-curve").capability, "state.read")


# ------------------------------------------------------------ saved screens
class BondSavedScreenTests(unittest.TestCase):
    def screen(self, **overrides) -> dict:
        base = {"name": "Long TIPS", "universe": BONDS, "view": "Treasuries",
                "filters": [{"id": "t", "field": "tips", "operator": "eq", "value": "Yes"}],
                "sort": {"field": "maturity", "descending": False},
                "columns": {"visible": ["symbol", "security_type", "maturity"], "order": ["symbol", "security_type", "maturity"],
                            "widths": {"symbol": 220}, "pinned": ["symbol"]}}
        return {**base, **overrides}

    def test_bond_screen_persists_configuration_only(self):
        saved = validate_screen(self.screen())
        self.assertEqual((saved["universe"], saved["view"], saved["version"]), (BONDS, "Treasuries", 2))
        self.assertEqual(set(saved), {"id", "version", "name", "universe", "filters", "view", "sort", "columns"})

    def test_bond_screen_rejects_equity_views_columns_and_filters(self):
        for bad in (self.screen(view="Short Squeeze"),
                    self.screen(columns={"visible": ["symbol", "float_shares"], "order": ["symbol", "float_shares"], "widths": {}, "pinned": []}),
                    self.screen(filters=[{"id": "f", "field": "short_float_pct", "operator": "gt", "value": 20}]),
                    self.screen(sort={"field": "reference_rate_missing", "descending": True})):
            with self.assertRaises(ValueError):
                validate_screen(bad)
        # A version-1 screen can never claim the Bonds universe (S5 migration rule).
        with self.assertRaises(ValueError):
            validate_screen(self.screen(version=1))

    def test_panel_layout_accepts_rates_curve(self):
        layout = validate_panel_layout({"version": 1, "open_panels": ["charts", "rates_curve"], "active_panel": "rates_curve",
                                        "dock_height": 300, "dockview_layout": None})
        self.assertEqual(layout["open_panels"], ["charts", "rates_curve"])


if __name__ == "__main__":
    unittest.main()

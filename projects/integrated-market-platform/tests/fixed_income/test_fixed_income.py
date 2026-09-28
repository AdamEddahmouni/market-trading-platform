"""S9 fixed-income adapters and analytics: Treasury catalog, daily rates, bond math, FRED, FINRA.

Fixtures are real excerpts of official U.S. Treasury publications (test-only).
Bond-math test vectors are Treasury's own published auction prices and rates.
"""

from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from datetime import date
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.fixed_income import analytics as A  # noqa: E402
from market_platform_foundation.fixed_income import fred_context, finra_fixed_income as finra  # noqa: E402
from market_platform_foundation.fixed_income.http import FixedIncomeSourceError, get_json, http_get  # noqa: E402
from market_platform_foundation.fixed_income.treasury_catalog import (  # noqa: E402
    BILL, BOND, FRN, NOTE, TIPS, build_catalog, cusip_valid, days_to_maturity, load_treasury_catalog,
    maturity_bucket, years_to_maturity,
)
from market_platform_foundation.fixed_income.treasury_rates import (  # noqa: E402
    NOMINAL, REAL, CurvePoint, CurvePublication, TreasuryRates, breakevens, curve_shape, curve_spreads, fetch_rates,
    match_reference, parse_bills, parse_curve, publication_state,
)

FIXTURES = ROOT / "tests" / "fixtures" / "fixed_income"
TODAY = date(2026, 9, 27)


def auctions() -> list[dict]:
    return json.loads((FIXTURES / "auctions_excerpt.json").read_text(encoding="utf-8"))["data"]


def mspd() -> list[dict]:
    return json.loads((FIXTURES / "mspd_excerpt.json").read_text(encoding="utf-8"))["data"]


def xml(name: str) -> bytes:
    return (FIXTURES / f"{name}_202609_excerpt.xml").read_bytes()


def catalog(rows: list[dict] | None = None, today: date = TODAY, **kwargs):
    return build_catalog(auctions() if rows is None else rows, kwargs.pop("mspd_rows", mspd()), today=today,
                         fetched_at="2026-09-27T20:00:00Z", mspd_record_date=date(2026, 8, 31), **kwargs)


def number(value: str) -> float | None:
    return None if value in (None, "", "null") else float(value)


def day(value: str) -> date | None:
    return None if value in (None, "", "null") else date.fromisoformat(value[:10])


# ------------------------------------------------------------------ catalog
class TreasuryCatalogTests(unittest.TestCase):
    def test_every_type_is_typed_from_provider_flags(self):
        result = {item.cusip: item for item in catalog().outstanding(TODAY)}
        self.assertEqual(result["912797WA1"].kind, BILL)
        self.assertEqual(result["91282CRF0"].kind, NOTE)
        self.assertEqual(result["912810UW6"].kind, BOND)
        self.assertEqual(result["912810US5"].kind, TIPS)
        self.assertEqual(result["912810US5"].base_type, BOND)  # a TIPS bond, typed by the inflation flag
        self.assertEqual(result["91282CRD5"].kind, FRN)
        self.assertEqual(result["91282CRD5"].payments_per_year, 4)
        self.assertEqual(result["91282CRD5"].frn_spread_pct, 0.05)
        self.assertIsNone(result["91282CRD5"].coupon_pct)

    def test_terms_are_parsed_not_inferred(self):
        note = next(item for item in catalog().securities if item.cusip == "91282CRF0")
        self.assertEqual((note.coupon_pct, note.payments_per_year, note.original_term), (4.625, 2, "10-Year"))
        self.assertEqual((note.issue_date, note.maturity_date), (date(2026, 8, 17), date(2036, 8, 15)))
        self.assertEqual(note.description, "U.S. Treasury Note 4.625% Aug 2036")
        self.assertEqual(note.mspd_outstanding_musd, 52623.0393)

    def test_bill_has_no_coupon_and_discount_rate_is_never_a_coupon(self):
        bill = next(item for item in catalog().securities if item.cusip == "912797WA1")
        self.assertIsNone(bill.coupon_pct)
        self.assertEqual(bill.payments_per_year, 0)
        self.assertEqual(bill.description, "U.S. Treasury Bill Sep 2 2027")

    def test_reopenings_reconcile_to_one_security_with_original_issue(self):
        bond = next(item for item in catalog().securities if item.cusip == "912810UW6")
        self.assertEqual(len(bond.auctions), 2)
        self.assertTrue(bond.reopened)
        self.assertEqual(bond.issue_date, date(2026, 8, 17))  # original issue, not the reopening's
        self.assertEqual(bond.latest_auction.auction_date, date(2026, 9, 10))
        self.assertTrue(bond.latest_auction.reopening)

    def test_exact_duplicate_rows_collapse_to_one_auction(self):
        rows = auctions() + [deepcopy(row) for row in auctions() if row["cusip"] == "91282CRF0"]
        note = next(item for item in catalog(rows).securities if item.cusip == "91282CRF0")
        self.assertEqual(len(note.auctions), 2)

    def test_conflicting_terms_for_one_cusip_fail_closed(self):
        rows = auctions()
        conflicting = deepcopy(next(row for row in rows if row["cusip"] == "91282CRF0"))
        conflicting["maturity_date"] = "2036-11-15"
        result = catalog(rows + [conflicting])
        self.assertNotIn("91282CRF0", {item.cusip for item in result.securities})
        self.assertEqual(result.rejected["CONFLICTING_TERMS"], 1)
        coupon = deepcopy(next(row for row in rows if row["cusip"] == "912810UW6"))
        coupon["int_rate"] = "5.250000"
        self.assertNotIn("912810UW6", {item.cusip for item in catalog(rows + [coupon]).securities})

    def test_malformed_rows_are_rejected_and_counted(self):
        base = next(row for row in auctions() if row["cusip"] == "912797WA1")
        bad = [{**base, "cusip": "912797WA2"}, {**base, "cusip": "91282CRF0", "maturity_date": "2036-13-45"},
               {**base, "cusip": "91282CRF0", "security_type": "Strip"}, {**base, "issue_date": "null"},
               {**base, "high_yield": "four"}]
        result = catalog(bad, mspd_rows=[])
        self.assertEqual(result.securities, ())
        self.assertEqual(sum(result.rejected.values()), 5)
        self.assertEqual(set(result.rejected), {"INVALID_CUSIP", "MALFORMED_DATE", "UNKNOWN_SECURITY_TYPE",
                                                "MISSING_DATE", "MALFORMED_NUMBER"})

    def test_matured_and_announced_securities_are_not_current(self):
        result = catalog()
        cusips = {item.cusip for item in result.outstanding(TODAY)}
        self.assertNotIn("91282CHY0", cusips)  # in the 2026-08-31 MSPD, matured 2026-09-15
        self.assertNotIn("912797WJ2", cusips)  # auctioned 2026-09-29, issues 2026-10-01
        self.assertEqual(result.announced, 1)
        tips = next(item for item in result.securities if item.cusip == "91282CDC2")
        self.assertTrue(tips.outstanding_on(date(2026, 10, 14)))
        self.assertFalse(tips.outstanding_on(date(2026, 10, 15)))  # maturity date: no longer outstanding
        self.assertNotIn("91282CDC2", {item.cusip for item in result.outstanding(date(2026, 10, 15))})

    def test_mspd_only_security_is_kept_with_its_own_terms(self):
        rows = [row for row in auctions() if row["cusip"] != "91282CRF0"]
        note = next(item for item in catalog(rows).securities if item.cusip == "91282CRF0")
        self.assertEqual((note.kind, note.coupon_pct, note.source), (NOTE, 4.625, "US_TREASURY_FISCAL_DATA_MSPD"))
        self.assertEqual(note.payments_per_year, 2)  # from MSPD's two interest payment dates
        self.assertEqual(note.auctions, ())

    def test_mspd_failure_keeps_catalog_with_amounts_unavailable(self):
        calls = []

        def get(url, timeout):
            calls.append(url)
            if "mspd" in url:
                raise FixedIncomeSourceError("HTTP_503")
            return json.dumps({"data": auctions(), "meta": {"total-pages": 1}}).encode()

        result = load_treasury_catalog(today=TODAY, fetched_at="t", get=get)
        self.assertEqual(result.mspd_error, "HTTP_503")
        self.assertTrue(result.securities)
        self.assertTrue(all(item.mspd_outstanding_musd is None for item in result.securities))
        self.assertIn("filter=maturity_date:gte:2026-09-27", calls[0])

    def test_auction_failure_and_malformed_payload_raise_stable_codes(self):
        def down(url, timeout):
            raise FixedIncomeSourceError("SOURCE_UNREACHABLE")

        with self.assertRaises(FixedIncomeSourceError) as raised:
            load_treasury_catalog(today=TODAY, fetched_at="t", get=down)
        self.assertEqual(raised.exception.code, "SOURCE_UNREACHABLE")
        with self.assertRaises(FixedIncomeSourceError) as raised:
            load_treasury_catalog(today=TODAY, fetched_at="t", get=lambda url, timeout: b"{\"data\": 3}")
        self.assertEqual(raised.exception.code, "MALFORMED_RESPONSE")

    def test_paging_is_bounded(self):
        def get(url, timeout):
            return json.dumps({"data": [], "meta": {"total-pages": 99}}).encode()

        with self.assertRaises(FixedIncomeSourceError) as raised:
            load_treasury_catalog(today=TODAY, fetched_at="t", get=get)
        self.assertEqual(raised.exception.code, "RESPONSE_TOO_LARGE")

    def test_cusip_check_digit(self):
        for value in ("912797WA1", "91282CRF0", "912810UW6", "912810US5", "91282CRD5"):
            self.assertTrue(cusip_valid(value), value)
        for value in ("912797WA2", "91282CRF", "", "TREASURY10Y", "912797wa1x"):
            self.assertFalse(cusip_valid(value), value)

    def test_days_years_and_buckets_at_calendar_boundaries(self):
        self.assertEqual(days_to_maturity(date(2026, 9, 28), TODAY), 1)
        self.assertEqual(days_to_maturity(TODAY, TODAY), 0)
        self.assertEqual(days_to_maturity(date(2028, 3, 1), date(2028, 2, 28)), 2)  # leap day counted
        self.assertAlmostEqual(years_to_maturity(date(2027, 9, 27), TODAY), 365 / 365.25)
        self.assertEqual(maturity_bucket(0.0), "<1Y")
        self.assertEqual(maturity_bucket(0.9999), "<1Y")
        self.assertEqual(maturity_bucket(1.0), "1-3Y")
        self.assertEqual(maturity_bucket(10.0), "10-20Y")
        self.assertEqual(maturity_bucket(20.0), "20Y+")
        self.assertIsNone(maturity_bucket(-0.01))


# -------------------------------------------------------------------- rates
class TreasuryRatesTests(unittest.TestCase):
    def setUp(self):
        self.nominal = parse_curve(xml("nominal"), NOMINAL)
        self.real = parse_curve(xml("real"), REAL)
        self.bills = parse_bills(xml("bill"))

    def test_nominal_and_real_curves_parse_with_publication_dates(self):
        latest = self.nominal[-1]
        self.assertEqual(latest.date, date(2026, 9, 25))
        self.assertEqual([p.tenor for p in latest.points][:3], ["1M", "1.5M", "2M"])
        self.assertEqual((latest.value("2Y"), latest.value("10Y"), latest.value("30Y")), (4.81, 5.17, 5.49))
        self.assertEqual([p.tenor for p in self.real[-1].points], ["5Y", "7Y", "10Y", "20Y", "30Y"])
        self.assertEqual(self.real[-1].value("10Y"), 2.83)

    def test_bill_rates_attach_to_the_named_cusip_only(self):
        latest = self.bills[-1]
        quote = latest.for_cusip("912797VN4")
        self.assertEqual((quote.term, quote.discount_rate, quote.coupon_equivalent), ("4W", 3.9, 3.97))
        self.assertIsNone(latest.for_cusip("91282CRF0"))

    def test_missing_tenor_is_absent_not_zero(self):
        body = xml("nominal").replace(b"<d:BC_2MONTH m:type=\"Edm.Double\">4.20</d:BC_2MONTH>", b"<d:BC_2MONTH m:type=\"Edm.Double\"></d:BC_2MONTH>")
        latest = parse_curve(body, NOMINAL)[-1]
        self.assertIsNone(latest.value("2M"))
        self.assertNotIn("2M", [p.tenor for p in latest.points])

    def test_malformed_xml_is_a_stable_failure(self):
        with self.assertRaises(FixedIncomeSourceError):
            parse_curve(b"<feed><entry>", NOMINAL)

    def test_publication_state(self):
        self.assertEqual(publication_state(date(2026, 9, 25), TODAY), "PUBLICATION_CURRENT")  # Friday, read Sunday
        self.assertEqual(publication_state(date(2026, 9, 22), TODAY), "STALE")
        self.assertEqual(publication_state(None, TODAY), "UNAVAILABLE")

    def test_derived_spreads_and_shape(self):
        spreads = {item["id"]: item for item in curve_spreads(self.nominal[-1])}
        self.assertEqual(spreads["2s10s"]["value_bp"], 36.0)
        self.assertEqual(spreads["3m10y"]["value_bp"], 93.0)
        self.assertEqual(spreads["5s30s"]["value_bp"], 51.0)
        self.assertEqual(spreads["10s30s"]["value_bp"], 32.0)
        self.assertTrue(all(item["class"] == "DERIVED" and item["publication_date"] == "2026-09-25" for item in spreads.values()))
        self.assertEqual(curve_shape(self.nominal[-1])["state"], "UPWARD_SLOPING")

        def pub(**values):
            years = {"3M": 0.25, "2Y": 2.0, "10Y": 10.0}
            return CurvePublication(NOMINAL, TODAY, tuple(CurvePoint(t, years[t], v) for t, v in values.items()))

        self.assertEqual(curve_shape(pub(**{"3M": 5.0, "2Y": 4.8, "10Y": 4.2}))["state"], "INVERTED")
        self.assertEqual(curve_shape(pub(**{"3M": 4.0, "2Y": 4.5, "10Y": 4.45}))["state"], "FLAT_OR_MIXED")
        self.assertEqual(curve_shape(None)["state"], "UNAVAILABLE")
        self.assertNotIn("recession", json.dumps(curve_shape(self.nominal[-1])).lower())

    def test_breakevens_need_the_same_publication_date(self):
        result = breakevens(self.nominal[-1], self.real[-1])
        ten = next(item for item in result["items"] if item["tenor"] == "10Y")
        self.assertAlmostEqual(ten["value"], 5.17 - 2.83)
        self.assertEqual(breakevens(self.nominal[-1], self.real[-2])["reason"], "PUBLICATION_DATE_MISMATCH")

    def test_nearest_tenor_reference_is_a_benchmark_not_an_identity(self):
        latest = self.nominal[-1]
        ref = match_reference(9.88, latest)
        self.assertEqual((ref["tenor"], ref["value"], ref["method"]), ("10Y", 5.17, "NEAREST_PUBLISHED_TENOR"))
        self.assertNotIn("cusip", ref)
        self.assertEqual(match_reference(6.0, latest)["tenor"], "5Y")  # tie 5Y/7Y → shorter tenor
        self.assertEqual(match_reference(0.01, latest)["tenor"], "1M")
        self.assertEqual(match_reference(3.0, self.real[-1])["reason"], "OUTSIDE_CURVE_RANGE")
        self.assertEqual(match_reference(5.0, None)["reason"], "CURVE_UNAVAILABLE")

    def test_fetch_rates_reports_each_feed_independently(self):
        def get(url, timeout):
            if "real_yield" in url:
                raise FixedIncomeSourceError("HTTP_500")
            if "bill_rates" in url:
                return xml("bill") if "202609" in url else b"<feed/>"
            return xml("nominal") if "202609" in url else b"<feed/>"

        result = fetch_rates(today=TODAY, fetched_at="t", get=get)
        self.assertEqual(result.latest_nominal.date, date(2026, 9, 25))
        self.assertEqual(result.real, ())
        self.assertEqual(result.errors, {REAL: "HTTP_500"})
        self.assertEqual(result.latest_bills.date, date(2026, 9, 25))

    def test_http_allowlist(self):
        with self.assertRaises(FixedIncomeSourceError) as raised:
            http_get("https://example.com/data")
        self.assertEqual(raised.exception.code, "HOST_NOT_ALLOWED")
        with self.assertRaises(FixedIncomeSourceError) as raised:
            get_json(lambda url, timeout: b"not json", "https://api.fiscaldata.treasury.gov/x")
        self.assertEqual(raised.exception.code, "MALFORMED_RESPONSE")


# ----------------------------------------------------------------- analytics
class BondMathTests(unittest.TestCase):
    """Test vectors: Treasury's own published auction results in the fixture."""

    def test_nominal_price_from_yield_matches_treasury_published_prices(self):
        checked = 0
        for row in auctions():
            if row["security_type"] == "Bill" or row["floating_rate"] == "Yes" or number(row["high_price"]) is None:
                continue
            tips = row["inflation_index_security"] == "Yes"
            published = number(row["unadj_price"] if tips else row["high_price"])
            price = A.price_from_yield(number(row["high_yield"]), number(row["int_rate"]), 2, day(row["issue_date"]),
                                       day(row["maturity_date"]), dated_date=day(row["dated_date"]))
            self.assertAlmostEqual(price, published, delta=1e-5, msg=(row["cusip"], row["auction_date"]))
            recovered = A.yield_from_price(published, number(row["int_rate"]), 2, day(row["issue_date"]),
                                           day(row["maturity_date"]), dated_date=day(row["dated_date"]))
            self.assertAlmostEqual(recovered, number(row["high_yield"]), delta=5e-5)
            checked += 1
        self.assertGreaterEqual(checked, 8)

    def test_known_vector_ten_year_note(self):
        # 91282CRF0 reopening, auction 2026-09-09: 4.625% coupon, 4.834% high yield → 98.361116.
        result = A.fixed_coupon_analytics(4.834, 4.625, 2, date(2026, 9, 15), date(2036, 8, 15), dated_date=date(2026, 8, 15))
        self.assertAlmostEqual(result.clean_price, 98.361116, places=5)
        self.assertAlmostEqual(result.accrued, 4.625 / 2 * 31 / 184)
        self.assertLess(result.modified_duration, result.macaulay_years)
        self.assertAlmostEqual(result.macaulay_years, result.modified_duration * (1 + 0.04834 / 2))
        self.assertAlmostEqual(result.dv01, result.modified_duration * result.dirty_price * 1e-4, places=6)
        self.assertAlmostEqual(result.current_yield_pct, 4.625 / result.clean_price * 100)
        self.assertTrue(7.5 < result.modified_duration < 8.2)

    def test_negative_real_yield_is_supported(self):
        # 912810SV1 TIPS reopening 2021-08-19: 0.125% coupon at −0.292% real yield → unadjusted 112.836888.
        price = A.price_from_yield(-0.292, 0.125, 2, date(2021, 8, 31), date(2051, 2, 15), dated_date=date(2021, 8, 15))
        self.assertAlmostEqual(price, 112.836888, delta=2e-5)

    def test_bill_price_and_investment_rate_match_treasury(self):
        checked = 0
        for row in auctions():
            if row["security_type"] != "Bill" or number(row["high_price"]) is None:
                continue
            days = (day(row["maturity_date"]) - day(row["issue_date"])).days
            price = A.bill_price_from_discount(number(row["high_discnt_rate"]), days)
            self.assertAlmostEqual(price, number(row["high_price"]), places=6)
            rate = A.bill_investment_rate(price, days, day(row["issue_date"]))
            self.assertAlmostEqual(rate, number(row["high_investment_rate"]), delta=6e-4)  # published to 3 decimals
            checked += 1
        self.assertGreaterEqual(checked, 3)

    def test_zero_coupon_duration_is_time_to_maturity(self):
        self.assertAlmostEqual(A.bill_macaulay_years(182, date(2026, 9, 3)), 182 / 365)
        self.assertAlmostEqual(A.bill_macaulay_years(182, date(2027, 9, 3)), 182 / 366)  # year contains Feb 29 2028

    def test_coupon_schedule_end_of_month_and_semiannual(self):
        period = A.coupon_period(date(2026, 9, 27), date(2028, 2, 29), 2)
        self.assertEqual((period.previous, period.next), (date(2026, 8, 31), date(2027, 2, 28)))
        period = A.coupon_period(date(2026, 9, 27), date(2036, 8, 15), 2)
        self.assertEqual((period.previous, period.next, len(period.remaining)), (date(2026, 8, 15), date(2027, 2, 15), 20))
        self.assertEqual(A.coupon_period(date(2026, 8, 15), date(2036, 8, 15), 2).previous, date(2026, 8, 15))
        self.assertAlmostEqual(A.accrued_interest(4.625, 2, date(2026, 8, 15), date(2036, 8, 15)), 0.0)

    def test_failure_conditions(self):
        cases = {
            "FRN_FLOATING_COUPON": lambda: A.price_from_yield(4.0, 4.0, 4, TODAY, date(2028, 7, 31), floating=True),
            "MISSING_TERMS": lambda: A.price_from_yield(4.0, None, 2, TODAY, date(2030, 8, 15)),
            "MATURED": lambda: A.price_from_yield(4.0, 4.0, 2, date(2030, 8, 15), date(2030, 8, 15)),
            "NON_POSITIVE_PRICE": lambda: A.yield_from_price(0.0, 4.0, 2, TODAY, date(2030, 8, 15)),
            "UNSUPPORTED_FREQUENCY": lambda: A.price_from_yield(4.0, 4.0, 3, TODAY, date(2030, 8, 15)),
            "IRREGULAR_FIRST_PERIOD": lambda: A.price_from_yield(4.0, 4.0, 2, date(2026, 9, 30), date(2036, 8, 15),
                                                                 dated_date=date(2026, 9, 1)),
            "NOT_YET_DATED": lambda: A.accrued_interest(4.0, 2, TODAY, date(2036, 8, 15), dated_date=date(2026, 10, 15)),
        }
        for code, call in cases.items():
            with self.assertRaises(A.FixedIncomeMathError, msg=code) as raised:
                call()
            self.assertEqual(raised.exception.code, code)
        with self.assertRaises(A.FixedIncomeMathError):
            A.current_yield(None, 99.0)
        with self.assertRaises(A.FixedIncomeMathError):
            A.bill_investment_rate(-1.0, 90, TODAY)


# ---------------------------------------------------------------- FRED / FINRA
class FakeFred:
    def __init__(self, fail: set[str] = frozenset()):
        self.fail, self.calls = fail, []

    def series_observations(self, series_id, **kwargs):
        self.calls.append((series_id, kwargs))
        if series_id in self.fail:
            raise OSError("boom api_key=SHOULD_NOT_LEAK")
        return {"observations": [
            {"date": "2026-09-25", "value": ".", "realtime_start": "2026-09-26", "realtime_end": "9999-12-31"},
            {"date": "2026-09-24", "value": "4.33", "realtime_start": "2026-09-25", "realtime_end": "9999-12-31"},
        ]}


class FredContextTests(unittest.TestCase):
    def test_not_configured_without_key_or_flag(self):
        with mock.patch.object(fred_context, "api_key_present", return_value=False):
            result = fred_context.load_fred_context(today=TODAY, retrieved="2026-09-27T20:00:00Z")
        self.assertEqual((result["state"], result["reason"], result["items"]), ("NOT_CONFIGURED", "FRED_API_KEY_MISSING", []))
        with mock.patch.object(fred_context, "api_key_present", return_value=True), \
                mock.patch.object(fred_context, "live_enabled", return_value=False):
            self.assertEqual(fred_context.load_fred_context(today=TODAY, retrieved="t")["reason"], "IMP_FRED_LIVE_NOT_SET")

    def test_latest_non_missing_value_keeps_its_knowledge_interval(self):
        client = FakeFred(fail={"BAMLH0A0HYM2"})
        with mock.patch.object(fred_context, "api_key_present", return_value=True), \
                mock.patch.object(fred_context, "live_enabled", return_value=True):
            result = fred_context.load_fred_context(today=TODAY, retrieved="2026-09-27T20:00:00Z", client_factory=lambda: client)
        items = {item["id"]: item for item in result["items"]}
        self.assertEqual(result["state"], "PARTIAL")
        self.assertEqual(items["US_POLICY_RATE_UPPER"]["value"], 4.33)
        self.assertEqual(items["US_POLICY_RATE_UPPER"]["observation_date"], "2026-09-24")
        self.assertEqual(items["US_POLICY_RATE_UPPER"]["knowledge_start_date"], "2026-09-25")
        self.assertIsNone(items["US_HY_SPREAD"]["value"])
        self.assertEqual(items["US_IG_SPREAD"]["usage_rights"], "redistribution_review_required")
        self.assertEqual(client.calls[0][1]["observation_start"], "2026-08-13")
        self.assertNotIn("SHOULD_NOT_LEAK", json.dumps(result))


class FakeFinraTransport:
    def __init__(self, records=None, error: Exception | None = None):
        self.records, self.error, self.posts = records, error, []

    def post(self, path, payload):
        self.posts.append((path, payload))
        if self.error:
            raise self.error
        return mock.Mock(records=self.records)


class FinraFixedIncomeTests(unittest.TestCase):
    RECORDS = [  # field names from FINRA's published treasuryDailyAggregates metadata
        {"tradeDate": "2026-09-24", "productCategory": "Treasury Notes", "yearsToMaturity": "5-7", "benchmark": "OTR",
         "atsInterdealerCount": 10, "atsInterdealerVolume": 1e9, "dealerCustomerCount": 20, "dealerCustomerVolume": 2e9,
         "volumeWeightedAveragePrice": 99.5},
        {"tradeDate": "2026-09-25", "productCategory": "Treasury Notes", "yearsToMaturity": "5-7", "benchmark": "OTR",
         "atsInterdealerCount": 11, "atsInterdealerVolume": 1.1e9, "dealerCustomerCount": 21, "dealerCustomerVolume": 2.1e9,
         "volumeWeightedAveragePrice": 99.6},
        {"tradeDate": "bad", "productCategory": "Treasury Bills"},
    ]

    def test_security_level_trace_requires_licensed_terms(self):
        capability = finra.trace_capability()
        self.assertEqual(capability["state"], "FINRA_TERMS_REQUIRED")
        self.assertEqual(capability["corporate_coverage"], "CORPORATE_COVERAGE_UNAVAILABLE")

    def test_aggregates_not_configured_without_the_flag(self):
        result = finra.load_treasury_aggregates(today=TODAY, env={})
        self.assertEqual((result["state"], result["reason"]), ("NOT_CONFIGURED", "IMP_FINRA_LIVE_NOT_SET"))

    def test_aggregates_normalize_the_latest_trade_date_only(self):
        transport = FakeFinraTransport(self.RECORDS)
        result = finra.load_treasury_aggregates(today=TODAY, transport_factory=lambda: transport)
        self.assertEqual((result["state"], result["trade_date"], result["dropped"]), ("PUBLICATION_CURRENT", "2026-09-25", 1))
        self.assertEqual(len(result["rows"]), 1)
        row = result["rows"][0]
        self.assertEqual(row["dealerCustomerVolume"], 2.1e9)
        self.assertFalse({"bid", "ask", "price", "last"} & set(row))  # aggregates are never quotes
        path, payload = transport.posts[0]
        self.assertEqual(path, "/data/group/fixedIncomeMarket/name/treasuryDailyAggregates")
        self.assertEqual(payload["dateRangeFilters"][0]["startDate"], "2026-09-17")

    def test_aggregate_failures_are_stable_codes(self):
        auth = finra.load_treasury_aggregates(today=TODAY, transport_factory=lambda: FakeFinraTransport(error=OSError("AUTH_FAILED token=abc")))
        self.assertEqual((auth["state"], auth["reason"]), ("UNAVAILABLE", "AUTH_FAILED"))
        limited = finra.load_treasury_aggregates(today=TODAY, transport_factory=lambda: FakeFinraTransport(error=OSError("FINRA_HTTP_429")))
        self.assertEqual(limited["reason"], "FINRA_HTTP_429")
        malformed = finra.load_treasury_aggregates(today=TODAY, transport_factory=lambda: FakeFinraTransport(records="x"))
        self.assertEqual(malformed["reason"], "MALFORMED_RESPONSE")
        empty = finra.load_treasury_aggregates(today=TODAY, transport_factory=lambda: FakeFinraTransport([]))
        self.assertEqual((empty["state"], empty["reason"]), ("UNAVAILABLE", "NO_RECORDS"))
        self.assertNotIn("abc", json.dumps(auth))


if __name__ == "__main__":
    unittest.main()

"""S15 Futures CFTC coverage: every root decided, mapping evidence, report semantics, values, PIT.

The root list is the Moomoo OpenD Futures catalog observed 2026-09-29 (root, venue, lead
contract only). CFTC rows are the real S12 fixtures, varied in memory for edge cases.
No network.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cftc.contracts import CotReportFamily  # noqa: E402
from market_platform_foundation.cftc.release_schedule import (  # noqa: E402
    HOLIDAY_FIXTURE_POSITION, release_for_position_date,
)
from market_platform_foundation.cftc.root_coverage import (  # noqa: E402
    SINGLE_STOCK_ROOTS, UNMAPPED_ROOTS, classify_root, coverage_summary,
)
from market_platform_foundation.cftc.screener_positioning import (  # noqa: E402
    NOT_IN_LATEST_RELEASE, POSITIONING_MARKETS, MappingBasis, build_positioning,
)

FIXTURES = ROOT / "tests" / "fixtures" / "cftc"
CATALOG = json.loads((FIXTURES / "s15_futures_roots_20260929.json").read_text(encoding="utf-8"))
TFF_ES = json.loads((FIXTURES / "s12_tff_futures_only_es.json").read_text(encoding="utf-8"))
DIS_CL = json.loads((FIXTURES / "s12_disaggregated_futures_only_cl.json").read_text(encoding="utf-8"))
AFTER = datetime(2026, 9, 28, tzinfo=UTC)

#: Reference: the 67 roots verified against CFTC Public Reporting on 2026-09-29 (market code, report).
#: A registry change must be made here too, deliberately.
EXPECTED_MAPPED = {
    "10Y": ("04360Y", "TFF"), "6A": ("232741", "TFF"), "6B": ("096742", "TFF"), "6C": ("090741", "TFF"),
    "6E": ("099741", "TFF"), "6J": ("097741", "TFF"), "6L": ("102741", "TFF"), "6M": ("095741", "TFF"),
    "6N": ("112741", "TFF"), "6S": ("092741", "TFF"), "6Z": ("122741", "TFF"), "ALI": ("191691", "DIS"),
    "BTC": ("133741", "TFF"), "BZ": ("06765T", "DIS"), "CL": ("067651", "DIS"), "EMD": ("33874A", "TFF"),
    "ES": ("13874A", "TFF"), "ETH": ("146021", "TFF"), "GC": ("088691", "DIS"), "GF": ("061641", "DIS"),
    "HE": ("054642", "DIS"), "HG": ("085692", "DIS"), "HO": ("022651", "DIS"), "KE": ("001612", "DIS"),
    "LE": ("057642", "DIS"), "M2K": ("239747", "TFF"), "MBT": ("133742", "TFF"), "MES": ("13874U", "TFF"),
    "METH": ("146022", "TFF"), "MGC": ("088695", "DIS"), "MHG": ("085699", "DIS"), "MNQ": ("209747", "TFF"),
    "MSL": ("177742", "TFF"), "MXP": ("176741", "TFF"), "MYM": ("124608", "TFF"), "NG": ("023651", "DIS"),
    "NIY": ("240743", "TFF"), "NKD": ("240741", "TFF"), "NQ": ("209742", "TFF"), "PA": ("075651", "DIS"),
    "PL": ("076651", "DIS"), "QG": ("023655", "DIS"), "RB": ("111659", "DIS"), "RP": ("299741", "TFF"),
    "RTY": ("239742", "TFF"), "RY": ("399741", "TFF"), "SI": ("084691", "DIS"), "SIL": ("084694", "DIS"),
    "SOL": ("177741", "TFF"), "SR3": ("134741", "TFF"), "TN": ("043607", "TFF"), "UB": ("020604", "TFF"),
    "VX": ("1170E1", "TFF"), "XK": ("005603", "DIS"), "XRP": ("176740", "TFF"), "YM": ("124603", "TFF"),
    "ZB": ("020601", "TFF"), "ZC": ("002602", "DIS"), "ZF": ("044601", "TFF"), "ZL": ("007601", "DIS"),
    "ZM": ("026603", "DIS"), "ZN": ("043602", "TFF"), "ZO": ("004603", "DIS"), "ZR": ("039601", "DIS"),
    "ZS": ("005602", "DIS"), "ZT": ("042601", "TFF"), "ZW": ("001602", "DIS"),
}


def _audit_module():
    spec = importlib.util.spec_from_file_location("cftc_coverage_audit", ROOT / "tools" / "screener" / "cftc_coverage_audit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def es_row(**changes):
    """The 2026-09-22 E-mini S&P 500 TFF row with fields replaced (None deletes the column)."""

    row = copy.deepcopy(next(item for item in TFF_ES if item["report_date_as_yyyy_mm_dd"].startswith("2026-09-22")))
    for key, value in changes.items():
        if value is None:
            row.pop(key, None)
        else:
            row[key] = value
    return row


def category(report, cid):
    return next(item for item in report["categories"] if item["id"] == cid)


class RootAccountingTests(unittest.TestCase):
    def test_every_current_root_is_classified(self):
        summary = coverage_summary((item["root"], item["exchange"]) for item in CATALOG)
        self.assertEqual(summary["universe_roots"], 178)
        self.assertEqual(summary["by_status"], {"MAPPED": 67, "NO_CFTC_REPORT": 110, "AMBIGUOUS": 1, "UNCLASSIFIED": 0})
        self.assertEqual(summary["by_reason"], {"AMBIGUOUS_MAPPING": 1, "NO_CFTC_MARKET_FOUND": 33, "PRODUCT_NOT_COVERED": 77})
        self.assertEqual([(item["id"], item["count"]) for item in summary["breakdown"]],
                         [("MAPPED", 67), ("PRODUCT_NOT_COVERED", 77), ("NO_CFTC_MARKET_FOUND", 33), ("AMBIGUOUS_MAPPING", 1)])

    def test_mapped_roots_match_the_verified_reference(self):
        mapped = {item["root"] for item in CATALOG
                  if classify_root(item["root"], exchange=item["exchange"])["status"] == "MAPPED"}
        self.assertEqual(mapped, set(EXPECTED_MAPPED))
        actual = {root: (market.code, market.report.value[:3]) for root, market in POSITIONING_MARKETS.items()}
        self.assertEqual(actual, EXPECTED_MAPPED)

    def test_registry_is_the_catalog(self):
        self.assertEqual(set(POSITIONING_MARKETS) | set(UNMAPPED_ROOTS), {item["root"] for item in CATALOG})
        self.assertFalse(set(POSITIONING_MARKETS) & set(UNMAPPED_ROOTS))

    def test_micro_ether_is_meth_not_met(self):
        self.assertNotIn("MET", POSITIONING_MARKETS)
        self.assertEqual(classify_root("METH")["market"]["cftc_contract_market_code"], "146022")
        self.assertEqual(classify_root("MET")["status"], "UNCLASSIFIED")

    def test_mini_vix_stays_ambiguous(self):
        decision = classify_root("VXM", exchange="US_CBOE")
        self.assertEqual((decision["status"], decision["reason"], decision["candidate_code"]),
                         ("AMBIGUOUS", "AMBIGUOUS_MAPPING", "1170E1"))
        self.assertIsNone(decision["market"])
        self.assertIn("Mini VIX", decision["note"])

    def test_single_stock_future_has_no_cot_market(self):
        self.assertEqual(len(SINGLE_STOCK_ROOTS), 77)
        decision = classify_root("SNVDA")
        self.assertEqual((decision["status"], decision["reason"]), ("NO_CFTC_REPORT", "PRODUCT_NOT_COVERED"))
        self.assertIn("Single-stock", decision["label"])
        self.assertIsNone(decision["market"])

    def test_no_cftc_market_root(self):
        for root in ("2YY", "M6E", "MZC", "1OZ"):
            with self.subTest(root):
                decision = classify_root(root)
                self.assertEqual((decision["status"], decision["reason"]), ("NO_CFTC_REPORT", "NO_CFTC_MARKET_FOUND"))
        self.assertEqual(classify_root("1OZ")["candidate_code"], "088LM1")  # a rejected Coinbase market, recorded

    def test_exchange_mismatch_fails_closed(self):
        self.assertEqual(classify_root("ES", exchange="US_CME")["status"], "MAPPED")
        self.assertEqual(classify_root("ES", exchange=None)["status"], "MAPPED")  # no venue: nothing to contradict
        mismatch = classify_root("ES", exchange="US_CBOT")
        self.assertEqual((mismatch["status"], mismatch["reason"], mismatch["market"]), ("AMBIGUOUS", "EXCHANGE_MISMATCH", None))
        report = _audit_module().audit([{"root": "ES", "exchange": "US_CBOT", "symbol": "ESZ26"}])
        self.assertIn("EXCHANGE_MISMATCH ES US_CBOT", report["findings"])

    def test_new_provider_root_is_unclassified_and_fails_the_audit(self):
        decision = classify_root("ZZNEW", exchange="US_CME")
        self.assertEqual((decision["status"], decision["market"]), ("UNCLASSIFIED", None))
        audit = _audit_module()
        clean = audit.audit(CATALOG)
        self.assertEqual(clean["findings"], [])
        dirty = audit.audit([*CATALOG, {"root": "ZZNEW", "exchange": "US_CME", "symbol": "ZZNEWZ26"}])
        self.assertIn("UNCLASSIFIED_ROOT ZZNEW", dirty["findings"])

    def test_every_mapping_states_its_basis(self):
        for root, market in POSITIONING_MARKETS.items():
            with self.subTest(root):
                self.assertIn(market.basis, tuple(MappingBasis))
                self.assertIn(market.confidence, ("EXACT", "SUPPORTED_ALIAS"))
                if market.basis == MappingBasis.CURATED_OFFICIAL_ALIAS:
                    self.assertTrue(market.note)


class MarketIdentityTests(unittest.TestCase):
    def kc_wheat(self, name):
        row = copy.deepcopy(DIS_CL[0])
        row.update({"cftc_contract_market_code": "001612", "market_and_exchange_names": name})
        return build_positioning([row], POSITIONING_MARKETS["KE"], now=AFTER)

    def test_market_rename_keeps_code_identity(self):
        current = self.kc_wheat("WHEAT-HRW - CHICAGO BOARD OF TRADE")
        former = self.kc_wheat("WHEAT - KANSAS CITY BOARD OF TRADE")
        self.assertEqual(current["cftc_contract_market_code"], former["cftc_contract_market_code"])
        self.assertNotIn("MARKET_NAME_DIFFERS_FROM_REFERENCE", current["quality_flags"])
        self.assertNotIn("MARKET_NAME_DIFFERS_FROM_REFERENCE", former["quality_flags"])
        self.assertEqual(former["market_name"], "WHEAT - KANSAS CITY BOARD OF TRADE")  # history is shown as published
        renamed = self.kc_wheat("WHEAT-HRW NEW NAME - CHICAGO BOARD OF TRADE")
        self.assertIsNotNone(renamed)  # an unknown new name is flagged, not unmapped
        self.assertIn("MARKET_NAME_DIFFERS_FROM_REFERENCE", renamed["quality_flags"])

    def test_whitespace_is_not_a_rename(self):
        row = es_row(market_and_exchange_names="E-MINI S&P 500  - CHICAGO MERCANTILE EXCHANGE")
        self.assertNotIn("MARKET_NAME_DIFFERS_FROM_REFERENCE",
                         build_positioning([row], POSITIONING_MARKETS["ES"], now=AFTER)["quality_flags"])

    def test_known_market_absent_from_latest_release(self):
        older = [row for row in TFF_ES if not row["report_date_as_yyyy_mm_dd"].startswith("2026-09-22")]
        report = build_positioning(older, POSITIONING_MARKETS["ES"], now=AFTER)
        self.assertEqual(report["report_date"], "2026-09-15")
        self.assertIn(NOT_IN_LATEST_RELEASE, report["quality_flags"])
        self.assertEqual(report["coverage_state"], "MAPPED")  # still a known market, not "no CFTC market"
        latest = build_positioning(TFF_ES, POSITIONING_MARKETS["ES"], now=AFTER)
        self.assertNotIn(NOT_IN_LATEST_RELEASE, latest["quality_flags"])

    def test_identical_duplicates_resolve_deterministically(self):
        first, second = es_row(id="B"), es_row(id="A")
        for rows in ([first, second], [second, first]):
            report = build_positioning(rows, POSITIONING_MARKETS["ES"], now=AFTER)
            self.assertEqual((report["source_row_id"], report["quality_state"]), ("A", "OK"))
            self.assertIn("DUPLICATE_ROW_IGNORED", report["quality_flags"])

    def test_conflicting_duplicates_fail_closed(self):
        rows = [es_row(id="A"), es_row(id="B", dealer_positions_long_all="1")]
        report = build_positioning(rows, POSITIONING_MARKETS["ES"], now=AFTER)
        self.assertEqual(report["quality_state"], "CONFLICTING_DUPLICATE_ROWS")
        self.assertEqual((report["categories"], report["open_interest"], report["change_open_interest"]), ([], None, None))


class ReportFamilyTests(unittest.TestCase):
    def test_tff_and_disaggregated_categories_stay_distinct(self):
        tff = build_positioning(TFF_ES, POSITIONING_MARKETS["ES"], now=AFTER)
        dis = build_positioning(DIS_CL, POSITIONING_MARKETS["CL"], now=AFTER)
        tff_ids = [item["id"] for item in tff["categories"]]
        dis_ids = [item["id"] for item in dis["categories"]]
        self.assertEqual(tff_ids, ["DEALER_INTERMEDIARY", "ASSET_MANAGER_INSTITUTIONAL", "LEVERAGED_FUNDS",
                                   "OTHER_REPORTABLES", "NON_REPORTABLES"])
        self.assertEqual(dis_ids, ["PRODUCER_MERCHANT", "SWAP_DEALER", "MANAGED_MONEY", "OTHER_REPORTABLE", "NON_REPORTABLE"])
        self.assertEqual(category(tff, "ASSET_MANAGER_INSTITUTIONAL")["label"], "Asset manager / institutional")
        self.assertEqual(category(dis, "MANAGED_MONEY")["label"], "Managed money")
        self.assertNotEqual(tff["report_label"], dis["report_label"])
        self.assertEqual((tff["report"], dis["report"]), ("TFF", "DISAGGREGATED"))

    def test_financial_and_physical_families(self):
        for root in ("ES", "ZN", "6E", "VX", "BTC", "METH", "SR3"):
            self.assertEqual(POSITIONING_MARKETS[root].report, CotReportFamily.TFF)
        for root in ("CL", "NG", "GC", "HG", "ZC", "KE", "LE", "HE"):
            self.assertEqual(POSITIONING_MARKETS[root].report, CotReportFamily.DISAGGREGATED)
        self.assertNotIn(CotReportFamily.LEGACY, {market.report for market in POSITIONING_MARKETS.values()})


class ValueTests(unittest.TestCase):
    def report(self, **changes):
        return build_positioning([es_row(**changes)], POSITIONING_MARKETS["ES"], now=AFTER)

    def test_positive_long_short_spreading_and_derived_net(self):
        report = self.report()
        dealer = category(report, "DEALER_INTERMEDIARY")
        row = es_row()
        self.assertEqual(dealer["long"], int(float(row["dealer_positions_long_all"])))
        self.assertEqual(dealer["short"], int(float(row["dealer_positions_short_all"])))
        self.assertEqual(dealer["spreading"], int(float(row["dealer_positions_spread_all"])))
        self.assertEqual(dealer["net"], dealer["long"] - dealer["short"])
        self.assertTrue(report["net_method"].startswith("DERIVED"))
        self.assertTrue(report["oi_method"].startswith("DERIVED"))
        self.assertIsNone(category(report, "NON_REPORTABLES")["spreading"])  # no spreading column in TFF non-reportables

    def test_zero_is_not_missing(self):
        report = self.report(dealer_positions_long_all="0", asset_mgr_positions_short=None)
        dealer = category(report, "DEALER_INTERMEDIARY")
        self.assertEqual((dealer["long"], dealer["long_pct_oi"]), (0, 0.0))
        self.assertEqual(dealer["net"], -dealer["short"])
        manager = category(report, "ASSET_MANAGER_INSTITUTIONAL")
        self.assertIsNone(manager["short"])
        self.assertIsNone(manager["net"])  # never long − 0
        self.assertIsNone(manager["short_pct_oi"])

    def test_negative_weekly_change(self):
        dealer = category(self.report(change_in_dealer_long_all="-1234", change_in_dealer_short_all="66"), "DEALER_INTERMEDIARY")
        self.assertEqual((dealer["change_long"], dealer["net_change"]), (-1234, -1300))

    def test_open_interest_ratio(self):
        report = self.report(open_interest_all="200000", dealer_positions_long_all="50000")
        self.assertEqual(category(report, "DEALER_INTERMEDIARY")["long_pct_oi"], 25.0)

    def test_zero_and_missing_open_interest_give_no_ratio(self):
        zero = self.report(open_interest_all="0")
        self.assertEqual(zero["open_interest"], 0)
        self.assertTrue(all(item["long_pct_oi"] is None and item["short_pct_oi"] is None for item in zero["categories"]))
        missing = self.report(open_interest_all=None)
        self.assertIsNone(missing["open_interest"])
        self.assertTrue(all(item["long_pct_oi"] is None for item in missing["categories"]))


class PointInTimeTests(unittest.TestCase):
    def test_thursday_before_friday_release_does_not_see_tuesday_report(self):
        thursday = build_positioning(TFF_ES, POSITIONING_MARKETS["ES"], now=datetime(2026, 9, 24, 20, 0, tzinfo=UTC))
        self.assertEqual(thursday["report_date"], "2026-09-15")
        friday = build_positioning(TFF_ES, POSITIONING_MARKETS["ES"], now=datetime(2026, 9, 25, 19, 30, tzinfo=UTC))
        self.assertEqual((friday["report_date"], friday["publication_time"]), ("2026-09-22", "2026-09-25T19:30:00Z"))

    def test_holiday_delayed_release(self):
        release = release_for_position_date(HOLIDAY_FIXTURE_POSITION)
        self.assertTrue(release.delayed)
        row = es_row(report_date_as_yyyy_mm_dd="2026-11-24T00:00:00.000", id="261124-ES")
        rows = [row, *TFF_ES]
        normal_friday = build_positioning(rows, POSITIONING_MARKETS["ES"], now=datetime(2026, 11, 27, 21, 0, tzinfo=UTC))
        self.assertNotEqual(normal_friday["report_date"], "2026-11-24")  # not public on the usual Friday
        before = build_positioning(rows, POSITIONING_MARKETS["ES"], now=datetime(2026, 11, 30, 20, 29, tzinfo=UTC))
        self.assertNotEqual(before["report_date"], "2026-11-24")
        after = build_positioning(rows, POSITIONING_MARKETS["ES"], now=datetime(2026, 11, 30, 20, 30, tzinfo=UTC))
        self.assertEqual((after["report_date"], after["publication_basis"], after["publication_time"]),
                         ("2026-11-24", "CFTC_OFFICIAL_SCHEDULE_DELAYED", "2026-11-30T20:30:00Z"))

    def test_report_date_is_never_the_release_time(self):
        report = build_positioning(TFF_ES, POSITIONING_MARKETS["ES"], now=AFTER)
        self.assertEqual(report["report_date"], "2026-09-22")
        self.assertEqual(report["available_at"], report["publication_time"])
        self.assertNotEqual(report["publication_time"][:10], report["report_date"])


if __name__ == "__main__":
    unittest.main()

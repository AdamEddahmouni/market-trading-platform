"""S15 Futures CFTC coverage in the S12 Participants service: Positioning view, panel, Quick Preview.

Uses the S12 service harness (injected fakes over real CFTC fixture rows). No network.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_screener_s12 as s12  # noqa: E402  (the S12 service harness and fixtures)

FUT = [
    s12.row("FUT", "ESZ6", root="ES", company="E-mini S&P 500", exchange="US_CME"),
    s12.row("FUT", "CLX6", root="CL", company="Crude Oil", exchange="US_NYMEX"),
    s12.row("FUT", "ZOZ6", root="ZO", company="Oats", exchange="US_CBOT"),
    s12.row("FUT", "VXMV6", root="VXM", company="Mini VIX", exchange="US_CBOE"),
    s12.row("FUT", "SNVDAZ6", root="SNVDA", company="NVIDIA single-stock future", exchange=None),
    s12.row("FUT", "M6EZ6", root="M6E", company="Micro EUR/USD", exchange="US_CME"),
]
ROOTS_178 = json.loads((ROOT / "tests" / "fixtures" / "cftc" / "s15_futures_roots_20260929.json").read_text(encoding="utf-8"))


def futures_service(rows=FUT, cot_query=s12.cot_query):
    svc = s12.service(catalog={"FUTURES": rows})
    by_id = {item["instrument"]["instrument_id"]: item for item in rows}
    svc._row_for = lambda instrument_id, universe: by_id.get(instrument_id) if universe == "FUTURES" else None
    svc._cot_query = cot_query
    return svc


def panel(svc, instrument_id, compact=False):
    return svc.instrument(universe="FUTURES", instrument_id=instrument_id, lens="institutional", compact=compact)


class PositioningViewTests(unittest.TestCase):
    def test_every_root_is_explained(self):
        view = futures_service().positioning_view(universe="FUTURES")
        coverage = view["coverage"]
        self.assertEqual((view["state"], view["reason"]), ("PUBLICATION_CURRENT", None))  # decided roots are not "partial"
        self.assertEqual((coverage["universe_roots"], coverage["mapped_roots"], coverage["reported_roots"]), (6, 3, 2))
        self.assertEqual(coverage["by_status"], {"MAPPED": 3, "NO_CFTC_REPORT": 2, "AMBIGUOUS": 1, "UNCLASSIFIED": 0})
        self.assertEqual(coverage["mapped_without_report"], ["ZO"])  # a known market, not "no CFTC market"
        self.assertEqual([item["label"] for item in coverage["breakdown"]],
                         ["Mapped to a CFTC market", "Single-stock future · no COT market", "No CFTC market",
                          "Ambiguous CFTC market"])
        unmapped = {item["root"]: item for item in view["unmapped"]}
        self.assertEqual(set(unmapped), {"VXM", "SNVDA", "M6E"})
        self.assertEqual(coverage["unmapped_roots"], ["M6E", "SNVDA", "VXM"])
        self.assertEqual((unmapped["VXM"]["status"], unmapped["VXM"]["reason"]), ("AMBIGUOUS", "AMBIGUOUS_MAPPING"))
        self.assertEqual(unmapped["SNVDA"]["reason"], "PRODUCT_NOT_COVERED")
        self.assertEqual((unmapped["M6E"]["reason"], unmapped["M6E"]["contract"]), ("NO_CFTC_MARKET_FOUND", "M6EZ6"))
        for item in unmapped.values():
            self.assertTrue(item["note"])
            self.assertFalse({"long", "short", "net", "open_interest", "categories"} & set(item))  # never zero positions
        self.assertIn("Legacy", view["report_policy"])
        self.assertTrue(view["oi_method"].startswith("DERIVED"))

    def test_mapped_rows_carry_identity_and_evidence(self):
        view = futures_service().positioning_view(universe="FUTURES")
        groups = {group["report"]: group["rows"] for group in view["groups"]}
        es, cl = groups["TFF"][0], groups["DISAGGREGATED"][0]
        self.assertEqual((es["root"], es["contract"], es["cftc_contract_market_code"]), ("ES", "ESZ6", "13874A"))
        self.assertEqual(es["mapping"], {"basis": "EXCHANGE_PLUS_PRODUCT", "confidence": "EXACT", "note": None,
                                         "cftc_exchange": "CHICAGO MERCANTILE EXCHANGE", "provider_exchange": "US_CME",
                                         "former_names": []})
        self.assertEqual((es["coverage_state"], es["quality_state"]), ("MAPPED", "OK"))
        self.assertEqual((es["report_date"], es["publication_time"]), ("2026-09-22", "2026-09-25T19:30:00Z"))
        self.assertEqual(cl["report"], "DISAGGREGATED")
        self.assertIn("MANAGED_MONEY", {item["id"] for item in cl["categories"]})
        self.assertNotIn("MANAGED_MONEY", {item["id"] for item in es["categories"]})

    def test_unclassified_root_leaves_the_view_partial(self):
        view = futures_service([*FUT, s12.row("FUT", "ZZNEWZ6", root="ZZNEW", exchange="US_CME")]).positioning_view(universe="FUTURES")
        self.assertEqual((view["state"], view["reason"]), ("PARTIAL", "SOME_ROOTS_UNCLASSIFIED"))
        self.assertEqual(view["coverage"]["by_status"]["UNCLASSIFIED"], 1)

    def test_exchange_mismatch_is_not_shown_as_positioning(self):
        rows = [s12.row("FUT", "ESZ6", root="ES", exchange="US_CBOT"), *FUT[1:]]
        view = futures_service(rows).positioning_view(universe="FUTURES")
        self.assertEqual((view["state"], view["reason"]), ("PARTIAL", "EXCHANGE_MISMATCH"))
        self.assertEqual([row["root"] for group in view["groups"] for row in group["rows"]], ["CL"])
        self.assertEqual(next(item for item in view["unmapped"] if item["root"] == "ES")["reason"], "EXCHANGE_MISMATCH")

    def test_full_current_catalog(self):
        rows = [s12.row("FUT", item["symbol"], root=item["root"], exchange=item["exchange"]) for item in ROOTS_178]
        view = futures_service(rows).positioning_view(universe="FUTURES")
        coverage = view["coverage"]
        self.assertEqual((coverage["universe_roots"], coverage["mapped_roots"]), (178, 67))
        self.assertEqual(coverage["by_reason"], {"AMBIGUOUS_MAPPING": 1, "NO_CFTC_MARKET_FOUND": 33, "PRODUCT_NOT_COVERED": 77})
        self.assertEqual(view["state"], "PUBLICATION_CURRENT")
        self.assertEqual(len(view["unmapped"]), 111)


class PanelTests(unittest.TestCase):
    def test_mapped_root_panel(self):
        section = panel(futures_service(), "FUT:ESZ6")["sections"]["futures_positioning"]
        self.assertEqual((section["state"], section["root"], section["contract"]), ("PUBLICATION_CURRENT", "ES", "ESZ6"))
        self.assertEqual(section["coverage"]["status"], "MAPPED")
        self.assertEqual(section["report"]["mapping"]["cftc_exchange"], "CHICAGO MERCANTILE EXCHANGE")
        self.assertEqual(section["evidence_basis"], "CFTC_LARGE_TRADER_CONTEXT")

    def test_unmapped_root_panels_explain_why(self):
        svc = futures_service()
        for instrument_id, reason in (("FUT:VXMV6", "AMBIGUOUS_MAPPING"), ("FUT:SNVDAZ6", "PRODUCT_NOT_COVERED"),
                                      ("FUT:M6EZ6", "NO_CFTC_MARKET_FOUND")):
            with self.subTest(instrument_id):
                section = panel(svc, instrument_id)["sections"]["futures_positioning"]
                self.assertEqual((section["state"], section["reason"]), ("NO_MATCH", reason))
                self.assertNotIn("report", section)
                self.assertTrue(section["coverage"]["note"])

    def test_known_market_without_a_recent_report(self):
        section = panel(futures_service(), "FUT:ZOZ6")["sections"]["futures_positioning"]
        self.assertEqual((section["state"], section["reason"]), ("NO_DISCLOSURES", "KNOWN_MARKET_NOT_IN_RECENT_RELEASES"))
        self.assertEqual(section["coverage"]["status"], "MAPPED")

    def test_conflicting_duplicate_rows_fail_closed(self):
        def conflicting(dataset, where):
            rows = s12.cot_query(dataset, where)
            latest = copy.deepcopy(rows[0])
            latest.update({"id": "zz-conflict", "dealer_positions_long_all": "1", "prod_merc_positions_long": "1"})
            return [*rows, latest]

        section = panel(futures_service(cot_query=conflicting), "FUT:ESZ6")["sections"]["futures_positioning"]
        self.assertEqual((section["state"], section["reason"]), ("UNAVAILABLE", "CONFLICTING_DUPLICATE_ROWS"))
        self.assertEqual(section["report"]["categories"], [])

    def test_quick_preview_is_compact_and_explains_unmapped(self):
        svc = futures_service()
        mapped = panel(svc, "FUT:CLX6", compact=True)
        self.assertTrue(mapped["compact"])
        self.assertEqual(mapped["sections"]["futures_positioning"]["report"]["report"], "DISAGGREGATED")
        unmapped = panel(svc, "FUT:SNVDAZ6", compact=True)["sections"]["futures_positioning"]
        self.assertEqual(unmapped["coverage"]["label"], "Single-stock future · no COT market")

    def test_rapid_root_switching_returns_the_last_root(self):
        svc = futures_service()
        panel(svc, "FUT:ESZ6", compact=True)
        panel(svc, "FUT:VXMV6", compact=True)
        final = panel(svc, "FUT:CLX6", compact=True)
        section = final["sections"]["futures_positioning"]
        self.assertEqual(final["instrument"]["instrument_id"], "FUT:CLX6")
        self.assertEqual((section["root"], section["report"]["root"], section["report"]["cftc_contract_market_code"]),
                         ("CL", "CL", "067651"))
        self.assertEqual(section["coverage"]["root"], "CL")

    def test_lead_contract_roll_keeps_the_market(self):
        before = panel(futures_service(), "FUT:ESZ6")["sections"]["futures_positioning"]
        rolled_rows = [s12.row("FUT", "ESH7", root="ES", exchange="US_CME"), *FUT[1:]]
        after = panel(futures_service(rolled_rows), "FUT:ESH7")["sections"]["futures_positioning"]
        self.assertEqual((before["contract"], after["contract"]), ("ESZ6", "ESH7"))
        self.assertEqual(before["report"]["cftc_contract_market_code"], after["report"]["cftc_contract_market_code"])
        self.assertEqual(before["report"]["categories"], after["report"]["categories"])


if __name__ == "__main__":
    unittest.main()

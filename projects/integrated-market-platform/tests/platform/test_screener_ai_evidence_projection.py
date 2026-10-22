"""AI evidence projection must keep its exact shape and order per row.

``observations_for_row`` builds the bounded observation list that becomes the
AI packet's current-market and reference evidence. Membership tests were moved
to frozensets and the per-row ``decision_inputs`` read was hoisted out of the
capability loop; the emitted list, its capability-major order and its fact
values must be byte-identical, because ``build_candidate`` caps observations at
40 and any reordering would change what the model is allowed to see.

``reference_category`` gained memoization; a cached answer must be the answer.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.ui_api.screener_ai import (
    _REFERENCE_FIELDS,
    _TECHNICAL_FIELDS,
    observations_for_row,
)
from market_platform_foundation.ui_api.screener_admission import (
    EXCHANGE_TRADED_FUND,
    LISTED_EQUITY,
    REIT,
    SHELL_COMPANY,
    CLOSED_END_FUND,
    UNCLASSIFIED,
    reference_category,
)

NOW = "2026-10-02T15:00:00Z"
QUOTE_FIELDS = ("price", "bid", "ask", "spread_pct")


def reference_observations(row):
    """The original projection, transcribed: capability-major, bounded allowlists."""

    observations = []
    fields = row.get("fields") or {}
    for capability, allowed in (("QUOTE", QUOTE_FIELDS), ("TECHNICALS", _TECHNICAL_FIELDS),
                                ("RATES", _REFERENCE_FIELDS)):
        for status in row.get("decision_inputs", []):
            names = [name for name in status.get("covered_fields", []) if name in allowed]
            if not names:
                continue
            facts = {}
            for name in names:
                value = fields[name].get("value")
                if isinstance(value, (int, float)) and not isinstance(value, bool) and value == value \
                        and abs(value) != float("inf"):
                    facts[name] = value
            observations.append((capability, status, facts, []))
    return observations


def _status(capability, covered, source="FINVIZ_ELITE", state="SNAPSHOT"):
    return {"capability": capability, "covered_fields": list(covered), "source": source, "state": state,
            "delivery_mode": "SNAPSHOT", "policy": "L1_EVENT_V1", "basis": "PROVIDER_AS_OF",
            "decision_role": "CURRENT_MARKET_CONTEXT"}


def _row(covered_groups, values):
    fields = {name: {"value": value, "source": "FINVIZ_ELITE", "state": "SNAPSHOT", "as_of": NOW}
              for name, value in values.items()}
    return {"instrument": {"instrument_id": "EQ:S00001"}, "fields": fields,
            "decision_inputs": [_status(group[0], group[1]) for group in covered_groups]}


class ObservationProjectionParityTests(unittest.TestCase):
    def test_matches_the_reference_on_many_row_shapes(self) -> None:
        shapes = [
            (_row([("market_snapshot", ("price", "volume", "change_pct", "rsi_14"))],
                  {"price": 10.0, "volume": 100, "change_pct": 1.5, "rsi_14": 55.0, "bid": 9.9, "ask": 10.1}),
             ),
            (_row([("market_snapshot", ("price", "bid", "ask", "spread_pct")),
                   ("reference_fields", ("auction_yield", "outstanding"))],
                  {"price": 10.0, "bid": 9.9, "ask": 10.1, "spread_pct": 1.0,
                   "auction_yield": 4.5, "outstanding": 123.0}),
             ),
            (_row([("reference_fields", ("auction_yield",))], {"auction_yield": None}),
             ),
            (_row([("market_snapshot", ("price",))], {"price": float("nan")}),
             ),
            (_row([("market_snapshot", ("price", "unknown_field"))], {"price": 1.0}),
             ),
            (_row([], {"price": 1.0}),
             ),
            ({"instrument": {"instrument_id": "EQ:S00002"}, "fields": {}, "decision_inputs": []},
             ),
            ({"instrument": {"instrument_id": "EQ:S00003"}, "fields": {}},
             ),
            ({"instrument": {"instrument_id": "EQ:S00004"}, "fields": {"price": {"value": 1.0}},
              "decision_inputs": None},
             ),
            (_row([("market_snapshot", ()),
                   ("reference_fields", ()),
                   ("other", ("price",))],
                  {"price": 2.0, "auction_yield": 1.0}),
             ),
        ]
        for index, (row,) in enumerate(shapes):
            with self.subTest(shape=index):
                if row.get("decision_inputs", []) is None:
                    with self.assertRaises(TypeError):
                        reference_observations(row)
                    with self.assertRaises(TypeError):
                        observations_for_row(row, now=NOW)
                else:
                    self.assertEqual(observations_for_row(row, now=NOW), reference_observations(row))

    def test_capability_major_order_is_preserved(self) -> None:
        # Two statuses, each covering fields that belong to different capability
        # families. The emitted order must stay capability-major, not status-major.
        row = _row([("reference_fields", ("auction_yield", "volume")),
                    ("market_snapshot", ("price", "rsi_14"))],
                   {"price": 10.0, "rsi_14": 60.0, "volume": 5, "auction_yield": 2.0})
        observations = observations_for_row(row, now=NOW)
        self.assertEqual([item[0] for item in observations],
                         ["QUOTE", "TECHNICALS", "TECHNICALS", "RATES"])
        self.assertEqual([list(item[2]) for item in observations],
                         [["price"], ["volume"], ["rsi_14"], ["auction_yield"]])

    def test_non_finite_and_boolean_facts_are_excluded(self) -> None:
        row = _row([("market_snapshot", ("price", "volume", "rsi_14"))],
                   {"price": float("inf"), "volume": True, "rsi_14": float("nan")})
        observations = observations_for_row(row, now=NOW)
        self.assertEqual(observations[0][2], {})

    def test_a_row_without_decision_inputs_yields_nothing(self) -> None:
        self.assertEqual(observations_for_row({"fields": {"price": {"value": 1.0}}}, now=NOW), [])
        self.assertEqual(observations_for_row({}, now=NOW), [])

    def test_covered_field_order_inside_a_status_is_preserved(self) -> None:
        row = _row([("market_snapshot", ("volume", "price", "change_pct"))],
                   {"price": 1.0, "volume": 2, "change_pct": 3.0})
        quote, technicals = observations_for_row(row, now=NOW)
        self.assertEqual(quote[0], "QUOTE")
        self.assertEqual(list(quote[2]), ["price"])
        self.assertEqual(technicals[0], "TECHNICALS")
        self.assertEqual(list(technicals[2]), ["volume", "change_pct"])

    def test_every_projected_fact_is_finite(self) -> None:
        row = _row([("market_snapshot", ("price", "volume"))], {"price": 1.0, "volume": 2})
        for _capability, _status, facts, _quality in observations_for_row(row, now=NOW):
            for value in facts.values():
                self.assertIsInstance(value, (int, float))
                self.assertEqual(value, value)


class ReferenceCategoryTests(unittest.TestCase):
    def test_memoization_returns_the_same_classification(self) -> None:
        samples = ["Exchange Traded Fund", "exchange traded fund", "  EXCHANGE TRADED FUND ",
                   "REIT - Industrial", "reit", "Closed-End Fund", "closed-end fund",
                   "Shell Companies", "shell companies", "Semiconductors", "", None, "banks"]
        first = [reference_category(sample) for sample in samples]
        for _ in range(20):
            self.assertEqual([reference_category(sample) for sample in samples], first)

    def test_expected_categories(self) -> None:
        self.assertEqual(reference_category("Exchange Traded Fund"), EXCHANGE_TRADED_FUND)
        self.assertEqual(reference_category("exchange traded fund"), EXCHANGE_TRADED_FUND)
        self.assertEqual(reference_category("REIT - Industrial"), REIT)
        self.assertEqual(reference_category("Closed-End Fund"), CLOSED_END_FUND)
        self.assertEqual(reference_category("Shell Companies"), SHELL_COMPANY)
        self.assertEqual(reference_category("Semiconductors"), LISTED_EQUITY)
        self.assertEqual(reference_category(""), UNCLASSIFIED)
        self.assertEqual(reference_category(None), UNCLASSIFIED)
        self.assertEqual(reference_category("   "), UNCLASSIFIED)

    def test_a_reit_is_not_an_etf(self) -> None:
        self.assertNotEqual(reference_category("REIT - Residential"), EXCHANGE_TRADED_FUND)



class RecoveryAIInputTests(unittest.TestCase):
    def test_null_decision_inputs_retains_original_failure(self):
        with self.assertRaises(TypeError):
            observations_for_row({"fields": {}, "decision_inputs": None}, now=NOW)

    def test_unhashable_unknown_covered_fields_are_ignored_as_before(self):
        row = _row([("market_snapshot", ("price",))], {"price": 10.0})
        row["decision_inputs"][0]["covered_fields"] = [[], {}, "price"]
        result = observations_for_row(row, now=NOW)
        self.assertEqual([(item[0], item[2]) for item in result], [("QUOTE", {"price": 10.0})])

    def test_null_covered_fields_retains_original_failure(self):
        row = _row([("market_snapshot", ("price",))], {"price": 10.0})
        row["decision_inputs"][0]["covered_fields"] = None
        with self.assertRaises(TypeError):
            observations_for_row(row, now=NOW)


if __name__ == "__main__":
    unittest.main()
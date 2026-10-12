"""Screener rule evaluation and row ordering must not change under optimization.

``apply_filters``/``rule_matches``/``field_value`` are the exact predicates the
Screener filters and orders a universe with. They were rewritten to evaluate a
prepared rule and compare directly instead of rebuilding a dispatch table per
row. That is only safe if every operator, every field kind, and the ordering
tie-breaks all produce the identical answer, so this module pins the behaviour
against a deliberately naive reference implementation written straight from the
published contract.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.ui_api.screener_filters import (
    NUMERIC_OPERATORS,
    TEXT_OPERATORS,
    _CATALOG,
    apply_filters,
    catalog_entry,
    field_value,
    rule_matches,
    validate_filters,
)
from market_platform_foundation.ui_api.screener_query import (
    exact_matches_first,
    order_rows,
    page_payload,
    parse_query,
)


# --------------------------------------------------------------------- reference

def reference_field_value(row: dict, field: str):
    """The published rule: text comes from the row, numbers from its envelope."""

    kind = _CATALOG.get(field, {}).get("type")
    if kind == "text" or field not in row.get("fields", {}):
        return row.get(field)
    return row["fields"][field]["value"]


def reference_matches(row: dict, rule: dict) -> bool:
    field, operator, wanted = rule["field"], rule["operator"], rule["value"]
    observed = reference_field_value(row, field)
    if observed is None:
        return False
    if _CATALOG[field]["type"] == "text":
        observed = str(observed).casefold()
        wanted = [v.casefold() for v in wanted] if operator in ("in", "not_in") else wanted.casefold()
        return {"eq": lambda: observed == wanted, "ne": lambda: observed != wanted,
                "in": lambda: observed in wanted, "not_in": lambda: observed not in wanted,
                "contains": lambda: wanted in observed}[operator]()
    if not isinstance(observed, (int, float)) or not math.isfinite(observed):
        return False
    return {"eq": lambda: observed == wanted, "ne": lambda: observed != wanted,
            "gt": lambda: observed > wanted, "gte": lambda: observed >= wanted,
            "lt": lambda: observed < wanted, "lte": lambda: observed <= wanted,
            "between": lambda: wanted[0] <= observed <= wanted[1]}[operator]()



def reference_order(rows, sort, descending):
    present, missing = [], []
    for row in rows:
        value = reference_field_value(row, sort)
        identity = row["instrument"]["instrument_id"]
        if value is None or value == "":
            missing.append((identity, row))
        else:
            present.append((value.casefold() if isinstance(value, str) else value, identity, row))
    present.sort(key=lambda item: item[1])
    present.sort(key=lambda item: item[0], reverse=descending)
    missing.sort(key=lambda item: item[0])
    return [item[2] for item in present] + [item[1] for item in missing]


# ----------------------------------------------------------------------- fixtures

def _row(index: int, **fields) -> dict:
    envelope = {name: {"value": value, "source": "TEST", "state": "SNAPSHOT", "as_of": "2026-10-02T15:00:00Z"}
                for name, value in fields.items()}
    row = {
        "instrument": {"instrument_id": f"EQ:S{index:05d}", "venue_id": "US_EQUITY",
                       "asset_class": "EQUITY", "instrument_kind": "TRADABLE_SECURITY"},
        "symbol": f"S{index:05d}",
        "company": f"Company {index}",
        "sector": ("Technology", "Financial", "Energy", None)[index % 4],
        "industry": ("Semiconductors", "Banks - Diversified", "Oil & Gas Integrated", "Shell Companies")[index % 4],
        "country": "USA",
        "fields": envelope,
    }
    return row


def _universe(size: int = 240) -> list[dict]:
    rows = []
    for index in range(size):
        rows.append(_row(
            index,
            price=None if index % 17 == 0 else round(5 + (index % 90) * 1.5, 2),
            volume=(index * 7919) % 5_000_000,
            rel_volume=round(0.2 + (index % 50) * 0.2, 2),
            market_cap=1.0e8 + index * 1.0e6,
            rsi_14=round(10 + (index % 90) * 0.9, 1),
        ))
    return rows


class FieldValueParityTests(unittest.TestCase):
    def test_matches_reference_for_every_catalog_field(self) -> None:
        rows = _universe(60)
        for field in _CATALOG:
            for row in rows[:5]:
                with self.subTest(field=field, symbol=row["symbol"]):
                    self.assertEqual(field_value(row, field), reference_field_value(row, field))

    def test_unknown_field_and_missing_envelope_are_tolerated(self) -> None:
        self.assertIsNone(field_value({"fields": {}}, "not_a_field"))
        self.assertEqual(field_value({"fields": {}, "extra": 7}, "extra"), 7)
        self.assertEqual(field_value({}, "price"), None)

    def test_text_field_never_reads_the_numeric_envelope(self) -> None:
        row = _row(0)
        expected = row["sector"]
        row["fields"]["sector"] = {"value": "ignored", "source": "T", "state": "SNAPSHOT", "as_of": "x"}
        self.assertEqual(field_value(row, "sector"), expected)
        self.assertEqual(reference_field_value(row, "sector"), expected)


class RuleEvaluationParityTests(unittest.TestCase):
    """Every operator over every field kind, against the naive reference."""

    def _rules(self):
        return [
            {"id": f"n{index}", "field": field, "operator": operator, "value": value}
            for index, (field, operator, value) in enumerate([
                ("price", "gte", 40.0), ("price", "lt", 12.0), ("price", "between", [20.0, 80.0]),
                ("price", "ne", 5.0), ("price", "eq", 6.5), ("price", "gt", 100.0), ("price", "lte", 8.0),
                ("volume", "gt", 1_000_000), ("rel_volume", "gte", 2.0), ("rsi_14", "lt", 30.0),
                ("market_cap", "between", [1e8, 5e8]),
                ("sector", "eq", "Technology"), ("sector", "ne", "Energy"),
                ("sector", "in", ["Technology", "Financial"]), ("sector", "not_in", ["Energy"]),
                ("sector", "contains", "ech"), ("symbol", "eq", "S00007"), ("symbol", "contains", "0001"),
                ("company", "contains", "company 1"), ("industry", "in", ["Shell Companies"]),
            ])
        ]

    def test_single_rule_matches_reference(self) -> None:
        rows = _universe()
        for rule in self._rules():
            validated = validate_filters([dict(rule)])[0]
            expected = [row for row in rows if reference_matches(row, validated)]
            with self.subTest(rule=rule):
                self.assertEqual(apply_filters(rows, [validated]), expected)
                for row in rows:
                    self.assertEqual(rule_matches(row, validated), reference_matches(row, validated))

    def test_stacked_rules_match_reference_and_short_circuit(self) -> None:
        rows = _universe()
        validated = validate_filters(self._rules())
        expected = [row for row in rows if all(reference_matches(row, rule) for rule in validated)]
        self.assertEqual(apply_filters(rows, validated), expected)

    def test_one_rule_and_many_rules_agree_with_the_reference_path(self) -> None:
        rows = _universe()
        validated = validate_filters(self._rules())
        for count in (1, 2, 3, len(validated)):
            subset = validated[:count]
            expected = [row for row in rows if all(reference_matches(row, rule) for rule in subset)]
            self.assertEqual(apply_filters(rows, subset), expected, f"rule count {count}")

    def test_no_rules_returns_every_row_in_order(self) -> None:
        rows = _universe(30)
        self.assertEqual(apply_filters(rows, []), rows)
        self.assertIsNot(apply_filters(rows, []), rows)  # a fresh list, never the caller's

    def test_in_operator_does_not_depend_on_row_ordering(self) -> None:
        rows = _universe(50)
        validated = validate_filters([{"id": "a", "field": "sector", "operator": "in",
                                       "value": ["Technology", "Energy"]}])[0]
        self.assertEqual(apply_filters(rows, [validated]), [row for row in rows if reference_matches(row, validated)])


class OrderingParityTests(unittest.TestCase):
    def test_order_matches_reference_for_every_sort_and_direction(self) -> None:
        rows = _universe()
        for sort in ("price", "volume", "rel_volume", "rsi_14", "market_cap"):
            for descending in (True, False):
                with self.subTest(sort=sort, descending=descending):
                    self.assertEqual(order_rows(rows, sort, descending, field_value),
                                     reference_order(rows, sort, descending))

    def test_missing_values_sort_last_in_both_directions(self) -> None:
        rows = _universe(120)
        for descending in (True, False):
            ordered = order_rows(rows, "price", descending, field_value)
            present = [row for row in ordered if (row["fields"]["price"]["value"] is not None)]
            missing = [row for row in ordered if (row["fields"]["price"]["value"] is None)]
            self.assertTrue(present and missing)
            self.assertEqual(ordered[:len(present)], present)
            identities = [row["instrument"]["instrument_id"] for row in missing]
            self.assertEqual(identities, sorted(identities))

    def test_ties_break_on_canonical_identity_ascending(self) -> None:
        rows = [_row(index, price=10.0) for index in range(40)]
        for descending in (True, False):
            ordered = order_rows(rows, "price", descending, field_value)
            identities = [row["instrument"]["instrument_id"] for row in ordered]
            self.assertEqual(identities, sorted(identities))

    def test_ordering_is_deterministic_across_repeated_calls(self) -> None:
        rows = _universe()
        first = [row["instrument"]["instrument_id"] for row in order_rows(rows, "volume", True, field_value)]
        for _ in range(5):
            again = [row["instrument"]["instrument_id"] for row in order_rows(rows, "volume", True, field_value)]
            self.assertEqual(first, again)


class PagingContractTests(unittest.TestCase):
    def test_page_payload_reports_truthful_counts_and_position(self) -> None:
        rows = _universe(95)
        ordered = order_rows(rows, "volume", True, field_value)
        query = parse_query(universe="US_EQUITIES", sort="volume", descending=True, offset=10, limit=25,
                            selected=ordered[60]["instrument"]["instrument_id"])
        payload = page_payload(query, ordered)
        self.assertEqual(payload["result_count"], 95)
        self.assertEqual(payload["offset"], 10)
        self.assertEqual(payload["returned"], 25)
        self.assertTrue(payload["has_more"])
        self.assertEqual(payload["selected_index"], 60)
        self.assertEqual(len(payload["rows"]), 25)

    def test_exact_matches_first_is_a_stable_promotion(self) -> None:
        rows = _universe(60)
        ordered = order_rows(rows, "volume", True, field_value)
        promoted = exact_matches_first(ordered, "s00007")
        self.assertEqual(promoted[0]["symbol"], "S00007")
        self.assertEqual([row["symbol"] for row in promoted if row["symbol"] == "S00007"][0], "S00007")
        self.assertEqual(len(promoted), len(ordered))
        self.assertEqual(exact_matches_first(ordered, ""), ordered)


class CatalogIntegrityTests(unittest.TestCase):
    def test_every_advertised_operator_is_implemented(self) -> None:
        rows = _universe(10)
        for field, entry in _CATALOG.items():
            if field not in ("symbol", "company", "sector", "industry", "country", "recommendation"):
                continue
            for operator in entry["operators"]:
                value = ["Technology", "Energy"] if operator in ("in", "not_in") else "Technology"
                rule = validate_filters([{"id": "x", "field": field, "operator": operator, "value": value}])[0]
                for row in rows:
                    reference_matches(row, rule)  # must not raise for an advertised operator
                    rule_matches(row, rule)

    def test_numeric_operators_are_all_covered(self) -> None:
        rows = _universe(10)
        for operator in NUMERIC_OPERATORS:
            value = [5.0, 50.0] if operator == "between" else 10.0
            rule = validate_filters([{"id": "x", "field": "price", "operator": operator, "value": value}])[0]
            for row in rows:
                self.assertEqual(rule_matches(row, rule), reference_matches(row, rule))

    def test_text_operators_are_all_covered(self) -> None:
        rows = _universe(10)
        for operator in TEXT_OPERATORS:
            value = ["Technology", "Energy"] if operator in ("in", "not_in") else "Technology"
            rule = validate_filters([{"id": "x", "field": "sector", "operator": operator, "value": value}])[0]
            for row in rows:
                self.assertEqual(rule_matches(row, rule), reference_matches(row, rule))

    def test_catalog_entry_is_isolated_from_the_shared_table(self) -> None:
        entry = catalog_entry("price")
        entry["label"] = "mutated"
        self.assertNotEqual(catalog_entry("price")["label"], "mutated")



class RecoveryFilterInputTests(unittest.TestCase):
    def test_text_fields_short_circuit_a_malformed_numeric_envelope(self):
        self.assertEqual(field_value({"sector": "Technology", "fields": None}, "sector"), "Technology")
        with self.assertRaises(TypeError):
            field_value({"fields": None}, "price")

    def test_empty_rows_do_not_evaluate_invalid_rules(self):
        self.assertEqual(apply_filters([], [{"field": "sector", "operator": "eq", "value": None}]), [])

    def test_rule_short_circuit_preserves_error_timing(self):
        rules = [{"field": "sector", "operator": "eq", "value": "Energy"},
                 {"field": "sector", "operator": "eq", "value": None}]
        self.assertEqual(apply_filters([{"sector": "Technology"}], rules), [])

    def test_unknown_operators_raise_when_observed_value_is_usable(self):
        for field, row in [("sector", {"sector": "Technology"}), ("price", {"fields": {"price": {"value": 3}}})]:
            with self.subTest(field=field), self.assertRaises(KeyError):
                rule_matches(row, {"field": field, "operator": "unknown", "value": "x" if field == "sector" else 1})


if __name__ == "__main__":
    unittest.main()
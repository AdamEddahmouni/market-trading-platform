"""S2 canonical filtering and preset contracts."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.ui_api.screener_filters import (
    apply_filters, builtin_presets, filter_catalog, validate_filters,
)
from market_platform_foundation.finviz.screener import FinvizScreenerRow
from market_platform_foundation.ui_api.screener_projections import ScreenerService
from market_platform_foundation.ui_api.screener_config import ScreenerConfigRepository
from market_platform_foundation.platform.security.route_policy import policy_for_route
from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.local_state.repository import LocalStateRepository


class ScreenerFilterTests(unittest.TestCase):
    def test_catalog_excludes_window_only_quotes(self):
        fields = {item["field"] for item in filter_catalog()}
        self.assertIn("price", fields)
        self.assertIn("sector", fields)
        self.assertNotIn("bid", fields)
        self.assertNotIn("ask", fields)
        self.assertNotIn("spread_pct", fields)

    def test_saved_screen_write_requires_state_write_capability(self):
        self.assertEqual(policy_for_route("POST", "/screener/config").capability, "state.write")

    def test_numeric_between_and_multiple_rules(self):
        rules = validate_filters([
            {"id": "one", "field": "price", "operator": "between", "value": [2, 20]},
            {"id": "two", "field": "rel_volume", "operator": "gt", "value": 2},
        ])
        rows = [
            {"symbol": "A", "company": "A", "sector": "Tech", "fields": {"price": {"value": 10}, "rel_volume": {"value": 3}}},
            {"symbol": "B", "company": "B", "sector": "Tech", "fields": {"price": {"value": 21}, "rel_volume": {"value": 3}}},
            {"symbol": "C", "company": "C", "sector": "Tech", "fields": {"price": {"value": 10}, "rel_volume": {"value": None}}},
        ]
        self.assertEqual([r["symbol"] for r in apply_filters(rows, rules)], ["A"])

    def test_string_rules_and_missing_values(self):
        rules = validate_filters([{"id": "s", "field": "sector", "operator": "contains", "value": "tech"}])
        rows = [
            {"symbol": "A", "company": "A", "sector": "Technology", "fields": {}},
            {"symbol": "B", "company": "B", "sector": None, "fields": {}},
        ]
        self.assertEqual([r["symbol"] for r in apply_filters(rows, rules)], ["A"])

    def test_validation_rejects_unknown_mismatched_and_nonfinite(self):
        for rule in (
            {"id": "x", "field": "unknown", "operator": "gt", "value": 2},
            {"id": "x", "field": "sector", "operator": "gt", "value": 2},
            {"id": "x", "field": "price", "operator": "gt", "value": float("nan")},
            {"id": "x", "field": "price", "operator": "between", "value": [20, 2]},
        ):
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                validate_filters([rule])
        with self.assertRaisesRegex(ValueError, "INVALID_FILTER_LIST"):
            validate_filters({})

    def test_every_discovery_preset_has_explicit_translation_status(self):
        from market_platform_foundation.discovery.screens import SCREEN_LIBRARY
        presets = builtin_presets()
        self.assertEqual({p["id"] for p in presets}, set(SCREEN_LIBRARY))
        self.assertEqual({p["name"] for p in presets}, {
            "Short Squeeze Discovery", "Unusual Volume", "Momentum Ignition", "Gap / Catalyst",
            "Earnings Movers", "Analyst Events", "Insider Activity", "Technical Breakouts",
        })
        self.assertTrue(all(p["status"] in ("SUPPORTED", "UNSUPPORTED") for p in presets))
        for preset in presets:
            if preset["status"] == "SUPPORTED":
                validate_filters(preset["filters"])
            else:
                self.assertTrue(preset["reason"])
        presets[0]["filters"].clear()
        self.assertTrue(builtin_presets()[0]["filters"])

    def test_service_applies_filters_before_sort_and_window(self):
        class Source:
            def fetch_export(self, *, filter_expr, columns):
                return {"success": True, "received_at": "2026-09-25T13:00:00Z", "rows": [
                    FinvizScreenerRow(ticker="AAA", company="Alpha", price=5, volume=100),
                    FinvizScreenerRow(ticker="BBB", company="Beta", price=25, volume=200),
                ]}
        service = ScreenerService(source_factory=Source, runtime_getter=lambda **_: None)
        result = service.read(filters=[{"id": "p", "field": "price", "operator": "between", "value": [2, 20]}])
        self.assertEqual(result["result_count"], 1)
        self.assertEqual(result["rows"][0]["symbol"], "AAA")
        self.assertEqual(result["unfiltered_count"], 2)
        with self.assertRaisesRegex(ValueError, "INVALID_FILTER_LIST"):
            service.read(filters={})

    def test_extended_snapshot_fields_keep_source_and_units(self):
        class Source:
            def fetch_export(self, *, filter_expr, columns):
                return {"success": True, "received_at": "2026-09-25T13:00:00Z", "rows": [
                    FinvizScreenerRow(ticker="AAA", company="Alpha", country="USA", avg_volume=12_000,
                                       shares_outstanding=22_000_000, short_ratio=3.2, eps_ttm=1.5,
                                       pe=8, fwd_pe=7, perf_week=12, recommendation="Buy"),
                ]}
        row = ScreenerService(source_factory=Source, runtime_getter=lambda **_: None).read()["rows"][0]
        self.assertEqual(row["country"], "USA")
        self.assertEqual(row["recommendation"], "Buy")
        self.assertEqual(row["fields"]["shares_outstanding"]["value"], 22_000_000)
        self.assertEqual(row["fields"]["shares_outstanding"]["source"], "FINVIZ_ELITE")

    def test_saved_screen_round_trip_and_builtin_protection(self):
        class Store:
            preferences = {}
            def get_preferences(self):
                return self.preferences
            def set_preference(self, key, value):
                self.preferences[key] = value
        store = Store()
        repository = ScreenerConfigRepository(store)
        screen = repository.save({"name": "My Momentum", "universe": "US_EQUITIES", "filters": [
            {"id": "x", "field": "rel_volume", "operator": "gt", "value": 2}],
            "view": "Overview", "sort": {"field": "volume", "descending": True},
            "columns": {"visible": ["symbol", "price"], "order": ["symbol", "price"],
                        "widths": {"symbol": 180}, "pinned": ["symbol"]}})
        self.assertEqual(ScreenerConfigRepository(store).list_saved()[0]["id"], screen["id"])
        self.assertEqual(repository.get(screen["id"])["filters"][0]["value"], 2)
        renamed = repository.save({**screen, "name": "Renamed"})
        self.assertEqual(renamed["name"], "Renamed")
        self.assertTrue(repository.delete(screen["id"]))
        self.assertEqual(repository.list_saved(), [])
        with self.assertRaises(ValueError):
            repository.delete("SHORT_SQUEEZE_DISCOVERY")

    def test_last_configuration_survives_new_repository(self):
        class Store:
            preferences = {}
            def get_preferences(self):
                return self.preferences
            def set_preference(self, key, value):
                self.preferences[key] = value
        store = Store()
        data = {"name": "Last Used", "universe": "US_EQUITIES", "filters": [], "view": "Technical",
                "sort": {"field": "price", "descending": False},
                "columns": {"visible": ["symbol", "price"], "order": ["symbol", "price"], "widths": {}, "pinned": ["symbol"]}}
        ScreenerConfigRepository(store).save_last(data)
        self.assertEqual(ScreenerConfigRepository(store).get_last()["view"], "Technical")

    def test_personal_screen_survives_sqlite_reopen(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "state.sqlite"
            connection = LocalStateConnection(path)
            repository = ScreenerConfigRepository(LocalStateRepository(connection))
            saved = repository.save({"name": "Durable", "universe": "US_EQUITIES", "filters": [],
                "view": "Overview", "sort": {"field": "volume", "descending": True},
                "columns": {"visible": ["symbol"], "order": ["symbol"], "widths": {}, "pinned": ["symbol"]}})
            connection.close()
            reopened = LocalStateConnection(path)
            self.assertEqual(ScreenerConfigRepository(LocalStateRepository(reopened)).get(saved["id"])["name"], "Durable")
            reopened.close()

    def test_malformed_persisted_screen_fails_closed(self):
        class Store:
            def get_preferences(self):
                return {"screener.s2.screens": {"version": 2, "screens": [{"id": "bad"}]}}
        self.assertEqual(ScreenerConfigRepository(Store()).list_saved(), [])


if __name__ == "__main__":
    unittest.main()

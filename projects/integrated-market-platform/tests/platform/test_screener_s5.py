"""S5 contract, provider boundary, and migration tests without market fixtures in product paths."""

from __future__ import annotations

import sys
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.ui_api.screener_config import (  # noqa: E402
    PREF_KEY, ScreenerConfigRepository, validate_screen,
)
from market_platform_foundation.ui_api.screener_filters import (  # noqa: E402
    filter_catalog, validate_filters,
)
from market_platform_foundation.ui_api.screener_multi import (  # noqa: E402
    MultiUniverseScreener, _futures_session, _quote_from_futures_snapshot, project_etf_catalog, project_futures_catalog,
)
from market_platform_foundation.ui_api.screener_universes import (  # noqa: E402
    FUTURES, US_EQUITIES, US_ETFS, universe_payload, universe_spec,
)

TODAY = date(2026, 9, 27)
AS_OF = "2026-09-27T12:00:00Z"


def future_main(root: str = "ES", month: str = "DEC6") -> dict:
    return {"code": f"US.{root}main", "name": f"{root} ({month})", "stock_type": "FUTURE",
            "delisting": False}


def future_dated(root: str = "ES", year_month: str = "2612", expiry: str = "2026-12-18") -> dict:
    return {"code": f"US.{root}{year_month}", "name": f"{root} {year_month}", "stock_type": "FUTURE",
            "delisting": False, "last_trade_time": expiry + " 16:00:00", "exchange_type": "CME"}


def etf(symbol: str = "SPY", *, stock_type: str = "ETF", delisting: bool = False) -> dict:
    return {"code": f"US.{symbol}", "name": f"{symbol} Fund", "stock_type": stock_type,
            "delisting": delisting, "exchange_type": "NYSE"}


def screen(universe: str, *, field: str = "symbol", view: str = "Overview") -> dict:
    return {"name": "Saved", "universe": universe, "filters": [], "view": view,
            "sort": {"field": field, "descending": False},
            "columns": {"visible": ["symbol"], "order": ["symbol"], "widths": {}, "pinned": ["symbol"]}}


class Store:
    def __init__(self) -> None:
        self.values: dict = {}

    def get_preferences(self) -> dict:
        return self.values

    def set_preference(self, key: str, value: object) -> None:
        self.values[key] = value


class UniverseContractTests(unittest.TestCase):
    def test_admitted_universes_with_typed_capabilities(self) -> None:
        payload = universe_payload()
        # S9 added the owner-authorized Bonds universe and S10 Crypto; nothing else may join without authorization.
        self.assertEqual([item["id"] for item in payload], [US_EQUITIES, FUTURES, US_ETFS, "BONDS", "CRYPTO"])
        self.assertEqual(universe_spec(FUTURES).asset_class, "FUTURE")
        self.assertEqual(universe_spec(US_ETFS).asset_class, "ETF_FUND")
        self.assertEqual(universe_spec(FUTURES).panels, ())
        self.assertNotIn("Fundamentals", universe_spec(FUTURES).views)
        self.assertNotIn("Fund", universe_spec(US_ETFS).views)
        self.assertEqual(list(universe_spec(FUTURES).views), ["Overview", "Contract", "Performance", "Custom"])
        self.assertEqual(list(universe_spec(US_ETFS).views), ["Overview", "Performance", "Custom"])
        self.assertEqual(payload[0]["view_order"][:2], ["Overview", "Performance"])
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_UNIVERSE"):
            universe_spec("OPTIONS")

    def test_fields_and_screens_cannot_cross_universes(self) -> None:
        self.assertIn("dte", {item["field"] for item in filter_catalog(FUTURES)})
        self.assertNotIn("short_float_pct", {item["field"] for item in filter_catalog(FUTURES)})
        # S6: ETF market fields filter only through the complete ETF snapshot; Futures
        # market fields stay unfilterable while quote entitlement is absent.
        self.assertNotIn("price", {item["field"] for item in filter_catalog(FUTURES)})
        self.assertNotIn("rel_volume", {item["field"] for item in filter_catalog(US_ETFS)})
        with self.assertRaisesRegex(ValueError, "FILTER_UNIVERSE_MISMATCH"):
            validate_filters([{"id": "x", "field": "short_float_pct", "operator": "gt", "value": 5}], universe=FUTURES)
        with self.assertRaisesRegex(ValueError, "INVALID_SCREEN_VIEW"):
            validate_screen(screen(FUTURES, view="Fundamentals"))
        incompatible = screen(US_ETFS)
        incompatible["columns"]["visible"].append("float_shares")
        incompatible["columns"]["order"].append("float_shares")
        with self.assertRaisesRegex(ValueError, "INVALID_SCREEN_COLUMN"):
            validate_screen(incompatible)

    def test_saved_screen_migration_and_universe_persistence(self) -> None:
        store = Store()
        repo = ScreenerConfigRepository(store)
        old = screen(US_EQUITIES)
        old.pop("universe")
        old.update(id="user-old", version=1)
        store.values[PREF_KEY] = {"version": 1, "screens": [old]}
        self.assertEqual(repo.list_saved()[0]["universe"], US_EQUITIES)
        self.assertEqual(repo.list_saved()[0]["version"], 2)
        future = repo.save(screen(FUTURES, field="root"))
        etf_saved = repo.save(screen(US_ETFS))
        self.assertEqual({item["universe"] for item in repo.list_saved()}, {US_EQUITIES, FUTURES, US_ETFS})
        self.assertEqual(repo.get(future["id"])["sort"]["field"], "root")
        self.assertEqual(repo.get(etf_saved["id"])["universe"], US_ETFS)
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_UNIVERSE"):
            validate_screen(screen("OPTIONS"))


class CatalogProjectionTests(unittest.TestCase):
    def test_current_dated_lead_contract_and_expired_rejection(self) -> None:
        rows = project_futures_catalog([
            future_main(), future_dated(), future_main("NQ", "SEP6"),
            future_dated("NQ", "2609", "2026-09-18"), future_main(),
        ], today=TODAY, as_of=AS_OF)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["root"], row["symbol"], row["provider_symbol"]), ("ES", "ESZ26", "US.ES2612"))
        self.assertEqual(row["instrument"]["asset_class"], "FUTURE")
        self.assertEqual(row["instrument"]["instrument_kind"], "FUTURE_CONTRACT")
        self.assertNotEqual(row["instrument"]["instrument_id"], "ES")
        self.assertEqual(row["fields"]["dte"]["value"], 82)
        self.assertEqual(row["fields"]["price"]["value"], None)
        self.assertEqual(row["fields"]["price"]["state"], "UNAVAILABLE")

    def test_unresolved_and_delisted_contracts_are_excluded(self) -> None:
        bad = future_dated()
        bad["delisting"] = True
        self.assertEqual(project_futures_catalog([future_main(), bad], today=TODAY, as_of=AS_OF), [])
        self.assertEqual(project_futures_catalog([future_main(month="JUNK6"), future_dated()], today=TODAY, as_of=AS_OF), [])

    def test_etf_classification_and_duplicate_identity(self) -> None:
        rows = project_etf_catalog([etf(), etf(), etf("QQQ"), etf("AAPL", stock_type="STOCK"),
                                    etf("OLD", delisting=True)], as_of=AS_OF)
        self.assertEqual([row["symbol"] for row in rows], ["QQQ", "SPY"])
        self.assertTrue(all(row["instrument"]["asset_class"] == "ETF_FUND" for row in rows))
        self.assertNotEqual(rows[1]["instrument"]["instrument_id"], "SPY")
        self.assertEqual(rows[1]["fields"]["price"]["state"], "UNAVAILABLE")
        missing = project_etf_catalog([{**etf("NOVENUE"), "exchange_type": "N/A"}], as_of=AS_OF)[0]
        self.assertIsNone(missing["exchange"])


class LiveBoundaryTests(unittest.TestCase):
    def test_quote_requires_fresh_clock_and_explicit_mode(self) -> None:
        event = datetime(2026, 9, 27, 10, 0, tzinfo=ZoneInfo("America/New_York"))
        payload = {"update_time": "2026-09-27 10:00:00", "last_price": 6000, "prev_close_price": 5900,
                   "volume": 25}
        now = event.timestamp() + 3
        live = _quote_from_futures_snapshot({**payload, "data_mode": "REALTIME"}, now)
        delayed = _quote_from_futures_snapshot({**payload, "data_mode": "DELAYED"}, now)
        unknown = _quote_from_futures_snapshot(payload, now)
        stale = _quote_from_futures_snapshot({**payload, "data_mode": "REALTIME"}, now + 60)
        self.assertEqual((live["state"], delayed["state"], unknown["state"], stale["state"]),
                         ("LIVE", "DELAYED", "UNAVAILABLE", "STALE"))
        self.assertEqual(delayed["fields"]["price"]["state"], "DELAYED")
        self.assertIsNone(unknown["fields"]["price"]["value"])
        self.assertIsNone(stale["fields"]["price"]["value"])
        self.assertEqual(live["fields"]["price"]["value"], 6000)

    def test_provider_refusal_never_substitutes_a_price(self) -> None:
        class Transport:
            def fetch_future_contracts(self, codes: list[str]) -> dict:
                return {"rows": [future_main(), future_dated()], "reason_code": None}

            def fetch_future_quotes(self, codes: list[str]) -> dict:
                return {"rows": None, "reason_code": "MOOMOO_QUOTE_NOT_ENTITLED"}

            def fetch_market_states(self, codes: list[str]) -> dict:
                return {"rows": [{"code": codes[0], "market_state": "FUTURE_CLOSE"}], "reason_code": None}

        service = MultiUniverseScreener(transport_getter=Transport, today=lambda: TODAY,
                                        now=lambda: AS_OF, clock=lambda: 1.0)
        rows = service.read(universe=FUTURES)["rows"]
        with patch("market_platform_foundation.ui_api.screener_multi.screener_service") as equity:
            equity.return_value.release.return_value = {"released": True}
            window = service.window("client", [rows[0]["instrument"]["instrument_id"]], universe=FUTURES)
        quote = next(iter(window["quotes"].values()))
        self.assertEqual(quote["state"], "UNAVAILABLE")
        self.assertEqual(quote["reason"], "MOOMOO_QUOTE_NOT_ENTITLED")
        self.assertEqual(quote["fields"], {})
        self.assertEqual((quote["session_state"], window["market_session"]), ("CLOSED", "CLOSED"))

    def test_futures_market_state_fails_closed(self) -> None:
        self.assertEqual(_futures_session("FUTURE_OPEN"), "TRADING")
        self.assertEqual(_futures_session("FUTURE_REST"), "MAINTENANCE")
        self.assertEqual(_futures_session("FUTURE_CLOSE"), "CLOSED")
        self.assertEqual(_futures_session("UNKNOWN"), "UNAVAILABLE")

    def test_etf_window_maps_canonical_identity_to_provider_symbol(self) -> None:
        class Transport:
            def fetch_etf_catalog(self) -> dict:
                return {"rows": [etf()], "reason_code": None}

        service = MultiUniverseScreener(transport_getter=Transport, today=lambda: TODAY,
                                        now=lambda: AS_OF, clock=lambda: 1.0)
        row = service.read(universe=US_ETFS)["rows"][0]
        with patch("market_platform_foundation.ui_api.screener_multi.screener_service") as equity:
            equity.return_value.window.return_value = {"quotes": {}, "active": 0, "cap": 32}
            service.window("client", [row["instrument"]["instrument_id"]], universe=US_ETFS)
            self.assertEqual(equity.return_value.window.call_args.kwargs["known"],
                             {row["instrument"]["instrument_id"]: "SPY"})

    def test_catalog_failure_has_no_fixture_fallback(self) -> None:
        class Broken:
            def fetch_etf_catalog(self) -> dict:
                raise ConnectionError("offline")

        service = MultiUniverseScreener(transport_getter=Broken, today=lambda: TODAY,
                                        now=lambda: AS_OF, clock=lambda: 1.0)
        result = service.read(universe=US_ETFS)
        self.assertEqual((result["result_count"], result["source_error"]), (0, "PROVIDER_UNAVAILABLE"))
        self.assertEqual(result["rows"], [])


    def test_futures_preview_is_contract_scoped_without_equity_fields_or_bars(self) -> None:
        from market_platform_foundation.ui_api.screener_preview import ScreenerPreviewService

        class Transport:
            def fetch_future_contracts(self, codes: list[str]) -> dict:
                return {"rows": [future_main(), future_dated()], "reason_code": None}

            def fetch_future_quotes(self, codes: list[str]) -> dict:
                return {"rows": None, "reason_code": "MOOMOO_QUOTE_NOT_ENTITLED"}

            def fetch_market_states(self, codes: list[str]) -> dict:
                return {"rows": [], "reason_code": None}

        multi = MultiUniverseScreener(transport_getter=Transport, today=lambda: TODAY,
                                      now=lambda: AS_OF, clock=lambda: 1.0)
        ident = multi.read(universe=FUTURES)["rows"][0]["instrument"]["instrument_id"]
        with patch("market_platform_foundation.ui_api.screener_multi.multi_screener_service", return_value=multi),                 patch("market_platform_foundation.ui_api.screener_multi.screener_service"):
            preview = ScreenerPreviewService(screener=object(), bars=object(), futures=object()).read(
                ident, universe=FUTURES)
        self.assertEqual((preview["instrument"]["symbol"], preview["instrument"]["root"]), ("ESZ26", "ES"))
        self.assertEqual(preview["bars"]["state"], "UNAVAILABLE")
        self.assertEqual(preview["levels"]["state"], "UNAVAILABLE")
        self.assertEqual(preview["quote"]["reason"], "MOOMOO_QUOTE_NOT_ENTITLED")
        fields = {item["field"]: item for item in preview["key_data"]}
        self.assertTrue({"market_cap", "float_shares", "short_float_pct", "pe"}.isdisjoint(fields))
        self.assertEqual(fields["dte"]["value"], 82)
        self.assertEqual((fields["price"]["value"], fields["price"]["state"]), (None, "UNAVAILABLE"))
        self.assertEqual(preview["futures"]["items"], [])

    def test_catalog_admitted_etf_panels_do_not_require_the_equity_snapshot(self) -> None:
        from market_platform_foundation.ui_api.screener_specialist import ScreenerSpecialistService

        service = ScreenerSpecialistService(runtime_getter=lambda: None, known_instrument=lambda _i: False,
                                            schedule_expiry=False)
        with self.assertRaisesRegex(ValueError, "UNKNOWN_INSTRUMENT"):
            service.demand("etf-client", "SPY", ["order_flow"])
        result = service.demand("etf-client", "SPY", ["order_flow"], admitted=True)
        self.assertEqual(result["instrument_id"], "SPY")
        self.assertEqual({item["reason"] for item in result["capabilities"]}, {"LIVE_RUNTIME_UNAVAILABLE"})

if __name__ == "__main__":
    unittest.main()

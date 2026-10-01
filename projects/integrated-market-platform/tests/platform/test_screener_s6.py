"""S6 canonical query, server paging, and market-snapshot truth (no market fixtures in product paths)."""

from __future__ import annotations

import sys
import unittest
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.ui_api.screener_config import validate_screen  # noqa: E402
from market_platform_foundation.ui_api.screener_filters import filter_catalog  # noqa: E402
from market_platform_foundation.ui_api.screener_multi import MultiUniverseScreener  # noqa: E402
from market_platform_foundation.ui_api.screener_projections import ScreenerService  # noqa: E402
from market_platform_foundation.ui_api.screener_query import (  # noqa: E402
    CATALOG, LIVE_WINDOW, MAX_PAGE_LIMIT, SNAPSHOT, field_capabilities, order_rows, parse_query,
)
from market_platform_foundation.ui_api.screener_snapshot import (  # noqa: E402
    SNAPSHOT_RETAINED, SNAPSHOT_TTL_SECONDS, snapshot_values,
)
from market_platform_foundation.ui_api.screener_admission import ClassificationReference  # noqa: E402
from market_platform_foundation.ui_api.screener_universes import FUTURES, US_EQUITIES, US_ETFS  # noqa: E402

TODAY = date(2026, 9, 27)
AS_OF = "2026-09-27T12:00:00Z"
REFERENCE_AS_OF = "2026-09-27T11:58:00Z"
WALL = datetime(2026, 9, 27, 16, 0, tzinfo=UTC)
FRESH = "2026-09-25 16:00:00"


def etf(symbol: str, exchange: str = "US_NYSE") -> dict:
    return {"code": f"US.{symbol}", "name": f"{symbol} Fund", "stock_type": "ETF", "delisting": False,
            "exchange_type": exchange}


def quote(code: str, price: float | None, *, volume: float = 100, updated: str = FRESH) -> dict:
    return {"code": code, "update_time": updated, "last_price": price, "prev_close_price": 50,
            "volume": volume, "bid_price": price, "ask_price": None if price is None else price + 0.02}


class Clock:
    def __init__(self) -> None:
        self.value = 1.0

    def __call__(self) -> float:
        return self.value


class EtfTransport:
    """OpenD-shaped: catalog plus bounded snapshot batches with named per-code refusals."""

    def __init__(self, symbols: list[str], prices: dict[str, float | None] | None = None, *,
                 refused: tuple[str, ...] = (), fail_batch: int | None = None, drop: tuple[str, ...] = ()) -> None:
        self.symbols = symbols
        self.prices = prices or {}
        self.refused = set(f"US.{code}" for code in refused)
        self.fail_batch = fail_batch
        self.drop = set(f"US.{code}" for code in drop)
        self.calls: list[list[str]] = []

    def fetch_etf_catalog(self) -> dict:
        return {"rows": [etf(symbol) for symbol in self.symbols], "reason_code": None}

    def fetch_market_snapshot(self, codes: list[str]) -> dict:
        self.calls.append(list(codes))
        if self.fail_batch is not None and len(self.calls) == self.fail_batch:
            return {"rows": None, "reason_code": "MOOMOO_PROTOCOL_ERROR"}
        blocked = [code for code in codes if code in self.refused]
        if blocked:
            return {"rows": None, "reason_code": "MOOMOO_QUOTE_NOT_ENTITLED", "refused_codes": blocked[:1]}
        return {"rows": [quote(code, self.prices.get(code[3:], 10.0)) for code in codes if code not in self.drop],
                "reason_code": None}


def etf_reference(symbols) -> ClassificationReference:
    """S13: Finviz evidence that each listing is an exchange-traded fund (ETF admission needs it)."""

    return ClassificationReference.build(
        [SimpleNamespace(ticker=symbol, sector="Financial", industry="Exchange Traded Fund", country="USA")
         for symbol in symbols], as_of=REFERENCE_AS_OF)


def service_for(transport: object, clock: Clock | None = None) -> MultiUniverseScreener:
    def reference() -> ClassificationReference:
        catalog = transport.fetch_etf_catalog() if hasattr(transport, "fetch_etf_catalog") else {"rows": []}
        return etf_reference(row["code"][3:] for row in catalog["rows"] or [])

    return MultiUniverseScreener(transport_getter=lambda: transport, reference_getter=reference,
                                 today=lambda: TODAY, now=lambda: AS_OF,
                                 clock=clock or Clock(), wall=lambda: WALL)


def ids(result: dict) -> list[str]:
    return [row["symbol"] for row in result["rows"]]


class QueryContractTests(unittest.TestCase):
    def test_query_validation(self) -> None:
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_UNIVERSE"):
            parse_query(universe="OPTIONS")
        with self.assertRaisesRegex(ValueError, "UNKNOWN_FILTER_FIELD"):
            parse_query(universe=US_ETFS, filters=[{"id": "a", "field": "aum", "operator": "gt", "value": 1}])
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_FILTER_OPERATOR"):
            parse_query(universe=US_ETFS, filters=[{"id": "a", "field": "price", "operator": "contains", "value": 1}])
        for offset, limit in ((-1, 10), (0, 0), (0, MAX_PAGE_LIMIT + 1), (0, True)):
            with self.assertRaisesRegex(ValueError, "INVALID_RESULT_WINDOW"):
                parse_query(universe=US_ETFS, offset=offset, limit=limit)
        self.assertEqual(parse_query(universe=US_ETFS, limit=MAX_PAGE_LIMIT).limit, MAX_PAGE_LIMIT)
        with self.assertRaisesRegex(ValueError, "INVALID_SEARCH"):
            parse_query(universe=US_ETFS, search="x" * 81)

    def test_live_window_fields_neither_sort_nor_filter_a_universe(self) -> None:
        self.assertEqual(parse_query(universe=US_EQUITIES, sort="bid").sort, "bid")
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_SORT"):
            parse_query(universe=FUTURES, sort="price")
        with self.assertRaisesRegex(ValueError, "FILTER_UNIVERSE_MISMATCH"):
            parse_query(universe=FUTURES, filters=[{"id": "a", "field": "price", "operator": "gt", "value": 1}])
        self.assertEqual(len(parse_query(universe=US_EQUITIES, filters=[
            {"id": "a", "field": "spread_pct", "operator": "lt", "value": 1}]).filters), 1)
        with self.assertRaisesRegex(ValueError, "FILTER_UNIVERSE_MISMATCH"):
            parse_query(universe=US_ETFS, filters=[{"id": "a", "field": "short_float_pct", "operator": "gt", "value": 1}])

    def test_field_capabilities_drive_filter_and_sort_availability(self) -> None:
        etfs, futures, equities = (field_capabilities(universe) for universe in (US_ETFS, FUTURES, US_EQUITIES))
        self.assertEqual(etfs["price"], {"execution": SNAPSHOT, "sortable": True, "filterable": True})
        self.assertEqual(etfs["symbol"]["execution"], CATALOG)
        self.assertNotIn("rel_volume", etfs)
        self.assertEqual(futures["price"], {"execution": LIVE_WINDOW, "sortable": False, "filterable": False})
        self.assertEqual(futures["dte"], {"execution": CATALOG, "sortable": True, "filterable": True})
        self.assertEqual(equities["bid"], {"execution": SNAPSHOT, "sortable": True, "filterable": True})
        self.assertFalse(equities["sector"]["sortable"])
        for universe in (US_EQUITIES, FUTURES, US_ETFS):
            for entry in filter_catalog(universe):
                self.assertIn(field_capabilities(universe)[entry["field"]]["execution"], (CATALOG, SNAPSHOT))

    def test_one_ordering_missing_last_and_identity_ties(self) -> None:
        def row(identity: str, value: float | None) -> dict:
            return {"instrument": {"instrument_id": identity}, "fields": {"price": {"value": value}}}
        rows = [row("d", None), row("c", 2), row("b", 1), row("a", 2), row("e", None)]
        value = lambda item, _field: item["fields"]["price"]["value"]  # noqa: E731
        order = lambda descending: [r["instrument"]["instrument_id"] for r in order_rows(rows, "price", descending, value)]  # noqa: E731
        self.assertEqual(order(False), ["b", "a", "c", "d", "e"])
        self.assertEqual(order(True), ["a", "c", "b", "d", "e"])


class CatalogPagingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.symbols = [f"E{index:04d}" for index in range(0, 1050)]
        self.transport = EtfTransport(self.symbols)
        self.service = service_for(self.transport)

    def test_bounded_first_page_and_truthful_counts(self) -> None:
        first = self.service.read(universe=US_ETFS)
        self.assertEqual((first["result_count"], first["returned"], first["limit"]), (1050, 200, 200))
        self.assertTrue(first["has_more"])
        self.assertEqual(first["unfiltered_count"], 1050)
        self.assertEqual(first["evaluation"], "CATALOG")
        self.assertEqual(self.transport.calls, [], "a catalog page never snapshots")

    def test_adjacent_pages_have_no_duplicates_or_gaps(self) -> None:
        first = self.service.read(universe=US_ETFS, sort="symbol", descending=True, limit=300)
        seen = list(ids(first))
        offset = 300
        while True:
            page = self.service.read(universe=US_ETFS, sort="symbol", descending=True, offset=offset, limit=300,
                                     result_set=first["result_set_id"])
            if not page["rows"]:
                break
            seen += ids(page)
            offset += page["returned"]
        self.assertEqual(seen, sorted(self.symbols, reverse=True))
        empty = self.service.read(universe=US_ETFS, offset=5000, result_set=first["result_set_id"])
        self.assertEqual((empty["rows"], empty["result_count"], empty["has_more"]), ([], 1050, False))

    def test_server_search_filter_and_selection_position(self) -> None:
        found = self.service.read(universe=US_ETFS, search="e104", descending=False, selected="missing")
        self.assertEqual(ids(found), [f"E104{digit}" for digit in range(10)])
        self.assertIsNone(found["selected_index"])
        target = self.service.read(universe=US_ETFS, descending=False, limit=1)["rows"][0]["instrument"]["instrument_id"]
        placed = self.service.read(universe=US_ETFS, sort="symbol", descending=True, limit=10, selected=target)
        self.assertEqual(placed["selected_index"], 1049)
        by_exchange = self.service.read(universe=US_ETFS, filters=[
            {"id": "x", "field": "exchange", "operator": "in", "value": ["US_NYSE"]}])
        self.assertEqual(by_exchange["result_count"], 1050)

    def test_changed_catalog_rejects_a_stale_page_token(self) -> None:
        first = self.service.read(universe=US_ETFS)
        with self.assertRaisesRegex(ValueError, "RESULT_SET_CHANGED"):
            self.service.read(universe=US_ETFS, offset=200, result_set="2020-01-01T00:00:00Z|")
        with self.assertRaisesRegex(ValueError, "RESULT_SET_CHANGED"):
            # A catalog token cannot continue a snapshot-ordered query.
            self.service.read(universe=US_ETFS, sort="price", offset=200, result_set=first["result_set_id"])


class EtfSnapshotTruthTests(unittest.TestCase):
    def test_price_filter_requires_a_complete_snapshot_not_the_visible_window(self) -> None:
        symbols = [f"E{index:04d}" for index in range(900)]
        # The first 400 rows (more than any 32-row window) would satisfy Price > 100.
        prices = {symbol: 150.0 for symbol in symbols[:400]}
        transport = EtfTransport(symbols, prices, fail_batch=2)
        service = service_for(transport)
        result = service.read(universe=US_ETFS, filters=[{"id": "p", "field": "price", "operator": "gt", "value": 100}])
        self.assertEqual((result["rows"], result["result_count"]), ([], 0))
        self.assertEqual(result["source_error"], "MOOMOO_PROTOCOL_ERROR")
        self.assertIsNone(result["result_set_id"])
        self.assertEqual(result["provider_health"][-1]["state"], "UNAVAILABLE")

    def test_no_snapshot_source_is_unavailable_even_with_window_quotes(self) -> None:
        class CatalogOnly:
            def fetch_etf_catalog(self) -> dict:
                return {"rows": [etf(f"E{index:04d}") for index in range(64)], "reason_code": None}

        service = service_for(CatalogOnly())
        with patch("market_platform_foundation.ui_api.screener_multi.screener_service") as equity:
            equity.return_value.window.return_value = {"quotes": {}, "active": 32, "cap": 32}
            result = service.read(universe=US_ETFS, sort="price")
        self.assertEqual((result["rows"], result["source_error"]), ([], "MARKET_SNAPSHOT_UNAVAILABLE"))
        self.assertEqual(ids(service.read(universe=US_ETFS, descending=False))[:1], ["E0000"], "catalog still usable")

    def test_named_refusals_complete_the_snapshot_and_stay_unpriced(self) -> None:
        symbols = ["AAA", "BBB", "OTCX", "CCC"]
        transport = EtfTransport(symbols, {"AAA": 120.0, "BBB": 90.0, "CCC": 101.0}, refused=("OTCX",))
        service = service_for(transport)
        result = service.read(universe=US_ETFS, sort="price", descending=True)
        self.assertEqual(ids(result), ["AAA", "CCC", "BBB", "OTCX"])
        summary = result["snapshot"]
        self.assertEqual((summary["complete"], summary["total"], summary["returned"], summary["refused"]),
                         (True, 4, 3, 1))
        self.assertEqual(result["rows"][-1]["fields"]["price"]["state"], "UNAVAILABLE")
        self.assertEqual(result["rows"][0]["fields"]["price"]["source"], "MOOMOO_OPEND_SNAPSHOT")
        above = service.read(universe=US_ETFS, descending=False,
                             filters=[{"id": "p", "field": "price", "operator": "gt", "value": 100}])
        self.assertEqual(ids(above), ["AAA", "CCC"])
        self.assertEqual(len(transport.calls), 2, "one refusal retry, then the snapshot is reused")
        # The learned refusal is not re-requested on the next build.
        service.read(universe=US_ETFS, sort="price", force_refresh=True)
        self.assertEqual(len(transport.calls), 2, "explicit refresh is rate-bounded")

    def test_unaccounted_rows_make_the_snapshot_incomplete(self) -> None:
        transport = EtfTransport(["AAA", "BBB"], drop=("BBB",))
        result = service_for(transport).read(universe=US_ETFS, sort="volume")
        self.assertEqual((result["rows"], result["source_error"]), ([], "MARKET_SNAPSHOT_INCOMPLETE"))

    def test_snapshot_pages_are_pinned_while_new_chains_refresh(self) -> None:
        clock = Clock()
        prices = {"AAA": 3.0, "BBB": 2.0, "CCC": 1.0}
        transport = EtfTransport(list(prices), prices)
        service = service_for(transport, clock)
        first = service.read(universe=US_ETFS, sort="price", descending=True, limit=2)
        self.assertEqual(ids(first), ["AAA", "BBB"])
        transport.prices = {"AAA": 1.0, "BBB": 2.0, "CCC": 3.0}
        clock.value += SNAPSHOT_TTL_SECONDS + 1
        second = service.read(universe=US_ETFS, sort="price", descending=True, offset=2, limit=2,
                              result_set=first["result_set_id"])
        self.assertEqual(ids(second), ["CCC"], "the pinned chain finishes on its own snapshot")
        fresh = service.read(universe=US_ETFS, sort="price", descending=True, limit=2)
        self.assertEqual(ids(fresh), ["CCC", "BBB"])
        self.assertNotEqual(fresh["snapshot"]["id"], first["snapshot"]["id"])
        for _ in range(SNAPSHOT_RETAINED):
            clock.value += SNAPSHOT_TTL_SECONDS + 1
            service.read(universe=US_ETFS, sort="price")
        with self.assertRaisesRegex(ValueError, "RESULT_SET_CHANGED"):
            service.read(universe=US_ETFS, sort="price", descending=True, offset=2, limit=2,
                         result_set=first["result_set_id"])

    def test_snapshot_values_and_staleness(self) -> None:
        values, as_of = snapshot_values(quote("US.AAA", 101.0), WALL)
        self.assertEqual(values["price"], 101.0)
        self.assertAlmostEqual(values["change_pct"], 102.0)
        self.assertAlmostEqual(values["spread_pct"], 0.02 / 101.01 * 100)
        self.assertEqual(as_of, "2026-09-25T20:00:00Z")
        stale, stale_as_of = snapshot_values(quote("US.AAA", 101.0, updated="2021-10-15 16:00:00"), WALL)
        self.assertEqual((set(stale.values()), stale_as_of), ({None}, None))
        unpriced, _ = snapshot_values(quote("US.AAA", 0.0), WALL)
        self.assertIsNone(unpriced["price"])

    def test_why_matched_uses_the_evaluated_snapshot_value(self) -> None:
        from market_platform_foundation.ui_api.screener_preview import explain_matches

        transport = EtfTransport(["AAA"], {"AAA": 120.0})
        service = service_for(transport)
        result = service.read(universe=US_ETFS, filters=[{"id": "p", "field": "price", "operator": "gt", "value": 100}])
        identity = result["rows"][0]["instrument"]["instrument_id"]
        transport.prices = {"AAA": 80.0}
        row, _ = service.row_for(identity, universe=US_ETFS, snapshot_id=result["snapshot"]["id"])
        why = explain_matches(row, [{"id": "p", "field": "price", "operator": "gt", "value": 100}], universe=US_ETFS)
        self.assertEqual(why["state"], "MATCHED")
        self.assertIn("market snapshot", why["items"][0]["text"])
        plain, _ = service.row_for(identity, universe=US_ETFS)
        self.assertIsNone(plain["fields"]["price"]["value"], "catalog rows carry no market value")


class ResponseAuditTests(unittest.TestCase):
    def test_paged_and_snapshot_responses_pass_the_api_secret_audit(self) -> None:
        from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload

        service = service_for(EtfTransport(["AAA", "BBB"], {"AAA": 120.0}))
        for payload in (service.read(universe=US_ETFS), service.read(universe=US_ETFS, sort="price", selected="x")):
            self.assertIsNotNone(payload["result_set_id"])
            assert_no_secrets_in_payload(payload)


class FuturesAndEquityTests(unittest.TestCase):
    def test_futures_metadata_query_filters_sorts_and_pages(self) -> None:
        class Transport:
            def fetch_future_contracts(self, codes: list[str]) -> dict:
                rows = []
                for root, ym, month, expiry in (("ES", "2612", "DEC6", "2026-12-18"), ("CL", "2611", "NOV6", "2026-10-20"),
                                                ("GC", "2612", "DEC6", "2026-12-29"), ("NQ", "2612", "DEC6", "2026-12-18")):
                    rows += [{"code": f"US.{root}main", "name": f"{root} ({month})", "stock_type": "FUTURE",
                              "delisting": False},
                             {"code": f"US.{root}{ym}", "name": f"{root} {ym}", "stock_type": "FUTURE",
                              "delisting": False, "last_trade_time": expiry + " 16:00:00", "exchange_type": "CME"}]
                return {"rows": rows, "reason_code": None}

        service = MultiUniverseScreener(transport_getter=Transport, today=lambda: TODAY, now=lambda: AS_OF,
                                        clock=Clock(), wall=lambda: WALL)
        by_dte = service.read(universe=FUTURES, sort="dte", descending=False, limit=2)
        self.assertEqual((ids(by_dte), by_dte["result_count"]), (["CLX26", "ESZ26"], 4))
        tail = service.read(universe=FUTURES, sort="dte", descending=False, offset=2, limit=2,
                            result_set=by_dte["result_set_id"])
        self.assertEqual(ids(tail), ["NQZ26", "GCZ26"], "equal DTE ties break by canonical id")
        near = service.read(universe=FUTURES, filters=[{"id": "d", "field": "dte", "operator": "lt", "value": 90}])
        self.assertEqual(sorted(ids(near)), ["CLX26", "ESZ26", "NQZ26"])
        rooted = service.read(universe=FUTURES, search="gc")
        self.assertEqual(ids(rooted), ["GCZ26"])
        self.assertEqual(service.read(universe=FUTURES, sort="expiry", descending=True)["rows"][0]["root"], "GC")

    def test_equity_pages_pin_the_finviz_snapshot(self) -> None:
        from market_platform_foundation.finviz.screener import FinvizScreenerRow

        class Source:
            version = 0

            def fetch_export(self, **_kwargs: object) -> dict:
                Source.version += 1
                return {"success": True, "error": None, "received_at": f"2026-09-27T12:00:0{Source.version}Z",
                        "rows": [FinvizScreenerRow(ticker=f"T{i:04d}", company=f"Company {i}", price=float(i),
                                                   volume=i * 100) for i in range(250)]}

        clock = Clock()
        service = ScreenerService(source_factory=Source, runtime_getter=lambda **_: None, monotonic=clock)
        first = service.read()
        self.assertEqual((first["returned"], first["result_count"], first["has_more"]), (200, 250, True))
        self.assertEqual(first["rows"][0]["symbol"], "T0249")
        clock.value += 10_000
        service.read()  # the next chain reads a new Finviz snapshot
        tail = service.read(offset=200, result_set=first["result_set_id"])
        self.assertEqual((tail["returned"], tail["rows"][0]["symbol"]), (50, "T0049"))
        clock.value += 10_000
        service.read()
        with self.assertRaisesRegex(ValueError, "RESULT_SET_CHANGED"):
            service.read(offset=200, result_set=first["result_set_id"])


class SavedScreenCompatibilityTests(unittest.TestCase):
    def test_s5_screens_restore_as_configuration_only(self) -> None:
        columns = {"visible": ["symbol", "price"], "order": ["symbol", "price"], "widths": {}, "pinned": ["symbol"]}
        etf_screen = validate_screen({"name": "ETF", "universe": US_ETFS, "view": "Overview", "filters": [],
                                      "sort": {"field": "price", "descending": True}, "columns": columns})
        self.assertEqual(set(etf_screen), {"id", "version", "name", "universe", "filters", "view", "sort", "columns"})
        futures_screen = validate_screen({"name": "Fut", "universe": FUTURES, "view": "Overview",
                                          "filters": [{"id": "d", "field": "dte", "operator": "lt", "value": 30}],
                                          "sort": {"field": "dte", "descending": False},
                                          "columns": {**columns, "visible": ["symbol"], "order": ["symbol"]}})
        self.assertEqual(futures_screen["version"], 2)
        legacy = validate_screen({"version": 1, "name": "Old", "view": "Overview", "filters": [],
                                  "sort": {"field": "volume", "descending": True}, "columns": columns})
        self.assertEqual(legacy["universe"], US_EQUITIES)
        window_sorted = validate_screen({"name": "Fut price", "universe": FUTURES, "view": "Overview", "filters": [],
                                         "sort": {"field": "price", "descending": True},
                                         "columns": {**columns, "visible": ["symbol"], "order": ["symbol"]}})
        self.assertEqual(window_sorted["sort"]["field"], "price",
                         "an S5 window-only sort stays saved configuration; the UI orders by the universe default")


class TransportSnapshotTests(unittest.TestCase):
    def test_named_otc_refusal_is_structured(self) -> None:
        from tools.moomoo.opend_quote_transport import MARKET_SNAPSHOT_MAX_CODES, OpendCurrentKlineSession

        session = OpendCurrentKlineSession(host="127.0.0.1", port=11111, sdk=object())
        session.fetch_future_quotes = lambda codes: {  # type: ignore[method-assign]
            "reason_code": "MOOMOO_PROTOCOL_ERROR", "rows": None,
            "vendor_ret_msg": "US OTC market quote is not available for BCHG."}
        refused = session.fetch_market_snapshot(["US.SPY", "US.BCHG"])
        self.assertEqual((refused["reason_code"], refused["refused_codes"]), ("MOOMOO_QUOTE_NOT_ENTITLED", ["US.BCHG"]))
        # Live OpenD, equity list from Finviz: a code the vendor does not carry fails the batch by name.
        session.fetch_future_quotes = lambda codes: {  # type: ignore[method-assign]
            "reason_code": "MOOMOO_PROTOCOL_ERROR", "rows": None, "vendor_ret_msg": "Unknown stock. BF-A"}
        self.assertEqual(session.fetch_market_snapshot(["US.SPY", "US.BF-A"])["refused_codes"], ["US.BF-A"])
        session.fetch_future_quotes = lambda codes: {  # type: ignore[method-assign]
            "reason_code": "MOOMOO_PROTOCOL_ERROR", "rows": None, "vendor_ret_msg": "disconnected"}
        self.assertNotIn("refused_codes", session.fetch_market_snapshot(["US.SPY"]))
        self.assertEqual(session.fetch_market_snapshot(["US.X"] * (MARKET_SNAPSHOT_MAX_CODES + 1))["reason_code"],
                         "MOOMOO_PROTOCOL_ERROR")


if __name__ == "__main__":
    unittest.main()

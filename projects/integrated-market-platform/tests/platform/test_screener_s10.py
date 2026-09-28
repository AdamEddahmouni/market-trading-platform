"""S10 Crypto universe regression contracts."""

import unittest

from market_platform_foundation.ui_api.screener_universes import UNIVERSES
from market_platform_foundation.ui_api.screener_crypto import CryptoScreener, project_catalog, project_ticker, project_ohlc
from market_platform_foundation.ui_api.screener_query import parse_query


class CryptoUniverseTests(unittest.TestCase):
    def test_exactly_five_core_universes(self):
        self.assertEqual(list(UNIVERSES), ["US_EQUITIES", "FUTURES", "US_ETFS", "BONDS", "CRYPTO"])


class KrakenProjectionTests(unittest.TestCase):
    def test_catalog_preserves_pair_order_venue_and_status(self):
        payload = {"error": [], "result": {
            "BTC/USD": {"base": "BTC", "quote": "USD", "wsname": "XBT/USD", "aclass_base": "currency",
                        "aclass_quote": "currency", "status": "online", "ordermin": "0.0001",
                        "tick_size": "0.1", "lot_decimals": 8},
            "BTC/USDT": {"base": "BTC", "quote": "USDT", "aclass_base": "currency",
                         "aclass_quote": "currency", "status": "online"},
            "USD/BTC": {"base": "USD", "quote": "BTC", "aclass_base": "currency",
                        "aclass_quote": "currency", "status": "online"},
            "ETH/USD": {"base": "ETH", "quote": "USD", "aclass_base": "currency",
                        "aclass_quote": "currency", "status": "offline"},
        }}
        rows = project_catalog(payload, as_of="2026-09-28T12:00:00Z")
        self.assertEqual([row["symbol"] for row in rows], ["BTC/USD", "BTC/USDT", "USD/BTC"])
        self.assertEqual(len({row["instrument"]["instrument_id"] for row in rows}), 3)
        self.assertEqual(rows[0]["instrument"]["venue_id"], "KRAKEN")
        self.assertEqual(rows[0]["product_type"], "SPOT")
        self.assertEqual(rows[0]["min_order_size"], "0.0001")

    def test_ticker_uses_rolling_volume_and_utc_day_change(self):
        data = {"a": ["101"], "b": ["99"], "c": ["100"], "v": ["2", "5"],
                "p": ["98", "97"], "h": ["105", "110"], "l": ["95", "90"],
                "o": "80", "t": [2, 5]}
        values = project_ticker(data)
        self.assertEqual(values["change_pct"], 25)
        self.assertEqual(values["base_volume"], 5)
        self.assertEqual(values["quote_volume"], 485)
        self.assertEqual(values["high_24h"], 110)
        self.assertEqual(values["low_24h"], 90)
        self.assertEqual(values["spread_pct"], 2)


class CryptoQueryTests(unittest.TestCase):
    def setUp(self):
        self.pairs = {"error": [], "result": {
            pair: {"base": base, "quote": quote, "aclass_base": "currency", "aclass_quote": "currency",
                   "status": "online"}
            for pair, base, quote in (("BTC/USD", "BTC", "USD"), ("ETH/USD", "ETH", "USD"))}}
        self.tickers = {"error": [], "result": {
            pair: {"a": [str(price + 1)], "b": [str(price - 1)], "c": [str(price)],
                   "v": ["2", "5"], "p": ["98", "97"], "t": [2, 5],
                   "h": ["105", "110"], "l": ["95", "90"], "o": "80"}
            for pair, price in (("BTC/USD", 100), ("ETH/USD", 50))}}

    def service(self, tickers=None):
        class Client:
            def asset_pairs(inner):
                return self.pairs

            def ticker(inner, pair=None):
                return self.tickers if pair is None else {"error": [], "result": {key: self.tickers["result"][key]
                                                                  for key in pair if key in self.tickers["result"]}}

        instance = CryptoScreener(client=Client(), env={"IMP_CRYPTO_LIVE": "1"},
                                  now=lambda: "2026-09-28T12:00:00Z", clock=lambda: 0)
        if tickers is not None:
            self.tickers = tickers
        return instance

    def test_complete_snapshot_filters_and_pages_canonically(self):
        query = parse_query(universe="CRYPTO", sort="price", descending=True,
                            filters=[{"id": "p", "field": "price", "operator": "gt", "value": 60}], limit=1)
        result = self.service().read(query)
        self.assertEqual(result["result_count"], 1)
        self.assertEqual(result["rows"][0]["symbol"], "BTC/USD")
        self.assertEqual(result["snapshot"]["complete"], True)
        self.assertEqual(result["market_session"], "24_7")

    def test_partial_ticker_refuses_broad_market_filter(self):
        partial = {"error": [], "result": {"BTC/USD": self.tickers["result"]["BTC/USD"]}}
        query = parse_query(universe="CRYPTO", sort="price")
        result = self.service(partial).read(query)
        self.assertEqual(result["result_count"], 0)
        self.assertEqual(result["source_error"], "MARKET_SNAPSHOT_INCOMPLETE")

    def test_next_page_keeps_snapshot_and_catalog_counts(self):
        instance = self.service()
        first = instance.read(parse_query(universe="CRYPTO", sort="symbol", descending=False, limit=1))
        second = instance.read(parse_query(universe="CRYPTO", sort="symbol", descending=False, limit=1,
                                           offset=1, result_set=first["result_set_id"]))
        self.assertEqual([first["rows"][0]["symbol"], second["rows"][0]["symbol"]], ["BTC/USD", "ETH/USD"])
        self.assertEqual(second["snapshot"], first["snapshot"])
        self.assertEqual(second["unfiltered_count"], first["unfiltered_count"])


class CryptoBarsTests(unittest.TestCase):
    def test_weekend_utc_bars_keep_last_candle_forming(self):
        payload = {"error": [], "result": {"BTC/USD": [
            [1790510400, "100", "102", "99", "101", "100.5", "3", 8],
            [1790510460, "101", "103", "100", "102", "101.5", "2", 5],
        ], "last": 1790510460}}
        result = project_ohlc(payload, pair="BTC/USD", timeframe="1m", received_at="2026-09-27T12:02:00Z")
        self.assertEqual(result["session_scope"], "24_7")
        self.assertEqual(result["bar_count"], 1)
        self.assertEqual(result["bars"][0]["close"], 101)
        self.assertEqual(result["forming"]["close"], 102)


# ------------------------------------------------------------------ S10 closure
class FullClient:
    """Kraken-shaped public responses: catalog precision, one missing last price, 1m OHLC."""

    pairs = {"error": [], "result": {
        "BTC/USD": {"base": "BTC", "quote": "USD", "aclass_base": "currency", "aclass_quote": "currency",
                    "status": "online", "tick_size": "0.1", "pair_decimals": 1, "lot_decimals": 8,
                    "cost_decimals": 5, "ordermin": "0.00005", "costmin": "0.5"},
        "SHIB/USD": {"base": "SHIB", "quote": "USD", "aclass_base": "currency", "aclass_quote": "currency",
                     "status": "online", "tick_size": "0.000000001", "pair_decimals": 9, "lot_decimals": 5,
                     "cost_decimals": 5},
        "OLD/USD": {"base": "OLD", "quote": "USD", "aclass_base": "currency", "aclass_quote": "currency",
                    "status": "cancel_only"},
    }}

    def asset_pairs(self):
        return self.pairs

    def ticker(self, pair=None):
        tickers = {"BTC/USD": {"a": ["83000.2"], "b": ["83000.1"], "c": ["83000.1"], "v": ["10", "20"],
                               "p": ["82000", "82500"], "t": [100, 200], "h": ["84000", "84500"],
                               "l": ["81000", "80500"], "o": "82000"},
                   # Kraken lists the pair but publishes no usable last price.
                   "SHIB/USD": {"a": ["0.000005741"], "b": ["0.000005739"], "c": ["0"], "v": ["0", "0"],
                                "p": ["0", "0"], "t": [0, 0], "h": ["0", "0"], "l": ["0", "0"], "o": "0"}}
        return {"error": [], "result": tickers if pair is None else {key: tickers[key] for key in pair if key in tickers}}

    def ohlc(self, pair, interval):
        start = 1790510400
        bars = [[start + index * 60, str(100 + index % 7), str(103 + index % 7), str(98 + index % 7),
                 str(101 + index % 7), "100", "2", 5] for index in range(80)]
        return {"error": [], "result": {pair: bars, "last": bars[-1][0]}}


def full_service():
    return CryptoScreener(client=FullClient(), env={"IMP_CRYPTO_LIVE": "1"}, now=lambda: "2026-09-27T12:00:00Z",
                          clock=lambda: 0)


class CryptoRegistryTests(unittest.TestCase):
    def test_panel_matrix_is_backed_by_venue_evidence_only(self):
        spec = UNIVERSES["CRYPTO"]
        self.assertEqual(spec.panels, ("order_flow", "cvd", "level2", "charts", "news"))  # S11 News & Analysis
        for equity_only in ("futures", "options", "short_squeeze", "rates_curve"):
            self.assertNotIn(equity_only, spec.panels)
        self.assertEqual(spec.session_model, "24_7")
        self.assertEqual(list(spec.views), ["Overview", "Performance", "Liquidity", "Custom"])
        self.assertTrue({"trade_count", "base_asset", "quote_asset"} <= spec.columns)

    def test_change_is_labelled_utc_day_not_rolling_24h(self):
        from market_platform_foundation.ui_api.screener_filters import filter_catalog

        units = {entry["field"]: entry["unit"] for entry in filter_catalog("CRYPTO")}
        self.assertEqual(units["change_pct"], "UTC_DAY_PERCENT")
        self.assertEqual(units["price"], "QUOTE_UNITS")
        self.assertNotIn("market_cap", units)


class CryptoCatalogTruthTests(unittest.TestCase):
    def test_increments_come_from_venue_precision(self):
        rows = {row["symbol"]: row for row in project_catalog(FullClient.pairs, as_of="t")}
        self.assertEqual(set(rows), {"BTC/USD", "SHIB/USD"})  # cancel_only is not an online market
        self.assertEqual((rows["BTC/USD"]["base_increment"], rows["BTC/USD"]["quote_increment"]),
                         ("0.00000001", "0.00001"))
        self.assertEqual((rows["BTC/USD"]["price_decimals"], rows["SHIB/USD"]["price_decimals"]), (1, 9))

    def test_missing_last_price_stays_missing_not_zero(self):
        result = full_service().read(parse_query(universe="CRYPTO", sort="symbol", descending=False))
        shib = next(row for row in result["rows"] if row["symbol"] == "SHIB/USD")
        self.assertIsNone(shib["fields"]["price"]["value"])
        self.assertEqual(shib["fields"]["price"]["state"], "UNAVAILABLE")
        self.assertIsNone(shib["fields"]["change_pct"]["value"])
        self.assertEqual(result["snapshot"]["priced"], 1)
        # A price filter never admits a pair whose price is unknown.
        priced = full_service().read(parse_query(universe="CRYPTO", filters=[
            {"id": "p", "field": "price", "operator": "gte", "value": 0}]))
        self.assertEqual([row["symbol"] for row in priced["rows"]], ["BTC/USD"])


class CryptoPreviewAndChartTests(unittest.TestCase):
    def setUp(self):
        self.svc = full_service()
        self.btc = next(row for row in self.svc._catalog()[0] if row["symbol"] == "BTC/USD")["instrument"]["instrument_id"]
        self.svc.read(parse_query(universe="CRYPTO", sort="symbol"))

    def test_chart_uses_venue_bars_and_levels_with_kraken_provenance(self):
        chart = self.svc.chart(self.btc, "1m")
        self.assertEqual((chart["schema_version"], chart["market_session"]), ("screener-chart/1.0.0", "24_7"))
        self.assertEqual(chart["bars"]["session_scope"], "24_7")
        self.assertEqual(chart["bars"]["bar_count"], 79)
        self.assertEqual(chart["levels"]["provider"], "KRAKEN_SPOT_PUBLIC")
        self.assertEqual(chart["levels"]["session_scope"], "24_7")
        self.assertEqual(chart["levels"]["price"]["source"], "KRAKEN_TICKER_LAST")
        self.assertIsNone(self.svc.chart("XA01:0000000000000000", "1m"))

    def test_levels_are_unavailable_without_current_bars(self):
        levels = CryptoScreener.levels({"timeframe": "1m", "source_id": "x", "state": "UNAVAILABLE",
                                        "reason": "CRYPTO_BARS_UNAVAILABLE", "bar_count": 0,
                                        "latest_complete_bar_end": None, "bars": []}, {"state": "UNAVAILABLE"})
        self.assertEqual((levels["state"], levels["reason"], levels["zones"]),
                         ("UNAVAILABLE", "CRYPTO_BARS_UNAVAILABLE", []))

    def test_preview_structure_and_no_equity_fields(self):
        from unittest import mock

        from market_platform_foundation.ui_api import screener_crypto
        from market_platform_foundation.ui_api.screener_preview import ScreenerPreviewService

        service = object.__new__(ScreenerPreviewService)
        service._now_ns = lambda: 1_790_510_400_000_000_000
        with mock.patch.object(screener_crypto, "_SERVICE", self.svc):
            preview = service.read(self.btc, universe="CRYPTO", timeframe="1m")
        self.assertEqual(preview["market_session"], "24_7")
        instrument = preview["instrument"]
        self.assertEqual((instrument["base_increment"], instrument["quote_increment"], instrument["price_increment"]),
                         ("0.00000001", "0.00001", "0.1"))
        self.assertIn("levels", preview)
        for equity in ("sector", "industry", "market_cap", "float_shares", "short_float_pct"):
            self.assertNotIn(equity, preview["fields"])
            self.assertNotIn(equity, instrument)


class CryptoStreamConfigurationTests(unittest.TestCase):
    def test_panels_are_honestly_unavailable_when_crypto_is_not_enabled(self):
        import os
        from unittest import mock

        from market_platform_foundation.ui_api.screener_crypto import _stream_runtime
        from market_platform_foundation.ui_api.screener_specialist import ScreenerSpecialistService

        with mock.patch.dict(os.environ, {"IMP_CRYPTO_LIVE": "0"}):
            self.assertIsNone(_stream_runtime())
            service = ScreenerSpecialistService(runtime_getter=_stream_runtime, known_instrument=lambda _i: True,
                                                session_label=lambda: "24_7", trades_capability="CRYPTO_TRADES",
                                                depth_capability="CRYPTO_BOOK", schedule_expiry=False)
            flow = service.order_flow("XA01:0000000000000001")
        self.assertEqual((flow["state"], flow["reason"], flow["market_session"]),
                         ("UNAVAILABLE", "LIVE_RUNTIME_UNAVAILABLE", "24_7"))

    def test_rapid_pair_switching_is_not_held_like_opend(self):
        # Kraken frees a pair on unsubscribe; only the OpenD runtime keeps a
        # released instrument occupying a slot for its one-minute minimum.
        from market_platform_foundation.crypto_market.kraken_stream import BOOK, TRADES, KrakenStreamRuntime
        from market_platform_foundation.ui_api import screener_crypto
        from market_platform_foundation.ui_api.screener_specialist import MAX_SPECIALIST_INSTRUMENTS

        pairs = [f"XA01:{index:016X}" for index in range(MAX_SPECIALIST_INSTRUMENTS + 3)]
        runtime = KrakenStreamRuntime(resolve=lambda instrument: (f"P{instrument[-2:]}/USD", 1, 8), start_worker=False)
        from unittest import mock

        with mock.patch.object(screener_crypto, "_SPECIALIST", None), \
                mock.patch.object(screener_crypto, "_stream_runtime", lambda: runtime), \
                mock.patch.object(screener_crypto, "crypto_screener_service") as catalog:
            catalog.return_value.row_for.return_value = ({"instrument_id": "x"}, None)
            service = screener_crypto.crypto_specialist_service()
            service._schedule = False
            for pair in pairs:
                result = service.demand("c1", pair, ["order_flow", "cvd", "level2"])
                self.assertTrue(all(item["accepted"] for item in result["capabilities"]), pair)
                self.assertEqual(result["cap"]["occupied_instruments"], 1)
        self.assertEqual({key for key, consumers in runtime._consumers.items() if consumers},
                         {(pairs[-1], TRADES), (pairs[-1], BOOK)})

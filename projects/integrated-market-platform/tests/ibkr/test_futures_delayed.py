"""IBKR delayed futures source: contract identity, delayed-only labeling, and the Screener fill."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from market_platform_foundation.market_data.delayed_futures_bridge import (
    FuturesContractRef,
    delayed_futures_source,
    inject_delayed_futures_source,
)
from market_platform_foundation.ui_api.screener_multi import MultiUniverseScreener, _quote_from_delayed_source
from tools.ibkr.futures_delayed import DELAYED_MARKET_DATA, IDLE_SECONDS, IbkrDelayedFutures, install_delayed_futures_source

NOW = datetime(2026, 10, 1, 22, 30, tzinfo=UTC).timestamp()
ES = FuturesContractRef(key="XA01:ESZ26", root="ES", contract_month="202612", expiry="2026-12-18")


def contract(con_id, exchange="CME", expiry="20261218", currency="USD"):
    return SimpleNamespace(conId=con_id, exchange=exchange, lastTradeDateOrContractMonth=expiry, currency=currency)


class FakeIb:
    def __init__(self, details):
        self.details, self.subscribed, self.cancelled, self.history = details, [], [], []

    def reqContractDetails(self, _wanted):
        return [SimpleNamespace(contract=item) for item in self.details]

    def reqMktData(self, item, *_args):
        self.subscribed.append(item)
        return SimpleNamespace(last=7726.0, bid=7725.75, ask=7726.0, close=7724.0, volume=3281.0,
                               time=datetime.fromtimestamp(NOW - 2, tz=UTC))

    def cancelMktData(self, item):
        self.cancelled.append(item)

    def reqHistoricalData(self, item, *_args, **_kwargs):
        self.history.append(item)
        bar = lambda start, close: SimpleNamespace(date=datetime.fromtimestamp(start, tz=UTC), open=close, high=close,  # noqa: E731
                                                   low=close, close=close, volume=10.0)
        return [bar(NOW - 600, 7725.0), bar(NOW - 300, 7726.0), bar(NOW - 100, 7727.0)]   # the last is still forming


def source(details, clock):
    return IbkrDelayedFutures(host="127.0.0.1", port=4001, client_id=40, clock=clock,
                              ib_factory=lambda: None, future_factory=lambda root, month: (root, month))


class ContractIdentityTests(unittest.TestCase):
    def step(self, details):
        ib, item = FakeIb(details), source(details, lambda: NOW)
        item.quotes([ES])
        item._step(ib)
        return ib, item

    def test_one_contract_listed_on_two_venues_uses_the_listing_exchange(self):
        ib, item = self.step([contract(1, "QBALGO"), contract(1, "CME")])
        self.assertEqual([entry.exchange for entry in ib.subscribed], ["CME"])
        self.assertEqual(item.quotes([ES])[ES.key]["last"], 7726.0)

    def test_two_different_contracts_are_ambiguous_and_stay_unavailable(self):
        ib, item = self.step([contract(1), contract(2)])
        self.assertEqual((ib.subscribed, item.quotes([ES])), ([], {}))

    def test_expiry_or_currency_mismatch_is_not_the_catalog_contract(self):
        for details in ([contract(1, expiry="20270319")], [contract(1, currency="EUR")], []):
            with self.subTest(details=details):
                ib, item = self.step(details)
                self.assertEqual((ib.subscribed, item.quotes([ES])), ([], {}))


class SubscriptionTests(unittest.TestCase):
    def test_a_zero_price_is_no_price(self):
        ib, item = FakeIb([contract(1)]), source([contract(1)], lambda: NOW)
        ib.reqMktData = lambda *_args: SimpleNamespace(last=0.0, bid=-1.0, ask=float("nan"), close=5.2, volume=0.0, time=None)
        item.quotes([ES])
        item._step(ib)
        self.assertEqual(item.quotes([ES]), {})               # nothing tradeable was reported, so nothing is published

    def test_an_unrequested_contract_is_unsubscribed_and_no_longer_published(self):
        clock = {"now": NOW}
        ib, item = FakeIb([contract(1)]), source([contract(1)], lambda: clock["now"])
        item.quotes([ES])
        item._step(ib)
        self.assertIn(ES.key, item.quotes([]) | item._quotes)
        clock["now"] += IDLE_SECONDS + 1
        item._step(ib)
        self.assertEqual((len(ib.cancelled), item._quotes), (1, {}))

    def test_bars_drop_the_forming_bar_and_are_cached(self):
        ib, item = FakeIb([contract(1)]), source([contract(1)], lambda: NOW)
        item._fetch_bars(ib, ES, "5m")
        cached_at, bars = item._bars[(ES.key, "5m")]
        self.assertEqual(([bar["close"] for bar in bars], cached_at), ([7725.0, 7726.0], NOW))
        self.assertEqual(item.bars(ES, "5m"), bars)          # served from the cache; no second provider call
        self.assertEqual(len(ib.history), 1)
        self.assertIsNone(item.bars(ES, "1h"))

    def test_only_delayed_market_data_is_requested(self):
        self.assertEqual(DELAYED_MARKET_DATA, 3)


class InstallTests(unittest.TestCase):
    def tearDown(self):
        inject_delayed_futures_source(None)

    def test_absent_unless_ibkr_tws_is_explicitly_enabled(self):
        for env in ({}, {"IMP_IBKR_LIVE": "1"}, {"IMP_IBKR_LIVE": "0", "IMP_IBKR_TRANSPORT": "tws"}):
            with self.subTest(env=env):
                self.assertIsNone(install_delayed_futures_source(env))
                self.assertIsNone(delayed_futures_source())


class ScreenerFillTests(unittest.TestCase):
    VALUES = {"last": 7726.0, "bid": 7725.75, "ask": 7726.0, "prev_close": 7724.0, "volume": 3281.0, "updated_s": NOW - 2}
    ROW = {"instrument": {"instrument_id": ES.key}, "root": "ES", "contract_month": "202612", "expiry": "2026-12-18"}

    def test_a_delayed_quote_is_never_live_and_names_its_source(self):
        quote = _quote_from_delayed_source(self.VALUES, NOW)
        self.assertEqual((quote["state"], quote["reason"], quote["age_ms"]), ("DELAYED", "DELAYED_PROVIDER", 2000))
        price = quote["fields"]["price"]
        self.assertEqual((price["value"], price["source"], price["state"]), (7726.0, "IBKR_DELAYED", "DELAYED"))
        self.assertAlmostEqual(quote["fields"]["change_pct"]["value"], (7726.0 - 7724.0) / 7724.0 * 100)
        self.assertEqual(quote["fields"]["open_interest"], {"value": None, "source": "IBKR_DELAYED", "state": "UNAVAILABLE",
                                                            "as_of": price["as_of"]})
        self.assertIsNone(_quote_from_delayed_source({"updated_s": NOW}, NOW))

    def fill(self, quotes, delayed):
        service = MultiUniverseScreener(now_s=lambda: NOW, delayed_futures_getter=lambda: delayed)
        service._fill_from_delayed_source(quotes, {ES.key: self.ROW})
        return quotes

    def test_fills_only_what_the_primary_source_left_empty(self):
        asked = []
        delayed = SimpleNamespace(quotes=lambda refs: asked.append(refs) or {ES.key: self.VALUES})
        empty = {"state": "UNAVAILABLE", "reason": "MOOMOO_QUOTE_NOT_ENTITLED", "fields": {}}
        self.assertEqual(self.fill({ES.key: dict(empty)}, delayed)[ES.key]["state"], "DELAYED")
        self.assertEqual(asked, [[ES]])
        live = {"state": "LIVE", "reason": None, "fields": {"price": {"value": 1.0}}}
        self.assertEqual(self.fill({ES.key: live}, delayed)[ES.key], live)
        self.assertEqual(len(asked), 1)                       # a live primary quote is never asked about

    def test_no_source_an_unknown_contract_or_a_failing_source_changes_nothing(self):
        empty = {"state": "UNAVAILABLE", "reason": "MOOMOO_QUOTE_NOT_ENTITLED", "fields": {}}

        def broken(_refs):
            raise OSError("gateway down")

        for delayed in (None, SimpleNamespace(quotes=lambda refs: {}), SimpleNamespace(quotes=broken)):
            with self.subTest(delayed=delayed):
                self.assertEqual(self.fill({ES.key: dict(empty)}, delayed)[ES.key], empty)


if __name__ == "__main__":
    unittest.main()

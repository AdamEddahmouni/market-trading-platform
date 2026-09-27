"""S7 Screener current options context: Finviz chain adapter, normalization, analytics, service truth."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.finviz.options import FinvizOptionsClient, parse_options_csv  # noqa: E402
from market_platform_foundation.platform.security.leak_audit import assert_no_secrets_in_payload  # noqa: E402
from market_platform_foundation.platform.security.route_policy import policy_for_route  # noqa: E402
from market_platform_foundation.providers.adapters.finviz_option_chain import (  # noqa: E402
    FinvizOptionChainProvider, finviz_ticker, normalize_chain,
)
from market_platform_foundation.providers.adapters.fixture_option_chain import FixtureOptionChainProvider  # noqa: E402
from market_platform_foundation.providers.composition import (  # noqa: E402
    ProviderComposition, configure_fixture_provider_composition, configure_provider_composition,
    get_provider_composition,
)
from market_platform_foundation.ui_api.screener_config import validate_panel_layout  # noqa: E402
from market_platform_foundation.ui_api.screener_filters import filter_catalog  # noqa: E402
from market_platform_foundation.ui_api.screener_options import (  # noqa: E402
    LAST_GOOD_MAX_AGE_S, REFRESH_AFTER_S, STALE_AFTER_S, ScreenerOptionsService, chain_analytics,
    current_option_chain_provider,
)
from market_platform_foundation.ui_api.screener_universes import FUTURES, US_EQUITIES, US_ETFS, universe_spec  # noqa: E402

COLUMNS = ["Contract Name", "Last Trade", "Expiry", "Strike", "Last Close", "Bid", "Ask", "Change $", "Change %",
           "Volume", "Open Int.", "Type", "IV", "Delta", "Gamma", "Theta", "Vega", "Rho"]
#: Sunday 2026-09-27 12:00 ET (market closed) and Monday 2026-09-28 11:00 ET (regular session).
SUNDAY = datetime(2026, 9, 27, 16, 0, tzinfo=UTC)
MONDAY = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)
API_KEY = "sk-live-0123456789abcdef0123456789"


def contract(symbol: str = "AAPL", expiry: str = "10/2/2026", kind: str = "call", strike: str = "250", *,
             bid: str = "1.10", ask: str = "1.20", last: str = "1.15", volume: str = "100", oi: str = "1000",
             iv: str = "0.3120", delta: str = "0.5", **extra: str) -> dict[str, str]:
    month, day, year = expiry.split("/")
    try:
        strike_code = f"{int(round(float(strike) * 1000)):08d}"
    except ValueError:
        strike_code = "00000000"
    occ = f"{symbol.replace('-', '')}{year[2:]}{int(month):02d}{int(day):02d}{kind[0].upper()}{strike_code}"
    row = {"Contract Name": occ, "Last Trade": "9/25/2026 3:59:59 PM", "Expiry": expiry, "Strike": strike,
           "Last Close": last, "Bid": bid, "Ask": ask, "Change $": "0", "Change %": "0.00%", "Volume": volume,
           "Open Int.": oi, "Type": kind, "IV": iv, "Delta": delta if kind == "call" else f"-{delta}",
           "Gamma": "0.0100", "Theta": "-0.0500", "Vega": "0.2000", "Rho": "0.0300"}
    row.update(extra)
    return row


def csv_text(rows: list[dict[str, str]]) -> str:
    lines = [",".join(COLUMNS)] + [",".join(row.get(column, "") for column in COLUMNS) for row in rows]
    return "\n".join(lines) + "\n"


class FakeManager:
    """Stands in for the Finviz request manager; records every request."""

    def __init__(self, responses: list[tuple[int, str]]):
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def get(self, url, *, params, priority, cache_ttl_s, api_key):
        self.calls.append({"url": url, "params": dict(params), "cache_ttl_s": cache_ttl_s})
        status, body = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        return status, body, {"cached": False, "cache_hit": False, "status_code": status}

    def clear_cache(self):
        pass


def provider_with(responses: list[tuple[int, str]], *, api_key: str | None = API_KEY, now: datetime = SUNDAY):
    manager = FakeManager(responses)
    provider = FinvizOptionChainProvider(
        client_factory=lambda: FinvizOptionsClient(api_key=api_key, request_manager=manager) if api_key
        else _Unconfigured(), clock=lambda: now)
    return provider, manager


class _Unconfigured:
    def fetch_chain(self, symbol):
        return {"success": False, "error": "NOT_CONFIGURED", "contracts": [], "columns": []}


def standard_chain() -> list[dict[str, str]]:
    return [
        contract(expiry="9/25/2026", strike="245"),  # expired on Friday
        contract(strike="245", volume="300", oi="2000"), contract(kind="put", strike="245", volume="100", oi="1500"),
        contract(strike="250", volume="600", oi="4000", iv="0.2900"), contract(kind="put", strike="250", volume="200", oi="3000", iv="0.3300"),
        contract(strike="255", volume="100", oi="500"), contract(kind="put", strike="255", volume="0", oi="0", bid="", ask=""),
        contract(expiry="10/16/2026", strike="250", volume="50", oi="800"),
        contract(expiry="10/16/2026", kind="put", strike="250", volume="75", oi="900"),
    ]


class Rows:
    def __init__(self):
        self.rows = {
            "AAPL-ID": {"symbol": "AAPL", "fields": {"price": {"value": 251.2, "source": "FINVIZ_ELITE", "as_of": "2026-09-27T15:00:00Z"}}},
            "NVDA-ID": {"symbol": "NVDA", "fields": {"price": {"value": 180.0, "source": "FINVIZ_ELITE"}}},
            "SPY-ID": {"symbol": "SPY", "market_data_id": "SPY", "fields": {"price": {"value": None}}},
        }

    def __call__(self, instrument_id, universe, snapshot_id):
        return self.rows.get(instrument_id), None


class Clock:
    def __init__(self, now: datetime = SUNDAY):
        self.now = now.timestamp()

    def __call__(self):
        return self.now


def service_for(provider, *, clock: Clock | None = None, session: str = "CLOSED", quote=None, max_entries: int = 6):
    clock = clock or Clock()
    return ScreenerOptionsService(
        provider_getter=lambda: provider, row_getter=Rows(), clock=clock, session_label=lambda: session,
        quote_getter=quote or (lambda instrument, universe: {"state": "UNAVAILABLE", "fields": {}}),
        max_entries=max_entries), clock


class FinvizProviderTests(unittest.TestCase):
    def test_configured_current_chain_uses_request_manager_and_redacts(self):
        provider, manager = provider_with([(200, csv_text(standard_chain()))])
        result = provider.fetch_chain("aapl", underlying_id="AAPL-ID")
        self.assertEqual(result.status, "available")
        self.assertEqual(len(manager.calls), 1)
        self.assertEqual(manager.calls[0]["params"]["t"], "AAPL")
        self.assertIsNotNone(manager.calls[0]["cache_ttl_s"])
        chain = result.details["chain"]
        self.assertEqual((chain.provider_rows, len(chain.rows), chain.expired_excluded), (9, 8, 1))
        self.assertEqual(chain.unmapped_columns, ("Change $", "Change %"))
        rendered = json.dumps([dict(event) for event in result.events])
        self.assertNotIn(API_KEY, rendered)
        self.assertNotIn("auth", rendered)

    def test_not_configured(self):
        provider, manager = provider_with([(200, "")], api_key=None)
        result = provider.fetch_chain("AAPL")
        self.assertEqual((result.status, result.reason_code), ("unavailable", "PROVIDER_NOT_CONFIGURED"))
        self.assertEqual(manager.calls, [])

    def test_http_error_login_page_and_invalid_csv(self):
        cases = {(500, "oops"): ("unavailable", "FINVIZ_OPTIONS_HTTP_ERROR"),
                 (403, ""): ("not_entitled", "FINVIZ_OPTIONS_AUTH_REJECTED"),
                 (429, ""): ("unavailable", "FINVIZ_RATE_LIMITED"),
                 (200, "<html><body>Login</body></html>"): ("not_entitled", "FINVIZ_OPTIONS_AUTH_REJECTED"),
                 (200, ""): ("unavailable", "FINVIZ_OPTIONS_INVALID_RESPONSE")}
        for response, expected in cases.items():
            provider, _ = provider_with([response])
            result = provider.fetch_chain("AAPL")
            self.assertEqual((result.status, result.reason_code), expected, response)
            self.assertEqual(result.events, ())

    def test_header_only_export_is_no_chain(self):
        provider, _ = provider_with([(200, csv_text([]))])
        result = provider.fetch_chain("BRK-A")
        self.assertEqual((result.status, result.reason_code), ("empty", "NO_CHAIN"))

    def test_csv_missing_required_columns_is_invalid(self):
        provider, _ = provider_with([(200, "Contract Name,Bid\nX,1\n")])
        self.assertEqual(provider.fetch_chain("AAPL").reason_code, "FINVIZ_OPTIONS_INVALID_RESPONSE")

    def test_point_in_time_request_is_refused(self):
        provider, manager = provider_with([(200, csv_text(standard_chain()))])
        result = provider.fetch_chain("AAPL", as_of_time_ns=1)
        self.assertEqual(result.reason_code, "OPTION_CHAIN_CURRENT_ONLY")
        self.assertEqual(manager.calls, [])

    def test_share_class_and_etf_dot_symbols_use_finviz_dash(self):
        self.assertEqual(finviz_ticker("brk.b"), "BRK-B")
        provider, manager = provider_with([(200, csv_text([]))])
        self.assertEqual(provider.fetch_chain("../x").reason_code, "INVALID_UNDERLYING")
        self.assertEqual(manager.calls, [])

    def test_parse_options_csv_contract(self):
        rows, columns, error = parse_options_csv(csv_text(standard_chain()))
        self.assertIsNone(error)
        self.assertEqual(list(columns), COLUMNS)
        self.assertEqual(len(rows), 9)


class NormalizationTests(unittest.TestCase):
    def normalize(self, rows, now=SUNDAY):
        return normalize_chain(rows, COLUMNS, symbol="AAPL", underlying_id="AAPL-ID", now=now)

    def test_types_units_identity_and_dte(self):
        chain = self.normalize([contract(strike="277.5", bid="2.00", ask="2.10", volume="1,234", oi="5678")])
        row = chain.rows[0]
        self.assertEqual((row.option_type, row.expiration, row.dte, row.strike), ("CALL", "2026-10-02", 5, 277.5))
        self.assertEqual((row.bid, row.ask, row.mid, row.spread, row.spread_pct), (2.0, 2.1, 2.05, 0.1, 4.88))
        self.assertEqual((row.volume, row.open_interest), (1234, 5678))
        self.assertEqual(row.iv, 0.312)  # decimal fraction: 31.2 %
        self.assertEqual((row.delta, row.gamma, row.theta, row.vega, row.rho), (0.5, 0.01, -0.05, 0.2, 0.03))
        self.assertEqual(row.option_id, "AAPL20261002C00277500")
        self.assertEqual(row.provider_symbol, "AAPL261002C00277500")
        self.assertEqual(row.underlying_id, "AAPL-ID")
        self.assertEqual(row.last_trade_at, "2026-09-25T19:59:59Z")
        self.assertEqual(row.to_dict()["volume_oi_ratio"], 0.2173)

    def test_put_normalization(self):
        row = self.normalize([contract(kind="PUT", strike="240")]).rows[0]
        self.assertEqual((row.option_type, row.delta, row.option_id), ("PUT", -0.5, "AAPL20261002P00240000"))

    def test_missing_values_are_unavailable_not_zero(self):
        row = self.normalize([contract(bid="", ask="", last="", oi="", iv="", delta="", Gamma="", Theta="",
                                       Vega="", Rho="", **{"Last Trade": ""})]).rows[0]
        self.assertEqual((row.bid, row.ask, row.mid, row.spread_pct, row.last, row.open_interest), (None,) * 6)
        self.assertEqual((row.iv, row.delta, row.gamma, row.theta, row.vega, row.rho, row.last_trade_at), (None,) * 7)
        self.assertIn("NO_TWO_SIDED_MARKET", row.quality_flags)
        self.assertEqual(row.volume, 100)
        self.assertIsNone(row.to_dict()["volume_oi_ratio"])

    def test_provider_zero_volume_stays_zero_and_blank_volume_is_unavailable(self):
        rows = self.normalize([contract(volume="0"), contract(strike="260", volume="")]).rows
        self.assertEqual([row.volume for row in rows], [0, None])

    def test_iv_sentinels_and_inconsistent_greeks(self):
        rows = self.normalize([contract(iv="-1.0000"), contract(strike="260", iv="0.0000"),
                               contract(strike="265", iv="abc"), contract(strike="270", delta="-0.4")]).rows
        self.assertEqual([row.iv for row in rows[:3]], [None, None, None])
        self.assertTrue(all("IV_INVALID" in row.quality_flags for row in rows[:3]))
        self.assertIsNone(rows[3].delta)
        self.assertIn("GREEKS_INCONSISTENT", rows[3].quality_flags)

    def test_crossed_wide_and_zero_bid_markets(self):
        rows = self.normalize([contract(bid="1.50", ask="1.20"), contract(strike="260", bid="0.10", ask="0.50"),
                               contract(strike="265", bid="0", ask="0.05")]).rows
        self.assertEqual((rows[0].mid, rows[0].spread), (None, None))
        self.assertIn("CROSSED_OPTION_MARKET", rows[0].quality_flags)
        self.assertIn("WIDE_OPTION_SPREAD", rows[1].quality_flags)
        self.assertTrue({"ZERO_BID", "NO_TWO_SIDED_MARKET"} <= set(rows[2].quality_flags))

    def test_malformed_rows_are_dropped_and_counted(self):
        chain = self.normalize([
            contract(), contract(strike="abc"), contract(strike="-5"), contract(Type="straddle"),
            contract(Expiry="13/45/2026", strike="260"), contract(strike="270", volume="-3", oi="-1"),
            contract(strike="275", **{"Contract Name": "AAPL261002C00999000"}), contract(),
        ])
        self.assertEqual(len(chain.rows), 2)
        self.assertEqual(chain.dropped, {"INVALID_STRIKE": 2, "INVALID_TYPE": 1, "INVALID_EXPIRY": 1,
                                         "IDENTITY_MISMATCH": 1, "DUPLICATE_CONTRACT": 1})
        negative = next(row for row in chain.rows if row.strike == 270)
        self.assertEqual((negative.volume, negative.open_interest), (None, None))
        self.assertTrue({"INVALID_VOLUME", "INVALID_OPEN_INTEREST"} <= set(negative.quality_flags))

    def test_expired_contracts_are_removed_including_same_day_after_close(self):
        friday_close = datetime(2026, 10, 2, 20, 30, tzinfo=UTC)  # 16:30 ET on the expiry date
        chain = self.normalize([contract(), contract(expiry="10/9/2026")], now=friday_close)
        self.assertEqual([row.expiration for row in chain.rows], ["2026-10-09"])
        self.assertEqual(chain.expired_excluded, 1)
        morning = datetime(2026, 10, 2, 14, 0, tzinfo=UTC)
        self.assertEqual(self.normalize([contract()], now=morning).rows[0].dte, 0)


class AnalyticsTests(unittest.TestCase):
    def rows(self):
        return list(normalize_chain(standard_chain(), COLUMNS, symbol="AAPL", underlying_id="AAPL-ID", now=SUNDAY).rows)

    def test_volume_oi_ratios_and_counts(self):
        summary = chain_analytics(self.rows(), 251.2)
        self.assertEqual((summary["contracts"], summary["calls"], summary["puts"], summary["expirations"]), (8, 4, 4, 2))
        self.assertEqual((summary["call_volume"], summary["put_volume"], summary["total_volume"]), (1050, 375, 1425))
        self.assertEqual(summary["put_call_volume_ratio"], round(375 / 1050, 4))
        self.assertEqual(summary["call_put_volume_ratio"], round(1050 / 375, 4))
        self.assertEqual((summary["call_open_interest"], summary["put_open_interest"]), (7300, 5400))
        self.assertEqual(summary["put_call_oi_ratio"], round(5400 / 7300, 4))
        self.assertEqual(summary["nearest_expiration"], "2026-10-02")

    def test_zero_and_missing_denominators_are_undefined(self):
        rows = [row for row in self.rows() if row.option_type == "PUT"]
        summary = chain_analytics(rows)
        self.assertIsNone(summary["call_volume"])
        self.assertIsNone(summary["put_call_volume_ratio"])
        zero = normalize_chain([contract(volume="0", oi="0"), contract(kind="put", volume="5", oi="7")], COLUMNS,
                               symbol="AAPL", underlying_id="AAPL-ID", now=SUNDAY).rows
        summary = chain_analytics(list(zero))
        self.assertEqual((summary["call_volume"], summary["put_call_volume_ratio"], summary["put_call_oi_ratio"]), (0, None, None))
        self.assertEqual(json.loads(json.dumps(summary, allow_nan=False))["put_volume"], 5)
        empty = chain_analytics([])
        self.assertEqual((empty["contracts"], empty["call_volume"], empty["median_spread_pct"], empty["nearest_strike"]), (0, None, None, None))

    def test_concentration_and_nearest_strike(self):
        summary = chain_analytics(self.rows(), 251.2)
        top = summary["most_active"][0]
        self.assertEqual((top["type"], top["strike"], top["volume"], top["share_of_side_volume_pct"]), ("CALL", 250.0, 600, 57.14))
        self.assertEqual(summary["largest_open_interest"][0]["open_interest"], 4000)
        near = summary["nearest_strike"]
        self.assertEqual((near["expiration"], near["strike"], near["exact"], near["call_iv"], near["put_iv"]),
                         ("2026-10-02", 250.0, False, 0.29, 0.33))
        self.assertEqual(near["distance_pct"], round((250 - 251.2) / 251.2 * 100, 2))
        self.assertIsNone(chain_analytics(self.rows(), None)["nearest_strike"])

    def test_spread_summary_uses_two_sided_contracts_only(self):
        summary = chain_analytics(self.rows())
        self.assertEqual(summary["two_sided"], 7)
        self.assertEqual(summary["median_spread_pct"], 8.7)


class ServiceTruthTests(unittest.TestCase):
    def test_market_closed_snapshot_with_separate_clocks(self):
        provider, manager = provider_with([(200, csv_text(standard_chain()))])
        service, _ = service_for(provider)
        payload = service.read("AAPL-ID", universe=US_EQUITIES)
        self.assertEqual(payload["schema_version"], "screener-options/1.0.0")
        self.assertEqual((payload["state"], payload["reason"]), ("MARKET_CLOSED", "OPTIONS_MARKET_CLOSED"))
        self.assertEqual(payload["provider"], {"id": "options.finviz.elite_export", "label": "Finviz Elite", "delivery": "SNAPSHOT"})
        self.assertIsNone(payload["clock"]["provider_as_of"])
        self.assertEqual(payload["clock"]["latest_contract_trade_at"], "2026-09-25T19:59:59Z")
        self.assertEqual(payload["underlying"], {"price": 251.2, "source": "FINVIZ_ELITE", "state": "SNAPSHOT",
                                                 "as_of": "2026-09-27T15:00:00Z"})
        self.assertEqual(payload["selected_expiration"], "2026-10-02")
        self.assertEqual([item["expiration"] for item in payload["expirations"]], ["2026-10-02", "2026-10-16"])
        self.assertEqual(len(payload["contracts"]), 6)
        self.assertEqual(payload["completeness"]["expired_excluded"], 1)
        self.assertEqual(payload["capability"]["OPTIONS_UNIVERSE_QUERY"], "NOT_SUPPORTED")
        self.assertEqual(payload["capability"]["OPTIONS_EXECUTION_DATA"], "NOT_AUTHORIZED")
        self.assertEqual(len(manager.calls), 1)

    def test_current_snapshot_during_regular_session_and_live_underlying_clock(self):
        provider, _ = provider_with([(200, csv_text(standard_chain()))], now=MONDAY)
        quote = lambda instrument, universe: {"state": "LIVE", "fields": {"price": {"value": 252.4, "source": "MOOMOO", "as_of_ns": 1_790_000_000_000_000_000}}}
        service, _ = service_for(provider, clock=Clock(MONDAY), session="REGULAR", quote=quote)
        payload = service.read("AAPL-ID", universe=US_EQUITIES)
        self.assertEqual((payload["state"], payload["reason"]), ("CURRENT_SNAPSHOT", None))
        self.assertEqual((payload["underlying"]["price"], payload["underlying"]["state"]), (252.4, "LIVE"))
        self.assertNotEqual(payload["underlying"]["as_of"], payload["clock"]["fetched_at"])

    def test_expiration_selection_and_summary_view(self):
        provider, manager = provider_with([(200, csv_text(standard_chain()))])
        service, _ = service_for(provider)
        chosen = service.read("AAPL-ID", universe=US_EQUITIES, expiration="2026-10-16")
        self.assertEqual((chosen["selected_expiration"], len(chosen["contracts"])), ("2026-10-16", 2))
        self.assertEqual(chosen["expiry_summary"]["contracts"], 2)
        fallback = service.read("AAPL-ID", universe=US_EQUITIES, expiration="2026-09-25")
        self.assertEqual(fallback["selected_expiration"], "2026-10-02")  # never an expired default
        summary = service.read("AAPL-ID", universe=US_EQUITIES, view="summary")
        self.assertEqual((summary["contracts"], summary["expiry_summary"]), ([], None))
        self.assertEqual(summary["summary"]["call_volume"], 1050)
        self.assertEqual(len(manager.calls), 1)  # expiry switches and the Preview summary share one fetch
        with self.assertRaisesRegex(ValueError, "INVALID_OPTIONS_VIEW"):
            service.read("AAPL-ID", universe=US_EQUITIES, view="universe")

    def test_not_configured_not_entitled_unavailable_and_no_chain(self):
        cases = [(provider_with([(200, "")], api_key=None)[0], "NOT_CONFIGURED", "PROVIDER_NOT_CONFIGURED"),
                 (provider_with([(403, "")])[0], "NOT_ENTITLED", "FINVIZ_OPTIONS_AUTH_REJECTED"),
                 (provider_with([(502, "")])[0], "PROVIDER_UNAVAILABLE", "FINVIZ_OPTIONS_HTTP_ERROR"),
                 (provider_with([(200, csv_text([]))])[0], "NO_CHAIN", "NO_CURRENT_CONTRACTS"),
                 (provider_with([(200, csv_text([contract(expiry="9/25/2026")]))])[0], "NO_CHAIN", "ONLY_EXPIRED_CONTRACTS")]
        for provider, state, reason in cases:
            payload = service_for(provider)[0].read("AAPL-ID", universe=US_EQUITIES)
            self.assertEqual((payload["state"], payload["reason"]), (state, reason))
            self.assertEqual((payload["contracts"], payload["summary"]), ([], None))

    def test_incomplete_chain_is_reported(self):
        provider, _ = provider_with([(200, csv_text(standard_chain() + [contract(strike="bad")]))])
        payload = service_for(provider)[0].read("AAPL-ID", universe=US_EQUITIES)
        self.assertEqual((payload["completeness"]["usable"], payload["completeness"]["dropped"]), (8, 1))
        self.assertIn("OPTION_CHAIN_INCOMPLETE", payload["quality_flags"])

    def test_refresh_ttl_last_good_stale_and_expiry(self):
        provider, manager = provider_with([(200, csv_text(standard_chain())), (502, "")])
        service, clock = service_for(provider)
        service.read("AAPL-ID", universe=US_EQUITIES)
        clock.now += REFRESH_AFTER_S - 1
        self.assertEqual(service.read("AAPL-ID", universe=US_EQUITIES)["state"], "MARKET_CLOSED")
        self.assertEqual(len(manager.calls), 1)
        clock.now += 2
        stale = service.read("AAPL-ID", universe=US_EQUITIES)
        self.assertEqual((stale["state"], stale["reason"]), ("STALE", "FINVIZ_OPTIONS_HTTP_ERROR"))
        self.assertIn("OPTION_CHAIN_STALE", stale["quality_flags"])
        self.assertEqual(len(manager.calls), 2)
        clock.now += LAST_GOOD_MAX_AGE_S
        gone = service.read("AAPL-ID", universe=US_EQUITIES)
        self.assertEqual((gone["state"], gone["contracts"]), ("PROVIDER_UNAVAILABLE", []))
        self.assertGreater(LAST_GOOD_MAX_AGE_S, STALE_AFTER_S)

    def test_old_snapshot_is_stale_even_from_provider_cache(self):
        class Aged:
            provider_id, delivery = "options.finviz.elite_export", "SNAPSHOT"

            def fetch_chain(self, symbol, **_):
                inner, _ = provider_with([(200, csv_text(standard_chain()))])
                result = inner.fetch_chain(symbol)
                result.details["fetched_time_ns"] = int((SUNDAY.timestamp() - STALE_AFTER_S - 5) * 1e9)
                return result
        payload = service_for(Aged())[0].read("AAPL-ID", universe=US_EQUITIES)
        self.assertEqual((payload["state"], payload["reason"]), ("STALE", "SNAPSHOT_AGE_EXCEEDED"))

    def test_cache_is_bounded_and_keyed_by_underlying(self):
        requested: list[str] = []

        class Recording:
            provider_id, delivery = "options.finviz.elite_export", "SNAPSHOT"

            def fetch_chain(self, symbol, **_):
                requested.append(symbol)
                rows = [contract(symbol=symbol), contract(symbol=symbol, kind="put")]
                return provider_with([(200, csv_text(rows))])[0].fetch_chain(symbol)
        service, _ = service_for(Recording(), max_entries=2)
        aapl = service.read("AAPL-ID", universe=US_EQUITIES)
        nvda = service.read("NVDA-ID", universe=US_EQUITIES)
        self.assertTrue(all(row["option_id"].startswith("AAPL") for row in aapl["contracts"]))
        self.assertTrue(all(row["option_id"].startswith("NVDA") for row in nvda["contracts"]))
        service.read("SPY-ID", universe=US_ETFS)
        self.assertEqual(service.cached_underlyings(), ["NVDA", "SPY"])
        service.read("AAPL-ID", universe=US_EQUITIES)
        self.assertEqual(requested, ["AAPL", "NVDA", "SPY", "AAPL"])
        self.assertIsNone(service.read("MISSING", universe=US_EQUITIES))

    def test_fixture_provider_is_never_used(self):
        service, _ = service_for(FixtureOptionChainProvider())
        payload = service.read("NVDA-ID", universe=US_EQUITIES)
        self.assertEqual((payload["state"], payload["reason"], payload["contracts"]), ("UNAVAILABLE", "NON_CURRENT_PROVIDER_REFUSED", []))
        previous = get_provider_composition()
        try:
            # Research paths may register the fixture chain; the Screener's source does not change.
            composition = configure_fixture_provider_composition()
            self.assertEqual(composition.option_chain.provider_id, "options.fixture.chain")
            self.assertEqual(current_option_chain_provider().provider_id, "options.finviz.elite_export")
            self.assertEqual(ScreenerOptionsService()._provider_getter().provider_id, "options.finviz.elite_export")
            self.assertEqual(ProviderComposition().option_chain.provider_id, "stub.option_chain.unconfigured")
        finally:
            configure_provider_composition(previous)

    def test_payload_passes_secret_leak_audit(self):
        provider, _ = provider_with([(200, csv_text(standard_chain()))])
        payload = service_for(provider)[0].read("AAPL-ID", universe=US_EQUITIES)
        assert_no_secrets_in_payload(payload, context="screener options")
        rendered = json.dumps(payload, allow_nan=False)
        for forbidden in (API_KEY, "auth=", "elite.finviz.com", "token"):
            self.assertNotIn(forbidden, rendered)


class ScopeTests(unittest.TestCase):
    def test_capability_matrix(self):
        self.assertIn("options", universe_spec(US_EQUITIES).panels)
        self.assertIn("options", universe_spec(US_ETFS).panels)
        self.assertNotIn("options", universe_spec(FUTURES).panels)
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_UNIVERSE"):
            universe_spec("OPTIONS")

    def test_no_options_filters_sorts_or_columns(self):
        words = ("call", "put", "iv", "implied", "option", "open_interest_ratio", "greek")
        for universe in (US_EQUITIES, US_ETFS):
            fields = {item["field"] for item in filter_catalog(universe)} | set(universe_spec(universe).columns)
            self.assertFalse([field for field in fields if any(word in field for word in words)], universe)

    def test_layout_accepts_one_options_panel(self):
        layout = validate_panel_layout({"version": 1, "open_panels": ["charts", "options"], "active_panel": "options",
                                        "dock_height": 300, "dockview_layout": None})
        self.assertEqual(layout["open_panels"], ["charts", "options"])
        with self.assertRaises(ValueError):
            validate_panel_layout({"version": 1, "open_panels": ["options", "options"], "active_panel": None,
                                   "dock_height": 300, "dockview_layout": None})

    def test_etf_underlying_uses_only_an_already_retained_snapshot(self):
        from market_platform_foundation.ui_api.screener_multi import MultiUniverseScreener

        service = MultiUniverseScreener(transport_getter=lambda: None)
        self.assertIsNone(service.latest_snapshot_id(US_ETFS))  # nothing is built for options
        self.assertIsNone(service.latest_snapshot_id(US_EQUITIES))

    def test_route_is_read_scoped(self):
        self.assertEqual(policy_for_route("GET", "/screener/options").capability, "state.read")


if __name__ == "__main__":
    unittest.main()

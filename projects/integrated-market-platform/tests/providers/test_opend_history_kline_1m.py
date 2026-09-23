"""Item 9 OpenD 1m history-kline window: oldest-page vs session-day.

Vendor ``request_history_kline(start=None, end=None, max_count=N)`` normalizes
to ``[today-365d, today]`` and returns the **oldest** N rows (moomoo-api
``normalize_start_end_date(..., 365)``). Lawful captured evidence:
``evidence/market_data/moomoo/capability-report.json`` probed 2026-09-15 UTC
with ``K_DAY`` ``max_count=5`` and sampled ``time_key`` ``2025-09-15 00:00:00``.

These tests replay that oldest-first contract with a fake SDK. ``K_DAY``
oldest-first is captured; ``K_1M`` paging is hypothesized, not live-sampled.
They are not empirical OpenD ticks and do not loosen PIT.
"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from unittest import mock

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "src"))

from market_platform_foundation.paper.calibration.bar_ohlcv_prospective_proof import (  # noqa: E402
    REASON_NO_POST_SIGNAL_BAR,
    run_prospective_proof,
)
from market_platform_foundation.paper.calibration.bar_ohlcv_sources import (  # noqa: E402
    US_EQUITY_BAR_TZ,
    first_admissible_post_signal_bar,
    load_moomoo_opend_kline_bars,
    normalize_moomoo_kline_row,
)

COLLECTION_ROOT = _ROOT.parent
SESSION_DAY = "2026-09-15"
YEAR_AGO_DAY = "2025-09-15"
# 09:34:30.709 ET — poll #1 signal clock (wall ns).
SIGNAL_NS = int(
    datetime(2026, 9, 15, 9, 34, 30, 709000, tzinfo=US_EQUITY_BAR_TZ).timestamp() * 1_000_000_000
)
# 10:39:31 ET — poll #1 observation at timeout, after many completed 1m bars.
OBSERVATION_NS = int(
    datetime(2026, 9, 15, 10, 39, 31, tzinfo=US_EQUITY_BAR_TZ).timestamp() * 1_000_000_000
)


def _kline_row(time_key: str) -> dict[str, Any]:
    return {
        "code": "US.AAPL",
        "time_key": time_key,
        "open": 230.0,
        "high": 231.0,
        "low": 229.0,
        "close": 230.5,
        "volume": 1000,
    }


def _vendor_normalize_window(start: str | None, end: str | None, *, today: str) -> tuple[str, str]:
    """Mirror moomoo-api ``normalize_start_end_date(start, end, 365)`` date half."""

    today_dt = datetime.strptime(today, "%Y-%m-%d")
    if not start and not end:
        return (today_dt - timedelta(days=365)).strftime("%Y-%m-%d"), today
    if start and not end:
        return start[:10], (datetime.strptime(start[:10], "%Y-%m-%d") + timedelta(days=365)).strftime(
            "%Y-%m-%d"
        )
    if end and not start:
        return (datetime.strptime(end[:10], "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d"), end[:10]
    return str(start)[:10], str(end)[:10]


class _OldestFirstKlineContext:
    """Fake OpenD quote context: history kline is oldest-first inside [start, end]."""

    def __init__(self, catalog: list[dict[str, Any]], *, today: str = SESSION_DAY) -> None:
        self.catalog = catalog
        self.today = today
        self.closed = False
        self.calls: list[dict[str, Any]] = []

    def get_global_state(self) -> tuple[int, dict[str, Any]]:
        return 0, {"qot_logined": True}

    def request_history_kline(
        self,
        code: str,
        start: str | None = None,
        end: str | None = None,
        ktype: str | None = None,
        autype: str | None = None,
        max_count: int = 120,
        extended_time: bool = False,
        session: str | None = None,
    ) -> tuple[int, list[dict[str, Any]], None]:
        window_start, window_end = _vendor_normalize_window(start, end, today=self.today)
        self.calls.append(
            {
                "code": code,
                "start": start,
                "end": end,
                "window_start": window_start,
                "window_end": window_end,
                "ktype": ktype,
                "max_count": max_count,
                "extended_time": extended_time,
                "session": session,
            }
        )
        matched: list[dict[str, Any]] = []
        for row in sorted(self.catalog, key=lambda item: str(item["time_key"])):
            day = str(row["time_key"])[:10]
            if window_start <= day <= window_end:
                matched.append(row)
            if len(matched) >= int(max_count):
                break
        return 0, matched, None

    def close(self) -> None:
        self.closed = True


class _ProtocolErrorKlineContext:
    def __init__(self, message: str = "freq limit: too many history kline requests") -> None:
        self.message = message
        self.closed = False

    def get_global_state(self) -> tuple[int, dict[str, Any]]:
        return 0, {"qot_logined": True}

    def request_history_kline(self, *_args: Any, **_kwargs: Any) -> tuple[int, str, None]:
        return -1, self.message, None

    def close(self) -> None:
        self.closed = True


class _FakeKlineSdk:
    RET_OK = 0

    class KLType:
        K_1M = "K_1M"

    class AuType:
        QFQ = "QFQ"

    class Session:
        ALL = "ALL"
        NONE = "NONE"

    def __init__(self, context: _OldestFirstKlineContext) -> None:
        self._context = context
        self.OpenQuoteContext = lambda **_kwargs: context


def _minute_rows(day: str, *, hour: int, minute: int, count: int) -> list[dict[str, Any]]:
    start = datetime.strptime(f"{day} {hour:02d}:{minute:02d}:00", "%Y-%m-%d %H:%M:%S")
    rows: list[dict[str, Any]] = []
    for offset in range(count):
        stamp = start + timedelta(minutes=offset)
        rows.append(_kline_row(stamp.strftime("%Y-%m-%d %H:%M:%S")))
    return rows


def _catalog() -> list[dict[str, Any]]:
    # 120 oldest 1m bars fill max_count when the window is [today-365d, today].
    return _minute_rows(YEAR_AGO_DAY, hour=9, minute=30, count=120) + [
        _kline_row(f"{SESSION_DAY} 09:30:00"),
        _kline_row(f"{SESSION_DAY} 09:35:00"),
        _kline_row(f"{SESSION_DAY} 09:36:00"),
        _kline_row(f"{SESSION_DAY} 10:38:00"),
    ]


class OpenDHistoryKline1mWindowTests(unittest.TestCase):
    def test_session_day_window_returns_today_1m_not_365d_oldest_page(self) -> None:
        from tools.moomoo.opend_quote_transport import fetch_history_kline_1m

        ctx = _OldestFirstKlineContext(_catalog())
        payload = fetch_history_kline_1m(
            "AAPL",
            host="127.0.0.1",
            port=11111,
            max_count=120,
            sdk=_FakeKlineSdk(ctx),
            session_date=SESSION_DAY,
        )
        self.assertIsNone(payload["reason_code"])
        rows = payload["rows"] or []
        keys = [str(row["time_key"]) for row in rows]
        self.assertTrue(keys, "expected 1m rows from the observation session")
        self.assertTrue(any(key.startswith(SESSION_DAY) for key in keys))
        self.assertFalse(any(key.startswith(YEAR_AGO_DAY) for key in keys))
        self.assertEqual(len(ctx.calls), 1)
        call = ctx.calls[0]
        self.assertEqual(call["start"], SESSION_DAY)
        self.assertEqual(call["end"], SESSION_DAY)
        self.assertGreaterEqual(int(call["max_count"]), 390)
        self.assertTrue(ctx.closed)

    def test_none_none_window_replays_captured_oldest_page_and_fails_pit(self) -> None:
        """Year-old page is one lawful fail-closed path; not the only poll #1 explanation."""

        ctx = _OldestFirstKlineContext(_catalog())
        k_ret, data, _page = ctx.request_history_kline(
            "US.AAPL",
            start=None,
            end=None,
            ktype="K_1M",
            max_count=120,
        )
        self.assertEqual(k_ret, 0)
        keys = [str(row["time_key"]) for row in data]
        self.assertTrue(all(key.startswith(YEAR_AGO_DAY) for key in keys))
        self.assertEqual(keys[0], f"{YEAR_AGO_DAY} 09:30:00")

        fetched_at = OBSERVATION_NS
        canonical = [
            row
            for raw in data
            if (row := normalize_moomoo_kline_row(raw, instrument_id="AAPL", fetched_at_ns=fetched_at))
            is not None
        ]
        self.assertTrue(canonical)
        self.assertIsNone(first_admissible_post_signal_bar(canonical, signal_time_ns=SIGNAL_NS))

        outcome = run_prospective_proof(
            instrument_id="AAPL",
            collection_root=COLLECTION_ROOT,
            env={},
            signal_time_ns=SIGNAL_NS,
            signal_established_at_ns=SIGNAL_NS,
            observation_time_ns=OBSERVATION_NS,
            kline_rows=tuple(data),
            runtime_git_sha="diagnosis-test",
        )
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["reason_code"], REASON_NO_POST_SIGNAL_BAR)
        self.assertIsNone(outcome["receipt"])
        fetch = outcome["kline_fetch"]
        self.assertEqual(int(fetch["raw_row_count"]), 120)
        self.assertTrue(str(fetch["first_raw_time_key"]).startswith(YEAR_AGO_DAY))
        self.assertTrue(str(fetch["last_raw_time_key"]).startswith(YEAR_AGO_DAY))

    def test_session_day_max_count_120_oldest_first_misses_rth_after_premarket(self) -> None:
        """Even with today's date, 120 oldest-first bars are 04:00–05:59, all before 09:34."""

        catalog = _minute_rows(SESSION_DAY, hour=4, minute=0, count=330) + [
            _kline_row(f"{SESSION_DAY} 09:30:00"),
            _kline_row(f"{SESSION_DAY} 09:35:00"),
        ]
        ctx = _OldestFirstKlineContext(catalog)
        k_ret, data, _page = ctx.request_history_kline(
            "US.AAPL",
            start=SESSION_DAY,
            end=SESSION_DAY,
            ktype="K_1M",
            max_count=120,
            extended_time=True,
            session="ALL",
        )
        self.assertEqual(k_ret, 0)
        keys = [str(row["time_key"]) for row in data]
        self.assertEqual(len(keys), 120)
        self.assertEqual(keys[0], f"{SESSION_DAY} 04:00:00")
        self.assertEqual(keys[-1], f"{SESSION_DAY} 05:59:00")
        self.assertFalse(any("09:3" in key for key in keys))

        outcome = run_prospective_proof(
            instrument_id="AAPL",
            collection_root=COLLECTION_ROOT,
            env={},
            signal_time_ns=SIGNAL_NS,
            signal_established_at_ns=SIGNAL_NS,
            observation_time_ns=OBSERVATION_NS,
            kline_rows=tuple(data),
            runtime_git_sha="diagnosis-test",
        )
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["reason_code"], REASON_NO_POST_SIGNAL_BAR)
        self.assertIsNone(outcome["receipt"])
        fetch = outcome["kline_fetch"]
        self.assertEqual(int(fetch["raw_row_count"]), 120)
        self.assertEqual(fetch["first_raw_time_key"], f"{SESSION_DAY} 04:00:00")
        self.assertEqual(fetch["last_raw_time_key"], f"{SESSION_DAY} 05:59:00")

    def test_kline_fetch_surfaces_vendor_ret_msg_on_protocol_error(self) -> None:
        from tools.moomoo.opend_quote_transport import fetch_history_kline_1m

        ctx = _ProtocolErrorKlineContext("freq limit: too many history kline requests")
        payload = fetch_history_kline_1m(
            "AAPL",
            host="127.0.0.1",
            port=11111,
            sdk=_FakeKlineSdk(ctx),
            session_date=SESSION_DAY,
        )
        self.assertEqual(payload["reason_code"], "MOOMOO_PROTOCOL_ERROR")
        self.assertIsNone(payload["rows"])
        self.assertEqual(payload["vendor_ret"], -1)
        self.assertEqual(payload["vendor_ret_msg"], "freq limit: too many history kline requests")
        self.assertEqual(payload["raw_row_count"], 0)
        self.assertTrue(ctx.closed)

    def test_kline_fetch_logs_row_count_and_time_keys_on_success(self) -> None:
        from tools.moomoo.opend_quote_transport import fetch_history_kline_1m

        ctx = _OldestFirstKlineContext(_catalog())
        payload = fetch_history_kline_1m(
            "AAPL",
            host="127.0.0.1",
            port=11111,
            sdk=_FakeKlineSdk(ctx),
            session_date=SESSION_DAY,
        )
        self.assertIsNone(payload["reason_code"])
        self.assertGreater(int(payload["raw_row_count"]), 0)
        self.assertIsNotNone(payload["first_raw_time_key"])
        self.assertIsNotNone(payload["last_raw_time_key"])
        self.assertTrue(str(payload["first_raw_time_key"]).startswith(SESSION_DAY))
        self.assertIsNone(payload["vendor_ret_msg"])

    def test_today_rth_rows_are_admissible_without_loosening_pit(self) -> None:
        rows = (
            _kline_row(f"{SESSION_DAY} 09:30:00"),
            _kline_row(f"{SESSION_DAY} 09:35:00"),
        )
        outcome = run_prospective_proof(
            instrument_id="AAPL",
            collection_root=COLLECTION_ROOT,
            env={},
            signal_time_ns=SIGNAL_NS,
            signal_established_at_ns=SIGNAL_NS,
            observation_time_ns=OBSERVATION_NS,
            kline_rows=rows,
            runtime_git_sha="diagnosis-test",
        )
        self.assertTrue(outcome["ok"])
        receipt = outcome["receipt"]
        assert receipt is not None
        self.assertFalse(receipt["calibrated"])
        self.assertFalse(receipt["orders_placed"])
        self.assertGreater(int(receipt["bar_available_time_ns"]), SIGNAL_NS)

    def test_incomplete_in_progress_bar_still_hidden(self) -> None:
        row = _kline_row(f"{SESSION_DAY} 10:39:00")
        mid = SIGNAL_NS  # well before this bar's end
        self.assertIsNone(normalize_moomoo_kline_row(row, instrument_id="AAPL", fetched_at_ns=mid))


class OpenDHistoryKlineLoadWindowTests(unittest.TestCase):
    def test_loader_passes_observation_session_date_into_fetcher(self) -> None:
        captured: dict[str, Any] = {}

        def _fetcher(symbol: str, *, host: str, port: int, max_count: int = 120, **kwargs: Any) -> dict[str, Any]:
            captured["symbol"] = symbol
            captured["host"] = host
            captured["port"] = port
            captured["max_count"] = max_count
            captured["session_date"] = kwargs.get("session_date")
            return {
                "reason_code": None,
                "rows": [_kline_row(f"{SESSION_DAY} 09:35:00")],
            }

        fake_module = type("M", (), {"fetch_history_kline_1m": staticmethod(_fetcher)})()
        with mock.patch(
            "market_platform_foundation.paper.calibration.bar_ohlcv_sources._load_tools_kline_module",
            return_value=fake_module,
        ), mock.patch(
            "market_platform_foundation.paper.calibration.bar_ohlcv_sources.opend_reachable",
            return_value=True,
        ), mock.patch(
            "market_platform_foundation.paper.calibration.bar_ohlcv_sources.opend_is_loopback",
            return_value=True,
        ):
            loaded = load_moomoo_opend_kline_bars(
                instrument_id="AAPL",
                observation_time_ns=OBSERVATION_NS,
                fetched_at_ns=OBSERVATION_NS,
            )
        self.assertTrue(loaded.ok)
        self.assertEqual(captured["session_date"], SESSION_DAY)
        self.assertGreaterEqual(int(captured["max_count"]), 390)
        hit = first_admissible_post_signal_bar(loaded.bars, signal_time_ns=SIGNAL_NS)
        self.assertIsNotNone(hit)

    def test_live_prospective_success_fetches_opend_exactly_once(self) -> None:
        """Gate + dry-run must reuse one kline page (no second live OpenD pull)."""

        fetch_calls: list[int] = [0]
        row = _kline_row(f"{SESSION_DAY} 09:35:00")

        def _fetcher(symbol: str, *, host: str, port: int, max_count: int = 120, **kwargs: Any) -> dict[str, Any]:
            fetch_calls[0] += 1
            return {
                "reason_code": None,
                "rows": [row],
                "raw_row_count": 1,
                "first_raw_time_key": row["time_key"],
                "last_raw_time_key": row["time_key"],
                "vendor_ret": 0,
                "vendor_ret_msg": None,
                "kline_start": SESSION_DAY,
                "kline_end": SESSION_DAY,
                "max_count_requested": max_count,
                "connection_host": host,
                "connection_port": port,
                "request_duration_ms": 1.0,
            }

        outcome = self._proof_with_fetcher(_fetcher)
        self.assertTrue(outcome["ok"])
        self.assertEqual(fetch_calls[0], 1)
        receipt = outcome["receipt"]
        assert receipt is not None
        self.assertFalse(receipt["orders_placed"])
        self.assertFalse(receipt["calibrated"])
        self.assertEqual(receipt["item9_status"], "PARTIAL_NOT_CALIBRATED")
        self.assertEqual(int(outcome["kline_fetch"]["raw_row_count"]), 1)
        self.assertEqual(outcome["kline_fetch"]["first_raw_time_key"], row["time_key"])
        self.assertEqual(outcome["kline_fetch"]["last_raw_time_key"], row["time_key"])

    def _patched_live_load(self, fetcher: Any):
        fake_module = type("M", (), {"fetch_history_kline_1m": staticmethod(fetcher)})()
        return mock.patch(
            "market_platform_foundation.paper.calibration.bar_ohlcv_sources._load_tools_kline_module",
            return_value=fake_module,
        ), mock.patch(
            "market_platform_foundation.paper.calibration.bar_ohlcv_sources.opend_reachable",
            return_value=True,
        ), mock.patch(
            "market_platform_foundation.paper.calibration.bar_ohlcv_sources.opend_is_loopback",
            return_value=True,
        )

    def _transport_fetcher(self, sdk: Any):
        from tools.moomoo.opend_quote_transport import fetch_history_kline_1m

        def _fetcher(symbol: str, *, host: str, port: int, max_count: int = 120, **kwargs: Any) -> dict[str, Any]:
            return fetch_history_kline_1m(
                symbol,
                host=host,
                port=port,
                max_count=max_count,
                sdk=sdk,
                session_date=kwargs.get("session_date") or SESSION_DAY,
            )

        return _fetcher

    def _load_with_fetcher(self, fetcher: Any) -> Any:
        load_patch, reach_patch, loop_patch = self._patched_live_load(fetcher)
        with load_patch, reach_patch, loop_patch:
            return load_moomoo_opend_kline_bars(
                instrument_id="AAPL",
                observation_time_ns=OBSERVATION_NS,
                fetched_at_ns=OBSERVATION_NS,
            )

    def _proof_with_fetcher(self, fetcher: Any) -> dict[str, Any]:
        load_patch, reach_patch, loop_patch = self._patched_live_load(fetcher)
        with load_patch, reach_patch, loop_patch:
            return run_prospective_proof(
                instrument_id="AAPL",
                collection_root=COLLECTION_ROOT,
                env={},
                signal_time_ns=SIGNAL_NS,
                signal_established_at_ns=SIGNAL_NS,
                observation_time_ns=OBSERVATION_NS,
                kline_rows=None,
                runtime_git_sha="diagnosis-test",
            )

    def test_empty_ret_ok_page_is_contract_mismatch_not_a_bar(self) -> None:
        from tools.moomoo.opend_quote_transport import fetch_history_kline_1m

        ctx = _OldestFirstKlineContext([])
        payload = fetch_history_kline_1m(
            "AAPL",
            host="127.0.0.1",
            port=11111,
            sdk=_FakeKlineSdk(ctx),
            session_date=SESSION_DAY,
        )
        self.assertIsNone(payload["reason_code"])
        self.assertEqual(payload["rows"], [])
        self.assertEqual(int(payload["raw_row_count"]), 0)
        self.assertIsNone(payload["first_raw_time_key"])
        self.assertIsNone(payload["last_raw_time_key"])
        self.assertEqual(payload["vendor_ret"], 0)
        self.assertIsNone(payload["vendor_ret_msg"])
        self.assertTrue(ctx.closed)

        fetcher = self._transport_fetcher(_FakeKlineSdk(_OldestFirstKlineContext([])))
        loaded = self._load_with_fetcher(fetcher)
        self.assertFalse(loaded.ok)
        self.assertEqual(loaded.reason_code, "EXPERIMENT_CONTRACT_MISMATCH")
        self.assertEqual(int(loaded.provenance["raw_row_count"]), 0)
        self.assertIsNone(loaded.provenance["first_raw_time_key"])
        self.assertEqual(len(loaded.bars), 0)

        outcome = self._proof_with_fetcher(self._transport_fetcher(_FakeKlineSdk(_OldestFirstKlineContext([]))))
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["reason_code"], "EXPERIMENT_CONTRACT_MISMATCH")
        self.assertIsNone(outcome["receipt"])
        self.assertEqual(int(outcome["kline_fetch"]["raw_row_count"]), 0)

    def test_loader_ret_error_is_moomoo_protocol_error(self) -> None:
        ctx = _ProtocolErrorKlineContext("RET_ERROR: no right to get the historical K-line")
        fetcher = self._transport_fetcher(_FakeKlineSdk(ctx))
        loaded = self._load_with_fetcher(fetcher)
        self.assertFalse(loaded.ok)
        self.assertEqual(loaded.reason_code, "MOOMOO_PROTOCOL_ERROR")
        self.assertEqual(
            loaded.provenance["vendor_ret_msg"],
            "RET_ERROR: no right to get the historical K-line",
        )
        self.assertEqual(loaded.provenance["vendor_ret"], -1)
        self.assertEqual(int(loaded.provenance["raw_row_count"]), 0)

        outcome = self._proof_with_fetcher(
            self._transport_fetcher(
                _FakeKlineSdk(_ProtocolErrorKlineContext("RET_ERROR: no right to get the historical K-line"))
            )
        )
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["reason_code"], "MOOMOO_PROTOCOL_ERROR")
        self.assertIsNone(outcome["receipt"])
        self.assertEqual(
            outcome["kline_fetch"]["vendor_ret_msg"],
            "RET_ERROR: no right to get the historical K-line",
        )

    def test_year_old_page_loads_but_pit_still_rejects(self) -> None:
        rows = tuple(_minute_rows(YEAR_AGO_DAY, hour=9, minute=30, count=5))
        loaded = load_moomoo_opend_kline_bars(
            instrument_id="AAPL",
            observation_time_ns=OBSERVATION_NS,
            fetched_at_ns=OBSERVATION_NS,
            kline_rows=rows,
        )
        self.assertTrue(loaded.ok)
        self.assertEqual(len(loaded.bars), 5)
        self.assertIsNone(first_admissible_post_signal_bar(loaded.bars, signal_time_ns=SIGNAL_NS))

        outcome = run_prospective_proof(
            instrument_id="AAPL",
            collection_root=COLLECTION_ROOT,
            env={},
            signal_time_ns=SIGNAL_NS,
            signal_established_at_ns=SIGNAL_NS,
            observation_time_ns=OBSERVATION_NS,
            kline_rows=rows,
            runtime_git_sha="diagnosis-test",
        )
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["reason_code"], REASON_NO_POST_SIGNAL_BAR)
        self.assertIsNone(outcome["receipt"])
        self.assertEqual(int(outcome["kline_fetch"]["raw_row_count"]), 5)
        self.assertTrue(str(outcome["kline_fetch"]["first_raw_time_key"]).startswith(YEAR_AGO_DAY))

    def test_incomplete_current_bar_hidden_by_loader(self) -> None:
        row = _kline_row(f"{SESSION_DAY} 10:39:00")
        mid_bar_ns = int(
            datetime(2026, 9, 15, 10, 39, 30, tzinfo=US_EQUITY_BAR_TZ).timestamp() * 1_000_000_000
        )
        loaded = load_moomoo_opend_kline_bars(
            instrument_id="AAPL",
            observation_time_ns=mid_bar_ns,
            fetched_at_ns=mid_bar_ns,
            kline_rows=(row,),
        )
        self.assertFalse(loaded.ok)
        self.assertEqual(loaded.reason_code, "EXPERIMENT_CONTRACT_MISMATCH")
        self.assertEqual(int(loaded.provenance["raw_row_count"]), 1)
        self.assertEqual(loaded.provenance["first_raw_time_key"], f"{SESSION_DAY} 10:39:00")
        self.assertEqual(len(loaded.bars), 0)

        outcome = run_prospective_proof(
            instrument_id="AAPL",
            collection_root=COLLECTION_ROOT,
            env={},
            signal_time_ns=SIGNAL_NS,
            signal_established_at_ns=SIGNAL_NS,
            observation_time_ns=mid_bar_ns,
            kline_rows=(row,),
            runtime_git_sha="diagnosis-test",
        )
        self.assertFalse(outcome["ok"])
        self.assertEqual(outcome["reason_code"], "EXPERIMENT_CONTRACT_MISMATCH")
        self.assertIsNone(outcome["receipt"])
        self.assertEqual(int(outcome["kline_fetch"]["raw_row_count"]), 1)


def _counting_kline_sdk(context: Any) -> tuple[Any, list[int]]:
    open_calls: list[int] = [0]

    class _Sdk:
        RET_OK = 0

        class KLType:
            K_1M = "K_1M"

        class AuType:
            QFQ = "QFQ"

        class Session:
            ALL = "ALL"

        @staticmethod
        def OpenQuoteContext(**_kwargs: Any) -> Any:
            open_calls[0] += 1
            return context

    return _Sdk(), open_calls


class OpenDQuoteKlineSessionTests(unittest.TestCase):
    def test_persistent_session_reuses_one_connect(self) -> None:
        from tools.moomoo.opend_quote_transport import OpendQuoteKlineSession

        ctx = _OldestFirstKlineContext(_catalog())
        sdk, open_calls = _counting_kline_sdk(ctx)
        session = OpendQuoteKlineSession(host="127.0.0.1", port=11111, sdk=sdk)
        for _ in range(3):
            payload = session.fetch_history_kline_1m("AAPL", session_date=SESSION_DAY)
            self.assertIsNone(payload["reason_code"])
        self.assertEqual(open_calls[0], 1)
        self.assertFalse(ctx.closed)
        session.close()
        self.assertTrue(ctx.closed)

    def test_ephemeral_fetch_closes_after_single_call(self) -> None:
        from tools.moomoo.opend_quote_transport import fetch_history_kline_1m

        ctx = _OldestFirstKlineContext(_catalog())
        sdk, open_calls = _counting_kline_sdk(ctx)
        fetch_history_kline_1m(
            "AAPL",
            host="127.0.0.1",
            port=11111,
            sdk=sdk,
            session_date=SESSION_DAY,
        )
        self.assertEqual(open_calls[0], 1)
        self.assertTrue(ctx.closed)

    def test_session_invalidates_on_disconnect_exception_path(self) -> None:
        from tools.moomoo.opend_quote_transport import OpendQuoteKlineSession

        class _FlakyContext(_OldestFirstKlineContext):
            def __init__(self, catalog: list[dict[str, Any]]) -> None:
                super().__init__(catalog)
                self.fail_once = True

            def request_history_kline(self, *args: Any, **kwargs: Any) -> tuple[int, Any, None]:
                if self.fail_once:
                    self.fail_once = False
                    raise ConnectionError("disconnect from peer")
                return super().request_history_kline(*args, **kwargs)

        ctx = _FlakyContext(_catalog())
        sdk, open_calls = _counting_kline_sdk(ctx)
        session = OpendQuoteKlineSession(host="127.0.0.1", port=11111, sdk=sdk)
        first = session.fetch_history_kline_1m("AAPL", session_date=SESSION_DAY)
        self.assertEqual(first["reason_code"], "MOOMOO_PROTOCOL_ERROR")
        second = session.fetch_history_kline_1m("AAPL", session_date=SESSION_DAY)
        self.assertIsNone(second["reason_code"])
        self.assertEqual(open_calls[0], 2)
        session.close()


class OpenDHistoryKlineExtendedDiagnosticsTests(unittest.TestCase):
    def test_success_payload_includes_timing_connection_and_window(self) -> None:
        from tools.moomoo.opend_quote_transport import fetch_history_kline_1m

        ctx = _OldestFirstKlineContext(_catalog())
        payload = fetch_history_kline_1m(
            "AAPL",
            host="127.0.0.1",
            port=11111,
            sdk=_FakeKlineSdk(ctx),
            session_date=SESSION_DAY,
        )
        self.assertIsNone(payload["reason_code"])
        self.assertEqual(payload["connection_host"], "127.0.0.1")
        self.assertEqual(payload["connection_port"], 11111)
        self.assertEqual(payload["kline_start"], SESSION_DAY)
        self.assertEqual(payload["kline_end"], SESSION_DAY)
        self.assertGreaterEqual(int(payload["max_count_requested"]), 1000)
        self.assertIsNotNone(payload["request_duration_ms"])
        self.assertGreaterEqual(float(payload["request_duration_ms"]), 0.0)
        self.assertNotIn("request_retry_index", payload)
        self.assertIsNone(payload["protocol_error_category"])

    def test_protocol_error_category_frequency_limit(self) -> None:
        from tools.moomoo.opend_quote_transport import (
            classify_kline_protocol_error_category,
            fetch_history_kline_1m,
        )

        self.assertEqual(
            classify_kline_protocol_error_category(
                reason_code="MOOMOO_PROTOCOL_ERROR",
                vendor_ret=-1,
                vendor_ret_msg="freq limit: too many history kline requests",
            ),
            "vendor_frequency_limit",
        )
        ctx = _ProtocolErrorKlineContext("freq limit: too many history kline requests")
        payload = fetch_history_kline_1m(
            "AAPL",
            host="127.0.0.1",
            port=11111,
            sdk=_FakeKlineSdk(ctx),
            session_date=SESSION_DAY,
        )
        self.assertEqual(payload["protocol_error_category"], "vendor_frequency_limit")
        self.assertIsNotNone(payload["request_duration_ms"])

    def test_unmatched_protocol_error_is_unclassified_not_exception(self) -> None:
        from tools.moomoo.opend_quote_transport import (
            KLINE_PROTOCOL_UNCLASSIFIED,
            classify_kline_protocol_error_category,
            fetch_history_kline_1m,
        )

        self.assertEqual(
            classify_kline_protocol_error_category(
                reason_code="MOOMOO_PROTOCOL_ERROR",
                vendor_ret=0,
                vendor_ret_msg=None,
            ),
            KLINE_PROTOCOL_UNCLASSIFIED,
        )
        incomplete_sdk = type(
            "IncompleteSdk",
            (),
            {
                "OpenQuoteContext": _ProtocolErrorKlineContext,
                "KLType": _FakeKlineSdk.KLType,
            },
        )()
        payload = fetch_history_kline_1m(
            "AAPL",
            host="127.0.0.1",
            port=11111,
            sdk=incomplete_sdk,
            session_date=SESSION_DAY,
        )
        self.assertEqual(payload["reason_code"], "MOOMOO_PROTOCOL_ERROR")
        self.assertEqual(payload["protocol_error_category"], KLINE_PROTOCOL_UNCLASSIFIED)

    def test_loader_attaches_extended_diagnostics_from_payload(self) -> None:
        def _fetcher(symbol: str, *, host: str, port: int, max_count: int = 120, **kwargs: Any) -> dict[str, Any]:
            return {
                "reason_code": "MOOMOO_PROTOCOL_ERROR",
                "raw_row_count": 0,
                "vendor_ret": -1,
                "vendor_ret_msg": "RET_ERROR: no right",
                "connection_host": host,
                "connection_port": port,
                "kline_start": SESSION_DAY,
                "kline_end": SESSION_DAY,
                "max_count_requested": max_count,
                "request_duration_ms": 12.5,
                "protocol_error_category": "vendor_ret_error",
            }

        fake_module = type("M", (), {"fetch_history_kline_1m": staticmethod(_fetcher)})()
        with mock.patch(
            "market_platform_foundation.paper.calibration.bar_ohlcv_sources._load_tools_kline_module",
            return_value=fake_module,
        ), mock.patch(
            "market_platform_foundation.paper.calibration.bar_ohlcv_sources.opend_reachable",
            return_value=True,
        ), mock.patch(
            "market_platform_foundation.paper.calibration.bar_ohlcv_sources.opend_is_loopback",
            return_value=True,
        ):
            loaded = load_moomoo_opend_kline_bars(
                instrument_id="AAPL",
                observation_time_ns=OBSERVATION_NS,
                poll_attempt_index=2,
            )
        self.assertFalse(loaded.ok)
        self.assertEqual(loaded.provenance["poll_attempt_index"], 2)
        self.assertEqual(loaded.provenance["protocol_error_category"], "vendor_ret_error")
        self.assertEqual(float(loaded.provenance["request_duration_ms"]), 12.5)
        self.assertEqual(loaded.provenance["connection_host"], loaded.provenance["host"])

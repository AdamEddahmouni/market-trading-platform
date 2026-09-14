"""Live workspace lanes fail closed; they must not substitute fixture data."""

from __future__ import annotations

import sys
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.market_data.provider_lifecycle import ProviderConnectionState
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.ui_api import live_projections


def _fresh_book(**overrides: object) -> dict:
    book = {
        "asks": [{"price": 190.2, "size": 2}],
        "available_time_ns": 1_000,
        "bids": [{"price": 190.1, "size": 1}],
        "book_state_valid": True,
        "event_time_ns": 900,
        "freshness_status": "FRESH",
        "quality": "PASS",
    }
    book.update(overrides)
    return book


def _runtime(
    *,
    book: dict | None = None,
    trades: list | None = None,
    freshness_ms: int | None = 100,
    connection: ProviderConnectionState = ProviderConnectionState.CONNECTED,
    mark: dict | None = None,
) -> SimpleNamespace:
    depth = SimpleNamespace(account_entitled=True)
    return SimpleNamespace(
        capability_registry=SimpleNamespace(get=lambda _cap: depth),
        lifecycle=SimpleNamespace(connection_state=connection),
        live_mark_for=lambda _symbol: mark,
        state=SimpleNamespace(
            book_for=lambda _symbol: book,
            freshness_ms=lambda _symbol: freshness_ms,
            metrics_report=lambda: {},
            trades_for=lambda _symbol: list(trades or []),
        ),
    )


class LiveOrderBookFailClosedTests(unittest.TestCase):
    def test_stale_book_is_unavailable_without_snapshots(self) -> None:
        runtime = _runtime(book=_fresh_book(quality="STALE", freshness_status="STALE"))
        with mock.patch.object(live_projections, "_runtime_or_none", return_value=runtime):
            payload = live_projections.build_live_order_book_payload("AAPL")
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertFalse(payload["available"])
        self.assertEqual(payload["reason"], "STALE_BOOK")
        self.assertEqual(payload["state"], "STALE")
        self.assertEqual(payload["source"], "LIVE_OBSERVATIONAL")
        self.assertNotIn("snapshots", payload)
        self.assertNotIn("best_bid", payload)

    def test_missing_live_book_does_not_return_none(self) -> None:
        runtime = _runtime(book=None)
        with mock.patch.object(live_projections, "_runtime_or_none", return_value=runtime):
            payload = live_projections.build_live_order_book_payload("AAPL")
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertFalse(payload["available"])
        self.assertEqual(payload["reason"], "NO_LIVE_BOOK")

    def test_stale_live_book_does_not_fall_back_to_fixture(self) -> None:
        runtime = _runtime(book=_fresh_book(quality="STALE", freshness_status="STALE"))
        fixture = mock.Mock(return_value={"available": True, "source": "FIXTURE"})
        with mock.patch.object(live_projections, "_runtime_or_none", return_value=runtime):
            with mock.patch(
                "market_platform_foundation.providers.projections.build_workspace_order_book_payload",
                fixture,
            ):
                payload = live_projections.resolve_workspace_order_book_payload(
                    "AAPL",
                    as_of_context={},
                    prediction_cutoff=0,
                )
        fixture.assert_not_called()
        self.assertFalse(payload["available"])
        self.assertEqual(payload["reason"], "STALE_BOOK")

    def test_live_off_still_uses_fixture_workspace_book(self) -> None:
        fixture = mock.Mock(return_value={"available": True, "source": "FIXTURE"})
        with mock.patch.object(live_projections, "_runtime_or_none", return_value=None):
            with mock.patch(
                "market_platform_foundation.providers.projections.build_workspace_order_book_payload",
                fixture,
            ):
                payload = live_projections.resolve_workspace_order_book_payload(
                    "AAPL",
                    as_of_context={"as_of_time": "t"},
                    prediction_cutoff=1,
                )
        fixture.assert_called_once()
        self.assertEqual(payload["source"], "FIXTURE")

    def test_fresh_book_remains_available(self) -> None:
        runtime = _runtime(book=_fresh_book())
        with mock.patch.object(live_projections, "_runtime_or_none", return_value=runtime):
            payload = live_projections.build_live_order_book_payload("AAPL")
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertTrue(payload["available"])
        self.assertEqual(payload["snapshots"][0]["best_bid"], 190.1)


class LiveOrderFlowFailClosedTests(unittest.TestCase):
    def test_unavailable_live_flow_does_not_fall_back_to_fixture(self) -> None:
        runtime = _runtime(trades=[], book=None)
        fixture = mock.Mock(return_value={"available": True, "source": "FIXTURE"})
        with mock.patch.object(live_projections, "_runtime_or_none", return_value=runtime):
            with mock.patch(
                "market_platform_foundation.providers.projections.build_workspace_order_flow_payload",
                fixture,
            ):
                payload = live_projections.resolve_workspace_order_flow_payload(
                    "AAPL",
                    as_of_context={},
                    prediction_cutoff=0,
                )
        fixture.assert_not_called()
        self.assertFalse(payload["available"])
        self.assertEqual(payload["reason"], "NO_LIVE_TRADES")
        self.assertNotIn("cvd", payload)

    def test_disconnected_feed_blocks_cvd(self) -> None:
        runtime = _runtime(
            trades=[{"aggressor_side": "BUY", "quantity": 1, "event_time_ns": 1}],
            connection=ProviderConnectionState.DISCONNECTED,
        )
        with mock.patch.object(live_projections, "_runtime_or_none", return_value=runtime):
            payload = live_projections.build_live_order_flow_payload("AAPL")
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertFalse(payload["available"])
        self.assertEqual(payload["reason"], "LIVE_FEED_UNHEALTHY")
        self.assertNotIn("cvd", payload)


class LiveMarkBridgeFailClosedTests(unittest.TestCase):
    def test_stale_live_mark_is_not_applied_to_paper_ledger(self) -> None:
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="live-mark-stale",
            instrument_id="AAPL",
            symbol="AAPL",
            data_mode="LIVE_OBSERVATIONAL",
            data_provider="MOOMOO",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )
        ledger.apply_live_mark(
            mark_minor=19100,
            mark_provider="MOOMOO",
            mark_as_of_ns=100,
            mark_quality="PASS",
        )
        store = SimpleNamespace(paper_ledger=ledger, execution_deferred=False)
        runtime = _runtime(
            mark={
                "mark_as_of_ns": 250,
                "mark_minor": 50,
                "mark_provider": "MOOMOO",
                "mark_quality": "STALE",
            }
        )
        with mock.patch.object(live_projections, "_runtime_or_none", return_value=runtime):
            with mock.patch(
                "market_platform_foundation.ui_api.paper_projections._live_focus_instrument_id",
                return_value="AAPL",
            ):
                with mock.patch("market_platform_foundation.local_state.startup.persist_ledger"):
                    live_projections.apply_live_marks_to_ledger(store)
        self.assertEqual(ledger._live_mark_minor, 19100)
        self.assertEqual(ledger._live_mark_quality, "PASS")

"""OCT1-09 — Paper experiment service, HTTP routes, persistence and restart.

SOFTWARE_CONTROLLED. The production preview/submit route, pre-trade risk, the
bar-conservative simulator, the ledger, SQLite local state and the experiment
service are used. Only the observation clock, the completed-bar feed and the
marks are controlled fixtures (``tests.support.paper_experiment_feed``).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.local_state.paper_experiments import (  # noqa: E402
    paper_experiment_repository,
    reset_paper_experiment_repository_for_tests,
)
from market_platform_foundation.local_state.startup import reset_local_state_for_tests  # noqa: E402
from market_platform_foundation.platform.security.route_policy import policy_for_route as policy_for  # noqa: E402
from market_platform_foundation.ui_api import paper_experiment  # noqa: E402
from market_platform_foundation.ui_api.paper_projections import (  # noqa: E402
    build_paper_portfolio_payload,
    cancel_paper_order,
    close_paper_session,
    open_paper_session,
    preview_paper_order,
    submit_paper_order,
)
from market_platform_foundation.ui_api.server import UiApiHandler  # noqa: E402
from market_platform_foundation.ui_api.store import ReplayStore  # noqa: E402
from market_platform_foundation.xa01.compatibility import register_equity  # noqa: E402
from tests.support.paper_experiment_feed import PROVIDER, ControlledFeed  # noqa: E402

INITIAL = 10_000_000
_ENV_KEYS = (
    "IMP_STATE_DIR",
    "IMP_PAPER_EXECUTION",
    "IMP_PERSIST_STATE",
    "IMP_LIVE_OBSERVATIONAL",
    "IMP_LIVE_EXECUTION",
    "IMP_BROKER_PAPER_EXECUTION",
    "IMP_BROKER_LIVE_EXECUTION",
    "IMP_MOOMOO_LIVE",
    "IMP_FINVIZ_LIVE",
    "IMP_LIVE_INTERNAL_SIMULATION",
    "IMP_CONTROLLED_REPLAY",
)


class _Base(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {key: os.environ.get(key) for key in _ENV_KEYS}
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        for key in _ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["IMP_STATE_DIR"] = self._tmp.name
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        reset_local_state_for_tests()
        reset_paper_experiment_repository_for_tests()
        self.feed = ControlledFeed()
        # A second tradable identity, registered canonically (G1) the way the operator fixtures are.
        register_equity(symbol="NVDA")
        patcher = self.feed.patched()
        patcher.__enter__()
        self.addCleanup(patcher.__exit__, None, None, None)
        self.addCleanup(self._restore)
        self.store = self.boot()
        self._orders = 0

    def _restore(self) -> None:
        reset_local_state_for_tests()
        reset_paper_experiment_repository_for_tests()
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def boot(self) -> ReplayStore:
        """A fresh process view of the same state directory."""
        reset_local_state_for_tests()
        reset_paper_experiment_repository_for_tests()
        store = ReplayStore(collection_root=ROOT.parent)
        store.load()
        store.mode = "PAPER"
        return store

    def create(self, **body: object) -> dict:
        return paper_experiment.create_experiment(self.store, dict(body))["experiment"]

    def order(self, instrument: str, side: str, quantity: int, price: str, *, key: str | None = None) -> dict:
        self._orders += 1
        key = key or f"oct109-{self._orders}"
        self.feed.prices[instrument] = price
        body = {
            "client_order_id": key,
            "idempotency_key": key,
            "instrument_id": instrument,
            "order_type": "MARKET",
            "quantity": quantity,
            "side": side,
        }
        preview = preview_paper_order(self.store, body)["preview"]
        self.last_preview = preview
        return submit_paper_order(self.store, {**body, "preview_id": preview["preview_id"]})["submission"]

    def valuation(self) -> dict:
        return self.store.paper_ledger.project_valuation()


class ExperimentLifecycleServiceTests(_Base):
    def test_no_experiment_until_explicitly_created(self) -> None:
        self.assertEqual(paper_experiment.current_experiment_payload(self.store)["state"], "NO_ACTIVE_PAPER_EXPERIMENT")
        self.assertIsNone(build_paper_portfolio_payload(self.store)["experiment"])
        # The default Paper account is still the legacy default, not $100k.
        self.assertEqual(self.store.paper_ledger.policy["initial_cash_minor"], 1_000_000_00)
        self.assertFalse(self.store.paper_ledger.is_portfolio_scoped())

    def test_create_is_exactly_100k_simulated_internal(self) -> None:
        experiment = self.create()
        self.assertTrue(experiment["experiment_id"].startswith("PPE-"))
        self.assertEqual(experiment["initial_capital_minor"], INITIAL)
        self.assertEqual(experiment["currency"], "USD")
        self.assertEqual(experiment["execution_mode"], "INTERNAL_SIMULATION")
        self.assertEqual(experiment["capital_kind"], "SIMULATED")
        self.assertIs(experiment["live_capital"], False)
        self.assertEqual(experiment["evidence_class"], "SOFTWARE_CONTROLLED")
        self.assertEqual(experiment["slippage_model"], "NOT_SEPARATELY_MODELED")
        value = self.valuation()
        self.assertEqual((value["cash_minor"], value["equity_minor"], value["total_pnl_minor"]), (INITIAL, INITIAL, 0))
        self.assertEqual(value["quality"], "CURRENT")
        self.assertEqual(self.store.paper_ledger.paper_account_id, experiment["paper_account_id"])

    def test_live_and_broker_paper_execution_modes_are_refused(self) -> None:
        for mode in ("LIVE", "BROKER_PAPER", "LIVE_CAPITAL"):
            with self.assertRaisesRegex(ValueError, "EXPERIMENT_EXECUTION_MODE_FORBIDDEN"):
                self.create(execution_mode=mode)
        self.assertEqual(paper_experiment_repository().count(), 0)

    def test_create_fails_closed_without_paper_execution_authority(self) -> None:
        os.environ["IMP_PAPER_EXECUTION"] = "0"
        before = self.store.paper_ledger
        with self.assertRaisesRegex(ValueError, "PAPER_EXECUTION_NOT_AUTHORIZED"):
            self.create()
        self.assertEqual(paper_experiment_repository().count(), 0)
        self.assertIs(self.store.paper_ledger, before)
        self.assertFalse(any(e["event_type"] == "PaperSessionClosed" for e in before.events))

    def test_second_create_and_legacy_session_routes_cannot_replace_it(self) -> None:
        first = self.create()
        self.order("AAPL", "BUY", 10, "150.00")
        with self.assertRaisesRegex(ValueError, "PAPER_EXPERIMENT_ACTIVE"):
            self.create()
        with self.assertRaisesRegex(ValueError, "PAPER_EXPERIMENT_ACTIVE"):
            open_paper_session(self.store, {"instrument_id": "AAPL"})
        with self.assertRaisesRegex(ValueError, "PAPER_EXPERIMENT_ACTIVE"):
            close_paper_session(self.store)
        self.assertEqual(self.store.paper_ledger.experiment_id, first["experiment_id"])
        self.assertEqual(self.valuation()["cash_minor"], INITIAL - 150_000)

    def test_close_is_refused_with_open_positions_and_never_liquidates(self) -> None:
        experiment = self.create()
        self.order("AAPL", "BUY", 10, "150.00")
        with self.assertRaisesRegex(ValueError, "OPEN_POSITIONS_REMAIN"):
            paper_experiment.close_experiment(self.store, experiment["experiment_id"])
        self.assertEqual(self.store.paper_ledger.position_shares_for("AAPL"), 10)
        self.assertEqual(paper_experiment.current_experiment_payload(self.store)["state"], "ACTIVE")

    def test_close_is_refused_with_working_orders(self) -> None:
        experiment = self.create()
        # 300 shares of bar volume caps the fill at 3 of 5: the order stays working.
        self.feed.volume = 300
        order = self.order("AAPL", "BUY", 5, "100.00")["order"]
        self.feed.volume = 1_000_000
        self.assertEqual(order["state"], "PARTIALLY_FILLED")
        account = self.store.paper_ledger.project_account()
        self.assertEqual(account["cash_minor"], INITIAL - 30_000)
        self.assertEqual(account["reserved_cash_minor"], 20_000)
        # Buying power is cash less the working-order reservation; no leverage is invented.
        self.assertEqual(account["buying_power_minor"], INITIAL - 30_000 - 20_000)
        with self.assertRaisesRegex(ValueError, "OPEN_POSITIONS_REMAIN"):
            paper_experiment.close_experiment(self.store, experiment["experiment_id"])
        self.order("AAPL", "SELL", 3, "100.00")
        with self.assertRaisesRegex(ValueError, "WORKING_ORDERS_REMAIN"):
            paper_experiment.close_experiment(self.store, experiment["experiment_id"])
        cancel_paper_order(self.store, {"order_id": order["order_id"]})
        # The cancelled remainder is order history, never a trade.
        self.assertEqual(len(self.store.paper_ledger.project_trades()), 2)
        self.assertEqual(self.store.paper_ledger.project_account()["buying_power_minor"], INITIAL)
        closed = paper_experiment.close_experiment(self.store, experiment["experiment_id"])["experiment"]
        self.assertEqual(closed["status"], "CLOSED")

    def test_flat_close_freezes_final_values_and_blocks_new_orders(self) -> None:
        experiment = self.create()
        self.order("AAPL", "BUY", 10, "150.00")
        self.order("AAPL", "SELL", 10, "152.00")
        closed = paper_experiment.close_experiment(self.store, experiment["experiment_id"])["experiment"]
        self.assertEqual(closed["status"], "CLOSED")
        self.assertEqual(closed["closing"]["final_cash_minor"], INITIAL + 2_000)
        # Flat closed experiment: equity is cash, and P&L is all realized.
        self.assertEqual(closed["closing"]["final_equity_minor"], closed["closing"]["final_cash_minor"])
        self.assertEqual(closed["closing"]["final_realized_pnl_minor"], 2_000)
        self.assertEqual(closed["closing"]["final_total_pnl_minor"], 2_000)
        self.assertEqual(closed["closing"]["trade_count"], 2)
        with self.assertRaisesRegex(ValueError, "PAPER_EXPERIMENT_CLOSED"):
            self.order("AAPL", "BUY", 1, "150.00")
        with self.assertRaisesRegex(ValueError, "EXPERIMENT_ALREADY_CLOSED"):
            paper_experiment.close_experiment(self.store, experiment["experiment_id"])
        # History stays readable after close.
        trades = paper_experiment.trades_payload(self.store, experiment_id=experiment["experiment_id"])
        self.assertEqual(trades["total_count"], 2)
        history = paper_experiment.equity_history_payload(self.store, experiment_id=experiment["experiment_id"])
        self.assertEqual(history["snapshots"][0]["trigger"], "EXPERIMENT_CLOSED")

    def test_new_experiment_after_close_is_a_new_account_with_fresh_100k(self) -> None:
        first = self.create()
        self.order("AAPL", "BUY", 10, "150.00")
        self.order("AAPL", "SELL", 10, "140.00")
        paper_experiment.close_experiment(self.store, first["experiment_id"])
        second = self.create()
        self.assertNotEqual(second["experiment_id"], first["experiment_id"])
        self.assertNotEqual(second["paper_account_id"], first["paper_account_id"])
        self.assertNotEqual(second["paper_session_id"], first["paper_session_id"])
        self.assertEqual(self.valuation()["cash_minor"], INITIAL)
        self.assertEqual(self.store.paper_ledger.project_trades(), [])
        # The prior experiment is immutable and still readable with its own loss.
        prior = paper_experiment.experiment_payload(self.store, first["experiment_id"])
        self.assertEqual(prior["experiment"]["status"], "CLOSED")
        self.assertEqual(prior["valuation"]["cash_minor"], INITIAL - 10_000)
        self.assertEqual(paper_experiment.trades_payload(self.store, experiment_id=first["experiment_id"])["total_count"], 2)
        self.assertEqual(paper_experiment.trades_payload(self.store)["total_count"], 0)
        listing = paper_experiment.list_experiments_payload(self.store)
        self.assertEqual(listing["total_count"], 2)
        self.assertEqual(listing["active_experiment_id"], second["experiment_id"])


class ExperimentRouteAccountingTests(_Base):
    def test_one_account_two_instruments_independent_marks_through_the_route(self) -> None:
        experiment = self.create()
        first = self.order("AAPL", "BUY", 100, "150.00")
        second = self.order("NVDA", "BUY", 50, "240.00")
        ledger = self.store.paper_ledger
        # One experiment, one account, one capital base.
        self.assertEqual((first["order"]["state"], second["order"]["state"]), ("FILLED", "FILLED"))
        self.assertEqual(ledger.paper_account_id, experiment["paper_account_id"])
        self.assertEqual(sum(1 for e in ledger.events if e["event_type"] == "PaperAccountCreated"), 1)
        self.assertEqual(paper_experiment_repository().count(), 1)
        self.assertEqual(self.valuation()["cash_minor"], INITIAL - 1_500_000 - 1_200_000)
        self.assertEqual(self.valuation()["initial_capital_minor"], INITIAL)

        # No mark yet: positions are present, never valued at zero.
        portfolio = build_paper_portfolio_payload(self.store)
        self.assertEqual(portfolio["valuation"]["quality"], "UNAVAILABLE")
        self.assertIsNone(portfolio["valuation"]["equity_minor"])
        self.assertIsNone(portfolio["pnl"]["unrealized_display"])
        self.assertEqual(sorted(portfolio["valuation"]["missing_mark_instruments"]), ["AAPL", "NVDA"])

        self.feed.mark(self.store, "AAPL", "155.00")
        self.assertEqual(self.valuation()["quality"], "PARTIAL")
        self.assertEqual(self.valuation()["missing_mark_instruments"], ["NVDA"])
        self.feed.mark(self.store, "NVDA", "236.00")
        rows = {row["instrument_id"]: row for row in build_paper_portfolio_payload(self.store)["positions"]}
        self.assertEqual((rows["AAPL"]["mark_minor"], rows["AAPL"]["unrealized_pnl_minor"]), (15_500, 50_000))
        self.assertEqual((rows["NVDA"]["mark_minor"], rows["NVDA"]["unrealized_pnl_minor"]), (23_600, -20_000))
        self.assertEqual(rows["AAPL"]["mark_provider"], PROVIDER)
        value = self.valuation()
        self.assertEqual(value["quality"], "CURRENT")
        self.assertEqual(value["equity_minor"], value["cash_minor"] + 100 * 15_500 + 50 * 23_600)
        self.assertEqual(value["total_pnl_minor"], value["equity_minor"] - INITIAL)
        self.assertEqual(value["total_pnl_minor"], 30_000)
        self.assertEqual(value["return_bps"], 30)

    def test_return_is_symmetric_for_gains_and_losses(self) -> None:
        self.create()
        self.order("AAPL", "BUY", 100, "150.00")
        self.feed.mark(self.store, "AAPL", "148.22")
        loss = self.valuation()
        self.assertEqual((loss["total_pnl_minor"], loss["return_bps"]), (-17_800, -17))
        self.feed.mark(self.store, "AAPL", "151.78")
        gain = self.valuation()
        self.assertEqual((gain["total_pnl_minor"], gain["return_bps"]), (17_800, 17))
        self.feed.mark(self.store, "AAPL", "149.99")
        self.assertEqual(self.valuation()["return_bps"], 0)

    def test_partial_then_full_close_reconciles(self) -> None:
        self.create()
        self.order("AAPL", "BUY", 100, "150.00")
        self.feed.mark(self.store, "AAPL", "155.00")
        self.order("AAPL", "SELL", 40, "155.00")
        value = self.valuation()
        self.assertEqual(value["cash_minor"], INITIAL - 1_500_000 + 620_000)
        self.assertEqual(value["realized_pnl_minor"], 20_000)
        self.assertEqual(value["unrealized_pnl_minor"], 30_000)
        self.assertEqual(value["equity_minor"], INITIAL + 50_000)
        row = self.store.paper_ledger.project_positions()[0]
        self.assertEqual((row["quantity"], row["average_fill_minor"], row["cost_basis_minor"]), (60, 15_000, 900_000))
        self.order("AAPL", "SELL", 60, "153.00")
        value = self.valuation()
        self.assertEqual(self.store.paper_ledger.project_positions(), [])
        self.assertEqual(value["realized_pnl_minor"], 20_000 + 18_000)
        self.assertEqual(value["unrealized_pnl_minor"], 0)
        self.assertEqual(value["equity_minor"], value["cash_minor"])
        self.assertEqual(value["equity_minor"], INITIAL + 38_000)
        trades = self.store.paper_ledger.project_trades()
        self.assertEqual([t["position_effect"] for t in trades], ["OPEN", "REDUCE", "CLOSE"])
        self.assertEqual([t["realized_pnl_delta_minor"] for t in trades], [0, 20_000, 18_000])

    def test_stale_mark_degrades_valuation_and_keeps_its_identity(self) -> None:
        self.create()
        self.order("AAPL", "BUY", 10, "150.00")
        self.feed.mark(self.store, "AAPL", "151.00", quality="STALE")
        value = build_paper_portfolio_payload(self.store)["valuation"]
        self.assertEqual(value["quality"], "DEGRADED")
        self.assertEqual(value["degraded_instruments"], ["AAPL"])
        mark = value["marks"][0]
        self.assertEqual((mark["provider"], mark["quality"], mark["mark_minor"]), (PROVIDER, "STALE", 15_100))
        self.assertIsNotNone(mark["mark_as_of_ns"])
        self.assertEqual(value["equity_minor"], INITIAL + 1_000)

    def test_preview_shows_which_account_the_order_touches(self) -> None:
        experiment = self.create()
        self.order("AAPL", "BUY", 10, "150.00")
        self.feed.prices["AAPL"] = "150.00"
        body = {"client_order_id": "p", "idempotency_key": "p", "instrument_id": "AAPL", "order_type": "MARKET", "quantity": 1, "side": "BUY"}
        events = len(self.store.paper_ledger.events)
        context = preview_paper_order(self.store, body)["preview"]["experiment_context"]
        self.assertEqual(context["experiment_id"], experiment["experiment_id"])
        self.assertEqual(context["paper_account_id"], experiment["paper_account_id"])
        self.assertEqual(context["initial_capital_minor"], INITIAL)
        self.assertEqual(context["cash_minor"], INITIAL - 150_000)
        self.assertEqual(context["buying_power_minor"], INITIAL - 150_000)
        self.assertEqual(context["current_position_quantity"], 10)
        self.assertEqual(context["capital_kind"], "SIMULATED")
        self.assertEqual(len(self.store.paper_ledger.events), events, "preview never mutates the ledger")

    def test_duplicate_submit_does_not_double_account(self) -> None:
        self.create()
        first = self.order("AAPL", "BUY", 10, "150.00", key="same")
        cash = self.valuation()["cash_minor"]
        events = len(self.store.paper_ledger.events)
        body = {"client_order_id": "same", "idempotency_key": "same", "instrument_id": "AAPL", "order_type": "MARKET", "quantity": 10, "side": "BUY"}
        retry = submit_paper_order(self.store, {**body, "preview_id": self.last_preview["preview_id"]})["submission"]
        self.assertTrue(retry["duplicate"])
        self.assertEqual(retry["order_id"], first["order"]["order_id"])
        self.assertEqual(self.valuation()["cash_minor"], cash)
        self.assertEqual(len(self.store.paper_ledger.events), events)
        self.assertEqual(len(self.store.paper_ledger.project_trades()), 1)
        self.assertEqual(self.store.paper_ledger.position_shares_for("AAPL"), 10)

    def test_rejected_and_oversell_orders_are_not_trades(self) -> None:
        self.create()
        self.order("AAPL", "BUY", 10, "150.00")
        cash = self.valuation()["cash_minor"]
        try:
            rejected = self.order("AAPL", "SELL", 11, "150.00")
        except ValueError as exc:  # refused at the boundary
            self.assertIn("INSUFFICIENT_POSITION", str(exc))
        else:
            self.assertNotEqual(rejected["order"]["state"], "FILLED")
        self.assertEqual(len(self.store.paper_ledger.project_trades()), 1)
        self.assertEqual(self.valuation()["cash_minor"], cash)
        self.assertEqual(self.store.paper_ledger.position_shares_for("AAPL"), 10)
        # A sell of an instrument that is not held never opens a short.
        try:
            self.order("NVDA", "SELL", 1, "240.00")
        except ValueError as exc:
            self.assertIn("INSUFFICIENT_POSITION", str(exc))
        self.assertEqual(self.store.paper_ledger.position_shares_for("NVDA"), 0)
        self.assertEqual(len(self.store.paper_ledger.project_trades()), 1)

    def test_trade_rows_carry_experiment_lineage_and_simulated_labels(self) -> None:
        experiment = self.create()
        self.order("AAPL", "BUY", 10, "150.00")
        trade = paper_experiment.trades_payload(self.store)["trades"][0]
        self.assertEqual(trade["fill_kind"], "SIMULATED_FILL")
        self.assertIs(trade["is_market_truth"], False)
        self.assertEqual(trade["decision_source"], "MANUAL_TEST")
        kinds = {ref["kind"]: ref["id"] for ref in trade["lineage_refs"]}
        self.assertEqual(kinds["PAPER_EXPERIMENT"], experiment["experiment_id"])
        self.assertEqual(kinds["PAPER_PREVIEW"], self.last_preview["preview_id"])
        self.assertEqual((trade["commission_minor"], trade["fees_minor"]), (0, 0))
        self.assertEqual((trade["symbol"], trade["side"], trade["filled_quantity"], trade["fill_price_minor"]), ("AAPL", "BUY", 10, 15_000))

    def test_governed_order_lineage_names_every_upstream_record(self) -> None:
        from market_platform_foundation.ui_api.paper_projections import _order_lineage_refs

        experiment = self.create()
        record = {
            "cycle_id": "RC-1",
            "decision_trace_id": "TRACE-1",
            "evidence_snapshot": {"candidate_run_id": "RUN-1"},
            "opportunity_id": "OPP-1",
            "server_exit": {"policy_id": "STP-1", "position_epoch_id": "PE-1", "stop_state_id": "STS-1"},
        }
        parsed = {"decision_source_snapshot": {"reasons": [
            {"code": "ACTION_DECISION", "label": "AD-1"},
            {"code": "ACTION_SNAPSHOT", "label": "AS-1"},
            {"code": "WATCHED_OPPORTUNITY", "label": "not lineage"},
        ]}}
        refs = _order_lineage_refs(self.store, parsed=parsed, body={"preview_id": "PRV-1"}, action_record=record)
        self.assertEqual(
            {ref["kind"]: ref["id"] for ref in refs},
            {
                "ACTION_DECISION": "AD-1", "ACTION_SNAPSHOT": "AS-1", "CANDIDATE_RUN": "RUN-1", "OPPORTUNITY": "OPP-1",
                "DECISION_TRACE": "TRACE-1", "REEVALUATION_CYCLE": "RC-1", "SMA_STOP_STATE": "STS-1", "SMA_STOP_POLICY": "STP-1",
                "POSITION_EPOCH": "PE-1", "PAPER_PREVIEW": "PRV-1", "PAPER_EXPERIMENT": experiment["experiment_id"],
            },
        )
        self.assertTrue(all(ref["schema_version"] == "1" for ref in refs))

    def test_derivative_orders_are_refused_in_the_experiment_account(self) -> None:
        self.create()
        for kind in ("OPTION_CONTRACT", "FUTURE_CONTRACT"):
            with self.assertRaisesRegex(ValueError, "EXPERIMENT_INSTRUMENT_KIND_UNSUPPORTED"):
                paper_experiment.assert_experiment_instrument_supported(self.store, {"instrument_kind": kind})
        paper_experiment.assert_experiment_instrument_supported(self.store, {"instrument_kind": "EQUITY"})
        self.order("AAPL", "BUY", 1, "150.00")
        self.assertEqual(len(self.store.paper_ledger.project_trades()), 1)

    def test_data_mode_mismatch_blocks_orders_but_portfolio_stays_readable(self) -> None:
        self.create()
        self.order("AAPL", "BUY", 10, "150.00")
        self.store.paper_ledger.data_mode = "LIVE_OBSERVATIONAL"
        with self.assertRaisesRegex(ValueError, "EXPERIMENT_MARKET_DATA_UNAVAILABLE"):
            self.order("AAPL", "BUY", 1, "150.00")
        payload = build_paper_portfolio_payload(self.store)
        self.assertEqual(payload["boundary"]["market_data"]["state"], "MARKET_DATA_UNAVAILABLE")
        self.assertEqual(payload["valuation"]["cash_minor"], INITIAL - 150_000)

    def test_authority_loss_blocks_submit_and_never_reaches_live(self) -> None:
        self.create()
        self.store.paper_ledger.execution_authority = "BLOCKED"
        with self.assertRaises(ValueError):
            self.order("AAPL", "BUY", 1, "150.00")
        self.assertEqual(self.store.paper_ledger.project_trades(), [])
        self.assertEqual(build_paper_portfolio_payload(self.store)["valuation"]["equity_minor"], INITIAL)
        self.assertNotIn("IMP_LIVE_EXECUTION", os.environ)


class ExperimentEquityHistoryTests(_Base):
    def test_material_states_are_recorded_once(self) -> None:
        experiment = self.create()
        repo = paper_experiment_repository()
        eid = experiment["experiment_id"]
        self.assertEqual(repo.snapshot_count(eid), 1)
        for _ in range(5):  # repeated reads never append identical rows
            build_paper_portfolio_payload(self.store)
            paper_experiment.record_equity_snapshot(self.store, trigger="MARK_UPDATE")
        self.assertEqual(repo.snapshot_count(eid), 1)
        self.order("AAPL", "BUY", 10, "150.00")
        self.assertEqual(repo.snapshot_count(eid), 2)
        self.feed.mark(self.store, "AAPL", "151.00")
        build_paper_portfolio_payload(self.store)
        build_paper_portfolio_payload(self.store)
        # A mark-only change inside the rate limit is not a new row.
        self.assertEqual(repo.snapshot_count(eid), 2)
        self.order("AAPL", "SELL", 10, "151.00")
        paper_experiment.close_experiment(self.store, eid)
        history = paper_experiment.equity_history_payload(self.store, experiment_id=eid)
        self.assertEqual([row["trigger"] for row in history["snapshots"]], ["EXPERIMENT_CLOSED", "FILL", "FILL", "EXPERIMENT_CREATED"])
        self.assertEqual([row["equity_minor"] for row in history["snapshots"]][-1], INITIAL)
        self.assertEqual(history["snapshots"][0]["equity_minor"], INITIAL + 1_000)
        self.assertEqual(history["total_count"], 4)

    def test_history_and_trades_are_bounded_and_paged(self) -> None:
        experiment = self.create()
        for index in range(6):
            self.order("AAPL", "BUY" if index % 2 == 0 else "SELL", 1, "150.00")
        page = paper_experiment.trades_payload(self.store, limit=4)
        self.assertEqual((len(page["trades"]), page["total_count"], page["page_size"]), (4, 6, 4))
        rest = paper_experiment.trades_payload(self.store, limit=4, cursor=page["next_cursor"])
        self.assertEqual(len(rest["trades"]), 2)
        self.assertIsNone(rest["next_cursor"])
        ids = [t["fill_id"] for t in page["trades"] + rest["trades"]]
        self.assertEqual(len(set(ids)), 6)
        self.assertEqual(paper_experiment.trades_payload(self.store, limit=10_000)["page_size"], 100)
        self.assertEqual(paper_experiment.trades_payload(self.store, limit=-5)["page_size"], 1)
        with self.assertRaisesRegex(ValueError, "TRADE_CURSOR_INVALID"):
            paper_experiment.trades_payload(self.store, cursor="nope")
        first = paper_experiment.equity_history_payload(self.store, limit=3)
        self.assertEqual(len(first["snapshots"]), 3)
        older = paper_experiment.equity_history_payload(self.store, limit=3, before=first["next_before"])
        self.assertTrue(all(row["snapshot_id"] < first["next_before"] for row in older["snapshots"]))
        self.assertEqual(paper_experiment.equity_history_payload(self.store, limit=10_000)["page_size"], 100)
        self.assertEqual(first["experiment_id"], experiment["experiment_id"])


class ExperimentRestartTests(_Base):
    def test_restart_restores_the_same_experiment_without_reseeding(self) -> None:
        experiment = self.create()
        self.order("AAPL", "BUY", 100, "150.00")
        self.order("NVDA", "BUY", 50, "240.00")
        self.feed.mark(self.store, "AAPL", "155.00")
        self.feed.mark(self.store, "NVDA", "236.00")
        self.order("AAPL", "SELL", 40, "155.00")
        before_ledger = self.store.paper_ledger
        before = {
            "account": before_ledger.project_account(),
            "positions": before_ledger.project_positions(),
            "trades": before_ledger.project_trades(),
            "events": [e["event_id"] for e in before_ledger.events],
        }
        snapshots = paper_experiment_repository().snapshot_count(experiment["experiment_id"])

        for _ in range(2):  # API restart, then again
            self.store = self.boot()
            ledger = self.store.paper_ledger
            self.assertIsNot(ledger, before_ledger)
            self.assertEqual(ledger.experiment_id, experiment["experiment_id"])
            self.assertEqual(ledger.paper_account_id, experiment["paper_account_id"])
            self.assertEqual(ledger.session_id, experiment["paper_session_id"])
            account = ledger.project_account()
            self.assertEqual(account["initial_cash_minor"], INITIAL)
            self.assertEqual(account["cash_minor"], before["account"]["cash_minor"])
            self.assertEqual(account["cash_minor"], INITIAL - 1_500_000 - 1_200_000 + 620_000)
            self.assertEqual(account["realized_pnl_minor"], 20_000)
            self.assertEqual([e["event_id"] for e in ledger.events], before["events"])
            self.assertEqual(ledger.project_trades(), before["trades"])
            rows = {row["instrument_id"]: row for row in ledger.project_positions()}
            prior = {row["instrument_id"]: row for row in before["positions"]}
            for instrument in ("AAPL", "NVDA"):
                for key in ("quantity", "side", "cost_basis_minor", "average_fill_minor", "first_entry_time_ns",
                            "latest_fill_time_ns", "mark_minor", "mark_provider", "mark_as_of_ns", "realized_pnl_minor"):
                    self.assertEqual(rows[instrument][key], prior[instrument][key], (instrument, key))
                # A mark read back from disk is not a current observation.
                self.assertEqual(rows[instrument]["mark_quality"], "RESTORED")
            value = ledger.project_valuation()
            self.assertEqual(value["quality"], "DEGRADED")
            self.assertEqual(value["equity_minor"], account["cash_minor"] + 60 * 15_500 + 50 * 23_600)
            # Restart is not a material portfolio event and never tops the account up.
            self.assertEqual(paper_experiment.current_experiment_payload(self.store)["state"], "ACTIVE")
            self.assertEqual(paper_experiment_repository().count(), 1)
            self.assertEqual(paper_experiment.list_experiments_payload(self.store)["total_count"], 1)
            self.assertTrue(self.store.execution_deferred)
        self.assertGreaterEqual(paper_experiment_repository().snapshot_count(experiment["experiment_id"]), snapshots)

    def test_duplicate_submit_after_restart_is_still_idempotent(self) -> None:
        self.create()
        self.order("AAPL", "BUY", 10, "150.00", key="durable")
        preview_id = self.last_preview["preview_id"]
        self.store = self.boot()
        self.store.execution_deferred = False
        self.store.execution_mode = self.store.paper_ledger.execution_mode
        self.store.execution_authority = self.store.paper_ledger.execution_authority = "PAPER_ONLY"
        body = {"client_order_id": "durable", "idempotency_key": "durable", "instrument_id": "AAPL", "order_type": "MARKET",
                "quantity": 10, "side": "BUY", "preview_id": preview_id}
        retry = submit_paper_order(self.store, body)["submission"]
        self.assertTrue(retry["duplicate"])
        self.assertEqual(len(self.store.paper_ledger.project_trades()), 1)
        self.assertEqual(self.store.paper_ledger.project_account()["cash_minor"], INITIAL - 150_000)

    def test_closed_experiment_is_not_reopened_by_restart(self) -> None:
        experiment = self.create()
        self.order("AAPL", "BUY", 10, "150.00")
        self.order("AAPL", "SELL", 10, "150.00")
        paper_experiment.close_experiment(self.store, experiment["experiment_id"])
        self.store = self.boot()
        self.assertEqual(paper_experiment.current_experiment_payload(self.store)["state"], "NO_ACTIVE_PAPER_EXPERIMENT")
        self.assertFalse(self.store.paper_ledger.is_portfolio_scoped())
        readback = paper_experiment.experiment_payload(self.store, experiment["experiment_id"])
        self.assertEqual(readback["experiment"]["status"], "CLOSED")
        self.assertEqual(readback["experiment"]["closing"]["final_equity_minor"], INITIAL)
        self.assertEqual(readback["valuation"]["cash_minor"], INITIAL)

    def test_two_experiments_never_share_account_cash_or_fills(self) -> None:
        first = self.create()
        self.order("AAPL", "BUY", 10, "150.00")
        self.order("AAPL", "SELL", 10, "151.00")
        paper_experiment.close_experiment(self.store, first["experiment_id"])
        second = self.create()
        self.order("NVDA", "BUY", 5, "240.00")
        self.store = self.boot()
        a = paper_experiment.experiment_payload(self.store, first["experiment_id"])
        b = paper_experiment.experiment_payload(self.store, second["experiment_id"])
        self.assertNotEqual(a["experiment"]["paper_account_id"], b["experiment"]["paper_account_id"])
        self.assertEqual(a["valuation"]["cash_minor"], INITIAL + 1_000)
        self.assertEqual(b["valuation"]["cash_minor"], INITIAL - 120_000)
        self.assertEqual(a["positions"], [])
        self.assertEqual([row["instrument_id"] for row in b["positions"]], ["NVDA"])
        fills_a = {t["fill_id"] for t in paper_experiment.trades_payload(self.store, experiment_id=first["experiment_id"])["trades"]}
        fills_b = {t["fill_id"] for t in paper_experiment.trades_payload(self.store, experiment_id=second["experiment_id"])["trades"]}
        self.assertEqual((len(fills_a), len(fills_b)), (2, 1))
        self.assertFalse(fills_a & fills_b)


class _OpenHandler(UiApiHandler):
    def _authorize_request(self, *args: object, **kwargs: object) -> bool:  # auth is covered by the route-policy tests
        return True

    def log_message(self, *args: object) -> None:
        return


class ExperimentHttpRouteTests(_Base):
    def setUp(self) -> None:
        super().setUp()
        _OpenHandler.store = self.store
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _OpenHandler)
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def call(self, path: str, body: dict | None = None) -> tuple[int, dict]:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    def test_route_policies_require_read_or_write_capability(self) -> None:
        for path in ("/paper/experiments", "/paper/experiments/current", "/paper/experiments/PPE-X", "/paper/trades", "/paper/equity-history"):
            policy = policy_for("GET", path)
            self.assertIsNotNone(policy, path)
            self.assertEqual(policy.capability, "state.read", path)
        for path in ("/paper/experiments", "/paper/experiments/PPE-X/close"):
            policy = policy_for("POST", path)
            self.assertIsNotNone(policy, path)
            self.assertEqual(policy.capability, "state.write", path)

    def test_full_http_lifecycle(self) -> None:
        status, current = self.call("/paper/experiments/current")
        self.assertEqual((status, current["state"], current["experiment"]), (200, "NO_ACTIVE_PAPER_EXPERIMENT", None))
        status, empty = self.call("/paper/trades")
        self.assertEqual((status, empty["trades"], empty["experiment_id"]), (200, [], None))
        status, empty = self.call("/paper/equity-history")
        self.assertEqual((status, empty["snapshots"]), (200, []))

        status, refused = self.call("/paper/experiments", {"execution_mode": "LIVE"})
        self.assertGreaterEqual(status, 400)
        self.assertIn("EXPERIMENT_EXECUTION_MODE_FORBIDDEN", json.dumps(refused))

        status, created = self.call("/paper/experiments", {"name": "http"})
        self.assertEqual(status, 200, created)
        eid = created["experiment"]["experiment_id"]
        self.assertEqual(created["experiment"]["initial_capital_minor"], INITIAL)
        status, again = self.call("/paper/experiments", {})
        self.assertGreaterEqual(status, 400)
        self.assertIn("PAPER_EXPERIMENT_ACTIVE", json.dumps(again))

        status, current = self.call("/paper/experiments/current")
        self.assertEqual((current["state"], current["valuation"]["equity_minor"]), ("ACTIVE", INITIAL))
        self.assertEqual(current["boundary"]["capital"], {"kind": "SIMULATED", "live_capital": False})
        self.assertEqual(current["boundary"]["execution"]["mode"], "INTERNAL_SIMULATION")
        self.assertEqual(current["boundary"]["market_data"]["mode"], "FIXTURE_REPLAY")

        self.feed.prices["AAPL"] = "150.00"
        order = {"client_order_id": "h1", "idempotency_key": "h1", "instrument_id": "AAPL", "order_type": "MARKET", "quantity": 10, "side": "BUY"}
        status, preview = self.call("/paper/orders/preview", order)
        self.assertEqual(status, 200, preview)
        status, submitted = self.call("/paper/orders", {**order, "preview_id": preview["preview"]["preview_id"]})
        self.assertEqual(status, 200, submitted)

        status, blocked = self.call(f"/paper/experiments/{eid}/close", {})
        self.assertGreaterEqual(status, 400)
        self.assertIn("OPEN_POSITIONS_REMAIN", json.dumps(blocked))

        status, trades = self.call("/paper/trades?limit=1")
        self.assertEqual((status, len(trades["trades"]), trades["total_count"]), (200, 1, 1))
        status, bad = self.call("/paper/trades?cursor=unknown")
        self.assertGreaterEqual(status, 400)
        status, history = self.call("/paper/equity-history?limit=1")
        self.assertEqual((status, len(history["snapshots"]), history["total_count"]), (200, 1, 2))
        status, one = self.call(f"/paper/experiments/{eid}")
        self.assertEqual((status, one["experiment"]["experiment_id"], len(one["positions"])), (200, eid, 1))
        status, missing = self.call("/paper/experiments/PPE-DOES-NOT-EXIST")
        self.assertGreaterEqual(status, 400)
        self.assertIn("EXPERIMENT_NOT_FOUND", json.dumps(missing))
        status, missing = self.call("/paper/experiments/PPE-DOES-NOT-EXIST/close", {})
        self.assertGreaterEqual(status, 400)

        self.feed.prices["AAPL"] = "151.00"
        order = {"client_order_id": "h2", "idempotency_key": "h2", "instrument_id": "AAPL", "order_type": "MARKET", "quantity": 10, "side": "SELL"}
        status, preview = self.call("/paper/orders/preview", order)
        status, submitted = self.call("/paper/orders", {**order, "preview_id": preview["preview"]["preview_id"]})
        self.assertEqual(status, 200, submitted)
        status, closed = self.call(f"/paper/experiments/{eid}/close", {})
        self.assertEqual((status, closed["experiment"]["status"]), (200, "CLOSED"))
        self.assertEqual(closed["experiment"]["closing"]["final_equity_minor"], INITIAL + 1_000)
        status, listing = self.call("/paper/experiments?limit=500")
        self.assertEqual((status, listing["total_count"], listing["page_size"], listing["active_experiment_id"]), (200, 1, 100, None))
        status, current = self.call("/paper/experiments/current")
        self.assertEqual(current["state"], "NO_ACTIVE_PAPER_EXPERIMENT")


if __name__ == "__main__":
    unittest.main()

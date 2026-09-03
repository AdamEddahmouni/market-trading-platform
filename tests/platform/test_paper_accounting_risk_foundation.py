"""Paper cash-account, multi-instrument, and monetary-risk regression tests."""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.ledger import PaperExecutionLedger  # noqa: E402
from market_platform_foundation.paper.broker_paper import (  # noqa: E402
    apply_broker_status_event,
    submit_broker_paper_order,
)
from market_platform_foundation.portfolio.ledger import apply_fill, build_ledger_state  # noqa: E402
from market_platform_foundation.providers.contracts import ProviderResult  # noqa: E402
from market_platform_foundation.risk.decision import evaluate_risk  # noqa: E402
from market_platform_foundation.risk.kill_switch import KillSwitchState  # noqa: E402
from market_platform_foundation.risk.policy import build_risk_policy  # noqa: E402
from market_platform_foundation.ui_api.paper_projections import _bars_for_paper_execution  # noqa: E402
from market_platform_foundation.local_state.startup import (  # noqa: E402
    compatible_resume,
    ledger_from_session,
    persist_ledger,
    session_record_from_ledger,
)


def _fill(
    fill_id: str,
    instrument_id: str,
    direction: str,
    quantity: int,
    price_minor: int,
) -> dict:
    return {
        "direction": direction,
        "fill_id": fill_id,
        "fill_price_minor": price_minor,
        "fill_quantity": quantity,
        "fill_time": 1,
        "instrument_id": instrument_id,
        "order_id": f"order-{fill_id}",
    }


class MultiInstrumentAccountingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = build_risk_policy(
            initial_cash_minor=100_000,
            max_order_shares=1_000,
            max_position_shares=1_000,
        )

    def test_fills_keep_independent_symbol_positions_and_realized_pnl(self) -> None:
        state = build_ledger_state(initial_cash_minor=100_000)
        state = apply_fill(
            state,
            fill=_fill("a-buy", "AAA", "long", 10, 100),
            policy=self.policy,
        )
        state = apply_fill(
            state,
            fill=_fill("b-buy", "BBB", "long", 5, 200),
            policy=self.policy,
        )
        state = apply_fill(
            state,
            fill=_fill("a-sell", "AAA", "short", 4, 120),
            policy=self.policy,
        )

        self.assertEqual(state["cash_minor"], 98_480)
        self.assertEqual(
            state["positions_by_instrument"],
            {
                "AAA": {
                    "position_cost_basis_minor": 600,
                    "position_shares": 6,
                    "realized_pnl_minor": 80,
                },
                "BBB": {
                    "position_cost_basis_minor": 1_000,
                    "position_shares": 5,
                    "realized_pnl_minor": 0,
                },
            },
        )
        self.assertEqual(state["realized_pnl_minor"], 80)

    def test_buy_that_would_make_cash_negative_is_rejected(self) -> None:
        state = build_ledger_state(initial_cash_minor=100)
        with self.assertRaisesRegex(ValueError, "PAPER_CASH_NEGATIVE"):
            apply_fill(
                state,
                fill=_fill("too-large", "AAA", "long", 2, 60),
                policy=self.policy,
            )

    def test_sell_that_would_open_short_position_is_rejected(self) -> None:
        state = build_ledger_state(initial_cash_minor=100_000)
        state = apply_fill(
            state,
            fill=_fill("buy", "AAA", "long", 3, 100),
            policy=self.policy,
        )
        with self.assertRaisesRegex(ValueError, "PAPER_SHORT_SELL_NOT_ALLOWED"):
            apply_fill(
                state,
                fill=_fill("oversell", "AAA", "short", 4, 120),
                policy=self.policy,
            )

    def test_ledger_projects_nonzero_positions_in_instrument_order(self) -> None:
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="multi-symbol",
            instrument_id="AAA",
            symbol="AAA",
            policy=self.policy,
        )
        for fill in (
            _fill("b", "BBB", "long", 5, 200),
            _fill("a", "AAA", "long", 10, 100),
        ):
            ledger._append("FillRecorded", {"fill": fill, "order_id": fill["order_id"]})

        positions = ledger.project_positions()

        self.assertEqual([row["instrument_id"] for row in positions], ["AAA", "BBB"])
        self.assertEqual([row["quantity"] for row in positions], [10, 5])
        self.assertEqual([row["average_fill_minor"] for row in positions], [100, 200])


class CashAccountRiskTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = build_risk_policy(
            initial_cash_minor=100_000,
            max_order_shares=100,
            max_position_shares=500,
            max_order_notional_minor=10_000,
            max_position_notional_minor=50_000,
        )

    def _decision(
        self,
        *,
        direction: str,
        quantity: int,
        position: int = 0,
        cash: int = 100_000,
        reserved_cash: int = 0,
        reserved_sell: int = 0,
        price: int = 1_000,
    ) -> dict:
        return evaluate_risk(
            intent={
                "desired_quantity": quantity,
                "direction": direction,
                "instrument_id": "AAA",
                "intent_id": "risk-intent",
            },
            policy=self.policy,
            kill_switch=KillSwitchState(),
            current_position_shares=position,
            current_cash_minor=cash,
            reserved_cash_minor=reserved_cash,
            reserved_sell_shares=reserved_sell,
            risk_price_minor=price,
            risk_price_source="TEST",
            risk_price_as_of_ns=10,
            risk_price_quality="PASS",
            open_order_count=0,
        )

    def test_buy_resizes_to_cash_available_after_existing_reservations(self) -> None:
        decision = self._decision(
            direction="long",
            quantity=10,
            cash=10_000,
            reserved_cash=4_000,
            price=1_000,
        )
        self.assertEqual(decision["decision"], "RESIZE")
        self.assertEqual(decision["approved_quantity"], 6)
        self.assertIn("RISK_INSUFFICIENT_BUYING_POWER", decision["reason_codes"])
        self.assertEqual(decision["approved_notional_minor"], 6_000)
        self.assertEqual(decision["projected_available_cash_minor"], 0)

    def test_sell_resizes_to_unreserved_owned_shares(self) -> None:
        decision = self._decision(
            direction="short",
            quantity=10,
            position=8,
            reserved_sell=3,
        )
        self.assertEqual(decision["decision"], "RESIZE")
        self.assertEqual(decision["approved_quantity"], 5)
        self.assertIn("RISK_INSUFFICIENT_POSITION", decision["reason_codes"])
        self.assertEqual(decision["projected_position_shares"], 3)

    def test_buy_uses_smallest_share_and_notional_capacity(self) -> None:
        decision = self._decision(
            direction="long",
            quantity=50,
            position=45,
            price=1_000,
        )
        self.assertEqual(decision["approved_quantity"], 5)
        self.assertEqual(
            set(decision["reason_codes"]),
            {"RISK_MAX_ORDER_NOTIONAL_EXCEEDED", "RISK_MAX_POSITION_NOTIONAL_EXCEEDED"},
        )

    def test_zero_capacity_rejects(self) -> None:
        decision = self._decision(
            direction="short",
            quantity=1,
            position=2,
            reserved_sell=2,
        )
        self.assertEqual(decision["decision"], "REJECT")
        self.assertEqual(decision["approved_quantity"], 0)
        self.assertIn("RISK_INSUFFICIENT_POSITION", decision["reason_codes"])

    def test_missing_risk_price_rejects(self) -> None:
        decision = self._decision(direction="long", quantity=1, price=0)
        self.assertEqual(decision["decision"], "REJECT")
        self.assertIn("RISK_PRICE_UNAVAILABLE", decision["reason_codes"])

    def test_working_order_reservations_reduce_after_fill_and_release_at_terminal(self) -> None:
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="reservations",
            instrument_id="AAA",
            symbol="AAA",
            policy=self.policy,
            execution_mode="BROKER_PAPER",
            execution_authority="PAPER_ONLY",
            execution_provider="TEST",
        )
        intent = {
            "client_order_id": "client-1",
            "desired_quantity": 10,
            "direction": "long",
            "idempotency_key": "idem-1",
            "instrument": {"instrument_id": "AAA", "symbol": "AAA"},
            "instrument_id": "AAA",
            "intent_id": "intent-1",
            "side": "BUY",
        }
        decision = {
            "approved_quantity": 10,
            "decision": "APPROVE",
            "estimated_commission_minor": 0,
            "estimated_fee_minor": 0,
            "intent_id": "intent-1",
            "risk_price_minor": 1_000,
        }
        order = {"order_id": "order-1", "quantity": 10, "state": "WORKING"}
        ledger.append_intent(intent)
        ledger.append_risk_decision(decision)
        ledger.append_order(order, intent=intent)

        self.assertEqual(ledger.project_reservations()["reserved_cash_minor"], 10_000)

        ledger._append(
            "FillRecorded",
            {"fill": _fill("partial", "AAA", "long", 4, 900), "order_id": "order-1"},
        )
        ledger.events[-1]["payload"]["fill"]["order_id"] = "order-1"
        self.assertEqual(ledger.project_reservations()["reserved_cash_minor"], 6_000)

        ledger.append_order_state(order_id="order-1", state="FILLED", prior_state="WORKING")
        self.assertEqual(ledger.project_reservations()["reserved_cash_minor"], 0)

    def test_risk_projection_exposes_monetary_limits_and_reservations(self) -> None:
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="risk-projection",
            instrument_id="AAA",
            symbol="AAA",
            policy=self.policy,
        )
        risk = ledger.project_risk()
        self.assertEqual(risk["limits"]["max_order_notional_minor"], 10_000)
        self.assertEqual(risk["limits"]["max_position_notional_minor"], 50_000)
        self.assertEqual(risk["reserved_cash_minor"], 0)
        self.assertEqual(risk["reserved_sell_shares"], 0)


class _RecordingBrokerProvider:
    def __init__(self) -> None:
        self.intents: list[dict] = []

    def place_order(self, intent: dict) -> ProviderResult:
        self.intents.append(dict(intent))
        return ProviderResult(status="error", reason_code="TEST_REJECT")


class _StatusBrokerProvider:
    def __init__(self, initial_status: dict, polled_status: dict) -> None:
        self.initial_status = initial_status
        self.polled_status = polled_status

    def place_order(self, intent: dict) -> ProviderResult:
        del intent
        return ProviderResult(
            status="ok",
            events=[{"broker_event_type": "ORDER_STATUS", "payload": self.initial_status}],
        )

    def fetch_order(self, broker_order_id: str) -> ProviderResult:
        del broker_order_id
        return ProviderResult(
            status="ok",
            events=[{"broker_event_type": "ORDER_STATUS", "payload": self.polled_status}],
        )


class BrokerExecutionRiskTests(unittest.TestCase):
    def _ledger(self) -> PaperExecutionLedger:
        return PaperExecutionLedger.open_session(
            replay_session_id="broker-risk",
            instrument_id="AAA",
            symbol="AAA",
            policy=build_risk_policy(
                initial_cash_minor=100_000,
                max_order_shares=100,
                max_position_shares=500,
                max_order_notional_minor=10_000,
                max_position_notional_minor=50_000,
            ),
            execution_mode="BROKER_PAPER",
            execution_authority="PAPER_ONLY",
            execution_provider="TEST",
        )

    def test_market_reserve_uses_fresh_mark_plus_five_percent_and_sends_resize(self) -> None:
        provider = _RecordingBrokerProvider()
        result = submit_broker_paper_order(
            ledger=self._ledger(),
            provider=provider,
            instrument={"instrument_id": "AAA", "symbol": "AAA"},
            side="BUY",
            quantity=20,
            observation_time=10_000_000_000,
            client_order_id="broker-resize",
            idempotency_key="broker-resize",
            mark_snapshot={
                "instrument_id": "AAA",
                "mark_as_of_ns": 9_000_000_000,
                "mark_minor": 1_000,
                "mark_provider": "TEST",
                "mark_quality": "PASS",
            },
        )

        self.assertEqual(result["decision"], "RESIZE")
        self.assertEqual(provider.intents[0]["desired_quantity"], 9)
        risk = [
            event["payload"]["decision"]
            for event in self._ledger().events
            if event["event_type"] == "RiskDecisionRecorded"
        ]
        self.assertEqual(provider.intents[0]["desired_quantity"], 9)

    def test_stale_market_mark_rejects_before_provider_call(self) -> None:
        provider = _RecordingBrokerProvider()
        result = submit_broker_paper_order(
            ledger=self._ledger(),
            provider=provider,
            instrument={"instrument_id": "AAA", "symbol": "AAA"},
            side="BUY",
            quantity=1,
            observation_time=10_000_000_000,
            client_order_id="broker-stale",
            idempotency_key="broker-stale",
            mark_snapshot={
                "instrument_id": "AAA",
                "mark_as_of_ns": 1,
                "mark_minor": 1_000,
                "mark_provider": "TEST",
                "mark_quality": "PASS",
            },
        )

        self.assertTrue(result["rejected"])
        self.assertIn("RISK_PRICE_STALE", result["reason_codes"])
        self.assertEqual(provider.intents, [])

    def test_limit_order_uses_limit_as_risk_price_without_mark(self) -> None:
        provider = _RecordingBrokerProvider()
        result = submit_broker_paper_order(
            ledger=self._ledger(),
            provider=provider,
            instrument={"instrument_id": "AAA", "symbol": "AAA"},
            side="BUY",
            quantity=10,
            observation_time=10_000_000_000,
            client_order_id="broker-limit",
            idempotency_key="broker-limit",
            order_type="LIMIT",
            limit_price_minor=1_000,
        )
        self.assertEqual(result["decision"], "APPROVE")
        self.assertEqual(provider.intents[0]["desired_quantity"], 10)

    def test_overreported_broker_fill_is_rejected_before_lifecycle_mutation(self) -> None:
        provider = _StatusBrokerProvider(
            {
                "broker_order_id": "broker-order",
                "status": "working",
                "event_time_ns": 10,
                "receive_time_ns": 11,
            },
            {
                "broker_order_id": "broker-order",
                "status": "filled",
                "event_time_ns": 20,
                "receive_time_ns": 21,
                "filled_quantity": 11,
                "fills": [
                    {
                        "broker_fill_id": "fill-too-large",
                        "quantity": 11,
                        "price_minor": 1_000,
                        "event_time_ns": 20,
                        "receive_time_ns": 21,
                    }
                ],
            },
        )
        ledger = self._ledger()
        submitted = submit_broker_paper_order(
            ledger=ledger,
            provider=provider,
            instrument={"instrument_id": "AAA", "symbol": "AAA"},
            side="BUY",
            quantity=10,
            observation_time=10,
            client_order_id="overreported",
            idempotency_key="overreported",
            order_type="LIMIT",
            limit_price_minor=1_000,
        )
        self.assertEqual(submitted["order"]["state"], "WORKING")

        with self.assertRaisesRegex(ValueError, "BROKER_FILL_QUANTITY_EXCEEDS_APPROVED"):
            apply_broker_status_event(
                ledger=ledger,
                provider=provider,
                order_id=submitted["order_id"],
            )

        self.assertEqual(ledger.lookup_order(submitted["order_id"])["state"], "WORKING")
        self.assertEqual(ledger.project_fills(), [])


class ReplayInstrumentIntegrityTests(unittest.TestCase):
    def test_fixture_replay_rejects_bars_for_a_different_instrument(self) -> None:
        store = SimpleNamespace(
            data_mode="FIXTURE_REPLAY",
            bars_for_execution=lambda: [
                {
                    "available_time": 2,
                    "instrument_id": "BBB",
                    "bar_payload": {"high": "10.00", "low": "9.00", "volume": 100},
                }
            ],
        )
        with self.assertRaisesRegex(ValueError, "PAPER_INSTRUMENT_DATA_UNAVAILABLE"):
            _bars_for_paper_execution(store, instrument_id="AAA")


class PortfolioValuationTests(unittest.TestCase):
    def _ledger(self, *, live: bool = True) -> PaperExecutionLedger:
        policy = build_risk_policy(initial_cash_minor=100_000)
        ledger = PaperExecutionLedger.open_session(
            replay_session_id="valuation",
            instrument_id="AAA",
            symbol="AAA",
            policy=policy,
            data_mode="LIVE_OBSERVATIONAL" if live else "FIXTURE_REPLAY",
        )
        for fill in (
            _fill("a", "AAA", "long", 10, 100),
            _fill("b", "BBB", "long", 5, 200),
        ):
            ledger._append("FillRecorded", {"fill": fill, "order_id": fill["order_id"]})
        return ledger

    def test_account_aggregates_complete_multi_symbol_valuation(self) -> None:
        ledger = self._ledger()
        ledger.apply_live_mark(
            instrument_id="AAA",
            mark_minor=110,
            mark_provider="TEST",
            mark_as_of_ns=10,
            mark_quality="PASS",
        )
        ledger.apply_live_mark(
            instrument_id="BBB",
            mark_minor=180,
            mark_provider="TEST",
            mark_as_of_ns=10,
            mark_quality="PASS",
        )

        account = ledger.project_account()

        self.assertEqual(account["market_value_minor"], 2_000)
        self.assertEqual(account["gross_exposure_minor"], 2_000)
        self.assertEqual(account["unrealized_pnl_minor"], 0)
        self.assertEqual(account["equity_minor"], 100_000)
        self.assertEqual(account["valuation_quality"], "COMPLETE")
        self.assertEqual(account["valuation_reasons"], [])

    def test_account_marks_totals_unavailable_when_one_position_has_no_mark(self) -> None:
        ledger = self._ledger()
        ledger.apply_live_mark(
            instrument_id="AAA",
            mark_minor=110,
            mark_provider="TEST",
            mark_as_of_ns=10,
            mark_quality="PASS",
        )

        account = ledger.project_account()

        self.assertIsNone(account["market_value_minor"])
        self.assertIsNone(account["gross_exposure_minor"])
        self.assertIsNone(account["unrealized_pnl_minor"])
        self.assertIsNone(account["equity_minor"])
        self.assertEqual(account["valuation_quality"], "INCOMPLETE")
        self.assertEqual(account["valuation_reasons"], ["MARK_UNAVAILABLE:BBB"])

    def test_position_exposes_reserved_and_available_to_sell(self) -> None:
        ledger = self._ledger(live=False)
        intent = {
            "client_order_id": "sell-client",
            "desired_quantity": 4,
            "direction": "short",
            "idempotency_key": "sell-key",
            "instrument": {"instrument_id": "AAA", "symbol": "AAA"},
            "instrument_id": "AAA",
            "intent_id": "sell-intent",
            "side": "SELL",
        }
        ledger.append_intent(intent)
        ledger.append_risk_decision(
            {
                "approved_quantity": 4,
                "decision": "APPROVE",
                "intent_id": "sell-intent",
                "risk_price_minor": 100,
            }
        )
        ledger.append_order({"order_id": "sell-order", "quantity": 4, "state": "WORKING"}, intent=intent)

        position = ledger.project_positions()[0]

        self.assertEqual(position["reserved_sell_shares"], 4)
        self.assertEqual(position["available_to_sell"], 6)


class _SnapshotRepository:
    def __init__(self, snapshot: dict | None = None) -> None:
        self.snapshot = snapshot
        self.saved_projection: dict | None = None

    def persist_paper_events(self, **_kwargs) -> None:
        return None

    def save_snapshot(self, *, projection: dict, **_kwargs) -> None:
        self.saved_projection = projection

    def load_snapshot(self, _session_id: str) -> dict | None:
        return self.snapshot


class PaperPersistenceCompatibilityTests(unittest.TestCase):
    def _ledger(self) -> PaperExecutionLedger:
        return PaperExecutionLedger.open_session(
            replay_session_id="persist",
            instrument_id="AAA",
            symbol="AAA",
        )

    def _row(self, ledger: PaperExecutionLedger) -> dict:
        return session_record_from_ledger(ledger)

    def test_persisted_snapshot_contains_marks_by_instrument(self) -> None:
        ledger = self._ledger()
        ledger.apply_live_mark(
            instrument_id="AAA",
            mark_minor=100,
            mark_provider="TEST",
            mark_as_of_ns=10,
            mark_quality="PASS",
        )
        ledger.apply_live_mark(
            instrument_id="BBB",
            mark_minor=200,
            mark_provider="TEST",
            mark_as_of_ns=11,
            mark_quality="PASS",
        )
        repo = _SnapshotRepository()
        with patch("market_platform_foundation.local_state.startup.open_local_state", return_value=repo):
            persist_ledger(ledger)
        self.assertEqual(set(repo.saved_projection["marks_by_instrument"]), {"AAA", "BBB"})

    def test_restore_loads_multi_instrument_and_legacy_mark_snapshots(self) -> None:
        source = self._ledger()
        row = self._row(source)
        multi_repo = _SnapshotRepository(
            {
                "marks_by_instrument": {
                    "AAA": {
                        "mark_as_of_ns": 10,
                        "mark_minor": 100,
                        "mark_provider": "TEST",
                        "mark_quality": "PASS",
                    },
                    "BBB": {
                        "mark_as_of_ns": 11,
                        "mark_minor": 200,
                        "mark_provider": "TEST",
                        "mark_quality": "PASS",
                    },
                }
            }
        )
        with patch("market_platform_foundation.local_state.startup.open_local_state", return_value=multi_repo):
            restored = ledger_from_session(row, source.events, {})
        self.assertEqual(restored._mark_for_instrument("BBB")["mark_minor"], 200)

        legacy_repo = _SnapshotRepository(
            {
                "live_mark_as_of_ns": 12,
                "live_mark_minor": 125,
                "live_mark_provider": "LEGACY",
                "live_mark_quality": "PASS",
            }
        )
        with patch("market_platform_foundation.local_state.startup.open_local_state", return_value=legacy_repo):
            legacy = ledger_from_session(row, source.events, {})
        self.assertEqual(legacy._mark_for_instrument("AAA")["mark_minor"], 125)

    def test_policy_identity_mismatch_is_not_resume_compatible(self) -> None:
        ledger = self._ledger()
        stored = self._row(ledger)
        current = self._row(ledger)
        stored["policy"] = {**stored["policy"], "risk_policy_identity_hash": "legacy"}
        self.assertFalse(compatible_resume(stored=stored, current=current))

    def test_restore_counts_submitted_order_as_open_and_rebuilds_reservation(self) -> None:
        source = self._ledger()
        intent = {
            "client_order_id": "restore-client",
            "desired_quantity": 2,
            "direction": "long",
            "idempotency_key": "restore-key",
            "instrument": {"instrument_id": "AAA", "symbol": "AAA"},
            "instrument_id": "AAA",
            "intent_id": "restore-intent",
            "side": "BUY",
        }
        source.append_intent(intent)
        source.append_risk_decision(
            {
                "approved_quantity": 2,
                "decision": "APPROVE",
                "intent_id": "restore-intent",
                "risk_price_minor": 100,
            }
        )
        source.append_order(
            {"order_id": "restore-order", "quantity": 2, "state": "SUBMITTED"},
            intent=intent,
        )
        with patch(
            "market_platform_foundation.local_state.startup.open_local_state",
            return_value=_SnapshotRepository(),
        ):
            restored = ledger_from_session(self._row(source), source.events, {})
        self.assertEqual(restored.open_order_count, 1)
        self.assertEqual(restored.project_reservations()["reserved_cash_minor"], 200)

    def test_legacy_short_history_remains_readable(self) -> None:
        source = self._ledger()
        source._append(
            "FillRecorded",
            {"fill": _fill("legacy-short", "AAA", "short", 2, 100), "order_id": "legacy-order"},
        )
        row = self._row(source)
        legacy_policy = dict(row["policy"])
        legacy_policy.pop("cash_account", None)
        legacy_policy.pop("long_only", None)
        legacy_policy["policy_version"] = "phase7.bar-conservative/1.0.0"
        legacy_policy["risk_policy_identity_hash"] = "legacy"
        row["policy"] = legacy_policy
        with patch(
            "market_platform_foundation.local_state.startup.open_local_state",
            return_value=_SnapshotRepository(),
        ):
            restored = ledger_from_session(row, source.events, {})
        positions = restored.project_positions()
        self.assertEqual(positions[0]["quantity"], -2)
        self.assertEqual(positions[0]["side"], "SHORT")


if __name__ == "__main__":
    unittest.main()

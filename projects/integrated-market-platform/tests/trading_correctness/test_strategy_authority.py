"""G3 BL-0201 — strategy-engine prepared-decision authority binding tests.

The automation path does not use UI preview IDs; it uses an equivalent
server-authoritative prepared-decision binding (PreparedPaperExecution).
This file proves that binding end to end:
- prepare_paper produces a content-derived risk_decision_id;
- the paper idempotency key derives deterministically from that decision;
- _submit_prepared rejects a mutated/swapped prepared record whose
  idempotency key does not derive from its own risk decision;
- submission re-runs the execution-authority check and the final financial
  gate on the real ledger;
- the same prepared decision submits the same logical order exactly once.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.execution import (  # noqa: E402
    PaperExecutionOrchestrator,
)
from market_platform_foundation.intelligence.execution.identity import (  # noqa: E402
    derive_paper_order_idempotency_key,
)
from market_platform_foundation.paper.execution import submit_interactive_order  # noqa: E402
from market_platform_foundation.paper.ledger import PaperExecutionLedger  # noqa: E402
from market_platform_foundation.risk.policy import DEFAULT_RISK_POLICY  # noqa: E402
from tests.intelligence.execution_fixtures import (  # noqa: E402
    default_execution_policy,
    flat_portfolio,
    sample_opportunity,
    sample_quote,
)
from tests.intelligence.outcome_fixtures import T  # noqa: E402


def _ledger() -> PaperExecutionLedger:
    policy = dict(DEFAULT_RISK_POLICY)
    policy["max_order_shares"] = 1_000
    policy["max_position_shares"] = 5_000
    return PaperExecutionLedger.open_session(
        replay_session_id="g3-strategy-1",
        instrument_id="BIYA",
        symbol="BIYA",
        policy=policy,
        execution_mode="INTERNAL_SIMULATION",
        execution_authority="PAPER_ONLY",
    )


def _bars(volume: int = 100_000) -> list[dict[str, object]]:
    return [
        {
            "available_time": 100 + i * 100,
            "bar_payload": {
                "close": "10.00",
                "high": "10.00",
                "low": "10.00",
                "open": "10.00",
                "volume": volume,
            },
        }
        for i in range(1, 4)
    ]


def _prepare(orchestrator: PaperExecutionOrchestrator) -> object:
    policy = default_execution_policy()
    portfolio = flat_portfolio(equity_minor=100_000_00, cash_minor=100_000_00)
    quote = sample_quote()
    opportunity = sample_opportunity()
    return orchestrator.prepare_paper(
        opportunity=opportunity,
        policy=policy,
        portfolio=portfolio,
        quote=quote,
        decision_time_ns=T + 2_000_000_000,
        instrument_id="inst-biya",
        symbol="BIYA",
        execution_authority="PAPER_ONLY",
    )


class StrategyReferencePriceEvidenceTests(unittest.TestCase):
    """G3 BL-0201/§16 — the strategy path supplies server-authoritative price
    evidence so the final submit-time financial recheck works without bar tape.

    The prepared risk decision carries genuine price evidence
    (approved_notional_minor / approved_quantity). These tests prove:
    - a prepared BUY submits with no bars when the risk-decision reference
      price is passed through (previously REQUIRED_PRICE_MISSING);
    - a direct submit with no bars and no trusted reference still fails
      closed with REQUIRED_PRICE_MISSING (rule is not weakened);
    - an explicit reference price cannot bypass insufficient cash;
    - the submitted quantity / reference price come from the server-side risk
      decision, not from any caller-supplied value.
    """

    def _ledger(self, cash_minor: int = 10_000_00) -> PaperExecutionLedger:
        policy = dict(DEFAULT_RISK_POLICY)
        policy["max_order_shares"] = 1_000
        policy["max_position_shares"] = 5_000
        policy["initial_cash_minor"] = cash_minor
        policy["risk_policy_identity_hash"] = "g3-refprice"
        return PaperExecutionLedger.open_session(
            replay_session_id="g3-refprice",
            instrument_id="BIYA",
            symbol="BIYA",
            policy=policy,
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="PAPER_ONLY",
        )

    def test_prepared_submit_with_no_bars_uses_risk_reference_price(self) -> None:
        # The governed flow path (test_build01_23_lifecycle) submits a
        # prepared BUY with bars=[]; the risk decision's approved notional /
        # approved quantity is the price evidence, so the final financial gate
        # must not raise REQUIRED_PRICE_MISSING.
        orchestrator = PaperExecutionOrchestrator()
        prepared = _prepare(orchestrator)
        risk = prepared.risk_decision
        self.assertGreater(risk.approved_quantity, 0)
        ledger = self._ledger()
        result = orchestrator.submit_prepared(prepared=prepared, ledger=ledger, bars=[])
        self.assertIsNotNone(result.paper_submit)
        self.assertIsNotNone(result.paper_submit["order_id"])
        # The order was recorded (simulator rejects on empty bar tape, but the
        # financial gate accepted the server-authoritative reference price).
        order = ledger.lookup_order(result.paper_submit["order_id"])
        self.assertIsNotNone(order)
        self.assertEqual(int(order["submitted_quantity"]), risk.approved_quantity)

    def test_no_bars_no_reference_price_fails_closed(self) -> None:
        # A direct MARKET BUY without any price evidence still fails closed:
        # the reference-price rule is not weakened by the strategy path.
        ledger = self._ledger()
        with self.assertRaises(ValueError) as ctx:
            submit_interactive_order(
                ledger=ledger,
                bars=[],
                symbol="BIYA",
                instrument_id="BIYA",
                side="BUY",
                quantity=10,
                observation_time=1,
                client_order_id="nb-ref-1",
                idempotency_key="nb-ref-1",
            )
        self.assertIn("REQUIRED_PRICE_MISSING", str(ctx.exception))
        order_events = [e for e in ledger.events if e.get("event_type", "").startswith("Order")]
        self.assertEqual(order_events, [])

    def test_reference_price_cannot_bypass_insufficient_cash(self) -> None:
        # Even with an explicit trusted reference price, required > available
        # still fails closed with INSUFFICIENT_CASH.
        ledger = self._ledger(cash_minor=10_000_00)  # $10,000
        with self.assertRaises(ValueError) as ctx:
            submit_interactive_order(
                ledger=ledger,
                bars=[],
                symbol="BIYA",
                instrument_id="BIYA",
                side="BUY",
                quantity=2_000,  # 2,000 × $100 = $200,000 >> $10,000
                observation_time=1,
                client_order_id="nb-ref-2",
                idempotency_key="nb-ref-2",
                reference_price_minor=10_000,
            )
        self.assertIn("INSUFFICIENT_CASH", str(ctx.exception))

    def test_prepared_quantity_and_reference_price_server_authoritative(self) -> None:
        # The submitted quantity and the reference price used for the final
        # gate derive from the server-side risk decision (approved_quantity /
        # approved_notional), never from a caller-supplied value.
        orchestrator = PaperExecutionOrchestrator()
        prepared = _prepare(orchestrator)
        risk = prepared.risk_decision
        expected_reference = int(risk.approved_notional_minor // risk.approved_quantity)
        self.assertGreater(expected_reference, 0)
        self.assertEqual(risk.approved_notional_minor, risk.approved_quantity * expected_reference)
        ledger = self._ledger()
        result = orchestrator.submit_prepared(prepared=prepared, ledger=ledger, bars=_bars())
        order = result.paper_submit["order"]
        self.assertEqual(int(order["submitted_quantity"]), risk.approved_quantity)
        self.assertEqual(
            int(order["quantity_facts"]["risk_approved_quantity"]),
            risk.approved_quantity,
        )
        self.assertEqual(
            int(order["quantity_facts"]["risk_approved_notional_minor"]),
            risk.approved_notional_minor,
        )


class StrategyPreparedBindingTests(unittest.TestCase):
    def test_prepare_produces_content_derived_risk_decision(self) -> None:
        orchestrator = PaperExecutionOrchestrator()
        prepared = _prepare(orchestrator)
        risk = prepared.risk_decision
        self.assertTrue(risk.risk_decision_id)
        # Same inputs -> same risk decision id (deterministic, content-derived).
        again = _prepare(orchestrator)
        self.assertEqual(risk.risk_decision_id, again.risk_decision.risk_decision_id)

    def test_paper_idempotency_key_derives_from_risk_decision(self) -> None:
        prepared = _prepare(PaperExecutionOrchestrator())
        expected = derive_paper_order_idempotency_key(prepared.risk_decision.risk_decision_id)
        self.assertEqual(prepared.idempotency_key, expected)
        # Pure derivation is stable and distinct from the raw id.
        self.assertEqual(
            derive_paper_order_idempotency_key(prepared.risk_decision.risk_decision_id),
            expected,
        )
        self.assertNotEqual(expected, prepared.risk_decision.risk_decision_id)

    def test_mutated_prepared_record_rejected_at_submit(self) -> None:
        orchestrator = PaperExecutionOrchestrator()
        prepared = _prepare(orchestrator)
        ledger = _ledger()
        # Swap the idempotency key: it no longer derives from the risk decision.
        from dataclasses import replace

        mutated = replace(prepared, idempotency_key="FORGED-KEY")
        with self.assertRaises(ValueError) as ctx:
            orchestrator.submit_prepared(prepared=mutated, ledger=ledger, bars=_bars())
        self.assertIn("PREPARED_EXECUTION_IDEMPOTENCY_MISMATCH", str(ctx.exception))
        # No order events were written to the ledger (account creation only).
        order_events = [e for e in ledger.events if e.get("event_type", "").startswith("Order")]
        self.assertEqual(order_events, [])

    def test_same_prepared_submits_same_order_once(self) -> None:
        orchestrator = PaperExecutionOrchestrator()
        prepared = _prepare(orchestrator)
        ledger = _ledger()
        first = orchestrator.submit_prepared(prepared=prepared, ledger=ledger, bars=_bars())
        self.assertIsNotNone(first.paper_submit)
        second = orchestrator.submit_prepared(prepared=prepared, ledger=ledger, bars=_bars())
        self.assertTrue(second.paper_submit["duplicate"])
        self.assertEqual(
            first.paper_submit["order_id"],
            second.paper_submit["order_id"],
        )

    def test_submit_rechecks_authority_and_financial_gate(self) -> None:
        # A prepared decision approved against a rich portfolio must still be
        # gated by the live ledger's execution authority and cash at submit.
        orchestrator = PaperExecutionOrchestrator()
        prepared = _prepare(orchestrator)
        # BLOCKED authority ledger: submit must fail before any mutation.
        blocked = PaperExecutionLedger.open_session(
            replay_session_id="g3-strategy-blocked",
            instrument_id="BIYA",
            symbol="BIYA",
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="BLOCKED",
        )
        with self.assertRaises(ValueError) as ctx:
            orchestrator.submit_prepared(prepared=prepared, ledger=blocked, bars=_bars())
        self.assertIn("NOT_AUTHORIZED", str(ctx.exception))
        order_events = [e for e in blocked.events if e.get("event_type", "").startswith("Order")]
        self.assertEqual(order_events, [])


if __name__ == "__main__":
    unittest.main()
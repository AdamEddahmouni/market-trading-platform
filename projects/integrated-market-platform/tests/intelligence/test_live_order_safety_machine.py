"""Live order lifecycle + preflight control contracts (zero-submit)."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.live_execution_safety import (
    LIVE_ORDER_TERMINAL_STATES,
    BrokerOrderStateKind,
    LiveOrderSafetyMachine,
    LivePreflightControlId,
    LivePreflightDisposition,
    LiveSubmitForbiddenError,
    evaluate_buying_power,
    evaluate_live_preflight_bundle,
    evaluate_malformed_order,
    evaluate_market_state,
    evaluate_maximum_order_size,
    evaluate_operator_confirmation,
    evaluate_price_freshness,
    validate_live_order_transition,
)

T = 1_700_000_000_000_000_000


class LiveOrderLifecycleTests(unittest.TestCase):
    def test_ack_partial_fill_cancel_path(self) -> None:
        machine = LiveOrderSafetyMachine(client_order_id="coid-1", order_quantity=10)
        machine.advance(BrokerOrderStateKind.DRY_RUN_VALIDATED, event="dry_run")
        machine.advance(BrokerOrderStateKind.SUBMISSION_PENDING, event="local_intent")
        machine.advance(BrokerOrderStateKind.ACKNOWLEDGED, event="ack")
        machine.advance(BrokerOrderStateKind.OPEN, event="open")
        machine.advance(
            BrokerOrderStateKind.PARTIALLY_FILLED,
            event="partial",
            filled_delta=4,
        )
        self.assertEqual(machine.filled_quantity, 4)
        machine.advance(BrokerOrderStateKind.CANCEL_PENDING, event="cancel_req")
        machine.advance(BrokerOrderStateKind.CANCELLED, event="cancelled")
        self.assertIn(machine.state, LIVE_ORDER_TERMINAL_STATES)

    def test_rejected_from_pending(self) -> None:
        machine = LiveOrderSafetyMachine(client_order_id="coid-2", order_quantity=5)
        machine.advance(BrokerOrderStateKind.DRY_RUN_VALIDATED, event="dry_run")
        machine.advance(BrokerOrderStateKind.SUBMISSION_PENDING, event="local_intent")
        machine.advance(BrokerOrderStateKind.REJECTED, event="reject")
        self.assertEqual(machine.state, BrokerOrderStateKind.REJECTED)

    def test_invalid_transition_fail_closed(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            validate_live_order_transition(
                prior_state=BrokerOrderStateKind.CREATED,
                next_state=BrokerOrderStateKind.FILLED,
            )
        self.assertIn("LIVE_ORDER_TRANSITION_INVALID", str(ctx.exception))

    def test_terminal_blocks_further_advance(self) -> None:
        machine = LiveOrderSafetyMachine(client_order_id="coid-3", order_quantity=1)
        machine.advance(BrokerOrderStateKind.DRY_RUN_VALIDATED, event="dry_run")
        machine.advance(BrokerOrderStateKind.SUBMISSION_PENDING, event="local_intent")
        machine.advance(BrokerOrderStateKind.ACKNOWLEDGED, event="ack")
        machine.advance(BrokerOrderStateKind.FILLED, event="fill", filled_delta=1)
        with self.assertRaises(ValueError) as ctx:
            machine.advance(BrokerOrderStateKind.CANCEL_PENDING, event="late_cancel")
        self.assertIn("LIVE_ORDER_TRANSITION_FROM_TERMINAL", str(ctx.exception))

    def test_disconnect_marks_unknown_reconcile_required_submit_still_refused(self) -> None:
        """Disconnect marks UNKNOWN + reconcile_required; submit stays forbidden.

        Unlike restart_blocked, disconnect does not freeze in-process ``advance``
        by itself — valid reconcile recoveries from UNKNOWN remain allowed.
        """
        machine = LiveOrderSafetyMachine(client_order_id="coid-4", order_quantity=3)
        machine.advance(BrokerOrderStateKind.DRY_RUN_VALIDATED, event="dry_run")
        machine.advance(BrokerOrderStateKind.SUBMISSION_PENDING, event="local_intent")
        machine.advance(BrokerOrderStateKind.ACKNOWLEDGED, event="ack")
        machine.advance(BrokerOrderStateKind.OPEN, event="open")
        machine.record_disconnect()
        self.assertEqual(machine.state, BrokerOrderStateKind.UNKNOWN)
        self.assertTrue(machine.reconcile_required)
        self.assertFalse(machine.restart_blocked)
        # Disconnect does not freeze lifecycle advance the way restart does.
        machine.advance(BrokerOrderStateKind.OPEN, event="reconciled_open")
        self.assertEqual(machine.state, BrokerOrderStateKind.OPEN)
        self.assertFalse(machine.reconcile_required)
        with self.assertRaises(LiveSubmitForbiddenError):
            machine.attempt_network_submit()

    def test_fill_delta_quantity_guards(self) -> None:
        machine = LiveOrderSafetyMachine(client_order_id="coid-fill", order_quantity=10)
        machine.advance(BrokerOrderStateKind.DRY_RUN_VALIDATED, event="dry_run")
        machine.advance(BrokerOrderStateKind.SUBMISSION_PENDING, event="local_intent")
        machine.advance(BrokerOrderStateKind.ACKNOWLEDGED, event="ack")
        machine.advance(BrokerOrderStateKind.OPEN, event="open")

        # Valid partial / fill deltas.
        machine.advance(
            BrokerOrderStateKind.PARTIALLY_FILLED,
            event="partial",
            filled_delta=4,
        )
        self.assertEqual(machine.filled_quantity, 4)

        # Zero-delta claimed partial: still enforce consistency (4 < 10 OK).
        machine.advance(
            BrokerOrderStateKind.PARTIALLY_FILLED,
            event="partial_zero_delta",
            filled_delta=0,
        )
        self.assertEqual(machine.filled_quantity, 4)

        # Overfill via positive delta.
        with self.assertRaises(ValueError) as overfill_ctx:
            machine.advance(
                BrokerOrderStateKind.PARTIALLY_FILLED,
                event="overfill",
                filled_delta=7,
            )
        self.assertIn("LIVE_ORDER_OVERFILL", str(overfill_ctx.exception))
        self.assertEqual(machine.filled_quantity, 4)
        self.assertEqual(machine.state, BrokerOrderStateKind.PARTIALLY_FILLED)

        # Terminal FILLED quantity consistency (including zero-delta mismatch).
        with self.assertRaises(ValueError) as mismatch_ctx:
            machine.advance(
                BrokerOrderStateKind.FILLED,
                event="fill_zero_delta_mismatch",
                filled_delta=0,
            )
        self.assertIn("LIVE_ORDER_FILL_QUANTITY_MISMATCH", str(mismatch_ctx.exception))
        machine.advance(
            BrokerOrderStateKind.FILLED,
            event="fill_complete",
            filled_delta=6,
        )
        self.assertEqual(machine.state, BrokerOrderStateKind.FILLED)
        self.assertEqual(machine.filled_quantity, 10)

    def test_restart_restore_blocks_until_operator_resume(self) -> None:
        machine = LiveOrderSafetyMachine(client_order_id="coid-5")
        machine.restore_after_restart(
            state=BrokerOrderStateKind.SUBMISSION_STATUS_UNKNOWN,
            order_quantity=2,
        )
        self.assertTrue(machine.restart_blocked)
        with self.assertRaises(ValueError) as ctx:
            machine.advance(BrokerOrderStateKind.ACKNOWLEDGED, event="auto")
        self.assertIn("LIVE_ORDER_RESTART_BLOCKED", str(ctx.exception))
        machine.operator_resume_after_restart()
        machine.advance(BrokerOrderStateKind.ACKNOWLEDGED, event="reconciled_ack")
        self.assertEqual(machine.state, BrokerOrderStateKind.ACKNOWLEDGED)

    def test_attempt_network_submit_always_refused(self) -> None:
        machine = LiveOrderSafetyMachine(client_order_id="coid-6", order_quantity=1)
        machine.advance(BrokerOrderStateKind.DRY_RUN_VALIDATED, event="dry_run")
        with self.assertRaises(LiveSubmitForbiddenError):
            machine.attempt_network_submit()


class LivePreflightControlTests(unittest.TestCase):
    def test_price_freshness_stale_blocks(self) -> None:
        finding = evaluate_price_freshness(
            reference_price_minor=150_00,
            quote_as_of_ns=T - 10_000_000_000,
            decision_time_ns=T,
            max_age_ns=1_000_000_000,
        )
        self.assertEqual(finding.disposition, LivePreflightDisposition.BLOCK)
        self.assertEqual(finding.reason_code, "QUOTE_STALE")

    def test_buying_power_unavailable_fail_closed(self) -> None:
        finding = evaluate_buying_power(
            required_notional_minor=1000,
            buying_power_minor=None,
        )
        self.assertEqual(finding.disposition, LivePreflightDisposition.FAIL_CLOSED)
        self.assertEqual(finding.reason_code, "BUYING_POWER_UNAVAILABLE")

    def test_market_state_closed_blocks(self) -> None:
        finding = evaluate_market_state(session_state="CLOSED")
        self.assertEqual(finding.disposition, LivePreflightDisposition.BLOCK)

    def test_malformed_limit_without_price(self) -> None:
        finding = evaluate_malformed_order(
            side="BUY",
            order_type="LIMIT",
            quantity=1,
            limit_price_minor=None,
        )
        self.assertEqual(finding.reason_code, "LIMIT_PRICE_REQUIRED")

    def test_max_order_size_exceeded(self) -> None:
        finding = evaluate_maximum_order_size(quantity=101, max_quantity=100)
        self.assertEqual(finding.reason_code, "MAX_ORDER_SIZE_EXCEEDED")

    def test_operator_confirmation_missing(self) -> None:
        finding = evaluate_operator_confirmation(
            confirmation_present=False,
            confirmation_expired=False,
            confirmation_matches_intent=False,
        )
        self.assertEqual(finding.reason_code, "OPERATOR_CONFIRMATION_MISSING")

    def test_bundle_never_allows_network_submit(self) -> None:
        report = evaluate_live_preflight_bundle(
            reference_price_minor=150_00,
            quote_as_of_ns=T - 100,
            decision_time_ns=T,
            max_quote_age_ns=1_000_000_000,
            quantity=1,
            max_quantity=10,
            required_notional_minor=150_00,
            buying_power_minor=1_000_000,
            session_state="RTH_OPEN",
            side="BUY",
            order_type="MARKET",
            limit_price_minor=None,
            confirmation_present=True,
            confirmation_expired=False,
            confirmation_matches_intent=True,
        )
        self.assertFalse(report.allows_network_submit)
        self.assertTrue(report.blocked)
        codes = {f.reason_code for f in report.findings}
        self.assertIn("BUILD28_LIVE_SUBMIT_FORBIDDEN", codes)
        self.assertEqual(
            report.findings[-1].control_id,
            LivePreflightControlId.FAIL_CLOSED,
        )


if __name__ == "__main__":
    unittest.main()

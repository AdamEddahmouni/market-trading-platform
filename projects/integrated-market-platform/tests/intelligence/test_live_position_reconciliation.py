"""Live position reconciliation contract (zero-submit, fail closed)."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.live_execution_safety import (
    BrokerPositionObservationV1,
    ImpPositionTruthV1,
    LivePositionReconciliationGate,
    LiveSubmitForbiddenError,
    PositionReconciliationState,
)
from market_platform_foundation.intelligence.live_execution_safety.dry_run import (
    GLOBAL_ZERO_SUBMIT_GUARD,
)

T = 1_700_000_000_000_000_000
MAX_AGE_NS = 5_000_000_000


def _imp(*, instrument_id: str = "AAPL", quantity: int = 10, open_quantity: int = 0) -> ImpPositionTruthV1:
    return ImpPositionTruthV1(
        instrument_id=instrument_id,
        quantity=quantity,
        open_quantity=open_quantity,
        as_of_ns=T,
    )


def _broker(
    *,
    instrument_id: str = "AAPL",
    quantity: int = 10,
    snapshot_id: str = "snap-1",
    as_of_ns: int = T,
    freshness: str = "FRESH",
) -> BrokerPositionObservationV1:
    return BrokerPositionObservationV1(
        instrument_id=instrument_id,
        quantity=quantity,
        as_of_ns=as_of_ns,
        snapshot_id=snapshot_id,
        freshness=freshness,
    )


class LivePositionReconciliationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = LivePositionReconciliationGate(max_broker_age_ns=MAX_AGE_NS)
        self.assertFalse(self.gate.allows_network_submit)
        self.assertTrue(self.gate.reconciliation_required)
        self.assertFalse(self.gate.allows_subsequent_live_action)

    def test_match(self) -> None:
        result = self.gate.reconcile(
            imp_positions=(_imp(),),
            broker_snapshot=_broker(),
            decision_time_ns=T,
        )
        self.assertEqual(result.state, PositionReconciliationState.MATCH)
        self.assertFalse(result.allows_network_submit)
        self.assertIn("POSITION_QUANTITY_MATCH", result.reason_codes)

    def test_quantity_mismatch(self) -> None:
        result = self.gate.reconcile(
            imp_positions=(_imp(quantity=10),),
            broker_snapshot=_broker(quantity=7),
            decision_time_ns=T,
        )
        self.assertEqual(result.state, PositionReconciliationState.QUANTITY_MISMATCH)
        self.assertTrue(self.gate.reconciliation_required)
        self.assertFalse(self.gate.allows_subsequent_live_action)
        self.assertFalse(result.allows_network_submit)

    def test_partial_fill_quantity_still_open(self) -> None:
        result = self.gate.reconcile(
            imp_positions=(_imp(quantity=4, open_quantity=6),),
            broker_snapshot=_broker(quantity=4),
            decision_time_ns=T,
        )
        self.assertEqual(result.state, PositionReconciliationState.PARTIAL_FILL_OPEN)
        self.assertTrue(self.gate.reconciliation_required)
        self.assertFalse(result.allows_network_submit)

    def test_stale_broker_snapshot_refused(self) -> None:
        result = self.gate.reconcile(
            imp_positions=(_imp(),),
            broker_snapshot=_broker(as_of_ns=T - MAX_AGE_NS - 1, freshness="STALE"),
            decision_time_ns=T,
        )
        self.assertEqual(result.state, PositionReconciliationState.STALE)
        self.assertIn("BROKER_SNAPSHOT_STALE", result.reason_codes)
        self.assertTrue(self.gate.reconciliation_required)
        # Stale must not be treated as truth / match.
        self.assertNotEqual(result.state, PositionReconciliationState.MATCH)

    def test_stale_by_age_even_if_freshness_label_fresh(self) -> None:
        result = self.gate.reconcile(
            imp_positions=(_imp(),),
            broker_snapshot=_broker(as_of_ns=T - MAX_AGE_NS - 1, freshness="FRESH"),
            decision_time_ns=T,
        )
        self.assertEqual(result.state, PositionReconciliationState.STALE)

    def test_duplicate_replayed_snapshot_idempotent(self) -> None:
        first = self.gate.reconcile(
            imp_positions=(_imp(),),
            broker_snapshot=_broker(snapshot_id="snap-dup"),
            decision_time_ns=T,
        )
        second = self.gate.reconcile(
            imp_positions=(_imp(),),
            broker_snapshot=_broker(snapshot_id="snap-dup"),
            decision_time_ns=T,
        )
        self.assertEqual(first, second)
        self.assertEqual(self.gate.applied_snapshot_ids, ("snap-dup",))
        self.assertEqual(self.gate.apply_count_for("snap-dup"), 1)

    def test_unknown_external_position_unresolved_mismatch(self) -> None:
        result = self.gate.reconcile(
            imp_positions=(),
            broker_snapshot=_broker(instrument_id="XYZ", quantity=3),
            decision_time_ns=T,
        )
        self.assertEqual(result.state, PositionReconciliationState.UNKNOWN_EXTERNAL_POSITION)
        self.assertIn("UNKNOWN_EXTERNAL_POSITION", result.reason_codes)
        self.assertTrue(self.gate.reconciliation_required)
        # Must not silently adopt the broker position into IMP truth.
        self.assertEqual(self.gate.imp_truth_instruments(), ())

    def test_missing_broker_snapshot_is_not_a_match(self) -> None:
        result = self.gate.reconcile(
            imp_positions=(_imp(),),
            broker_snapshot=None,
            decision_time_ns=T,
        )
        self.assertEqual(result.state, PositionReconciliationState.MISSING_BROKER_SNAPSHOT)
        self.assertNotEqual(result.state, PositionReconciliationState.MATCH)
        self.assertTrue(self.gate.reconciliation_required)

    def test_startup_mismatch_fail_closed_requires_ack_before_live_action(self) -> None:
        mismatch = self.gate.reconcile(
            imp_positions=(_imp(quantity=10),),
            broker_snapshot=_broker(quantity=1, snapshot_id="snap-mm"),
            decision_time_ns=T,
        )
        self.assertEqual(mismatch.state, PositionReconciliationState.QUANTITY_MISMATCH)
        self.assertTrue(self.gate.reconciliation_required)
        self.assertFalse(self.gate.allows_subsequent_live_action)

        # Operator ack records audit but does not clear mismatch block or authorize submit.
        ack = self.gate.acknowledge_operator(
            note="operator saw mismatch",
            decision_time_ns=T + 1,
        )
        self.assertTrue(ack.recorded)
        self.assertFalse(ack.allows_network_submit)
        self.assertFalse(self.gate.allows_network_submit)
        self.assertTrue(self.gate.reconciliation_required)
        self.assertFalse(self.gate.allows_subsequent_live_action)

        # After match + operator acknowledgement, subsequent live action may be modeled
        # as allowed — but network submit remains forbidden.
        match = self.gate.reconcile(
            imp_positions=(_imp(quantity=10),),
            broker_snapshot=_broker(quantity=10, snapshot_id="snap-ok"),
            decision_time_ns=T + 2,
        )
        self.assertEqual(match.state, PositionReconciliationState.MATCH)
        self.assertFalse(self.gate.reconciliation_required)
        self.assertFalse(self.gate.allows_subsequent_live_action)

        ack2 = self.gate.acknowledge_operator(
            note="startup reconcile matched",
            decision_time_ns=T + 3,
        )
        self.assertTrue(ack2.recorded)
        self.assertTrue(self.gate.allows_subsequent_live_action)
        self.assertFalse(self.gate.allows_network_submit)
        self.assertFalse(ack2.allows_network_submit)

        with self.assertRaises(LiveSubmitForbiddenError):
            self.gate.attempt_network_submit()

    def test_operator_ack_never_authorizes_network_submit(self) -> None:
        self.gate.reconcile(
            imp_positions=(_imp(),),
            broker_snapshot=_broker(snapshot_id="snap-ok2"),
            decision_time_ns=T,
        )
        ack = self.gate.acknowledge_operator(note="ack", decision_time_ns=T + 1)
        self.assertFalse(ack.allows_network_submit)
        self.assertFalse(self.gate.allows_network_submit)
        with self.assertRaises(LiveSubmitForbiddenError):
            self.gate.attempt_network_submit()
        GLOBAL_ZERO_SUBMIT_GUARD.assert_zero()


if __name__ == "__main__":
    unittest.main()

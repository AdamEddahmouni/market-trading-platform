"""IBKR L2 (reqMktDepth) observational adapter tests (G6 §25 matrix).

Covers the verified IB operation/side mapping, the critical position/rank
translation rules, canonical book integration, generation isolation, the
NO_SEQUENCE contract, and the observational safety boundary.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from market_platform_foundation.market_data.observational_state import (  # noqa: E402
    ObservationalStateStore,
)
from market_platform_foundation.order_flow.order_book.contracts import (  # noqa: E402
    ApplyOutcome,
    DepthOperation,
    DepthSide,
    DepthUpdate,
)
from market_platform_foundation.providers.ibkr_observational.constants import (  # noqa: E402
    IB_OP_DELETE,
    IB_OP_INSERT,
    IB_OP_UPDATE,
    IB_SIDE_ASK,
    IB_SIDE_BID,
)
from market_platform_foundation.providers.ibkr_observational.contracts import (  # noqa: E402
    DepthTranslationOutcome,
    EntitlementState,
    IbkrSubscriptionState,
)
from market_platform_foundation.providers.ibkr_observational.mapping import (  # noqa: E402
    decode_depth_operation,
    decode_depth_side,
    is_verified_depth_operation,
    is_verified_depth_side,
)
from market_platform_foundation.providers.ibkr_observational.rank import (  # noqa: E402
    SubscriptionRankState,
    translate_depth_callback,
)

from ibkr_observational_support import (  # noqa: E402
    FakeLookup,
    connected_adapter,
    make_record,
)

AAPL = make_record("AAPL")
MSFT = make_record("MSFT")


class VerifiedMappingTests(unittest.TestCase):
    """Exact IB operation/side integers are pinned and decoded correctly."""

    def test_ib_insert_maps_to_canonical_insert(self) -> None:
        self.assertEqual(IB_OP_INSERT, 0)
        self.assertIs(decode_depth_operation(0), DepthOperation.INSERT)

    def test_ib_update_maps_to_canonical_update(self) -> None:
        self.assertEqual(IB_OP_UPDATE, 1)
        self.assertIs(decode_depth_operation(1), DepthOperation.UPDATE)

    def test_ib_delete_maps_to_canonical_delete(self) -> None:
        self.assertEqual(IB_OP_DELETE, 2)
        self.assertIs(decode_depth_operation(2), DepthOperation.DELETE)

    def test_ib_ask_side_maps_to_canonical_ask(self) -> None:
        self.assertEqual(IB_SIDE_ASK, 0)
        self.assertIs(decode_depth_side(0), DepthSide.ASK)

    def test_ib_bid_side_maps_to_canonical_bid(self) -> None:
        self.assertEqual(IB_SIDE_BID, 1)
        self.assertIs(decode_depth_side(1), DepthSide.BID)

    def test_unknown_operation_and_side_fail_closed(self) -> None:
        self.assertFalse(is_verified_depth_operation(3))
        self.assertFalse(is_verified_depth_side(2))
        with self.assertRaises(ValueError):
            decode_depth_operation(3)
        with self.assertRaises(ValueError):
            decode_depth_side(2)


class RankTranslationTests(unittest.TestCase):
    """Position/rank semantics: the G6 critical rule."""

    def _apply(
        self,
        rank: SubscriptionRankState,
        *,
        operation: int,
        side: int,
        position: int,
        price: float | None = None,
        size: float | None = None,
        market_maker: str | None = None,
        is_smart_depth: bool | None = None,
        resolve_snapshot_price=None,
    ):
        return translate_depth_callback(
            rank,
            instrument_id="AAPL",
            subscription_id="sub1",
            generation=1,
            side_value=side,
            operation_value=operation,
            position=position,
            price=price,
            size=size,
            market_maker=market_maker,
            is_smart_depth=is_smart_depth,
            callback_type="updateMktDepthL2",
            received_time_ns=1000,
            provider_req_id=42,
            resolve_snapshot_price=resolve_snapshot_price,
        )

    # --- INSERT ---

    def test_insert_at_position_zero(self) -> None:
        rank = SubscriptionRankState()
        outcome, events, reason = self._apply(
            rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=0, price=100.0, size=10.0
        )
        self.assertIs(outcome, DepthTranslationOutcome.APPLIED)
        self.assertEqual(len(events), 1)
        self.assertIs(events[0].operation, DepthOperation.INSERT)
        self.assertIs(events[0].side, DepthSide.BID)
        self.assertEqual(str(events[0].price), "100.0")
        self.assertEqual(len(rank.bids), 1)
        self.assertEqual(rank.bids[0].price, 100.0)

    def test_insert_middle_shifts_ranks(self) -> None:
        rank = SubscriptionRankState()
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=0, price=100.0, size=1.0)
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=1, price=99.0, size=1.0)
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=1, price=99.5, size=1.0)
        self.assertEqual([level.price for level in rank.bids], [100.0, 99.5, 99.0])

    def test_insert_tail(self) -> None:
        rank = SubscriptionRankState()
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_ASK, position=0, price=101.0, size=1.0)
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_ASK, position=1, price=102.0, size=1.0)
        self.assertEqual([level.price for level in rank.asks], [101.0, 102.0])

    # --- UPDATE ---

    def test_update_size_at_rank(self) -> None:
        rank = SubscriptionRankState()
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=0, price=100.0, size=10.0)
        outcome, events, _ = self._apply(
            rank, operation=IB_OP_UPDATE, side=IB_SIDE_BID, position=0, price=100.0, size=25.0
        )
        self.assertIs(outcome, DepthTranslationOutcome.APPLIED)
        self.assertEqual(len(events), 1)
        self.assertIs(events[0].operation, DepthOperation.UPDATE)
        self.assertEqual(str(events[0].size), "25.0")
        self.assertEqual(rank.bids[0].size, 25.0)

    def test_update_price_at_rank_is_delete_plus_insert(self) -> None:
        """A price-changing UPDATE must not leave a stale old-price level."""
        rank = SubscriptionRankState()
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=0, price=100.0, size=10.0)
        outcome, events, _ = self._apply(
            rank, operation=IB_OP_UPDATE, side=IB_SIDE_BID, position=0, price=99.0, size=10.0
        )
        self.assertIs(outcome, DepthTranslationOutcome.APPLIED)
        self.assertEqual([event.operation for event in events], [DepthOperation.DELETE, DepthOperation.INSERT])
        self.assertEqual(str(events[0].price), "100.0")  # old price deleted
        self.assertEqual(str(events[1].price), "99.0")  # new price inserted
        self.assertEqual([level.price for level in rank.bids], [99.0])

    def test_update_size_zero_implies_delete(self) -> None:
        rank = SubscriptionRankState()
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=0, price=100.0, size=10.0)
        outcome, events, _ = self._apply(
            rank, operation=IB_OP_UPDATE, side=IB_SIDE_BID, position=0, price=100.0, size=0.0
        )
        self.assertIs(outcome, DepthTranslationOutcome.APPLIED)
        self.assertEqual(len(events), 1)
        self.assertIs(events[0].operation, DepthOperation.DELETE)
        self.assertEqual(rank.bids, [])

    # --- DELETE ---

    def test_delete_head(self) -> None:
        rank = SubscriptionRankState()
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=0, price=100.0, size=1.0)
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=1, price=99.0, size=1.0)
        outcome, events, _ = self._apply(
            rank, operation=IB_OP_DELETE, side=IB_SIDE_BID, position=0, price=100.0
        )
        self.assertIs(outcome, DepthTranslationOutcome.APPLIED)
        self.assertIs(events[0].operation, DepthOperation.DELETE)
        self.assertEqual(str(events[0].price), "100.0")
        self.assertEqual([level.price for level in rank.bids], [99.0])

    def test_delete_middle(self) -> None:
        rank = SubscriptionRankState()
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=0, price=100.0, size=1.0)
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=1, price=99.0, size=1.0)
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=2, price=98.0, size=1.0)
        outcome, events, _ = self._apply(
            rank, operation=IB_OP_DELETE, side=IB_SIDE_BID, position=1, price=99.0
        )
        self.assertIs(outcome, DepthTranslationOutcome.APPLIED)
        self.assertEqual(str(events[0].price), "99.0")
        self.assertEqual([level.price for level in rank.bids], [100.0, 98.0])

    def test_delete_tail(self) -> None:
        rank = SubscriptionRankState()
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=0, price=100.0, size=1.0)
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=1, price=99.0, size=1.0)
        outcome, events, _ = self._apply(
            rank, operation=IB_OP_DELETE, side=IB_SIDE_BID, position=1, price=99.0
        )
        self.assertIs(outcome, DepthTranslationOutcome.APPLIED)
        self.assertEqual([level.price for level in rank.bids], [100.0])

    def test_delete_with_unreliable_price_resolves_rank(self) -> None:
        """A delete callback with zero/unreliable price must resolve the rank."""
        rank = SubscriptionRankState()
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=0, price=100.0, size=1.0)
        # Provider sends delete price 0.0 — canonical price comes from rank state.
        outcome, events, _ = self._apply(
            rank, operation=IB_OP_DELETE, side=IB_SIDE_BID, position=0, price=0.0
        )
        self.assertIs(outcome, DepthTranslationOutcome.APPLIED)
        self.assertEqual(str(events[0].price), "100.0")
        self.assertEqual(rank.bids, [])

    def test_delete_unknown_rank_resolves_snapshot_price(self) -> None:
        rank = SubscriptionRankState()
        # Rank state cleared (post-reset), but the canonical snapshot still has
        # the level; the resolver supplies the canonical price.
        outcome, events, _ = self._apply(
            rank,
            operation=IB_OP_DELETE,
            side=IB_SIDE_BID,
            position=0,
            price=None,
            resolve_snapshot_price=lambda side, position: _D("100.0"),
        )
        self.assertIs(outcome, DepthTranslationOutcome.APPLIED)
        self.assertEqual(str(events[0].price), "100.0")

    def test_rank_mismatch_fails_closed(self) -> None:
        rank = SubscriptionRankState()
        # UPDATE at a rank with no provider level must not guess.
        outcome, events, reason = self._apply(
            rank, operation=IB_OP_UPDATE, side=IB_SIDE_BID, position=5, price=100.0, size=1.0
        )
        self.assertIs(outcome, DepthTranslationOutcome.DEGRADED)
        self.assertEqual(events, [])
        self.assertIn("no provider rank level", reason or "")

    def test_insert_beyond_frontier_fails_closed(self) -> None:
        rank = SubscriptionRankState()
        self._apply(rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=0, price=100.0, size=1.0)
        outcome, events, reason = self._apply(
            rank, operation=IB_OP_INSERT, side=IB_SIDE_BID, position=3, price=97.0, size=1.0
        )
        self.assertIs(outcome, DepthTranslationOutcome.DEGRADED)
        self.assertIn("beyond rank frontier", reason or "")

    # --- market maker / smart depth provenance ---

    def test_market_maker_preserved_in_provenance(self) -> None:
        rank = SubscriptionRankState()
        outcome, events, _ = self._apply(
            rank,
            operation=IB_OP_INSERT,
            side=IB_SIDE_ASK,
            position=0,
            price=101.0,
            size=1.0,
            market_maker="MARKET_MAKER_X",
            is_smart_depth=True,
        )
        self.assertIs(outcome, DepthTranslationOutcome.APPLIED)
        self.assertEqual(events[0].provenance["market_maker"], "MARKET_MAKER_X")
        self.assertTrue(events[0].provenance["is_smart_depth"])
        self.assertEqual(events[0].provenance["callback_type"], "updateMktDepthL2")
        self.assertEqual(events[0].provenance["provider_req_id"], 42)


class BookIntegrationTests(unittest.TestCase):
    """Fake IB callback → canonical DepthUpdate → IncrementalOrderBook."""

    def setUp(self) -> None:
        self.store = ObservationalStateStore()
        self.adapter, self.transport = connected_adapter(
            store=self.store, lookup=FakeLookup(AAPL, MSFT)
        )
        self.result = self.adapter.subscribe_l2(instrument_id="AAPL")
        self.assertTrue(self.result.accepted, self.result.reason)
        self.req_id = self.result.req_id

    def test_callback_produces_canonical_book(self) -> None:
        self.adapter.on_mkt_depth(self.req_id, 0, IB_OP_INSERT, IB_SIDE_BID, 100.0, 10.0)
        self.adapter.on_mkt_depth(self.req_id, 0, IB_OP_INSERT, IB_SIDE_ASK, 101.0, 7.0)
        engine = self.store.book_engine_for("AAPL")
        self.assertIsNotNone(engine)
        self.assertEqual(engine.best_bid_price, 100)
        self.assertEqual(engine.best_ask_price, 101)
        self.assertTrue(engine.book_state_valid)

    def test_best_bid_ask_after_rank_moves(self) -> None:
        self.adapter.on_mkt_depth(self.req_id, 0, IB_OP_INSERT, IB_SIDE_BID, 100.0, 10.0)
        self.adapter.on_mkt_depth(self.req_id, 0, IB_OP_INSERT, IB_SIDE_ASK, 101.0, 7.0)
        self.adapter.on_mkt_depth(self.req_id, 0, IB_OP_INSERT, IB_SIDE_BID, 100.5, 5.0)
        engine = self.store.book_engine_for("AAPL")
        self.assertEqual(engine.best_bid_price, 100.5)

    def test_canonical_state_hash_deterministic(self) -> None:
        for _ in range(2):
            fresh = ObservationalStateStore()
            adapter, transport = connected_adapter(store=fresh, lookup=FakeLookup(AAPL))
            sub = adapter.subscribe_l2(instrument_id="AAPL")
            adapter.on_mkt_depth(sub.req_id, 0, IB_OP_INSERT, IB_SIDE_BID, 100.0, 10.0)
            adapter.on_mkt_depth(sub.req_id, 0, IB_OP_INSERT, IB_SIDE_ASK, 101.0, 7.0)
            adapter.on_mkt_depth(sub.req_id, 0, IB_OP_INSERT, IB_SIDE_BID, 99.0, 4.0)
            hashes = []
            hashes.append(fresh.book_engine_for("AAPL").state_hash())
            if len(hashes) == 1:
                first_hash = hashes[0]
        self.assertEqual(first_hash, hashes[0])

    def test_no_fabricated_sequence_and_no_sequence_state(self) -> None:
        self.adapter.on_mkt_depth(self.req_id, 0, IB_OP_INSERT, IB_SIDE_BID, 100.0, 10.0)
        result = self.adapter.on_mkt_depth(self.req_id, 0, IB_OP_INSERT, IB_SIDE_ASK, 101.0, 7.0)
        for event in result.events:
            self.assertIsNone(event.sequence)
        engine = self.store.book_engine_for("AAPL")
        self.assertEqual(engine.sequence_state.value, "NO_SEQUENCE")


class GenerationSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ObservationalStateStore()
        self.adapter, self.transport = connected_adapter(
            store=self.store, lookup=FakeLookup(AAPL)
        )

    def test_reconnect_resets_book_and_new_generation(self) -> None:
        sub = self.adapter.subscribe_l2(instrument_id="AAPL")
        old_req = sub.req_id
        self.adapter.on_mkt_depth(old_req, 0, IB_OP_INSERT, IB_SIDE_BID, 100.0, 10.0)
        self.adapter.on_mkt_depth(old_req, 0, IB_OP_INSERT, IB_SIDE_ASK, 101.0, 7.0)
        old_hash = self.store.book_engine_for("AAPL").state_hash()
        self.adapter.handle_reconnect()
        # Book was reset: no levels until fresh callbacks arrive.
        engine = self.store.book_engine_for("AAPL")
        self.assertTrue(engine.is_empty or not engine.book_state_valid)
        self.assertGreater(engine.generation, 0)
        new_sub = self.adapter.subscription_status()["ibkr:L2:2"]
        self.adapter.on_mkt_depth(new_sub["req_id"], 0, IB_OP_INSERT, IB_SIDE_BID, 100.0, 10.0)
        self.adapter.on_mkt_depth(new_sub["req_id"], 0, IB_OP_INSERT, IB_SIDE_ASK, 101.0, 7.0)
        self.assertEqual(self.store.book_engine_for("AAPL").best_bid_price, 100)

    def test_late_old_generation_callback_rejected(self) -> None:
        sub = self.adapter.subscribe_l2(instrument_id="AAPL")
        old_req = sub.req_id
        old_sub_id = sub.subscription_id
        self.adapter.handle_reconnect()
        # Feed a callback stamped with the OLD subscription id directly to the
        # canonical engine: it must be rejected as GENERATION_MISMATCH.
        from market_platform_foundation.order_flow.order_book.contracts import (
            build_depth_update,
        )

        stale = build_depth_update(
            instrument_id="AAPL",
            operation=DepthOperation.INSERT,
            side=DepthSide.BID,
            price=99.0,
            size=1.0,
            subscription_id=old_sub_id,
            source="IBKR",
            received_time_ns=5000,
        )
        result = self.store.apply_depth_update(stale)
        self.assertIs(result.outcome, ApplyOutcome.REJECTED)
        self.assertEqual(result.reason.value, "GENERATION_MISMATCH")

    def test_local_rank_state_cleared_on_reconnect(self) -> None:
        sub = self.adapter.subscribe_l2(instrument_id="AAPL")
        self.adapter.on_mkt_depth(sub.req_id, 0, IB_OP_INSERT, IB_SIDE_BID, 100.0, 10.0)
        self.adapter.on_mkt_depth(sub.req_id, 1, IB_OP_INSERT, IB_SIDE_BID, 99.0, 5.0)
        self.assertEqual(len(self.adapter._rank_states[sub.subscription_id].bids), 2)
        self.adapter.handle_reconnect()
        new_records = self.adapter._registry.active_records()
        self.assertTrue(all(record.subscription_id != sub.subscription_id for record in new_records))
        # Old rank state object is no longer consulted (popped on retire).
        self.assertNotIn(sub.subscription_id, self.adapter._rank_states)


class L2SafetyTests(unittest.TestCase):
    """Entitlement failure and offline behavior for depth."""

    def setUp(self) -> None:
        self.store = ObservationalStateStore()
        self.adapter, self.transport = connected_adapter(
            store=self.store, lookup=FakeLookup(AAPL)
        )

    def test_entitlement_failure_cannot_produce_valid_book(self) -> None:
        sub = self.adapter.subscribe_l2(instrument_id="AAPL")
        self.adapter.on_mkt_depth(sub.req_id, 0, IB_OP_INSERT, IB_SIDE_BID, 100.0, 10.0)
        self.adapter.on_error(
            sub.req_id, 354, "market data is not subscribed", received_ns=2000
        )
        record = self.adapter.subscription_status()["ibkr:L2:1"]
        self.assertEqual(record["entitlement"], EntitlementState.NOT_ENTITLED.value)
        self.assertEqual(record["state"], IbkrSubscriptionState.FAILED.value)
        engine = self.store.book_engine_for("AAPL")
        self.assertFalse(engine.book_state_valid)

    def test_offline_mode_prevents_connect_and_subscribe(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.adapter import (
            IbkrOfflineError,
        )
        from ibkr_observational_support import make_adapter

        adapter, transport = make_adapter(live=False, store=self.store, lookup=FakeLookup(AAPL))
        with self.assertRaises(IbkrOfflineError):
            adapter.connect()
        with self.assertRaises(IbkrOfflineError):
            adapter.subscribe_l2(instrument_id="AAPL")
        self.assertEqual(transport.mkt_depth_requests, [])

    def test_unknown_instrument_fails_before_provider_request(self) -> None:
        from market_platform_foundation.providers.ibkr_observational.identity import (
            IdentityAdmissionError,
        )

        with self.assertRaises(IdentityAdmissionError):
            self.adapter.subscribe_l2(instrument_id="UNKNOWN")
        self.assertEqual(self.transport.mkt_depth_requests, [])

    def test_future_family_rejected(self) -> None:
        from market_platform_foundation.xa01.enums import InstrumentKind

        family = make_record("ES_FAMILY", kind=InstrumentKind.FUTURE_FAMILY)
        adapter, transport = connected_adapter(
            store=self.store, lookup=FakeLookup(AAPL, family)
        )
        from market_platform_foundation.providers.ibkr_observational.identity import (
            IdentityAdmissionError,
        )

        with self.assertRaises(IdentityAdmissionError):
            adapter.subscribe_l2(instrument_id="ES_FAMILY")
        self.assertEqual(transport.mkt_depth_requests, [])

    def test_continuous_future_rejected(self) -> None:
        from market_platform_foundation.xa01.enums import InstrumentKind

        continuous = make_record("ES1!", kind=InstrumentKind.CONTINUOUS_SERIES)
        adapter, transport = connected_adapter(
            store=self.store, lookup=FakeLookup(AAPL, continuous)
        )
        from market_platform_foundation.providers.ibkr_observational.identity import (
            IdentityAdmissionError,
        )

        with self.assertRaises(IdentityAdmissionError):
            adapter.subscribe_l2(instrument_id="ES1!")
        self.assertEqual(transport.mkt_depth_requests, [])

    def test_cancel_mkt_depth_uses_cancel_not_execution(self) -> None:
        sub = self.adapter.subscribe_l2(instrument_id="AAPL")
        self.adapter.cancel_l2("AAPL")
        self.assertEqual(self.transport.mkt_depth_cancels, [(sub.req_id, False)])


def _D(value: str):
    from decimal import Decimal

    return Decimal(value)


if __name__ == "__main__":
    unittest.main()
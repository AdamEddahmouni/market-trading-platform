"""Live observational as_of, attention admission, and ranked-book honesty."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from market_platform_foundation.ui_api.opportunity_projections import (
    apply_opportunity_ack,
    build_opportunities_summary_payload,
)
from market_platform_foundation.ui_api.operator_opportunity_state import reset_operator_acks
from market_platform_foundation.ui_api.projections import (
    LIVE_AS_OF_UNAVAILABLE,
    REPLAY_SHELF_LABEL,
    build_as_of_context,
    build_attention_page,
    build_quality_summary,
    is_fixture_rth_attention_id,
)
from market_platform_foundation.ui_api.store import ReplayStore

from tests.ui1.test_ui_api import COLLECTION_ROOT


class LiveObservationalStateTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_operator_acks()
        self.store = ReplayStore(collection_root=COLLECTION_ROOT)
        self.store.load()
        self.store.data_mode = "LIVE_OBSERVATIONAL"
        self.store.mode = "LIVE"
        self._runtime_patch = patch(
            "market_platform_foundation.market_data.live_runtime.get_live_runtime",
            return_value=None,
        )
        self._runtime_patch.start()

    def tearDown(self) -> None:
        self._runtime_patch.stop()

    def test_live_as_of_without_quotes_is_unavailable_not_fixture(self) -> None:
        as_of = build_as_of_context(self.store)
        quality = build_quality_summary(self.store)
        self.assertEqual(as_of["as_of_time"], LIVE_AS_OF_UNAVAILABLE)
        self.assertEqual(as_of["as_of_provenance"], "UNAVAILABLE")
        self.assertNotIn("2026-07-21", str(as_of["as_of_time"]))
        self.assertNotIn("fixture", str(quality.get("detail") or "").lower())
        self.assertEqual(quality["state"], "UNAVAILABLE")
        self.assertEqual(quality["detail"], "LIVE_OBSERVATIONAL_NO_LIVE_RECEIVE_TIME")

    def test_live_as_of_uses_admitted_receive_time(self) -> None:
        self.store.last_source_time_ns = 1_779_000_000_000_000_000
        as_of = build_as_of_context(self.store)
        quality = build_quality_summary(self.store)
        self.assertNotEqual(as_of["as_of_time"], LIVE_AS_OF_UNAVAILABLE)
        self.assertEqual(as_of["as_of_provenance"], "LIVE_RECEIVE")
        self.assertNotIn("2026-07-21", str(as_of["as_of_time"]))
        self.assertNotIn("admitted equity intraday fixture", str(quality.get("detail") or "").lower())

    def test_live_attention_excludes_fixture_cards_from_current_items(self) -> None:
        page = build_attention_page(self.store, limit=50)
        current_ids = [item.get("attention_id") for item in (page.get("items") or [])]
        self.assertFalse(any(is_fixture_rth_attention_id(item_id) for item_id in current_ids))
        self.assertNotIn("att-replay-context", current_ids)
        self.assertFalse(any(str(item_id).startswith("att-mc9-") for item_id in current_ids))
        self.assertNotIn("att-futures-es-imbalance", current_ids)
        shelf = page.get("replay_shelf") or []
        self.assertEqual(page.get("replay_shelf_label"), REPLAY_SHELF_LABEL)
        self.assertTrue(shelf)
        for item in shelf:
            self.assertEqual(item.get("attention_shelf"), REPLAY_SHELF_LABEL)
            self.assertEqual(item.get("attention_data_kind"), "FIXTURE_REPLAY")
        shelf_ids = {item.get("attention_id") for item in shelf}
        self.assertIn("att-replay-context", shelf_ids)

    def test_zero_qualifying_live_book_is_empty_not_fixture_unavailable(self) -> None:
        payload = build_opportunities_summary_payload(self.store)
        self.assertEqual(payload["feed_status"], "EMPTY")
        self.assertNotIn("reason", payload)
        self.assertEqual(payload["items"], [])
        self.assertEqual(payload["as_of_context"]["as_of_time"], LIVE_AS_OF_UNAVAILABLE)
        self.assertNotIn("2026-07-21", str(payload["as_of_context"]["as_of_time"]))
        with self.assertRaises(PermissionError) as ack_ctx:
            apply_opportunity_ack(self.store, row_id="any-id", action="DISMISSED")
        self.assertEqual(str(ack_ctx.exception), "LIVE_OBSERVATIONAL_NO_OPPORTUNITY_ENGINE")


if __name__ == "__main__":
    unittest.main()

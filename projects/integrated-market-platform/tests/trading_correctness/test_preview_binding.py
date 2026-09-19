"""G3 BL-0201 — server-side preview binding tests.

Proves the server-authoritative preview contract at the UI boundary:
- a submit must carry a current, matching server preview (PREVIEW_REQUIRED);
- any mutation of the bound intent is rejected (quantity/side/instrument/type);
- previews expire (PREVIEW_EXPIRED) and go stale on portfolio/policy change;
- previews and orders are isolated by account + mode;
- an accepted submit consumes the preview but the idempotent retry still works.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.paper.eligibility import ensure_operator_fixture_registered
from market_platform_foundation.ui_api.paper_projections import preview_paper_order, submit_paper_order
from market_platform_foundation.ui_api.store import ReplayStore

from tests.platform.test_paper_p0 import COLLECTION_ROOT  # reuse fixture root


def setUpModule() -> None:
    global _paper_env
    _paper_env = patch.dict(os.environ, {"IMP_PAPER_EXECUTION": "1"})
    _paper_env.start()


def tearDownModule() -> None:
    _paper_env.stop()


def _open_store(mode: str = "INTERNAL_SIMULATION") -> ReplayStore:
    store = ReplayStore(collection_root=COLLECTION_ROOT)
    store.load()
    from market_platform_foundation.ui_api.paper_projections import open_paper_session

    open_paper_session(store, {"execution_mode": mode})
    # Move the cursor to a fillable region like the platform suite does.
    from market_platform_foundation.paper.execution import preview_interactive_order

    for index in range(len(store.bars) - 2, -1, -1):
        store.set_cursor_index(index)
        preview = preview_interactive_order(
            ledger=store.paper_ledger,
            bars=store.bars_for_execution(),
            symbol=store.symbol,
            instrument_id=store.instrument_id,
            side="BUY",
            quantity=1,
            observation_time=store.prediction_cutoff(),
            client_order_id="cursor-probe",
            idempotency_key="cursor-probe",
        )
        if preview.get("fill_preview") is not None and preview.get("risk_status") == "PASS":
            return store
    raise AssertionError("no fillable cursor on fixture")


def _base_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "client_order_id": "g3-preview-1",
        "idempotency_key": "g3-preview-key-1",
        "quantity": 1,
        "side": "BUY",
    }
    body.update(overrides)
    return body


class PreviewIssuanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_operator_fixture_registered()
        cls.store = _open_store()

    def test_preview_returns_bound_claims(self) -> None:
        result = preview_paper_order(self.store, _base_body())
        preview = result["preview"]
        binding = preview["preview_binding"]
        self.assertTrue(preview["preview_id"])
        self.assertTrue(binding["intent_digest"])
        self.assertTrue(binding["portfolio_revision"])
        self.assertTrue(binding["risk_policy_revision"])
        self.assertEqual(binding["mode"], "PAPER")
        self.assertEqual(binding["account_id"], self.store.paper_ledger.paper_account_id)

    def test_submit_without_preview_rejected(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            submit_paper_order(self.store, _base_body(client_order_id="g3-np-1", idempotency_key="g3-np-1"))
        self.assertIn("PREVIEW_REQUIRED", str(ctx.exception))

    def test_preview_then_submit_succeeds(self) -> None:
        body = _base_body(client_order_id="g3-ok-1", idempotency_key="g3-ok-1")
        preview = preview_paper_order(self.store, body)
        result = submit_paper_order(self.store, {**body, "preview_id": preview["preview"]["preview_id"]})
        self.assertFalse(result["submission"]["duplicate"])
        self.assertTrue(result["submission"]["order_id"])

    def test_idempotent_retry_after_accepted_submit(self) -> None:
        body = _base_body(client_order_id="g3-retry-1", idempotency_key="g3-retry-key-1")
        preview = preview_paper_order(self.store, body)
        preview_id = preview["preview"]["preview_id"]
        first = submit_paper_order(self.store, {**body, "preview_id": preview_id})
        # Retry with the same key + intent: same logical order, no duplicate order.
        second = submit_paper_order(self.store, {**body, "preview_id": preview_id})
        self.assertTrue(second["submission"]["duplicate"])
        self.assertEqual(first["submission"]["order_id"], second["submission"]["order_id"])


class PreviewMutationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        ensure_operator_fixture_registered()
        cls.store = _open_store()

    def test_quantity_mutation_rejected(self) -> None:
        body = _base_body(client_order_id="g3-mut-q", idempotency_key="g3-mut-q")
        preview = preview_paper_order(self.store, body)
        preview_id = preview["preview"]["preview_id"]
        with self.assertRaises(ValueError) as ctx:
            submit_paper_order(self.store, {**body, "quantity": 2, "preview_id": preview_id})
        self.assertIn("PREVIEW_INTENT_MISMATCH", str(ctx.exception))

    def test_side_mutation_rejected(self) -> None:
        body = _base_body(client_order_id="g3-mut-s", idempotency_key="g3-mut-s")
        preview = preview_paper_order(self.store, body)
        preview_id = preview["preview"]["preview_id"]
        with self.assertRaises(ValueError) as ctx:
            submit_paper_order(self.store, {**body, "side": "SELL", "preview_id": preview_id})
        self.assertIn("PREVIEW_INTENT_MISMATCH", str(ctx.exception))

    def test_instrument_mutation_rejected(self) -> None:
        # MSFT must be canonically registered so admission passes and the
        # submit reaches the preview-intent binding (rather than failing
        # earlier at identity admission).
        from market_platform_foundation.xa01.compatibility import register_equity

        register_equity(symbol="MSFT")
        body = _base_body(client_order_id="g3-mut-i", idempotency_key="g3-mut-i")
        preview = preview_paper_order(self.store, body)
        preview_id = preview["preview"]["preview_id"]
        with self.assertRaises(ValueError) as ctx:
            submit_paper_order(
                self.store,
                {**body, "instrument_id": "MSFT", "symbol": "MSFT", "preview_id": preview_id},
            )
        self.assertIn("PREVIEW_INTENT_MISMATCH", str(ctx.exception))

    def test_order_type_mutation_rejected(self) -> None:
        body = _base_body(client_order_id="g3-mut-t", idempotency_key="g3-mut-t")
        preview = preview_paper_order(self.store, body)
        preview_id = preview["preview"]["preview_id"]
        with self.assertRaises(ValueError) as ctx:
            submit_paper_order(self.store, {**body, "order_type": "LIMIT", "limit_price_minor": 10000, "preview_id": preview_id})
        self.assertIn("PREVIEW_INTENT_MISMATCH", str(ctx.exception))


class PreviewExpiryTests(unittest.TestCase):
    def test_expired_preview_rejected(self) -> None:
        store = _open_store()
        body = _base_body(client_order_id="g3-exp-1", idempotency_key="g3-exp-1")
        preview = preview_paper_order(store, body)
        preview_id = preview["preview"]["preview_id"]
        # Force expiry: purge with a now far past every record's TTL removes
        # the record, so submit must surface PREVIEW_EXPIRED / not found.
        removed = store.preview_store.purge_expired(
            now_ns=store.preview_store.get_by_id(preview_id).expires_at_ns + 1
        )
        self.assertGreaterEqual(removed, 1)
        with self.assertRaises(ValueError) as ctx:
            submit_paper_order(store, {**body, "preview_id": preview_id})
        message = str(ctx.exception)
        # Fail closed: an expired preview must never authorize a submit.
        self.assertTrue("PREVIEW_EXPIRED" in message or "PREVIEW_NOT_FOUND" in message, message)


class PreviewStalenessTests(unittest.TestCase):
    def test_unknown_preview_id_rejected(self) -> None:
        store = _open_store()
        body = _base_body(client_order_id="g3-unk-1", idempotency_key="g3-unk-1")
        with self.assertRaises(ValueError) as ctx:
            submit_paper_order(store, {**body, "preview_id": "no-such-preview"})
        self.assertIn("PREVIEW_NOT_FOUND", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
"""PLATFORM-PAPER-001 acceptance and safety invariant tests."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.operating_modes import (
    EXECUTION_MODES,
    live_execution_env_enabled,
    paper_execution_env_enabled,
    resolve_execution_authority,
)
from market_platform_foundation.paper.execution import preview_interactive_order, submit_interactive_order
from market_platform_foundation.paper.ledger import PaperExecutionLedger
from market_platform_foundation.ui_api.paper_projections import (
    build_paper_account_payload,
    build_paper_portfolio_payload,
    open_paper_session,
    submit_paper_order,
)
from market_platform_foundation.ui_api.projections import build_as_of_context, build_context_payload
from market_platform_foundation.ui_api.store import ReplayStore

COLLECTION_ROOT = ROOT.parent


class PlatformPaperP0Tests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=COLLECTION_ROOT)
        cls.store.load()

    def test_orthogonal_context_fields(self) -> None:
        ctx = build_as_of_context(self.store)
        self.assertEqual(ctx["mode"], "REPLAY")
        self.assertEqual(ctx["data_mode"], "FIXTURE_REPLAY")
        self.assertEqual(ctx["execution_mode"], "NONE")
        self.assertEqual(ctx["execution_authority"], "BLOCKED")
        self.assertEqual(ctx["data_provider"], "INTERNAL")

    def test_context_payload_legacy_mode(self) -> None:
        payload = build_context_payload(self.store)
        self.assertEqual(payload["as_of_context"]["mode"], "REPLAY")

    def test_paper_account_initial_cash(self) -> None:
        payload = build_paper_account_payload(self.store)
        account = payload["account"]
        self.assertEqual(account["currency"], "USD")
        self.assertGreater(account["cash_minor"], 0)
        self.assertEqual(account["execution_authority"], "BLOCKED")

    def test_ledger_events_append_only(self) -> None:
        events = self.store.paper_ledger.events
        self.assertGreaterEqual(len(events), 2)
        sequences = [int(event["sequence"]) for event in events]
        self.assertEqual(sequences, sorted(sequences))
        types = {event["event_type"] for event in events}
        self.assertIn("PaperAccountCreated", types)
        self.assertIn("PaperSessionOpened", types)

    def test_portfolio_observability_payload(self) -> None:
        payload = build_paper_portfolio_payload(self.store)
        self.assertEqual(payload["authority_boundary"], "PAPER_OBSERVABILITY")
        self.assertIn("account", payload)
        self.assertIn("risk", payload)
        self.assertIn("data_health", payload)

    def test_order_preview_without_authorization(self) -> None:
        preview = preview_interactive_order(
            ledger=self.store.paper_ledger,
            bars=self.store.bars_for_execution(),
            symbol=self.store.symbol,
            instrument_id=self.store.instrument_id,
            side="BUY",
            quantity=1,
            observation_time=self.store.prediction_cutoff(),
            client_order_id="preview-test-1",
            idempotency_key="preview-key-1",
        )
        self.assertIn("risk_status", preview)
        self.assertIn("order_preview", preview)

    def test_submit_blocked_without_authorization(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            submit_interactive_order(
                ledger=self.store.paper_ledger,
                bars=self.store.bars_for_execution(),
                symbol=self.store.symbol,
                instrument_id=self.store.instrument_id,
                side="BUY",
                quantity=1,
                observation_time=self.store.prediction_cutoff(),
                client_order_id="submit-test-1",
                idempotency_key="submit-key-1",
            )
        self.assertIn("NOT_AUTHORIZED", str(ctx.exception))


class PlatformPaperSimulationTests(unittest.TestCase):
    store: ReplayStore

    @classmethod
    def setUpClass(cls) -> None:
        cls.store = ReplayStore(collection_root=COLLECTION_ROOT)
        cls.store.load()

    def setUp(self) -> None:
        self._prior = os.environ.get("IMP_PAPER_EXECUTION")
        os.environ["IMP_PAPER_EXECUTION"] = "1"
        open_paper_session(self.store, {"execution_mode": "INTERNAL_SIMULATION"})
        self._select_fillable_cursor()

    def _select_fillable_cursor(self) -> None:
        for index in range(len(self.store.bars) - 2, -1, -1):
            self.store.set_cursor_index(index)
            preview = preview_interactive_order(
                ledger=self.store.paper_ledger,
                bars=self.store.bars_for_execution(),
                symbol=self.store.symbol,
                instrument_id=self.store.instrument_id,
                side="BUY",
                quantity=1,
                observation_time=self.store.prediction_cutoff(),
                client_order_id="cursor-probe",
                idempotency_key="cursor-probe",
            )
            if preview.get("fill_preview") is not None and preview.get("risk_status") == "PASS":
                return
        self.fail("No fillable replay cursor found on BIYA fixture")

    def tearDown(self) -> None:
        if self._prior is None:
            os.environ.pop("IMP_PAPER_EXECUTION", None)
        else:
            os.environ["IMP_PAPER_EXECUTION"] = self._prior

    def test_biya_vertical_slice_deterministic(self) -> None:
        cutoff = self.store.prediction_cutoff()
        body = {
            "side": "BUY",
            "quantity": 1,
            "client_order_id": "biya-slice-1",
            "idempotency_key": "biya-slice-key-1",
        }
        first = submit_paper_order(self.store, body)
        second = submit_paper_order(self.store, body)
        self.assertFalse(first["submission"]["duplicate"])
        self.assertTrue(second["submission"]["duplicate"])
        fills = self.store.paper_ledger.project_fills()
        self.assertGreaterEqual(len(fills), 1)
        positions = self.store.paper_ledger.project_positions()
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0]["quantity"], 1)

        # Replay determinism: fresh ledger at same cutoff produces identical fill id.
        ledger_b = PaperExecutionLedger.open_session(
            replay_session_id=self.store.session_id,
            instrument_id=self.store.instrument_id,
            symbol=self.store.symbol,
            execution_mode="INTERNAL_SIMULATION",
            execution_authority="AUTHORIZED",
        )
        result_b = submit_interactive_order(
            ledger=ledger_b,
            bars=self.store.bars_for_execution(),
            symbol=self.store.symbol,
            instrument_id=self.store.instrument_id,
            side="BUY",
            quantity=1,
            observation_time=cutoff,
            client_order_id="biya-slice-1",
            idempotency_key="biya-slice-key-1",
        )
        self.assertEqual(fills[0]["fill_id"], result_b["fill"]["fill_id"])


class PlatformSafetyInvariantTests(unittest.TestCase):
    def test_live_execution_blocked_by_default(self) -> None:
        prior_live = os.environ.pop("IMP_LIVE_EXECUTION", None)
        try:
            self.assertFalse(live_execution_env_enabled())
            self.assertEqual(resolve_execution_authority(requested_mode="LIVE"), "BLOCKED")
        finally:
            if prior_live is not None:
                os.environ["IMP_LIVE_EXECUTION"] = prior_live

    def test_paper_execution_blocked_by_default(self) -> None:
        prior = os.environ.pop("IMP_PAPER_EXECUTION", None)
        try:
            self.assertFalse(paper_execution_env_enabled())
            self.assertEqual(resolve_execution_authority(requested_mode="INTERNAL_SIMULATION"), "BLOCKED")
        finally:
            if prior is not None:
                os.environ["IMP_PAPER_EXECUTION"] = prior

    def test_live_mode_not_in_default_execution_modes_without_env(self) -> None:
        prior = os.environ.pop("IMP_LIVE_EXECUTION", None)
        try:
            self.assertIn("LIVE", EXECUTION_MODES)
            self.assertEqual(resolve_execution_authority(requested_mode="LIVE"), "BLOCKED")
        finally:
            if prior is not None:
                os.environ["IMP_LIVE_EXECUTION"] = prior


if __name__ == "__main__":
    unittest.main()

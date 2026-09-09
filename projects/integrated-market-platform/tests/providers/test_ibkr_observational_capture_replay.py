"""IBKR adapter capture/replay determinism tests (G6 §23).

Proves ``capture → adapter replay → DepthUpdate → IncrementalOrderBook``
produces the same canonical final state/hash as direct fake callbacks, with
no live IB connection (replay subscriptions are registered offline).
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from market_platform_foundation.market_data.observational_state import (  # noqa: E402
    ObservationalStateStore,
)
from market_platform_foundation.providers.ibkr_observational.constants import (  # noqa: E402
    IB_OP_DELETE,
    IB_OP_INSERT,
    IB_OP_UPDATE,
    IB_SIDE_ASK,
    IB_SIDE_BID,
)
from market_platform_foundation.providers.ibkr_observational.contracts import (  # noqa: E402
    CapabilityKind,
)
from market_platform_foundation.providers.ibkr_observational.capture import (  # noqa: E402
    capture_depth_callback,
    capture_error_record,
    redact,
    redact_text,
)

from ibkr_observational_support import (  # noqa: E402
    FakeLookup,
    connected_adapter,
    make_adapter,
    make_record,
)

AAPL = make_record("AAPL")


def _script(req_id: int):
    """A representative depth callback script (bid/ask insert, updates, delete)."""
    return [
        (req_id, 0, IB_OP_INSERT, IB_SIDE_BID, 100.0, 10.0),
        (req_id, 0, IB_OP_INSERT, IB_SIDE_ASK, 101.0, 7.0),
        (req_id, 1, IB_OP_INSERT, IB_SIDE_BID, 99.0, 5.0),
        (req_id, 0, IB_OP_UPDATE, IB_SIDE_BID, 100.0, 12.0),
        (req_id, 0, IB_OP_INSERT, IB_SIDE_BID, 100.5, 3.0),
        (req_id, 1, IB_OP_UPDATE, IB_SIDE_BID, 99.0, 0.0),  # zero-size → delete
        (req_id, 1, IB_OP_DELETE, IB_SIDE_ASK, 101.0, None),
    ]


class CaptureRedactionTests(unittest.TestCase):
    def test_capture_payload_has_no_secret_fields(self) -> None:
        record = capture_depth_callback(
            callback="updateMktDepthL2",
            req_id=42,
            instrument_id="AAPL",
            generation=1,
            position=0,
            operation=IB_OP_INSERT,
            side=IB_SIDE_BID,
            price=100.0,
            size=10.0,
            market_maker="MM1",
        )
        text = json.dumps(record)
        self.assertNotIn("password", text.lower())
        self.assertNotIn("account", text.lower())
        self.assertNotIn("token", text.lower())

    def test_error_capture_redacts_embedded_secrets(self) -> None:
        record = capture_error_record(
            req_id=42,
            code=123,
            message="authorization=super-secret-value and password=hunter2",
            category="UNKNOWN_PROVIDER_ERROR",
            received_time_ns=1000,
        )
        self.assertNotIn("super-secret-value", record["message"])
        self.assertNotIn("hunter2", record["message"])

    def test_redact_recursive(self) -> None:
        payload = {
            "password": "hunter2",
            "nested": {"api_key": "abc", "safe": "value"},
            "list": [{"token": "xyz"}],
        }
        out = redact(payload)
        self.assertEqual(out["password"], "<REDACTED>")
        self.assertEqual(out["nested"]["api_key"], "<REDACTED>")
        self.assertEqual(out["nested"]["safe"], "value")
        self.assertEqual(out["list"][0]["token"], "<REDACTED>")


class CaptureReplayTests(unittest.TestCase):
    def test_replay_produces_same_canonical_state_hash(self) -> None:
        # --- direct path: fake callbacks through the live adapter ---
        direct_store = ObservationalStateStore()
        direct, transport = connected_adapter(
            store=direct_store, lookup=FakeLookup(AAPL)
        )
        sub = direct.subscribe_l2(instrument_id="AAPL")
        for args in _script(sub.req_id):
            direct.on_mkt_depth(*args, received_ns=1000)
        direct_hash = direct_store.book_engine_for("AAPL").state_hash()
        captured = direct.capture_records()

        # --- replay path: captured records through a fresh adapter, offline ---
        replay_store = ObservationalStateStore()
        replay, _ = make_adapter(
            live=False, store=replay_store, lookup=FakeLookup(AAPL)
        )
        # Offline replay registration: no transport I/O.
        reg = replay.register_replay_subscription(
            instrument_id="AAPL",
            capability=CapabilityKind.L2,
            req_id=sub.req_id,
        )
        self.assertTrue(reg.accepted, reg.reason)
        for record in captured:
            replay.on_captured_record(record)
        replay_hash = replay_store.book_engine_for("AAPL").state_hash()
        self.assertEqual(replay_hash, direct_hash)

    def test_capture_records_are_safe_facts(self) -> None:
        direct_store = ObservationalStateStore()
        direct, _ = connected_adapter(store=direct_store, lookup=FakeLookup(AAPL))
        sub = direct.subscribe_l2(instrument_id="AAPL")
        direct.on_mkt_depth(sub.req_id, 0, IB_OP_INSERT, IB_SIDE_BID, 100.0, 10.0)
        records = direct.capture_records()
        self.assertTrue(any(r.get("callback_kind") == "DEPTH" for r in records))
        for record in records:
            text = json.dumps(record)
            self.assertNotIn("password", text.lower())
            self.assertNotIn("account", text.lower())


if __name__ == "__main__":
    unittest.main()
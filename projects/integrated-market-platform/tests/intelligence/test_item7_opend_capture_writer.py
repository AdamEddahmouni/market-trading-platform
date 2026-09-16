"""Item 7 upstream capture writer (SOFTWARE/CONTROLLED — fixture rows only)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.outcomes.opend_capture_ledger import (  # noqa: E402
    iter_jsonl_envelopes,
    scan_capture_funnel,
)
from market_platform_foundation.intelligence.production.item7_opend_capture_writer import (  # noqa: E402
    CANONICAL_CAPTURE_FILENAME,
    DISPOSITION_APPENDED,
    DISPOSITION_REFUSED,
    Item7CaptureWriterError,
    REFUSAL_IMP_STATE_DIR_MISSING,
    append_from_probe_diagnostic,
    append_vendor_snapshot_capture,
    canonical_item7_opend_capture_path,
)
from market_platform_foundation.market_data.moomoo_snapshot_bbo import (  # noqa: E402
    BboClocks,
    SNAPSHOT_BBO_CAPABILITY,
)
from tests.intelligence.test_baseline_fixtures import T as DECISION_T  # noqa: E402
from tests.intelligence.test_opend_capture_ledger_bridge import (  # noqa: E402
    AS_OF,
    SESSION_START,
)


def _vendor_row(**overrides: object) -> dict:
    base = {
        "code": "US.NVDA",
        "last_price": 190.1,
        "update_time": "2026-09-12 15:59:00.000",
        "bid_price": 190.0,
        "ask_price": 190.2,
        "bid_vol": 100,
        "ask_vol": 200,
        "sec_status": "NORMAL",
    }
    base.update(overrides)
    return base


def _clocks() -> BboClocks:
    five_sec = 5 * 1_000_000_000
    received = DECISION_T + five_sec
    return BboClocks(
        request_time_ns=DECISION_T,
        provider_time_ns=DECISION_T,
        receive_time_ns=received,
        available_time_ns=received,
    )


class Item7OpendCaptureWriterTests(unittest.TestCase):
    _env_keys = ("IMP_STATE_DIR",)

    def setUp(self) -> None:
        self._saved = {key: os.environ.get(key) for key in self._env_keys}

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_valid_bbo_appends_to_capture_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capture = Path(tmp) / CANONICAL_CAPTURE_FILENAME
            result = append_vendor_snapshot_capture(
                _vendor_row(),
                clocks=_clocks(),
                capture_path=capture,
                require_imp_state_dir=False,
                auto_persist=False,
            )
            self.assertEqual(result.disposition, DISPOSITION_APPENDED)
            self.assertIsNotNone(result.envelope)
            self.assertEqual(result.envelope["capability"], SNAPSHOT_BBO_CAPABILITY)
            lines = list(iter_jsonl_envelopes(capture))
            self.assertEqual(len(lines), 1)
            self.assertIsNone(lines[0][2])
            funnel = scan_capture_funnel(capture, as_of_ns=AS_OF, session_start_ns=SESSION_START)
            self.assertEqual(funnel.grid_points, 1)

    def test_invalid_bbo_refuses_without_capture_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capture = Path(tmp) / CANONICAL_CAPTURE_FILENAME
            result = append_vendor_snapshot_capture(
                _vendor_row(bid_price=None, ask_price=None),
                clocks=_clocks(),
                capture_path=capture,
                require_imp_state_dir=False,
                auto_persist=False,
            )
            self.assertEqual(result.disposition, DISPOSITION_REFUSED)
            self.assertFalse(capture.is_file())

    def test_failure_receipt_written_on_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capture = Path(tmp) / CANONICAL_CAPTURE_FILENAME
            refusal_path = capture.parent / "item7-opend-prospective-capture.refusals.jsonl"
            append_vendor_snapshot_capture(
                _vendor_row(bid_price=190.5, ask_price=190.0),
                clocks=_clocks(),
                capture_path=capture,
                require_imp_state_dir=False,
                write_failure_receipt=True,
            )
            self.assertFalse(capture.is_file())
            self.assertTrue(refusal_path.is_file())
            refusal_lines = list(iter_jsonl_envelopes(refusal_path))
            self.assertEqual(len(refusal_lines), 1)

    def test_missing_imp_state_dir_fail_closed(self) -> None:
        os.environ.pop("IMP_STATE_DIR", None)
        with self.assertRaises(Item7CaptureWriterError):
            canonical_item7_opend_capture_path(require_imp_state_dir=True)
        result = append_vendor_snapshot_capture(
            _vendor_row(),
            clocks=_clocks(),
            require_imp_state_dir=True,
            auto_persist=False,
        )
        self.assertEqual(result.disposition, DISPOSITION_REFUSED)
        self.assertEqual(result.refusal_reason, REFUSAL_IMP_STATE_DIR_MISSING)

    def test_imp_state_dir_canonical_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["IMP_STATE_DIR"] = tmp
            path = canonical_item7_opend_capture_path()
            self.assertEqual(path.name, CANONICAL_CAPTURE_FILENAME)
            self.assertEqual(path.parent.name, "captures")

    def test_probe_blocked_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capture = Path(tmp) / CANONICAL_CAPTURE_FILENAME
            now = DECISION_T
            from market_platform_foundation.market_data.moomoo_snapshot_bbo import BboDiagnostic

            diag = BboDiagnostic(
                symbol="US.NVDA",
                clocks=BboClocks(
                    request_time_ns=now,
                    provider_time_ns=None,
                    receive_time_ns=now,
                    available_time_ns=now,
                ),
                probe_status="BLOCKED",
                block_reason="OPEND_UNAVAILABLE",
            )
            result = append_from_probe_diagnostic(
                _vendor_row(),
                diag,
                capture_path=capture,
                require_imp_state_dir=False,
                auto_persist=False,
            )
            self.assertEqual(result.disposition, DISPOSITION_REFUSED)
            self.assertFalse(capture.is_file())

    def test_clock_order_invalid_refuses_envelope(self) -> None:
        clocks = BboClocks(
            request_time_ns=1_000,
            provider_time_ns=5_000,
            receive_time_ns=2_000,
            available_time_ns=3_000,
        )
        with tempfile.TemporaryDirectory() as tmp:
            capture = Path(tmp) / CANONICAL_CAPTURE_FILENAME
            result = append_vendor_snapshot_capture(
                _vendor_row(),
                clocks=clocks,
                capture_path=capture,
                require_imp_state_dir=False,
                auto_persist=False,
            )
            self.assertEqual(result.disposition, DISPOSITION_REFUSED)
            self.assertFalse(capture.is_file())

    def test_sequence_monotonic_on_append(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capture = Path(tmp) / CANONICAL_CAPTURE_FILENAME
            first = append_vendor_snapshot_capture(
                _vendor_row(),
                clocks=_clocks(),
                capture_path=capture,
                require_imp_state_dir=False,
                auto_persist=False,
            )
            second = append_vendor_snapshot_capture(
                _vendor_row(),
                clocks=_clocks(),
                capture_path=capture,
                require_imp_state_dir=False,
                auto_persist=False,
            )
            self.assertEqual(first.sequence, 1)
            self.assertEqual(second.sequence, 2)
            raw = json.loads(capture.read_text(encoding="utf-8").strip().splitlines()[-1])
            self.assertEqual(raw["sequence"], 2)

    def test_receipt_never_claims_governed_row_captured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capture = Path(tmp) / CANONICAL_CAPTURE_FILENAME
            result = append_vendor_snapshot_capture(
                _vendor_row(),
                clocks=_clocks(),
                capture_path=capture,
                require_imp_state_dir=False,
                auto_persist=False,
            )
            blob = json.dumps(result.to_dict())
            self.assertNotIn("ITEM7_GOVERNED_ROW_CAPTURED", blob)
            self.assertNotIn("ITEM7_COMPLETE", blob)


if __name__ == "__main__":
    unittest.main()

"""Regression tests for Monday RTH hop JSON Item 2 / EMIT gate checker."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools.hop_json_gate_check import MOOMOO_OPEND_L1, evaluate_hop, main


def _finviz_fetched_equity_context() -> dict:
    return {
        "discovery": {
            "provider_id": "finviz.elite.context",
            "auto_fetch_status": "FETCHED",
            "classification": "CONFIGURED_BLOCKED",
            "reason_code": "LIVE_DISABLED",
            "overlay_token_present": True,
            "is_l1": False,
        },
        "result": {
            "provider_id": "finviz.elite.context",
            "is_l1": False,
            "reason_code": "LIVE_DISABLED",
            "status": "ok",
        },
    }


def _opend_l1_stack(actionable: bool, status: str = "OK") -> dict:
    freshness = {"actionable": actionable}
    return {
        "discovery": {"provider_id": MOOMOO_OPEND_L1},
        "result": {
            "provider_id": MOOMOO_OPEND_L1,
            "status": status,
            "freshness": freshness,
        },
        "equity_context": _finviz_fetched_equity_context(),
    }


class HopJsonGateCheckTests(unittest.TestCase):
    def test_item2_flip_yes_when_all_gates_pass(self) -> None:
        metrics = evaluate_hop(_opend_l1_stack(actionable=True))
        self.assertEqual(metrics["ITEM2_FLIP"], "yes")
        self.assertEqual(metrics["EMIT"], "run")
        self.assertEqual(metrics["FTEP"], "NOT_READY")
        self.assertEqual(metrics["freshness_actionable"], "true")
        self.assertEqual(metrics["hop_l1_provider"], MOOMOO_OPEND_L1)
        self.assertEqual(metrics["finviz_overlay"], "FETCHED")

    def test_top_level_last_price_disqualifies_l1(self) -> None:
        payload = _opend_l1_stack(actionable=True)
        payload["last_price"] = 227.5
        metrics = evaluate_hop(payload)
        self.assertEqual(metrics["ITEM2_FLIP"], "no")
        self.assertEqual(metrics["EMIT"], "skip")
        self.assertIn("top_level", metrics["hop_l1_provider"])

    def test_sunday_leftover_g7_not_actionable(self) -> None:
        payload = _opend_l1_stack(actionable=False, status="G7_NOT_ACTIONABLE")
        metrics = evaluate_hop(payload)
        self.assertEqual(metrics["ITEM2_FLIP"], "no")
        self.assertEqual(metrics["EMIT"], "skip")
        self.assertEqual(metrics["FTEP"], "NOT_READY")
        self.assertEqual(metrics["freshness_actionable"], "false")
        self.assertEqual(metrics["g7_status"], "G7_NOT_ACTIONABLE")

    def test_ftep_always_not_ready(self) -> None:
        for payload in (
            _opend_l1_stack(actionable=True),
            _opend_l1_stack(actionable=False, status="G7_NOT_ACTIONABLE"),
        ):
            self.assertEqual(evaluate_hop(payload)["FTEP"], "NOT_READY")

    def test_finviz_not_fetched_blocks_flip(self) -> None:
        payload = _opend_l1_stack(actionable=True)
        payload["equity_context"]["discovery"]["auto_fetch_status"] = "NOT_ATTEMPTED"
        metrics = evaluate_hop(payload)
        self.assertEqual(metrics["ITEM2_FLIP"], "no")
        self.assertEqual(metrics["EMIT"], "skip")
        self.assertTrue(metrics["finviz_overlay"].startswith("no:"))

    def test_wrong_l1_provider_blocks_flip(self) -> None:
        payload = _opend_l1_stack(actionable=True)
        payload["result"]["provider_id"] = "yahoo.finance.delayed"
        metrics = evaluate_hop(payload)
        self.assertEqual(metrics["ITEM2_FLIP"], "no")
        self.assertEqual(metrics["hop_l1_provider"], "yahoo.finance.delayed")

    def test_cli_reads_file_and_exits_zero_on_skip(self) -> None:
        payload = _opend_l1_stack(actionable=False, status="G7_NOT_ACTIONABLE")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hop.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            code = main([str(path)])
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()

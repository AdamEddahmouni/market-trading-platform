"""Order Flow OF12 gate rule tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.order_flow.research.gates import (  # noqa: E402
    GATE_MILESTONE_OF12_S1,
    GATE_MILESTONE_OF_Q9,
    evaluate_of12_s1_gate,
    evaluate_of_q9_gate,
)


class Of12GateTests(unittest.TestCase):
    def test_insufficient_sample_when_empty(self) -> None:
        result = evaluate_of12_s1_gate([], [], [])
        self.assertEqual(result["gate_milestone"], GATE_MILESTONE_OF12_S1)
        self.assertEqual(result["gate_status"], "INSUFFICIENT_SAMPLE")

    def test_of_q9_fail_when_fill_unchanged(self) -> None:
        result = evaluate_of_q9_gate(
            0.7,
            0.7,
            l2_queue_model="none",
            mbo_queue_model="fifo_displayed_mbo_v1",
        )
        self.assertEqual(result["gate_milestone"], GATE_MILESTONE_OF_Q9)
        self.assertEqual(result["gate_status"], "FAIL")


if __name__ == "__main__":
    unittest.main()

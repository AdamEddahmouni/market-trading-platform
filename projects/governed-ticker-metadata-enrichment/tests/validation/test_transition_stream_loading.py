"""Regression tests for immutable default transition-fixture reuse."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.donor_bridge import transition_stream


class TransitionStreamLoadingTests(unittest.TestCase):
    def test_default_fixture_bytes_are_read_once_and_results_are_independent(self) -> None:
        self.assertTrue(hasattr(transition_stream, "_default_transition_payload_bytes"))
        transition_stream._default_transition_payload_bytes.cache_clear()
        original_read = Path.read_bytes
        with patch.object(Path, "read_bytes", autospec=True, side_effect=original_read) as read:
            first = transition_stream.replay_transition_stream()
            second = transition_stream.replay_transition_stream()
        default_reads = [
            call
            for call in read.call_args_list
            if call.args and call.args[0] == transition_stream.DEFAULT_TRANSITION_STREAM_FIXTURE
        ]
        self.assertEqual(len(default_reads), 1)
        self.assertEqual(first, second)
        self.assertIsNot(first, second)
        self.assertIsNot(first[0], second[0])
        first[0]["state"] = "MUTATED"
        self.assertNotEqual(second[0].get("state"), "MUTATED")


if __name__ == "__main__":
    unittest.main()

"""ReplayClock unit tests (BUILD 07)."""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.replay import ReplayClock, ReplayClockError  # noqa: E402

T = 1_700_000_000_000_000_000


class ReplayClockTests(unittest.TestCase):
    def test_initialization(self) -> None:
        clock = ReplayClock(T)
        self.assertEqual(clock.now_ns(), T)

    def test_advance_to(self) -> None:
        clock = ReplayClock(T)
        clock.advance_to(T + 10)
        self.assertEqual(clock.now_ns(), T + 10)

    def test_advance_by(self) -> None:
        clock = ReplayClock(T)
        clock.advance_by(25)
        self.assertEqual(clock.now_ns(), T + 25)

    def test_cannot_go_backward(self) -> None:
        clock = ReplayClock(T + 10)
        with self.assertRaises(ReplayClockError):
            clock.advance_to(T)

    def test_negative_delta_rejected(self) -> None:
        clock = ReplayClock(T)
        with self.assertRaises(ReplayClockError):
            clock.advance_by(-1)

    def test_no_wall_clock_in_replay_core(self) -> None:
        replay_dir = ROOT / "src" / "market_platform_foundation" / "intelligence" / "replay"
        forbidden = ("time.time", "time.sleep", "datetime.now", "datetime.utcnow", "asyncio.sleep")
        for path in replay_dir.glob("*.py"):
            if path.name == "clock.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    source = f"{ast.unparse(node.func.value)}.{node.func.attr}"
                    if source in forbidden or node.func.attr in {"time_ns", "sleep"}:
                        if path.name != "clock.py":
                            self.fail(f"forbidden wall-clock call in {path.name}: {source}")


if __name__ == "__main__":
    unittest.main()

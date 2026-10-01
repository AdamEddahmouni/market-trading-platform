"""The API warms each Screener universe once at start so the first page after a restart is fast."""

from __future__ import annotations

import os
import unittest
from unittest import mock

from tools.ui1 import run_ui_api


class ScreenerWarmupTests(unittest.TestCase):
    def test_reads_each_universe_once_and_survives_a_failing_one(self) -> None:
        calls: list[str] = []

        def read(**kwargs):  # type: ignore[no-untyped-def]
            calls.append(kwargs["universe"])
            self.assertEqual(kwargs["limit"], 1)
            if kwargs["universe"] == "US_ETFS":
                raise RuntimeError("OpenD down")
            return {}

        timings = run_ui_api.warm_screener(read)
        self.assertEqual(calls, ["US_EQUITIES", "US_ETFS", "FUTURES"])
        self.assertEqual(timings["US_ETFS"], "RuntimeError")
        self.assertIsInstance(timings["FUTURES"], float)

    def test_only_a_live_launch_warms(self) -> None:
        with mock.patch.dict(os.environ, {"IMP_FINVIZ_LIVE": "0", "IMP_MOOMOO_LIVE": "0"}):
            self.assertIsNone(run_ui_api.start_screener_warmup())
        with mock.patch.dict(os.environ, {"IMP_FINVIZ_LIVE": "1", "IMP_SCREENER_WARMUP": "0"}):
            self.assertIsNone(run_ui_api.start_screener_warmup())
        with mock.patch.dict(os.environ, {"IMP_FINVIZ_LIVE": "1", "IMP_SCREENER_WARMUP": "1"}), \
                mock.patch.object(run_ui_api, "warm_screener", return_value={}) as warm:
            thread = run_ui_api.start_screener_warmup()
            self.assertIsNotNone(thread)
            assert thread is not None
            thread.join(5)
            warm.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()

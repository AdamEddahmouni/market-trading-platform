"""Unit tests must restore process environment after they finish."""

from __future__ import annotations

import os
import unittest

from tests.finviz.test_finviz_provider import FinvizDiscoveryOfflineTests
from tests.intelligence.test_ftep_campaign_status import FtepCampaignStatusTests
from tests.platform.test_discovery_p33 import DiscoveryP33Tests


class ProcessEnvIsolationTests(unittest.TestCase):
    def test_discovery_capture_dir_is_restored(self) -> None:
        prior = os.environ.get("IMP_FINVIZ_CAPTURE_DIR")
        case = DiscoveryP33Tests("test_capture_persist_and_replay")
        case.test_capture_persist_and_replay()
        self.assertEqual(os.environ.get("IMP_FINVIZ_CAPTURE_DIR"), prior)

    def test_finviz_fixture_suite_does_not_set_capture_dir(self) -> None:
        prior = os.environ.get("IMP_FINVIZ_CAPTURE_DIR")
        case = FinvizDiscoveryOfflineTests("test_capture_replay_equivalence")
        case.test_capture_replay_equivalence()
        self.assertEqual(os.environ.get("IMP_FINVIZ_CAPTURE_DIR"), prior)

    def test_campaign_status_persist_flag_is_restored(self) -> None:
        prior = os.environ.get("IMP_PERSIST_STATE")
        case = FtepCampaignStatusTests("test_ftep_v1_002_status_snapshot")
        case.setUp()
        try:
            self.assertEqual(os.environ.get("IMP_PERSIST_STATE"), "1")
        finally:
            case.tearDown()
        self.assertEqual(os.environ.get("IMP_PERSIST_STATE"), prior)


if __name__ == "__main__":
    unittest.main()

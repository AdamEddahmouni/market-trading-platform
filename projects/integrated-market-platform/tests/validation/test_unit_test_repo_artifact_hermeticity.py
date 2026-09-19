"""Unit tests must not mutate tracked IMP artifact paths."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.cross_lane.test_g14_product_convergence import G14ProductProjectionTests  # noqa: E402


class UnitTestRepoArtifactHermeticityTests(unittest.TestCase):
    def test_g14_performance_does_not_write_repo_artifacts(self) -> None:
        target = ROOT / "artifacts" / "g14-runtime-performance.json"
        prior_mtime_ns = target.stat().st_mtime_ns if target.exists() else None

        prior_cwd = Path.cwd()
        try:
            os.chdir(ROOT)
            case = G14ProductProjectionTests("test_g14_product_performance_measured")
            case.setUp()
            case.test_g14_product_performance_measured()
        finally:
            os.chdir(prior_cwd)

        if prior_mtime_ns is None:
            self.assertFalse(target.exists())
        else:
            self.assertEqual(target.stat().st_mtime_ns, prior_mtime_ns)


if __name__ == "__main__":
    unittest.main()

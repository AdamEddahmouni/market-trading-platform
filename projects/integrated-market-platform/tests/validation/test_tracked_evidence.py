"""Tracked evidence artifacts are refreshed only on explicit request."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools.tracked_evidence import REFRESH_ENVIRONMENT_VARIABLE, evidence_output_path


class TrackedEvidenceOutputPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracked = Path(__file__).resolve().parents[2] / "artifacts" / "example-evidence.json"

    def test_routine_runs_write_outside_the_checkout(self) -> None:
        for value in (None, "", "0", "true"):
            with self.subTest(value=value):
                environment = {k: v for k, v in os.environ.items() if k != REFRESH_ENVIRONMENT_VARIABLE}
                if value is not None:
                    environment[REFRESH_ENVIRONMENT_VARIABLE] = value
                with mock.patch.dict(os.environ, environment, clear=True):
                    output = evidence_output_path(self.tracked)
                self.assertEqual(output.name, self.tracked.name)
                self.assertTrue(output.parent.is_dir())
                self.assertTrue(output.is_relative_to(Path(tempfile.gettempdir())))
                self.assertFalse(output.is_relative_to(self.tracked.parents[1]))

    def test_explicit_refresh_targets_the_tracked_file(self) -> None:
        with mock.patch.dict(os.environ, {REFRESH_ENVIRONMENT_VARIABLE: "1"}):
            self.assertEqual(evidence_output_path(self.tracked), self.tracked)


if __name__ == "__main__":
    unittest.main()

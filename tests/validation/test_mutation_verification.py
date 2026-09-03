"""Tests for controlled validation mutation verification."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.mutation_verification import MUTATIONS, apply_mutation


class MutationVerificationTests(unittest.TestCase):
    def test_required_failure_modes_are_declared(self) -> None:
        self.assertEqual(
            {mutation.id for mutation in MUTATIONS},
            {
                "bitemporal-knowledge-time-removed",
                "fred-missing-dot-becomes-zero",
                "credential-redaction-removed",
                "wrong-listing-authority-routing",
                "fred-realtime-end-as-availability",
                "eia-period-end-as-availability",
            },
        )
        self.assertEqual([mutation.mode for mutation in MUTATIONS[:3]], ["fast"] * 3)
        self.assertEqual([mutation.mode for mutation in MUTATIONS[3:]], ["changed"] * 3)

    def test_apply_mutation_requires_one_unambiguous_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "sample.py"
            target.write_text("before\nneedle\nafter\n", encoding="utf-8")

            apply_mutation(target, "needle", "replacement")
            self.assertEqual(target.read_text(encoding="utf-8"), "before\nreplacement\nafter\n")

            with self.assertRaisesRegex(ValueError, "exactly once"):
                apply_mutation(target, "missing", "replacement")


if __name__ == "__main__":
    unittest.main()

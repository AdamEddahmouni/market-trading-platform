"""Audit-fix tests: skip identities in worker payloads (F1) and short_intelligence
fixture provenance manifest coverage (F3)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "short_intelligence"

try:
    from tools.validation_worker import StructuredTestResult, _skip_rows
except ModuleNotFoundError as exc:  # RED: report the absent builder as a failure.
    StructuredTestResult = None  # type: ignore[assignment,misc]
    _skip_rows = None  # type: ignore[assignment]
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None



@unittest.skip("probe fixture must be skipped")
class _SkippedProbe(unittest.TestCase):
    def test_later(self) -> None:  # pragma: no cover - never executed
        self.fail("must be skipped")


_SkippedProbe._validation_selector = (
    "tests/synthetic/test_skip.py::_SkippedProbe::test_later"
)


@unittest.skip("upstream provider unavailable in offline audit run")
class SkippedTests(unittest.TestCase):
    _validation_selector = "tests/synthetic/test_skip.py::SkippedTests::test_offline"

    def test_offline(self) -> None:  # pragma: no cover - never executed
        raise AssertionError("must be skipped")


class SkipDetailPayloadTests(unittest.TestCase):
    """F1: skipped tests must serialize selector + reason, not just a count."""

    def setUp(self) -> None:
        if IMPORT_ERROR is not None:
            self.fail(f"validation_worker import failed: {IMPORT_ERROR}")
        self.result = StructuredTestResult(REPO_ROOT)
        self.result.startTest(SkippedTests("test_offline"))
        self.result.addSkip(SkippedTests("test_offline"), "offline gate closed")
        self.result.stopTest(SkippedTests("test_offline"))

    def test_structured_result_records_skips(self) -> None:
        self.assertEqual(self.result.testsRun, 1)
        self.assertEqual(len(self.result.skipped), 1)

    def test_skip_rows_serialize_identities(self) -> None:
        rows = _skip_rows(self.result.skipped, REPO_ROOT)
        self.assertEqual(
            rows,
            [
                {
                    "selector": "tests/synthetic/test_skip.py::SkippedTests::test_offline",
                    "reason": "offline gate closed",
                }
            ],
        )

    def test_skip_rows_are_sorted_by_selector(self) -> None:
        suite = unittest.TestSuite(
            [
                _SkippedProbe("test_later"),
                SkippedTests("test_offline"),
            ]
        )
        structured = StructuredTestResult(REPO_ROOT)
        suite.run(structured)
        self.assertEqual(structured.testsRun, 2)
        self.assertEqual(len(structured.skipped), 2)
        rows = _skip_rows(structured.skipped, REPO_ROOT)
        selectors = [row["selector"] for row in rows]
        self.assertEqual(selectors, sorted(selectors))
        self.assertIn("::SkippedTests::test_offline", selectors[0])
        self.assertIn("::_SkippedProbe::test_later", selectors[1])
        for row in rows:
            self.assertTrue(row["reason"], "skip reason must not be dropped")

    def test_skip_rows_survive_unresolvable_module_paths(self) -> None:
        probe = SkippedTests("test_offline")
        probe._validation_selector = "<external>::SkippedTests::test_offline"
        rows = _skip_rows([(probe, "no network")], Path("/definitely/not/the/repo"))
        self.assertEqual(rows[0]["selector"], "<external>::SkippedTests::test_offline")
        self.assertEqual(rows[0]["reason"], "no network")


class ShortIntelligenceManifestTests(unittest.TestCase):
    """F3: every fixture file must carry an explicit recorded|synthetic label."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (FIXTURE_DIR / "admission_manifest.json").read_text(encoding="utf-8")
        )

    def test_manifest_is_admitted_research_only(self) -> None:
        self.assertEqual(self.manifest["status"], "ADMITTED")
        self.assertTrue(self.manifest["research_only"])
        self.assertEqual(self.manifest["schema_version"], "1.0.0")

    def test_manifest_covers_every_file_in_directory(self) -> None:
        declared = {entry["content_path"] for entry in self.manifest["files"]}
        actual = {
            f"tests/fixtures/short_intelligence/{path.name}"
            for path in FIXTURE_DIR.iterdir()
            if path.is_file() and path.name != "admission_manifest.json"
        }
        self.assertFalse(actual - declared, "fixture files missing from manifest")
        self.assertFalse(declared - actual, "manifest entries pointing at absent files")

    def test_every_file_labeled_recorded_or_synthetic(self) -> None:
        for entry in self.manifest["files"]:
            with self.subTest(path=entry["content_path"]):
                provenance = entry["provenance"]
                self.assertTrue(
                    provenance.startswith(("recorded", "synthetic")),
                    f"ambiguous provenance label: {provenance!r}",
                )
                if provenance.startswith("synthetic-format-sample"):
                    self.assertIn("UNVERIFIED", provenance)
                self.assertIn("source", entry)

    def test_gmeu_file_provenance_is_honest(self) -> None:
        entry = next(
            item
            for item in self.manifest["files"]
            if item["content_path"].endswith("cboe_bzx_gmeu_20250617.txt")
        )
        self.assertIn("synthetic", entry["provenance"])
        self.assertIn("UNVERIFIED", entry["provenance"])

    def test_no_duplicate_entries(self) -> None:
        paths = [entry["content_path"] for entry in self.manifest["files"]]
        self.assertEqual(len(paths), len(set(paths)))


if __name__ == "__main__":
    unittest.main()

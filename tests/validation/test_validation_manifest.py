"""Synthetic-repository tests for the canonical validation manifest."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

try:
    from tools.validation_manifest import ManifestValidationError, load_manifest
except ModuleNotFoundError as exc:  # RED: make the missing implementation a test failure.
    ManifestValidationError = RuntimeError  # type: ignore[assignment,misc]
    load_manifest = None  # type: ignore[assignment]
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


class ValidationManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        if IMPORT_ERROR is not None:
            self.fail(f"validation manifest loader is missing: {IMPORT_ERROR}")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "tests" / "alpha").mkdir(parents=True)
        (self.root / "tests" / "alpha" / "test_alpha.py").write_text(
            "import unittest\n"
            "class AlphaTests(unittest.TestCase):\n"
            "    def test_ok(self): self.assertTrue(True)\n",
            encoding="utf-8",
        )
        self.manifest_path = self.root / "tools" / "validation_manifest.json"
        self.manifest_path.parent.mkdir()

    def valid_payload(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "domains": ["core"],
            "full_invalidators": ["tools/validation_*.py"],
            "mandatory_invariants": [
                {
                    "id": "alpha-ok",
                    "selector": "tests/alpha/test_alpha.py::AlphaTests::test_ok",
                    "order": 10,
                    "isolation": "shared",
                }
            ],
            "suites": [
                {
                    "id": "alpha",
                    "path": "tests/alpha",
                    "classification": "offline",
                    "tiers": ["full"],
                    "domains": ["core"],
                    "parallel_safety": "PARALLEL_SAFE",
                    "resource_weight": 1,
                    "source_globs": ["src/alpha/**"],
                    "test_globs": ["tests/alpha/test_*.py"],
                    "neighbors": [],
                }
            ],
        }

    def write_payload(self, payload: dict[str, object]) -> None:
        self.manifest_path.write_text(json.dumps(payload), encoding="utf-8")

    def assert_manifest_error(self, payload: dict[str, object], message: str) -> None:
        self.write_payload(payload)
        with self.assertRaisesRegex(ManifestValidationError, message):
            load_manifest(self.manifest_path, repository_root=self.root)

    def test_loads_typed_immutable_manifest(self) -> None:
        self.write_payload(self.valid_payload())
        manifest = load_manifest(self.manifest_path, repository_root=self.root)
        self.assertEqual(manifest.schema_version, "1.0")
        self.assertEqual(manifest.suites[0].id, "alpha")
        self.assertEqual(manifest.suites[0].tiers, ("full",))
        with self.assertRaises((AttributeError, TypeError)):
            manifest.suites[0].id = "changed"  # type: ignore[misc]

    def test_rejects_duplicate_suite_ids(self) -> None:
        payload = self.valid_payload()
        payload["suites"] = [*payload["suites"], dict(payload["suites"][0])]  # type: ignore[index]
        self.assert_manifest_error(payload, "duplicate suite id.*alpha")

    def test_rejects_duplicate_owned_directories(self) -> None:
        payload = self.valid_payload()
        duplicate = dict(payload["suites"][0])  # type: ignore[index]
        duplicate["id"] = "alpha-copy"
        payload["suites"] = [payload["suites"][0], duplicate]  # type: ignore[index]
        self.assert_manifest_error(payload, "duplicate suite path.*tests/alpha")

    def test_rejects_existing_unclassified_test_directory(self) -> None:
        (self.root / "tests" / "beta").mkdir()
        (self.root / "tests" / "beta" / "test_beta.py").write_text("", encoding="utf-8")
        self.assert_manifest_error(self.valid_payload(), "unclassified test directory.*tests/beta")

    def test_rejects_missing_configured_directory(self) -> None:
        payload = self.valid_payload()
        payload["suites"][0]["path"] = "tests/missing"  # type: ignore[index]
        self.assert_manifest_error(payload, "configured suite path does not exist.*tests/missing")

    def test_allows_explained_intentionally_absent_directory(self) -> None:
        payload = self.valid_payload()
        payload["suites"].append(  # type: ignore[union-attr]
            {
                "id": "old-phase",
                "path": "tests/old_phase",
                "classification": "intentionally_absent",
                "tiers": [],
                "domains": ["core"],
                "parallel_safety": "SERIAL_REQUIRED",
                "resource_weight": 1,
                "source_globs": [],
                "test_globs": [],
                "neighbors": [],
                "absence_reason": "superseded by alpha",
            }
        )
        self.write_payload(payload)
        manifest = load_manifest(self.manifest_path, repository_root=self.root)
        self.assertEqual(manifest.suites[-1].classification, "intentionally_absent")

    def test_rejects_absent_entry_without_reason(self) -> None:
        payload = self.valid_payload()
        payload["suites"][0]["classification"] = "intentionally_absent"  # type: ignore[index]
        (self.root / "tests" / "alpha" / "test_alpha.py").unlink()
        (self.root / "tests" / "alpha").rmdir()
        self.assert_manifest_error(payload, "absence_reason")

    def test_rejects_invalid_safety_domain_and_glob(self) -> None:
        cases = (
            ("parallel_safety", "UNSAFE", "invalid parallel_safety"),
            ("domains", ["unknown"], "unknown domain"),
            ("source_globs", ["../outside/**"], "invalid source glob"),
            ("test_globs", ["/absolute/test_*.py"], "invalid test glob"),
        )
        for field, value, message in cases:
            with self.subTest(field=field):
                payload = self.valid_payload()
                payload["suites"][0][field] = value  # type: ignore[index]
                self.assert_manifest_error(payload, message)

    def test_rejects_live_suite_in_offline_full_tier(self) -> None:
        payload = self.valid_payload()
        payload["suites"][0]["classification"] = "live"  # type: ignore[index]
        payload["suites"][0]["live_provider"] = "alpha"  # type: ignore[index]
        self.assert_manifest_error(payload, "live suite.*full tier")

    def test_rejects_invalid_mandatory_selector(self) -> None:
        payload = self.valid_payload()
        payload["mandatory_invariants"][0]["selector"] = "tests/alpha/test_alpha.py"  # type: ignore[index]
        self.assert_manifest_error(payload, "invalid mandatory selector")

    def test_rejects_missing_mandatory_selector_target(self) -> None:
        payload = self.valid_payload()
        payload["mandatory_invariants"][0]["selector"] = (  # type: ignore[index]
            "tests/alpha/test_alpha.py::AlphaTests::test_missing"
        )
        self.assert_manifest_error(payload, "mandatory selector target not found")

    def test_repository_manifest_classifies_every_test_directory(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        manifest = load_manifest(
            repository_root / "tools" / "validation_manifest.json",
            repository_root=repository_root,
        )
        offline = [suite for suite in manifest.suites if suite.classification == "offline"]
        live = [suite for suite in manifest.suites if suite.classification == "live"]
        absent = [
            suite for suite in manifest.suites if suite.classification == "intentionally_absent"
        ]
        self.assertEqual(len(offline), 55)
        self.assertEqual(len(live), 12)
        self.assertEqual(len(absent), 3)
        self.assertNotIn("live", {tier for suite in offline for tier in suite.tiers})


if __name__ == "__main__":
    unittest.main()

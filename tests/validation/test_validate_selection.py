"""Synthetic selection tests for validate.py."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.validation_manifest import load_manifest

try:
    from tools.validate import (
        ValidationSelectionError,
        changed_paths_from_baseline,
        changed_paths_from_file,
        changed_paths_from_git,
        create_baseline_snapshot,
        normalize_repository_path,
        select_changed,
        select_domain,
        select_extended,
        select_full,
        select_live,
    )
except ModuleNotFoundError as exc:  # RED: make the missing CLI a failure.
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


class ValidateSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        if IMPORT_ERROR is not None:
            self.fail(f"validation CLI is missing: {IMPORT_ERROR}")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for directory in ("alpha", "beta", "core", "live_alpha", "extended"):
            target = self.root / "tests" / directory
            target.mkdir(parents=True)
            (target / f"test_{directory}.py").write_text(
                "import unittest\nclass Tests(unittest.TestCase):\n"
                "    def test_ok(self): self.assertTrue(True)\n",
                encoding="utf-8",
            )
        manifest_path = self.root / "tools" / "validation_manifest.json"
        manifest_path.parent.mkdir()
        manifest_path.write_text(json.dumps(self.payload()), encoding="utf-8")
        self.manifest = load_manifest(manifest_path, repository_root=self.root)

    def payload(self) -> dict[str, object]:
        common = {
            "tiers": ["full"],
            "parallel_safety": "PARALLEL_SAFE",
            "resource_weight": 1,
        }
        return {
            "schema_version": "1.0",
            "domains": ["core", "leaf"],
            "full_invalidators": ["src/shared/**", "tools/validation_*.py"],
            "mandatory_invariants": [
                {
                    "id": "alpha-ok",
                    "selector": "tests/alpha/test_alpha.py::Tests::test_ok",
                    "order": 10,
                    "isolation": "shared",
                }
            ],
            "suites": [
                {
                    **common,
                    "id": "alpha",
                    "path": "tests/alpha",
                    "classification": "offline",
                    "domains": ["leaf"],
                    "source_globs": ["src/alpha/**"],
                    "test_globs": ["tests/alpha/test_*.py"],
                    "neighbors": ["beta"],
                },
                {
                    **common,
                    "id": "beta",
                    "path": "tests/beta",
                    "classification": "offline",
                    "domains": ["leaf"],
                    "source_globs": ["src/beta/**"],
                    "test_globs": ["tests/beta/test_*.py"],
                    "neighbors": [],
                },
                {
                    **common,
                    "id": "core",
                    "path": "tests/core",
                    "classification": "offline",
                    "domains": ["core"],
                    "source_globs": ["src/core/**", "tools/validation_*.py"],
                    "test_globs": ["tests/core/test_*.py"],
                    "neighbors": [],
                },
                {
                    **common,
                    "id": "live-alpha",
                    "path": "tests/live_alpha",
                    "classification": "live",
                    "tiers": ["live"],
                    "domains": ["leaf"],
                    "parallel_safety": "LIVE_EXCLUSIVE",
                    "source_globs": [],
                    "test_globs": ["tests/live_alpha/test_*.py"],
                    "neighbors": [],
                    "live_provider": "alpha",
                },
                {
                    **common,
                    "id": "extended",
                    "path": "tests/extended",
                    "classification": "extended",
                    "tiers": ["extended"],
                    "domains": ["core"],
                    "parallel_safety": "RESOURCE_HEAVY",
                    "source_globs": [],
                    "test_globs": ["tests/extended/test_*.py"],
                    "neighbors": [],
                },
            ],
        }

    def test_provider_leaf_change_selects_owner_neighbor_and_invariants(self) -> None:
        selection = select_changed(self.manifest, ["src/alpha/client.py"])
        self.assertEqual(selection.selected_suite_ids, ("alpha", "beta"))
        self.assertEqual(selection.mandatory_selectors, ("tests/alpha/test_alpha.py::Tests::test_ok",))
        self.assertFalse(selection.full_suite_required)
        self.assertTrue(
            any("direct source ownership" in reason for reason in selection.selection_reasons["alpha"])
        )
        self.assertIn("neighbor of alpha", selection.selection_reasons["beta"])

    def test_test_only_change_does_not_fan_out_to_neighbors(self) -> None:
        selection = select_changed(self.manifest, ["tests/alpha/test_client.py"])
        self.assertEqual(selection.selected_suite_ids, ("alpha",))
        self.assertTrue(selection.mandatory_selectors)

    def test_doc_only_change_runs_only_cheap_checks(self) -> None:
        selection = select_changed(self.manifest, ["docs/engineering/guide.md"])
        self.assertEqual(selection.selected_suite_ids, ())
        self.assertEqual(selection.mandatory_selectors, ())
        self.assertEqual(selection.cheap_checks, ("documentation",))
        self.assertFalse(selection.full_suite_required)

    def test_evidence_only_change_runs_json_and_redaction_checks(self) -> None:
        selection = select_changed(self.manifest, ["evidence/alpha/report.json"])
        self.assertEqual(selection.selected_suite_ids, ())
        self.assertEqual(selection.cheap_checks, ("evidence-json", "secret-redaction"))

    def test_shared_change_sets_full_required_but_selects_diagnostics(self) -> None:
        selection = select_changed(self.manifest, ["src/shared/clock.py"])
        self.assertTrue(selection.full_suite_required)
        self.assertIn("core", selection.selected_suite_ids)
        self.assertTrue(selection.mandatory_selectors)
        self.assertIn("FULL_INVALIDATOR", selection.global_reasons)

    def test_unknown_executable_path_fails_safe(self) -> None:
        selection = select_changed(self.manifest, ["src/unowned/new_engine.py"])
        self.assertTrue(selection.full_suite_required)
        self.assertEqual(selection.selected_suite_ids, ("core",))
        self.assertTrue(selection.mandatory_selectors)
        self.assertIn("UNKNOWN_EXECUTABLE_PATH", selection.global_reasons)

    def test_modes_enforce_offline_live_and_extended_boundaries(self) -> None:
        self.assertEqual(select_domain(self.manifest, "leaf").selected_suite_ids, ("alpha", "beta"))
        self.assertEqual(select_full(self.manifest).selected_suite_ids, ("alpha", "beta", "core"))
        self.assertEqual(select_live(self.manifest, "alpha").selected_suite_ids, ("live-alpha",))
        self.assertEqual(select_extended(self.manifest).selected_suite_ids, ("extended",))
        with self.assertRaises(ValidationSelectionError):
            select_domain(self.manifest, "missing")
        with self.assertRaises(ValidationSelectionError):
            select_live(self.manifest, "missing")

    def test_normalization_rejects_traversal_and_absolute_paths(self) -> None:
        self.assertEqual(normalize_repository_path("src\\alpha\\client.py"), "src/alpha/client.py")
        for value in ("../outside.py", "/absolute.py", "C:/outside.py"):
            with self.subTest(value=value), self.assertRaises(ValidationSelectionError):
                normalize_repository_path(value)

    def initialize_git(self) -> None:
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "validation@example.invalid"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "Validation Test"], cwd=self.root, check=True)

    def test_git_changes_include_modified_deleted_and_untracked_nonignored(self) -> None:
        self.initialize_git()
        (self.root / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        modified = self.root / "tracked.txt"
        deleted = self.root / "deleted.txt"
        modified.write_text("before", encoding="utf-8")
        deleted.write_text("before", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=self.root, check=True)
        modified.write_text("after", encoding="utf-8")
        deleted.unlink()
        (self.root / "untracked.txt").write_text("new", encoding="utf-8")
        (self.root / "ignored.txt").write_text("ignored", encoding="utf-8")
        self.assertEqual(
            changed_paths_from_git(self.root),
            ("deleted.txt", "tracked.txt", "untracked.txt"),
        )

    def test_baseline_comparison_detects_added_removed_and_modified(self) -> None:
        self.initialize_git()
        tracked = self.root / "tracked.txt"
        removed = self.root / "removed.txt"
        tracked.write_text("before", encoding="utf-8")
        removed.write_text("before", encoding="utf-8")
        (self.root / ".env").write_text("SECRET=value", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt", "removed.txt", ".env"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "baseline"], cwd=self.root, check=True)
        baseline = create_baseline_snapshot(self.root)
        self.assertNotIn(".env", {row["path"] for row in baseline["files"]})
        baseline_path = self.root / "baseline.json"
        baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
        tracked.write_text("after", encoding="utf-8")
        removed.unlink()
        (self.root / "added.txt").write_text("new", encoding="utf-8")
        self.assertEqual(
            changed_paths_from_baseline(self.root, baseline_path),
            ("added.txt", "removed.txt", "tracked.txt"),
        )

    def test_explicit_paths_file_supports_clean_ci_checkouts(self) -> None:
        paths = self.root / "changed-paths.txt"
        paths.write_text("ui\\src\\App.tsx\nsrc/core/new.py\n", encoding="utf-8")
        self.assertEqual(
            changed_paths_from_file(paths),
            ("src/core/new.py", "ui/src/App.tsx"),
        )


if __name__ == "__main__":
    unittest.main()

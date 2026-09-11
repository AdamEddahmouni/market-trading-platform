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
        CLASS_CORE_CHECKPOINT_ESCALATION,
        CLASS_DEPENDENT_SUITE_SELECTION,
        CLASS_DOCUMENTATION_ONLY_CHECK,
        CLASS_EVIDENCE_ONLY_CHECK,
        CLASS_EXPLICIT_SAFE_IGNORE,
        CLASS_FAIL_SAFE,
        CLASS_OWNING_SUITE_SELECTION,
        ValidationSelectionError,
        canonicalize_changed_path,
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
            "core_checkpoint_invalidators": ["src/shared/**", "tools/validation_*.py"],
            "shared_module_dependents": [
                {
                    "path": "src/market_platform_foundation/market_sessions.py",
                    "dependent_suites": ["alpha"],
                    "reason": "synthetic consumer",
                }
            ],
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
                    "source_globs": [
                        "src/alpha/**",
                        "tests/fixtures/alpha/**",
                        "config/alpha/**",
                    ],
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
        self.assertFalse(selection.core_checkpoint_required)
        self.assertTrue(
            any("DIRECT_OWNER" in reason for reason in selection.selection_reasons["alpha"])
        )
        self.assertIn("neighbor of alpha", selection.selection_reasons["beta"])
        decision = selection.path_decisions[0]
        self.assertEqual(decision.classification, CLASS_OWNING_SUITE_SELECTION)
        self.assertEqual(decision.owning_suites, ("alpha",))
        self.assertEqual(decision.normalized, "src/alpha/client.py")

    def test_test_only_change_does_not_fan_out_to_neighbors(self) -> None:
        selection = select_changed(self.manifest, ["tests/alpha/test_client.py"])
        self.assertEqual(selection.selected_suite_ids, ("alpha",))
        self.assertTrue(selection.mandatory_selectors)

    def test_doc_only_change_runs_only_cheap_checks(self) -> None:
        selection = select_changed(self.manifest, ["docs/engineering/guide.md"])
        self.assertEqual(selection.selected_suite_ids, ())
        self.assertEqual(selection.mandatory_selectors, ())
        self.assertEqual(selection.cheap_checks, ("documentation",))
        self.assertFalse(selection.core_checkpoint_required)
        self.assertEqual(
            selection.path_decisions[0].classification, CLASS_DOCUMENTATION_ONLY_CHECK
        )

    def test_evidence_only_change_runs_json_and_redaction_checks(self) -> None:
        selection = select_changed(self.manifest, ["evidence/alpha/report.json"])
        self.assertEqual(selection.selected_suite_ids, ())
        self.assertEqual(selection.cheap_checks, ("evidence-json", "secret-redaction"))
        self.assertEqual(
            selection.path_decisions[0].classification, CLASS_EVIDENCE_ONLY_CHECK
        )

    def test_shared_change_sets_core_checkpoint_but_selects_diagnostics(self) -> None:
        selection = select_changed(self.manifest, ["src/shared/clock.py"])
        self.assertTrue(selection.core_checkpoint_required)
        self.assertIn("core", selection.selected_suite_ids)
        self.assertTrue(selection.mandatory_selectors)
        self.assertIn("CORE_CHECKPOINT_INVALIDATOR", selection.global_reasons)
        self.assertEqual(
            selection.path_decisions[0].classification, CLASS_CORE_CHECKPOINT_ESCALATION
        )

    def test_unknown_executable_path_fails_safe(self) -> None:
        selection = select_changed(self.manifest, ["src/unowned/new_engine.py"])
        self.assertTrue(selection.core_checkpoint_required)
        self.assertEqual(selection.selected_suite_ids, ("core",))
        self.assertTrue(selection.mandatory_selectors)
        self.assertIn("UNKNOWN_EXECUTABLE_PATH", selection.global_reasons)
        self.assertEqual(
            selection.path_decisions[0].classification, CLASS_CORE_CHECKPOINT_ESCALATION
        )
        self.assertTrue(selection.path_decisions[0].escalated)

    def test_modes_enforce_offline_live_and_extended_boundaries(self) -> None:
        self.assertEqual(select_domain(self.manifest, "leaf").selected_suite_ids, ("alpha", "beta"))
        self.assertEqual(select_full(self.manifest).selected_suite_ids, ("alpha", "beta", "core"))
        self.assertEqual(select_live(self.manifest, "alpha").selected_suite_ids, ("live-alpha",))
        self.assertEqual(select_extended(self.manifest).selected_suite_ids, ("extended",))
        with self.assertRaises(ValidationSelectionError):
            select_domain(self.manifest, "missing")
        with self.assertRaises(ValidationSelectionError):
            select_live(self.manifest, "missing")

    def test_parent_monorepo_path_normalizes_and_selects_same_suites(self) -> None:
        prefixes = ("projects/integrated-market-platform/",)
        prefixed = ["projects/integrated-market-platform/src/alpha/client.py"]
        child = ["src/alpha/client.py"]
        self.assertEqual(
            canonicalize_changed_path(prefixed[0], embedding_prefixes=prefixes),
            "src/alpha/client.py",
        )
        from_prefix = select_changed(self.manifest, prefixed, embedding_prefixes=prefixes)
        from_child = select_changed(self.manifest, child)
        self.assertEqual(from_prefix.selected_suite_ids, from_child.selected_suite_ids)
        self.assertEqual(from_prefix.selected_suite_ids, ("alpha", "beta"))
        self.assertEqual(from_prefix.changed_files, ("src/alpha/client.py",))
        self.assertEqual(from_prefix.path_decisions[0].original, prefixed[0])
        self.assertEqual(from_prefix.path_decisions[0].normalized, "src/alpha/client.py")

    def test_owned_fixture_change_selects_consumer_suite(self) -> None:
        selection = select_changed(self.manifest, ["tests/fixtures/alpha/data.json"])
        self.assertEqual(selection.selected_suite_ids, ("alpha", "beta"))
        self.assertFalse(selection.core_checkpoint_required)
        self.assertEqual(
            selection.path_decisions[0].classification, CLASS_OWNING_SUITE_SELECTION
        )

    def test_unowned_fixture_change_escalates_not_silent(self) -> None:
        selection = select_changed(self.manifest, ["tests/fixtures/orphan/data.json"])
        self.assertTrue(selection.core_checkpoint_required)
        self.assertIn("core", selection.selected_suite_ids)
        self.assertIn("UNOWNED_FIXTURE_OR_CONFIG", selection.global_reasons)
        self.assertEqual(
            selection.path_decisions[0].classification, CLASS_CORE_CHECKPOINT_ESCALATION
        )

    def test_top_level_fixture_change_escalates_not_silent(self) -> None:
        selection = select_changed(self.manifest, ["fixtures/raw/table.parquet"])
        self.assertTrue(selection.core_checkpoint_required)
        self.assertIn("UNOWNED_FIXTURE_OR_CONFIG", selection.global_reasons)

    def test_config_change_without_owner_escalates_not_silent(self) -> None:
        selection = select_changed(self.manifest, ["config/global/settings.json"])
        self.assertTrue(selection.core_checkpoint_required)
        self.assertIn("UNOWNED_FIXTURE_OR_CONFIG", selection.global_reasons)

    def test_owned_config_change_selects_consumer_suite(self) -> None:
        selection = select_changed(self.manifest, ["config/alpha/app.json"])
        self.assertEqual(selection.selected_suite_ids, ("alpha", "beta"))
        self.assertFalse(selection.core_checkpoint_required)

    def test_mapped_shared_module_selects_dependent_suites(self) -> None:
        selection = select_changed(
            self.manifest, ["src/market_platform_foundation/market_sessions.py"]
        )
        self.assertEqual(selection.selected_suite_ids, ("alpha",))
        self.assertFalse(selection.core_checkpoint_required)
        self.assertEqual(
            selection.path_decisions[0].classification, CLASS_DEPENDENT_SUITE_SELECTION
        )
        self.assertEqual(selection.path_decisions[0].dependent_suites, ("alpha",))

    def test_unmapped_shared_module_escalates_explicitly(self) -> None:
        selection = select_changed(
            self.manifest, ["src/market_platform_foundation/numeric.py"]
        )
        self.assertTrue(selection.core_checkpoint_required)
        self.assertIn("SHARED_MODULE_UNBOUNDED", selection.global_reasons)
        self.assertEqual(
            selection.path_decisions[0].classification, CLASS_CORE_CHECKPOINT_ESCALATION
        )

    def test_outside_tree_path_is_explicitly_ignored_when_embedded(self) -> None:
        prefixes = ("projects/integrated-market-platform/",)
        selection = select_changed(
            self.manifest, ["Claude Code News/package.json"], embedding_prefixes=prefixes
        )
        self.assertEqual(selection.selected_suite_ids, ())
        self.assertFalse(selection.core_checkpoint_required)
        self.assertEqual(
            selection.path_decisions[0].classification, CLASS_EXPLICIT_SAFE_IGNORE
        )

    def test_unknown_non_executable_path_fails_safe(self) -> None:
        selection = select_changed(self.manifest, ["artifacts/scratch/notes.txt"])
        self.assertTrue(selection.core_checkpoint_required)
        self.assertEqual(
            selection.path_decisions[0].classification, CLASS_FAIL_SAFE
        )
        self.assertIn("UNCLASSIFIED_PATH", selection.global_reasons)

    def test_deleted_or_renamed_path_still_selects_by_path(self) -> None:
        paths = self.root / "changed-paths.txt"
        paths.write_text("src/alpha/gone.py\nui/src/App.tsx\n", encoding="utf-8")
        changed = changed_paths_from_file(paths)
        self.assertIn("src/alpha/gone.py", changed)
        selection = select_changed(self.manifest, changed)
        self.assertIn("alpha", selection.selected_suite_ids)

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


class RealManifestSelectionTests(unittest.TestCase):
    """Bind G0 fixture/config/shared-module ownership to the real manifest.

    These tests load the canonical ``tools/validation_manifest.json`` and assert
    the selection semantics required by BL-0003 (G0 Wave 0): prefixed paths
    normalize identically to child-relative paths, owned fixtures select their
    consumer suites, owned config selects its suite, mapped shared modules
    select dependents, unbounded shared modules and unknown executables fail
    safe to the core checkpoint, and documentation/evidence paths stay cheap.
    """

    ROOT = Path(__file__).resolve().parents[2]

    def setUp(self) -> None:
        self.manifest = load_manifest(
            self.ROOT / "tools" / "validation_manifest.json", repository_root=self.ROOT
        )

    def test_prefixed_source_path_normalizes_to_child_relative(self) -> None:
        prefixed = "projects/integrated-market-platform/src/market_platform_foundation/paper/execution.py"
        child = "src/market_platform_foundation/paper/execution.py"
        prefixes = ("projects/integrated-market-platform/",)
        self.assertEqual(
            canonicalize_changed_path(prefixed, embedding_prefixes=prefixes), child
        )
        from_prefix = select_changed(self.manifest, [prefixed], embedding_prefixes=prefixes)
        from_child = select_changed(self.manifest, [child])
        self.assertEqual(from_prefix.selected_suite_ids, from_child.selected_suite_ids)
        self.assertIn("platform", from_prefix.selected_suite_ids)
        decision = from_prefix.path_decisions[0]
        self.assertEqual(decision.normalized, child)
        self.assertEqual(decision.classification, CLASS_OWNING_SUITE_SELECTION)

    def test_order_flow_fixture_selects_consumer_suites(self) -> None:
        selection = select_changed(
            self.manifest, ["tests/fixtures/providers/order_flow/admitted_cvd_nvda.json"]
        )
        self.assertFalse(selection.core_checkpoint_required)
        self.assertIn("order_flow", selection.selected_suite_ids)
        self.assertIn("participant", selection.selected_suite_ids)
        self.assertEqual(
            selection.path_decisions[0].classification, CLASS_OWNING_SUITE_SELECTION
        )

    def test_config_change_selects_of03(self) -> None:
        selection = select_changed(self.manifest, ["config/of03/workflows.json"])
        self.assertFalse(selection.core_checkpoint_required)
        self.assertIn("of03", selection.selected_suite_ids)

    def test_mapped_shared_module_selects_dependents(self) -> None:
        selection = select_changed(
            self.manifest, ["src/market_platform_foundation/market_sessions.py"]
        )
        self.assertFalse(selection.core_checkpoint_required)
        self.assertIn("platform", selection.selected_suite_ids)
        self.assertEqual(
            selection.path_decisions[0].classification, CLASS_DEPENDENT_SUITE_SELECTION
        )

    def test_unbounded_shared_module_fails_safe(self) -> None:
        selection = select_changed(
            self.manifest, ["src/market_platform_foundation/numeric.py"]
        )
        self.assertTrue(selection.core_checkpoint_required)
        self.assertIn("SHARED_MODULE_UNBOUNDED", selection.global_reasons)

    def test_unknown_executable_fails_safe(self) -> None:
        selection = select_changed(
            self.manifest, ["src/market_platform_foundation/unowned_new_engine.py"]
        )
        self.assertTrue(selection.core_checkpoint_required)
        self.assertIn("UNKNOWN_EXECUTABLE_PATH", selection.global_reasons)

    def test_documentation_and_evidence_stay_cheap(self) -> None:
        docs = select_changed(self.manifest, ["docs/platform/MASTER_ROADMAP.md"])
        self.assertEqual(docs.cheap_checks, ("documentation",))
        self.assertFalse(docs.core_checkpoint_required)
        evidence = select_changed(self.manifest, ["evidence/participant/report.json"])
        self.assertEqual(evidence.cheap_checks, ("evidence-json", "secret-redaction"))
        self.assertFalse(evidence.core_checkpoint_required)


if __name__ == "__main__":
    unittest.main()

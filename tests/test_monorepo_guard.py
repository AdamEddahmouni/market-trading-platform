import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.monorepo_guard import (
    GuardError,
    normalize_remote_url,
    validate_manifest_data,
    validate_snapshot_entries,
    validate_snapshot_parity,
)


class MonorepoGuardTests(unittest.TestCase):
    def test_current_workspace_contract_is_valid(self):
        manifest = {
            "version": 1,
            "parent": {
                "repository": "AdamEddahmouni/market-trading-platform",
                "visibility": "private",
            },
            "projects": [
                {
                    "id": "integrated-platform",
                    "source_path": "integrated-market-platform",
                    "snapshot_path": "projects/integrated-market-platform",
                    "source_remote": "https://github.com/owner/repo.git",
                    "source_ref": "codex/paper-accounting-risk-foundation",
                    "source_commit": "6308fcfce9e71ffaeaf22f24743a03c81691e0c6",
                    "expected_visibility": "private",
                    "source_policy": "unchanged",
                },
                {
                    "id": "short-squeeze",
                    "source_path": "short-squeeze-project",
                    "snapshot_path": "projects/short-squeeze-project",
                    "source_remote": "https://github.com/owner/repo.git",
                    "source_ref": "phase/3e-historical-acquisition",
                    "source_commit": "0b40834" + "0" * 33,
                    "expected_visibility": "public",
                    "source_policy": "unchanged",
                },
            ],
        }

        self.assertEqual(validate_manifest_data(manifest), [])

    def test_manifest_rejects_snapshot_outside_projects(self):
        manifest = {
            "version": 1,
            "parent": {"repository": "owner/repo", "visibility": "private"},
            "projects": [
                {
                    "id": "example",
                    "source_path": "example",
                    "snapshot_path": "example",
                    "source_ref": "main",
                    "source_commit": "a" * 40,
                    "expected_visibility": "private",
                    "source_policy": "unchanged",
                }
            ],
        }

        errors = validate_manifest_data(manifest)

        self.assertIn("snapshot_path must be under projects/", errors)

    def test_snapshot_entries_reject_embedded_gitlinks(self):
        with self.assertRaises(GuardError):
            validate_snapshot_entries(
                [
                    ("100644", "projects/example/README.md"),
                    ("160000", "projects/example/nested-repository"),
                ]
            )

    def test_remote_url_comparison_ignores_git_suffix(self):
        self.assertEqual(
            normalize_remote_url("https://github.com/owner/repo"),
            normalize_remote_url("https://github.com/owner/repo.git"),
        )

    def test_manifest_rejects_invalid_snapshot_overlay(self):
        manifest = {
            "version": 1,
            "parent": {"repository": "owner/repo", "visibility": "private"},
            "projects": [
                {
                    "id": "example",
                    "source_path": "example",
                    "snapshot_path": "projects/example",
                    "source_ref": "main",
                    "source_commit": "a" * 40,
                    "expected_visibility": "private",
                    "source_policy": "unchanged",
                    "snapshot_overlay": ["../escape.txt", 42],
                }
            ],
        }

        errors = validate_manifest_data(manifest)

        self.assertTrue(
            any("snapshot_overlay must be an array of relative paths" in error for error in errors)
        )

    def _init_repos(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        parent = Path(temporary.name) / "parent"
        child = Path(temporary.name) / "child"
        parent.mkdir()
        child.mkdir()
        for repo in (parent, child):
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "guard@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Guard Test"], cwd=repo, check=True)
        return parent, child

    def test_snapshot_parity_matches_child_tree_and_declared_overlay(self):
        parent, child = self._init_repos()
        snapshot = parent / "projects" / "example"
        (snapshot / "src").mkdir(parents=True)
        (snapshot / "src" / "app.py").write_text("child code\n", encoding="utf-8")
        (snapshot / "extra.py").write_text("new child file\n", encoding="utf-8")
        (snapshot / "pins.json").write_text("parent-local\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=parent, check=True)
        subprocess.run(["git", "commit", "-qm", "snapshot"], cwd=parent, check=True)
        (child / "src").mkdir()
        (child / "src" / "app.py").write_text("child code\n", encoding="utf-8")
        (child / "extra.py").write_text("new child file\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=child, check=True)
        subprocess.run(["git", "commit", "-qm", "child"], cwd=child, check=True)
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=child, capture_output=True, text=True, check=True
        ).stdout.strip()
        project = {
            "snapshot_path": "projects/example",
            "source_commit": commit,
            "snapshot_overlay": ["pins.json"],
        }
        validate_snapshot_parity(parent, project, child)
        with self.assertRaises(GuardError) as raised:
            validate_snapshot_parity(
                parent,
                {"snapshot_path": "projects/example", "source_commit": commit},
                child,
            )
        self.assertIn("unexpected snapshot file not in child tree", str(raised.exception))
        with self.assertRaises(GuardError) as raised:
            validate_snapshot_parity(
                parent,
                {
                    "snapshot_path": "projects/example",
                    "source_commit": commit,
                    "snapshot_overlay": ["pins.json", "missing-overlay.json"],
                },
                child,
            )
        self.assertIn("declared snapshot overlay path exists in neither", str(raised.exception))


if __name__ == "__main__":
    unittest.main()

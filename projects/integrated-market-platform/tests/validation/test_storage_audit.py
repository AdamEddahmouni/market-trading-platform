"""Hermetic tests for the read-only IMP storage audit."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.storage_audit import (
    ADVISORY_NOTICE,
    ReadOnlyGit,
    SCHEMA_VERSION,
    classify_link_kind,
    classify_worktree_hints,
    cursor_project_slug,
    discover_cursor_project_dir,
    git_argv_is_allowed,
    parse_worktree_porcelain,
    render_text_report,
    run_audit,
    run_cli,
)


def _run_git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
    )


def _init_repo(path: Path) -> str:
    _run_git(path, "init", "-b", "main")
    _run_git(path, "config", "user.email", "storage-audit@example.com")
    _run_git(path, "config", "user.name", "Storage Audit")
    (path / "README.md").write_text("seed\n", encoding="utf-8")
    _run_git(path, "add", "README.md")
    _run_git(path, "commit", "-m", "seed")
    head = _run_git(path, "rev-parse", "HEAD")
    return head.stdout.strip()


def _try_dir_link(target: Path, link: Path) -> bool:
    if link.exists() or link.is_symlink():
        return True
    if os.name == "nt":
        completed = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            text=True,
            check=False,
        )
        return completed.returncode == 0 and (link.exists() or link.is_symlink())
    os.symlink(target, link, target_is_directory=True)
    return True


class ParseWorktreePorcelainTests(unittest.TestCase):
    def test_parses_branch_detached_and_gone_metadata(self) -> None:
        text = """
worktree /repo
HEAD abcdef1234567890
branch refs/heads/main

worktree /repo/.worktrees/feature
HEAD fedcba0987654321
branch refs/heads/feature

worktree /repo/.worktrees/detached
HEAD 1111111111111111
detached
prunable

worktree /missing
HEAD 2222222222222222
detached
locked reason
""".strip()
        records = parse_worktree_porcelain(text)
        self.assertEqual(len(records), 4)
        self.assertEqual(records[0].branch, "refs/heads/main")
        self.assertFalse(records[0].detached)
        self.assertTrue(records[2].detached)
        self.assertTrue(records[2].prunable)
        self.assertTrue(records[3].locked)


class GitAllowlistTests(unittest.TestCase):
    def test_allows_read_only_inventory_commands(self) -> None:
        self.assertTrue(git_argv_is_allowed(("worktree", "list", "--porcelain")))
        self.assertTrue(git_argv_is_allowed(("count-objects", "-v")))
        self.assertTrue(git_argv_is_allowed(("-C", "/tmp/repo", "status", "--porcelain=v1")))
        self.assertTrue(git_argv_is_allowed(("merge-base", "--is-ancestor", "HEAD", "origin/main")))

    def test_blocks_destructive_git_commands(self) -> None:
        self.assertFalse(git_argv_is_allowed(("gc",)))
        self.assertFalse(git_argv_is_allowed(("prune",)))
        self.assertFalse(git_argv_is_allowed(("clean", "-fdx")))
        self.assertFalse(git_argv_is_allowed(("reset", "--hard")))
        self.assertFalse(git_argv_is_allowed(("worktree", "prune")))
        self.assertFalse(git_argv_is_allowed(("worktree", "remove", "x")))
        self.assertFalse(git_argv_is_allowed(("reflog", "expire", "--all")))
        runner = ReadOnlyGit()
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(RuntimeError):
                runner.run(("clean", "-fd"), cwd=Path(temporary))


class HintClassificationTests(unittest.TestCase):
    def test_gone_upstream_and_dirty_are_hints_not_removal(self) -> None:
        hints = classify_worktree_hints(
            dirty=True,
            detached=False,
            upstream_status="GONE",
            ancestor_of_main=True,
            unique_commits_possible=False,
        )
        self.assertIn("DIRTY", hints)
        self.assertIn("UPSTREAM_GONE", hints)
        self.assertIn("MERGED_OR_ANCESTOR", hints)
        self.assertIn("REVIEW_REQUIRED", hints)
        self.assertNotIn("REMOVABLE", hints)

    def test_detached_unique_commits(self) -> None:
        hints = classify_worktree_hints(
            dirty=False,
            detached=True,
            upstream_status="NONE",
            ancestor_of_main=False,
            unique_commits_possible=True,
        )
        self.assertIn("DETACHED", hints)
        self.assertIn("UNIQUE_COMMITS_POSSIBLE", hints)
        self.assertIn("REVIEW_REQUIRED", hints)


class StorageAuditRepoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        self.head = _init_repo(self.root)
        _run_git(self.root, "update-ref", "refs/remotes/origin/main", self.head)

    def _audit(self, **kwargs):
        git = kwargs.pop("git", ReadOnlyGit())
        return run_audit(start=self.root, scan_root=self.root, git=git, progress=lambda _m: None, **kwargs), git

    def test_json_schema_basics_and_advisory_notice(self) -> None:
        report, _git = self._audit()
        self.assertEqual(report["schema_version"], SCHEMA_VERSION)
        self.assertEqual(report["advisory_notice"], ADVISORY_NOTICE)
        self.assertTrue(report["safety"]["read_only"])
        self.assertFalse(report["safety"]["deletion_authority"])
        for key in (
            "repo",
            "git",
            "worktrees",
            "dependencies",
            "caches",
            "artifacts",
            "temporary",
            "cursor",
            "largest_paths",
            "warnings",
            "summary",
        ):
            self.assertIn(key, report)
        text = render_text_report(report)
        self.assertIn("IMP STORAGE AUDIT", text)
        self.assertIn(ADVISORY_NOTICE, text)

    def test_gone_upstream_handling(self) -> None:
        _run_git(self.root, "remote", "add", "origin", str(self.root))
        _run_git(self.root, "update-ref", "refs/remotes/origin/deleted", self.head)
        _run_git(self.root, "checkout", "-b", "feature")
        _run_git(self.root, "branch", "--set-upstream-to=origin/deleted")
        _run_git(self.root, "update-ref", "-d", "refs/remotes/origin/deleted")
        report, _git = self._audit()
        item = report["worktrees"]["items"][0]
        self.assertEqual(item["upstream_status"], "GONE")
        self.assertIn("UPSTREAM_GONE", item["hints"])
        self.assertTrue(item["hint_is_not_deletion_authority"])

    def test_dirty_worktree_handling(self) -> None:
        (self.root / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        (self.root / "README.md").write_text("changed\n", encoding="utf-8")
        report, _git = self._audit()
        item = report["worktrees"]["items"][0]
        self.assertTrue(item["dirty"])
        self.assertGreaterEqual(item["untracked"], 1)
        self.assertGreaterEqual(item["tracked_modifications"], 1)
        self.assertIn("DIRTY", item["hints"])
        self.assertNotIn("REMOVABLE", item["hints"])
        self.assertGreaterEqual(report["summary"]["dirty_worktrees"], 1)

    def test_detached_worktree_handling(self) -> None:
        _run_git(self.root, "checkout", "--detach", "HEAD")
        report, _git = self._audit()
        item = report["worktrees"]["items"][0]
        self.assertTrue(item["detached"])
        self.assertIn("DETACHED", item["hints"])

    def test_ancestor_of_main_detection(self) -> None:
        _run_git(self.root, "checkout", "-b", "side")
        (self.root / "side.txt").write_text("side\n", encoding="utf-8")
        _run_git(self.root, "add", "side.txt")
        _run_git(self.root, "commit", "-m", "side")
        report_unique, _ = self._audit()
        unique_item = report_unique["worktrees"]["items"][0]
        self.assertFalse(unique_item["head_is_ancestor_of_origin_main"])
        self.assertIn("UNIQUE_COMMITS_POSSIBLE", unique_item["hints"])

        _run_git(self.root, "checkout", "main")
        report_main, _ = self._audit()
        main_item = report_main["worktrees"]["items"][0]
        self.assertTrue(main_item["head_is_ancestor_of_origin_main"])
        self.assertIn("MERGED_OR_ANCESTOR", main_item["hints"])

    def test_cache_categorization(self) -> None:
        cache = self.root / "__pycache__"
        cache.mkdir()
        (cache / "mod.cpython-311.pyc").write_bytes(b"cache-bytes-0123456789")
        (self.root / ".pytest_cache").mkdir()
        (self.root / ".pytest_cache" / "v").write_text("pytest\n", encoding="utf-8")
        report, _ = self._audit()
        categories = {row["category"]: row for row in report["caches"]["categories"]}
        self.assertIn("pycache", categories)
        self.assertIn("pytest", categories)
        self.assertGreater(report["caches"]["total_bytes"], 0)
        self.assertEqual(report["summary"]["estimated_reviewable_reclaimable_bytes"], report["caches"]["total_bytes"])
        self.assertEqual(report["summary"]["reclaimable_basis"], "CONSERVATIVE_CACHES_ONLY")

    def test_protected_artifact_classification(self) -> None:
        artifacts = self.root / "artifacts" / "ftep-v1-002"
        artifacts.mkdir(parents=True)
        (artifacts / "receipt.json").write_text('{"kind":"evidence"}\n', encoding="utf-8")
        report, _ = self._audit()
        self.assertEqual(report["artifacts"]["classification"], "PROTECTED_OR_REVIEW_REQUIRED")
        self.assertFalse(report["artifacts"]["deletion_authority"])
        self.assertGreater(report["artifacts"]["total_bytes"], 0)
        self.assertNotEqual(
            report["summary"]["estimated_reviewable_reclaimable_bytes"],
            report["artifacts"]["total_bytes"],
        )

    def test_no_double_counting_linked_venvs(self) -> None:
        canonical = self.root / "canonical-venv"
        (canonical / "lib").mkdir(parents=True)
        (canonical / "pyvenv.cfg").write_text("home = python\n", encoding="utf-8")
        (canonical / "lib" / "site.py").write_bytes(b"x" * 4096)
        physical = self.root / ".venv"
        self.assertTrue(_try_dir_link(canonical, physical), "failed to create venv junction/symlink")
        extra = self.root / "work" / ".venv"
        extra.parent.mkdir()
        self.assertTrue(_try_dir_link(canonical, extra), "failed to create second venv link")
        report, _ = self._audit()
        self.assertEqual(report["dependencies"]["physical_venv_count"], 1)
        self.assertGreaterEqual(report["dependencies"]["linked_venv_count"], 1)
        physical_items = [
            item
            for item in report["dependencies"]["items"]
            if item.get("type") == "venv" and item.get("kind") == "PHYSICAL"
        ]
        self.assertEqual(len(physical_items), 1)
        linked_items = [
            item
            for item in report["dependencies"]["items"]
            if item.get("type") == "venv" and item.get("kind") != "PHYSICAL"
        ]
        self.assertGreaterEqual(len(linked_items), 1)

    def test_path_scan_does_not_escape_through_links(self) -> None:
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        secret = outside / "secret.bin"
        secret.write_bytes(b"S" * 200000)
        inside_link = self.root / "escape-link"
        self.assertTrue(_try_dir_link(outside, inside_link), "failed to create escape junction/symlink")
        report, _ = self._audit()
        largest = " ".join(row["path"] for row in report["largest_paths"])
        self.assertNotIn("secret.bin", largest)
        self.assertLess(int(report["repo"]["physical_bytes"]), 150000)

    def test_permission_unreadable_path_is_reported(self) -> None:
        blocked = self.root / "blocked"
        blocked.mkdir()
        (blocked / "file.txt").write_text("nope\n", encoding="utf-8")
        real_scandir = os.scandir

        def fake_scandir(path):
            if Path(path) == blocked:
                raise PermissionError("denied")
            return real_scandir(path)

        with patch("tools.storage_audit.os.scandir", side_effect=fake_scandir):
            report, _ = self._audit()
        self.assertTrue(any(row["path"] == str(blocked) for row in report["unreadable_paths"]))
        self.assertTrue(any(row["code"] == "UNREADABLE_PATHS_PRESENT" for row in report["warnings"]))

    def test_audit_performs_no_destructive_git_command(self) -> None:
        git = ReadOnlyGit()
        run_audit(start=self.root, scan_root=self.root, git=git, progress=lambda _m: None)
        self.assertTrue(git.history)
        for _cwd, argv in git.history:
            self.assertTrue(git_argv_is_allowed(argv), argv)
            verb = argv[0]
            self.assertNotIn(verb, {"gc", "prune", "clean", "reset", "checkout", "reflog"})

    def test_audit_does_not_mutate_tracked_repository_state(self) -> None:
        before = _run_git(self.root, "status", "--porcelain=v1").stdout
        head_before = _run_git(self.root, "rev-parse", "HEAD").stdout.strip()
        run_audit(start=self.root, scan_root=self.root, progress=lambda _m: None)
        after = _run_git(self.root, "status", "--porcelain=v1").stdout
        head_after = _run_git(self.root, "rev-parse", "HEAD").stdout.strip()
        self.assertEqual(before, after)
        self.assertEqual(head_before, head_after)

    def test_cli_json_and_top_option(self) -> None:
        (self.root / "big.txt").write_bytes(b"B" * 4096)
        stdout = io.StringIO()
        with patch.object(sys, "stdout", stdout):
            code = run_cli(["--json", "--top", "3", "--quiet", "--root", str(self.root)])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["schema_version"], SCHEMA_VERSION)
        self.assertLessEqual(len(payload["largest_paths"]), 3)

    def test_link_kind_physical_directory(self) -> None:
        path = self.root / "plain"
        path.mkdir()
        self.assertEqual(classify_link_kind(path), "PHYSICAL")


class CursorDiscoveryTests(unittest.TestCase):
    def test_slug_derives_from_path_without_hardcoded_user(self) -> None:
        slug = cursor_project_slug(Path(r"C:\Users\someone\Desktop\market-trading-platform"))
        self.assertTrue(slug.startswith("c-"))
        self.assertIn("someone", slug)
        self.assertNotIn("adame", slug)

    def test_override_outside_cursor_projects_is_unsupported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            previous = os.environ.get("IMP_CURSOR_PROJECT_DIR")
            os.environ["IMP_CURSOR_PROJECT_DIR"] = temporary
            try:
                path, status = discover_cursor_project_dir(Path(temporary))
            finally:
                if previous is None:
                    os.environ.pop("IMP_CURSOR_PROJECT_DIR", None)
                else:
                    os.environ["IMP_CURSOR_PROJECT_DIR"] = previous
        self.assertIsNone(path)
        self.assertEqual(status, "UNSUPPORTED_UNSAFE_PATH")


if __name__ == "__main__":
    unittest.main()

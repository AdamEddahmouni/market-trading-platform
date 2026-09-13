"""Regression tests for stdlib git repository discovery (including linked worktrees)."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.git_ref import (
    _parse_gitdir_pointer,
    git_common_dir,
    main_working_tree,
    read_git_head,
    repo_root,
)


def _run_git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(path: Path) -> str:
    _run_git(path, "init")
    _run_git(path, "config", "user.email", "test@example.com")
    _run_git(path, "config", "user.name", "Test User")
    (path / "README.md").write_text("seed\n", encoding="utf-8")
    _run_git(path, "add", "README.md")
    _run_git(path, "commit", "-m", "seed")
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


class ParseGitdirPointerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_absolute_pointer_windows_style(self) -> None:
        target = self.root / "metadata" / "git"
        target.mkdir(parents=True)
        git_file = self.root / ".git"
        git_file.write_text(f"gitdir: {target.as_posix()}\n", encoding="utf-8")
        resolved = _parse_gitdir_pointer(git_file)
        self.assertEqual(resolved, target.resolve())

    def test_relative_pointer(self) -> None:
        target = self.root / "metadata" / "git"
        target.mkdir(parents=True)
        git_file = self.root / ".git"
        git_file.write_text("gitdir: metadata/git\n", encoding="utf-8")
        resolved = _parse_gitdir_pointer(git_file)
        self.assertEqual(resolved, target.resolve())

    def test_malformed_pointer_rejected(self) -> None:
        git_file = self.root / ".git"
        git_file.write_text("not-a-git-pointer\n", encoding="utf-8")
        self.assertIsNone(_parse_gitdir_pointer(git_file))

    def test_missing_target_rejected(self) -> None:
        git_file = self.root / ".git"
        git_file.write_text("gitdir: missing/metadata\n", encoding="utf-8")
        self.assertIsNone(_parse_gitdir_pointer(git_file))


class GitRefRepositoryDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name) / "main"
        self.base.mkdir(parents=True)
        self.head = _init_repo(self.base)

    def test_standard_repository_root(self) -> None:
        self.assertEqual(repo_root(self.base), self.base.resolve())

    def test_standard_repository_subdirectory(self) -> None:
        nested = self.base / "src" / "pkg"
        nested.mkdir(parents=True)
        self.assertEqual(repo_root(nested), self.base.resolve())

    def test_standard_repository_head(self) -> None:
        self.assertEqual(read_git_head(start=self.base), self.head)

    def test_linked_worktree_root_and_subdirectory(self) -> None:
        worktree = Path(self.temporary.name) / "linked"
        _run_git(self.base, "worktree", "add", str(worktree), "-b", "linked-branch")
        self.assertEqual(repo_root(worktree), worktree.resolve())
        nested = worktree / "nested" / "module"
        nested.mkdir(parents=True)
        self.assertEqual(repo_root(nested), worktree.resolve())

    def test_linked_worktree_head_matches_main(self) -> None:
        worktree = Path(self.temporary.name) / "linked-head"
        _run_git(self.base, "worktree", "add", str(worktree), "-b", "linked-head-branch")
        self.assertEqual(read_git_head(start=worktree), self.head)

    def test_main_working_tree_matches_standard_checkout(self) -> None:
        self.assertEqual(main_working_tree(start=self.base), self.base.resolve())
        nested = self.base / "projects" / "integrated-market-platform"
        nested.mkdir(parents=True)
        self.assertEqual(main_working_tree(start=nested), self.base.resolve())
        common = git_common_dir(start=nested)
        self.assertIsNotNone(common)
        assert common is not None
        self.assertEqual(common, (self.base / ".git").resolve())

    def test_linked_worktree_main_working_tree_is_primary_checkout(self) -> None:
        worktree = Path(self.temporary.name) / "linked-main"
        _run_git(self.base, "worktree", "add", str(worktree), "-b", "linked-main-branch")
        nested = worktree / "projects" / "integrated-market-platform"
        nested.mkdir(parents=True)
        self.assertEqual(repo_root(nested), worktree.resolve())
        self.assertEqual(main_working_tree(start=nested), self.base.resolve())
        self.assertNotEqual(main_working_tree(start=nested), worktree.resolve())
        common = git_common_dir(start=nested)
        self.assertIsNotNone(common)
        assert common is not None
        self.assertEqual(common, (self.base / ".git").resolve())

    def test_main_working_tree_missing_git_is_none(self) -> None:
        orphan = Path(self.temporary.name) / "orphan-main"
        orphan.mkdir()
        self.assertIsNone(main_working_tree(start=orphan))
        self.assertIsNone(git_common_dir(start=orphan))

    def test_non_git_directory_rejected(self) -> None:
        orphan = Path(self.temporary.name) / "orphan"
        orphan.mkdir()
        with self.assertRaises(FileNotFoundError) as ctx:
            repo_root(orphan)
        self.assertEqual(str(ctx.exception), "GIT_REPOSITORY_NOT_FOUND")

    def test_malformed_git_file_blocks_parent_binding(self) -> None:
        fake = Path(self.temporary.name) / "fake"
        fake.mkdir()
        (fake / ".git").write_text("gitdir: nowhere\n", encoding="utf-8")
        with self.assertRaises(FileNotFoundError):
            repo_root(fake / "src")


class GitRefRealWorktreeRegressionTests(unittest.TestCase):
    """Ensure the performance worktree layout is recognized when executed in one."""

    def test_perf_worktree_pointer_layout(self) -> None:
        platform_root = Path(__file__).resolve().parents[2]
        monorepo_root = platform_root.parents[1]
        git_marker = monorepo_root / ".git"
        if not git_marker.is_file():
            self.skipTest("not executing inside a linked Git worktree")
        resolved_root = repo_root(monorepo_root)
        self.assertEqual(resolved_root, monorepo_root.resolve())
        head = read_git_head(start=monorepo_root)
        self.assertTrue(head)
        self.assertEqual(len(head), 40)


if __name__ == "__main__":
    unittest.main()

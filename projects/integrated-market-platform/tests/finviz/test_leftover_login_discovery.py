"""Worktree-aware leftover Finviz login discovery — paths only, no secrets."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from market_platform_foundation.finviz.config import (
    extra_operator_login_files,
    leftover_nested_imp_root,
    leftover_nested_imp_roots,
    operator_repo_search_roots,
    provider_env_path,
)
from market_platform_foundation.finviz.credential_manager import (  # noqa: E402
    reset_finviz_credential_manager,
)
from market_platform_foundation.providers.adapters.finviz_elite_context import (
    FINVIZ_CONTEXT_PROVIDER_ID,
    FINVIZ_LOGIN_NAMES,
    FINVIZ_TOKEN_NAMES,
)
from market_platform_foundation.providers.finviz_context_discovery import (
    discover_finviz_context_stack,
)

LOGIN_PASSWORD = "not-a-real-password"
FETCHED_TOKEN = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def _run_git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(path: Path) -> None:
    _run_git(path, "init")
    _run_git(path, "config", "user.email", "test@example.com")
    _run_git(path, "config", "user.name", "Test User")
    (path / "README.md").write_text("seed\n", encoding="utf-8")
    _run_git(path, "add", "README.md")
    _run_git(path, "commit", "-m", "seed")


def _write_login(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"username": "operator@example.com", "password": LOGIN_PASSWORD}),
        encoding="utf-8",
    )
    return path


def _resolved(paths: tuple[Path, ...]) -> set[Path]:
    return {path.resolve() for path in paths}


def _stub_login_session(*, token: str = FETCHED_TOKEN) -> MagicMock:
    session = MagicMock()
    session.get.side_effect = [
        MagicMock(
            status_code=200,
            text='<form action="/login_submit"></form>',
            url="https://finviz.com/login-email?remember=true",
            headers={"content-type": "text/html"},
        ),
        MagicMock(
            status_code=200,
            text=f'<a href="/export/screener?auth={token}">API</a>',
            url="https://elite.finviz.com/api_explanation",
            headers={"content-type": "text/html"},
        ),
        MagicMock(
            status_code=200,
            text="Ticker,Price\nAAPL,100\n",
            url="https://elite.finviz.com/export/screener",
            headers={"content-type": "text/csv"},
        ),
    ]
    session.post.return_value = MagicMock(
        status_code=200,
        text="account",
        url="https://finviz.com/",
        headers={"content-type": "text/html"},
    )
    return session


def _isolated_env() -> dict[str, str]:
    isolated = {name: "" for name in (*FINVIZ_TOKEN_NAMES, *FINVIZ_LOGIN_NAMES)}
    isolated["IMP_FINVIZ_SECRET_DIR"] = ""
    isolated["IMP_PROVIDER_ENV"] = ""
    isolated["IMP_FINVIZ_LIVE"] = ""
    return isolated


class LeftoverLoginDiscoveryTests(unittest.TestCase):
    def test_worktree_relative_nested_path_is_still_listed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hop_imp = (
                Path(tmp)
                / "market-trading-platform"
                / ".worktrees"
                / "hop"
                / "projects"
                / "integrated-market-platform"
            )
            hop_imp.mkdir(parents=True)
            isolated = _isolated_env()
            with patch.dict(os.environ, isolated, clear=False):
                relative = leftover_nested_imp_root(start=hop_imp)
                self.assertEqual(
                    relative.resolve(),
                    (hop_imp.parent.parent / "integrated-market-platform").resolve(),
                )
                files = extra_operator_login_files(start=hop_imp)
            self.assertIn(
                (relative / ".private" / "finviz-login.json").resolve(),
                _resolved(files),
            )

    def test_dot_worktrees_parent_finds_main_checkout_leftover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "market-trading-platform"
            leftover = _write_login(
                main / "integrated-market-platform" / ".private" / "finviz-login.json"
            )
            hop_imp = (
                main / ".worktrees" / "hop" / "projects" / "integrated-market-platform"
            )
            hop_imp.mkdir(parents=True)
            hop_leftover = (
                hop_imp.parent.parent / "integrated-market-platform" / ".private" / "finviz-login.json"
            )
            self.assertFalse(hop_leftover.is_file())
            isolated = _isolated_env()
            with patch.dict(os.environ, isolated, clear=False):
                roots = operator_repo_search_roots(start=hop_imp)
                files = extra_operator_login_files(start=hop_imp)
            self.assertIn(main.resolve(), _resolved(roots))
            self.assertIn(leftover.resolve(), _resolved(files))
            dumped = " ".join(path.as_posix() for path in files)
            self.assertNotIn(LOGIN_PASSWORD, dumped)
            self.assertNotIn("operator@example.com", dumped)

    def test_linked_worktree_uses_git_common_dir_main_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "market-trading-platform"
            main.mkdir()
            _init_repo(main)
            leftover = _write_login(
                main / "integrated-market-platform" / ".private" / "finviz-login.json"
            )
            hop = Path(tmp) / "sibling-hop"
            _run_git(main, "worktree", "add", str(hop), "-b", "leftover-hop")
            hop_imp = hop / "projects" / "integrated-market-platform"
            hop_imp.mkdir(parents=True)
            hop_leftover = hop / "integrated-market-platform" / ".private" / "finviz-login.json"
            self.assertFalse(hop_leftover.is_file())
            isolated = _isolated_env()
            with patch.dict(os.environ, isolated, clear=False):
                files = extra_operator_login_files(start=hop_imp)
                leftover_roots = leftover_nested_imp_roots(start=hop_imp)
            self.assertIn(leftover.resolve(), _resolved(files))
            self.assertIn(leftover.parent.parent.resolve(), _resolved(leftover_roots))

    def test_nested_clone_hop_finds_leftover_clone_private(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            leftover_clone = Path(tmp) / "market-trading-platform" / "integrated-market-platform"
            leftover = _write_login(leftover_clone / ".private" / "finviz-login.json")
            hop = leftover_clone / ".worktrees" / "hop"
            hop.mkdir(parents=True)
            isolated = _isolated_env()
            with patch.dict(os.environ, isolated, clear=False):
                files = extra_operator_login_files(start=hop)
            self.assertIn(leftover.resolve(), _resolved(files))

    def test_secret_dir_isolates_extra_operator_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hop_imp = Path(tmp) / "projects" / "integrated-market-platform"
            hop_imp.mkdir(parents=True)
            isolated = _isolated_env()
            isolated["IMP_FINVIZ_SECRET_DIR"] = str(Path(tmp) / "canonical")
            with patch.dict(os.environ, isolated, clear=False):
                self.assertEqual(extra_operator_login_files(start=hop_imp), ())

    def test_missing_leftover_fails_closed_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hop_imp = (
                Path(tmp)
                / "market-trading-platform"
                / ".worktrees"
                / "hop"
                / "projects"
                / "integrated-market-platform"
            )
            hop_imp.mkdir(parents=True)
            isolated = _isolated_env()
            with patch.dict(os.environ, isolated, clear=False):
                files = extra_operator_login_files(start=hop_imp)
            self.assertTrue(files)
            self.assertFalse(any(path.is_file() for path in files))

    def test_provider_env_uses_main_checkout_leftover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "market-trading-platform"
            leftover_env = (
                main / "integrated-market-platform" / ".private" / "providers.env"
            )
            leftover_env.parent.mkdir(parents=True)
            leftover_env.write_text("FINVIZ_USERNAME=operator@example.com\n", encoding="utf-8")
            hop_imp = (
                main / ".worktrees" / "hop" / "projects" / "integrated-market-platform"
            )
            hop_imp.mkdir(parents=True)
            isolated = _isolated_env()
            with patch.dict(os.environ, isolated, clear=False):
                found = provider_env_path(start=hop_imp)
            self.assertIsNotNone(found)
            assert found is not None
            self.assertEqual(found.resolve(), leftover_env.resolve())


class LeftoverLoginAutofetchTests(unittest.TestCase):
    def test_autofetch_from_main_checkout_leftover_without_junction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            main = Path(tmp) / "market-trading-platform"
            main.mkdir()
            _init_repo(main)
            leftover = _write_login(
                main / "integrated-market-platform" / ".private" / "finviz-login.json"
            )
            hop = Path(tmp) / "sibling-hop"
            _run_git(main, "worktree", "add", str(hop), "-b", "overlay-hop")
            hop_imp = hop / "projects" / "integrated-market-platform"
            hop_imp.mkdir(parents=True)
            hop_leftover = hop / "integrated-market-platform" / ".private" / "finviz-login.json"
            self.assertFalse(hop_leftover.is_file())
            isolated = _isolated_env()
            isolated["IMP_PROVIDER_ENV"] = str(hop_imp / ".private" / "missing.env")
            with patch(
                "market_platform_foundation.finviz.config.REPO_ROOT", hop_imp
            ), patch(
                "market_platform_foundation.finviz.secure_store.REPO_ROOT", hop_imp
            ), patch.dict(os.environ, isolated, clear=False):
                reset_finviz_credential_manager()
                adapter, discovery = discover_finviz_context_stack(
                    env=None,
                    session_factory=lambda: _stub_login_session(),
                )
                self.assertEqual(discovery.login_source, "NESTED_LOGIN_FILE")
                self.assertEqual(discovery.auto_fetch_status, "FETCHED")
                self.assertTrue(discovery.overlay_token_present)
                self.assertFalse(discovery.is_l1)
                self.assertFalse(discovery.is_paper_comparator)
                self.assertEqual(adapter.provider_id, FINVIZ_CONTEXT_PROVIDER_ID)
                repaired_login = hop_imp / ".private" / "finviz-login.json"
                repaired_token = hop_imp / ".private" / "finviz-token.txt"
                self.assertTrue(repaired_login.is_file())
                self.assertTrue(repaired_token.is_file())
                dumped = json.dumps(discovery.to_dict())
                self.assertNotIn(FETCHED_TOKEN, dumped)
                self.assertNotIn(LOGIN_PASSWORD, dumped)
                self.assertNotIn("operator@example.com", dumped)
                listing = extra_operator_login_files(start=hop_imp)
                self.assertIn(leftover.resolve(), _resolved(listing))
                reset_finviz_credential_manager()


if __name__ == "__main__":
    unittest.main()

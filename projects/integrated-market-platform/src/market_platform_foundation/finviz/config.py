"""Finviz Elite configuration — constants and non-secret paths."""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from ..git_ref import main_working_tree

REPO_ROOT = Path(__file__).resolve().parents[3]

_NESTED_LEFTOVER_CLONE = "integrated-market-platform"
_WORKTREES_DIRNAME = ".worktrees"
_LOGIN_RELATIVE = Path(".private") / "finviz-login.json"
_PROVIDERS_ENV_RELATIVE = Path(".private") / "providers.env"
_SHORT_SQUEEZE_PROVIDERS_ENV = (
    Path("short-squeeze-project") / "short-squeeze-core" / ".private" / "providers.env"
)

FINVIZ_EXPORT_URL = "https://elite.finviz.com/export/screener"
FINVIZ_NEWS_URL = "https://elite.finviz.com/news_export.ashx"
FINVIZ_OPTIONS_URL = "https://elite.finviz.com/export/options"
FINVIZ_EXPORT_VERSION = "152"
DEFAULT_SCREENER_COLUMNS = "1,25,26,30,31,84,42,43,49,50,52,53,55,59,56,60,61,64,65,66,57,81,86,87"

MIN_REQUEST_INTERVAL_S = 5.0
SCREENER_CACHE_TTL_S = 120.0
NEWS_CACHE_TTL_S = 180.0
OPTIONS_CACHE_TTL_S = 300.0
SYMBOL_CACHE_TTL_S = 300.0
FUNDAMENTAL_CACHE_TTL_S = 3600.0

REDACT_KEYS = (
    "auth",
    "token",
    "api_token",
    "password",
    "passwd",
    "secret",
    "key",
    "login",
    "pwd",
    "cookie",
    "set-cookie",
    "session",
    "sessionid",
    "authorization",
)


def finviz_live_enabled() -> bool:
    return os.environ.get("IMP_FINVIZ_LIVE", "").strip().lower() in ("1", "true", "yes")


def _dedupe_paths(paths: Iterable[Path]) -> tuple[Path, ...]:
    seen: set[str] = set()
    ordered: list[Path] = []
    for path in paths:
        try:
            key = str(path.resolve())
        except OSError:
            key = str(path)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
    return tuple(ordered)


def _worktree_relative_monorepo(start: Path) -> Path:
    """Monorepo root inferred from canonical IMP ``projects/<name>`` layout."""

    try:
        resolved = start.resolve()
    except OSError:
        resolved = start
    if resolved.name == _NESTED_LEFTOVER_CLONE and resolved.parent.name == "projects":
        return resolved.parent.parent
    return resolved


def _worktree_container_root(start: Path) -> Path | None:
    """Parent of ``.worktrees`` when ``start`` is inside a sibling hop checkout."""

    try:
        current = start.resolve()
    except OSError:
        return None
    for parent in [current, *current.parents]:
        if parent.name != _WORKTREES_DIRNAME:
            continue
        container = parent.parent
        try:
            if container.is_dir():
                return container
        except OSError:
            return None
        return None
    return None


def operator_repo_search_roots(*, start: Path | None = None) -> tuple[Path, ...]:
    """Repo roots that may hold the leftover nested IMP clone.

    Order: current worktree, git common-dir main checkout, ``.worktrees``
    parent. Missing git metadata is skipped (fail closed). Never logs file
    contents and never spawns git.
    """

    anchor = start if start is not None else REPO_ROOT
    roots: list[Path] = [_worktree_relative_monorepo(anchor)]
    try:
        main = main_working_tree(start=anchor)
    except OSError:
        main = None
    if main is not None:
        roots.append(main)
    container = _worktree_container_root(anchor)
    if container is not None:
        roots.append(container)
    return _dedupe_paths(roots)


def leftover_nested_imp_roots(*, start: Path | None = None) -> tuple[Path, ...]:
    """Leftover nested ``integrated-market-platform/`` clone candidates.

    Includes the nested leftover relative to each operator repo root, and the
    root itself when it *is* that leftover clone (a hop of the nested tree).
    """

    leftovers: list[Path] = []
    for repo in operator_repo_search_roots(start=start):
        leftovers.append(repo / _NESTED_LEFTOVER_CLONE)
        if repo.name == _NESTED_LEFTOVER_CLONE:
            leftovers.append(repo)
    return _dedupe_paths(leftovers)


def leftover_nested_imp_root(*, start: Path | None = None) -> Path:
    """Worktree-relative leftover ``integrated-market-platform/`` clone (not canonical IMP)."""

    anchor = start if start is not None else REPO_ROOT
    return _worktree_relative_monorepo(anchor) / _NESTED_LEFTOVER_CLONE


def extra_operator_login_files(*, start: Path | None = None) -> tuple[Path, ...]:
    """Existing operator ``finviz-login.json`` files outside canonical IMP ``.private``.

    Skipped when ``IMP_FINVIZ_SECRET_DIR`` isolates tests. Never logs file
    contents. Search is worktree-aware: the leftover nested clone on the
    operator machine stores Elite login at
    ``integrated-market-platform/.private/finviz-login.json`` relative to the
    current worktree, the git common-dir main checkout, and the parent of
    ``.worktrees`` — so sibling hops do not need a junction.
    """

    if os.environ.get("IMP_FINVIZ_SECRET_DIR"):
        return ()
    return tuple(root / _LOGIN_RELATIVE for root in leftover_nested_imp_roots(start=start))


def provider_env_path(*, start: Path | None = None) -> Path | None:
    override = os.environ.get("IMP_PROVIDER_ENV")
    if override:
        path = Path(override).expanduser()
        return path if path.is_file() else None
    anchor = start if start is not None else REPO_ROOT
    candidates: list[Path] = [anchor / _PROVIDERS_ENV_RELATIVE]
    for leftover in leftover_nested_imp_roots(start=start):
        candidates.append(leftover / _PROVIDERS_ENV_RELATIVE)
    candidates.append(anchor.parent / _SHORT_SQUEEZE_PROVIDERS_ENV)
    for repo in operator_repo_search_roots(start=start):
        candidates.append(repo / _SHORT_SQUEEZE_PROVIDERS_ENV)
    for candidate in _dedupe_paths(candidates):
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, _, value = text.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    except OSError:
        return {}
    return values


def finviz_api_key() -> str | None:
    from .credential_manager import get_finviz_credential_manager

    return get_finviz_credential_manager().get_token()


def finviz_evidence_root() -> Path:
    override = os.environ.get("IMP_FINVIZ_EVIDENCE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / "evidence" / "market_data" / "finviz"


def finviz_capture_root() -> Path:
    override = os.environ.get("IMP_FINVIZ_CAPTURE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    return REPO_ROOT / "data" / "captures" / "finviz"

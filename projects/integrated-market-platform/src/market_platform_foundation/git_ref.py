"""Stdlib-only git reference resolution (no subprocess)."""

from __future__ import annotations

from pathlib import Path

_GITDIR_PREFIX = "gitdir:"


def _parse_gitdir_pointer(git_file: Path) -> Path | None:
    """Resolve the git metadata directory from a linked-worktree `.git` file."""
    try:
        raw = git_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw.startswith(_GITDIR_PREFIX):
        return None
    target = raw[len(_GITDIR_PREFIX) :].strip()
    if not target:
        return None
    git_dir = Path(target)
    if not git_dir.is_absolute():
        git_dir = (git_file.parent / git_dir).resolve()
    else:
        git_dir = git_dir.resolve()
    if not git_dir.is_dir():
        return None
    return git_dir


def _locate_git(start: Path) -> tuple[Path, Path] | None:
    """Return ``(worktree_root, git_metadata_dir)`` walking upward from ``start``."""
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for parent in [current, *current.parents]:
        marker = parent / ".git"
        if marker.is_dir():
            return parent, marker
        if marker.is_file():
            git_dir = _parse_gitdir_pointer(marker)
            if git_dir is not None:
                return parent, git_dir
            return None
    return None


def _git_dir(start: Path | None = None) -> Path | None:
    located = _locate_git((start or Path(__file__).resolve()))
    if located is None:
        return None
    return located[1]


def _git_common_dir(git_dir: Path) -> Path:
    """Return the shared metadata directory for linked worktrees."""
    commondir_file = git_dir / "commondir"
    if not commondir_file.is_file():
        return git_dir
    try:
        relative = commondir_file.read_text(encoding="utf-8").strip()
    except OSError:
        return git_dir
    if not relative:
        return git_dir
    return (git_dir / relative).resolve()


def git_common_dir(*, start: Path | None = None) -> Path | None:
    """Shared git metadata directory (primary ``.git`` for linked worktrees).

    Fail closed: missing or unreadable git metadata returns None. Never spawns
    a git subprocess and never reads working-tree file contents.
    """

    git_dir = _git_dir(start)
    if git_dir is None:
        return None
    return _git_common_dir(git_dir)


def main_working_tree(*, start: Path | None = None) -> Path | None:
    """Working tree that owns the shared git directory.

    Linked worktrees store a ``commondir`` pointer into the primary ``.git``
    directory; that directory's parent is the main checkout. Ordinary
    single-checkout clones return the same path as the current worktree.
    Fail closed: missing git metadata returns None.
    """

    located = _locate_git((start or Path(__file__).resolve()))
    if located is None:
        return None
    worktree_root, git_dir = located
    common = _git_common_dir(git_dir)
    if common.name == ".git":
        parent = common.parent
        try:
            if parent.is_dir():
                return parent
        except OSError:
            return worktree_root
    return worktree_root


def repo_root(start: Path | None = None) -> Path:
    start_path = (start or Path(__file__).resolve()).resolve()
    if start_path.is_file():
        start_path = start_path.parent
    located = _locate_git(start_path)
    if located is None:
        raise FileNotFoundError("GIT_REPOSITORY_NOT_FOUND")
    worktree_root, _ = located
    if start is None:
        # When the platform tree is embedded inside a larger monorepo (e.g.
        # the market-trading-platform snapshot under
        # projects/integrated-market-platform), the nearest .git directory is
        # an ancestor of the platform tree. Repository-relative artifacts live
        # at the platform tree root (phase0-dependency-lock.json / artifacts/),
        # so prefer the deepest module anchor that still carries that marker
        # without ever climbing above the git root. In the platform's own
        # repository the anchor IS the git root, so behavior is unchanged.
        anchor = Path(__file__).resolve().parent
        for candidate in [anchor, *anchor.parents]:
            if candidate == worktree_root:
                break
            if (candidate / "phase0-dependency-lock.json").is_file():
                return candidate
    return worktree_root


def read_git_head(*, start: Path | None = None) -> str | None:
    git_dir = _git_dir(start)
    if git_dir is None:
        return None
    head_path = git_dir / "HEAD"
    try:
        if not head_path.is_file():
            return None
        head = head_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not head:
        return None
    if head.startswith("ref: "):
        return read_git_ref(head[5:].strip(), git_dir=git_dir)
    return head


def _read_loose_ref(ref: str, git_dir: Path) -> str | None:
    ref_path = git_dir / ref
    try:
        if ref_path.is_file():
            value = ref_path.read_text(encoding="utf-8").strip()
            return value or None
    except OSError:
        return None
    return None


def _read_packed_ref(ref: str, git_dir: Path) -> str | None:
    packed = git_dir / "packed-refs"
    try:
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1] == ref:
                    return parts[0]
    except OSError:
        return None
    return None


def read_git_ref(ref: str, *, git_dir: Path | None = None) -> str | None:
    resolved_git_dir = git_dir or _git_dir()
    if resolved_git_dir is None:
        return None
    search_dirs: list[Path] = []
    for candidate in (resolved_git_dir, _git_common_dir(resolved_git_dir)):
        if candidate not in search_dirs:
            search_dirs.append(candidate)
    for search_dir in search_dirs:
        value = _read_loose_ref(ref, search_dir)
        if value is not None:
            return value
    for search_dir in search_dirs:
        value = _read_packed_ref(ref, search_dir)
        if value is not None:
            return value
    return None


def read_remote_ref(remote: str, branch: str, *, start: Path | None = None) -> str | None:
    git_dir = _git_dir(start)
    if git_dir is None:
        return None
    return read_git_ref(f"refs/remotes/{remote}/{branch}", git_dir=git_dir)

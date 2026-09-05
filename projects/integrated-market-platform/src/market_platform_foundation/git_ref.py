"""Stdlib-only git reference resolution (no subprocess)."""

from __future__ import annotations

from pathlib import Path


def _git_dir(start: Path | None = None) -> Path | None:
    current = (start or Path(__file__).resolve()).resolve()
    if current.is_file():
        current = current.parent
    for parent in [current, *current.parents]:
        candidate = parent / ".git"
        if candidate.is_dir():
            return candidate
    return None


def repo_root(start: Path | None = None) -> Path:
    git_dir = _git_dir(start)
    if git_dir is None:
        raise FileNotFoundError("GIT_REPOSITORY_NOT_FOUND")
    git_root = git_dir.parent
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
            if candidate == git_root:
                break
            if (candidate / "phase0-dependency-lock.json").is_file():
                return candidate
    return git_root


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


def read_git_ref(ref: str, *, git_dir: Path | None = None) -> str | None:
    resolved_git_dir = git_dir or _git_dir()
    if resolved_git_dir is None:
        return None
    ref_path = resolved_git_dir / ref
    try:
        if ref_path.is_file():
            value = ref_path.read_text(encoding="utf-8").strip()
            return value or None
    except OSError:
        return None
    packed = resolved_git_dir / "packed-refs"
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


def read_remote_ref(remote: str, branch: str, *, start: Path | None = None) -> str | None:
    git_dir = _git_dir(start)
    if git_dir is None:
        return None
    return read_git_ref(f"refs/remotes/{remote}/{branch}", git_dir=git_dir)

"""Check links inside ``docs/**/*.md``: file targets exist and fragments match headings.

Purpose
-------
Docs drift when files are renamed or deleted and their referrers are not
updated. This checker fails CI whenever:

- a relative markdown link found in a file under the scanned tree points at a
  file that does not exist (or exists under a different case), or
- a link carries a ``#fragment`` (``[x](#section)`` or ``[x](file.md#section)``)
  and no heading in the target file slugs to that fragment under GitHub's
  heading-anchor rules.

Scope and rules
---------------
- By default every markdown file under ``docs/`` is scanned (override with
  positional roots: ``python tools/check_doc_links.py docs docs2``).
- ``--git-tracked`` scans the markdown files the *git repository containing
  the working directory* tracks (``git ls-files``) instead of walking a
  directory tree — the right mode for a whole repo or monorepo. Add
  ``--include-untracked`` to also scan non-ignored, not-yet-committed
  markdown files.
- ``--exclude NAME`` (repeatable) drops any scanned file whose path contains a
  path segment named ``NAME`` — for generated mirrors and vendored trees that
  are not real documentation (for example ``--exclude .railway-deploy``).
- Only inline links (``[text](target)`` and ``![alt](target)``) are checked.
  Targets inside fenced code blocks or inline code spans are ignored because
  they are prose/code, not rendered links.
- Remote links (``http://``, ``https://``, ``mailto:``, …) are ignored.
- The target is resolved relative to the file that contains the link. ``../``
  may point anywhere in the repository (for example ``../README.md``).
- A target ending in ``/`` is treated as a directory link and passes if that
  directory exists.
- ``#fragment`` links are checked against heading slugs generated with
  GitHub's anchor algorithm: lowercase; keep letters, digits, underscores and
  hyphens; delete other punctuation without inserting separators; turn every
  space into a hyphen without collapsing runs; repeated identical slugs get
  ``-1``, ``-2``, … suffixes (ATX and setext headings are recognized;
  fenced-code content is ignored).
- Case is compared exactly against the parent directory listing, so a link to
  ``limitations.md`` fails when the file is ``LIMITATIONS.md`` on every OS,
  including case-insensitive filesystems. Fragment matching is likewise exact.

Usage
-----
Run from the package root (``short-squeeze-core/``):

    # Scan one or more doc trees
    python tools/check_doc_links.py docs
    python tools/check_doc_links.py docs ../other-project/docs

    # Scan every markdown file a git repo tracks (from inside that repo)
    python tools/check_doc_links.py --git-tracked
    python tools/check_doc_links.py --git-tracked --include-untracked \
        --exclude .railway-deploy --exclude .pytest-run-*

Exit code is 0 when every link resolves, 1 when any link is broken, and 2 on
usage or configuration errors.
"""

from __future__ import annotations

import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

_SCAN_DEFAULT = "docs"
_MARKDOWN_SUFFIX = ".md"

# Inline links: [text](target) and image links ![alt](target). Checked per line
# after fenced blocks and inline code have been excluded.
_INLINE_LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")

_INLINE_CODE = re.compile(r"`[^`]*`")
# Code span with the inner text captured (used when reconstructing the
# rendered text of a heading before slugging).
_CODE_SPAN = re.compile(r"`([^`]*)`")
_FENCE_MARK = ("```", "~~~")
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")

_ATX_HEADING = re.compile(r"^#{1,6}(?:\s+|$)(.*)$")
_SETEXT_UNDERLINE = re.compile(r"^\s*(=+|-+)\s*$")
_LINK_TEXT = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_HTML_TAG = re.compile(r"<[^>]+>")


class BrokenLink:
    """A single link whose file target or fragment does not exist."""

    __slots__ = ("source", "line", "target")

    def __init__(self, source: Path, line: int, target: str) -> None:
        self.source = source
        self.line = line
        self.target = target

    def __str__(self) -> str:
        if "#" in self.target:
            kind = "link anchor not found"
        else:
            kind = "link target not found"
        return f"{self.source}:{self.line}: {kind}: {self.target}"


# ---------------------------------------------------------------------------
# Link parsing
# ---------------------------------------------------------------------------


def _split_target(raw: str) -> str | None:
    """Return the file portion of a raw link target, or ``None`` to ignore.

    ``None`` covers remote URLs, empty targets, and pure-fragment targets
    (``#section`` has no file component). ``%XX`` escapes are decoded; titles
    (``path "title"``), whole-target angle brackets (``<path>``,
    ``<path#frag>``), and ``#fragment`` suffixes are stripped.
    """
    target, _fragment = _split_path_and_fragment(raw)
    return target


def _split_path_and_fragment(raw: str) -> tuple[str | None, str | None]:
    """Split a raw link target into ``(path, fragment)``.

    ``path`` is ``None`` for targets with no file component (remote URLs,
    empty targets, pure ``#fragment`` links). ``fragment`` is ``None`` when the
    link carries no fragment.
    """
    target = raw.strip()
    if not target:
        return None, None
    # Remote / scheme links are not filesystem targets.
    if _SCHEME.match(target):
        return None, None
    # Whole-target angle brackets: <file.md> or <file.md#anchor>.
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1].strip()
    # Split off a title, if present: path "Title" or path 'Title'.
    if ' "' in target:
        target = target.split(' "', 1)[0]
    elif " '" in target:
        target = target.split(" '", 1)[0]
    fragment: str | None = None
    if "#" in target:
        target, fragment = target.split("#", 1)
        fragment = unquote(fragment).strip() or None
    target = unquote(target).strip()
    return (target or None), fragment


def iter_links(text: str) -> list[tuple[int, str]]:
    """Yield ``(line_number, file_target)`` for every link with a file target.

    Fenced code blocks (````` ``` ```` / ``~~~``) and inline code spans are
    skipped so code that merely looks like a link is never checked. Line
    numbers refer to the original ``text``. Pure-fragment links (``#x``) are
    not file links and are validated separately by :func:`check_file`.
    """
    results: list[tuple[int, str]] = []
    for line_no, raw in _iter_raw_targets(text):
        target = _split_target(raw)
        if target is not None:
            results.append((line_no, target))
    return results


def _iter_raw_targets(text: str):
    """Yield ``(line_number, raw_target)`` for every checkable inline link."""
    in_fence = False
    for line_no, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith(_FENCE_MARK):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = _INLINE_CODE.sub("", raw)
        for match in _INLINE_LINK.finditer(line):
            yield line_no, match.group(1)


# ---------------------------------------------------------------------------
# GitHub heading slugs
# ---------------------------------------------------------------------------


def _strip_inline_markup(text: str) -> str:
    """Reduce heading source to its rendered text for slugging."""
    text = _LINK_TEXT.sub(r"\1", text)
    text = _CODE_SPAN.sub(r"\1", text)
    text = _HTML_TAG.sub("", text)
    # Emphasis markers disappear when rendered.
    text = text.replace("**", "").replace("__", "").replace("~~", "")
    return text


def github_slug(text: str) -> str:
    """Return the GitHub-style anchor slug for a heading's rendered text.

    Mirrors the ``github-slugger`` rules GitHub uses for heading anchors:
    lowercase; delete punctuation and symbols without inserting separators;
    keep letters, digits, underscores and hyphens; turn *every* space into a
    hyphen without collapsing runs (so ``IBKR / Finviz`` becomes
    ``ibkr--finviz``, exactly as GitHub renders it). Repeated identical slugs
    get ``-1``, ``-2``, … suffixes, assigned by the caller.
    """
    text = unicodedata.normalize("NFC", _strip_inline_markup(text)).lower()
    kept: list[str] = []
    for char in text:
        if char.isalnum() or char in {"_", "-"}:
            kept.append(char)
        elif char == " ":
            kept.append("-")
        # Everything else (punctuation, symbols, control chars, tabs) is
        # deleted without inserting a separator.
    return "".join(kept)


def extract_heading_slugs(text: str) -> list[str]:
    """Return the anchor slugs of every heading, in document order.

    ATX (``## Text``) and setext (``Text`` + ``===``/``---``) headings are
    recognized. Content inside fenced code blocks never counts. Repeated
    identical headings receive GitHub's ``-1``, ``-2``, … suffixes.
    """
    slugs: list[str] = []
    counts: dict[str, int] = {}
    in_fence = False
    pending_paragraph: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(_FENCE_MARK):
            in_fence = not in_fence
            pending_paragraph = None
            continue
        if in_fence:
            pending_paragraph = None
            continue
        heading_text: str | None = None
        if stripped.startswith("#"):
            match = _ATX_HEADING.match(line)
            if match:
                heading_text = match.group(1)
                # GFM closing sequence: "## Title ##"
                heading_text = re.sub(r"\s+#+\s*$", "", heading_text).strip()
                pending_paragraph = None
        elif _SETEXT_UNDERLINE.match(stripped):
            if pending_paragraph is not None:
                # Setext heading: text line directly above the underline.
                heading_text = pending_paragraph
            pending_paragraph = None
        elif not stripped:
            pending_paragraph = None
        else:
            # Candidate paragraph content for a following setext underline.
            pending_paragraph = stripped
        if heading_text is None:
            continue
        slug = github_slug(heading_text)
        if not slug:
            continue
        counts[slug] = counts.get(slug, 0) + 1
        slugs.append(slug if counts[slug] == 1 else f"{slug}-{counts[slug] - 1}")
    return slugs


def _heading_slugs_for(path: Path) -> set[str]:
    """Return the set of heading slugs that exist in a markdown file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return set(extract_heading_slugs(text))


# ---------------------------------------------------------------------------
# Existence rules
# ---------------------------------------------------------------------------


def _case_exact_exists(candidate: Path) -> bool:
    """True when ``candidate`` exists with exactly the same case on disk."""
    if not candidate.exists():
        return False
    parent = candidate.parent
    try:
        entries = set(parent.iterdir())
    except OSError:
        return candidate.exists()
    name = candidate.name
    return any(entry.name == name for entry in entries)


def _target_exists(base_dir: Path, target: str) -> bool:
    """Resolve ``target`` relative to ``base_dir`` and test existence.

    Directory links (trailing ``/``) pass when the directory exists.
    """
    if target.endswith("/"):
        return _case_exact_exists(base_dir / target.rstrip("/"))
    if target.endswith((".md", ".png", ".jpg", ".json", ".yml", ".yaml", ".txt",
                         ".py", ".html", ".css", ".js", ".env.example", ".toml",
                         ".csv", ".zip", ".pdf", ".svg", ".gif", ".jpeg")):
        return _case_exact_exists(base_dir / target)
    # Unknown suffix (or none): accept either a file or a directory.
    return _case_exact_exists(base_dir / target)


def check_file(path: Path, report: list[BrokenLink]) -> None:
    """Check every link in a single markdown file, appending failures.

    File targets are checked for existence. ``#fragment`` links (same-file or
    cross-file) are checked against the target file's GitHub-style heading
    slugs.
    """
    # errors="replace": a legacy-encoded file must not crash the whole scan;
    # undecodable bytes become U+FFFD and the file is still checked.
    text = path.read_text(encoding="utf-8", errors="replace")
    self_slugs: set[str] | None = None
    slug_cache: dict[Path, set[str]] = {}
    for line_no, raw in _iter_raw_targets(text):
        file_target, fragment = _split_path_and_fragment(raw)
        if file_target is not None:
            if not _target_exists(path.parent, file_target):
                report.append(BrokenLink(path, line_no, file_target))
                continue
        if fragment is None:
            continue
        if file_target is None:
            # Same-file fragment link: [x](#section)
            if self_slugs is None:
                self_slugs = set(extract_heading_slugs(text))
            slugs = self_slugs
            display = f"#{fragment}"
        else:
            resolved = path.parent / file_target
            if resolved not in slug_cache:
                slug_cache[resolved] = _heading_slugs_for(resolved)
            slugs = slug_cache[resolved]
            display = f"{file_target}#{fragment}"
        if fragment not in slugs:
            report.append(BrokenLink(path, line_no, display))


def check_tree(root: Path) -> list[BrokenLink]:
    """Check every markdown file under ``root`` (recursively)."""
    report: list[BrokenLink] = []
    for path in sorted(root.rglob(f"*{_MARKDOWN_SUFFIX}")):
        if not path.is_file():
            continue
        check_file(path, report)
    return report


def _git(args: list[str], cwd: Path) -> str | None:
    """Run ``git`` with ``-C <cwd>``; return stdout or ``None`` on failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace")


def git_tracked_markdown(
    repo_root: Path,
    *,
    include_untracked: bool = False,
    exclude: set[str] | None = None,
) -> list[Path]:
    """Return the markdown files a git repository tracks (plus, optionally,
    non-ignored untracked markdown files).

    ``git ls-files`` honors the repository's ignore rules and never descends
    into nested repositories, so this is the clean way to scan a whole
    workspace repo without touching vendor clones, build output, or caches.
    """
    tracked = _git(["ls-files", "-z", "--", "*.md"], repo_root)
    files: set[Path] = set()
    if tracked is not None:
        files.update(
            repo_root / path for path in tracked.split("\0") if path
        )
    if include_untracked:
        untracked = _git(
            ["ls-files", "-z", "--others", "--exclude-standard", "--", "*.md"],
            repo_root,
        )
        if untracked is not None:
            files.update(
                repo_root / path for path in untracked.split("\0") if path
            )
    return _filter_excluded(sorted(files), exclude)


def check_git_tracked(
    repo_root: Path,
    *,
    include_untracked: bool = False,
    exclude: set[str] | None = None,
) -> list[BrokenLink]:
    """Check every git-tracked markdown file under ``repo_root``."""
    report: list[BrokenLink] = []
    files = git_tracked_markdown(
        repo_root, include_untracked=include_untracked, exclude=exclude
    )
    for path in files:
        try:
            check_file(path, report)
        except OSError:
            continue
    return report


def _filter_excluded(
    files: list[Path], exclude: set[str] | None
) -> list[Path]:
    """Drop files whose path has a component matching any exclude token.

    Exclusion matches a whole path segment (``.railway-deploy`` matches the
    generated mirror directory anywhere in the tree). A token ending in ``*``
    is treated as a prefix wildcard for that segment.
    """
    if not exclude:
        return files

    def _kept(path: Path) -> bool:
        for part in path.parts:
            lowered = part.lower()
            if any(
                lowered == token or (token.endswith("*") and lowered.startswith(token[:-1]))
                for token in exclude
            ):
                return False
        return True

    return [path for path in files if _kept(path)]


def _print_report(report: list[BrokenLink]) -> None:
    print(f"check_doc_links: {len(report)} broken link(s) found")
    for broken in report:
        print(f"  {broken}")
    print("\nFix the link target (or create the missing file) before merging.")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    git_tracked = "--git-tracked" in argv
    include_untracked = "--include-untracked" in argv
    exclude: set[str] = set()
    filtered: list[str] = []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--exclude":
            if i + 1 >= len(argv):
                print("check_doc_links: --exclude requires a value", file=sys.stderr)
                return 2
            exclude.add(argv[i + 1].lower())
            i += 2
        elif arg.startswith("--exclude=") and len(arg) > len("--exclude="):
            exclude.add(arg.split("=", 1)[1].lower())
            i += 1
        else:
            filtered.append(arg)
            i += 1
    roots = [arg for arg in filtered if not arg.startswith("-")]

    if git_tracked:
        start = Path.cwd()
        top = _git(["rev-parse", "--show-toplevel"], start)
        if top is None:
            print(
                "check_doc_links: --git-tracked requires a git repository "
                f"(no repo found at or above {start})",
                file=sys.stderr,
            )
            return 2
        repo_root = Path(top.strip())
        report = check_git_tracked(
            repo_root,
            include_untracked=include_untracked,
            exclude=exclude,
        )
    else:
        roots = roots or [_SCAN_DEFAULT]
        report = []
        for scan in roots:
            root = Path(scan)
            if not root.is_dir():
                print(f"check_doc_links: scan root not found: {root}", file=sys.stderr)
                return 2
            report.extend(_filter_excluded(check_tree(root), exclude))

    if report:
        _print_report(report)
        return 1
    print("check_doc_links: OK — every scanned link resolves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

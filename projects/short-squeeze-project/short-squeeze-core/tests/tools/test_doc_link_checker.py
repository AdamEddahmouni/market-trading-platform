"""Tests for tools/check_doc_links.py.

Unit tests cover link parsing and the existence rules in isolation; one
integrity test guards the real ``docs/`` tree so CI fails whenever a doc link
points at a missing file.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tools.check_doc_links import (
    BrokenLink,
    _split_path_and_fragment,
    _split_target,
    _target_exists,
    check_file,
    check_tree,
    extract_heading_slugs,
    git_tracked_markdown,
    github_slug,
    iter_links,
    main,
)

_GIT = shutil.which("git")
_NEEDS_GIT = pytest.mark.skipif(_GIT is None, reason="git not on PATH")

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Link parsing
# ---------------------------------------------------------------------------


def test_inline_and_image_links_are_collected() -> None:
    text = "[see docs](guide.md) and ![logo](assets/logo.png)"
    assert iter_links(text) == [(1, "guide.md"), (1, "assets/logo.png")]


def test_links_report_their_line_number() -> None:
    text = "line one\nline two [target](foo.md)"
    assert iter_links(text) == [(2, "foo.md")]


def test_fenced_code_blocks_are_not_parsed() -> None:
    text = "before\n```\n[not a link](missing.md)\n```\nafter [real](real.md)"
    assert iter_links(text) == [(5, "real.md")]


def test_inline_code_spans_are_not_parsed() -> None:
    text = "use `[cmd](no.md)` here but [yes](yes.md) there"
    assert iter_links(text) == [(1, "yes.md")]


def test_remote_and_fragment_links_are_ignored() -> None:
    text = (
        "[http](https://example.com/a) [mail](mailto:x@y.z) "
        "[ftp](ftp://host/f) [frag](#section) [empty]()"
    )
    assert iter_links(text) == []


def test_title_and_fragment_and_angle_brackets_are_stripped() -> None:
    text = '[a](file.md "Title") [b](<file.md#anchor>) [c](file.md#section)'
    assert iter_links(text) == [(1, "file.md"), (1, "file.md"), (1, "file.md")]


def test_url_escaped_spaces_are_decoded() -> None:
    text = "[a](getting%20started.md)"
    assert iter_links(text) == [(1, "getting started.md")]


def test_split_target_edge_cases() -> None:
    assert _split_target("  ") is None
    assert _split_target("#only") is None
    assert _split_target("https://x") is None
    assert _split_target("a b.md#frag") == "a b.md"


# ---------------------------------------------------------------------------
# Existence rules
# ---------------------------------------------------------------------------


def test_existence_is_case_exact(tmp_path: Path) -> None:
    (tmp_path / "LIMITATIONS.md").write_text("x", encoding="utf-8")
    assert _target_exists(tmp_path, "LIMITATIONS.md") is True
    # Wrong case must fail on every OS, not just case-sensitive CI.
    assert _target_exists(tmp_path, "limitations.md") is False


def test_directory_link_passes_when_directory_exists(tmp_path: Path) -> None:
    (tmp_path / "adr").mkdir()
    assert _target_exists(tmp_path, "adr/") is True
    assert _target_exists(tmp_path, "missing/") is False


def test_parent_relative_targets_resolve(tmp_path: Path) -> None:
    nested = tmp_path / "repo" / "a" / "b" / "c"
    nested.mkdir(parents=True)
    (tmp_path / "repo" / "a" / "README.md").write_text("x", encoding="utf-8")
    (nested / "spec.md").write_text("x", encoding="utf-8")
    # From c/, ../../README.md reaches a/README.md; ../.. alone is a/.
    assert _target_exists(nested, "../../README.md") is True
    assert _target_exists(nested, "../README.md") is False
    assert _target_exists(nested, "../nope.md") is False


def test_split_path_and_fragment() -> None:
    assert _split_path_and_fragment("guide.md#section") == ("guide.md", "section")
    assert _split_path_and_fragment("guide.md") == ("guide.md", None)
    assert _split_path_and_fragment("#section") == (None, "section")
    assert _split_path_and_fragment("https://x/y#z") == (None, None)


# ---------------------------------------------------------------------------
# GitHub heading slugs
# ---------------------------------------------------------------------------


def test_github_slug_punctuation_is_deleted_without_separators() -> None:
    assert github_slug("1. Introduction") == "1-introduction"
    assert github_slug("What's up?") == "whats-up"
    assert github_slug("Don't panic") == "dont-panic"
    assert github_slug("C# and C++") == "c-and-c"
    assert github_slug("API capabilities") == "api-capabilities"


def test_github_slug_keeps_underscores_and_hyphens() -> None:
    assert github_slug("foo_bar") == "foo_bar"
    assert github_slug("pre-registered batch") == "pre-registered-batch"


def test_github_slug_does_not_collapse_hyphen_runs() -> None:
    # GitHub turns every space into a hyphen; punctuation is deleted first.
    assert github_slug("Enable providers (IBKR / Finviz / News / SEC)") == (
        "enable-providers-ibkr--finviz--news--sec"
    )


def test_github_slug_rendered_text_not_markup() -> None:
    assert github_slug("**Bold** heading") == "bold-heading"
    assert github_slug("[Linked](target.md) text") == "linked-text"
    assert github_slug("use `code` here") == "use-code-here"


def test_extract_heading_slugs_atx_and_setext() -> None:
    text = "# Title\n\nSome paragraph\n=============\n\n### Sub\n"
    assert extract_heading_slugs(text) == ["title", "some-paragraph", "sub"]


def test_extract_heading_slugs_ignores_fences_and_handles_duplicates() -> None:
    text = (
        "# Notes\n\n```\n# Not a heading\n```\n\n## Notes\n\n# Notes\n"
    )
    # GitHub suffixes duplicates from -1 on the second identical slug.
    assert extract_heading_slugs(text) == ["notes", "notes-1", "notes-2"]


# ---------------------------------------------------------------------------
# Fragment (anchor) validation
# ---------------------------------------------------------------------------


def test_check_file_validates_same_file_fragments(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text(
        "# Existing section\n\n[ok](#existing-section)\n[bad](#no-such-heading)\n",
        encoding="utf-8",
    )
    report: list[BrokenLink] = []
    check_file(source, report)
    assert [(item.line, item.target) for item in report] == [(4, "#no-such-heading")]


def test_check_file_validates_cross_file_fragments(tmp_path: Path) -> None:
    other = tmp_path / "other.md"
    other.write_text("## Walk-forward validation\n", encoding="utf-8")
    source = tmp_path / "doc.md"
    source.write_text(
        "[ok](other.md#walk-forward-validation)\n"
        "[bad](other.md#walkforward)\n",
        encoding="utf-8"
    )
    report: list[BrokenLink] = []
    check_file(source, report)
    assert [(item.line, item.target) for item in report] == [
        (2, "other.md#walkforward")
    ]


def test_check_file_validates_fragment_case_exactly(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text("## API routes\n\n[bad](#API-routes)\n", encoding="utf-8")
    report: list[BrokenLink] = []
    check_file(source, report)
    assert [(item.line, item.target) for item in report] == [(3, "#API-routes")]


def test_check_file_reports_each_broken_link(tmp_path: Path) -> None:
    source = tmp_path / "doc.md"
    source.write_text(
        "[ok](present.md)\n[broken](missing.md) and [also](gone.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "present.md").write_text("x", encoding="utf-8")
    report: list[BrokenLink] = []
    check_file(source, report)
    assert [(item.line, item.target) for item in report] == [
        (2, "missing.md"),
        (2, "gone.md"),
    ]


# ---------------------------------------------------------------------------
# Scan-scope modes (multiple roots, whole git repo)
# ---------------------------------------------------------------------------


def test_multiple_scan_roots_aggregate(tmp_path: Path) -> None:
    good = tmp_path / "good"
    good.mkdir()
    (good / "a.md").write_text("# A\n\n[ok](b.md)\n", encoding="utf-8")
    (good / "b.md").write_text("target\n", encoding="utf-8")
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "a.md").write_text("[missing](gone.md)\n", encoding="utf-8")
    assert main([str(good)]) == 0
    assert main([str(good), str(bad)]) == 1
    assert main([str(bad)]) == 1


@_NEEDS_GIT
def test_git_tracked_scan_excludes_untracked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("# A\n\n[ok](b.md)\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("target\n", encoding="utf-8")
    # Untracked and broken: must NOT fail a plain --git-tracked run.
    (tmp_path / "draft.md").write_text("[missing](gone.md)\n", encoding="utf-8")
    subprocess.run(["git", "add", "--", "a.md", "b.md"], check=True)
    assert main(["--git-tracked"]) == 0


@_NEEDS_GIT
def test_git_tracked_scan_with_untracked_included(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("# A\n\n[ok](b.md)\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("target\n", encoding="utf-8")
    (tmp_path / "draft.md").write_text("[missing](gone.md)\n", encoding="utf-8")
    (tmp_path / "ignored.md").write_text("[missing](gone.md)\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("ignored.md\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "--", "a.md", "b.md", ".gitignore"], check=True
    )
    # draft.md is scanned and broken; ignored.md stays out.
    assert main(["--git-tracked", "--include-untracked"]) == 1


@_NEEDS_GIT
def test_git_tracked_scan_can_exclude_generated_mirrors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.md").write_text("# A\n\n[ok](b.md)\n", encoding="utf-8")
    (tmp_path / "b.md").write_text("target\n", encoding="utf-8")
    mirror = tmp_path / ".railway-deploy"
    mirror.mkdir()
    # Generated mirror with dangling links, like the real deploy bundle.
    (mirror / "README.md").write_text(
        "[docs](docs/CONFIGURATION.md)\n", encoding="utf-8"
    )
    subprocess.run(["git", "add", "--", "a.md", "b.md", mirror / "README.md"], check=True)
    assert main(["--git-tracked"]) == 1
    assert main(["--git-tracked", "--exclude", ".railway-deploy"]) == 0


@_NEEDS_GIT
def test_git_tracked_markdown_respects_ignore_rules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tracked.md").write_text("x", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("ignored.md\n", encoding="utf-8")
    (tmp_path / "ignored.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "--", "tracked.md", ".gitignore"], check=True)
    files = git_tracked_markdown(tmp_path, include_untracked=True)
    names = [path.name for path in files]
    assert "tracked.md" in names
    assert "ignored.md" not in names


# ---------------------------------------------------------------------------
# Integrity of the real docs tree
# ---------------------------------------------------------------------------


def test_every_link_in_docs_resolves() -> None:
    docs = REPO_ROOT / "docs"
    assert docs.is_dir(), f"expected docs/ under {REPO_ROOT}"
    report = check_tree(docs)
    assert report == [], (
        "Broken doc link(s) — fix the target or the link before merging:\n"
        + "\n".join(f"  {item}" for item in report)
    )

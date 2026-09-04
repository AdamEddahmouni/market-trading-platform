#!/usr/bin/env python3
"""Lightweight internal Markdown link checker for governance docs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE_GLOBS = [
    "docs/README.md",
    "docs/PROJECT_STATUS.md",
    "docs/GLOSSARY.md",
    "docs/architecture/**/*.md",
    "docs/engineering/**/*.md",
    "docs/operations/**/*.md",
    "docs/product/PRODUCT_BACKLOG.md",
    "README.md",
    "AGENTS.md",
    "ui/AGENTS.md",
    "src/market_platform_foundation/paper/AGENTS.md",
]
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
SKIP_PREFIXES = ("http://", "https://", "mailto:")


def iter_markdown_files() -> list[Path]:
    files: set[Path] = set()
    for pattern in GOVERNANCE_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            if path.is_file() and path.suffix == ".md":
                files.add(path)
    return sorted(files)


def should_skip(url: str) -> bool:
    url = url.strip()
    if not url or url.startswith(SKIP_PREFIXES):
        return True
    if url.startswith('"') or url.startswith("'"):
        return True
    if url in {"args", "head", "status"}:
        return True
    return False


def resolve_link(source: Path, target: str) -> Path | None:
    target = target.split("#", 1)[0].strip()
    if should_skip(target):
        return None
    base = source.parent
    resolved = (base / target).resolve()
    try:
        resolved.relative_to(REPO_ROOT)
    except ValueError:
        return None  # external to repo — pre-existing donor links
    return resolved


def main() -> int:
    broken: list[str] = []
    files = iter_markdown_files()
    for md in files:
        text = md.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            raw = match.group(1).strip()
            if raw.startswith("<"):
                continue
            resolved = resolve_link(md, raw)
            if resolved is None:
                continue
            if not resolved.exists():
                rel = md.relative_to(REPO_ROOT)
                broken.append(f"{rel}: ({raw})")
    if broken:
        print("Broken internal links:", file=sys.stderr)
        for line in broken:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"OK: checked links in {len(files)} governance markdown files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Fail if .railway-deploy mirror drifts from source trees used for Railway deploy.

This is an additive safety check. It does not modify or delete the mirror.
Run: python tools/check_railway_mirror.py
"""

from __future__ import annotations

import filecmp
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIRROR = ROOT / ".railway-deploy"
TREES = ("apps", "src", "scripts", "tools")
FILES = ("pyproject.toml",)


def _diff_trees(src: Path, dst: Path) -> list[str]:
    problems: list[str] = []
    if not dst.exists():
        return [f"missing mirror tree: {dst.relative_to(ROOT)}"]
    cmp = filecmp.dircmp(src, dst, ignore=["__pycache__", "*.pyc", ".pytest_cache"])
    if cmp.left_only:
        problems.append(
            f"{src.relative_to(ROOT)} has files not in mirror: {sorted(cmp.left_only)[:20]}"
        )
    if cmp.right_only:
        problems.append(
            f"mirror {dst.relative_to(ROOT)} has extra files: {sorted(cmp.right_only)[:20]}"
        )
    if cmp.diff_files:
        problems.append(
            f"content drift under {src.relative_to(ROOT)}: {sorted(cmp.diff_files)[:20]}"
        )
    for sub in cmp.common_dirs:
        problems.extend(_diff_trees(src / sub, dst / sub))
    return problems


def main() -> int:
    if not MIRROR.is_dir():
        print("FAIL: .railway-deploy/ is missing", file=sys.stderr)
        return 1
    problems: list[str] = []
    for name in TREES:
        problems.extend(_diff_trees(ROOT / name, MIRROR / name))
    for name in FILES:
        left = ROOT / name
        right = MIRROR / name
        if not right.exists():
            problems.append(f"missing mirrored file: {name}")
        elif left.read_bytes() != right.read_bytes():
            problems.append(f"content drift: {name}")
    if problems:
        print("Railway deploy mirror drift detected:", file=sys.stderr)
        for item in problems[:50]:
            print(f"  - {item}", file=sys.stderr)
        print(
            "\nRun `make deploy-sync` (or rsync apps/src/scripts/tools) before deploy.",
            file=sys.stderr,
        )
        return 1
    print("OK: .railway-deploy mirror matches source trees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

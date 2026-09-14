#!/usr/bin/env python3
"""Classify changed paths into expensive CI slices.

Developer/CI tooling only. This does not change production runtime, test
inventory, or selector semantics. Jobs still report success when a slice is
skipped so required GitHub checks remain 9/9.

Fail closed: unknown, empty, or unreadable path lists run every expensive
slice. Push-to-main and workflow_dispatch should pass ``--always-run``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Iterable, Sequence

SCHEMA_VERSION = "1.0"
REPORT_TYPE = "ci_job_selection"
IMP_PREFIX = "projects/integrated-market-platform/"

# Vitest / typecheck / gzip budget. ui/AGENTS.md is docs, not frontend runtime.
UI_PATTERNS = (
    "ui/src/",
    "ui/public/",
    "ui/index.html",
    "ui/package.json",
    "ui/package-lock.json",
    "ui/vite.config.ts",
    "ui/tsconfig.json",
    "ui/tsconfig.*.json",
    "manifests/ui1/",
)
UI_FORCE_WORKFLOWS = (".github/workflows/imp-validate.yml",)

DOCS_PATTERNS = (
    "docs/",
    "README.md",
    "AGENTS.md",
    "ui/AGENTS.md",
    "src/market_platform_foundation/paper/AGENTS.md",
    "tools/check_docs_links.py",
)

# Keep aligned with formulas / squeeze_models / donor_bridge source+test
# globs in tools/validation_manifest.json. Those suites import the admitted
# sibling short-squeeze-core checkout that CI sparse-clones. donor_bridge
# uses unittest.SkipTest when squeeze_core is missing, so skipping the
# clone would hide required failures instead of failing closed.
REPLAY_FIXTURE_PATTERNS = (
    "tests/formulas/",
    "tests/squeeze_models/",
    "tests/donor_bridge/",
    "tests/fixtures/formulas/",
    "tests/fixtures/squeeze/",
    "docs/research/formula_ledger.json",
    "docs/research/FORMULA_LEDGER.md",
    "src/market_platform_foundation/options/",
    "src/market_platform_foundation/order_flow/",
    "src/market_platform_foundation/cross_lane/",
    "src/market_platform_foundation/research/distribution/",
    "src/market_platform_foundation/research/baseline_naive.py",
    "src/market_platform_foundation/research/squeeze_models/",
    "src/market_platform_foundation/strategy/",
    "src/market_platform_foundation/intelligence/signals/calculators/",
    "src/market_platform_foundation/futures/baselines.py",
    "src/market_platform_foundation/donor_bridge/",
)
REPLAY_FORCE_WORKFLOWS = (".github/workflows/imp-python.yml",)


def normalize_changed_path(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    if not normalized or normalized.startswith("#"):
        return ""
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized.startswith(IMP_PREFIX):
        normalized = normalized[len(IMP_PREFIX) :]
    return normalized


def load_paths(values: Iterable[str] | None = None, *, paths_file: Path | None = None) -> tuple[str, ...]:
    raw: list[str] = []
    if paths_file is not None:
        text = paths_file.read_text(encoding="utf-8")
        raw.extend(text.splitlines())
    if values:
        raw.extend(values)
    normalized = []
    seen: set[str] = set()
    for item in raw:
        path = normalize_changed_path(item)
        if not path or path in seen:
            continue
        seen.add(path)
        normalized.append(path)
    return tuple(normalized)


def _matches(path: str, patterns: Sequence[str]) -> bool:
    for pattern in patterns:
        if pattern.endswith("/**"):
            prefix = pattern[:-3].rstrip("/")
            if path == prefix or path.startswith(prefix + "/"):
                return True
            continue
        if any(symbol in pattern for symbol in "*?[]"):
            if fnmatch(path, pattern):
                return True
            continue
        if path == pattern or path.startswith(pattern.rstrip("/") + "/"):
            return True
    return False


def select_ci_jobs(
    paths: Sequence[str],
    *,
    always_run: bool = False,
    paths_readable: bool = True,
) -> dict[str, object]:
    fail_closed = always_run or (not paths_readable) or (not paths)
    run_ui = fail_closed or any(
        _matches(path, UI_PATTERNS) or _matches(path, UI_FORCE_WORKFLOWS) for path in paths
    )
    run_docs = fail_closed or any(_matches(path, DOCS_PATTERNS) for path in paths)
    checkout_replay_fixture = fail_closed or any(
        _matches(path, REPLAY_FIXTURE_PATTERNS) or _matches(path, REPLAY_FORCE_WORKFLOWS)
        for path in paths
    )
    reasons = {
        "always_run": always_run,
        "fail_closed": fail_closed,
        "ui_paths": [path for path in paths if _matches(path, UI_PATTERNS) or _matches(path, UI_FORCE_WORKFLOWS)],
        "docs_paths": [path for path in paths if _matches(path, DOCS_PATTERNS)],
        "replay_fixture_paths": [
            path
            for path in paths
            if _matches(path, REPLAY_FIXTURE_PATTERNS) or _matches(path, REPLAY_FORCE_WORKFLOWS)
        ],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "report_type": REPORT_TYPE,
        "gating_policy": "SKIP_UNCHANGED_EXPENSIVE_STEPS",
        "always_run": always_run,
        "path_count": len(paths),
        "paths": list(paths),
        "run_ui": run_ui,
        "run_docs": run_docs,
        "checkout_replay_fixture": checkout_replay_fixture,
        "run_python_fast": True,
        "run_python_changed": True,
        "reasons": reasons,
    }


def write_github_output(selection: dict[str, object], target: Path | None = None) -> None:
    destination = target
    if destination is None:
        configured = os.environ.get("GITHUB_OUTPUT")
        if not configured:
            raise RuntimeError("GITHUB_OUTPUT is unset; pass --github-output-path in tests")
        destination = Path(configured)
    flags = ("run_ui", "run_docs", "checkout_replay_fixture", "always_run")
    lines = [f"{key}={str(selection[key]).lower()}\n" for key in flags]
    lines.append(f"path_count={selection['path_count']}\n")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8", newline="\n") as handle:
        handle.writelines(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="changed paths (repo-root or IMP-relative)")
    parser.add_argument("--paths-file", type=Path, help="newline-delimited changed paths")
    parser.add_argument("--always-run", action="store_true", help="force every expensive slice")
    parser.add_argument("--json", dest="json_path", type=Path)
    parser.add_argument("--github-output", action="store_true")
    parser.add_argument("--github-output-path", type=Path)
    parser.add_argument("--quiet", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    paths_readable = True
    try:
        paths = load_paths(args.paths, paths_file=args.paths_file)
    except OSError as exc:
        print(f"ci_job_selector: failed to read paths: {exc}", file=sys.stderr)
        paths = ()
        paths_readable = False
    selection = select_ci_jobs(
        paths,
        always_run=args.always_run,
        paths_readable=paths_readable,
    )
    if args.json_path:
        args.json_path.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(selection, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.github_output or args.github_output_path is not None:
        write_github_output(selection, args.github_output_path)
    if not args.quiet:
        print(json.dumps(selection, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

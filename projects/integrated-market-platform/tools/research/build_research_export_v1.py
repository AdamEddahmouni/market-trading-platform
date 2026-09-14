#!/usr/bin/env python3
"""Build immutable Research Export v1 packages (offline fixtures only)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from market_platform_foundation.research.export_v1 import (  # noqa: E402
    PROFILE_EVENT_MACRO,
    PROFILE_MARKET_TECHNICAL,
    build_research_export_v1,
    write_research_export_v1_package,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Research Export v1 package")
    parser.add_argument(
        "--profile",
        choices=(PROFILE_MARKET_TECHNICAL, PROFILE_EVENT_MACRO),
        required=True,
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repository-head-sha", default=None)
    args = parser.parse_args()
    package = build_research_export_v1(
        profile=args.profile,
        repository_head_sha=args.repository_head_sha,
    )
    manifest_path = write_research_export_v1_package(args.output_dir, package)
    print(manifest_path)
    print(package.manifest["export_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Deterministic builder for the postroot acceptance contract suite."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.offline_guard import install_guard

install_guard([])

from tools.postroot.contract_core import canonical_bytes, sha256_bytes
from tools.postroot.suite_definition import build_suite


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", dest="write")
    group.add_argument("--check", dest="check")
    parser.add_argument("--replace-unapproved", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    expected = canonical_bytes(build_suite())
    target = Path(args.write or args.check)
    if args.check:
        if not target.is_file() or target.read_bytes() != expected:
            print("SUITE-BYTES-MISMATCH", file=sys.stderr)
            return 1
        print(sha256_bytes(expected))
        return 0
    if target.exists() and target.read_bytes() != expected and not args.replace_unapproved:
        print("REFUSE-UNEQUAL-SUITE-OVERWRITE", file=sys.stderr)
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(expected)
    print(sha256_bytes(expected))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

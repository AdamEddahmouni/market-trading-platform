"""Validate the bundled NVDA demo dataset without MongoDB.

Checks manifest integrity and gz/jsonl readability. Use before
``python -m scripts.demo_dataset load`` when MongoDB is available.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "demo_data"
MANIFEST_PATH = DATA_DIR / "manifest.json"


def _count_jsonl_gz(path: Path) -> int:
    count = 0
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                count += 1
    return count


def main() -> int:
    if not MANIFEST_PATH.exists():
        print("FAIL: demo_data/manifest.json is missing")
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    files = manifest.get("files") or {}
    failures = 0

    print(f"Demo ticker: {manifest.get('ticker')}  day: {manifest.get('demo_day')}")
    for name, meta in files.items():
        path = DATA_DIR / name
        if not path.exists():
            print(f"FAIL: missing bundle file {name}")
            failures += 1
            continue
        expected_docs = int(meta.get("docs") or 0)
        actual_docs = _count_jsonl_gz(path)
        if actual_docs != expected_docs:
            print(
                f"FAIL: {name} doc count {actual_docs} != manifest {expected_docs}"
            )
            failures += 1
            continue
        print(f"PASS: {name} ({actual_docs} docs)")

    if failures:
        print(f"\n{failures} bundle check(s) failed.")
        return 1

    print("\nAll bundled demo files match manifest. Next steps:")
    print("  1. Start MongoDB on localhost:27017")
    print("  2. python -m scripts.demo_dataset load")
    print("  3. python -m scripts.coverage_and_latency")
    print("  4. python -m scripts.validate_moc")
    print("  5. python scripts/backtest_correlation.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

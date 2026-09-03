"""CLI: SQLite backup of local IMP state via sqlite3 backup API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.local_state.connection import LocalStateConnection
from market_platform_foundation.local_state.paths import database_path, state_dir


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    dest = Path(args.output) if args.output else (state_dir(create=True) / "backups" / "imp-state.backup.sqlite3")
    conn = LocalStateConnection(database_path(create_dir=True))
    conn.backup(dest)
    conn.close()
    print(json.dumps({"backup": str(dest), "source": str(database_path())}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

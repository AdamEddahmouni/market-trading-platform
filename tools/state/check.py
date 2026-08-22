"""CLI: integrity-check local IMP SQLite state."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.local_state.connection import CorruptStateError, LocalStateConnection
from market_platform_foundation.local_state.paths import database_path, persistence_enabled
from market_platform_foundation.local_state.startup import open_local_state, startup_report


def main() -> int:
    report = {
        "database": str(database_path()),
        "persistence_enabled": persistence_enabled(),
        "startup": startup_report(),
    }
    try:
        conn = LocalStateConnection(database_path(create_dir=True))
        report["integrity_ok"] = conn.integrity_ok()
        report["schema_version"] = conn.schema_version()
        conn.close()
    except CorruptStateError as exc:
        report["integrity_ok"] = False
        report["error"] = str(exc)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["integrity_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI: export local IMP state as JSON (no secrets, no tick files)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.local_state.paths import database_path
from market_platform_foundation.local_state.startup import open_local_state, reset_local_state_for_tests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    reset_local_state_for_tests()
    repo = open_local_state(force=True)
    assert repo is not None
    payload = {
        "captures": repo.list_captures(),
        "database": str(database_path()),
        "preferences": repo.get_preferences(),
        "recent_instruments": repo.list_recent_instruments(),
        "research_runs": repo.list_research_runs(),
        "schema_version": repo.connection.schema_version(),
        "sessions": [],
        "watchlists": repo.list_watchlists(),
        "workspace": repo.load_active_workspace(),
    }
    for session in repo.list_sessions():
        session_id = session["session_id"]
        payload["sessions"].append(
            {
                **{key: session[key] for key in session if key != "policy_json"},
                "events": repo.load_events(session_id),
                "idempotency": repo.load_idempotency(session_id),
            }
        )
    dest = Path(args.output)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"exported": str(dest), "sessions": len(payload["sessions"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

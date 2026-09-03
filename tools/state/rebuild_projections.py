"""CLI: rebuild paper projections from append-only events (cache only)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.local_state.startup import ledger_from_session, open_local_state, reset_local_state_for_tests


def main() -> int:
    reset_local_state_for_tests()
    repo = open_local_state(force=True)
    assert repo is not None
    rebuilt = []
    for session in repo.list_sessions():
        events = repo.load_events(session["session_id"])
        idempotency = repo.load_idempotency(session["session_id"])
        ledger = ledger_from_session(session, events, idempotency)
        projection = {
            "account": ledger.project_account(),
            "fills": ledger.project_fills(),
            "orders": ledger.project_orders(),
            "positions": ledger.project_positions(),
        }
        last_seq = max((int(event["sequence"]) for event in events), default=-1)
        repo.save_snapshot(session_id=session["session_id"], last_event_sequence=last_seq, projection=projection)
        rebuilt.append({"session_id": session["session_id"], "event_count": len(events), "last_event_sequence": last_seq})
    print(json.dumps({"rebuilt": rebuilt}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

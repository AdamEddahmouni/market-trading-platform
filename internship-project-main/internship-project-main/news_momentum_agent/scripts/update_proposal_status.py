#!/usr/bin/env python3
"""Manually mark a research proposal pending|adopted|rejected (never auto-edits settings).

CLI
---
``python scripts/update_proposal_status.py PROPOSAL_ID {pending|adopted|rejected}
[--note TEXT] [--file PATH]``

When to run
-----------
After human review of ``evaluation`` research proposals; governance step only.

Safe vs live agent
------------------
**Safe:** Updates proposal status file only — never modifies ``settings.json`` or
live agent configuration automatically.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.proposals import update_proposal_status  # noqa: E402


def main() -> int:
    """CLI entry: set a research proposal status (pending/adopted/rejected)."""
    parser = argparse.ArgumentParser()
    parser.add_argument("proposal_id")
    parser.add_argument("status", choices=["pending", "adopted", "rejected"])
    parser.add_argument("--note", default="")
    parser.add_argument("--file", default="")
    args = parser.parse_args()
    path = Path(args.file) if args.file else None
    update_proposal_status(args.proposal_id, args.status, proposals_path=path, note=args.note)
    print(f"Updated {args.proposal_id} → {args.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

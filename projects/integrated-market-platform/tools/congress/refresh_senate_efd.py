"""Download new Senate eFD Periodic Transaction Reports into the attested import directory.

The Screener does this in the background every 6 hours when ``IMP_SENATE_EFD_LIVE=1``;
this command does the same explicitly. It needs ``IMP_SENATE_EFD_IMPORT_DIR`` (a folder
whose ``ACCESS_ATTESTATION.json`` sets ``automated_access: true``) and ``SEC_USER_AGENT``
(name + email, sent as the contact on every request).

    python tools/congress/refresh_senate_efd.py           # accept terms, list, download new reports
    python tools/congress/refresh_senate_efd.py --check   # report the folder and last run; no network
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.congressional_ptr import senate, senate_efd_sync  # noqa: E402
from market_platform_foundation.local_state.external_cache import read_manifest  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="report the folder and last run only; never download")
    parser.add_argument("--max-new", type=int, default=senate_efd_sync.MAX_NEW_REPORTS)
    args = parser.parse_args(argv)
    root = senate.import_root_from_env()
    if not root:
        print(json.dumps({"state": "NOT_CONFIGURED", "reason": "IMP_SENATE_EFD_IMPORT_DIR_NOT_SET"}))
        return 2
    summary = read_manifest(Path(root) / senate_efd_sync.STATE_FILE)
    if not args.check:
        try:
            summary = senate_efd_sync.sync(Path(root), user_agent=os.environ.get("SEC_USER_AGENT", ""),
                                           max_new=max(0, args.max_new))
        except senate_efd_sync.SenateSyncError as exc:
            print(json.dumps({"state": "SYNC_FAILED", "reason": str(exc)}))
            return 2
    scan = senate.scan_import(root)
    print(json.dumps({"import": {"state": scan.state, "reason": scan.reason, **scan.coverage()}, "last_run": summary,
                      "import_dir": root}, indent=2))
    return 0 if not (summary or {}).get("error") and scan.state in ("READY", "PARTIAL") else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Managed refresh of the Screener's local 13F index (Screener S14).

Replaces hand-picking SEC Form 13F data-set ZIPs: the tool reads the SEC's data-set
page, downloads what the active index lacks (SEC Fair Access User-Agent required),
verifies it, rebuilds a candidate, validates it, and switches to it atomically. The
previous generation stays on disk for ``--rollback``. Everything lives under an
external data root, never in the repository:

    python tools/sec_edgar/thirteen_f_refresh.py --root <IMP_DATA>/13f --status
    python tools/sec_edgar/thirteen_f_refresh.py --root <IMP_DATA>/13f --check
    python tools/sec_edgar/thirteen_f_refresh.py --root <IMP_DATA>/13f --refresh [--dry-run]
    python tools/sec_edgar/thirteen_f_refresh.py --root <IMP_DATA>/13f --rollback

``--root`` defaults to ``IMP_13F_DATA_ROOT``. ``--check``/``--refresh`` need
``SEC_USER_AGENT`` (a name and a contact email). Offline, ``--import-zip`` admits
official data-set ZIPs that were downloaded by hand (same verification), and
``--listing-file`` reads a saved copy of the SEC data-set page. Start the UI API with
``IMP_13F_DATA_ROOT=<root>``; it serves the active generation and reads its freshness
from files only.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.sec_edgar.thirteen_f_lifecycle import (  # noqa: E402
    DEFAULT_DATASETS,
    RefreshError,
    ThirteenFLifecycle,
    ThirteenFStore,
    iter_generations,
    status,
)


def _inside_repository(path: Path) -> bool:
    resolved = path.resolve()
    return resolved == ROOT or ROOT in resolved.parents


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Managed refresh of the local 13F index")
    parser.add_argument("--root", type=Path, default=None, help="external 13F data root (default: IMP_13F_DATA_ROOT)")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--status", action="store_true", help="show the active generation and freshness (no network)")
    action.add_argument("--check", action="store_true", help="compare the SEC's published data sets with the active index")
    action.add_argument("--refresh", action="store_true", help="download, verify, rebuild, validate, and publish")
    action.add_argument("--rollback", action="store_true", help="re-activate the previous generation")
    action.add_argument("--generations", action="store_true", help="list published generations")
    parser.add_argument("--dry-run", action="store_true", help="with --refresh: report what would change")
    parser.add_argument("--force", action="store_true", help="with --refresh: rebuild even when current")
    parser.add_argument("--datasets", type=int, default=DEFAULT_DATASETS, help="newest data sets to index (default 2)")
    parser.add_argument("--listing-file", type=Path, help="saved copy of the SEC data-set page (offline discovery)")
    parser.add_argument("--import-zip", type=Path, action="append", default=[],
                        help="admit a hand-downloaded official data-set ZIP into the source store (repeatable)")
    args = parser.parse_args(argv)
    root = args.root or (Path(os.environ["IMP_13F_DATA_ROOT"]) if os.environ.get("IMP_13F_DATA_ROOT") else None)
    if root is None:
        parser.error("--root or IMP_13F_DATA_ROOT is required")
    if _inside_repository(root):
        parser.error("keep the 13F data root outside the repository")
    if args.status:
        print(json.dumps(status(root), indent=2, sort_keys=True))
        return 0
    if args.generations:
        store = ThirteenFStore(root)
        print(json.dumps({"current": store.current_generation(), "generations": list(iter_generations(root))}, indent=2))
        return 0
    store = ThirteenFStore(root)
    fetch_listing = None
    if args.listing_file is not None:
        text = args.listing_file.read_text(encoding="utf-8", errors="replace")
        fetch_listing = lambda: text  # noqa: E731
    lifecycle = ThirteenFLifecycle(store, fetch_listing=fetch_listing, datasets=args.datasets)
    if args.import_zip:
        store.acquire()
        try:
            for path in args.import_zip:
                try:
                    info = store.import_source(path)
                except RefreshError as exc:
                    print(json.dumps({"import": str(path.name), "outcome": "FAILED", "error": exc.code}))
                    return 1
                print(json.dumps({"import": info["name"], "sha256": info["sha256"], "outcome": "ADMITTED"}))
        finally:
            store.release()
    if args.check:
        result = lifecycle.check()
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["ok"] else 1
    if args.rollback:
        result = lifecycle.rollback()
    else:
        result = lifecycle.refresh(dry_run=args.dry_run, force=args.force)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result.get("outcome") != "FAILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

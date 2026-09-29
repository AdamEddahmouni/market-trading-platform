"""Managed refresh of the Screener's fund-held bond catalog from SEC Form N-PORT (Screener S16).

The SEC publishes Form N-PORT data sets quarterly (``<yyyy>q<n>_nport.zip``). This
tool reads the SEC's data-set page, downloads the newest quarter the active catalog
lacks (SEC Fair Access User-Agent required), verifies it, builds a candidate catalog
(reconciling terms across every reporting fund), validates it, and switches to it
atomically — the S14 lifecycle, unchanged. The previous generation stays on disk for
``--rollback``. Everything lives under an external data root, never in the repository:

    python tools/fixed_income/nport_refresh.py --root <IMP_DATA>/nport --status
    python tools/fixed_income/nport_refresh.py --root <IMP_DATA>/nport --check
    python tools/fixed_income/nport_refresh.py --root <IMP_DATA>/nport --refresh [--dry-run]
    python tools/fixed_income/nport_refresh.py --root <IMP_DATA>/nport --rollback

``--root`` defaults to ``IMP_NPORT_DATA_ROOT``. ``--check``/``--refresh`` need
``SEC_USER_AGENT`` (a name and a contact email). Offline, ``--import-zip`` admits an
official data-set ZIP downloaded by hand (same verification), and ``--listing-file``
reads a saved copy of the SEC data-set page. Start the UI API with
``IMP_NPORT_DATA_ROOT=<root>``; it serves the active generation.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.fixed_income.nport_catalog import (  # noqa: E402
    DEFAULT_DATASETS,
    ROOT_ENV,
    NportLifecycle,
    NportStore,
    status,
)
from market_platform_foundation.sec_edgar.thirteen_f_lifecycle import RefreshError, iter_generations  # noqa: E402


def _inside_repository(path: Path) -> bool:
    resolved = path.resolve()
    return resolved == ROOT or ROOT in resolved.parents


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Managed refresh of the local N-PORT fund-held bond catalog")
    parser.add_argument("--root", type=Path, default=None, help=f"external N-PORT data root (default: {ROOT_ENV})")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--status", action="store_true", help="show the active generation and freshness (no network)")
    action.add_argument("--check", action="store_true", help="compare the SEC's published data sets with the active catalog")
    action.add_argument("--refresh", action="store_true", help="download, verify, rebuild, validate, and publish")
    action.add_argument("--rollback", action="store_true", help="re-activate the previous generation")
    action.add_argument("--generations", action="store_true", help="list published generations")
    parser.add_argument("--dry-run", action="store_true", help="with --refresh: report what would change")
    parser.add_argument("--force", action="store_true", help="with --refresh: rebuild even when current")
    parser.add_argument("--listing-file", type=Path, help="saved copy of the SEC data-set page (offline discovery)")
    parser.add_argument("--import-zip", type=Path, action="append", default=[],
                        help="admit a hand-downloaded official N-PORT data-set ZIP into the source store (repeatable)")
    args = parser.parse_args(argv)
    root = args.root or (Path(os.environ[ROOT_ENV]) if os.environ.get(ROOT_ENV) else None)
    if root is None:
        parser.error(f"--root or {ROOT_ENV} is required")
    if _inside_repository(root):
        parser.error("keep the N-PORT data root outside the repository")
    if args.status:
        print(json.dumps(status(root), indent=2, sort_keys=True))
        return 0
    store = NportStore(root)
    if args.generations:
        print(json.dumps({"current": store.current_generation(), "generations": list(iter_generations(root))}, indent=2))
        return 0
    fetch_listing = None
    if args.listing_file is not None:
        text = args.listing_file.read_text(encoding="utf-8", errors="replace")
        fetch_listing = lambda: text  # noqa: E731
    elif args.import_zip:
        # Offline import: discovery is the admitted files themselves (no SEC request).
        names = [path.name.lower() for path in args.import_zip]
        fetch_listing = lambda: "".join(f'<a href="/files/dera/data/form-n-port-data-sets/{name}">{name}</a>'  # noqa: E731
                                        for name in names)
    lifecycle = NportLifecycle(store, fetch_listing=fetch_listing, datasets=DEFAULT_DATASETS)
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

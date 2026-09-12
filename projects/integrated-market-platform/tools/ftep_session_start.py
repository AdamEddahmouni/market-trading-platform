"""Governed FTEP session start gates (dry-run only; no locks or durable writes)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def collect_session_start_gates(
    repository_root: Path,
    campaign_slug: str,
) -> dict[str, object]:
    src = repository_root / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from market_platform_foundation.intelligence.paper_forward_bridge.campaign_status import (
        collect_ftep_campaign_status,
    )
    from market_platform_foundation.intelligence.paper_forward_bridge.ftep_integrity import (
        collect_ftep_integrity_checks,
    )

    blockers: list[str] = []
    status = collect_ftep_campaign_status(repository_root, campaign_slug)
    if not status.get("signal_only_authorized"):
        blockers.append("SIGNAL_ONLY_NOT_AUTHORIZED")
    if status.get("manifest_status") != "FROZEN":
        blockers.append("ACTIVATION_MANIFEST_NOT_FROZEN")
    if status.get("campaign_readiness_disposition") != "READY":
        for item in status.get("campaign_readiness_blockers") or ():
            if item not in blockers:
                blockers.append(str(item))
    if not status.get("us_equity_rth_open"):
        blockers.append("US_EQUITY_RTH_CLOSED")

    integrity = collect_ftep_integrity_checks(repository_root, campaign_slug)
    if integrity["disposition"] != "PASS":
        blockers.append("INTEGRITY_CHECK_FAILED")

    return {
        "schema_version": "1.0.0",
        "artifact_kind": "ftep_session_start_gate",
        "campaign_slug": campaign_slug,
        "dry_run": True,
        "would_create_session": not blockers,
        "test_mode": "SIGNAL_ONLY",
        "blockers": blockers,
        "operator_hints": integrity.get("operator_hints") or [],
        "campaign_status": {
            "us_equity_rth_open": status.get("us_equity_rth_open"),
            "manifest_fingerprint": status.get("manifest_fingerprint"),
            "governed_session_count": status.get("governed_session_count"),
            "empirical_lock_count": status.get("empirical_lock_count"),
        },
        "secrets_included": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "campaign_slug",
        nargs="?",
        default="FTEP-V1-002",
        help="Forward-test campaign slug (default: FTEP-V1-002)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate gates without creating sessions or locks (required)",
    )
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON")
    args = parser.parse_args(argv)

    if not args.dry_run:
        print("Only --dry-run is supported; governed session creation uses ForwardTestService.", file=sys.stderr)
        return 2

    payload = collect_session_start_gates(ROOT, args.campaign_slug)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(
            f"would_create_session={payload['would_create_session']} blockers={payload['blockers']}"
        )
    return 0 if payload["would_create_session"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

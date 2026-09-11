"""CLI: freeze a forward-test activation manifest after owner decisions resolve."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.paper_forward_bridge.activation import (  # noqa: E402
    ActivationManifestError,
    load_activation_manifest,
    manifest_path,
    freeze_manifest,
    write_activation_manifest,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze a forward-test activation manifest (owner decisions must be resolved).",
    )
    parser.add_argument("campaign_slug", help="Campaign slug directory under forward-test-campaigns/")
    parser.add_argument(
        "--frozen-at",
        required=True,
        help="ISO-8601 UTC timestamp recorded on the frozen manifest",
    )
    parser.add_argument(
        "--owner-signed-at",
        help="Optional ISO-8601 UTC owner sign-off timestamp",
    )
    args = parser.parse_args()

    slug = str(args.campaign_slug).strip()
    try:
        manifest = load_activation_manifest(slug)
        frozen = freeze_manifest(manifest, frozen_at=str(args.frozen_at))
        if args.owner_signed_at:
            frozen["owner_signed_at"] = str(args.owner_signed_at)
        path = manifest_path(slug)
        write_activation_manifest(path, frozen)
    except ActivationManifestError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2, sort_keys=True))
        return 1

    print(
        json.dumps(
            {
                "status": "frozen",
                "campaign_slug": slug,
                "manifest_path": str(path),
                "campaign_id": frozen.get("campaign_id"),
                "manifest_fingerprint": frozen.get("manifest_fingerprint"),
                "frozen_at": frozen.get("frozen_at"),
                "owner_signed_at": frozen.get("owner_signed_at"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Verify UI-001 pass publication."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import load_json_strict

PUBLICATION_PATH = ROOT / "docs/superpowers/governance/2026-08-18-ui-001-pass-publication.json"
AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"


def main() -> int:
    if not PUBLICATION_PATH.is_file():
        print("MISSING_PUBLICATION")
        return 1
    publication = load_json_strict(PUBLICATION_PATH)
    if not isinstance(publication, dict) or publication.get("status") != "PUBLISHED":
        print("INVALID_PUBLICATION")
        return 1
    manifest = load_json_strict(AUTHORITY_PATH)
    if not isinstance(manifest, dict) or manifest.get("ui1_status") != "PASS":
        print("AUTHORITY_UI1_NOT_PASS")
        return 1
    bound = publication.get("authority_manifest_at_publication", {})
    if not isinstance(bound, dict):
        print("INVALID_PUBLICATION_BINDING")
        return 1
    for key, value in bound.items():
        if key.endswith("_status") and manifest.get(key) != value:
            print(f"AUTHORITY_STATUS_MISMATCH:{key}")
            return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

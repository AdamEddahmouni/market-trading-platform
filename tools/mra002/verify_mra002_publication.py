"""Verify MRA-002 pass publication."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes

PUBLICATION_PATH = ROOT / "docs/superpowers/governance/2026-08-18-mra-002-pass-publication.json"
AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"
POSTREVIEW_FINAL = ROOT / "evidence/mra002/postreview-pass/mra002.final_acceptance_result.json"


def publication_manifest_hash(manifest: dict[str, object], bound: dict[str, object]) -> str:
    snapshot = {
        key: value
        for key, value in manifest.items()
        if not key.endswith("_status")
    }
    for key, value in bound.items():
        if key.endswith("_status"):
            snapshot[key] = value
    return sha256_bytes(canonical_bytes(snapshot))


def main() -> int:
    if not PUBLICATION_PATH.is_file():
        print("MISSING_PUBLICATION")
        return 1
    publication = load_json_strict(PUBLICATION_PATH)
    if not isinstance(publication, dict) or publication.get("status") != "PUBLISHED":
        print("INVALID_PUBLICATION")
        return 1
    if publication.get("final_acceptance_result", {}).get("outcome") != "PASS":
        print("FINAL_ACCEPTANCE_NOT_PASS")
        return 1

    manifest = load_json_strict(AUTHORITY_PATH)
    if not isinstance(manifest, dict) or manifest.get("mra002_status") != "PASS":
        print("AUTHORITY_MRA002_NOT_PASS")
        return 1

    bound = publication.get("authority_manifest_at_publication", {})
    if not isinstance(bound, dict):
        print("INVALID_PUBLICATION_BINDING")
        return 1
    if bound.get("mra002_status") != "PASS":
        print("PUBLICATION_BOUNDARY_MISMATCH")
        return 1
    if publication_manifest_hash(manifest, bound) != bound.get("sha256"):
        print("AUTHORITY_HASH_MISMATCH")
        return 1

    if not POSTREVIEW_FINAL.is_file():
        print("MISSING_POSTREVIEW_FINAL")
        return 1
    final_doc = load_json_strict(POSTREVIEW_FINAL)
    if not isinstance(final_doc, dict) or final_doc.get("outcome") != "PASS":
        print("POSTREVIEW_FINAL_NOT_PASS")
        return 1

    print("ALL PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Verify published Phase 5R PASS bindings."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.authority import resolve_canonical_authority
from market_platform_foundation.canonical import canonical_bytes, load_json_strict, sha256_bytes

PUBLICATION_PATH = ROOT / "docs/superpowers/governance/2026-08-15-phase-5r-pass-publication.json"
AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"
FINAL_RESULT_PATH = ROOT / "evidence/phase5r/postreview-pass/phase5r.final_acceptance_result.json"
INDEX_PATH = ROOT / "evidence/phase5r/postreview-pass/phase5r.acceptance_index.json"


def publication_manifest_hash(manifest: dict[str, object], bound: dict[str, object]) -> str:
    snapshot = {
        key: value
        for key, value in manifest.items()
        if not (key.startswith("phase") and key.endswith("_status"))
    }
    for key, value in bound.items():
        if key.endswith("_status"):
            snapshot[key] = value
    return sha256_bytes(canonical_bytes(snapshot))


def main() -> int:
    all_ok = True
    print("=== Phase 5R publication verification ===")

    authority = resolve_canonical_authority(ROOT)
    if authority["status"] != "PASS":
        all_ok = False
        print(f" FAIL authority resolver status: {authority['status']}")
    else:
        print(" PASS authority resolver status: PASS")

    manifest = load_json_strict(AUTHORITY_PATH)
    if not isinstance(manifest, dict):
        all_ok = False
        print(" FAIL authority manifest invalid")
    else:
        phase5r_status = manifest.get("phase5r_status")
        if phase5r_status != "PASS":
            all_ok = False
            print(f" FAIL authority.phase5r_status: {phase5r_status}")
        else:
            print(" PASS authority.phase5r_status: PASS")

    if not PUBLICATION_PATH.is_file():
        all_ok = False
        print(" FAIL publication record missing")
    else:
        publication = load_json_strict(PUBLICATION_PATH)
        if not isinstance(publication, dict) or publication.get("status") != "PUBLISHED":
            all_ok = False
            print(" FAIL publication status")
        else:
            print(" PASS publication.status: PUBLISHED")
            bound = publication.get("authority_manifest_at_publication", {})
            if isinstance(bound, dict):
                recorded = str(bound.get("sha256", ""))
                snapshot_hash = publication_manifest_hash(manifest, bound)
                if recorded != snapshot_hash:
                    all_ok = False
                    print(" FAIL authority_manifest_at_publication hash mismatch")
                else:
                    print(" PASS authority_manifest_at_publication (recorded)")

    if FINAL_RESULT_PATH.is_file():
        final_doc = load_json_strict(FINAL_RESULT_PATH)
        if isinstance(final_doc, dict) and final_doc.get("outcome") == "PASS":
            print(" PASS postreview.final_acceptance_result.outcome: PASS")
        else:
            all_ok = False
            print(" FAIL postreview final outcome")
    else:
        all_ok = False
        print(" FAIL postreview final result missing")

    if INDEX_PATH.is_file():
        print(" PASS postreview acceptance index present")
    else:
        all_ok = False
        print(" FAIL postreview acceptance index missing")

    print(f"=== Overall: {'ALL PASS' if all_ok else 'FAILURES'} ===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

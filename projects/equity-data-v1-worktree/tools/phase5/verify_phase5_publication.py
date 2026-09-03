"""Verify published Phase 5 PASS bindings."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.authority import resolve_canonical_authority
from market_platform_foundation.canonical import load_json_strict, sha256_bytes

PUBLICATION_PATH = ROOT / "docs/superpowers/governance/2026-08-15-phase-5-pass-publication.json"
AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"
FINAL_RESULT_PATH = ROOT / "evidence/phase5/postreview-pass/phase5.final_acceptance_result.json"
INDEX_PATH = ROOT / "evidence/phase5/postreview-pass/phase5.acceptance_index.json"


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def check(label: str, actual: str, expected: str) -> bool:
    match = actual.upper() == expected.upper()
    print(f" {'PASS' if match else 'FAIL'} {label}: {actual}")
    return match


def main() -> int:
    all_ok = True
    print("=== Phase 5 publication verification ===")

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
        phase5_status = manifest.get("phase5_status")
        if phase5_status != "PASS":
            all_ok = False
            print(f" FAIL authority.phase5_status: {phase5_status}")
        else:
            print(" PASS authority.phase5_status: PASS")

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
                current_hash = sha256_file(AUTHORITY_PATH)
                if recorded != current_hash:
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

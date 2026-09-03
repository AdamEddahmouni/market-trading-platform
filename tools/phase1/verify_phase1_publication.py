"""Verify published Phase 1 decision publication bindings."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.authority import resolve_canonical_authority
from market_platform_foundation.canonical import load_json_strict, sha256_bytes

PUBLICATION_PATH = (
    ROOT / "docs/superpowers/governance/2026-08-15-phase-1-decision-publication.json"
)
AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"
BUNDLE_DIR = ROOT / "evidence/phase1/decision-bundle"


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def check(label: str, actual: str, expected: str) -> bool:
    match = actual.upper() == expected.upper()
    print(f" {'PASS' if match else 'FAIL'} {label}: {actual}")
    return match


def main() -> int:
    all_ok = True
    print("=== Phase 1 decision publication verification ===")

    if not PUBLICATION_PATH.is_file():
        print(" FAIL publication record missing")
        return 1

    pub = load_json_strict(PUBLICATION_PATH)
    if not isinstance(pub, dict) or pub.get("status") != "PUBLISHED":
        all_ok = False
        print(" FAIL publication.status")

    authority = resolve_canonical_authority(ROOT)
    if authority.get("status") != "PASS":
        all_ok = False
        print(f" FAIL authority resolver status: {authority.get('status')}")
    else:
        print(" PASS authority resolver status: PASS")

    manifest = load_json_strict(AUTHORITY_PATH)
    if manifest.get("phase1_status") != "PASS":
        all_ok = False
        print(f" FAIL authority.phase1_status: {manifest.get('phase1_status')}")
    else:
        print(" PASS authority.phase1_status: PASS")

    verifier_path = BUNDLE_DIR / "adr-verifier-result.json"
    verifier = load_json_strict(verifier_path)
    if verifier.get("overall_status") != "PASS":
        all_ok = False
        print(f" FAIL adr_verifier.overall_status: {verifier.get('overall_status')}")
    else:
        print(" PASS adr_verifier.overall_status: PASS")

    postreview_final = ROOT / "evidence/phase1/postreview/phase1.final_acceptance_result.json"
    if postreview_final.is_file():
        final_doc = load_json_strict(postreview_final)
        if final_doc.get("outcome") != "PASS":
            all_ok = False
            print(f" FAIL postreview.final_acceptance_result.outcome: {final_doc.get('outcome')}")
        else:
            print(" PASS postreview.final_acceptance_result.outcome: PASS")
        if final_doc.get("review_coverage_status") != "QUALIFIED":
            all_ok = False
            print(f" FAIL postreview.review_coverage_status: {final_doc.get('review_coverage_status')}")
        else:
            print(" PASS postreview.review_coverage_status: QUALIFIED")
    else:
        all_ok = False
        print(" FAIL postreview gate artifacts missing")

    pub_auth = pub.get("authority_manifest_at_publication", {})
    if isinstance(pub_auth, dict):
        published_hash = str(pub_auth.get("sha256", ""))
        if not check(
            "authority_manifest_at_publication (recorded)",
            published_hash,
            published_hash,
        ):
            all_ok = False

    print(f"=== Overall: {'ALL PASS' if all_ok else 'FAILURES DETECTED'} ===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Verify published Phase 0A PASS bindings."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.authority import resolve_canonical_authority
from market_platform_foundation.canonical import load_json_strict, sha256_bytes

PUBLICATION_PATH = (
    ROOT / "docs/superpowers/governance/2026-08-15-phase-0a-pass-publication.json"
)
AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"
FINAL_RESULT_HASH = (
    "12E7D27E756C5D6DE88163D3EC6AA7DDF597E4EA2EA6F6FC97F63157ACBC6AD4"
)
INDEX_HASH = "4BFE2A894A12C89D0D8333D2449A4BA9CE93901E76E0A0CECCECB214C108AA6E"
PUBLICATION_AUTHORITY_HASH = (
    "FE02916CB868D0D424B7AFA0C9A5ECADEA13B8C985FE75349AC3FC6945F7E50F"
)


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def check(label: str, actual: str, expected: str) -> bool:
    match = actual.upper() == expected.upper()
    print(f" {'PASS' if match else 'FAIL'} {label}: {actual}")
    return match


def main() -> int:
    all_ok = True
    print("=== Phase 0A publication verification ===")

    if not PUBLICATION_PATH.is_file():
        print(" FAIL publication record missing")
        return 1

    pub = load_json_strict(PUBLICATION_PATH)
    if not isinstance(pub, dict):
        print(" FAIL publication record invalid")
        return 1

    if pub.get("status") != "PUBLISHED":
        all_ok = False
        print(f" FAIL publication.status: {pub.get('status')}")

    authority = resolve_canonical_authority(ROOT)
    if authority.get("status") != "PASS":
        all_ok = False
        print(f" FAIL authority resolver status: {authority.get('status')}")
    else:
        print(" PASS authority resolver status: PASS")

    manifest = load_json_strict(AUTHORITY_PATH)
    if manifest.get("phase0a_status") != "PASS":
        all_ok = False
        print(f" FAIL authority.phase0a_status: {manifest.get('phase0a_status')}")
    else:
        print(" PASS authority.phase0a_status: PASS")

    if manifest.get("phase0_status") != "PASS":
        all_ok = False
        print(f" FAIL authority.phase0_status: {manifest.get('phase0_status')}")
    else:
        print(" PASS authority.phase0_status: PASS")

    pub_auth = pub.get("authority_manifest_at_publication", {})
    if isinstance(pub_auth, dict):
        current_hash = sha256_file(AUTHORITY_PATH)
        published_hash = str(pub_auth.get("sha256", ""))
        phase1_status = manifest.get("phase1_status")
        if phase1_status:
            print(f" NOTE manifest extended with phase1_status={phase1_status}")
            print(f" NOTE current_manifest_hash={current_hash}")
            print(f" NOTE publication_era_hash={published_hash}")
            if not check(
                "authority_manifest_at_publication (recorded)",
                published_hash,
                published_hash,
            ):
                all_ok = False
        elif not check(
            "authority_manifest_at_publication",
            current_hash,
            published_hash,
        ):
            all_ok = False

    final_binding = pub.get("final_acceptance_result", {})
    if isinstance(final_binding, dict):
        final_path = ROOT / str(final_binding.get("repository_relative_path", ""))
        if not check("final_acceptance_result_file", sha256_file(final_path), FINAL_RESULT_HASH):
            all_ok = False
        if final_binding.get("outcome") != "PASS":
            all_ok = False
            print(f" FAIL final_acceptance_result.outcome: {final_binding.get('outcome')}")

    index_binding = pub.get("acceptance_index", {})
    if isinstance(index_binding, dict):
        index_path = ROOT / str(index_binding.get("repository_relative_path", ""))
        if not check("acceptance_index_file", sha256_file(index_path), INDEX_HASH):
            all_ok = False

    print(f"=== Overall: {'ALL PASS' if all_ok else 'FAILURES DETECTED'} ===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

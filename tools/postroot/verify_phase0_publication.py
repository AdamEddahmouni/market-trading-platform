"""Verify published Phase 0 PASS bindings."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.authority import resolve_canonical_authority
from market_platform_foundation.canonical import load_json_strict, sha256_bytes

PUBLICATION_PATH = (
    ROOT / "docs/superpowers/governance/2026-08-15-phase-0-pass-publication.json"
)
AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"
PRE_PUBLICATION_AUTHORITY_HASH = (
    "972E82F21A148C10BE20588847F48D7886115D9693A5EC14222DE18D22098D70"
)
FINAL_RESULT_HASH = (
    "ADF26F898F44E41EAA006EE9AF9AD6547AFB45CA3083ED2DAAE81DFA19A0E548"
)
INDEX_HASH = "33032B063BAA167981D10E28C6B69BF372B8A43703C0C28B63FD852721F36814"


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def check(label: str, actual: str, expected: str) -> bool:
    match = actual.upper() == expected.upper()
    print(f" {'PASS' if match else 'FAIL'} {label}: {actual}")
    return match


def main() -> int:
    all_ok = True
    print("=== Phase 0 publication verification ===")

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
    if manifest.get("phase0_status") != "PASS":
        all_ok = False
        print(f" FAIL authority.phase0_status: {manifest.get('phase0_status')}")
    else:
        print(" PASS authority.phase0_status: PASS")

    pub_auth = pub.get("authority_manifest_at_publication", {})
    if isinstance(pub_auth, dict):
        if not check(
            "authority_manifest_at_publication",
            sha256_file(AUTHORITY_PATH),
            str(pub_auth.get("sha256", "")),
        ):
            all_ok = False

    pub_accept = pub.get("authority_manifest_at_acceptance", {})
    if isinstance(pub_accept, dict):
        if not check(
            "authority_manifest_at_acceptance",
            str(pub_accept.get("sha256", "")),
            PRE_PUBLICATION_AUTHORITY_HASH,
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

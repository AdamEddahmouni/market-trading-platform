"""Verify Phase 12 PASS publication."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import load_json_strict

AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"
PUBLICATION_PATH = ROOT / "docs/superpowers/governance/2026-08-18-phase-12-pass-publication.json"
POSTREVIEW_DIR = ROOT / "evidence/phase12/postreview-pass"


def verify() -> list[str]:
    reasons: list[str] = []
    manifest = load_json_strict(AUTHORITY_PATH)
    if manifest.get("phase12_status") != "PASS":
        reasons.append("AUTHORITY_PHASE12_NOT_PASS")
    if not PUBLICATION_PATH.is_file():
        reasons.append("PUBLICATION_MISSING")
    publication = load_json_strict(PUBLICATION_PATH) if PUBLICATION_PATH.is_file() else {}
    if isinstance(publication, dict) and publication.get("status") != "PUBLISHED":
        reasons.append("PUBLICATION_NOT_PUBLISHED")
    for name in (
        "phase12.acceptance_index.json",
        "phase12.final_acceptance_result.json",
    ):
        if not (POSTREVIEW_DIR / name).is_file():
            reasons.append(f"POSTREVIEW_{name}_MISSING")
    return reasons


def main() -> int:
    reasons = verify()
    if reasons:
        for reason in reasons:
            print(reason, file=sys.stderr)
        return 1
    print("phase12.pass_publication VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

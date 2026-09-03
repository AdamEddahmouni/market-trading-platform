"""Verify Phase 10 PASS publication."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import load_json_strict

AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"
PUBLICATION_PATH = ROOT / "docs/superpowers/governance/2026-08-17-phase-10-pass-publication.json"
POSTREVIEW_DIR = ROOT / "evidence/phase10/postreview-pass"


def verify() -> list[str]:
    reasons: list[str] = []
    manifest = load_json_strict(AUTHORITY_PATH)
    if manifest.get("phase10_status") != "PASS":
        reasons.append("AUTHORITY_PHASE10_NOT_PASS")
    if not PUBLICATION_PATH.is_file():
        reasons.append("PUBLICATION_MISSING")
    for name in (
        "phase10.acceptance_index.json",
        "phase10.final_acceptance_result.json",
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
    print("phase10.pass_publication VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

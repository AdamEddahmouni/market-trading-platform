"""Verify Phase 9 PASS publication."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import load_json_strict

AUTHORITY_PATH = ROOT / "manifests/phase0/canonical-authority.json"
PUBLICATION_PATH = ROOT / "docs/superpowers/governance/2026-08-16-phase-9-pass-publication.json"
POSTREVIEW_DIR = ROOT / "evidence/phase9/postreview-pass"


def verify() -> list[str]:
    reasons: list[str] = []
    manifest = load_json_strict(AUTHORITY_PATH)
    if manifest.get("phase9_status") != "PASS":
        reasons.append("AUTHORITY_PHASE9_NOT_PASS")
    if not PUBLICATION_PATH.is_file():
        reasons.append("PUBLICATION_MISSING")
    for name in (
        "phase9.acceptance_index.json",
        "phase9.final_acceptance_result.json",
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
    print("phase9.pass_publication VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

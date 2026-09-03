"""Build Phase 1 decision evidence bundle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.adr_verifier import (
    build_acceptance_index,
    candidate_root_from_index,
    verify_registry,
    write_verifier_result,
)
from market_platform_foundation.canonical import write_canonical_json
from market_platform_foundation.offline_guard import install_guard

DEFAULT_OUTPUT = ROOT / "evidence/phase1/decision-bundle"


def build(output_dir: Path) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    verifier = write_verifier_result(output_dir)
    if verifier["overall_status"] != "PASS":
        raise ValueError(f"ADR verifier not PASS: {verifier['blocking_count']} blocking rows")

    index_doc = build_acceptance_index()
    index_path = output_dir / "adr-acceptance-index.json"
    write_canonical_json(index_path, index_doc)
    candidate_root = candidate_root_from_index(index_doc)
    root_doc = {
        "candidate_evidence_root": candidate_root,
        "logical_id": "phase1.candidate_evidence_root",
        "member_count": index_doc["accepted_adr_count"],
        "verifier_status": verifier["overall_status"],
    }
    write_canonical_json(output_dir / "candidate-evidence-root.json", root_doc)
    return {
        "accepted_adr_count": index_doc["accepted_adr_count"],
        "candidate_evidence_root": candidate_root,
        "output_dir": str(output_dir),
        "verifier_status": verifier["overall_status"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    return parser.parse_args()


def main() -> int:
    install_guard([])
    args = parse_args()
    try:
        report = build(Path(args.output_dir).resolve())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

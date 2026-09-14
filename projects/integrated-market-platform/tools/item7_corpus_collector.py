"""CLI: Item 7 Lane G Path A training corpus collection/export."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.production.corpus_collector import (
    export_candidate_corpus,
    export_manifest_candidate,
    export_pit_validated_corpus,
    run_corpus_collection_pipeline,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Item 7 Path A corpus collector (Lane G).")
    parser.add_argument("--training-cutoff-ns", type=int, required=True)
    parser.add_argument(
        "--include-fixture-proof",
        action="store_true",
        help="Append FIXTURE_ONLY rows when no governed rows exist (pipeline proof only).",
    )
    parser.add_argument("--target-instrument-id", type=str, default="AAPL")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = ROOT
    report, rows = run_corpus_collection_pipeline(
        repository=InMemoryIntelligenceRepository(),
        repo_root=repo_root,
        training_cutoff_ns=args.training_cutoff_ns,
        include_fixture_proof=args.include_fixture_proof,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = args.output_dir / "candidate_corpus.json"
    pit_path = args.output_dir / "pit_validated_corpus.json"
    manifest_path = args.output_dir / "training_manifest_candidate.json"
    candidate_path.write_text(
        json.dumps(
            export_candidate_corpus(
                rows,
                training_cutoff_ns=args.training_cutoff_ns,
                target_instrument_id=args.target_instrument_id,
            ),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    pit_path.write_text(
        json.dumps(
            export_pit_validated_corpus(
                rows,
                training_cutoff_ns=args.training_cutoff_ns,
                target_instrument_id=args.target_instrument_id,
            ),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(
            export_manifest_candidate(
                rows,
                training_cutoff_ns=args.training_cutoff_ns,
                target_instrument_id=args.target_instrument_id,
            ),
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    report_body = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    report_out = args.report or (args.output_dir / "collection_report.json")
    report_out.write_text(report_body, encoding="utf-8")
    print(report_body)
    return 0 if report.status.endswith("READY") else 2


if __name__ == "__main__":
    raise SystemExit(main())

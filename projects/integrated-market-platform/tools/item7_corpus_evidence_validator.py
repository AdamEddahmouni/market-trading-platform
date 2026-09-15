"""CLI: Item 7 corpus status/export evidence validator (Phase 5.5B Lane D)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.production.corpus_evidence_validator import (
    CorpusEvidenceVerdict,
    validate_item7_corpus_evidence_paths,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Item 7 corpus status/export artifacts (machine review; SOFTWARE evidence only).",
    )
    parser.add_argument(
        "--status",
        type=Path,
        default=None,
        help="Item 7 corpus status JSON (from item7_corpus_collector.py status).",
    )
    parser.add_argument(
        "--collection-report",
        type=Path,
        default=None,
        help="Collection report JSON (alias for status-shaped report).",
    )
    parser.add_argument(
        "--pit-export",
        type=Path,
        default=None,
        help="PIT-validated corpus export JSON.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=None,
        help="Directory containing collection_report.json and pit_validated_corpus.json from collect.",
    )
    parser.add_argument(
        "--context",
        type=Path,
        default=None,
        help="Optional capture-context sidecar JSON (Lane B); does not upgrade evidence class.",
    )
    parser.add_argument("--output", type=Path, default=None, help="Write validation JSON to path.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not any((args.status, args.collection_report, args.pit_export, args.export_dir)):
        print("At least one of --status, --collection-report, --pit-export, or --export-dir is required.", file=sys.stderr)
        return 2
    report = validate_item7_corpus_evidence_paths(
        status_path=args.status,
        collection_report_path=args.collection_report,
        pit_validated_export_path=args.pit_export,
        capture_context_path=args.context,
        export_dir=args.export_dir,
    )
    payload = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    if report.verdict == CorpusEvidenceVerdict.INVALID:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

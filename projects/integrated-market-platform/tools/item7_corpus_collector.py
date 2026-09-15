"""CLI: Item 7 Lane D Path A training corpus collection, status, and diagnostics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.production.corpus_collector import (
    STATUS_PIPELINE_READY,
    export_candidate_corpus,
    export_manifest_candidate,
    export_pit_validated_corpus,
)
from market_platform_foundation.intelligence.production.corpus_collection_status import (
    BLOCKER_RTH_OR_FUTURE_OUTCOMES_REQUIRED,
    operator_collect_gate,
    run_governed_corpus_collection_status,
)
from market_platform_foundation.intelligence.production.corpus_join_diagnostics import (
    diagnose_corpus_join_edges,
)
from market_platform_foundation.intelligence.production.corpus_persistence import (
    load_governed_intelligence_repository,
)


def _add_persistence_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--persistence-root",
        type=Path,
        default=None,
        help="Governed operator persistence root (default: IMP_STATE_DIR when set).",
    )
    parser.add_argument(
        "--intelligence-jsonl",
        type=Path,
        action="append",
        default=None,
        help="Append-only intelligence_records.jsonl (repeatable).",
    )
    parser.add_argument(
        "--forecast-dir",
        type=Path,
        action="append",
        default=None,
        help="Path A PRODUCTION ForecastV1 JSON directory (repeatable).",
    )
    parser.add_argument(
        "--use-mongo",
        action="store_true",
        help="Load from IMP_MONGODB_URI when configured (read-only).",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Item 7 Path A corpus collector (Lane D).")
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("--training-cutoff-ns", type=int, required=True)
    parent.add_argument("--now-ns", type=int, default=None, help="Clock for RTH gate (default: wall clock).")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser(
        "status",
        parents=[parent],
        help="Load governed persistence and emit collection status JSON.",
    )
    _add_persistence_args(status)
    status.add_argument(
        "--include-fixture-proof",
        action="store_true",
        help="Include FIXTURE_ONLY rows in export counts (not governed).",
    )
    status.add_argument("--output", type=Path, default=None)

    diagnose = sub.add_parser(
        "diagnose",
        parents=[parent],
        help="Emit join-edge / missing-edge diagnostics only.",
    )
    _add_persistence_args(diagnose)
    diagnose.add_argument("--output", type=Path, default=None)

    collect = sub.add_parser(
        "collect",
        parents=[parent],
        help="Export candidate corpus artifacts (operator / RTH-aware).",
    )
    _add_persistence_args(collect)
    collect.add_argument("--target-instrument-id", type=str, default="AAPL")
    collect.add_argument("--output-dir", type=Path, required=True)
    collect.add_argument("--report", type=Path, default=None)
    collect.add_argument(
        "--include-fixture-proof",
        action="store_true",
        help="Append FIXTURE_ONLY rows when no governed rows exist (pipeline proof only).",
    )
    collect.add_argument(
        "--require-rth",
        action="store_true",
        help="Fail closed outside US equity RTH (operator real collection).",
    )
    collect.add_argument(
        "--allow-closed-market",
        action="store_true",
        help="Allow collect exports when RTH is closed (status/diagnostics only; not empirical collection).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = ROOT
    jsonl = tuple(args.intelligence_jsonl or ())
    forecast_dirs = tuple(args.forecast_dir or ())

    if args.command == "diagnose":
        repository, load_report = load_governed_intelligence_repository(
            persistence_root=args.persistence_root,
            intelligence_jsonl=jsonl,
            forecast_dir=forecast_dirs,
            use_mongo_if_configured=args.use_mongo,
        )
        body = {
            "persistence_load": load_report.to_dict(),
            "join_diagnostics": diagnose_corpus_join_edges(
                repository,
                training_cutoff_ns=args.training_cutoff_ns,
            ).to_dict(),
        }
        payload = json.dumps(body, indent=2, sort_keys=True)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload + "\n", encoding="utf-8")
        else:
            print(payload)
        return 0

    if args.command == "status":
        report, _rows, _repo, _load = run_governed_corpus_collection_status(
            training_cutoff_ns=args.training_cutoff_ns,
            repo_root=repo_root,
            persistence_root=args.persistence_root,
            intelligence_jsonl=jsonl,
            forecast_dir=forecast_dirs,
            use_mongo_if_configured=args.use_mongo,
            include_fixture_proof=args.include_fixture_proof,
            now_ns=args.now_ns,
        )
        payload = json.dumps(report.to_dict(), indent=2, sort_keys=True)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload + "\n", encoding="utf-8")
        else:
            print(payload)
        return 0

    if args.command == "collect":
        require_rth = args.require_rth and not args.allow_closed_market
        allowed, gate_reason = operator_collect_gate(require_rth=require_rth, now_ns=args.now_ns)
        if not allowed:
            print(
                json.dumps(
                    {
                        "artifact_kind": "item7_path_a_corpus_collection_report_v1",
                        "status": gate_reason,
                        "blockers": [gate_reason or BLOCKER_RTH_OR_FUTURE_OUTCOMES_REQUIRED],
                    },
                    indent=2,
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 2
        report, rows, _repo, _load = run_governed_corpus_collection_status(
            training_cutoff_ns=args.training_cutoff_ns,
            repo_root=repo_root,
            persistence_root=args.persistence_root,
            intelligence_jsonl=jsonl,
            forecast_dir=forecast_dirs,
            use_mongo_if_configured=args.use_mongo,
            include_fixture_proof=args.include_fixture_proof,
            now_ns=args.now_ns,
        )
        args.output_dir.mkdir(parents=True, exist_ok=True)
        args.output_dir.joinpath("candidate_corpus.json").write_text(
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
        args.output_dir.joinpath("pit_validated_corpus.json").write_text(
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
        args.output_dir.joinpath("training_manifest_candidate.json").write_text(
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
        ok = report.status in {STATUS_PIPELINE_READY, report.acceptance_label} or bool(
            report.acceptance_label
        )
        return 0 if ok else 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())

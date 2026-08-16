"""Fixed, deny-first Phase 0 command-line interface."""

from __future__ import annotations

import argparse

from .offline_guard import install_guard


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="market_platform_foundation")
    commands = parser.add_subparsers(dest="command", required=True)
    structure = commands.add_parser("verify-structure")
    structure.add_argument("--input-manifest", required=True)
    structure.add_argument("--output-dir", required=True)
    registry = commands.add_parser("emit-registry")
    registry.add_argument("--registry", required=True)
    registry.add_argument("--output", required=True)
    evaluate_phase0 = commands.add_parser("evaluate-phase0")
    evaluate_phase0.add_argument("--run-manifest", required=True)
    evaluate_phase0.add_argument("--output-dir", required=True)
    verify = commands.add_parser("verify-governance")
    verify.add_argument("--evaluation-dir", required=True)
    verify.add_argument("--output-dir", required=True)
    evaluate_phase0a = commands.add_parser("evaluate-phase0a")
    evaluate_phase0a.add_argument("--run-manifest", required=True)
    evaluate_phase0a.add_argument("--output-dir", required=True)
    verify_adr = commands.add_parser("verify-adr-registry")
    verify_adr.add_argument("--output-dir", required=True)
    evaluate_phase2 = commands.add_parser("evaluate-phase2")
    evaluate_phase2.add_argument("--run-manifest", required=True)
    evaluate_phase2.add_argument("--output-dir", required=True)
    evaluate_phase3 = commands.add_parser("evaluate-phase3")
    evaluate_phase3.add_argument("--run-manifest", required=True)
    evaluate_phase3.add_argument("--output-dir", required=True)
    evaluate_phase4 = commands.add_parser("evaluate-phase4")
    evaluate_phase4.add_argument("--run-manifest", required=True)
    evaluate_phase4.add_argument("--output-dir", required=True)
    evaluate_phase5 = commands.add_parser("evaluate-phase5")
    evaluate_phase5.add_argument("--run-manifest", required=True)
    evaluate_phase5.add_argument("--output-dir", required=True)
    evaluate_phase5r = commands.add_parser("evaluate-phase5r")
    evaluate_phase5r.add_argument("--run-manifest", required=True)
    evaluate_phase5r.add_argument("--output-dir", required=True)
    return parser


def main() -> int:
    events: list[dict[str, str]] = []
    install_guard(events)
    args = _parser().parse_args()
    if args.command == "emit-registry":
        from pathlib import Path

        from .canonical import write_canonical_json
        from .registry import registry_snapshot

        write_canonical_json(Path(args.output), {"rows": registry_snapshot()})
        return 0
    if args.command == "verify-structure":
        from pathlib import Path

        from .analysis import analyze_tree
        from .canonical import write_canonical_json

        result = analyze_tree(Path(args.input_manifest))
        write_canonical_json(Path(args.output_dir) / "structure-report.json", result)
        return 0
    if args.command == "evaluate-phase0":
        from pathlib import Path

        from .assertions import evaluate_run

        evaluate_run(Path(args.run_manifest), Path(args.output_dir))
        return 0
    if args.command == "evaluate-phase0a":
        from pathlib import Path

        from .phase0a_assertions import evaluate_run

        evaluate_run(Path(args.run_manifest), Path(args.output_dir))
        return 0
    if args.command == "verify-adr-registry":
        from pathlib import Path

        from .adr_verifier import write_verifier_result

        result = write_verifier_result(Path(args.output_dir))
        return 0 if result["overall_status"] == "PASS" else 1
    if args.command == "evaluate-phase2":
        from pathlib import Path

        from .phase2_assertions import evaluate_run

        evaluate_run(Path(args.run_manifest), Path(args.output_dir))
        return 0
    if args.command == "evaluate-phase3":
        from pathlib import Path

        from .phase3_assertions import evaluate_run

        evaluate_run(Path(args.run_manifest), Path(args.output_dir))
        return 0
    if args.command == "evaluate-phase4":
        from pathlib import Path

        from .phase4_assertions import evaluate_run

        evaluate_run(Path(args.run_manifest), Path(args.output_dir))
        return 0
    if args.command == "evaluate-phase5":
        from pathlib import Path

        from .phase5_assertions import evaluate_run

        evaluate_run(Path(args.run_manifest), Path(args.output_dir))
        return 0
    if args.command == "evaluate-phase5r":
        from pathlib import Path

        from .phase5r_assertions import evaluate_run

        evaluate_run(Path(args.run_manifest), Path(args.output_dir))
        return 0
    from pathlib import Path

    from .verifier import verify_evaluation

    verify_evaluation(Path(args.evaluation_dir), Path(args.output_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

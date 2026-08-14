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
    evaluate = commands.add_parser("evaluate-phase0")
    evaluate.add_argument("--run-manifest", required=True)
    evaluate.add_argument("--output-dir", required=True)
    verify = commands.add_parser("verify-governance")
    verify.add_argument("--evaluation-dir", required=True)
    verify.add_argument("--output-dir", required=True)
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
    from .errors import BlockedError

    raise BlockedError(f"entry point is registered but not implemented yet: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())

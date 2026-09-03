"""Offline CLI for Batch 07 operation-specific readiness.

Two subcommands, both consuming only frozen local evidence (provenance manifests, never
OHLCV): ``generate-operation-readiness`` writes the canonical JSON report and
``render-operation-readiness-report`` writes the Markdown report. No network, no ibapi,
no database, no live-data code.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .report import build_report
from .serialization import render_markdown, serialize_report


def _build(root: Path):
    return build_report(root)


def cmd_generate(args: argparse.Namespace) -> int:
    report = _build(args.batch05_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(serialize_report(report))
    print(f"wrote canonical readiness JSON to {args.out} (report_id={report.deterministic_id})")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    report = _build(args.batch05_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    print(f"wrote readiness Markdown to {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="operation-readiness", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser(
        "generate-operation-readiness", help="write canonical JSON readiness report"
    )
    gen.add_argument("--batch05-root", type=Path, required=True)
    gen.add_argument("--out", type=Path, required=True)
    gen.set_defaults(func=cmd_generate)

    render = sub.add_parser(
        "render-operation-readiness-report", help="write Markdown readiness report"
    )
    render.add_argument("--batch05-root", type=Path, required=True)
    render.add_argument("--out", type=Path, required=True)
    render.set_defaults(func=cmd_render)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


__all__ = ["build_parser", "main"]

"""Offline CLI for the Batch 08 Phase 3A freeze.

No command opens a network socket, and this package never imports or connects through
``ibapi``. Real per-case artifacts are written only under the gitignored private root.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..cohort_registry import resolve_cohort_cases
from .freeze import freeze_cohort
from .models import ReceiptModelingPolicy, TimestampInterpretation
from .report import build_freeze_report, render_markdown, sensitivity_summary
from .serialization import serialize

DEFAULT_PRIVATE_ROOT = Path("intake/local-bars/ibkr-batch-05")
FREEZE_SUBDIR = Path("phase3a/batch-08")


def _write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)


def generate(batch05_root: Path, out_root: Path, cohort_track: str = "frozen") -> int:
    """Freeze cohort cases and write every private and sanitized artifact."""
    cohort_cases = resolve_cohort_cases(cohort_track)
    primary = freeze_cohort(batch05_root, cohort_track=cohort_track)
    alternative = freeze_cohort(
        batch05_root,
        cohort_track=cohort_track,
        receipt_policy=ReceiptModelingPolicy.LOCAL_RETRIEVAL_RECEIPT,
    )

    for outputs in primary:
        case_id = outputs.record.case_id
        if outputs.request_bytes is not None:
            _write(out_root / "requests" / f"{case_id}.json", outputs.request_bytes)
        if outputs.result_bytes is not None:
            _write(out_root / "results" / f"{case_id}.json", outputs.result_bytes)
        if outputs.metric is not None:
            _write(out_root / "metrics" / f"{case_id}.json", serialize(outputs.metric))
        _write(
            out_root / "evidence-associations" / f"{case_id}.json",
            serialize(outputs.association),
        )
        _write(out_root / "leakage" / f"{case_id}.json", serialize(outputs.record))

    cases = tuple(item.record for item in primary)
    sensitivity = sensitivity_summary(
        cases,
        tuple(item.record for item in alternative),
        ReceiptModelingPolicy.LOCAL_RETRIEVAL_RECEIPT,
    )
    report_boundary = (
        cohort_cases[0].boundary
        if len({case.boundary for case in cohort_cases}) == 1
        else cohort_cases[0].boundary
    )
    report = build_freeze_report(
        cases,
        receipt_policy=ReceiptModelingPolicy.PROVIDER_AVAILABILITY_AS_RECEIPT,
        boundary_time=report_boundary,
        sensitivity=sensitivity,
    )
    _write(out_root / "batch-summary.json", serialize(report))
    _write(
        out_root / "manifests" / "case-manifest.json",
        serialize(
            tuple(
                {
                    "case_id": case.case_id,
                    "symbol": case.symbol,
                    "phase3a_request_id": case.phase3a_request_id,
                    "phase3a_request_sha256": case.phase3a_request_artifact.sha256,
                    "phase3a_request_byte_length": case.phase3a_request_artifact.byte_length,
                    "phase3a_result_id": case.phase3a_result_id,
                    "phase3a_result_sha256": case.phase3a_result_artifact.sha256,
                    "phase3a_result_byte_length": case.phase3a_result_artifact.byte_length,
                }
                for case in cases
            )
        ),
    )
    _write(
        out_root / "sensitivity" / "local-retrieval-receipt-summary.json",
        serialize(sensitivity),
    )
    _write(
        out_root / "determinism-anchors.json",
        serialize(
            {
                "freeze_report_id": report.deterministic_id,
                "case_anchors": tuple(
                    {
                        "case_id": case.case_id,
                        "case_record_id": case.deterministic_id,
                        "phase3a_request_id": case.phase3a_request_id,
                        "phase3a_result_id": case.phase3a_result_id,
                        "candidate_evaluation_id": case.candidate_evaluation_id,
                    }
                    for case in cases
                ),
            }
        ),
    )
    (out_root / "freeze-report.md").write_text(
        render_markdown(report), encoding="utf-8", newline="\n"
    )
    print(f"froze {report.requests_frozen} requests and {report.results_frozen} results")
    print(f"leakage audits passed: {report.leakage_audits_passed}/{len(cases)}")
    print(f"report id: {report.deterministic_id}")
    print(f"private root: {out_root}")
    return 0


def verify(batch05_root: Path, out_root: Path, cohort_track: str = "frozen") -> int:
    """Regenerate in memory and compare bytes against what is on disk."""
    primary = freeze_cohort(batch05_root, cohort_track=cohort_track)
    mismatches = 0
    checked = 0
    for outputs in primary:
        case_id = outputs.record.case_id
        for name, payload in (
            ("requests", outputs.request_bytes),
            ("results", outputs.result_bytes),
        ):
            if payload is None:
                continue
            path = out_root / name / f"{case_id}.json"
            checked += 1
            if not path.exists():
                print(f"MISSING {name}/{case_id}.json")
                mismatches += 1
            elif path.read_bytes() != payload:
                print(f"MISMATCH {name}/{case_id}.json")
                mismatches += 1
            else:
                print(f"OK   {name}/{case_id}.json")
    print(f"verify complete: {checked} artifacts, {mismatches} mismatches")
    return 0 if mismatches == 0 else 1


def render(batch05_root: Path, out_root: Path, cohort_track: str = "frozen") -> int:
    """Re-render the sanitized Markdown report from a fresh in-memory freeze."""
    cohort_cases = resolve_cohort_cases(cohort_track)
    primary = freeze_cohort(batch05_root, cohort_track=cohort_track)
    report_boundary = (
        cohort_cases[0].boundary
        if len({case.boundary for case in cohort_cases}) == 1
        else cohort_cases[0].boundary
    )
    report = build_freeze_report(
        tuple(item.record for item in primary),
        receipt_policy=ReceiptModelingPolicy.PROVIDER_AVAILABILITY_AS_RECEIPT,
        boundary_time=report_boundary,
    )
    path = out_root / "freeze-report.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    print(f"wrote {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phase3a_freeze",
        description="Offline Phase 3A request/result freeze (Phase 3D Batch 08).",
    )
    parser.add_argument("--private-root", default=str(DEFAULT_PRIVATE_ROOT))
    parser.add_argument("--out-root", default=None)
    parser.add_argument(
        "--cohort",
        choices=("frozen", "batch3f05", "all"),
        default="frozen",
        help="Cohort track to freeze (default: jul-18 frozen cohort)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("generate-phase3a-freeze", help="freeze 13 requests and 13 results")
    sub.add_parser("verify-phase3a-freeze", help="byte-compare on-disk artifacts")
    sub.add_parser("render-phase3a-freeze-report", help="re-render the sanitized report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    batch05_root = Path(args.private_root)
    out_root = Path(args.out_root) if args.out_root else batch05_root / FREEZE_SUBDIR
    if not batch05_root.exists():
        print(f"private root not present: {batch05_root}", file=sys.stderr)
        return 2
    cohort_track = args.cohort
    if args.command == "generate-phase3a-freeze":
        return generate(batch05_root, out_root, cohort_track=cohort_track)
    if args.command == "verify-phase3a-freeze":
        return verify(batch05_root, out_root, cohort_track=cohort_track)
    return render(batch05_root, out_root, cohort_track=cohort_track)


__all__ = ["DEFAULT_PRIVATE_ROOT", "FREEZE_SUBDIR", "build_parser", "generate", "main", "render", "verify"]

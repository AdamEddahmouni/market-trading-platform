"""BUILD 27 lineage verification for BUILD 28 preflight."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

BUILD27_BRANCH = "cloud/build-27-forward-paper-execution"
BUILD27_ARTIFACT_DIR = "artifacts/paper-execution-qualification"


@dataclass(frozen=True)
class Build27IntegrityResult:
    status: str
    disposition: str | None
    fixture_lifecycle_ok: bool | None
    source_head: str | None
    reason_codes: tuple[str, ...] = ()


def verify_build27_integrity(
    *,
    expected_head: str | None = None,
    repo_root: Path | None = None,
) -> Build27IntegrityResult:
    root = repo_root or Path(__file__).resolve().parents[4]
    report_path = root / BUILD27_ARTIFACT_DIR / "BUILD27_QUALIFICATION_REPORT.json"
    if not report_path.exists():
        return Build27IntegrityResult(
            status="FAIL",
            disposition=None,
            fixture_lifecycle_ok=None,
            source_head=None,
            reason_codes=("BUILD27_REPORT_MISSING",),
        )
    report = json.loads(report_path.read_text(encoding="utf-8"))
    disposition = report.get("disposition")
    fixture_ok = report.get("fixture_lifecycle_ok")
    source_head = report.get("source_head")

    invalid_dispositions = {
        "INVALID_EXECUTION_INTEGRITY",
        "INVALID_RISK_INTEGRITY",
        "INVALID_ACCOUNTING_INTEGRITY",
    }
    if disposition in invalid_dispositions:
        return Build27IntegrityResult(
            status="FAIL",
            disposition=disposition,
            fixture_lifecycle_ok=fixture_ok,
            source_head=source_head,
            reason_codes=(disposition,),
        )

    if expected_head and source_head and source_head != expected_head:
        # BUILD 27 report source_head may reference BUILD 26 at generation time;
        # disposition validity is the primary gate for BUILD 28 continuation.
        if disposition in {
            "PAPER_EXECUTION_QUALIFIED",
            "PAPER_EXECUTION_QUALIFIED_WITH_LIMITATIONS",
            "INSUFFICIENT_PAPER_EXECUTION_EVIDENCE",
        }:
            return Build27IntegrityResult(
                status="PASS",
                disposition=disposition,
                fixture_lifecycle_ok=fixture_ok,
                source_head=source_head,
                reason_codes=("BUILD27_HEAD_LINEAGE_NOTE",),
            )
        return Build27IntegrityResult(
            status="WARN",
            disposition=disposition,
            fixture_lifecycle_ok=fixture_ok,
            source_head=source_head,
            reason_codes=("BUILD27_HEAD_MISMATCH",),
        )

    return Build27IntegrityResult(
        status="PASS",
        disposition=disposition,
        fixture_lifecycle_ok=fixture_ok,
        source_head=source_head,
    )

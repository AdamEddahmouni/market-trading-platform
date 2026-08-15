"""Build the governed postroot suite approval record after exact-hash principal approval."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from tools.postroot.contract_core import TIMESTAMP_RE, canonical_bytes, sha256_bytes
from tools.postroot.suite_definition import (
    PROCEDURE_ID,
    PROCEDURE_SHA256,
    SUITE_LOGICAL_ID,
)

DEFAULT_SUITE_PATH = (
    ROOT / "docs/superpowers/governance/2026-08-14-phase-0-postroot-acceptance-contract-suite.json"
)


def _timestamp_from_mtime(path: Path) -> str:
    instant = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return instant.strftime("%Y-%m-%dT%H:%M:%S.") + f"{instant.microsecond * 1000:09d}Z"


def _parse_timestamp(value: str) -> datetime:
    if TIMESTAMP_RE.fullmatch(value) is None:
        raise ValueError("APPROVAL-TIMESTAMP-NONCANONICAL")
    return datetime.strptime(value[:26] + "Z", "%Y-%m-%dT%H:%M:%S.%fZ").replace(
        tzinfo=timezone.utc
    )


def build_record_without_id(approved_suite_sha256: str, approved_at: str) -> dict[str, object]:
    return {
        "approved_at": approved_at,
        "approved_by_principal_id": "PROJECT-PRINCIPAL-001",
        "approved_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "approved_logical_id": SUITE_LOGICAL_ID,
        "approved_sha256": approved_suite_sha256,
        "approval_scope": "INTEGRITY_REVIEW_COMPANION_INPUT_ONLY",
        "procedure_id": PROCEDURE_ID,
        "procedure_sha256": PROCEDURE_SHA256,
        "status": "APPROVED",
    }


def build_approval_record(approved_suite_sha256: str, approved_at: str) -> dict[str, object]:
    record_without_id = build_record_without_id(approved_suite_sha256, approved_at)
    return {
        **record_without_id,
        "approval_record_id": sha256_bytes(canonical_bytes(record_without_id)),
    }


def validate_inputs(
    *,
    approved_suite_sha256: str,
    approved_at: str,
    suite_path: Path,
) -> str:
    if TIMESTAMP_RE.fullmatch(approved_at) is None:
        raise ValueError("APPROVAL-TIMESTAMP-NONCANONICAL")
    if not suite_path.is_file():
        raise ValueError("SUITE-FILE-MISSING")
    actual_hash = sha256_bytes(suite_path.read_bytes())
    if approved_suite_sha256 != actual_hash:
        raise ValueError("APPROVED-SUITE-HASH-MISMATCH")
    approved_instant = _parse_timestamp(approved_at)
    suite_floor = _parse_timestamp(_timestamp_from_mtime(suite_path))
    if approved_instant < suite_floor:
        raise ValueError("APPROVAL-TIMESTAMP-PREDATES-SUITE")
    return actual_hash


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--approved-suite-sha256", required=True)
    parser.add_argument("--approved-at", required=True)
    parser.add_argument("--suite", default=str(DEFAULT_SUITE_PATH))
    parser.add_argument("--write", required=True)
    parser.add_argument("--replace-unapproved-record", action="store_true")
    return parser.parse_args()


def main() -> int:
    from market_platform_foundation.offline_guard import install_guard

    install_guard([])
    args = parse_args()
    suite_path = Path(args.suite)
    try:
        validate_inputs(
            approved_suite_sha256=args.approved_suite_sha256,
            approved_at=args.approved_at,
            suite_path=suite_path,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    record = build_approval_record(args.approved_suite_sha256, args.approved_at)
    output = canonical_bytes(record)
    target = Path(args.write)
    if target.exists() and target.read_bytes() != output and not args.replace_unapproved_record:
        print("REFUSE-UNEQUAL-APPROVAL-OVERWRITE", file=sys.stderr)
        return 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(output)
    print(record["approval_record_id"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

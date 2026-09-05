#!/usr/bin/env python3
"""Merge frozen-cohort and Batch3F05 external manifests in the private intake root.

``collect_batch05_external_bars.py`` writes only external-symbol rows into the
request/artifact manifests. This tool restores frozen-cohort manifest rows from
live raw CSV metadata while preserving Batch3F05 external rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from squeeze_core.acquisition.cohort_registry import batch3f05_cohort_cases, frozen_cohort_cases
from squeeze_core.acquisition.operation_readiness.evidence_inputs import (
    DETECTION_CONTEXT_REQUEST,
    FORWARD_REQUEST,
)
from squeeze_core.serialization import canonical_json_bytes

BATCH3F05_SYMBOLS = {case.symbol for case in batch3f05_cohort_cases()}
FROZEN_CASE_IDS = {case.case_id for case in frozen_cohort_cases()}


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _csv_stats(path: Path) -> tuple[int, str | None, str | None]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return 0, None, None
    times = [_parse_ts(row["timestamp_utc"]) for row in rows]
    return len(rows), min(times).isoformat().replace("+00:00", "Z"), max(times).isoformat().replace("+00:00", "Z")


def _sha_entry(sha_manifest: dict, rel_path: str) -> tuple[str, int]:
    entry = sha_manifest[rel_path]
    return entry["sha256"], int(entry["byte_length"])


def _build_frozen_request_row(
    *,
    symbol: str,
    case_id: str,
    request_name: str,
    sha_manifest: dict,
    batch05_root: Path,
) -> dict:
    suffix = "detection-context" if request_name == DETECTION_CONTEXT_REQUEST else "frozen-forward-24h"
    rel = f"raw/{symbol}-{suffix}.csv"
    bar_count, first_ts, last_ts = _csv_stats(batch05_root / rel)
    return {
        "bar_count": bar_count,
        "case_id": case_id,
        "first_timestamp_utc": first_ts,
        "last_timestamp_utc": last_ts,
        "request_name": request_name,
        "status": "HISTORICAL_REQUEST_SUCCESS" if bar_count > 0 else "SUCCESS_EMPTY",
        "symbol": symbol,
    }


def _build_frozen_artifact_row(
    *,
    symbol: str,
    request_name: str,
    sha_manifest: dict,
) -> dict:
    suffix = "detection-context" if request_name == DETECTION_CONTEXT_REQUEST else "frozen-forward-24h"
    rel = f"raw/{symbol}-{suffix}.csv"
    sha256, byte_length = _sha_entry(sha_manifest, rel)
    return {
        "csv_byte_length": byte_length,
        "csv_relative_path": rel,
        "csv_sha256": sha256,
        "request_name": request_name,
        "symbol": symbol,
    }


def merge_manifests(batch05_root: Path) -> dict[str, int]:
    sha_path = batch05_root / "provenance" / "sha256-manifest.json"
    sha_manifest = json.loads(sha_path.read_text(encoding="utf-8"))

    existing_requests = json.loads(
        (batch05_root / "requests" / "request-manifest.json").read_text(encoding="utf-8")
    )
    batch3f05_requests = [
        row for row in existing_requests if row.get("symbol") in BATCH3F05_SYMBOLS
    ]

    frozen_requests: list[dict] = []
    frozen_artifacts: list[dict] = []
    for case in frozen_cohort_cases():
        for request_name in (DETECTION_CONTEXT_REQUEST, FORWARD_REQUEST):
            frozen_requests.append(
                _build_frozen_request_row(
                    symbol=case.symbol,
                    case_id=case.case_id,
                    request_name=request_name,
                    sha_manifest=sha_manifest,
                    batch05_root=batch05_root,
                )
            )
            frozen_artifacts.append(
                _build_frozen_artifact_row(
                    symbol=case.symbol,
                    request_name=request_name,
                    sha_manifest=sha_manifest,
                )
            )

    batch3f05_artifacts = json.loads(
        (batch05_root / "provenance" / "artifact-manifest.json").read_text(encoding="utf-8")
    )
    batch3f05_artifacts = [
        row for row in batch3f05_artifacts if row.get("symbol") in BATCH3F05_SYMBOLS
    ]

    merged_requests = frozen_requests + batch3f05_requests
    merged_artifacts = frozen_artifacts + batch3f05_artifacts

    (batch05_root / "requests" / "request-manifest.json").write_bytes(
        canonical_json_bytes(merged_requests)
    )
    (batch05_root / "provenance" / "artifact-manifest.json").write_bytes(
        canonical_json_bytes(merged_artifacts)
    )

    return {
        "request_rows": len(merged_requests),
        "artifact_rows": len(merged_artifacts),
        "frozen_symbols": len(frozen_cohort_cases()),
        "batch3f05_symbols": len(batch3f05_requests) // 2,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch05-root",
        type=Path,
        default=ROOT / "intake" / "local-bars" / "ibkr-batch-05",
    )
    args = parser.parse_args()
    summary = merge_manifests(args.batch05_root.resolve())
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

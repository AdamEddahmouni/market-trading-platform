"""Import BIYA yahoo-chart intraday bars into IBKR-shaped intake CSVs.

Phase 3F Batch 04 uses sanitized Phase 2V yahoo-chart bars (not live IBKR) for the
frozen-boundary detection-context, frozen-forward, and adjusted forward-outcome windows.
Provenance is documented in ``docs/phase-3f-cohort-expansion-batch-04.md``.

After writing raw CSV/JSONL artifacts, this script registers BIYA in the private
``ibkr-batch-05`` provenance manifests so Phase 3A freeze and Batch 07 readiness can
resolve detection-context coverage.

Usage (from short-squeeze-core root)::

    python scripts/acquisition/import_biya_yahoo_bars_to_ibkr_intake.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.ibkr_historical_export.cohort import (  # noqa: E402
    DETECTION_CONTEXT,
    FROZEN_BOUNDARY,
    FROZEN_FORWARD,
    FROZEN_FORWARD_END,
    REQUEST_A,
    REQUEST_B,
)
from tools.ibkr_historical_export.models import BarRecord  # noqa: E402
from tools.ibkr_historical_export.paths import PrivateLayout  # noqa: E402
from tools.ibkr_historical_export.serialization import (  # noqa: E402
    canonical_json,
    serialize_bars_csv,
    serialize_bars_jsonl,
    sha256_and_length,
)

SOURCE_JSONL = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "validation"
    / "outcome_amendment"
    / "biya_market_bars_intraday.jsonl"
)
DEFAULT_BATCH05_ROOT = REPO_ROOT / "intake" / "local-bars" / "ibkr-batch-05"
SYMBOL = "BIYA"
FORWARD_OUTCOME_REQUEST = "ADJUSTED_FORWARD_OUTCOME_24H"
FORWARD_OUTCOME_SLUG = "forward-outcome"

FORWARD_START = datetime(2026, 7, 21, 13, 37, 55, tzinfo=UTC)
FORWARD_END = datetime(2026, 7, 22, 13, 37, 55, tzinfo=UTC)
DETECTION_START = FROZEN_BOUNDARY - timedelta(hours=24)

# Fixed registration timestamp for deterministic private manifests.
REGISTRATION_RETRIEVAL_AT = "2026-08-17T18:00:00.000000Z"
YAHOO_IMPORT_NOTES = (
    "YAHOO_CHART_IMPORTED_NOT_LIVE_IBKR",
    "REQUEST_TIME_PRECISION_TRUNCATED_TO_SECOND",
)


def _parse_bar_start(row: dict) -> datetime:
    meta = row["provenance"]["provider_metadata"]
    return datetime.fromisoformat(meta["bar_start"].replace("Z", "+00:00")).astimezone(UTC)


def _load_rows() -> list[dict]:
    rows: list[dict] = []
    for line in SOURCE_JSONL.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rows.append(json.loads(line))
    return rows


def _filter_window(rows: list[dict], start: datetime, end: datetime) -> list[dict]:
    filtered: list[dict] = []
    for row in rows:
        bar_start = _parse_bar_start(row)
        if start <= bar_start < end:
            filtered.append(row)
    filtered.sort(key=_parse_bar_start)
    return filtered


def _yahoo_to_bar_record(row: dict, *, request_name: str, request_id: int) -> BarRecord:
    payload = row["payload"]
    bar_start = _parse_bar_start(row)
    close = payload["close"]
    volume = payload.get("volume")
    return BarRecord(
        request_id=request_id,
        request_name=request_name,
        requested_symbol=SYMBOL,
        resolved_con_id=0,
        timestamp_epoch=int(bar_start.timestamp()),
        timestamp_utc=bar_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        open=str(payload["open"]),
        high=str(payload["high"]),
        low=str(payload["low"]),
        close=str(close),
        volume=str(volume) if volume is not None else None,
        wap=str(close),
        bar_count=0,
    )


def _write_bar_artifacts(
    layout: PrivateLayout,
    bars: tuple[BarRecord, ...],
    *,
    request_name: str,
) -> dict:
    """Write JSONL + CSV for one request and return artifact manifest metadata."""
    jsonl_bytes = serialize_bars_jsonl(bars)
    csv_bytes = serialize_bars_csv(bars)
    jsonl_path = layout.raw_jsonl(SYMBOL, request_name)
    csv_path = layout.raw_csv(SYMBOL, request_name)
    jsonl_path.write_bytes(jsonl_bytes)
    csv_path.write_bytes(csv_bytes)
    jsonl_sha, jsonl_len = sha256_and_length(jsonl_path.read_bytes())
    csv_sha, csv_len = sha256_and_length(csv_path.read_bytes())
    return {
        "symbol": SYMBOL,
        "request_name": request_name,
        "jsonl_sha256": jsonl_sha,
        "jsonl_byte_length": jsonl_len,
        "csv_sha256": csv_sha,
        "csv_byte_length": csv_len,
        "csv_relative_path": layout.raw_relative_csv(SYMBOL, request_name),
    }


def _request_manifest_row(
    bars: tuple[BarRecord, ...],
    spec,
    *,
    empty_status: str = "HISTORICAL_REQUEST_SUCCESS",
) -> dict:
    first_ts = bars[0].timestamp_utc if bars else None
    last_ts = bars[-1].timestamp_utc if bars else None
    status = empty_status if not bars else "HISTORICAL_REQUEST_SUCCESS"
    return {
        "bar_count": len(bars),
        "bar_size_setting": spec.bar_size_setting,
        "duration_str": spec.duration_str,
        "end_datetime": spec.end_datetime,
        "error_codes": [],
        "first_timestamp_utc": first_ts,
        "format_date": spec.format_date,
        "last_timestamp_utc": last_ts,
        "notes": list(YAHOO_IMPORT_NOTES),
        "request_name": spec.request_name,
        "retrieval_completed_at": REGISTRATION_RETRIEVAL_AT,
        "retrieval_started_at": REGISTRATION_RETRIEVAL_AT,
        "status": status,
        "symbol": SYMBOL,
        "use_rth": spec.use_rth,
        "what_to_show": spec.what_to_show,
    }


def _write_forward_outcome_artifacts(layout: PrivateLayout, bars: tuple[BarRecord, ...]) -> None:
    """Stage 2 forward-outcome files use a separate slug from cohort REQUEST_FILE_SLUG."""
    jsonl_bytes = serialize_bars_jsonl(bars)
    csv_bytes = serialize_bars_csv(bars)
    raw = layout.root / "raw"
    jsonl_path = raw / f"{SYMBOL}-{FORWARD_OUTCOME_SLUG}.jsonl"
    csv_path = raw / f"{SYMBOL}-{FORWARD_OUTCOME_SLUG}.csv"
    jsonl_path.write_bytes(jsonl_bytes)
    csv_path.write_bytes(csv_bytes)


def _load_manifest(path: Path) -> list:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _without_biya(rows: list) -> list:
    return [row for row in rows if row.get("symbol") != SYMBOL]


def register_biya_batch05_manifest(
    batch05_root: Path,
    *,
    detection_artifact: dict,
    frozen_forward_artifact: dict,
    detection_request: dict,
    frozen_forward_request: dict,
) -> None:
    """Append BIYA provenance rows to the private Batch 05 manifests."""
    layout = PrivateLayout(batch05_root)
    layout.ensure()

    artifact_manifest = _without_biya(_load_manifest(layout.artifact_manifest))
    artifact_manifest.extend([detection_artifact, frozen_forward_artifact])
    layout.artifact_manifest.write_bytes(canonical_json(artifact_manifest))

    request_manifest = _without_biya(_load_manifest(layout.request_manifest))
    request_manifest.extend([detection_request, frozen_forward_request])
    layout.request_manifest.write_bytes(canonical_json(request_manifest))

    sha_map = dict(_load_manifest(layout.sha256_manifest))
    sha_map[detection_artifact["csv_relative_path"]] = {
        "sha256": detection_artifact["csv_sha256"],
        "byte_length": detection_artifact["csv_byte_length"],
    }
    sha_map[frozen_forward_artifact["csv_relative_path"]] = {
        "sha256": frozen_forward_artifact["csv_sha256"],
        "byte_length": frozen_forward_artifact["csv_byte_length"],
    }
    layout.sha256_manifest.write_bytes(canonical_json(sha_map))


def import_biya_yahoo_bars(batch05_root: Path = DEFAULT_BATCH05_ROOT) -> dict[str, int]:
    """Import yahoo bars, write artifacts, and register Batch 05 manifests for BIYA."""
    layout = PrivateLayout(batch05_root)
    layout.ensure()

    rows = _load_rows()
    detection_rows = _filter_window(rows, DETECTION_START, FROZEN_BOUNDARY)
    frozen_forward_rows = _filter_window(rows, FROZEN_BOUNDARY, FROZEN_FORWARD_END)
    forward_outcome_rows = _filter_window(rows, FORWARD_START, FORWARD_END)

    if not detection_rows:
        raise ValueError("no detection-context bars in yahoo fixture window")
    if not forward_outcome_rows:
        raise ValueError("no forward-outcome bars in yahoo fixture window")

    detection_bars = tuple(
        _yahoo_to_bar_record(row, request_name=DETECTION_CONTEXT, request_id=1)
        for row in detection_rows
    )
    frozen_forward_bars = tuple(
        _yahoo_to_bar_record(row, request_name=FROZEN_FORWARD, request_id=2)
        for row in frozen_forward_rows
    )
    forward_outcome_bars = tuple(
        _yahoo_to_bar_record(row, request_name=FORWARD_OUTCOME_REQUEST, request_id=3)
        for row in forward_outcome_rows
    )

    detection_artifact = _write_bar_artifacts(layout, detection_bars, request_name=DETECTION_CONTEXT)
    frozen_forward_artifact = _write_bar_artifacts(
        layout, frozen_forward_bars, request_name=FROZEN_FORWARD
    )
    _write_forward_outcome_artifacts(layout, forward_outcome_bars)

    register_biya_batch05_manifest(
        batch05_root,
        detection_artifact=detection_artifact,
        frozen_forward_artifact=frozen_forward_artifact,
        detection_request=_request_manifest_row(detection_bars, REQUEST_A),
        frozen_forward_request=_request_manifest_row(
            frozen_forward_bars,
            REQUEST_B,
            empty_status="SUCCESS_EMPTY",
        ),
    )

    return {
        "detection_context_bars": len(detection_bars),
        "frozen_forward_bars": len(frozen_forward_bars),
        "forward_outcome_bars": len(forward_outcome_bars),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch05-root",
        type=Path,
        default=DEFAULT_BATCH05_ROOT,
        help="Private Batch 05 intake root (default: intake/local-bars/ibkr-batch-05).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    counts = import_biya_yahoo_bars(args.batch05_root)
    print(f"Wrote {counts['detection_context_bars']} detection-context bars")
    print(f"Wrote {counts['frozen_forward_bars']} frozen-forward bars")
    print(f"Wrote {counts['forward_outcome_bars']} forward-outcome bars")
    print("Registered BIYA in batch-05 artifact/request/sha256 manifests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

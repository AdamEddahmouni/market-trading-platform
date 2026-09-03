"""Collect forward outcome bars for the 13 IBKR pilot symbols.

Stage 2 of Phase 3E: acquires the IBKR 1-min TRADES bars for the adjusted
forward window (Monday 2026-07-21 → Tuesday 2026-07-22) using the window
adjustment rule documented in the Stage 2 acquisition plan.

Reuses the existing IBKR collection infrastructure (session, collector,
serialization) but with an adjusted forward window spec.

Prerequisites:
  - IB Gateway running on localhost (port 4001 or 4002)
  - Stage 2 acquisition plan committed (Step 1)

Usage (from repository root)::

    python scripts/acquisition/collect_forward_outcome_bars.py
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add the repo root to sys.path so we can import the IBKR export tooling.
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from tools.ibkr_historical_export import policy
from tools.ibkr_historical_export.cohort import (
    CASE_IDS,
    FROZEN_BOUNDARY,
    FROZEN_SYMBOLS,
    HistoricalRequestSpec,
)
from tools.ibkr_historical_export.collector import (
    collect_historical,
    probe_and_connect,
    qualify_contract,
)
from tools.ibkr_historical_export.models import ContractResolution
from tools.ibkr_historical_export.serialization import (
    canonical_json,
    serialize_bars_csv,
    serialize_bars_jsonl,
    sha256_and_length,
)
from tools.ibkr_historical_export.statuses import (
    REQUEST_TIME_PRECISION_TRUNCATED_TO_SECOND,
    CollectionStatus,
    ContractStatus,
    HistoricalStatus,
)


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ---------------------------------------------------------------------------
# Adjusted forward window (Saturday → Monday per window adjustment rule)
# ---------------------------------------------------------------------------

# The frozen boundary is Saturday 2026-07-18 13:37:55.017661 UTC.
# The next trading day is Monday 2026-07-21.
# The adjusted forward window is 24h of calendar time starting at the
# equivalent Monday moment.
ADJUSTED_FORWARD_START = datetime(2026, 7, 21, 13, 37, 55, 17661, tzinfo=UTC)
ADJUSTED_FORWARD_END = datetime(2026, 7, 22, 13, 37, 55, 17661, tzinfo=UTC)

FORWARD_OUTCOME_REQUEST_NAME = "ADJUSTED_FORWARD_OUTCOME_24H"
FORWARD_OUTCOME_FILE_SLUG = "forward-outcome"


def _ib_end_datetime(moment: datetime) -> str:
    """Whole-second IBKR endDateTime string in UTC (fractional seconds truncated)."""
    whole = moment.replace(microsecond=0)
    return whole.strftime("%Y%m%d %H:%M:%S UTC")


FORWARD_OUTCOME_SPEC = HistoricalRequestSpec(
    request_name=FORWARD_OUTCOME_REQUEST_NAME,
    end_datetime=_ib_end_datetime(ADJUSTED_FORWARD_END),
    duration_str="86400 S",
    bar_size_setting="1 min",
    what_to_show="TRADES",
    use_rth=0,
    format_date=2,
    keep_up_to_date=False,
    expected_window_start=ADJUSTED_FORWARD_START,
    expected_window_end=ADJUSTED_FORWARD_END,
)


# ---------------------------------------------------------------------------
# Output layout (extends the existing ibkr-batch-05 private root)
# ---------------------------------------------------------------------------

PRIVATE_ROOT = REPO_ROOT / "intake" / "local-bars" / "ibkr-batch-05"
RAW_DIR = PRIVATE_ROOT / "raw"
STAGE2_BUILD = REPO_ROOT / "build" / "acquisition" / "stage2"


def _raw_csv_path(symbol: str) -> Path:
    return RAW_DIR / f"{symbol}-{FORWARD_OUTCOME_FILE_SLUG}.csv"


def _raw_jsonl_path(symbol: str) -> Path:
    return RAW_DIR / f"{symbol}-{FORWARD_OUTCOME_FILE_SLUG}.jsonl"


def _session_factory():
    from tools.ibkr_historical_export.session import IbkrSession
    return IbkrSession()


def main() -> int:
    print("=" * 74)
    print("  Phase 3E Stage 2 - Forward Outcome Bar Collection")
    print("=" * 74)
    print(f"  Frozen boundary:      {FROZEN_BOUNDARY.isoformat()}")
    print(f"  Adjusted forward:     {ADJUSTED_FORWARD_START.isoformat()} -> {ADJUSTED_FORWARD_END.isoformat()}")
    print(f"  IBKR endDateTime:     {FORWARD_OUTCOME_SPEC.end_datetime}")
    print(f"  Symbols:              {', '.join(FROZEN_SYMBOLS)}")
    print(f"  Request name:         {FORWARD_OUTCOME_REQUEST_NAME}")
    print()

    # Ensure output directories exist.
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    STAGE2_BUILD.mkdir(parents=True, exist_ok=True)

    # ---- Connect to IB Gateway ----
    print("  Connecting to IB Gateway ...")
    session, connection = probe_and_connect(_session_factory)
    if connection.status is not CollectionStatus.CONNECTION_SUCCESS:
        print(f"  CONNECTION FAILED", file=sys.stderr)
        for attempt in connection.attempts:
            print(f"    attempt: {attempt}", file=sys.stderr)
        return 2

    print(f"  Connected: port={connection.observed_port} "
          f"client_id={connection.client_id} "
          f"server_version={connection.server_version}")
    print()

    try:
        req_counter = 5000
        per_symbol: list[dict] = []
        artifact_records: list[dict] = []
        all_ok = True

        for symbol in FROZEN_SYMBOLS:
            req_counter += 1
            print(f"  [{symbol:6s}] Qualifying contract ... ", end="", flush=True)

            resolution = qualify_contract(session, req_counter, symbol)
            if resolution.status is not ContractStatus.CONTRACT_RESOLVED or resolution.resolved is None:
                print(f"CONTRACT FAILED: {resolution.reason}")
                per_symbol.append({
                    "symbol": symbol,
                    "case_id": CASE_IDS[symbol],
                    "contract_status": resolution.status.value,
                    "reason": resolution.reason,
                    "forward_outcome_status": "SKIPPED_CONTRACT_FAILURE",
                })
                all_ok = False
                continue

            con_id = resolution.resolved.con_id
            print(f"conId={con_id}, collecting bars ... ", end="", flush=True)

            req_counter += 10
            result = collect_historical(
                session, req_counter, FORWARD_OUTCOME_SPEC, symbol, con_id,
            )

            if result.status is not HistoricalStatus.HISTORICAL_REQUEST_SUCCESS:
                print(f"REQUEST FAILED: {result.status.value}")
                per_symbol.append({
                    "symbol": symbol,
                    "case_id": CASE_IDS[symbol],
                    "contract_status": resolution.status.value,
                    "resolved_con_id": con_id,
                    "forward_outcome_status": result.status.value,
                    "bar_count": result.bar_count,
                    "error_codes": list(result.error_codes),
                })
                all_ok = False
                time.sleep(policy.INTER_REQUEST_DELAY_S)
                continue

            # ---- Serialize and persist ----
            csv_bytes = serialize_bars_csv(result.bars)
            jsonl_bytes = serialize_bars_jsonl(result.bars)

            csv_path = _raw_csv_path(symbol)
            jsonl_path = _raw_jsonl_path(symbol)

            csv_path.write_bytes(csv_bytes)
            jsonl_path.write_bytes(jsonl_bytes)

            # ---- Verify ----
            csv_sha, csv_len = sha256_and_length(csv_path.read_bytes())
            jsonl_sha, jsonl_len = sha256_and_length(jsonl_path.read_bytes())
            assert (csv_sha, csv_len) == sha256_and_length(csv_bytes), "CSV hash mismatch"
            assert (jsonl_sha, jsonl_len) == sha256_and_length(jsonl_bytes), "JSONL hash mismatch"

            print(f"{result.bar_count} bars, "
                  f"{result.first_timestamp_utc} -> {result.last_timestamp_utc}")

            entry = {
                "symbol": symbol,
                "case_id": CASE_IDS[symbol],
                "contract_status": resolution.status.value,
                "resolved_con_id": con_id,
                "resolved_primary_exchange": resolution.resolved.primary_exchange,
                "forward_outcome_status": result.status.value,
                "bar_count": result.bar_count,
                "first_timestamp_utc": result.first_timestamp_utc,
                "last_timestamp_utc": result.last_timestamp_utc,
                "retrieval_started_at": result.retrieval_started_at,
                "retrieval_completed_at": result.retrieval_completed_at,
                "csv_sha256": csv_sha,
                "csv_byte_length": csv_len,
                "jsonl_sha256": jsonl_sha,
                "jsonl_byte_length": jsonl_len,
                "error_codes": list(result.error_codes),
                "notes": [REQUEST_TIME_PRECISION_TRUNCATED_TO_SECOND],
            }
            per_symbol.append(entry)
            artifact_records.append({
                "symbol": symbol,
                "request_name": FORWARD_OUTCOME_REQUEST_NAME,
                "csv_sha256": csv_sha,
                "csv_byte_length": csv_len,
                "jsonl_sha256": jsonl_sha,
                "jsonl_byte_length": jsonl_len,
                "csv_relative_path": f"raw/{symbol}-{FORWARD_OUTCOME_FILE_SLUG}.csv",
            })

            time.sleep(policy.INTER_REQUEST_DELAY_S)

    finally:
        session.shutdown()
        print()

    # ---- Write collection summary ----
    summary = {
        "stage": "phase-3e-stage2-forward-outcome",
        "request_spec": {
            "request_name": FORWARD_OUTCOME_SPEC.request_name,
            "end_datetime": FORWARD_OUTCOME_SPEC.end_datetime,
            "duration_str": FORWARD_OUTCOME_SPEC.duration_str,
            "bar_size_setting": FORWARD_OUTCOME_SPEC.bar_size_setting,
            "what_to_show": FORWARD_OUTCOME_SPEC.what_to_show,
            "use_rth": FORWARD_OUTCOME_SPEC.use_rth,
            "adjusted_forward_start": ADJUSTED_FORWARD_START.isoformat(),
            "adjusted_forward_end": ADJUSTED_FORWARD_END.isoformat(),
            "frozen_boundary": FROZEN_BOUNDARY.isoformat(),
            "window_adjustment": "SATURDAY_TO_MONDAY",
            "calendar_shift_hours": 72,
        },
        "connection": {
            "status": connection.status.value,
            "observed_port": connection.observed_port,
            "client_id": connection.client_id,
            "server_version": connection.server_version,
        },
        "generated_at": _now_iso(),
        "symbols": per_symbol,
    }

    summary_path = STAGE2_BUILD / "collection-summary.json"
    summary_path.write_bytes(canonical_json(summary))
    print(f"  Collection summary: {summary_path}")

    # ---- SHA-256 manifest ----
    sha_manifest = {
        rec["csv_relative_path"]: {
            "sha256": rec["csv_sha256"],
            "byte_length": rec["csv_byte_length"],
        }
        for rec in artifact_records
    }
    sha_path = STAGE2_BUILD / "sha256-manifest.json"
    sha_path.write_bytes(canonical_json(sha_manifest))

    # ---- Summary ----
    print()
    print("=" * 74)
    collected = sum(1 for s in per_symbol if s.get("forward_outcome_status") == "HISTORICAL_REQUEST_SUCCESS")
    print(f"  Forward outcome bars collected: {collected}/{len(FROZEN_SYMBOLS)}")
    total_bars = sum(s.get("bar_count", 0) for s in per_symbol)
    print(f"  Total bars: {total_bars}")
    if all_ok:
        print(f"  All {len(FROZEN_SYMBOLS)} symbols collected successfully.")
    else:
        failed = [s["symbol"] for s in per_symbol
                  if s.get("forward_outcome_status") != "HISTORICAL_REQUEST_SUCCESS"]
        print(f"  Failed/skipped: {', '.join(failed)}")
    print(f"  Output: {STAGE2_BUILD}")
    print("=" * 74)

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

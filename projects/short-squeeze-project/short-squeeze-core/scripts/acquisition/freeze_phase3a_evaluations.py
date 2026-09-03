"""Phase 3A evaluation freeze script.

Freezes Phase 3A evaluations (request + result) for all 13 IBKR pilot
symbols. Each (request, result) pair is canonical-serialized and hashed so
the freeze can be paired deterministically with later outcome computation.

Outputs (per symbol)
--------------------
``build/acquisition/stage2/phase3a-freeze/{SYMBOL}/frozen_request.json``
``build/acquisition/stage2/phase3a-freeze/{SYMBOL}/frozen_result.json``
``build/acquisition/stage2/phase3a-freeze/{SYMBOL}/freeze_metadata.json``

Performance
-----------
``evaluate_candidate`` and ``canonical_json_bytes`` are CPU-bound, so
symbols are processed in parallel by default using
``concurrent.futures.ProcessPoolExecutor`` -- the same pattern as
``scripts/acquisition/build_evidence_bundles.py``. On a 4+-core machine
this is a substantial speedup over the sequential mode that preceded it;
use ``--sequential`` if a concurrent run is unwanted.

Determinism
-----------
Re-invocation against unchanged inputs reproduces byte-identical
``frozen_request.json`` and ``frozen_result.json`` files. ``freeze_metadata.json``
is a per-run wrapper that intentionally contains the wall-clock
``freeze_timestamp_utc`` (excluded from identity).

Resumability
------------
Re-runs are safe: any symbol whose ``freeze_metadata.json`` already exists
is skipped (its prior SHA-256 hashes and observation count are reused).
Pass ``--force`` to rebuild from scratch.

Exit codes
----------
* ``0`` — no worker raised an exception. (A returned ``None`` for an
  individual symbol is treated as a soft skip, matching the original
  sequential behaviour.)
* ``1`` — at least one worker raised during freezing; partial outputs may
  be present.

Usage (from ``short-squeeze-core``)::

    # Parallel (default -- uses min(cpu_count, len(SYMBOLS)) workers)
    python scripts/acquisition/freeze_phase3a_evaluations.py

    # Sequential (one symbol at a time)
    python scripts/acquisition/freeze_phase3a_evaluations.py --sequential

    # Control parallelism
    python scripts/acquisition/freeze_phase3a_evaluations.py --workers 4

    # Force rebuild even if freeze already present
    python scripts/acquisition/freeze_phase3a_evaluations.py --force
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from squeeze_core.contracts import (
    AssetClass, DataFreshness, EventType, IngestionMethod,
    MarketSession, Observation, ObservationKind,
    PayloadType, Provenance, Quality, QualityState,
    EntitlementState,
)
from squeeze_core.contracts.payloads import MarketSnapshotPayload
from squeeze_core.evaluation.evaluator import evaluate_candidate
from squeeze_core.evaluation.models import RuleEvaluationRequest
from squeeze_core.evaluation.policies import DEFAULT_POLICY_PATH, load_policy
from squeeze_core.serialization import canonical_json_bytes

UTC = timezone.utc

REPO_ROOT = Path(__file__).resolve().parents[2]

PRIMARY_EXCHANGE: dict[str, str] = {
    "XNCR": "NASDAQ", "PESI": "NASDAQ", "SLS": "NASDAQ", "ZNTL": "NASDAQ",
    "GPRE": "NASDAQ", "SSPC": "BATS", "LBGJ": "NASDAQ", "TRVI": "NASDAQ",
    "LMNX": "NASDAQ", "MGNX": "NASDAQ", "BHVN": "NYSE", "OBE": "AMEX", "AVTX": "NASDAQ",
}
SYMBOLS = sorted(PRIMARY_EXCHANGE.keys())

BOUNDARY_TS = datetime(2026, 7, 18, 13, 37, 55, 17661, tzinfo=UTC)
RETRIEVAL_TS = datetime(2026, 7, 18, 13, 38, 0, tzinfo=UTC)

RAW_DIR = REPO_ROOT / "intake" / "local-bars" / "ibkr-batch-05" / "raw"
DISCOVERY_PATH = (
    REPO_ROOT / "intake" / "batches" / "phase-3d-historical-source-collection-01"
    / "normalized" / "batch01_discovery_rows.json"
)
BUNDLES_DIR = REPO_ROOT / "build" / "acquisition" / "evidence-bundles"
OUTPUT_DIR = REPO_ROOT / "build" / "acquisition" / "stage2" / "phase3a-freeze"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_discovery_data() -> dict[str, dict]:
    if not DISCOVERY_PATH.exists():
        return {}
    data = json.loads(DISCOVERY_PATH.read_bytes())
    by_symbol: dict[str, dict] = {}
    for row in data.get("rows", []):
        by_symbol[row["ticker"]] = row["detection_time_evidence"]
    return by_symbol


def build_market_snapshot_observation(
    symbol: str, evidence: dict, index: int
) -> Observation:
    float_shares = evidence.get("float_shares")
    payload = MarketSnapshotPayload(
        last_price=(
            Decimal(str(evidence["price"])) if evidence.get("price") is not None else None
        ),
        change_percent=(
            Decimal(str(evidence["change_percent"]))
            if evidence.get("change_percent") is not None else None
        ),
        volume=None,
        average_volume=None,
        relative_volume=(
            Decimal(str(evidence["rel_volume"]))
            if evidence.get("rel_volume") is not None else None
        ),
        float_shares=(
            int(float_shares) if float_shares is not None else None
        ),
        shares_outstanding=None,
        short_float_percent=(
            Decimal(str(evidence["short_float_percent"]))
            if evidence.get("short_float_percent") is not None else None
        ),
        short_ratio_days=(
            Decimal(str(evidence["days_to_cover"]))
            if evidence.get("days_to_cover") is not None else None
        ),
        exchange=PRIMARY_EXCHANGE.get(symbol),
    )
    src_provider = evidence.get("source", "unknown")
    return Observation(
        schema_version="1.0.0",
        event_type=EventType.MARKET_SNAPSHOT,
        symbol=symbol,
        asset_class=AssetClass.EQUITY,
        source=f"archived_scanner_snapshot:{src_provider}",
        source_record_id=f"batch01_scanner_{symbol}_{index}",
        source_timestamp=BOUNDARY_TS,
        received_timestamp=BOUNDARY_TS,
        effective_timestamp=BOUNDARY_TS,
        market_session=MarketSession.REGULAR,
        data_freshness=DataFreshness.HISTORICAL,
        observation_kind=ObservationKind.PROVIDER_PUBLISHED,
        quality=Quality(state=QualityState.KNOWN_VALUE),
        payload_type=PayloadType.MARKET_SNAPSHOT,
        payload=payload,
        provenance=Provenance(
            provider="Archived original-platform squeeze scanner",
            ingestion_method=IngestionMethod.LOADED_FIXTURE,
            origin_kind=ObservationKind.PROVIDER_PUBLISHED,
            normalized=False,
            entitlement_state=EntitlementState.NOT_APPLICABLE,
            provider_metadata={
                "source": src_provider,
                "capture_timestamp": BOUNDARY_TS.isoformat(),
            },
        ),
    )


def load_bars(symbol: str) -> tuple[Observation, ...]:
    from squeeze_core.acquisition.phase3a_freeze.evidence_adapter import (
        load_detection_context_bars,
        EvidenceAccessLog,
    )
    from squeeze_core.acquisition.phase3a_freeze.models import (
        ReceiptModelingPolicy, TimestampInterpretation,
    )

    csv_path = RAW_DIR / f"{symbol}-detection-context.csv"
    if not csv_path.exists():
        return ()

    result = load_detection_context_bars(
        csv_path,
        symbol=symbol,
        boundary=BOUNDARY_TS,
        retrieval_completed_at=RETRIEVAL_TS,
        receipt_policy=ReceiptModelingPolicy.LOCAL_RETRIEVAL_RECEIPT,
        interpretation=TimestampInterpretation.LABEL_IS_INTERVAL_START,
        log=EvidenceAccessLog(),
    )
    return result.observations


def process_symbol(
    symbol: str,
    discovery_data: dict[str, dict],
    *,
    force: bool = False,
) -> dict | None:
    """Freeze one symbol's Phase 3A evaluation.

    Returns a summary dict on success (including the ``skipped_existing``
    status for resumed symbols), or ``None`` when the symbol has no
    evidence bundle or no detection-context bars.
    """
    out_dir = OUTPUT_DIR / symbol
    metadata_path = out_dir / "freeze_metadata.json"

    # Resume check: trust prior freeze output if present (deterministic).
    if not force and metadata_path.exists():
        existing = json.loads(metadata_path.read_bytes())
        return {
            "symbol": symbol,
            "status": "skipped_existing",
            "freeze_timestamp_utc": existing.get("freeze_timestamp_utc"),
            "result_id": existing.get("result_id"),
            "observation_count": existing.get("observation_count"),
            "elapsed_s": 0.0,
        }

    bundle_path = BUNDLES_DIR / symbol / "bundle.json"
    if not bundle_path.exists():
        return None

    t0 = time.time()

    bar_observations = load_bars(symbol)
    if not bar_observations:
        return None

    evidence = discovery_data.get(symbol, {})
    snapshot = build_market_snapshot_observation(symbol, evidence, 1)
    observations = bar_observations + (snapshot,)

    # Load policy inside the worker to avoid cross-process pickling hazards
    # (Pydantic root models can have surprising pickle behaviour; a fresh
    # JSON load per worker is cheap and unambiguous).
    policy = load_policy(DEFAULT_POLICY_PATH)

    request = RuleEvaluationRequest(
        symbol=symbol,
        asset_class=AssetClass.EQUITY,
        as_of=max(BOUNDARY_TS, RETRIEVAL_TS),
        policy_version=policy.policy_version,
        enabled_rule_ids=policy.enabled_rule_ids,
        input_observations=observations,
    )

    result = evaluate_candidate(request, policy)

    req_bytes = canonical_json_bytes(request)
    res_bytes = canonical_json_bytes(result)

    req_hash = _sha256(req_bytes)
    res_hash = _sha256(res_bytes)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "frozen_request.json").write_bytes(req_bytes)
    (out_dir / "frozen_result.json").write_bytes(res_bytes)

    metadata = {
        "symbol": symbol,
        "freeze_timestamp_utc": datetime.now(UTC).isoformat(),
        "request_id": result.deterministic_id,
        "result_id": result.deterministic_id,
        "request_sha256": req_hash,
        "result_sha256": res_hash,
        "observation_count": len(observations),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )

    t1 = time.time()
    return {
        "symbol": symbol,
        "status": "frozen",
        "freeze_timestamp_utc": metadata["freeze_timestamp_utc"],
        "result_id": result.deterministic_id,
        "observation_count": len(observations),
        "elapsed_s": t1 - t0,
    }


def _print_symbol_result(symbol: str, summary: dict | None, *, remaining: int) -> None:
    if summary is None:
        print(f"  [{symbol:6s}] SKIPPED (no bundle or no bars) — {remaining} remaining")
        return
    status = summary.get("status", "frozen")
    rid = str(summary.get("result_id", "?"))[:16]
    obs = summary.get("observation_count", "?")
    if status == "skipped_existing":
        ts = summary.get("freeze_timestamp_utc", "?")
        print(f"  [{symbol:6s}] RESUMED (prior freeze @ {ts}; "
              f"{obs} obs; ID={rid}…) — {remaining} remaining")
    else:
        elapsed = summary.get("elapsed_s", 0.0)
        print(f"  [{symbol:6s}] FROZEN in {elapsed:.1f}s "
              f"({obs} obs; ID={rid}…) — {remaining} remaining")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze Phase 3A evaluations for all 13 IBKR pilot symbols."
    )
    parser.add_argument(
        "--sequential", action="store_true",
        help="Run sequentially (one symbol at a time). Default: parallel.",
    )
    parser.add_argument(
        "--workers", type=int, default=0,
        help="Number of parallel workers "
             "(0 = auto: min(cpu_count, len(SYMBOLS))).",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Rebuild even when freeze_metadata.json already exists.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.sequential:
        max_workers = 1
    elif args.workers > 0:
        max_workers = args.workers
    else:
        max_workers = min(len(SYMBOLS), os.cpu_count() or 4)

    discovery_data = load_discovery_data()

    print("=" * 74)
    print("  Phase 3E Stage 2 — Phase 3A Evaluation Freeze")
    print("  (CPU-bound: evaluate_candidate + canonical_json_bytes)")
    print(f"  Mode:   {'SEQUENTIAL' if args.sequential else 'PARALLEL'}"
          f"{'' if args.sequential else f' ({max_workers} workers)'}")
    print(f"  Resume: {'DISABLED (--force)' if args.force else 'enabled (skip existing freezes)'}")
    print("=" * 74)
    print(f"  Boundary:       {BOUNDARY_TS.isoformat()}")
    print(f"  Symbols:        {', '.join(SYMBOLS)}")
    print(f"  Discovery data: {len(discovery_data)} symbols loaded")
    print(f"  Bundles dir:    {BUNDLES_DIR}")
    print(f"  Output dir:     {OUTPUT_DIR}")
    print()

    results: list[dict] = []
    failures: list[tuple[str, Exception]] = []
    all_ok = True

    if max_workers == 1:
        for i, symbol in enumerate(SYMBOLS):
            try:
                summary = process_symbol(symbol, discovery_data, force=args.force)
            except Exception as exc:
                print(f"  [{symbol:6s}] FAILED: {exc}  "
                      f"— {len(SYMBOLS) - i - 1} remaining")
                failures.append((symbol, exc))
                all_ok = False
                continue
            if summary is not None:
                results.append(summary)
            _print_symbol_result(
                symbol, summary, remaining=len(SYMBOLS) - i - 1
            )
    else:
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol: dict[concurrent.futures.Future, str] = {}
            for symbol in SYMBOLS:
                fut = executor.submit(
                    process_symbol, symbol, discovery_data, force=args.force
                )
                future_to_symbol[fut] = symbol

            remaining = len(future_to_symbol)
            for fut in concurrent.futures.as_completed(future_to_symbol):
                symbol = future_to_symbol[fut]
                remaining -= 1
                try:
                    summary = fut.result()
                except Exception as exc:
                    print(f"  [{symbol:6s}] FAILED: {exc}  — {remaining} remaining")
                    failures.append((symbol, exc))
                    all_ok = False
                    continue
            if summary is not None:
                results.append(summary)
            _print_symbol_result(symbol, summary, remaining=remaining)

    print()
    print("=" * 74)
    frozen_new = sum(1 for r in results if r.get("status") == "frozen")
    frozen_resumed = sum(1 for r in results if r.get("status") == "skipped_existing")
    skipped_none = len(SYMBOLS) - len(results) - len(failures)
    print(f"  Frozen (new):     {frozen_new}/{len(SYMBOLS)} symbols")
    print(f"  Frozen (resumed): {frozen_resumed}/{len(SYMBOLS)} symbols")
    print(f"  Skipped (none):   {skipped_none}/{len(SYMBOLS)} symbols")
    if failures:
        print(f"  Failures:         {len(failures)} symbols")
        for symbol, exc in failures:
            print(f"    - {symbol}: {exc}")
    if all_ok:
        print("  All OK: YES — every processable symbol was frozen without exceptions.")
    else:
        print(f"  Exceptions: {len(failures)} symbols raised; "
              "freezes still completed for the rest.")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 74)

    # Exit-code semantics: 0 when no worker raised; 1 when any worker raised.
    # A ``None`` return for a particular symbol (missing bundle or empty bars)
    # is a soft skip — it matches the original sequential behaviour.
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

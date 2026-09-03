"""Construct PointInTimeEvidenceBundles for all 13 IBKR pilot symbols.

Combines:
  - Normalized detection-context bars (via phase3a_freeze.evidence_adapter)
  - Scanner-snapshot metadata (float, price, volume from batch01_discovery_rows.json)
  - Catalyst evidence (NewsAPI, SEC EDGAR -- placeholder)
  - Structural validity metadata

Then runs the Phase 2D readiness evaluation on each bundle.

**Performance note:** ``build_point_in_time_evidence`` calls ``build_conflicts``
which does O(n^2) pair comparisons across all bar observations (~7M per
symbol with ~1 400 bars).  Symbols are processed in parallel by default.

Each bundle is written to ``build/acquisition/evidence-bundles/`` immediately
after construction so progress is never lost.  Re-run to resume without
reprocessing completed symbols.

Outcome-blind: no forward bars, no outcome data.

Usage (from repository root)::

    # Parallel (default — uses all CPU cores)
    python scripts/acquisition/build_evidence_bundles.py

    # Sequential (original behaviour)
    python scripts/acquisition/build_evidence_bundles.py --sequential

    # Control parallelism
    python scripts/acquisition/build_evidence_bundles.py --workers 4
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import io
import json
import os
import time as time_module
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from squeeze_core.contracts import (
    AssetClass, DataFreshness, EventType, IngestionMethod,
    MarketSession, Observation, ObservationKind,
    PayloadType, Provenance, Quality, QualityState,
    EntitlementState,
)
from squeeze_core.contracts.payloads import (
    MarketSnapshotPayload,
)
from squeeze_core.evidence.builder import build_point_in_time_evidence
from squeeze_core.evidence.models import CoverageDomain
from squeeze_core.evidence.policy import PointInTimeEvidencePolicy
from squeeze_core.readiness.coverage import build_domain_coverage_snapshot

UTC = timezone.utc

REPO_ROOT = Path(__file__).resolve().parents[2]

# Primary exchanges for each symbol, from Batch 05 contract resolution.
PRIMARY_EXCHANGE: dict[str, str] = {
    "XNCR": "NASDAQ", "PESI": "NASDAQ", "SLS": "NASDAQ", "ZNTL": "NASDAQ",
    "GPRE": "NASDAQ", "SSPC": "BATS", "LBGJ": "NASDAQ", "TRVI": "NASDAQ",
    "LMNX": "NASDAQ", "MGNX": "NASDAQ", "BHVN": "NYSE", "OBE": "AMEX", "AVTX": "NASDAQ",
}
SYMBOLS = sorted(PRIMARY_EXCHANGE.keys())

# Frozen boundary timestamp (all 13 symbols share this detection time).
BOUNDARY_TS = datetime(2026, 7, 18, 13, 37, 55, 17661, tzinfo=UTC)
RETRIEVAL_TS = datetime(2026, 7, 18, 13, 38, 0, tzinfo=UTC)

# Paths
RAW_DIR = REPO_ROOT / "intake" / "local-bars" / "ibkr-batch-05" / "raw"
DISCOVERY_PATH = (
    REPO_ROOT / "intake" / "batches" / "phase-3d-historical-source-collection-01"
    / "normalized" / "batch01_discovery_rows.json"
)
BUILD_DIR = REPO_ROOT / "build" / "acquisition" / "evidence-bundles"


def _serialisable(obj) -> object:
    """Recurse through a Pydantic / dataclass tree to plain dicts + primitives."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return _serialisable(obj.model_dump())
    if isinstance(obj, dict):
        return {k: _serialisable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_serialisable(item) for item in obj]
    if isinstance(obj, set):
        return sorted(_serialisable(item) for item in obj)
    if isinstance(obj, bytes):
        return obj.hex()
    return str(obj)


def load_discovery_data() -> dict[str, dict]:
    """Load scanner-snapshot metadata for each symbol."""
    data = json.loads(DISCOVERY_PATH.read_bytes())
    by_symbol: dict[str, dict] = {}
    for row in data["rows"]:
        by_symbol[row["ticker"]] = row["detection_time_evidence"]
    return by_symbol


def build_market_snapshot_observation(
    symbol: str, evidence: dict, index: int
) -> Observation:
    """Create a MARKET_SNAPSHOT Observation from scanner snapshot evidence."""
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
    """Load detection-context bars as Observations using the Phase 3A freeze adapter."""
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


def try_load_catalyst_evidence(symbol: str) -> tuple[Observation, ...]:
    """Attempt to load catalyst evidence (NewsAPI, SEC EDGAR).

    Returns empty tuple when not available (offline mode).
    NewsAPI and SEC EDGAR require online provider access which is not available
    in this outcome-blind offline pipeline. Catalyst evidence acquisition will
    be performed in a separate step with the existing adapter infrastructure
    (squeeze_core.adapters.news, squeeze_core.adapters.sec_edgar).
    """
    return ()


def readiness_summary(symbol: str, bundle) -> dict:
    """Phase 2D readiness summary for one bundle."""
    requested = (
        CoverageDomain.MARKET_BARS,
        CoverageDomain.CANDIDATE_SNAPSHOT,
        CoverageDomain.NEWS,
        CoverageDomain.SEC_FILINGS,
    )
    coverage = build_domain_coverage_snapshot(bundle, requested_domains=requested)

    return {
        "symbol": symbol,
        "bundle_id": bundle.bundle_id,
        "observation_count": len(bundle.observations),
        "included_count": bundle.completeness_summary.included_observation_count,
        "excluded_count": bundle.completeness_summary.excluded_observation_count,
        "present_domains": [
            (sc.domain.value, sc.state.value) for sc in bundle.source_coverage
        ],
        "missing_domains": [
            sc.domain.value for sc in bundle.source_coverage
            if sc.state.value == "MISSING"
        ],
        "coverage": {
            "present": [d.value for d in coverage.present_domains],
            "missing": [d.value for d in coverage.missing_domains],
        },
        "freshness": _serialisable(bundle.freshness_summary),
        "diagnostic_count": len(bundle.diagnostics),
    }


def process_symbol(
    symbol: str,
    discovery_data: dict[str, dict],
    *,
    force: bool = False,
) -> dict | None:
    """Build one evidence bundle, write it to disk, and return the readiness summary.

    Also writes ``build-log.txt`` (same text as printed to stdout) and
    ``build-metadata.json`` with per-phase timing breakdown.
    """
    build_dir = BUILD_DIR / symbol
    bundle_path = build_dir / "bundle.json"
    summary_path = build_dir / "summary.json"
    metadata_path = build_dir / "build-metadata.json"

    # Capture all stdout during this call so it can be written to build-log.txt.
    _stdout_capture = io.StringIO()

    def _p(*args, **kwargs):
        """print() wrapper that flushes reliably for both real and captured stdout."""
        kwargs.setdefault("flush", True)
        print(*args, **kwargs)

    with contextlib.redirect_stdout(_stdout_capture):
        # Resume check -- skip if already complete.
        if not force and bundle_path.exists() and summary_path.exists():
            summary = json.loads(summary_path.read_bytes())
            _p(f"  [{symbol:6s}] SKIP (already built: {summary.get('bundle_id', '?')})")
            # Flush captured output to build-log.txt before returning.
            build_dir.mkdir(parents=True, exist_ok=True)
            (build_dir / "build-log.txt").write_text(_stdout_capture.getvalue(), encoding="utf-8")
            return summary

        t_start = time_module.time()
        phases: dict[str, float] = {}

        _p(f"  [{symbol:6s}] Loading bars ... ", end="")
        bar_observations = load_bars(symbol)
        if not bar_observations:
            _p("NO BARS -- skipped")
            build_dir.mkdir(parents=True, exist_ok=True)
            (build_dir / "build-log.txt").write_text(_stdout_capture.getvalue(), encoding="utf-8")
            (build_dir / "build-metadata.json").write_text(
                json.dumps({
                    "symbol": symbol,
                    "built_at": datetime.now(UTC).isoformat(),
                    "status": "skipped_no_bars",
                }, indent=2),
                encoding="utf-8",
            )
            return None

        phases["load_bars_s"] = time_module.time() - t_start

        evidence = discovery_data.get(symbol, {})
        snapshot = build_market_snapshot_observation(symbol, evidence, 1)
        catalyst = try_load_catalyst_evidence(symbol)
        observations = bar_observations + (snapshot,) + catalyst

        _p(f"{len(bar_observations)} bars, building PITE bundle ... ", end="")

        as_of = max(BOUNDARY_TS, RETRIEVAL_TS)
        policy = PointInTimeEvidencePolicy(
            as_of=as_of,
            maximum_future_skew_ms=60_000,
            allow_stale=True,
            allow_delayed=True,
            allow_unknown_freshness=True,
            include_market_bars_domain=True,
        )

        t_build_start = time_module.time()
        bundle = build_point_in_time_evidence(
            symbol=symbol,
            observations=observations,
            policy=policy,
        )
        phases["build_bundle_s"] = time_module.time() - t_build_start

        _p("readiness ... ", end="")
        summary = readiness_summary(symbol, bundle)
        t_done = time_module.time()
        phases["total_s"] = t_done - t_start

        build_dir.mkdir(parents=True, exist_ok=True)

        t_ser_start = time_module.time()
        bundle_path.write_text(
            json.dumps(_serialisable(bundle.model_dump()), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        summary_path.write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        metadata_path.write_text(
            json.dumps({
                "symbol": symbol,
                "built_at": datetime.now(UTC).isoformat(),
                "elapsed_s": round(t_done - t_start, 1),
                "phases": {k: round(v, 1) for k, v in phases.items()},
                "bar_count": len(bar_observations),
                "included_count": bundle.completeness_summary.included_observation_count,
                "excluded_count": bundle.completeness_summary.excluded_observation_count,
                "conflict_count": len(bundle.conflicts),
                "diagnostic_count": len(bundle.diagnostics),
            }, indent=2),
            encoding="utf-8",
        )
        phases["serialize_s"] = time_module.time() - t_ser_start

        _p(f"done ({t_done - t_start:.1f}s)")
        _p(f"         Bundle: {bundle.bundle_id}")
        _p(f"         Observations: {bundle.completeness_summary.included_observation_count} "
           f"included / {bundle.completeness_summary.excluded_observation_count} excluded")
        present = [d for d in bundle.source_coverage if d.state.value == "PRESENT"]
        missing = [d for d in bundle.source_coverage if d.state.value == "MISSING"]
        if present:
            _p(f"         Present domains: {', '.join(d.domain.value for d in present)}")
        if missing:
            _p(f"         Missing domains: {', '.join(d.domain.value for d in missing)}")
        fresh = bundle.freshness_summary
        _p(f"         Freshness: {fresh.historical_count} historical, "
           f"{fresh.live_count} live, {fresh.delayed_count} delayed, "
           f"{fresh.stale_count} stale")
        _p(f"         Phases: load={phases.get('load_bars_s', 0):.1f}s "
           f"build={phases.get('build_bundle_s', 0):.1f}s "
           f"serialize={phases.get('serialize_s', 0):.1f}s")
        _p(f"         Written to: {build_dir}")

        # Write build-log.txt with captured output.
        (build_dir / "build-log.txt").write_text(_stdout_capture.getvalue(), encoding="utf-8")

    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Construct evidence bundles for all 13 IBKR pilot symbols."
    )
    parser.add_argument(
        "--sequential", action="store_true",
        help="Run sequentially (one symbol at a time). Default: parallel."
    )
    parser.add_argument(
        "--workers", type=int, default=0,
        help="Number of parallel workers (default: CPU count, capped at symbol count)."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    discovery_data = load_discovery_data()
    results: list[dict] = []
    all_ok = True

    max_workers: int | None
    if args.sequential:
        max_workers = 1
    elif args.workers > 0:
        max_workers = args.workers
    else:
        max_workers = min(len(SYMBOLS), os.cpu_count() or 4)

    print("=" * 74)
    print("  Phase 3E Stage 1 - Evidence Bundle Construction")
    print("  (O(n^2) conflict detection — expect ~30-60s per symbol)")
    print(f"  Mode: {'SEQUENTIAL' if args.sequential else 'PARALLEL'}"
          f"{'' if args.sequential else f' ({max_workers} workers)'}")
    print("  Re-run to resume without reprocessing completed symbols.")
    print("=" * 74)
    print(f"  Boundary:         {BOUNDARY_TS.isoformat()}")
    print(f"  Symbols:          {', '.join(SYMBOLS)}")
    print(f"  Discovery data:   {len(discovery_data)} symbols loaded")
    print(f"  Output directory: {BUILD_DIR}")
    print()

    if args.sequential or max_workers == 1:
        # ── Sequential mode (original behaviour, one symbol at a time) ──
        for symbol in SYMBOLS:
            summary = process_symbol(symbol, discovery_data)
            if summary is None:
                all_ok = False
            else:
                results.append(summary)
            print()
    else:
        # ── Parallel mode ──
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol: dict[concurrent.futures.Future, str] = {}
            for symbol in SYMBOLS:
                future = executor.submit(process_symbol, symbol, discovery_data)
                future_to_symbol[future] = symbol

            remaining = len(future_to_symbol)
            for future in concurrent.futures.as_completed(future_to_symbol):
                remaining -= 1
                symbol = future_to_symbol[future]
                try:
                    summary = future.result()
                    if summary is None:
                        all_ok = False
                        print(f"  [{symbol:6s}] SKIPPED (no bars)  — {remaining} remaining")
                    else:
                        results.append(summary)
                        inc = summary.get("included_count", 0)
                        exc = summary.get("excluded_count", 0)
                        doms = ", ".join(
                            d for d, _ in summary.get("present_domains", [])
                        )
                        print(f"  [{symbol:6s}] DONE  — {inc} incl / {exc} excl"
                              f"  — {doms}"
                              f"  — {remaining} remaining")
                except Exception as exc:
                    print(f"  [{symbol:6s}] FAILED: {exc}  — {remaining} remaining")
                    all_ok = False

        print()

    print("=" * 74)
    ok_count = len(results)
    print(f"  Summary: {ok_count}/{len(SYMBOLS)} bundles built")
    if ok_count == len(SYMBOLS):
        print("  All evidence bundles constructed successfully.")
        print("  Ready for Phase 3A evaluation pipeline.")
    else:
        print(f"  {len(SYMBOLS) - ok_count} symbols were skipped (no bars found).")
    print(f"  Output: {BUILD_DIR}")
    print("=" * 74)

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Regenerates tests/fixtures/metrics/expected_phase_2a_metric_metadata.json.

Not part of the runtime package. Builds the sixteen required Phase 2A anchor
results (handoff section 34) directly through squeeze_core.metrics, hashes each
with the same canonical_hash used everywhere else in the repository, and writes
the result set plus the raw CLI-output hash to the metadata file.

Deterministic: no wall clock, no randomness. Run with the project's .venv:

    .venv/Scripts/python.exe scripts/generate_phase_2a_anchors.py
"""

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from squeeze_core.adapters import AdapterContext  # noqa: E402
from squeeze_core.adapters.market_bars import BarInterval, normalize_market_bar_record  # noqa: E402
from squeeze_core.contracts import AssetClass, EntitlementState, IngestionMethod  # noqa: E402
from squeeze_core.metrics import (  # noqa: E402
    GapRequest,
    MetricName,
    RangeRequest,
    ReturnRequest,
    TrailingWindow,
    VolumeBaselineRequest,
    build_gap_result,
    build_range_result,
    build_return_result,
    build_volume_baseline_result,
    metric_result_hash,
    serialize_metric_result,
)
from squeeze_core.serialization import canonical_hash  # noqa: E402

AS_OF = datetime(2026, 2, 5, 0, 0, tzinfo=UTC)
OUT_PATH = ROOT / "tests" / "fixtures" / "metrics" / "expected_phase_2a_metric_metadata.json"
CLI_BARS = ROOT / "tests" / "fixtures" / "metrics" / "cli_demo_bars.jsonl"
CLI_SPEC = ROOT / "tests" / "fixtures" / "metrics" / "phase_2a_metric_cases.json"


def _context(at: str, provider: str = "market-bars-offline"):
    return AdapterContext(
        ingested_at=datetime.fromisoformat(at.replace("Z", "+00:00")),
        source_timezone=None,
        provider=provider,
        adapter_version="1.0.0",
        normalization_version="metrics-fixture-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="phase-2a-anchor-fixture",
    )


def _bar_record(**overrides):
    values = {
        "source_record_id": "anchor-bar-1",
        "provider_schema": "MARKET_BAR_V1",
        "record_type": "MARKET_BAR",
        "fixture_origin": "SYNTHETIC_EDGE_CASE",
        "provider": "ALPACA_SHAPED",
        "provider_record_id": None,
        "symbol": "TESTA",
        "asset_class": "EQUITY",
        "exchange": "XNAS",
        "interval": "1_DAY",
        "bar_start": "2026-01-15T00:00:00-05:00",
        "bar_end": "2026-01-16T00:00:00-05:00",
        "open": "1.00",
        "high": "1000.00",
        "low": "0.01",
        "close": "10.25",
        "volume": "100000",
        "trade_count": "500",
        "vwap": "10.20",
        "volume_unit": "SHARES",
        "session": "REGULAR",
        "session_date": "2026-01-15",
        "timezone": "America/New_York",
        "status": "COMPLETED",
        "publication_timestamp": "2026-01-15T16:01:00-05:00",
    }
    values.update(overrides)
    return values


def _make_bar(*, ingested_at="2026-01-20T22:00:00Z", **overrides):
    result = normalize_market_bar_record(_bar_record(**overrides), _context(ingested_at))
    assert result.accepted, result.rejection
    return result.observations[0]


def _daily(day, **overrides):
    values = {
        "source_record_id": f"anchor-bar-{day}",
        "bar_start": f"2026-01-{day:02d}T00:00:00-05:00",
        "bar_end": f"2026-01-{day + 1:02d}T00:00:00-05:00",
        "session_date": f"2026-01-{day:02d}",
        "publication_timestamp": f"2026-01-{day:02d}T16:01:00-05:00",
        "ingested_at": f"2026-01-{day:02d}T21:02:00Z",
    }
    values.update(overrides)
    return _make_bar(**values)


def _boundary(bar):
    metadata = bar.provenance.provider_metadata
    return metadata["bar_start"], metadata["bar_end"]


def build_anchor_results() -> dict[str, object]:
    results: dict[str, object] = {}

    # 1-3: returns
    start = _daily(15, close="10.00")
    end_up = _daily(16, close="12.50")
    end_down = _daily(16, close="8.00", source_record_id="anchor-bar-16-down")
    s0, s1 = _boundary(start)
    e0, e1 = _boundary(end_up)
    d0, d1 = _boundary(end_down)

    results["positive_absolute_return"] = build_return_result(
        [start, end_up],
        ReturnRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY,
            start_bar_start=s0, start_bar_end=s1, end_bar_start=e0, end_bar_end=e1,
        ),
        MetricName.ABSOLUTE_RETURN,
    )
    results["positive_percentage_return"] = build_return_result(
        [start, end_up],
        ReturnRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY,
            start_bar_start=s0, start_bar_end=s1, end_bar_start=e0, end_bar_end=e1,
        ),
        MetricName.PERCENTAGE_RETURN,
    )
    results["negative_percentage_return"] = build_return_result(
        [start, end_down],
        ReturnRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY,
            start_bar_start=s0, start_bar_end=s1, end_bar_start=d0, end_bar_end=d1,
        ),
        MetricName.PERCENTAGE_RETURN,
    )

    # 4-5: gaps
    prior = _daily(17, close="10.00", source_record_id="anchor-bar-17-prior")
    current = _daily(18, open="10.50", source_record_id="anchor-bar-18-current")
    p0, p1 = _boundary(prior)
    c0, c1 = _boundary(current)
    results["positive_absolute_gap"] = build_gap_result(
        [prior, current],
        GapRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY,
            prior_bar_start=p0, prior_bar_end=p1, current_bar_start=c0, current_bar_end=c1,
        ),
        MetricName.ABSOLUTE_SESSION_GAP,
    )
    results["positive_percentage_gap"] = build_gap_result(
        [prior, current],
        GapRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY,
            prior_bar_start=p0, prior_bar_end=p1, current_bar_start=c0, current_bar_end=c1,
        ),
        MetricName.PERCENTAGE_SESSION_GAP,
    )

    # 6-7: ranges
    range_bar = _daily(19, high="11.00", low="10.00", open="10.20", close="10.80", source_record_id="anchor-bar-19-range")
    r0, r1 = _boundary(range_bar)
    results["absolute_range"] = build_range_result(
        [range_bar],
        RangeRequest(symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY, target_bar_start=r0, target_bar_end=r1),
        MetricName.ABSOLUTE_BAR_RANGE,
    )
    results["percentage_range"] = build_range_result(
        [range_bar],
        RangeRequest(symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY, target_bar_start=r0, target_bar_end=r1),
        MetricName.PERCENTAGE_BAR_RANGE,
    )

    # 8-9: volume baselines
    vol_bars = [_daily(d, volume=str(v), source_record_id=f"anchor-vol-{d}") for d, v in [(20, 1000), (21, 2000), (22, 3000), (23, 4000), (24, 5000)]]
    vol_target = _daily(25, volume="9999", source_record_id="anchor-vol-target")
    vt0, vt1 = _boundary(vol_target)
    results["three_sample_volume_baseline"] = build_volume_baseline_result(
        [*vol_bars, vol_target],
        VolumeBaselineRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY,
            target_bar_start=vt0, target_bar_end=vt1, window=TrailingWindow(requested_count=3, minimum_samples=3),
        ),
    )
    results["five_sample_volume_baseline"] = build_volume_baseline_result(
        [*vol_bars, vol_target],
        VolumeBaselineRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval=BarInterval.ONE_DAY,
            target_bar_start=vt0, target_bar_end=vt1, window=TrailingWindow(requested_count=5, minimum_samples=5),
        ),
    )

    # 10-11: before/after correction
    corr_start = _daily(26, close="10.00", source_record_id="anchor-corr-start")
    corr_original = _daily(27, close="12.00", provider_record_id="anchor-corr-original", source_record_id="anchor-corr-orig-rec")
    corr_corrected = _daily(
        27, close="12.50", provider_record_id="anchor-corr-corrected", source_record_id="anchor-corr-corrected-rec",
        status="CORRECTED", revision_number=1, supersedes_provider_record_id="anchor-corr-original",
        publication_timestamp="2026-01-29T09:00:00-05:00", ingested_at="2026-01-29T09:05:00Z",
    )
    cs0, cs1 = _boundary(corr_start)
    co0, co1 = _boundary(corr_original)
    corr_observations = [corr_start, corr_original, corr_corrected]
    corr_request_kwargs = dict(
        symbol="TESTA", asset_class=AssetClass.EQUITY, source_interval=BarInterval.ONE_DAY,
        start_bar_start=cs0, start_bar_end=cs1, end_bar_start=co0, end_bar_end=co1,
    )
    results["before_correction_metric_result"] = build_return_result(
        corr_observations,
        ReturnRequest(as_of=datetime(2026, 1, 28, 0, 0, tzinfo=UTC), **corr_request_kwargs),
        MetricName.ABSOLUTE_RETURN,
    )
    results["after_correction_metric_result"] = build_return_result(
        corr_observations,
        ReturnRequest(as_of=AS_OF, **corr_request_kwargs),
        MetricName.ABSOLUTE_RETURN,
    )

    # 12-13: before/after cancellation
    cancel_start = _daily(28, close="10.00", source_record_id="anchor-cancel-start")
    cancel_original = _daily(29, close="12.00", provider_record_id="anchor-cancel-original", source_record_id="anchor-cancel-orig-rec")
    cancel_cancelled = _daily(
        29, close="12.00", provider_record_id="anchor-cancel-cancelled", source_record_id="anchor-cancel-cancelled-rec",
        status="CANCELLED", revision_number=1, supersedes_provider_record_id="anchor-cancel-original",
        publication_timestamp="2026-01-31T09:00:00-05:00", ingested_at="2026-01-31T09:05:00Z",
    )
    ccs0, ccs1 = _boundary(cancel_start)
    cco0, cco1 = _boundary(cancel_original)
    cancel_observations = [cancel_start, cancel_original, cancel_cancelled]
    cancel_request_kwargs = dict(
        symbol="TESTA", asset_class=AssetClass.EQUITY, source_interval=BarInterval.ONE_DAY,
        start_bar_start=ccs0, start_bar_end=ccs1, end_bar_start=cco0, end_bar_end=cco1,
    )
    results["before_cancellation_metric_result"] = build_return_result(
        cancel_observations,
        ReturnRequest(as_of=datetime(2026, 1, 30, 0, 0, tzinfo=UTC), **cancel_request_kwargs),
        MetricName.ABSOLUTE_RETURN,
    )
    results["after_cancellation_metric_result"] = build_return_result(
        cancel_observations,
        ReturnRequest(as_of=AS_OF, **cancel_request_kwargs),
        MetricName.ABSOLUTE_RETURN,
    )

    return results


def main() -> None:
    results = build_anchor_results()
    anchors: dict[str, str] = {name: metric_result_hash(result) for name, result in results.items()}

    ordered_names = sorted(results)
    collection = [results[name] for name in ordered_names]
    anchors["mixed_phase_2a_metric_output_sha256"] = canonical_hash(list(collection))
    anchors["serialized_final_metric_collection_sha256"] = hashlib.sha256(
        b"[" + b",".join(serialize_metric_result(item) for item in collection) + b"]"
    ).hexdigest()

    cli = subprocess.run(
        [
            sys.executable, "-m", "squeeze_core", "build-market-metrics",
            "--input", str(CLI_BARS), "--symbol", "TESTA", "--as-of", "2026-01-20T22:00:00Z",
            "--spec", str(CLI_SPEC),
        ],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    anchors["cli_output_sha256"] = hashlib.sha256(cli.stdout.encode("utf-8")).hexdigest()

    metadata = {
        "schema_version": "1.0.0",
        "description": "Phase 2A anchor hashes (handoff section 34). Each *_sha256 value is canonical_hash() of the named MetricResult, except mixed_phase_2a_metric_output_sha256 (canonical_hash of the sorted-by-name result list), serialized_final_metric_collection_sha256 (sha256 of the concatenated per-result canonical JSON bytes), and cli_output_sha256 (sha256 of build-market-metrics stdout for tests/fixtures/metrics/cli_demo_bars.jsonl + phase_2a_metric_cases.json at as_of=2026-01-20T22:00:00Z).",
        "anchor_result_order": ordered_names,
        "anchors": dict(sorted(anchors.items())),
    }
    OUT_PATH.write_text(json.dumps(metadata, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()

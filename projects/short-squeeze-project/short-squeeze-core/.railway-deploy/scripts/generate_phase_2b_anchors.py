"""Regenerates tests/fixtures/metrics/expected_phase_2b_metric_metadata.json.

Not part of the runtime package. Builds the twenty required Phase 2B anchor
results (handoff section 28) directly through squeeze_core.metrics, hashes each
with the same canonical_hash used everywhere else in the repository, and writes
the result set plus the raw CLI-output hash to the metadata file. Mirrors
scripts/generate_phase_2a_anchors.py's structure and conventions exactly.

Deterministic: no wall clock, no randomness. Run with the project's .venv:

    .venv/Scripts/python.exe scripts/generate_phase_2b_anchors.py
"""

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from squeeze_core.adapters import AdapterContext  # noqa: E402
from squeeze_core.adapters.market_bars import normalize_market_bar_record  # noqa: E402
from squeeze_core.contracts import AssetClass, EntitlementState, IngestionMethod  # noqa: E402
from squeeze_core.metrics import (  # noqa: E402
    RelativeVolumeRequest,
    ReturnBaselineRequest,
    ReturnCountWindow,
    ReturnZScoreRequest,
    TrailingWindow,
    VolumeZScoreRequest,
    build_mean_percentage_return_baseline_result,
    build_percentage_return_standard_deviation_baseline_result,
    build_percentage_return_z_score_result,
    build_relative_volume_result,
    build_volume_percent_deviation_result,
    build_volume_z_score_result,
    normalized_metric_result_hash,
    serialize_normalized_metric_result,
)
from squeeze_core.serialization import canonical_hash  # noqa: E402

AS_OF = datetime(2026, 2, 10, 0, 0, tzinfo=UTC)
OUT_PATH = ROOT / "tests" / "fixtures" / "metrics" / "expected_phase_2b_metric_metadata.json"
CLI_BARS = ROOT / "tests" / "fixtures" / "metrics" / "phase_2b_cli_demo_bars.jsonl"
CLI_SPEC = ROOT / "tests" / "fixtures" / "metrics" / "phase_2b_normalized_metric_cases.json"


def _context(at: str, provider: str = "market-bars-offline"):
    return AdapterContext(
        ingested_at=datetime.fromisoformat(at.replace("Z", "+00:00")),
        source_timezone=None,
        provider=provider,
        adapter_version="1.0.0",
        normalization_version="metrics-fixture-v1",
        entitlement_status=EntitlementState.NOT_APPLICABLE,
        collection_method=IngestionMethod.LOADED_FIXTURE,
        source_endpoint_name="phase-2b-anchor-fixture",
    )


def _bar_record(**overrides):
    values = {
        "source_record_id": "anchor2b-bar-1",
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


def _make_bar(*, ingested_at="2026-02-01T22:00:00Z", **overrides):
    result = normalize_market_bar_record(_bar_record(**overrides), _context(ingested_at))
    assert result.accepted, result.rejection
    return result.observations[0]


_EPOCH = datetime(2026, 1, 1)


def _day_date(day: int) -> datetime:
    return _EPOCH + timedelta(days=day - 1)


def _daily(day, close="10.00", volume="1000", **overrides):
    start = _day_date(day)
    end = start + timedelta(days=1)
    values = {
        "source_record_id": f"anchor2b-bar-{day}",
        "bar_start": start.strftime("%Y-%m-%dT00:00:00-05:00"),
        "bar_end": end.strftime("%Y-%m-%dT00:00:00-05:00"),
        "session_date": start.strftime("%Y-%m-%d"),
        "publication_timestamp": start.strftime("%Y-%m-%dT16:01:00-05:00"),
        "ingested_at": start.strftime("%Y-%m-%dT21:02:00Z"),
        "open": close,
        "close": close,
        "volume": volume,
    }
    values.update(overrides)
    return _make_bar(**values)


def _boundary(bar):
    metadata = bar.provenance.provider_metadata
    return metadata["bar_start"], metadata["bar_end"]


def build_anchor_results() -> dict[str, object]:
    results: dict[str, object] = {}

    # 1-4: relative volume
    baseline_bars = [_daily(d, volume=str(v)) for d, v in [(10, 1000), (11, 1000), (12, 1000)]]
    window = TrailingWindow(requested_count=3, minimum_samples=3)

    above_target = _daily(13, volume="3000")
    t0, t1 = _boundary(above_target)
    results["relative_volume_above_baseline"] = build_relative_volume_result(
        [*baseline_bars, above_target],
        RelativeVolumeRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval="1_DAY",
            target_bar_start=t0, target_bar_end=t1, window=window,
        ),
    )

    below_target = _daily(13, volume="500", source_record_id="anchor2b-bar-13-below")
    b0, b1 = _boundary(below_target)
    results["relative_volume_below_baseline"] = build_relative_volume_result(
        [*baseline_bars, below_target],
        RelativeVolumeRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval="1_DAY",
            target_bar_start=b0, target_bar_end=b1, window=window,
        ),
    )

    equal_target = _daily(13, volume="1000", source_record_id="anchor2b-bar-13-equal")
    e0, e1 = _boundary(equal_target)
    results["relative_volume_equal_baseline"] = build_relative_volume_result(
        [*baseline_bars, equal_target],
        RelativeVolumeRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval="1_DAY",
            target_bar_start=e0, target_bar_end=e1, window=window,
        ),
    )

    zero_target = _daily(13, volume="0", source_record_id="anchor2b-bar-13-zero")
    z0, z1 = _boundary(zero_target)
    results["zero_target_relative_volume"] = build_relative_volume_result(
        [*baseline_bars, zero_target],
        RelativeVolumeRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval="1_DAY",
            target_bar_start=z0, target_bar_end=z1, window=window,
        ),
    )

    # 5-6: volume percent deviation
    results["positive_volume_percent_deviation"] = build_volume_percent_deviation_result(
        [*baseline_bars, above_target],
        RelativeVolumeRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval="1_DAY",
            target_bar_start=t0, target_bar_end=t1, window=window,
        ),
    )
    results["negative_volume_percent_deviation"] = build_volume_percent_deviation_result(
        [*baseline_bars, below_target],
        RelativeVolumeRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval="1_DAY",
            target_bar_start=b0, target_bar_end=b1, window=window,
        ),
    )

    # 7-9: volume z-score. Population [2,4,4,4,5,5,7,9]: mean=5, variance=4, stddev=2.
    zscore_bars = [_daily(d, volume=str(v)) for d, v in zip(range(20, 28), (2, 4, 4, 4, 5, 5, 7, 9))]
    z_window = TrailingWindow(requested_count=8, minimum_samples=2)

    positive_z_target = _daily(28, volume="9", source_record_id="anchor2b-vz-positive")
    pz0, pz1 = _boundary(positive_z_target)
    results["positive_volume_z_score"] = build_volume_z_score_result(
        [*zscore_bars, positive_z_target],
        VolumeZScoreRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval="1_DAY",
            target_bar_start=pz0, target_bar_end=pz1, window=z_window,
        ),
    )

    negative_z_target = _daily(28, volume="1", source_record_id="anchor2b-vz-negative")
    nz0, nz1 = _boundary(negative_z_target)
    results["negative_volume_z_score"] = build_volume_z_score_result(
        [*zscore_bars, negative_z_target],
        VolumeZScoreRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval="1_DAY",
            target_bar_start=nz0, target_bar_end=nz1, window=z_window,
        ),
    )

    zero_z_target = _daily(28, volume="5", source_record_id="anchor2b-vz-zero")
    zz0, zz1 = _boundary(zero_z_target)
    results["zero_volume_z_score"] = build_volume_z_score_result(
        [*zscore_bars, zero_z_target],
        VolumeZScoreRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval="1_DAY",
            target_bar_start=zz0, target_bar_end=zz1, window=z_window,
        ),
    )

    # 10-14: return baselines and return z-scores. Mixed history: +20%, -25% -> mean -2.5, std > 0.
    return_history = [
        _daily(30, close="10.00", source_record_id="anchor2b-ret-30"),
        _daily(31, close="12.00", source_record_id="anchor2b-ret-31"),
        _daily(32, close="9.00", source_record_id="anchor2b-ret-32"),
    ]
    return_window = ReturnCountWindow(requested_count=2, minimum_samples=2)
    baseline_target_start, _ = _boundary(_daily(33, close="9.00", source_record_id="anchor2b-ret-33-probe"))
    return_baseline_request = ReturnBaselineRequest(
        symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval="1_DAY",
        target_bar_start=baseline_target_start, window=return_window,
    )
    results["mean_percentage_return_baseline"] = build_mean_percentage_return_baseline_result(
        return_history, return_baseline_request
    )
    results["percentage_return_standard_deviation_baseline"] = (
        build_percentage_return_standard_deviation_baseline_result(return_history, return_baseline_request)
    )

    target_start_bar = _daily(33, close="9.00", source_record_id="anchor2b-ret-33")
    ts0, ts1 = _boundary(target_start_bar)

    positive_end = _daily(34, close="18.00", source_record_id="anchor2b-ret-34-positive")
    pe0, pe1 = _boundary(positive_end)
    results["positive_percentage_return_z_score"] = build_percentage_return_z_score_result(
        [*return_history, target_start_bar, positive_end],
        ReturnZScoreRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval="1_DAY",
            target_start_bar_start=ts0, target_start_bar_end=ts1,
            target_end_bar_start=pe0, target_end_bar_end=pe1, window=return_window,
        ),
    )

    negative_end = _daily(34, close="4.50", source_record_id="anchor2b-ret-34-negative")
    ne0, ne1 = _boundary(negative_end)
    results["negative_percentage_return_z_score"] = build_percentage_return_z_score_result(
        [*return_history, target_start_bar, negative_end],
        ReturnZScoreRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval="1_DAY",
            target_start_bar_start=ts0, target_start_bar_end=ts1,
            target_end_bar_start=ne0, target_end_bar_end=ne1, window=return_window,
        ),
    )

    zero_end = _daily(34, close="8.775", source_record_id="anchor2b-ret-34-zero")
    ze0, ze1 = _boundary(zero_end)
    results["zero_percentage_return_z_score"] = build_percentage_return_z_score_result(
        [*return_history, target_start_bar, zero_end],
        ReturnZScoreRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF, source_interval="1_DAY",
            target_start_bar_start=ts0, target_start_bar_end=ts1,
            target_end_bar_start=ze0, target_end_bar_end=ze1, window=return_window,
        ),
    )

    # 15-18: before/after correction and cancellation (relative volume, target bar). Reuses days
    # 1-4 -- safe, since this group's observations list is entirely independent of every other
    # group above (each build_* call only ever sees the bars explicitly passed to it).
    corr_baseline = [_daily(d, volume="1000", source_record_id=f"anchor2b-corr-base-{d}") for d in (1, 2, 3)]
    corr_original = _daily(4, volume="1000", provider_record_id="anchor2b-corr-original", source_record_id="anchor2b-corr-orig-rec")
    corr_receipt = _day_date(4) + timedelta(days=3)
    corr_corrected = _daily(
        4, volume="4000", provider_record_id="anchor2b-corr-corrected", source_record_id="anchor2b-corr-corrected-rec",
        status="CORRECTED", revision_number=1, supersedes_provider_record_id="anchor2b-corr-original",
        publication_timestamp=corr_receipt.strftime("%Y-%m-%dT09:00:00-05:00"),
        ingested_at=corr_receipt.strftime("%Y-%m-%dT09:05:00Z"),
    )
    cc0, cc1 = _boundary(corr_corrected)
    corr_observations = [*corr_baseline, corr_original, corr_corrected]
    corr_window = TrailingWindow(requested_count=3, minimum_samples=3)
    corr_before_as_of = corr_receipt - timedelta(days=1)
    results["before_correction_normalized_result"] = build_relative_volume_result(
        corr_observations,
        RelativeVolumeRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=corr_before_as_of.replace(tzinfo=UTC),
            source_interval="1_DAY", target_bar_start=cc0, target_bar_end=cc1, window=corr_window,
        ),
    )
    results["after_correction_normalized_result"] = build_relative_volume_result(
        corr_observations,
        RelativeVolumeRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF,
            source_interval="1_DAY", target_bar_start=cc0, target_bar_end=cc1, window=corr_window,
        ),
    )

    cancel_baseline = [_daily(d, volume="1000", source_record_id=f"anchor2b-cancel-base-{d}") for d in (1, 2, 3)]
    cancel_original = _daily(4, volume="2000", provider_record_id="anchor2b-cancel-original", source_record_id="anchor2b-cancel-orig-rec")
    cancel_receipt = _day_date(4) + timedelta(days=3)
    cancel_cancelled = _daily(
        4, volume="2000", provider_record_id="anchor2b-cancel-cancelled", source_record_id="anchor2b-cancel-cancelled-rec",
        status="CANCELLED", revision_number=1, supersedes_provider_record_id="anchor2b-cancel-original",
        publication_timestamp=cancel_receipt.strftime("%Y-%m-%dT09:00:00-05:00"),
        ingested_at=cancel_receipt.strftime("%Y-%m-%dT09:05:00Z"),
    )
    cx0, cx1 = _boundary(cancel_cancelled)
    cancel_observations = [*cancel_baseline, cancel_original, cancel_cancelled]
    cancel_before_as_of = cancel_receipt - timedelta(days=1)
    results["before_cancellation_normalized_result"] = build_relative_volume_result(
        cancel_observations,
        RelativeVolumeRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=cancel_before_as_of.replace(tzinfo=UTC),
            source_interval="1_DAY", target_bar_start=cx0, target_bar_end=cx1, window=corr_window,
        ),
    )
    results["after_cancellation_normalized_result"] = build_relative_volume_result(
        cancel_observations,
        RelativeVolumeRequest(
            symbol="TESTA", asset_class=AssetClass.EQUITY, as_of=AS_OF,
            source_interval="1_DAY", target_bar_start=cx0, target_bar_end=cx1, window=corr_window,
        ),
    )

    return results


def main() -> None:
    results = build_anchor_results()
    anchors: dict[str, str] = {name: normalized_metric_result_hash(result) for name, result in results.items()}

    ordered_names = sorted(results)
    collection = [results[name] for name in ordered_names]
    anchors["mixed_phase_2b_metric_output"] = canonical_hash(list(collection))
    anchors["serialized_phase_2b_metric_collection"] = hashlib.sha256(
        b"[" + b",".join(serialize_normalized_metric_result(item) for item in collection) + b"]"
    ).hexdigest()

    cli = subprocess.run(
        [
            sys.executable, "-m", "squeeze_core", "build-market-metrics",
            "--input", str(CLI_BARS), "--symbol", "TESTB", "--as-of", "2026-02-01T22:00:00Z",
            "--spec", str(CLI_SPEC),
        ],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    anchors["phase_2b_cli_output"] = hashlib.sha256(cli.stdout.encode("utf-8")).hexdigest()

    metadata = {
        "schema_version": "1.0.0",
        "description": "Phase 2B anchor hashes (handoff section 28). Each value is normalized_metric_result_hash() (canonical_hash of a NormalizedMetricResult), except mixed_phase_2b_metric_output (canonical_hash of the sorted-by-name result list), serialized_phase_2b_metric_collection (sha256 of the concatenated per-result canonical JSON bytes), and phase_2b_cli_output (sha256 of build-market-metrics stdout for tests/fixtures/metrics/phase_2b_cli_demo_bars.jsonl + phase_2b_normalized_metric_cases.json at as_of=2026-02-01T22:00:00Z). This is a Phase 2B-only anchor manifest, intentionally separate from tests/fixtures/compatibility/phase_1_anchor_manifest.json and tests/fixtures/metrics/expected_phase_2a_metric_metadata.json; neither of those files is written by this script.",
        "anchor_result_order": ordered_names,
        "anchors": dict(sorted(anchors.items())),
    }
    OUT_PATH.write_text(json.dumps(metadata, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()

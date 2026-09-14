"""Build REPLAY_LATENCY_BASELINE from fixture RT-01 workload and optional BUILD 07 replay."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from market_platform_foundation.clock import reset_clock_for_tests
from market_platform_foundation.rt01.collector import InMemoryTraceCollector
from market_platform_foundation.rt01.enums import SamplingMode
from market_platform_foundation.rt01.export import export_document
from market_platform_foundation.rt01.tracer import Tracer, configure_tracer
from market_platform_foundation.rt01.workloads import fixture_path, run_fixture_ingest_workload

from .exercise import derive_timestamp_exercise, validate_baseline_document
from .models import HotPathQualityCounters, ReplayLatencyBaselineDocument
from .quality_mapping import apply_finding_code, record_normalized_success
from .replay_aggregation import aggregate_replay_outputs
from .rt01_aggregation import aggregate_rt01_spans
from .stats import merge_presence


def fixture_sha256(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).digest()
    return digest.hex().upper()


def _merge_quality(left: HotPathQualityCounters, right: HotPathQualityCounters) -> HotPathQualityCounters:
    merged = left.to_dict()
    for key, value in right.to_dict().items():
        merged[key] = merged.get(key, 0) + value
    return HotPathQualityCounters(**merged)


def _optional_build_09_replay() -> tuple[Any, Any, Any] | tuple[None, None, None]:
    try:
        from market_platform_foundation.intelligence.normalization import (
            IngestionMode,
            NormalizationContext,
            require_normalized_event,
        )
        from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
        from market_platform_foundation.intelligence.quality import IntelligenceCapability
        from market_platform_foundation.intelligence.replay import (
            ReplayDecisionSchedule,
            ReplayPipelineConfig,
            ReplayRuntime,
            observed_replay_scenario,
        )
        from market_platform_foundation.intelligence.signals import SignalComputationRequest
        from market_platform_foundation.intelligence.snapshots import (
            SnapshotBuildRequest,
            SnapshotCompositionPolicy,
        )
        from tests.intelligence.routing_fixtures import T, WINDOW_NS, quality_decision
        from tests.intelligence.test_signal_integration import _moomoo_quote_fixture, _moomoo_trade_fixture
        from tests.intelligence.test_snapshot_fixtures import SCOPE
    except ImportError:
        return None, None, None

    ONE_SECOND = 1_000_000_000
    D1 = T + 4 * ONE_SECOND
    D2 = T + 8 * ONE_SECOND

    def _normalize(raw: dict[str, object], received_time_ns: int):
        return require_normalized_event(
            raw,
            context=NormalizationContext(
                received_time_ns=received_time_ns,
                ingestion_mode=IngestionMode.LIVE_OBSERVED,
            ),
            source_key="moomoo.capture",
        )

    quote_time = T + ONE_SECOND
    sell_time = T + 2 * ONE_SECOND
    buy_time = T + 6 * ONE_SECOND
    events = (
        _normalize(_moomoo_quote_fixture(quote_time), quote_time),
        _normalize(_moomoo_trade_fixture(sell_time, sequence=1, side="SELL", qty=100), sell_time),
        _normalize(_moomoo_trade_fixture(buy_time, sequence=2, side="BUY", qty=300), buy_time),
    )
    source = InMemoryIntelligenceRepository()
    for row in events:
        source.put_event(row)
    output = InMemoryIntelligenceRepository()
    config = ReplayPipelineConfig(
        snapshot_request=SnapshotBuildRequest(
            decision_time_ns=D1,
            scope=SCOPE,
            composition_policy=SnapshotCompositionPolicy(max_events=50, max_signals=5),
        ),
        signal_request=SignalComputationRequest(
            window_ns=WINDOW_NS,
            signal_types=frozenset({"net_signed_share"}),
            persist=True,
        ),
        quality_decisions=(
            quality_decision(
                IntelligenceCapability.QUOTES,
                IntelligenceCapability.TRADES,
                decision_time_ns=D1,
            ),
            quality_decision(
                IntelligenceCapability.QUOTES,
                IntelligenceCapability.TRADES,
                decision_time_ns=D2,
            ),
        ),
        enable_build_09=True,
        persist_outputs=True,
    )
    scenario = observed_replay_scenario(
        source_start_time_ns=T,
        source_end_time_ns=D2,
        decision_schedule=ReplayDecisionSchedule(decision_times_ns=(D1, D2)),
    )
    from .observer import HotPathTelemetryObserver

    observer = HotPathTelemetryObserver()
    result = ReplayRuntime(observer=observer).run(
        scenario,
        source,
        output_repository=output,
        pipeline_config=config,
    )
    return result, output, source


def build_replay_latency_baseline(
    *,
    include_build_09_replay: bool = True,
    repo_root: Path | None = None,
) -> ReplayLatencyBaselineDocument:
    """Measured fixture/replay baseline — not live-capture latency."""
    reset_clock_for_tests()
    path = fixture_path() if repo_root is None else repo_root / "tests" / "fixtures" / "market_data" / "moomoo" / "captured-aapl.jsonl"
    configure_tracer(Tracer(mode=SamplingMode.FULL, collector=InMemoryTraceCollector()))
    spans = run_fixture_ingest_workload()
    rt01 = aggregate_rt01_spans(spans)
    rt01_export = export_document(spans, metadata={"workload": "fixture_ingest"})

    presence = dict(rt01["timestamp_presence"])
    segments = dict(rt01["latency_segments_ns"])
    counters = HotPathQualityCounters(
        received=rt01.get("trace_count", 0),
        normalized=rt01.get("normalized_span_ok_count", 0),
    )
    replay_run_id: str | None = None
    if include_build_09_replay:
        replay_pair = _optional_build_09_replay()
        if replay_pair[0] is not None and replay_pair[1] is not None:
            result, output, source = replay_pair
            replay_run_id = result.run_id
            replay_agg = aggregate_replay_outputs(result, output, source_repository=source)
            for key, value in replay_agg["timestamp_presence"].items():
                presence[key] = merge_presence(presence.get(key, {"present_count": 0, "missing_count": 0}), value)
            segments.update(replay_agg["latency_segments_ns"])
            replay_counters = HotPathQualityCounters(**replay_agg["quality_counters"])
            counters = _merge_quality(counters, replay_counters)

    exercise = derive_timestamp_exercise(presence)
    document = ReplayLatencyBaselineDocument(
        schema_version="hot_path_telemetry.replay_latency_baseline/1.0.0",
        artifact_type="REPLAY_LATENCY_BASELINE",
        measurement_class="MEASURED_FIXTURE_REPLAY",
        fixture_path="tests/fixtures/market_data/moomoo/captured-aapl.jsonl",
        fixture_sha256=fixture_sha256(path),
        timestamp_exercise=exercise,
        timestamp_presence=presence,
        latency_segments_ns=segments,
        quality_counters=counters.to_dict(),
        rt01_span_count=len(spans),
        replay_run_id=replay_run_id,
        metadata={
            "rt01_export_span_count": rt01_export.get("span_count"),
            "clock_basis_processing": "process_monotonic_ns",
            "data_source": "FIXTURE_REPLAY",
        },
    )
    validate_baseline_document(document.to_dict())
    return document


__all__ = ["build_replay_latency_baseline", "fixture_sha256"]

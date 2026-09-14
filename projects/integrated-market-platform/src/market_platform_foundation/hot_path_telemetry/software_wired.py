"""Fixture/replay proof that production software paths emit hot-path clocks.

Cross-stage segment latencies that merge BUILD 09 detections or opportunity/UI clocks
onto the first ingress row (via ``_first_router_row`` / ``_first_detected_row``) are
**non-authoritative**: they only prove the software path *emits* timestamps, not that
those stages share one correlation id or clock domain. Missing pairs stay missing;
``aggregate_software_clock_rows`` reports ``missing_pair_count`` without inventing values.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from market_platform_foundation.clock import reset_clock_for_tests
from market_platform_foundation.intelligence.normalization import IngestionMode
from market_platform_foundation.intelligence.observation_ingress import (
    IngressDispatchContext,
    build_production_observation_ingress_router,
    dispatch_normalization_result,
)
from market_platform_foundation.intelligence.outcomes.opend_capture_ledger import (
    iter_jsonl_envelopes,
    normalize_capture_record_result,
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
from market_platform_foundation.intelligence.snapshots import SnapshotBuildRequest, SnapshotCompositionPolicy
from market_platform_foundation.rt01.clock import monotonic_process_ns
from market_platform_foundation.rt01.workloads import fixture_path

from .collector import HotPathClockCollector
from .exercise import derive_timestamp_exercise, validate_baseline_document
from .models import HotPathQualityCounters, ReplayLatencyBaselineDocument
from .software_aggregation import aggregate_software_clock_rows


def fixture_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).digest().hex().upper()


def _first_router_row(collector: HotPathClockCollector):
    """First ingress-dispatched row; anchor for optional demo merge only (not lineage)."""
    for row in collector.rows.values():
        if row.router_dispatched_at is not None:
            return row
    return None


def _first_detected_row(collector: HotPathClockCollector):
    for row in collector.rows.values():
        if row.detected_at is not None:
            return row
    for row in collector.detection_rows:
        if row.detected_at is not None:
            return row
    return None


def _optional_build_09_replay(collector: HotPathClockCollector) -> tuple[Any, Any, Any] | tuple[None, None, None]:
    try:
        from market_platform_foundation.intelligence.normalization import (
            NormalizationContext,
            require_normalized_event,
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
    result = ReplayRuntime().run(
        scenario,
        source,
        output_repository=output,
        pipeline_config=config,
    )
    for decision in result.decision_results:
        for ref in decision.detection_refs:
            detection = output.get_detection(ref.id)
            if detection is None:
                continue
            anchor = _first_router_row(collector)
            if anchor is not None and anchor.detected_at is None:
                anchor.detected_at = detection.detected_at_ns
            else:
                collector.note_detection(detection)
    return result, output, source


def _optional_opportunity_and_projection(collector: HotPathClockCollector) -> None:
    try:
        from market_platform_foundation.intelligence.opportunity.engine import OpportunityEngine
        from market_platform_foundation.intelligence.opportunity.types import AssessmentAction
        from market_platform_foundation.intelligence.promotion.engine import PromotionEngine
        from market_platform_foundation.ui_api.opportunity_projections import build_opportunities_summary_payload
        from market_platform_foundation.ui_api.store import ReplayStore
        from tests.intelligence.opportunity_fixtures import (
            champion_forecast,
            default_opportunity_context,
            default_opportunity_policy,
        )
        from tests.intelligence.promotion_fixtures import bootstrap_control_champion, validated_candidate_bundle
        from tests.ui1.test_ui_api import COLLECTION_ROOT
    except ImportError:
        return

    _repo, _manifest, candidate, _, _, _ = validated_candidate_bundle()
    champion = bootstrap_control_champion(PromotionEngine(), candidate)
    forecast = champion_forecast(champion)
    decision_time = forecast.decision_time_ns + 1
    assessed = OpportunityEngine().assess(
        forecast=forecast,
        policy=default_opportunity_policy(),
        context=default_opportunity_context(decision_time_ns=decision_time),
        champion_at_forecast=champion,
        champion_at_opportunity=champion,
        opportunity_decision_time_ns=decision_time,
    )
    if assessed.opportunity is None or assessed.assessment.assessment_action != AssessmentAction.EMIT:
        return
    opportunity = assessed.opportunity
    anchor = _first_detected_row(collector)
    if anchor is not None and anchor.opportunity_created_at is None:
        anchor.opportunity_created_at = opportunity.created_at_ns
    else:
        collector.note_opportunity(opportunity)

    store = ReplayStore(collection_root=COLLECTION_ROOT)
    store.load()
    build_opportunities_summary_payload(store, hot_path_collector=collector)
    surfaced_anchor = anchor if anchor is not None else _first_detected_row(collector)
    if surfaced_anchor is not None and surfaced_anchor.operator_surfaced_at is None:
        surfaced_anchor.operator_surfaced_at = monotonic_process_ns()


def _ingress_fixture_events(collector: HotPathClockCollector, path: Path, *, max_lines: int = 12) -> HotPathQualityCounters:
    repository = InMemoryIntelligenceRepository()
    router = build_production_observation_ingress_router(repository, dispatch_observer=collector)
    counters = HotPathQualityCounters()
    processed = 0
    for line_index, record, parse_error in iter_jsonl_envelopes(path):
        if parse_error is not None or record is None:
            continue
        if processed >= max_lines:
            break
        normalization = normalize_capture_record_result(record, capture_path=path, line_index=line_index)
        if normalization.event is None:
            continue
        counters = HotPathQualityCounters(**{**counters.to_dict(), "received": counters.received + 1})
        event = normalization.event
        dispatch_time_ns = event.available_time_ns
        try:
            receipt = dispatch_normalization_result(
                router,
                normalization,
                context=IngressDispatchContext(
                    dispatch_time_ns=dispatch_time_ns,
                    ingestion_mode=IngestionMode.REPLAY,
                    source_label=f"moomoo.capture:{path.name}:{line_index}",
                ),
                clock_collector=collector,
            )
        except Exception:
            counters = HotPathQualityCounters(**{**counters.to_dict(), "router_failures": counters.router_failures + 1})
            continue
        if receipt is not None:
            counters = HotPathQualityCounters(**{**counters.to_dict(), "normalized": counters.normalized + 1})
            processed += 1
    return counters


def build_software_wired_document(
    *,
    repo_root: Path | None = None,
    include_build_09_replay: bool = True,
    include_opportunity_projection: bool = True,
) -> ReplayLatencyBaselineDocument:
    """Measured fixture/software wiring — not live production latency."""
    reset_clock_for_tests()
    path = fixture_path() if repo_root is None else repo_root / "tests" / "fixtures" / "market_data" / "moomoo" / "captured-aapl.jsonl"
    collector = HotPathClockCollector()
    counters = _ingress_fixture_events(collector, path)
    replay_run_id: str | None = None
    if include_build_09_replay:
        replay_pair = _optional_build_09_replay(collector)
        if replay_pair[0] is not None:
            replay_run_id = replay_pair[0].run_id
    if include_opportunity_projection:
        _optional_opportunity_and_projection(collector)
    aggregated = aggregate_software_clock_rows(collector.all_rows())
    presence = aggregated["timestamp_presence"]
    exercise = derive_timestamp_exercise(presence)
    document = ReplayLatencyBaselineDocument(
        schema_version="hot_path_telemetry.software_wired/1.0.0",
        artifact_type="SOFTWARE_WIRED_HOT_PATH",
        measurement_class="MEASURED_FIXTURE_SOFTWARE",
        fixture_path="tests/fixtures/market_data/moomoo/captured-aapl.jsonl",
        fixture_sha256=fixture_sha256(path),
        timestamp_exercise=exercise,
        timestamp_presence=presence,
        latency_segments_ns=aggregated["latency_segments_ns"],
        quality_counters=counters.to_dict(),
        rt01_span_count=0,
        replay_run_id=replay_run_id,
        metadata={
            "clock_basis_processing": "process_monotonic_ns",
            "data_source": "FIXTURE_SOFTWARE_PATH",
            "acceptance": "HOT_PATH_TELEMETRY_SOFTWARE_WIRED",
        },
    )
    validate_baseline_document(document.to_dict())
    return document


__all__ = ["build_software_wired_document", "fixture_sha256"]

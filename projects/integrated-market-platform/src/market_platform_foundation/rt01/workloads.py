"""RT-01 representative deterministic workloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes
from ..replay.feature_lifecycle import run_feature_replay, run_feature_root_hash
from ..replay.quality_lifecycle import run_quality_replay, run_quality_root_hash
from .enums import TraceStage, TraceStatus
from .clock import monotonic_process_ns
from .instrumentation.paper import start_paper_trace, trace_refs
from .span import TraceSpan
from .tracer import get_tracer


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def fixture_path() -> Path:
    return _repo_root() / "tests" / "fixtures" / "market_data" / "moomoo" / "captured-aapl.jsonl"


def _sample_events() -> list[dict[str, Any]]:
    from ..market_data.capture import read_envelopes

    path = fixture_path()
    return list(read_envelopes(path))


def _sample_bar_events() -> list[dict[str, Any]]:
    events = _sample_events()
    rows: list[dict[str, Any]] = []
    for event in events:
        instrument = str(event.get("instrument_id", "AAPL"))
        available = int(event.get("available_time_ns", event.get("available_time", 0)))
        rows.append(
            {
                "available_time": available,
                "event_time": available,
                "instrument_id": instrument,
                "normalized_event_id": f"bar-{instrument}-{available}",
                "event_type": "BAR",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000,
            }
        )
    return rows


def run_fixture_ingest_workload() -> list[TraceSpan]:
    from ..market_data.live_runtime import LiveObservationalRuntime

    tracer = get_tracer()
    runtime = LiveObservationalRuntime()
    root = tracer.start_root("fixture_ingest", stable_sample_key="fixture-aapl")
    path = fixture_path()
    count_span = tracer.start_span(TraceStage.PROVIDER_RECEIVE, "feed_fixture", parent=root.context if root else None)
    count = runtime.feed_fixture_path(path)
    if count_span:
        count_span.end(output_ref=f"records:{count}")
    if root:
        root.end(output_ref=f"ingested:{count}")
    return list(tracer.collector.spans)


def fixture_ingest_domain_hash() -> dict[str, Any]:
    from ..market_data.live_runtime import LiveObservationalRuntime

    runtime = LiveObservationalRuntime()
    count = runtime.feed_fixture_path(fixture_path())
    body = {
        "count": count,
        "instruments": sorted(runtime.scope_symbols),
        "quotes": len(runtime.state.quotes),
    }
    return {"domain_hash": sha256_bytes(canonical_bytes(body)), "body": body}


def run_quality_replay_workload() -> list[TraceSpan]:
    tracer = get_tracer()
    events = _sample_bar_events()
    root = tracer.start_root("quality_replay")
    span = tracer.start_span(TraceStage.QUALITY, "run_quality_replay", parent=root.context if root else None)
    state = run_quality_replay(events, clocks=[2000], decision_times=[2000])
    digest = run_quality_root_hash(state)
    if span:
        span.end(output_ref=f"hash:{digest[:16]}")
    feature_span = tracer.start_span(
        TraceStage.FEATURE,
        "run_feature_replay",
        parent=root.context if root else None,
    )
    feature_state = run_feature_replay(events, clocks=[2000], decision_times=[2000], prediction_cutoff=2000)
    feature_digest = run_feature_root_hash(feature_state)
    if feature_span:
        feature_span.end(output_ref=f"hash:{feature_digest[:16]}")
    if root:
        root.end()
    return list(tracer.collector.spans)


def run_paper_trace_workload() -> list[TraceSpan]:
    """Run deterministic internal and broker Paper trace paths without I/O."""
    tracer = get_tracer()
    trace = start_paper_trace(
        "paper_internal_fixture",
        correlation_id="paper-workload-internal",
        tracer=tracer,
    )
    parent = trace.context
    queue_start = monotonic_process_ns()
    queue = tracer.start_span(
        TraceStage.QUEUE,
        "paper_fixture_queue",
        parent=parent,
        queue_enqueue_mono_ns=queue_start,
        queue_dequeue_mono_ns=monotonic_process_ns(),
        bind=False,
    )
    if queue is not None:
        queue.context.attributes.update(trace_refs(order_id="internal-order-1"))
        queue.end(output_ref="dequeued")
        parent = queue.context
    for stage, operation, output in (
        (TraceStage.SIGNAL, "paper_fixture_signal", "signal-1"),
        (TraceStage.OPPORTUNITY, "paper_fixture_opportunity", "opportunity-1"),
        (TraceStage.RISK, "paper_fixture_risk", "risk-1"),
        (TraceStage.ORDER_READY, "paper_fixture_internal_submit", "internal-order-1"),
    ):
        span = tracer.start_span(stage, operation, parent=parent, bind=False)
        if span is not None:
            span.context.attributes.update(
                trace_refs(
                    signal_id="signal-1",
                    opportunity_id="opportunity-1",
                    risk_decision_id="risk-1",
                    order_id=output,
                )
            )
            span.end(output_ref=output)
            parent = span.context
    trace.finish(output_ref="internal-order-1")

    broker_trace = start_paper_trace(
        "paper_broker_fixture",
        correlation_id="paper-workload-broker",
        tracer=tracer,
    )
    parent = broker_trace.context
    for stage, operation, output in (
        (TraceStage.QUEUE, "paper_fixture_queue", "dequeued"),
        (TraceStage.SIGNAL, "paper_fixture_signal", "signal-2"),
        (TraceStage.OPPORTUNITY, "paper_fixture_opportunity", "opportunity-2"),
        (TraceStage.RISK, "paper_fixture_risk", "risk-2"),
        (TraceStage.ORDER_READY, "paper_fixture_order_ready", "order-2"),
        (TraceStage.BROKER, "paper_fixture_partial_fill", "broker-order-2"),
        (TraceStage.RECONCILIATION, "paper_fixture_reconciliation", "report-2"),
    ):
        span = tracer.start_span(stage, operation, parent=parent, bind=False)
        if span is not None:
            span.context.attributes.update(
                trace_refs(
                    signal_id="signal-2",
                    opportunity_id="opportunity-2",
                    risk_decision_id="risk-2",
                    order_id="order-2",
                    broker_order_id="broker-order-2",
                    report_id="report-2",
                )
            )
            span.end(output_ref=output)
            parent = span.context
    broker_trace.finish(output_ref="report-2")
    return list(tracer.collector.spans)


def quality_replay_domain_hash() -> dict[str, Any]:
    events = _sample_bar_events()
    state = run_quality_replay(events, clocks=[2000], decision_times=[2000])
    digest = run_quality_root_hash(state)
    feature_state = run_feature_replay(events, clocks=[2000], decision_times=[2000], prediction_cutoff=2000)
    feature_digest = run_feature_root_hash(feature_state)
    body = {"quality_root": digest, "feature_root": feature_digest}
    return {"domain_hash": sha256_bytes(canonical_bytes(body)), "body": body}


__all__ = [
    "fixture_ingest_domain_hash",
    "fixture_path",
    "quality_replay_domain_hash",
    "run_paper_trace_workload",
    "run_fixture_ingest_workload",
    "run_quality_replay_workload",
]

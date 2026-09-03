"""Manual internal-paper smoke against live Moomoo data. Never calls Moomoo trade APIs."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "moomoo"))

from market_platform_foundation.market_data.internal_simulation_gate import evaluate_internal_simulation_gates
from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime, reset_live_runtime
from market_platform_foundation.market_data.subscription_manager import SubscriptionPriority
from market_platform_foundation.paper.execution import preview_interactive_order, submit_interactive_order
from market_platform_foundation.paper.ledger import PaperExecutionLedger


def main() -> int:
    os.environ.setdefault("IMP_LIVE_OBSERVATIONAL", "1")
    os.environ.setdefault("IMP_MOOMOO_LIVE", "1")
    os.environ.setdefault("IMP_PAPER_EXECUTION", "1")
    os.environ.setdefault("IMP_LIVE_INTERNAL_SIMULATION", "1")
    reset_live_runtime()
    runtime = LiveObservationalRuntime()
    runtime.configure()
    runtime.subscribe(
        instrument_id="AAPL",
        capabilities=["BASIC_QUOTE", "TRADES"],
        consumer_id="paper-smoke",
        priority=SubscriptionPriority.ACTIVE_EXECUTION_CONTEXT,
    )
    deadline = time.time() + 15
    while time.time() < deadline:
        gate = evaluate_internal_simulation_gates(
            runtime=runtime,
            probe_stale=runtime.capability_registry.is_stale,
        )
        if gate.status == "AUTHORIZED" and runtime.execution_buffer.report().get("event_count", 0) >= 2:
            break
        time.sleep(0.25)
    gate = evaluate_internal_simulation_gates(
        runtime=runtime,
        probe_stale=runtime.capability_registry.is_stale,
    )
    print({"gate": gate.to_dict(), "buffer": runtime.execution_buffer.report(), "lifecycle": runtime.lifecycle.connection_state.value})
    if gate.status != "AUTHORIZED":
        runtime.unsubscribe(instrument_id="AAPL", capabilities=["BASIC_QUOTE", "TRADES"], consumer_id="paper-smoke")
        runtime.stop()
        print("DEFERRED_FOR_SAFETY")
        return 2
    ledger = PaperExecutionLedger.open_session(
        replay_session_id="p21-live-paper",
        instrument_id="AAPL",
        symbol="AAPL",
        data_mode="LIVE_OBSERVATIONAL",
        data_provider="MOOMOO",
        execution_mode="INTERNAL_SIMULATION",
        execution_authority="PAPER_ONLY",
        execution_provider="INTERNAL",
    )
    intent_time = time.time_ns()
    deadline = time.time() + 8
    bars: list = []
    while time.time() < deadline:
        bars = runtime.execution_buffer.bars_after_intent(
            created_time_ns=intent_time,
            observation_time_ns=time.time_ns(),
            price_scale=int(ledger.policy["price_scale"]),
            instrument_id="AAPL",
        )
        if bars:
            break
        time.sleep(0.1)
    observation = intent_time
    preview = preview_interactive_order(
        ledger=ledger,
        bars=bars,
        symbol="AAPL",
        instrument_id="AAPL",
        side="BUY",
        quantity=1,
        observation_time=observation or time.time_ns(),
        client_order_id="p21-aapl-1",
        idempotency_key="p21-aapl-1",
    )
    submitted = submit_interactive_order(
        ledger=ledger,
        bars=bars,
        symbol="AAPL",
        instrument_id="AAPL",
        side="BUY",
        quantity=1,
        observation_time=observation or time.time_ns(),
        client_order_id="p21-aapl-1",
        idempotency_key="p21-aapl-1",
    )
    mark = runtime.live_mark_for("AAPL")
    if mark:
        ledger.apply_live_mark(
            mark_minor=int(mark["mark_minor"]),
            mark_provider=str(mark["mark_provider"]),
            mark_as_of_ns=int(mark["mark_as_of_ns"]),
            mark_quality=str(mark["mark_quality"]),
        )
    positions = ledger.project_positions()
    fill_id = None
    fills = ledger.project_fills()
    if fills:
        fill_id = str(fills[0].get("fill_id"))
    trace = None
    if fill_id:
        trace = ledger.project_execution_trace(fill_id=fill_id)
    counters = (runtime.feed_metrics or {}).get("trade_api_counters") or {}
    runtime.unsubscribe(instrument_id="AAPL", capabilities=["BASIC_QUOTE", "TRADES"], consumer_id="paper-smoke")
    runtime.stop()
    print(
        {
            "preview_decision": preview.get("decision"),
            "preview_fill": preview.get("fill_preview_available"),
            "preview_reasons": preview.get("reason_codes"),
            "order_state": submitted.get("order", {}).get("state") if isinstance(submitted.get("order"), dict) else None,
            "order_reasons": submitted.get("order", {}).get("reason_codes") if isinstance(submitted.get("order"), dict) else None,
            "bar_count": len(bars),
            "observation": observation,
            "bar_times": [row.get("available_time") for row in bars[-5:]],
            "submission_keys": sorted(submitted.keys()),
            "fills": len(fills),
            "positions": positions,
            "trace_broker_submitted": None if trace is None else trace.get("broker_order_submitted"),
            "trade_api_counters": counters,
            "market_data_provider": "MOOMOO",
            "execution_provider": "INTERNAL",
            "authority": "PAPER_ONLY",
        }
    )
    if not fills:
        return 1
    if any(int(counters.get(key) or 0) for key in counters):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

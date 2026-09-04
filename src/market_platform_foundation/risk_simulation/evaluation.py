"""End-to-end risk, simulation, and accounting evaluation."""

from __future__ import annotations

from typing import Any

from ..attribution.record import build_attribution_record
from ..canonical import canonical_bytes, sha256_bytes
from ..execution.intent import build_order_intent
from ..execution.simulator import BarConservativeSimulator
from ..portfolio.ledger import apply_fill, build_ledger_state
from ..portfolio.reconciliation import reconcile_ledgers
from ..risk.decision import evaluate_risk
from ..risk.kill_switch import KillSwitchState
from ..risk.policy import DEFAULT_RISK_POLICY
from ..strategy.evaluation import run_strategy_evaluation


def _squeeze_replay_hash(timeline: list[dict[str, Any]]) -> str:
    return sha256_bytes(canonical_bytes(timeline))


def _bars_from_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bars = [event for event in events if event.get("event_type") == "BAR_OHLCV_1M"]
    return sorted(bars, key=lambda row: (int(row["available_time"]), str(row["normalized_event_id"])))


def _instrument_for_cutoff(bars: list[dict[str, Any]], cutoff: int) -> str:
    for bar in reversed(bars):
        if int(bar["available_time"]) <= cutoff:
            return str(bar["instrument_id"])
    if bars:
        return str(bars[0]["instrument_id"])
    return "UNKNOWN"


def audit_fill_eligibility(
    orders: list[dict[str, Any]],
    fills: list[dict[str, Any]],
) -> dict[str, Any]:
    violations: list[str] = []
    for fill in fills:
        activation_time = int(fill["activation_time"])
        fill_time = int(fill["fill_time"])
        if fill_time < activation_time:
            violations.append(fill["fill_id"])
    for order in orders:
        if order.get("state") in {"FILLED", "PARTIALLY_FILLED"}:
            activation = order.get("activation_time")
            if activation is None:
                violations.append(str(order["order_id"]))
    return {
        "status": "PASS" if not violations else "FAIL",
        "violation_ids": sorted(set(violations)),
    }


def audit_allocation_ledger(
    *,
    fills: list[dict[str, Any]],
    bars: list[dict[str, Any]],
    policy: dict[str, Any],
) -> dict[str, Any]:
    from ..numeric import apply_participation_cap

    bar_volume_by_time = {
        int(bar["available_time"]): int(bar.get("bar_payload", {}).get("volume", 0))
        for bar in bars
        if isinstance(bar.get("bar_payload"), dict)
    }
    allocated: dict[int, int] = {}
    violations: list[str] = []
    for fill in fills:
        fill_time = int(fill["fill_time"])
        qty = int(fill["fill_quantity"])
        allocated[fill_time] = allocated.get(fill_time, 0) + qty
    for fill_time, qty in allocated.items():
        eligible = apply_participation_cap(
            bar_volume_by_time.get(fill_time, 0),
            numerator=int(policy["participation_cap_numerator"]),
            denominator=int(policy["participation_cap_denominator"]),
        )
        if qty > eligible:
            violations.append(str(fill_time))
    return {
        "status": "PASS" if not violations else "FAIL",
        "violation_bar_times": sorted(violations),
    }


def run_risk_simulation_evaluation(
    events: list[dict[str, Any]],
    *,
    policy: dict[str, Any] | None = None,
    kill_switch: KillSwitchState | None = None,
    desired_quantity: int | None = None,
    enable_squeeze_replay: bool = True,
) -> dict[str, object]:
    from ..donor_bridge.squeeze_simulation_context import resolve_squeeze_context_at_cutoff

    active_policy = policy or DEFAULT_RISK_POLICY
    switch = kill_switch or KillSwitchState()
    qty_default = desired_quantity or 1

    strategy_result = run_strategy_evaluation(events)
    bars = _bars_from_events(events)
    simulator = BarConservativeSimulator(policy=active_policy)

    intents: list[dict[str, Any]] = []
    risk_decisions: list[dict[str, Any]] = []
    orders: list[dict[str, Any]] = []
    fills: list[dict[str, Any]] = []
    attributions: list[dict[str, Any]] = []

    ledger = build_ledger_state(initial_cash_minor=int(active_policy["initial_cash_minor"]))
    position = 0
    open_orders = 0
    squeeze_timeline: list[dict[str, Any]] = []

    interpretations = strategy_result.get("interpretations", [])
    for interpretation in interpretations:
        if not isinstance(interpretation, dict):
            continue
        if interpretation.get("outcome") != "signal":
            continue
        obs_time = int(interpretation.get("prediction_cutoff", 0))
        instrument_id = _instrument_for_cutoff(bars, obs_time)
        intent = build_order_intent(
            interpretation=interpretation,
            instrument_id=instrument_id,
            observation_time=obs_time,
            desired_quantity=qty_default,
        )
        if intent is None:
            continue
        intents.append(intent)

        decision = evaluate_risk(
            intent=intent,
            policy=active_policy,
            kill_switch=switch,
            current_position_shares=position,
            open_order_count=open_orders,
        )
        risk_decisions.append(decision)

        if decision["decision"] in {"APPROVE", "RESIZE"}:
            open_orders += 1

        squeeze_context = None
        if enable_squeeze_replay:
            squeeze_context = resolve_squeeze_context_at_cutoff(obs_time)
            squeeze_timeline.append(
                {
                    "cutoff": obs_time,
                    "exhaustion_risk": squeeze_context.get("exhaustion_risk"),
                    "remaining_fuel": squeeze_context.get("remaining_fuel"),
                    "squeeze_state": squeeze_context.get("squeeze_state"),
                }
            )

        order, fill = simulator.simulate(
            intent=intent,
            risk_decision=decision,
            bars=bars,
            squeeze_context=squeeze_context,
        )
        orders.append(order)

        if decision["decision"] in {"APPROVE", "RESIZE"} and fill is None:
            open_orders = max(open_orders - 1, 0)

        ledger_entry: dict[str, Any] | None = None
        if fill is not None:
            fills.append(fill)
            prior_entries = len(ledger["entries"])
            ledger = apply_fill(ledger, fill=fill, policy=active_policy)
            if len(ledger["entries"]) > prior_entries:
                ledger_entry = ledger["entries"][-1]
            direction = str(fill["direction"])
            signed = int(fill["fill_quantity"]) if direction == "long" else -int(fill["fill_quantity"])
            position += signed
            open_orders = max(open_orders - 1, 0)

        attributions.append(
            build_attribution_record(
                intent=intent,
                risk_decision=decision,
                order=order,
                fill=fill,
                ledger_entry=ledger_entry,
            )
        )

    reconciliation = reconcile_ledgers(
        authoritative=ledger,
        fills=fills,
        policy=active_policy,
    )
    fill_audit = audit_fill_eligibility(orders, fills)
    allocation_audit = audit_allocation_ledger(fills=fills, bars=bars, policy=active_policy)

    return {
        "allocation_audit": allocation_audit,
        "attributions": attributions,
        "fill_audit": fill_audit,
        "fills": fills,
        "intents": intents,
        "ledger": ledger,
        "orders": orders,
        "reconciliation": reconciliation,
        "risk_decisions": risk_decisions,
        "risk_policy": active_policy,
        "squeeze_replay_hash": _squeeze_replay_hash(squeeze_timeline) if squeeze_timeline else None,
        "squeeze_timeline": squeeze_timeline,
        "strategy_result": strategy_result,
    }


def risk_simulation_root_hash(result: dict[str, object]) -> str:
    body = {
        "attribution_hashes": [
            sha256_bytes(canonical_bytes(row))
            for row in result.get("attributions", [])
            if isinstance(row, dict)
        ],
        "fill_audit_status": result.get("fill_audit", {}).get("status"),
        "ledger_root": sha256_bytes(
            canonical_bytes(
                {
                    "cash_minor": result["ledger"]["cash_minor"],
                    "position_shares": result["ledger"]["position_shares"],
                    "realized_pnl_minor": result["ledger"]["realized_pnl_minor"],
                }
            )
        ),
        "order_count": len(result.get("orders", [])),
        "reconciliation_status": result.get("reconciliation", {}).get("status"),
        "squeeze_replay_hash": result.get("squeeze_replay_hash"),
    }
    return sha256_bytes(canonical_bytes(body))

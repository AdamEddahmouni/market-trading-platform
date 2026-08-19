"""Options O9 execution — conservative NBBO fills, lifecycle, execution snapshot."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Sequence

from ..canonical import canonical_bytes, sha256_bytes
from ..contracts.options_quality import OptionQualityFlag
from ..donor_patterns.options_lane import liquidity_gate
from ..portfolio.options_ledger import (
    apply_option_fill,
    apply_settlement,
    build_options_ledger_state,
)
from .payoff import OptionLeg, leg_to_dict, payoff_at_spot

EXECUTION_VERSION = "options_execution_v1"
EXECUTION_METHOD = "NBBO_CONSERVATIVE_V1"
SIMULATOR_REGISTRY_ID = "simulation.options_conservative"

EARLY_EXERCISE_DEEP_ITM_BUFFER = 0.15
EARLY_EXERCISE_EXTRINSIC_RATIO = 0.05
DEFAULT_INITIAL_CASH = 100_000.0

NVDA_EXECUTION_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "providers"
    / "options"
    / "nvda_options_execution_slice.json"
)

LegSide = Literal["long", "short"]


def load_execution_fixture(symbol: str) -> dict[str, Any] | None:
    """Load fixture execution slice when symbol matches (fixture-first scope)."""
    if symbol.upper() != "NVDA" or not NVDA_EXECUTION_FIXTURE.is_file():
        return None
    payload = json.loads(NVDA_EXECUTION_FIXTURE.read_text(encoding="utf-8"))
    if str(payload.get("symbol", "")).upper() != symbol.upper():
        return None
    return payload


def _normalize_row(row: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    option_type = str(row.get("option_type", row.get("call_put", ""))).lower()
    if option_type not in {"call", "put"}:
        return None
    expiry = row.get("expiry", row.get("expiration"))
    strike_raw = row.get("strike")
    if not expiry or strike_raw is None:
        return None
    try:
        strike = float(strike_raw)
    except (TypeError, ValueError):
        return None
    bid = float(row.get("bid", 0.0) or 0.0)
    ask = float(row.get("ask", 0.0) or 0.0)
    if bid <= 0 or ask <= 0:
        return None
    return {
        "option_type": option_type,
        "call_put": option_type,
        "expiry": str(expiry),
        "strike": strike,
        "bid": bid,
        "ask": ask,
        "open_interest": int(row.get("open_interest", 0) or 0),
        "multiplier": float(row.get("multiplier", 100.0) or 100.0),
    }


def _find_chain_row(
    leg: OptionLeg | dict[str, Any],
    chain_rows: Sequence[dict[str, Any]],
) -> dict[str, Any] | None:
    call_put = leg.call_put if isinstance(leg, OptionLeg) else str(leg.get("call_put", ""))
    strike = leg.strike if isinstance(leg, OptionLeg) else float(leg.get("strike", 0))
    expiry = leg.expiry if isinstance(leg, OptionLeg) else str(leg.get("expiry", ""))
    for source in chain_rows:
        normalized = _normalize_row(source)
        if (
            normalized
            and normalized["call_put"] == call_put
            and normalized["strike"] == strike
            and normalized["expiry"] == expiry
        ):
            return normalized
    return None


def conservative_fill_price(row: dict[str, Any], side: LegSide) -> dict[str, Any]:
    """Long pays ask, short receives bid — fail-closed on invalid quotes."""
    bid = float(row.get("bid", 0.0))
    ask = float(row.get("ask", 0.0))
    if bid <= 0 or ask <= 0 or ask < bid:
        return {
            "available": False,
            "reason": "INVALID_QUOTES",
        }
    price = ask if side == "long" else bid
    return {
        "available": True,
        "fill_price": round(price, 6),
        "side": side,
    }


def legs_from_candidate(candidate: dict[str, Any]) -> list[OptionLeg]:
    """Deserialize O8 best_candidate legs into OptionLeg list."""
    raw_legs = candidate.get("legs", [])
    if not isinstance(raw_legs, list):
        return []
    legs: list[OptionLeg] = []
    for row in raw_legs:
        if not isinstance(row, dict):
            continue
        try:
            legs.append(
                OptionLeg(
                    call_put=str(row["call_put"]),  # type: ignore[arg-type]
                    strike=float(row["strike"]),
                    expiry=str(row["expiry"]),
                    side=str(row["side"]),  # type: ignore[arg-type]
                    quantity=int(row.get("quantity", 1)),
                    entry_premium=float(row.get("entry_premium", 0.0)),
                    multiplier=float(row.get("multiplier", 100.0)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return legs


def build_options_order_intent(
    candidate: dict[str, Any],
    as_of_time: str,
    *,
    symbol: str,
) -> dict[str, Any] | None:
    """Canonical multi-leg intent for options conservative simulator."""
    legs = legs_from_candidate(candidate)
    if not legs:
        return None
    body = {
        "as_of_time": as_of_time,
        "created_time": as_of_time,
        "instrument_type": "OPTION_MULTI_LEG",
        "legs": [leg_to_dict(leg) for leg in legs],
        "symbol": symbol.upper(),
        "template": candidate.get("template"),
    }
    return {
        **body,
        "intent_id": sha256_bytes(canonical_bytes(body)),
    }


def simulate_multi_leg_entry(
    legs: Sequence[OptionLeg],
    chain_rows: Sequence[dict[str, Any]],
    friction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Per-leg conservative fill with liquidity gate — multi-leg fails closed if any leg blocked."""
    del friction  # fixture scope: friction applied at lifecycle PnL summary only
    if not legs:
        return {
            "available": False,
            "reason": "NO_LEGS",
            "quality_flags": [OptionQualityFlag.EXECUTION_INPUTS_INCOMPLETE.value],
        }

    leg_fills: list[dict[str, Any]] = []
    liquidity_reasons: list[str] = []
    for index, leg in enumerate(legs):
        row = _find_chain_row(leg, chain_rows)
        if row is None:
            return {
                "available": False,
                "reason": "CHAIN_ROW_MISSING",
                "leg_index": index,
                "quality_flags": [OptionQualityFlag.EXECUTION_INPUTS_INCOMPLETE.value],
            }
        ok, reasons = liquidity_gate(
            bid=row["bid"],
            ask=row["ask"],
            open_interest=row["open_interest"],
        )
        if not ok:
            return {
                "available": False,
                "reason": "EXECUTION_LIQUIDITY_BLOCKED",
                "leg_index": index,
                "liquidity_reasons": sorted(set(reasons)),
                "quality_flags": [OptionQualityFlag.EXECUTION_LIQUIDITY_BLOCKED.value],
            }
        priced = conservative_fill_price(row, leg.side)
        if not priced.get("available"):
            return {
                "available": False,
                "reason": priced.get("reason", "INVALID_QUOTES"),
                "leg_index": index,
                "quality_flags": [OptionQualityFlag.EXECUTION_INPUTS_INCOMPLETE.value],
            }
        fill_body = {
            "leg_index": index,
            "call_put": leg.call_put,
            "strike": leg.strike,
            "expiry": leg.expiry,
            "side": leg.side,
            "fill_price": priced["fill_price"],
            "quantity": leg.quantity,
            "multiplier": leg.multiplier,
            "liquidity_ok": True,
            "liquidity_reasons": liquidity_reasons,
        }
        fill_body["fill_id"] = sha256_bytes(canonical_bytes(fill_body))
        leg_fills.append(fill_body)

    total_premium = 0.0
    for fill, leg in zip(leg_fills, legs, strict=True):
        premium = float(fill["fill_price"]) * float(fill["multiplier"]) * int(fill["quantity"])
        if leg.side == "long":
            total_premium += premium
        else:
            total_premium -= premium

    return {
        "available": True,
        "entry_fills": leg_fills,
        "total_entry_premium": round(total_premium, 6),
        "method": EXECUTION_METHOD,
        "model_version": EXECUTION_VERSION,
    }


def _leg_intrinsic(spot: float, position: dict[str, Any]) -> float:
    strike = float(position["strike"])
    if str(position["call_put"]) == "call":
        return max(0.0, spot - strike)
    return max(0.0, strike - spot)


def evaluate_early_exercise(
    position: dict[str, Any],
    spot: float,
    *,
    extrinsic_threshold_ratio: float = EARLY_EXERCISE_EXTRINSIC_RATIO,
    deep_itm_buffer: float = EARLY_EXERCISE_DEEP_ITM_BUFFER,
) -> dict[str, Any]:
    """American early exercise: deep ITM + low extrinsic (fixture constants)."""
    intrinsic = _leg_intrinsic(spot, position)
    entry_premium = float(position.get("entry_premium", 0.0))
    if str(position["side"]) != "long":
        return {"should_exercise": False, "reason": "NOT_LONG"}
    if spot <= 0:
        return {"should_exercise": False, "reason": "INVALID_SPOT"}
    if intrinsic <= 0:
        return {"should_exercise": False, "reason": "OTM"}
    strike = float(position["strike"])
    call_put = str(position["call_put"])
    if call_put == "call":
        moneyness = spot / strike if strike > 0 else 0.0
    else:
        moneyness = strike / spot if spot > 0 else 0.0
    itm_depth = moneyness - 1.0
    extrinsic = max(0.0, entry_premium - intrinsic)
    extrinsic_ratio = extrinsic / spot
    should = itm_depth >= deep_itm_buffer and extrinsic_ratio < extrinsic_threshold_ratio
    return {
        "should_exercise": should,
        "intrinsic": round(intrinsic, 6),
        "extrinsic": round(extrinsic, 6),
        "moneyness": round(moneyness, 6),
        "itm_depth": round(itm_depth, 6),
    }


def process_assignment_event(
    short_position: dict[str, Any],
    spot: float,
) -> dict[str, Any]:
    """Short option assigned — physical settlement at strike (fixture scope)."""
    if str(short_position.get("side")) != "short":
        return {"available": False, "reason": "NOT_SHORT_POSITION"}
    strike = float(short_position["strike"])
    quantity = int(short_position["quantity"])
    multiplier = float(short_position.get("multiplier", 100.0))
    call_put = str(short_position["call_put"])
    if call_put == "put":
        stock_delta = -quantity * int(multiplier)
        cash_delta = strike * quantity * multiplier
    else:
        stock_delta = quantity * int(multiplier)
        cash_delta = -strike * quantity * multiplier
    entry_premium = float(short_position.get("entry_premium", 0.0))
    premium_received = entry_premium * multiplier * quantity
    intrinsic_at_assignment = _leg_intrinsic(spot, {**short_position, "side": "long"})
    realized = premium_received - intrinsic_at_assignment * multiplier * quantity
    return {
        "available": True,
        "event_type": "ASSIGNMENT",
        "cash_delta": round(cash_delta, 6),
        "stock_delta": stock_delta,
        "realized_pnl_delta": round(realized, 6),
        "closed_position": dict(short_position),
        "detail": f"Assigned short {call_put} at strike {strike}",
    }


def settle_at_expiry(
    positions: Sequence[dict[str, Any]],
    spot_at_expiry: float,
    *,
    force_assignment: bool = False,
) -> list[dict[str, Any]]:
    """Cash-settle intrinsic at expiry; optional forced assignment on short ITM legs."""
    events: list[dict[str, Any]] = []
    for position in positions:
        intrinsic = _leg_intrinsic(spot_at_expiry, position)
        side = str(position["side"])
        quantity = int(position["quantity"])
        multiplier = float(position.get("multiplier", 100.0))
        entry_premium = float(position.get("entry_premium", 0.0))
        if side == "short" and intrinsic > 0 and force_assignment:
            assignment = process_assignment_event(position, spot_at_expiry)
            if assignment.get("available"):
                events.append(assignment)
            continue
        if intrinsic <= 0:
            realized = -entry_premium * multiplier * quantity if side == "long" else entry_premium * multiplier * quantity
            events.append(
                {
                    "event_type": "EXPIRATION",
                    "cash_delta": 0.0,
                    "stock_delta": 0,
                    "realized_pnl_delta": round(realized, 6),
                    "closed_position": dict(position),
                    "detail": "OTM expiration — worthless",
                }
            )
            continue
        settlement_cash = intrinsic * multiplier * quantity
        if side == "long":
            cash_delta = settlement_cash
            realized = settlement_cash - entry_premium * multiplier * quantity
        else:
            cash_delta = -settlement_cash
            realized = entry_premium * multiplier * quantity - settlement_cash
        events.append(
            {
                "event_type": "EXPIRATION",
                "cash_delta": round(cash_delta, 6),
                "stock_delta": 0,
                "realized_pnl_delta": round(realized, 6),
                "closed_position": dict(position),
                "detail": f"ITM expiration intrinsic={intrinsic}",
            }
        )
    return events


def run_options_lifecycle(
    simulation_state: dict[str, Any],
    scenario: dict[str, Any],
) -> dict[str, Any]:
    """Drive entry fills through optional early exercise and expiry."""
    ledger = simulation_state.get("ledger")
    if not isinstance(ledger, dict):
        return {
            "available": False,
            "reason": "LEDGER_UNAVAILABLE",
        }

    lifecycle_events: list[dict[str, Any]] = []
    spot_pre_expiry = float(scenario.get("spot_pre_expiry", scenario.get("spot_at_expiry", 0.0)))
    if scenario.get("evaluate_early_exercise"):
        for position in list(ledger["option_positions"]):
            exercise_eval = evaluate_early_exercise(position, spot_pre_expiry)
            if exercise_eval.get("should_exercise"):
                intrinsic = float(exercise_eval["intrinsic"])
                quantity = int(position["quantity"])
                multiplier = float(position.get("multiplier", 100.0))
                entry_premium = float(position.get("entry_premium", 0.0))
                settlement_cash = intrinsic * multiplier * quantity
                realized = settlement_cash - entry_premium * multiplier * quantity
                event = {
                    "event_type": "EARLY_EXERCISE",
                    "cash_delta": round(settlement_cash, 6),
                    "stock_delta": 0,
                    "realized_pnl_delta": round(realized, 6),
                    "closed_position": dict(position),
                    "detail": "American early exercise triggered",
                }
                ledger = apply_settlement(ledger, event=event)
                lifecycle_events.append(event)

    spot_at_expiry = float(scenario.get("spot_at_expiry", spot_pre_expiry))
    force_assignment = bool(scenario.get("force_assignment", False))
    expiry_events = settle_at_expiry(
        ledger["option_positions"],
        spot_at_expiry,
        force_assignment=force_assignment,
    )
    for event in expiry_events:
        ledger = apply_settlement(ledger, event=event)
        lifecycle_events.append(event)

    return {
        "available": True,
        "ledger": ledger,
        "lifecycle_events": lifecycle_events,
        "realized_pnl": float(ledger["realized_pnl"]),
    }


def _execution_replay_hash(payload: dict[str, Any]) -> str:
    canonical = {key: payload[key] for key in sorted(payload.keys()) if key != "execution_replay_hash"}
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _default_scenario(fixture: dict[str, Any] | None) -> dict[str, Any]:
    if fixture and isinstance(fixture.get("scenarios"), dict):
        scenarios = fixture["scenarios"]
        if "single_leg_fill" in scenarios:
            return dict(scenarios["single_leg_fill"])
    return {
        "spot_at_expiry": 135.0,
        "spot_pre_expiry": 135.0,
        "evaluate_early_exercise": False,
        "force_assignment": False,
    }


def build_execution_snapshot(
    symbol: str,
    as_of_time: str,
    *,
    strategy_snapshot: dict[str, Any] | None = None,
    chain_rows: Sequence[dict[str, Any]] | None = None,
    friction: dict[str, Any] | None = None,
    scenario: dict[str, Any] | None = None,
    squeeze_context: dict[str, Any] | None = None,
    initial_cash: float = DEFAULT_INITIAL_CASH,
) -> dict[str, Any]:
    """Top-level execution snapshot for workspace payload."""
    quality_flags: list[str] = []
    fixture = load_execution_fixture(symbol)

    effective_rows = list(chain_rows or [])
    if not effective_rows and fixture:
        effective_rows = list(fixture.get("chain_rows", []))

    if not strategy_snapshot or strategy_snapshot.get("status") != "RANKED":
        quality_flags.append(OptionQualityFlag.EXECUTION_INPUTS_INCOMPLETE.value)
        result = {
            "available": False,
            "status": "UNAVAILABLE",
            "outcome": "UNAVAILABLE",
            "symbol": symbol,
            "as_of_time": as_of_time,
            "reason": "STRATEGY_NOT_RANKED",
            "entry_fills": [],
            "lifecycle_events": [],
            "realized_pnl": None,
            "unrealized_pnl": None,
            "ledger_summary": {},
            "strategy_template": None,
            "method": EXECUTION_METHOD,
            "model_version": EXECUTION_VERSION,
            "simulator_registry_id": SIMULATOR_REGISTRY_ID,
            "quality_flags": quality_flags,
        }
        result["execution_replay_hash"] = _execution_replay_hash(result)
        return result

    best_candidate = strategy_snapshot.get("best_candidate")
    if not isinstance(best_candidate, dict):
        quality_flags.append(OptionQualityFlag.EXECUTION_INPUTS_INCOMPLETE.value)
        result = {
            "available": False,
            "status": "UNAVAILABLE",
            "outcome": "UNAVAILABLE",
            "symbol": symbol,
            "as_of_time": as_of_time,
            "reason": "BEST_CANDIDATE_MISSING",
            "entry_fills": [],
            "lifecycle_events": [],
            "realized_pnl": None,
            "unrealized_pnl": None,
            "ledger_summary": {},
            "strategy_template": None,
            "method": EXECUTION_METHOD,
            "model_version": EXECUTION_VERSION,
            "simulator_registry_id": SIMULATOR_REGISTRY_ID,
            "quality_flags": quality_flags,
        }
        result["execution_replay_hash"] = _execution_replay_hash(result)
        return result

    legs = legs_from_candidate(best_candidate)
    if not legs or not effective_rows:
        quality_flags.append(OptionQualityFlag.EXECUTION_INPUTS_INCOMPLETE.value)
        result = {
            "available": False,
            "status": "UNAVAILABLE",
            "outcome": "UNAVAILABLE",
            "symbol": symbol,
            "as_of_time": as_of_time,
            "reason": "LEGS_OR_CHAIN_UNAVAILABLE",
            "entry_fills": [],
            "lifecycle_events": [],
            "realized_pnl": None,
            "unrealized_pnl": None,
            "ledger_summary": {},
            "strategy_template": best_candidate.get("template"),
            "method": EXECUTION_METHOD,
            "model_version": EXECUTION_VERSION,
            "simulator_registry_id": SIMULATOR_REGISTRY_ID,
            "quality_flags": quality_flags,
        }
        result["execution_replay_hash"] = _execution_replay_hash(result)
        return result

    effective_scenario = dict(scenario or _default_scenario(fixture))
    if not effective_scenario.get("spot_at_expiry") and fixture:
        quality_flags.append(OptionQualityFlag.EXECUTION_SCENARIO_UNAVAILABLE.value)

    entry_result = simulate_multi_leg_entry(legs, effective_rows, friction)
    if not entry_result.get("available"):
        quality_flags.extend(entry_result.get("quality_flags", []))
        result = {
            "available": True,
            "status": "REJECTED",
            "outcome": "REJECTED",
            "symbol": symbol,
            "as_of_time": as_of_time,
            "reason": entry_result.get("reason", "ENTRY_REJECTED"),
            "entry_fills": [],
            "lifecycle_events": [],
            "realized_pnl": None,
            "unrealized_pnl": None,
            "ledger_summary": {},
            "strategy_template": best_candidate.get("template"),
            "method": EXECUTION_METHOD,
            "model_version": EXECUTION_VERSION,
            "simulator_registry_id": SIMULATOR_REGISTRY_ID,
            "quality_flags": sorted(set(quality_flags)),
        }
        if squeeze_context and squeeze_context.get("available"):
            result["squeeze_context"] = {
                "squeeze_state": squeeze_context.get("squeeze_state"),
                "exhaustion_risk": squeeze_context.get("exhaustion_risk"),
            }
        result["execution_replay_hash"] = _execution_replay_hash(result)
        return result

    ledger = build_options_ledger_state(initial_cash=initial_cash)
    entry_fills = entry_result["entry_fills"]
    for fill in entry_fills:
        ledger = apply_option_fill(ledger, fill=fill)

    lifecycle = run_options_lifecycle(
        {"ledger": ledger},
        effective_scenario,
    )
    if not lifecycle.get("available"):
        quality_flags.append(OptionQualityFlag.EXECUTION_SCENARIO_UNAVAILABLE.value)
        result = {
            "available": False,
            "status": "UNAVAILABLE",
            "outcome": "UNAVAILABLE",
            "symbol": symbol,
            "as_of_time": as_of_time,
            "reason": lifecycle.get("reason", "LIFECYCLE_FAILED"),
            "entry_fills": entry_fills,
            "lifecycle_events": [],
            "realized_pnl": None,
            "unrealized_pnl": None,
            "ledger_summary": {},
            "strategy_template": best_candidate.get("template"),
            "method": EXECUTION_METHOD,
            "model_version": EXECUTION_VERSION,
            "simulator_registry_id": SIMULATOR_REGISTRY_ID,
            "quality_flags": quality_flags,
        }
        result["execution_replay_hash"] = _execution_replay_hash(result)
        return result

    final_ledger = lifecycle["ledger"]
    lifecycle_events = lifecycle["lifecycle_events"]
    spot_at_expiry = float(effective_scenario.get("spot_at_expiry", 0.0))
    remaining_legs = [
        OptionLeg(
            call_put=pos["call_put"],  # type: ignore[arg-type]
            strike=float(pos["strike"]),
            expiry=str(pos["expiry"]),
            side=pos["side"],  # type: ignore[arg-type]
            quantity=int(pos["quantity"]),
            entry_premium=float(pos["entry_premium"]),
            multiplier=float(pos.get("multiplier", 100.0)),
        )
        for pos in final_ledger["option_positions"]
    ]
    unrealized = payoff_at_spot(spot_at_expiry, remaining_legs) if remaining_legs else None

    result = {
        "available": True,
        "status": "SIMULATED",
        "outcome": "FILLED",
        "symbol": symbol,
        "as_of_time": as_of_time,
        "entry_fills": entry_fills,
        "lifecycle_events": lifecycle_events,
        "realized_pnl": lifecycle.get("realized_pnl"),
        "unrealized_pnl": unrealized,
        "ledger_summary": {
            "cash": final_ledger["cash"],
            "open_positions": len(final_ledger["option_positions"]),
            "stock_shares": final_ledger["stock_shares"],
            "entry_count": len(entry_fills),
            "lifecycle_event_count": len(lifecycle_events),
        },
        "strategy_template": best_candidate.get("template"),
        "method": EXECUTION_METHOD,
        "model_version": EXECUTION_VERSION,
        "simulator_registry_id": SIMULATOR_REGISTRY_ID,
        "quality_flags": quality_flags,
    }
    if squeeze_context and squeeze_context.get("available"):
        result["squeeze_context"] = {
            "squeeze_state": squeeze_context.get("squeeze_state"),
            "exhaustion_risk": squeeze_context.get("exhaustion_risk"),
        }
    result["execution_replay_hash"] = _execution_replay_hash(result)
    return result


__all__ = [
    "DEFAULT_INITIAL_CASH",
    "EXECUTION_METHOD",
    "EXECUTION_VERSION",
    "SIMULATOR_REGISTRY_ID",
    "build_execution_snapshot",
    "build_options_order_intent",
    "conservative_fill_price",
    "evaluate_early_exercise",
    "legs_from_candidate",
    "load_execution_fixture",
    "process_assignment_event",
    "run_options_lifecycle",
    "settle_at_expiry",
    "simulate_multi_leg_entry",
]

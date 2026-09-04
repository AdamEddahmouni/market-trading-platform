"""Options O8 strategy optimizer — P vs Q template candidates and ranking."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from ..contracts.options_quality import OptionQualityFlag
from ..donor_patterns.options_lane import liquidity_gate
from .payoff import (
    PAYOFF_METHOD,
    OptionLeg,
    expected_pnl_under_physical_p,
    leg_to_dict,
)
from .surface import infer_underlying_price

STRATEGY_VERSION = "options_strategy_v1"
STRATEGY_METHOD = "P_VS_Q_TEMPLATE_RANK_V1"

DIRECTIONAL_EDGE_THRESHOLD = 0.005
VOL_EDGE_THRESHOLD = 0.02
TAIL_EDGE_THRESHOLD = 0.03
MIN_NET_EXPECTED_PNL = 0.0

NVDA_STRATEGY_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "providers"
    / "options"
    / "nvda_strategy_optimizer_slice.json"
)

CANDIDATE_TEMPLATES = (
    "long_call_atm",
    "bull_call_spread",
    "long_put_atm",
    "bear_put_spread",
    "long_straddle",
    "long_otm_call",
)


def load_strategy_optimizer_fixture(symbol: str) -> dict[str, Any] | None:
    """Load fixture strategy slice when symbol matches (fixture-first scope)."""
    if symbol.upper() != "NVDA" or not NVDA_STRATEGY_FIXTURE.is_file():
        return None
    payload = json.loads(NVDA_STRATEGY_FIXTURE.read_text(encoding="utf-8"))
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
    open_interest = int(row.get("open_interest", 0) or 0)
    underlying = row.get("underlying_price")
    spot_hint = float(underlying) if isinstance(underlying, (int, float)) else None
    return {
        "option_type": option_type,
        "expiry": str(expiry),
        "strike": strike,
        "bid": bid,
        "ask": ask,
        "open_interest": open_interest,
        "underlying_price": spot_hint,
        "multiplier": float(row.get("multiplier", 100) or 100),
    }


def _spot_from_rows(chain_rows: Sequence[dict[str, Any]]) -> float:
    for row in chain_rows:
        normalized = _normalize_row(row)
        if normalized and normalized.get("underlying_price"):
            return float(normalized["underlying_price"])
    for row in chain_rows:
        normalized = _normalize_row(row)
        if normalized:
            return infer_underlying_price(row, normalized["strike"], normalized["option_type"])
    return 0.0


def _rows_by_type(
    chain_rows: Sequence[dict[str, Any]],
    option_type: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in chain_rows:
        normalized = _normalize_row(row)
        if normalized and normalized["option_type"] == option_type:
            rows.append(normalized)
    return rows


def _nearest_expiry(rows: Sequence[dict[str, Any]]) -> str | None:
    expiries = sorted({row["expiry"] for row in rows if row.get("expiry")})
    return expiries[0] if expiries else None


def select_atm_contracts(
    chain_rows: Sequence[dict[str, Any]],
    spot: float | None = None,
) -> dict[str, Any]:
    """Deterministic closest-strike ATM call/put at nearest liquid expiry."""
    normalized_calls = _rows_by_type(chain_rows, "call")
    normalized_puts = _rows_by_type(chain_rows, "put")
    if not normalized_calls or not normalized_puts:
        return {
            "available": False,
            "reason": "ATM_CONTRACTS_MISSING",
        }

    effective_spot = spot if spot and spot > 0 else _spot_from_rows(chain_rows)
    if effective_spot <= 0:
        return {
            "available": False,
            "reason": "SPOT_UNAVAILABLE",
        }

    expiry = _nearest_expiry(normalized_calls + normalized_puts)
    calls = [row for row in normalized_calls if row["expiry"] == expiry]
    puts = [row for row in normalized_puts if row["expiry"] == expiry]
    if not calls or not puts:
        return {
            "available": False,
            "reason": "ATM_CONTRACTS_MISSING",
        }

    def _distance(row: dict[str, Any]) -> float:
        return abs(row["strike"] - effective_spot)

    atm_call = min(calls, key=_distance)
    atm_strike = atm_call["strike"]
    matching_puts = [row for row in puts if row["strike"] == atm_strike]
    atm_put = matching_puts[0] if matching_puts else min(puts, key=_distance)

    otm_calls = sorted(
        [row for row in calls if row["strike"] > atm_strike],
        key=lambda row: row["strike"],
    )
    otm_puts = sorted(
        [row for row in puts if row["strike"] < atm_strike],
        key=lambda row: row["strike"],
        reverse=True,
    )

    return {
        "available": True,
        "spot": effective_spot,
        "expiry": expiry,
        "atm_call": atm_call,
        "atm_put": atm_put,
        "otm_call": otm_calls[0] if otm_calls else None,
        "otm_put": otm_puts[0] if otm_puts else None,
    }


def _row_to_leg(
    row: dict[str, Any],
    *,
    side: str,
    quantity: int = 1,
) -> OptionLeg:
    mid = (row["bid"] + row["ask"]) / 2.0
    return OptionLeg(
        call_put=row["option_type"],
        strike=row["strike"],
        expiry=row["expiry"],
        side=side,  # type: ignore[arg-type]
        quantity=quantity,
        entry_premium=mid,
        multiplier=row.get("multiplier", 100.0),
    )


def build_candidate_legs(
    template: str,
    chain_rows: Sequence[dict[str, Any]],
    spot: float | None = None,
) -> dict[str, Any]:
    """Template to option legs — fail-closed when quotes missing."""
    selection = select_atm_contracts(chain_rows, spot=spot)
    if not selection.get("available"):
        return {
            "available": False,
            "template": template,
            "reason": selection.get("reason", "ATM_CONTRACTS_MISSING"),
        }

    effective_spot = float(selection["spot"])
    atm_call = selection["atm_call"]
    atm_put = selection["atm_put"]
    otm_call = selection.get("otm_call")
    otm_put = selection.get("otm_put")

    legs: list[OptionLeg] = []
    if template == "long_call_atm":
        legs = [_row_to_leg(atm_call, side="long")]
    elif template == "long_put_atm":
        legs = [_row_to_leg(atm_put, side="long")]
    elif template == "bull_call_spread":
        if otm_call is None:
            return {"available": False, "template": template, "reason": "OTM_CALL_MISSING"}
        legs = [
            _row_to_leg(atm_call, side="long"),
            _row_to_leg(otm_call, side="short"),
        ]
    elif template == "bear_put_spread":
        if otm_put is None:
            return {"available": False, "template": template, "reason": "OTM_PUT_MISSING"}
        legs = [
            _row_to_leg(atm_put, side="long"),
            _row_to_leg(otm_put, side="short"),
        ]
    elif template == "long_straddle":
        legs = [
            _row_to_leg(atm_call, side="long"),
            _row_to_leg(atm_put, side="long"),
        ]
    elif template == "long_otm_call":
        if otm_call is None:
            return {"available": False, "template": template, "reason": "OTM_CALL_MISSING"}
        legs = [_row_to_leg(otm_call, side="long")]
    else:
        return {"available": False, "template": template, "reason": "UNKNOWN_TEMPLATE"}

    return {
        "available": True,
        "template": template,
        "spot": effective_spot,
        "legs": legs,
    }


def _leg_liquidity_ok(row: dict[str, Any]) -> tuple[bool, list[str]]:
    return liquidity_gate(
        bid=row["bid"],
        ask=row["ask"],
        open_interest=row["open_interest"],
    )


def filter_candidates_by_liquidity(
    candidates: Sequence[dict[str, Any]],
    chain_rows: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Apply liquidity_gate per leg — multi-leg fails closed if any leg blocked."""
    filtered: list[dict[str, Any]] = []
    for candidate in candidates:
        if not candidate.get("available"):
            continue
        legs = candidate.get("legs", [])
        if not isinstance(legs, list) or not legs:
            continue
        liquidity_reasons: list[str] = []
        liquidity_ok = True
        for leg in legs:
            if not isinstance(leg, OptionLeg):
                liquidity_ok = False
                liquidity_reasons.append("INVALID_LEG")
                continue
            row = {
                "bid": leg.entry_premium,
                "ask": leg.entry_premium,
                "open_interest": 1000,
            }
            # Re-derive bid/ask from chain when possible; fallback uses mid with synthetic OI
            for source in chain_rows:
                normalized = _normalize_row(source)
                if (
                    normalized
                    and normalized["option_type"] == leg.call_put
                    and normalized["strike"] == leg.strike
                    and normalized["expiry"] == leg.expiry
                ):
                    row = normalized
                    break
            ok, reasons = _leg_liquidity_ok(row)
            if not ok:
                liquidity_ok = False
                liquidity_reasons.extend(reasons)
        if liquidity_ok:
            filtered.append(candidate)
        else:
            filtered.append(
                {
                    **candidate,
                    "available": False,
                    "reason": "STRATEGY_LIQUIDITY_BLOCKED",
                    "liquidity_reasons": sorted(set(liquidity_reasons)),
                    "quality_flags": [OptionQualityFlag.STRATEGY_LIQUIDITY_BLOCKED.value],
                }
            )
    return [row for row in filtered if row.get("available")]


def _edge_components(executable_edge: dict[str, Any] | None) -> dict[str, float | None]:
    if not executable_edge or not executable_edge.get("executable_available"):
        return {}
    exec_edge = executable_edge.get("executable_edge", {})
    if not isinstance(exec_edge, dict):
        return {}
    components = exec_edge.get("components", {})
    if not isinstance(components, dict):
        return {}
    result: dict[str, float | None] = {}
    for key in (
        "net_directional_edge",
        "net_volatility_edge",
        "skew_edge",
        "tail_edge",
        "downside_tail_edge",
    ):
        value = components.get(key)
        result[key] = float(value) if isinstance(value, (int, float)) else None
    return result


def _templates_for_edge(edge: dict[str, float | None]) -> list[str]:
    templates: list[str] = []
    directional = edge.get("net_directional_edge")
    vol_edge = edge.get("net_volatility_edge")
    tail_edge = edge.get("tail_edge")

    if isinstance(directional, (int, float)):
        if directional > DIRECTIONAL_EDGE_THRESHOLD:
            templates.extend(["long_call_atm", "bull_call_spread"])
        elif directional < -DIRECTIONAL_EDGE_THRESHOLD:
            templates.extend(["long_put_atm", "bear_put_spread"])
    if isinstance(vol_edge, (int, float)) and vol_edge > VOL_EDGE_THRESHOLD:
        templates.append("long_straddle")
    if isinstance(tail_edge, (int, float)) and tail_edge > TAIL_EDGE_THRESHOLD:
        templates.append("long_otm_call")
    return list(dict.fromkeys(templates))


def rank_candidates(
    candidates: Sequence[dict[str, Any]],
    physical_p: dict[str, Any] | None,
    friction: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Rank by net_expected_pnl — no universal score field."""
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        if not candidate.get("available"):
            continue
        legs = candidate.get("legs", [])
        if not isinstance(legs, list) or not legs:
            continue
        spot = float(candidate.get("spot", 0.0))
        payoff = expected_pnl_under_physical_p(
            physical_p,
            legs,
            spot=spot,
            friction=friction,
        )
        if not payoff.get("available"):
            continue
        ranked.append(
            {
                "template": candidate.get("template"),
                "edge_alignment": candidate.get("edge_alignment"),
                "legs": [leg_to_dict(leg) for leg in legs if isinstance(leg, OptionLeg)],
                "payoff": payoff,
                "net_expected_pnl": payoff.get("net_expected_pnl"),
            }
        )
    ranked.sort(
        key=lambda row: float(row.get("net_expected_pnl") or float("-inf")),
        reverse=True,
    )
    return ranked


def _replay_hash(payload: dict[str, Any]) -> str:
    canonical = {key: payload[key] for key in sorted(payload.keys()) if key != "replay_hash"}
    blob = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def build_strategy_snapshot(
    symbol: str,
    as_of_time: str,
    *,
    executable_edge: dict[str, Any] | None = None,
    physical_forecast: dict[str, Any] | None = None,
    chain_rows: Sequence[dict[str, Any]] | None = None,
    friction: dict[str, Any] | None = None,
    squeeze_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Top-level strategy optimizer snapshot for workspace payload."""
    del squeeze_context  # informational only in fixture scope — never auto-trigger trades
    quality_flags: list[str] = []

    effective_rows = list(chain_rows or [])
    fixture = load_strategy_optimizer_fixture(symbol)
    if not effective_rows and fixture:
        effective_rows = list(fixture.get("chain_rows", []))

    if not executable_edge or not executable_edge.get("executable_available"):
        quality_flags.append(OptionQualityFlag.STRATEGY_INPUTS_INCOMPLETE.value)
        return {
            "available": False,
            "status": "UNAVAILABLE",
            "outcome": "NO_CLEAR_EDGE",
            "symbol": symbol,
            "as_of_time": as_of_time,
            "reason": "EXECUTABLE_EDGE_UNAVAILABLE",
            "ranked_candidates": [],
            "best_candidate": None,
            "edge_summary": {},
            "method": STRATEGY_METHOD,
            "model_version": STRATEGY_VERSION,
            "quality_flags": quality_flags,
        }

    if not physical_forecast or not effective_rows:
        quality_flags.append(OptionQualityFlag.STRATEGY_INPUTS_INCOMPLETE.value)
        return {
            "available": False,
            "status": "UNAVAILABLE",
            "outcome": "NO_CLEAR_EDGE",
            "symbol": symbol,
            "as_of_time": as_of_time,
            "reason": "PHYSICAL_P_OR_CHAIN_UNAVAILABLE",
            "ranked_candidates": [],
            "best_candidate": None,
            "edge_summary": {},
            "method": STRATEGY_METHOD,
            "model_version": STRATEGY_VERSION,
            "quality_flags": quality_flags,
        }

    edge_summary = _edge_components(executable_edge)
    templates = _templates_for_edge(edge_summary)
    if not templates:
        quality_flags.append(OptionQualityFlag.STRATEGY_NO_EDGE.value)
        result = {
            "available": True,
            "status": "NO_CLEAR_EDGE",
            "outcome": "NO_CLEAR_EDGE",
            "symbol": symbol,
            "as_of_time": as_of_time,
            "reason": "EDGE_BELOW_THRESHOLDS",
            "ranked_candidates": [],
            "best_candidate": None,
            "edge_summary": edge_summary,
            "method": STRATEGY_METHOD,
            "model_version": STRATEGY_VERSION,
            "quality_flags": quality_flags,
        }
        result["replay_hash"] = _replay_hash(result)
        return result

    spot = _spot_from_rows(effective_rows)
    raw_candidates: list[dict[str, Any]] = []
    for template in templates:
        built = build_candidate_legs(template, effective_rows, spot=spot)
        if built.get("available"):
            built["edge_alignment"] = template
            raw_candidates.append(built)

    liquid_candidates = filter_candidates_by_liquidity(raw_candidates, effective_rows)
    if not liquid_candidates:
        quality_flags.append(OptionQualityFlag.STRATEGY_LIQUIDITY_BLOCKED.value)
        result = {
            "available": True,
            "status": "NO_CLEAR_EDGE",
            "outcome": "NO_CLEAR_EDGE",
            "symbol": symbol,
            "as_of_time": as_of_time,
            "reason": "ALL_CANDIDATES_LIQUIDITY_BLOCKED",
            "ranked_candidates": [],
            "best_candidate": None,
            "edge_summary": edge_summary,
            "method": STRATEGY_METHOD,
            "model_version": STRATEGY_VERSION,
            "quality_flags": quality_flags,
        }
        result["replay_hash"] = _replay_hash(result)
        return result

    ranked = rank_candidates(liquid_candidates, physical_forecast, friction)
    positive_ranked = [
        row
        for row in ranked
        if isinstance(row.get("net_expected_pnl"), (int, float))
        and float(row["net_expected_pnl"]) > MIN_NET_EXPECTED_PNL
    ]

    if not positive_ranked:
        quality_flags.append(OptionQualityFlag.STRATEGY_NO_EDGE.value)
        result = {
            "available": True,
            "status": "NO_CLEAR_EDGE",
            "outcome": "NO_CLEAR_EDGE",
            "symbol": symbol,
            "as_of_time": as_of_time,
            "reason": "NET_EXPECTED_PNL_NOT_POSITIVE",
            "ranked_candidates": ranked,
            "best_candidate": None,
            "edge_summary": edge_summary,
            "method": STRATEGY_METHOD,
            "model_version": STRATEGY_VERSION,
            "quality_flags": quality_flags,
            "payoff_method": PAYOFF_METHOD,
        }
        result["replay_hash"] = _replay_hash(result)
        return result

    best_candidate = positive_ranked[0]
    result = {
        "available": True,
        "status": "RANKED",
        "outcome": "RANKED",
        "symbol": symbol,
        "as_of_time": as_of_time,
        "ranked_candidates": positive_ranked,
        "best_candidate": best_candidate,
        "edge_summary": edge_summary,
        "method": STRATEGY_METHOD,
        "model_version": STRATEGY_VERSION,
        "quality_flags": quality_flags,
        "payoff_method": PAYOFF_METHOD,
    }
    result["replay_hash"] = _replay_hash(result)
    return result


__all__ = [
    "CANDIDATE_TEMPLATES",
    "STRATEGY_METHOD",
    "STRATEGY_VERSION",
    "build_candidate_legs",
    "build_strategy_snapshot",
    "filter_candidates_by_liquidity",
    "load_strategy_optimizer_fixture",
    "rank_candidates",
    "select_atm_contracts",
]

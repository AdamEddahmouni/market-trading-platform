"""Options O7 event volatility — earnings state machine, implied move, IV crush."""

from __future__ import annotations

import json
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

from ..contracts.options_quality import OptionQualityFlag
from ..contracts.reference import ReferenceKind, ReferenceQualityFlag
from ..runtime.bitemporal_store import BitemporalReferenceStore
from ..runtime.pit_joins import join_as_of
from .surface import build_surface_point, infer_underlying_price

EVENT_VOL_VERSION = "options_event_vol_v1"
EVENT_VOL_METHOD = "EARNINGS_STRADDLE_EMPIRICAL_V1"

DEFAULT_APPROACHING_DAYS = 14
DEFAULT_IMMINENT_HOURS = 48
DEFAULT_RESOLUTION_HOURS = 24
DEFAULT_NORMALIZATION_DAYS = 7

EXHAUSTION_CRUSH_BOOST = 1.15
EXHAUSTION_RISK_THRESHOLD = 70

EVENT_VOL_PREMIUM_THRESHOLD = 0.02
IV_CRUSH_RISK_THRESHOLD = 0.05

NVDA_EARNINGS_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "providers"
    / "options"
    / "nvda_earnings_event_slice.json"
)


def _parse_event_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def classify_event_state(
    as_of_time: str,
    event_time: str | None,
    *,
    approaching_days: int = DEFAULT_APPROACHING_DAYS,
    imminent_hours: int = DEFAULT_IMMINENT_HOURS,
    resolution_hours: int = DEFAULT_RESOLUTION_HOURS,
    normalization_days: int = DEFAULT_NORMALIZATION_DAYS,
) -> str:
    """Deterministic earnings event state from PIT timestamps."""
    if not event_time:
        return "NO_EVENT"
    anchor = _parse_event_time(as_of_time)
    event = _parse_event_time(event_time)
    if anchor is None or event is None:
        return "NO_EVENT"

    delta_seconds = (event - anchor).total_seconds()
    if delta_seconds > approaching_days * 86400:
        return "NO_EVENT"
    if delta_seconds > imminent_hours * 3600:
        return "EVENT_APPROACHING"
    if delta_seconds > 0:
        return "EVENT_IMMINENT"
    if delta_seconds >= -resolution_hours * 3600:
        return "EVENT_RESOLUTION"
    if delta_seconds >= -normalization_days * 86400:
        return "POST_EVENT_NORMALIZATION"
    return "NO_EVENT"


def _select_atm_straddle(
    chain_rows: Sequence[dict[str, Any]],
    *,
    event_expiry: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, float]:
    """Pick ATM call+put at event expiry — deterministic closest strike to spot."""
    calls: list[dict[str, Any]] = []
    puts: list[dict[str, Any]] = []
    spot_hint: float | None = None

    for row in chain_rows:
        if not isinstance(row, dict):
            continue
        option_type = str(row.get("option_type", row.get("call_put", ""))).lower()
        expiry = str(row.get("expiry", row.get("expiration", "")))
        if event_expiry and expiry != event_expiry:
            continue
        bid = float(row.get("bid", 0.0) or 0.0)
        ask = float(row.get("ask", 0.0) or 0.0)
        if bid <= 0 or ask <= 0:
            continue
        strike_raw = row.get("strike")
        if strike_raw is None:
            continue
        try:
            strike = float(strike_raw)
        except (TypeError, ValueError):
            continue
        underlying = row.get("underlying_price")
        if isinstance(underlying, (int, float)) and underlying > 0:
            spot_hint = float(underlying)
        if option_type == "call":
            calls.append(row)
        elif option_type == "put":
            puts.append(row)

    if not calls or not puts:
        return None, None, spot_hint or 0.0

    spot = spot_hint
    if spot is None or spot <= 0:
        sample = calls[0]
        spot = infer_underlying_price(sample, float(sample.get("strike", 0)), "call")

    def _strike_distance(row: dict[str, Any]) -> float:
        return abs(float(row.get("strike", 0)) - spot)

    atm_call = min(calls, key=_strike_distance)
    atm_strike = float(atm_call.get("strike", 0))
    matching_puts = [row for row in puts if float(row.get("strike", 0)) == atm_strike]
    if not matching_puts:
        atm_put = min(puts, key=_strike_distance)
    else:
        atm_put = matching_puts[0]
    return atm_call, atm_put, spot


def estimate_implied_event_move(
    chain_rows: Sequence[dict[str, Any]],
    *,
    event_expiry: str | None = None,
) -> dict[str, Any]:
    """ATM straddle % move from mid prices."""
    call_row, put_row, spot = _select_atm_straddle(chain_rows, event_expiry=event_expiry)
    if call_row is None or put_row is None or spot <= 0:
        return {
            "available": False,
            "reason": "STRADDLE_QUOTES_MISSING",
            "quality_flags": [OptionQualityFlag.STRADDLE_QUOTES_MISSING.value],
        }

    call_mid = (float(call_row["bid"]) + float(call_row["ask"])) / 2.0
    put_mid = (float(put_row["bid"]) + float(put_row["ask"])) / 2.0
    straddle_mid = call_mid + put_mid
    implied_move_pct = round((straddle_mid / spot) * 100.0, 6)

    call_surface = build_surface_point(call_row)
    put_surface = build_surface_point(put_row)
    pre_iv: float | None = None
    if call_surface and put_surface:
        call_iv = call_surface.get("internal_iv")
        put_iv = put_surface.get("internal_iv")
        if isinstance(call_iv, (int, float)) and isinstance(put_iv, (int, float)):
            pre_iv = round((float(call_iv) + float(put_iv)) / 2.0, 6)

    return {
        "available": True,
        "implied_event_move": implied_move_pct,
        "straddle_mid": round(straddle_mid, 6),
        "spot": round(spot, 6),
        "atm_strike": float(call_row.get("strike", 0)),
        "pre_iv": pre_iv,
        "method": EVENT_VOL_METHOD,
    }


def estimate_iv_crush(
    pre_iv: float | None,
    post_iv_history: Sequence[dict[str, Any]] | None,
    *,
    squeeze_context: dict[str, Any] | None = None,
    event_state: str = "NO_EVENT",
) -> dict[str, Any]:
    """Empirical IV crush from fixture history; exhaustion boosts crush (JQ-6)."""
    if pre_iv is None or pre_iv <= 0:
        return {
            "available": False,
            "reason": "PRE_IV_MISSING",
            "expected_iv_crush": None,
            "expected_post_event_iv": None,
        }

    history = [row for row in (post_iv_history or []) if isinstance(row, dict)]
    crush_ratios: list[float] = []
    for row in history:
        row_pre = row.get("pre_iv")
        row_post = row.get("post_iv")
        if isinstance(row_pre, (int, float)) and isinstance(row_post, (int, float)):
            if row_pre > 0:
                crush_ratios.append((float(row_pre) - float(row_post)) / float(row_pre))

    if not crush_ratios:
        return {
            "available": False,
            "reason": "CRUSH_HISTORY_MISSING",
            "expected_iv_crush": None,
            "expected_post_event_iv": None,
            "status": "RESEARCH_PROXY",
            "quality_flags": [OptionQualityFlag.POST_EVENT_IV_UNAVAILABLE.value],
        }

    crush_ratio = statistics.median(crush_ratios)
    exhaustion_risk = None
    if squeeze_context and squeeze_context.get("available"):
        exhaustion_risk = squeeze_context.get("exhaustion_risk")
    if (
        isinstance(exhaustion_risk, (int, float))
        and exhaustion_risk >= EXHAUSTION_RISK_THRESHOLD
        and event_state in {"EVENT_RESOLUTION", "POST_EVENT_NORMALIZATION"}
    ):
        crush_ratio = min(crush_ratio * EXHAUSTION_CRUSH_BOOST, 0.95)

    expected_crush = round(pre_iv * crush_ratio, 6)
    expected_post_iv = round(max(pre_iv - expected_crush, 0.0), 6)
    status = "CALIBRATED" if len(crush_ratios) >= 3 else "RESEARCH_PROXY"

    return {
        "available": True,
        "expected_iv_crush": expected_crush,
        "expected_post_event_iv": expected_post_iv,
        "crush_ratio_median": round(crush_ratio, 6),
        "history_sample_count": len(crush_ratios),
        "exhaustion_boost_applied": (
            isinstance(exhaustion_risk, (int, float)) and exhaustion_risk >= EXHAUSTION_RISK_THRESHOLD
        ),
        "status": status,
        "method": EVENT_VOL_METHOD,
    }


def _forecast_event_move(physical_forecast: dict[str, Any] | None) -> float | None:
    if not physical_forecast or not isinstance(physical_forecast, dict):
        return None
    vol = physical_forecast.get("vol_forecast_annualized")
    if not isinstance(vol, (int, float)) or vol <= 0:
        return None
    # One-day move scale from annualized vol (research proxy, not trade signal).
    daily_move = float(vol) / (252.0 ** 0.5)
    return round(daily_move * 100.0, 6)


def _vega_risk_label(
    *,
    event_state: str,
    expected_iv_crush: float | None,
    pre_iv: float | None,
) -> str:
    if event_state in {"NO_EVENT", "EVENT_APPROACHING"}:
        return "LOW"
    if expected_iv_crush is None or pre_iv is None or pre_iv <= 0:
        return "MODERATE" if event_state in {"EVENT_IMMINENT", "EVENT_RESOLUTION"} else "LOW"
    crush_fraction = expected_iv_crush / pre_iv
    if event_state in {"EVENT_IMMINENT", "EVENT_RESOLUTION"} and crush_fraction >= IV_CRUSH_RISK_THRESHOLD:
        return "HIGH"
    if event_state == "POST_EVENT_NORMALIZATION":
        return "MODERATE"
    return "MODERATE"


def load_earnings_event_fixture(
    symbol: str,
    *,
    fixture_path: Path | None = None,
) -> dict[str, Any] | None:
    """Load admitted earnings event fixture for symbol — fail-closed when missing."""
    path = fixture_path or NVDA_EARNINGS_FIXTURE
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    if str(payload.get("symbol", "")).upper() != symbol.upper():
        return None
    return payload


def build_event_vol_snapshot(
    symbol: str,
    as_of_time: str,
    *,
    chain_rows: Sequence[dict[str, Any]] | None = None,
    earnings_event: dict[str, Any] | None = None,
    physical_forecast: dict[str, Any] | None = None,
    squeeze_context: dict[str, Any] | None = None,
    empirical_crush_history: Sequence[dict[str, Any]] | None = None,
    post_event_chain: Sequence[dict[str, Any]] | None = None,
    catalyst_event_times: Sequence[str] | None = None,
    reference_store: BitemporalReferenceStore | None = None,
    knowledge_time: str | None = None,
) -> dict[str, Any]:
    """Top-level event volatility snapshot for workspace consumers."""
    quality_flags: list[str] = []
    event_time: str | None = None
    event_type: str | None = None
    event_expiry: str | None = None

    if earnings_event and isinstance(earnings_event, dict):
        event_time = earnings_event.get("earnings_event_time") or earnings_event.get("event_time")
        event_type = str(earnings_event.get("event_type", "earnings"))
        event_expiry = earnings_event.get("event_expiry")
        if empirical_crush_history is None:
            empirical_crush_history = earnings_event.get("empirical_crush_history")
        if post_event_chain is None:
            post_event_chain = earnings_event.get("post_event_chain")
        if chain_rows is None:
            chain_rows = earnings_event.get("pre_event_chain")

    if not event_time and reference_store is not None:
        joined = join_as_of(
            reference_store,
            ReferenceKind.EARNINGS_CALENDAR,
            symbol.upper(),
            as_of_time,
            knowledge_time or as_of_time,
        )
        if joined["status"] == "AVAILABLE":
            event_time = str(joined["payload"].get("earnings_event_time") or "")
            event_type = str(joined["payload"].get("event_type", "earnings"))
            quality_flags.extend(str(flag) for flag in joined.get("quality_flags") or [])
        else:
            quality_flags.append(OptionQualityFlag.EARNINGS_DATE_UNKNOWN.value)
            quality_flags.append(ReferenceQualityFlag.REFERENCE_UNAVAILABLE.value)
            quality_flags.extend(str(flag) for flag in joined.get("quality_flags") or [])
            return {
                "available": False,
                "status": "UNAVAILABLE",
                "event_type": None,
                "event_state": "NO_EVENT",
                "event_time": None,
                "implied_event_move": None,
                "forecast_event_move": None,
                "event_volatility_premium": None,
                "expected_post_event_iv": None,
                "expected_iv_crush": None,
                "vega_risk": "LOW",
                "method": EVENT_VOL_METHOD,
                "model_version": EVENT_VOL_VERSION,
                "quality_flags": quality_flags,
                "reason": "EARNINGS_DATE_UNKNOWN",
            }

    if not event_time and catalyst_event_times:
        for raw in catalyst_event_times:
            if raw:
                event_time = str(raw)
                event_type = event_type or "earnings"
                break

    if not event_time:
        quality_flags.append(OptionQualityFlag.EARNINGS_DATE_UNKNOWN.value)
        return {
            "available": False,
            "status": "UNAVAILABLE",
            "event_type": None,
            "event_state": "NO_EVENT",
            "event_time": None,
            "implied_event_move": None,
            "forecast_event_move": None,
            "event_volatility_premium": None,
            "expected_post_event_iv": None,
            "expected_iv_crush": None,
            "vega_risk": "LOW",
            "method": EVENT_VOL_METHOD,
            "model_version": EVENT_VOL_VERSION,
            "quality_flags": quality_flags,
            "reason": "EARNINGS_DATE_UNKNOWN",
        }

    event_state = classify_event_state(as_of_time, str(event_time))
    rows = list(chain_rows or [])
    implied = estimate_implied_event_move(rows, event_expiry=str(event_expiry) if event_expiry else None)
    if not implied.get("available") and earnings_event:
        fallback_rows = earnings_event.get("pre_event_chain")
        if isinstance(fallback_rows, list) and fallback_rows:
            implied = estimate_implied_event_move(
                fallback_rows,
                event_expiry=str(event_expiry) if event_expiry else None,
            )
    if not implied.get("available"):
        quality_flags.extend(implied.get("quality_flags", []))

    pre_iv = implied.get("pre_iv")
    post_iv: float | None = None
    if post_event_chain and event_state in {"EVENT_RESOLUTION", "POST_EVENT_NORMALIZATION"}:
        post_implied = estimate_implied_event_move(list(post_event_chain), event_expiry=str(event_expiry) if event_expiry else None)
        if post_implied.get("available"):
            post_iv = post_implied.get("pre_iv")

    crush = estimate_iv_crush(
        float(pre_iv) if isinstance(pre_iv, (int, float)) else None,
        empirical_crush_history,
        squeeze_context=squeeze_context,
        event_state=event_state,
    )
    if post_iv is not None and isinstance(pre_iv, (int, float)):
        crush = {
            **crush,
            "available": True,
            "expected_iv_crush": round(float(pre_iv) - float(post_iv), 6),
            "expected_post_event_iv": round(float(post_iv), 6),
            "observed_post_event_iv": round(float(post_iv), 6),
            "status": "CALIBRATED",
        }
    elif not crush.get("available"):
        quality_flags.extend(crush.get("quality_flags", []))

    forecast_move = _forecast_event_move(physical_forecast)
    implied_move = implied.get("implied_event_move")
    event_vol_premium: float | None = None
    if isinstance(implied_move, (int, float)) and isinstance(forecast_move, (int, float)):
        event_vol_premium = round(float(implied_move) - float(forecast_move), 6)

    status = "UNAVAILABLE"
    if implied.get("available") and crush.get("available"):
        status = str(crush.get("status", "RESEARCH_PROXY"))
    elif implied.get("available"):
        status = "RESEARCH_PROXY"

    vega_risk = _vega_risk_label(
        event_state=event_state,
        expected_iv_crush=crush.get("expected_iv_crush") if isinstance(crush.get("expected_iv_crush"), (int, float)) else None,
        pre_iv=float(pre_iv) if isinstance(pre_iv, (int, float)) else None,
    )

    return {
        "available": implied.get("available", False) or crush.get("available", False),
        "status": status,
        "event_type": event_type,
        "event_state": event_state,
        "event_time": str(event_time),
        "implied_event_move": implied_move,
        "forecast_event_move": forecast_move,
        "event_volatility_premium": event_vol_premium,
        "expected_post_event_iv": crush.get("expected_post_event_iv"),
        "expected_iv_crush": crush.get("expected_iv_crush"),
        "pre_iv": pre_iv,
        "vega_risk": vega_risk,
        "method": EVENT_VOL_METHOD,
        "model_version": EVENT_VOL_VERSION,
        "quality_flags": quality_flags,
        "exhaustion_boost_applied": crush.get("exhaustion_boost_applied", False),
        "not_trade_signal": True,
    }


__all__ = [
    "EVENT_VOL_METHOD",
    "EVENT_VOL_VERSION",
    "IV_CRUSH_RISK_THRESHOLD",
    "NVDA_EARNINGS_FIXTURE",
    "build_event_vol_snapshot",
    "classify_event_state",
    "estimate_implied_event_move",
    "estimate_iv_crush",
    "load_earnings_event_fixture",
]

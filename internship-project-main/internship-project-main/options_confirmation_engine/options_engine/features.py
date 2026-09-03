"""Feature engineering for options confirmation signals (v2).

Purpose
-------
Single entry point that assembles the full feature dict from a ``Snapshot`` plus
local snapshot history (IV rank, flow trend slope).

Features / API role
-------------------
Directional: ``call_volume_share``, ``put_call_volume_ratio``, ``put_call_oi_ratio``,
``net_delta_oi``, ``iv_skew``. Informational: ``atm_iv``, ``iv_rank``, OI walls.
Delegates 0DTE modules: GEX, max pain, liquidity, flow trend, TOD, regime.
Emits ``*_available`` flags so ``scoring`` can renormalize weights when inputs
are missing (e.g. no greeks on yfinance).

How ``news_momentum_agent`` consumes it
---------------------------------------
Invoked inside ``runner.run_ticker``; feature dict is returned on scored items as
``features`` / ``feature_values``. ``evaluation/spy_qqq_replay`` and
``evaluation/odte_backtest`` call ``compute_features`` on replay/historical
snapshots. ``odte_decision`` inspects liquidity keys from the merged dict.

Options-specific vs reusable
----------------------------
Options-specific: PCR, skew, delta-weighted OI, max pain, GEX. Reusable: history
lookback helpers and the composable sub-module pattern (one file per factor).
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any, Dict, List, Tuple

from options_engine.data_models import ContractRow, Snapshot
from options_engine.features_flow_trend import compute_flow_trend_features
from options_engine.features_gex import compute_gex_features
from options_engine.features_liquidity import compute_liquidity_features
from options_engine.features_max_pain import compute_max_pain_features
from options_engine.features_regime import compute_regime_features
from options_engine.features_tod import compute_tod_features


def _parse_expiration(expiration: str) -> datetime | None:
    text = str(expiration or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" and len(text) >= 10 else text, fmt).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            continue
    return None


def _nearest_dte(contracts: List[ContractRow], as_of: str | None = None) -> float:
    """Minimum days-to-expiry among contracts with open interest."""
    now = datetime.now(timezone.utc)
    if as_of:
        try:
            now = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    dtes: List[int] = []
    for row in contracts:
        if row.open_interest <= 0:
            continue
        exp = _parse_expiration(row.expiration)
        if exp is None:
            continue
        days = (exp.date() - now.date()).days
        if days >= 0:
            dtes.append(days)
    return float(min(dtes)) if dtes else -1.0


def _max_oi_strike_features(contracts: List[ContractRow], spot: float) -> Tuple[float, float, float]:
    """Return (max_oi_strike, pct_from_spot, total_oi_at_strike)."""
    by_strike: Dict[float, float] = {}
    for row in contracts:
        by_strike[row.strike] = by_strike.get(row.strike, 0.0) + float(row.open_interest)
    if not by_strike:
        return 0.0, 0.0, 0.0
    strike, oi = max(by_strike.items(), key=lambda item: item[1])
    pct = ((strike - spot) / spot * 100.0) if spot > 0 else 0.0
    return float(strike), float(pct), float(oi)


def _historical_volume_avg(history: List[Dict[str, Any]], lookback_days: int) -> float:
    volumes: List[float] = []
    for item in history[: max(1, lookback_days)]:
        if not isinstance(item, dict):
            continue
        cache = item.get("feature_cache", {})
        if not isinstance(cache, dict):
            continue
        try:
            vol = float(cache.get("total_volume", 0.0))
            if vol > 0:
                volumes.append(vol)
        except (TypeError, ValueError):
            continue
    return mean(volumes) if volumes else 0.0


def _split_contracts(contracts: List[ContractRow]) -> Tuple[List[ContractRow], List[ContractRow]]:
    calls = [row for row in contracts if row.side == "call"]
    puts = [row for row in contracts if row.side == "put"]
    return calls, puts


def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if denominator == 0:
        return default
    return float(numerator) / float(denominator)


def _atm_contracts(contracts: List[ContractRow], spot_price: float, band_pct: float) -> List[ContractRow]:
    if spot_price <= 0:
        return []
    lower = spot_price * (1 - band_pct)
    upper = spot_price * (1 + band_pct)
    return [row for row in contracts if lower <= row.strike <= upper]


def _extract_prev_iv(history: List[Dict[str, Any]]) -> float:
    if len(history) < 2:
        return 0.0
    prev = history[1]
    return float(prev.get("feature_cache", {}).get("atm_iv", 0.0)) if isinstance(prev, dict) else 0.0


def _extract_iv_series(history: List[Dict[str, Any]], lookback_days: int) -> List[float]:
    values: List[float] = []
    for item in history[: max(1, lookback_days)]:
        try:
            iv = float(item.get("feature_cache", {}).get("atm_iv", 0.0))
            if iv > 0:
                values.append(iv)
        except Exception:
            continue
    return values


def _has_greeks(contracts: List[ContractRow]) -> bool:
    return any(abs(row.delta) > 0 for row in contracts)


def _otm_iv_by_delta(
    calls: List[ContractRow],
    puts: List[ContractRow],
    low: float,
    high: float,
) -> Tuple[float, float, bool]:
    """Mean OTM call/put IV selected by |delta| band (e.g. 0.15-0.35)."""
    otm_calls = [c for c in calls if low <= c.delta <= high and c.implied_volatility > 0]
    otm_puts = [p for p in puts if -high <= p.delta <= -low and p.implied_volatility > 0]
    if not otm_calls or not otm_puts:
        return 0.0, 0.0, False
    return (
        mean([c.implied_volatility for c in otm_calls]),
        mean([p.implied_volatility for p in otm_puts]),
        True,
    )


def _otm_iv_by_strike(
    calls: List[ContractRow],
    puts: List[ContractRow],
    spot: float,
) -> Tuple[float, float, bool]:
    """Fallback OTM call/put IV by moneyness band when greeks are unavailable."""
    if spot <= 0:
        return 0.0, 0.0, False
    otm_calls = [c for c in calls if spot * 1.02 <= c.strike <= spot * 1.10 and c.implied_volatility > 0]
    otm_puts = [p for p in puts if spot * 0.90 <= p.strike <= spot * 0.98 and p.implied_volatility > 0]
    if not otm_calls or not otm_puts:
        return 0.0, 0.0, False
    return (
        mean([c.implied_volatility for c in otm_calls]),
        mean([p.implied_volatility for p in otm_puts]),
        True,
    )


def compute_features(snapshot: Snapshot, history: List[Dict[str, Any]], settings: Dict[str, Any]) -> Dict[str, float]:
    """Compute the v2 directional feature set from a snapshot and local history."""
    features_cfg = settings.get("features", {})
    band_pct = float(features_cfg.get("atm_strike_band_pct", 0.03))
    iv_lookback = int(features_cfg.get("iv_rank_lookback_days", 60))
    skew_low = float(features_cfg.get("skew_delta_low", 0.15))
    skew_high = float(features_cfg.get("skew_delta_high", 0.35))

    calls, puts = _split_contracts(snapshot.contracts)
    call_volume = sum(row.volume for row in calls)
    put_volume = sum(row.volume for row in puts)
    call_oi = sum(row.open_interest for row in calls)
    put_oi = sum(row.open_interest for row in puts)
    total_volume = call_volume + put_volume
    total_oi = call_oi + put_oi

    # --- Directional: order flow ---
    put_call_volume_ratio = _safe_div(put_volume, call_volume, default=1.0)
    call_volume_share = _safe_div(call_volume, total_volume, default=0.5)

    # --- Directional: standing positioning ---
    put_call_oi_ratio = _safe_div(put_oi, call_oi, default=1.0)

    # --- Directional: delta-weighted OI exposure ---
    greeks = _has_greeks(snapshot.contracts)
    net_delta_oi = (
        _safe_div(sum(row.delta * row.open_interest for row in snapshot.contracts), total_oi, default=0.0)
        if greeks
        else 0.0
    )

    # --- Directional: implied-volatility skew (fear vs greed) ---
    if greeks:
        call_iv, put_iv, skew_ok = _otm_iv_by_delta(calls, puts, skew_low, skew_high)
    else:
        call_iv, put_iv, skew_ok = _otm_iv_by_strike(calls, puts, snapshot.spot_price)
    iv_skew = (put_iv - call_iv) if skew_ok else 0.0

    # --- Regime / level (informational, history-dependent) ---
    atm_rows = _atm_contracts(snapshot.contracts, snapshot.spot_price, band_pct)
    atm_iv = mean([row.implied_volatility for row in atm_rows]) if atm_rows else 0.0
    prev_iv = _extract_prev_iv(history)
    iv_change = atm_iv - prev_iv if prev_iv > 0 else 0.0

    iv_series = _extract_iv_series(history, iv_lookback)
    if atm_iv > 0:
        iv_series = [atm_iv] + iv_series
    iv_rank = 0.5
    if iv_series:
        iv_min, iv_max = min(iv_series), max(iv_series)
        iv_rank = _safe_div(atm_iv - iv_min, iv_max - iv_min, default=0.5) if iv_max != iv_min else 0.5

    near_spot_oi = sum(row.open_interest for row in atm_rows)
    nearest_dte = _nearest_dte(snapshot.contracts, snapshot.as_of)
    max_oi_strike, max_oi_strike_pct_from_spot, max_oi_at_strike = _max_oi_strike_features(
        snapshot.contracts, snapshot.spot_price
    )
    lookback_days = int(features_cfg.get("lookback_days_for_averages", 20))
    hist_avg_volume = _historical_volume_avg(history, lookback_days)
    volume_oi_spike = (
        _safe_div(total_volume, hist_avg_volume, default=0.0)
        if hist_avg_volume > 0
        else _safe_div(total_volume, total_oi, default=0.0)
    )

    # --- 0DTE-oriented modules (each toggleable via settings.odte_signals) ---
    gex_feats = compute_gex_features(snapshot, settings)
    max_pain_feats = compute_max_pain_features(snapshot, settings)
    liquidity_feats = compute_liquidity_features(snapshot, settings)
    flow_feats = compute_flow_trend_features(
        call_volume_share=call_volume_share,
        put_call_volume_ratio=put_call_volume_ratio,
        as_of=snapshot.as_of,
        history=history,
        settings=settings,
    )
    tod_feats = compute_tod_features(settings, as_of=snapshot.as_of)
    # Regime uses live index/VIX by default; tests can pre-seed via settings override.
    regime_seed = settings.get("_regime_seed") if isinstance(settings.get("_regime_seed"), dict) else {}
    regime_feats = compute_regime_features(
        settings,
        vix=regime_seed.get("vix"),
        spy_pct=regime_seed.get("spy_pct"),
        qqq_pct=regime_seed.get("qqq_pct"),
    )

    # IV rank as a soft "rich premium" penalty input (0..1 already).
    iv_rank_penalty = max(0.0, float(iv_rank) - 0.5) * 2.0  # 0 at median, 1 at top of range

    return {
        # directional
        "put_call_volume_ratio": put_call_volume_ratio,
        "call_volume_share": call_volume_share,
        "put_call_oi_ratio": put_call_oi_ratio,
        "net_delta_oi": net_delta_oi,
        "iv_skew": iv_skew,
        # availability flags for weight renormalization
        "greeks_available": 1.0 if greeks else 0.0,
        "iv_skew_available": 1.0 if skew_ok else 0.0,
        "volume_available": 1.0 if total_volume > 0 else 0.0,
        "oi_available": 1.0 if total_oi > 0 else 0.0,
        # regime / informational
        "atm_iv": atm_iv,
        "atm_iv_change": iv_change,
        "iv_rank": iv_rank,
        "iv_rank_penalty": iv_rank_penalty,
        "oi_near_spot_concentration": _safe_div(near_spot_oi, total_oi, default=0.0),
        "volume_to_oi_spike": _safe_div(total_volume, total_oi, default=0.0),
        # Path B / expiry features
        "nearest_dte": nearest_dte,
        "max_oi_strike": max_oi_strike,
        "max_oi_strike_pct_from_spot": max_oi_strike_pct_from_spot,
        "max_oi_at_strike": max_oi_at_strike,
        "total_oi": float(total_oi),
        "total_volume": float(total_volume),
        "volume_oi_spike": volume_oi_spike,
        # 0DTE extensions
        **gex_feats,
        **max_pain_feats,
        **liquidity_feats,
        **flow_feats,
        **tod_feats,
        **regime_feats,
    }

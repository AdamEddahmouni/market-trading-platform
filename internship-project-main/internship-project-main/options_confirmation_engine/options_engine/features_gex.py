"""Dealer gamma exposure (GEX) estimates from the options chain.

Purpose
-------
Estimate net dealer gamma near spot from chain IV/OI and classify pin vs trend regime.

Features / API role
-------------------
``compute_gex_features`` → ``net_dealer_gex``, ``gex_regime_code``, ``gex_available``.
``black_scholes_gamma`` and ``gex_regime_label`` are public helpers for tests/docs.

How ``news_momentum_agent`` consumes it
---------------------------------------
Merged into ``features`` on scored items; ``scoring._apply_gex_regime_modulation``
post-processes the weighted score (not a weighted sub-score placeholder).

Options-specific vs reusable
----------------------------
Options-specific dealer-short sign convention and 0DTE gamma proxy. Reusable:
Black–Scholes gamma utility for any chain-based research.

Academic / internship note
--------------------------
We do **not** call a proprietary GEX API. Instead we estimate Black–Scholes
gamma from each contract's IV, strike, spot, and time-to-expiry, then aggregate
under the standard retail-dealer assumption:

    dealers are net short customer flow ⇒
    call GEX contributes negatively to dealer gamma,
    put GEX contributes positively
    (SpotGamma-style sign convention for "net dealer gamma").

Positive net dealer GEX ⇒ mean-revert / pin regime.
Negative net dealer GEX ⇒ trend / breakout regime.

When gamma inputs are missing (no IV), ``gex_available`` is 0.0 so scorers
can drop the factor without biasing toward neutral.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from options_engine.data_models import ContractRow, Snapshot


def _parse_expiration(expiration: str) -> Optional[datetime]:
    text = str(expiration or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m/%d/%Y"):
        try:
            parsed = datetime.strptime(
                text[:10] if fmt == "%Y-%m-%d" and len(text) >= 10 else text,
                fmt,
            )
            return parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _years_to_expiry(expiration: str, as_of: str, min_hours: float = 0.5) -> float:
    """Return years to expiry, floored so 0DTE still has a usable gamma."""
    exp = _parse_expiration(expiration)
    if exp is None:
        return min_hours / (365.0 * 24.0)
    now = datetime.now(timezone.utc)
    if as_of:
        try:
            now = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
            if now.tzinfo is None:
                now = now.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    hours = max(min_hours, (exp - now).total_seconds() / 3600.0)
    # If calendar date is today but timestamp is past close, still use min_hours.
    if exp.date() == now.date():
        hours = max(min_hours, hours)
    return hours / (365.0 * 24.0)


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def black_scholes_gamma(spot: float, strike: float, t_years: float, iv: float, rate: float = 0.0) -> float:
    """Black–Scholes gamma for a European option (same for call and put)."""
    if spot <= 0 or strike <= 0 or t_years <= 0 or iv <= 0:
        return 0.0
    sqrt_t = math.sqrt(t_years)
    denom = iv * sqrt_t
    if denom <= 0:
        return 0.0
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * t_years) / denom
    return _norm_pdf(d1) / (spot * denom)


def _regime_from_net_gex(net_gex: float, pos_threshold: float, neg_threshold: float) -> str:
    if net_gex >= pos_threshold:
        return "positive"
    if net_gex <= neg_threshold:
        return "negative"
    return "neutral"


def compute_gex_features(
    snapshot: Snapshot,
    settings: Dict[str, Any],
    *,
    near_spot_band_pct: Optional[float] = None,
) -> Dict[str, float]:
    """
    Estimate net dealer GEX near spot and classify the gamma regime.

    Returns keys (all floats for feature-cache compatibility):
      - net_dealer_gex: signed aggregate (scaled by spot^2 * 0.01 * 100)
      - gex_near_spot: same but only strikes within the ATM band
      - gex_regime_code: 1.0 positive / 0.0 neutral / -1.0 negative
      - gex_available: 1.0 if at least one contract contributed
    """
    odte = settings.get("odte_signals", {}).get("gex", {})
    if not bool(odte.get("enabled", True)):
        return {
            "net_dealer_gex": 0.0,
            "gex_near_spot": 0.0,
            "gex_regime_code": 0.0,
            "gex_available": 0.0,
        }

    spot = float(snapshot.spot_price or 0.0)
    if spot <= 0:
        return {
            "net_dealer_gex": 0.0,
            "gex_near_spot": 0.0,
            "gex_regime_code": 0.0,
            "gex_available": 0.0,
        }

    band = float(
        near_spot_band_pct
        if near_spot_band_pct is not None
        else odte.get("near_spot_band_pct", settings.get("features", {}).get("atm_strike_band_pct", 0.03))
    )
    min_hours = float(odte.get("min_hours_to_expiry", 0.5))
    pos_thr = float(odte.get("positive_threshold", 0.0))
    neg_thr = float(odte.get("negative_threshold", 0.0))
    # If thresholds are 0, use magnitude relative to total absolute GEX later.
    use_relative = abs(pos_thr) < 1e-12 and abs(neg_thr) < 1e-12

    lower = spot * (1.0 - band)
    upper = spot * (1.0 + band)
    contract_mult = 100.0
    scale = spot * spot * 0.01 * contract_mult

    net = 0.0
    near = 0.0
    used = 0
    for row in snapshot.contracts:
        iv = float(row.implied_volatility or 0.0)
        oi = float(row.open_interest or 0.0)
        if iv <= 0 or oi <= 0:
            continue
        t = _years_to_expiry(row.expiration, snapshot.as_of, min_hours=min_hours)
        gamma = black_scholes_gamma(spot, float(row.strike), t, iv)
        if gamma <= 0:
            continue
        # Dealer-short assumption: calls subtract, puts add.
        sign = -1.0 if row.side == "call" else 1.0
        contrib = sign * gamma * oi * scale
        net += contrib
        if lower <= float(row.strike) <= upper:
            near += contrib
        used += 1

    if used == 0:
        return {
            "net_dealer_gex": 0.0,
            "gex_near_spot": 0.0,
            "gex_regime_code": 0.0,
            "gex_available": 0.0,
        }

    ref = near if abs(near) > 0 else net
    if use_relative:
        # Soft regime: any clearly non-zero near-spot GEX.
        abs_ref = abs(ref)
        # Compare to a tiny epsilon of scale so noise doesn't flip regimes.
        eps = scale * 1e-6
        if ref > eps:
            regime = "positive"
        elif ref < -eps:
            regime = "negative"
        else:
            regime = "neutral"
        _ = abs_ref  # kept for readability / future thresholding
    else:
        regime = _regime_from_net_gex(ref, pos_thr, neg_thr)

    regime_code = {"positive": 1.0, "negative": -1.0, "neutral": 0.0}[regime]
    return {
        "net_dealer_gex": float(net),
        "gex_near_spot": float(near),
        "gex_regime_code": regime_code,
        "gex_available": 1.0,
    }


def gex_regime_label(gex_regime_code: float) -> str:
    """Map regime code back to a human label."""
    if gex_regime_code > 0.5:
        return "positive"
    if gex_regime_code < -0.5:
        return "negative"
    return "neutral"

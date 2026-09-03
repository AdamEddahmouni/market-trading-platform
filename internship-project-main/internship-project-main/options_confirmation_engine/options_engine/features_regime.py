"""Session-level regime / breadth filter (VIX + SPY/QQQ trend).

Purpose
-------
Attach macro context and a soft ``regime_trust_multiplier`` when VIX or indices
signal risk-off — informative for agent confidence, not a hard block by default.

Features / API role
-------------------
``compute_regime_features`` → ``vix_level``, ``regime_risk_off``, ``regime_available``.

How ``news_momentum_agent`` consumes it
---------------------------------------
Live: merged into scored ``features``. Tests/replay: inject via
``settings._regime_seed`` in ``compute_features``. Evaluation enrichment uses
separate ``evaluation/vix_history`` for panel rows.

Options-specific vs reusable
----------------------------
Reusable macro filter; lives in the options engine because 0DTE scoring reads it
alongside chain features. VIX/index fetch is best-effort via yfinance.

Same ticker-level signal should be trusted less on a broad risk-off day.
VIX and index trend can be injected for tests; otherwise we best-effort
fetch via yfinance (failures → unavailable, not a hard block).
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def _fetch_vix_and_trends() -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (vix, spy_intraday_pct, qqq_intraday_pct) or Nones on failure."""
    try:
        import yfinance as yf
    except Exception:
        return None, None, None

    def _intraday_pct(symbol: str) -> Optional[float]:
        try:
            hist = yf.Ticker(symbol).history(period="2d", interval="1d")
            if hist is None or len(hist) < 1:
                return None
            closes = hist["Close"].tolist()
            if len(closes) >= 2 and closes[-2] > 0:
                return float((closes[-1] / closes[-2] - 1.0) * 100.0)
            return 0.0
        except Exception:
            return None

    vix: Optional[float] = None
    try:
        vix_hist = yf.Ticker("^VIX").history(period="5d", interval="1d")
        if vix_hist is not None and not vix_hist.empty:
            vix = float(vix_hist["Close"].iloc[-1])
    except Exception:
        vix = None

    return vix, _intraday_pct("SPY"), _intraday_pct("QQQ")


def compute_regime_features(
    settings: Dict[str, Any],
    *,
    vix: Optional[float] = None,
    spy_pct: Optional[float] = None,
    qqq_pct: Optional[float] = None,
) -> Dict[str, float]:
    """
    Keys:
      - vix_level
      - spy_intraday_pct
      - qqq_intraday_pct
      - regime_risk_off (1.0 / 0.0)
      - regime_trust_multiplier (0..1, scales confidence)
      - regime_available
    """
    odte = settings.get("odte_signals", {}).get("regime", {})
    if not bool(odte.get("enabled", True)):
        return {
            "vix_level": 0.0,
            "spy_intraday_pct": 0.0,
            "qqq_intraday_pct": 0.0,
            "regime_risk_off": 0.0,
            "regime_trust_multiplier": 1.0,
            "regime_available": 0.0,
        }

    if vix is None and spy_pct is None and qqq_pct is None:
        vix, spy_pct, qqq_pct = _fetch_vix_and_trends()

    if vix is None and spy_pct is None and qqq_pct is None:
        return {
            "vix_level": 0.0,
            "spy_intraday_pct": 0.0,
            "qqq_intraday_pct": 0.0,
            "regime_risk_off": 0.0,
            "regime_trust_multiplier": 1.0,
            "regime_available": 0.0,
        }

    vix_level = float(vix if vix is not None else 0.0)
    spy = float(spy_pct if spy_pct is not None else 0.0)
    qqq = float(qqq_pct if qqq_pct is not None else 0.0)

    vix_risk_off = float(odte.get("vix_risk_off", 25.0))
    index_drop = float(odte.get("index_risk_off_pct", -1.0))
    risk_off_mult = float(odte.get("risk_off_trust_multiplier", 0.65))

    risk_off = False
    if vix is not None and vix_level >= vix_risk_off:
        risk_off = True
    if spy_pct is not None and spy <= index_drop:
        risk_off = True
    if qqq_pct is not None and qqq <= index_drop:
        risk_off = True

    trust = risk_off_mult if risk_off else 1.0
    return {
        "vix_level": vix_level,
        "spy_intraday_pct": spy,
        "qqq_intraday_pct": qqq,
        "regime_risk_off": 1.0 if risk_off else 0.0,
        "regime_trust_multiplier": float(trust),
        "regime_available": 1.0,
    }

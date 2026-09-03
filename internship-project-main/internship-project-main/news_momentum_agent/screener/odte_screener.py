"""Dedicated 0DTE / near-expiry opportunity screener — ranks setup quality, does not trade.

Purpose
-------
Wide-universe scan (seeds + Finviz optionables + Path A / high-alert names),
score each ticker via options engine features, and rank by weighted setup-quality
sub-scores (liquidity, GEX, max pain, IV rank, flow, catalyst, DTE fit).

Pipeline role
-------------
Upstream filter scheduled in ``main.refresh_odte_screener`` before Path A/B
spend LLM/API budget. Persists ``state/odte_watchlist.json`` for dashboard tab
and optional gating elsewhere.

Key outputs
-----------
``{as_of, ranked: [{ticker, setup_quality, sub_scores, nearest_dte, options_bias,
...}], universe_size, skip counters}``.

Handoff notes
-------------
**Options-only:** Depends on ``agent.options_client.score_ticker`` chain features
(GEX, max pain, IV rank). Not portable to cash equity/futures without a new
feature adapter.

**Reusable pattern:** Weighted sub-score framework + universe merge from state
files — reuse scoring skeleton with futures vol/OI features.

Runs upstream of Path A / Path B so both pipelines can filter against
"is this name worth watching today" before spending Claude/news API calls.

Universe is intentionally wide: mega-cap seeds + liquid Finviz optionables +
Path A / high-alert small-caps. Many small-caps will not have true same-day
expiry; those still appear when they clear a soft DTE/liquidity bar so the
internship screener is not limited to SPY/QQQ.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from screener.expiry_screener import DEFAULT_0DTE_SEED_TICKERS, merge_seed_tickers, screen_expiry_candidates


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
ODTE_WATCHLIST_PATH = STATE_DIR / "odte_watchlist.json"
PATH_A_WATCHLIST_PATH = STATE_DIR / "watchlist.json"
HIGH_ALERT_PATH = STATE_DIR / "high_alert.json"

# Broader than Path B default: optionable, lower price floor, milder rel-vol.
DEFAULT_ODTE_FINVIZ_FILTERS = "ind_stocksonly,sh_opt_option,sh_price_o5,sh_avgvol_o200,sh_relvol_o1"


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _tickers_from_state_file(path: Path) -> List[str]:
    try:
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        items = data.get("items") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        out: List[str] = []
        for row in items:
            if isinstance(row, dict) and row.get("ticker"):
                out.append(str(row["ticker"]).upper().strip())
        return out
    except Exception:
        return []


def score_setup_quality(
    feature_values: Dict[str, Any],
    *,
    has_catalyst: bool = False,
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Score one ticker's 0DTE / near-expiry setup quality with sub-scores.

    Sub-scores (each 0–100) are averaged with configurable weights.
    """
    cfg = (settings or {}).get("odte_screener") or {}
    weights = {
        "liquidity": float(cfg.get("w_liquidity", 22)),
        "gex": float(cfg.get("w_gex", 12)),
        "max_pain": float(cfg.get("w_max_pain", 12)),
        "iv_rank": float(cfg.get("w_iv_rank", 12)),
        "flow_trend": float(cfg.get("w_flow_trend", 14)),
        "catalyst": float(cfg.get("w_catalyst", 18)),
        "dte_fit": float(cfg.get("w_dte_fit", 10)),
    }

    liq_ok = float(feature_values.get("liquidity_ok", 0.0) or 0.0) >= 1.0
    spread = float(feature_values.get("atm_median_spread_pct", 1.0) or 1.0)
    liq_score = 90.0 if liq_ok else 20.0
    liq_score -= min(40.0, spread * 200.0)
    liq_score = _clamp(liq_score)

    gex_avail = float(feature_values.get("gex_available", 0.0) or 0.0) >= 1.0
    gex_code = float(feature_values.get("gex_regime_code", 0.0) or 0.0)
    if not gex_avail:
        gex_score = 40.0
    elif abs(gex_code) > 0.5:
        gex_score = 80.0
    else:
        gex_score = 55.0

    mp_avail = float(feature_values.get("max_pain_available", 0.0) or 0.0) >= 1.0
    dist = abs(float(feature_values.get("max_pain_distance_pct", 99.0) or 99.0))
    if not mp_avail:
        mp_score = 40.0
    else:
        mp_score = _clamp(90.0 - dist * 8.0)

    iv_rank = float(feature_values.get("iv_rank", 0.5) or 0.5)
    iv_score = _clamp(100.0 - abs(iv_rank - 0.45) * 120.0)

    ft_avail = float(feature_values.get("flow_trend_available", 0.0) or 0.0) >= 1.0
    ft = float(feature_values.get("flow_trend_score", 0.5) or 0.5)
    if not ft_avail:
        share = float(feature_values.get("call_volume_share", 0.5) or 0.5)
        ft_score = _clamp(abs(share - 0.5) * 200.0)
    else:
        ft_score = _clamp(abs(ft - 0.5) * 200.0)

    catalyst_score = 90.0 if has_catalyst else 30.0

    # Same-day best; weeklies still useful for small-caps that lack true 0DTE.
    dte_raw = feature_values.get("nearest_dte")
    try:
        dte = float(dte_raw) if dte_raw is not None else -1.0
    except (TypeError, ValueError):
        dte = -1.0
    if dte < 0:
        dte_fit = 25.0
    elif dte <= 0:
        dte_fit = 100.0
    elif dte <= 2:
        dte_fit = 75.0
    elif dte <= 7:
        dte_fit = 55.0
    else:
        dte_fit = 25.0

    subs = {
        "liquidity": round(liq_score, 1),
        "gex": round(gex_score, 1),
        "max_pain": round(mp_score, 1),
        "iv_rank": round(iv_score, 1),
        "flow_trend": round(ft_score, 1),
        "catalyst": round(catalyst_score, 1),
        "dte_fit": round(dte_fit, 1),
    }
    wsum = sum(weights.values()) or 1.0
    total = sum(subs[k] * weights[k] for k in subs) / wsum

    # Illiquid names are capped, but catalyst small-caps can still surface.
    if not liq_ok:
        cap = 55.0 if has_catalyst else 42.0
        total = min(total, cap)

    gex_label = "positive" if gex_code > 0.5 else ("negative" if gex_code < -0.5 else "neutral")
    return {
        "setup_quality": round(_clamp(total), 1),
        "sub_scores": subs,
        "weights": weights,
        "gex_regime": gex_label if gex_avail else "n/a",
        "liquidity_ok": liq_ok,
        "has_catalyst": has_catalyst,
        "nearest_dte": dte if dte >= 0 else None,
    }


def resolve_universe(settings: Dict[str, Any]) -> List[str]:
    """
    Wide universe: seeds + broad Finviz optionables + Path A / high-alert names.
    """
    cfg = settings.get("odte_screener") or {}
    expiry_cfg = settings.get("expiry_screener") or {}
    seeds = cfg.get("seed_tickers")
    if seeds is None:
        seeds = expiry_cfg.get("seed_tickers") or DEFAULT_0DTE_SEED_TICKERS
    tickers: List[str] = []
    seen: Set[str] = set()

    def _add(symbol: str) -> None:
        t = str(symbol or "").upper().strip()
        if t and t not in seen:
            seen.add(t)
            tickers.append(t)

    for t in seeds:
        _add(str(t))

    if bool(cfg.get("include_finviz_scan", True)):
        try:
            odte_expiry = {
                **expiry_cfg,
                "seed_tickers": [],
                "max_rows": int(cfg.get("finviz_max_rows", 120)),
                "min_relative_volume": float(cfg.get("finviz_min_relative_volume", 1.0)),
                "min_price": float(cfg.get("finviz_min_price", 5.0)),
                "filter_codes": str(
                    cfg.get("finviz_filter_codes")
                    or DEFAULT_ODTE_FINVIZ_FILTERS
                ),
            }
            rows = screen_expiry_candidates(
                screener_cfg=settings.get("screener"),
                expiry_cfg=odte_expiry,
            )
            rows = merge_seed_tickers(rows, {**expiry_cfg, "seed_tickers": list(seeds)})
            for row in rows:
                _add(str(row.get("ticker", "")))
        except Exception as error:
            print(f"[odte_screener] Finviz universe scan failed: {error}")

    if bool(cfg.get("include_path_a_watchlist", True)):
        for t in _tickers_from_state_file(PATH_A_WATCHLIST_PATH):
            _add(t)

    if bool(cfg.get("include_high_alert", True)):
        for t in _tickers_from_state_file(HIGH_ALERT_PATH):
            _add(t)

    max_n = int(cfg.get("max_universe", 80))
    return tickers[:max_n]


def run_odte_screener(
    settings: Dict[str, Any],
    *,
    catalyst_tickers: Optional[set] = None,
    score_fn=None,
) -> Dict[str, Any]:
    """
    Rank today's universe by setup quality.

    ``score_fn(ticker, settings) -> dict`` defaults to options_client.score_ticker
    so tests can inject a stub.
    """
    cfg = settings.get("odte_screener") or {}
    if not bool(cfg.get("enabled", True)):
        return {"as_of": datetime.now(timezone.utc).isoformat(), "enabled": False, "ranked": []}

    if score_fn is None:
        from agent import options_client

        score_fn = options_client.score_ticker

    catalysts = {str(t).upper() for t in (catalyst_tickers or set())}
    # Also treat Path A high-alert as catalysts when present.
    for t in _tickers_from_state_file(HIGH_ALERT_PATH):
        catalysts.add(t)

    min_score = float(cfg.get("min_setup_score", 45))
    max_dte_include = int(cfg.get("max_dte_include", 7))
    require_chain = bool(cfg.get("require_options_chain", True))
    universe = resolve_universe(settings)
    ranked: List[Dict[str, Any]] = []
    skipped_no_chain = 0
    skipped_dte = 0
    skipped_score = 0

    for ticker in universe:
        try:
            result = score_fn(ticker, settings)
        except Exception as error:
            print(f"[odte_screener] score failed for {ticker}: {error}")
            continue
        features = result.get("features") or result.get("feature_values") or {}
        if not isinstance(features, dict):
            features = {}

        bias = str(result.get("options_bias") or "")
        flags = []
        dq = result.get("data_quality") or {}
        if isinstance(dq, dict):
            flags = list(dq.get("flags") or [])
        if require_chain and (bias == "no_data" or "empty_chain" in flags or "no_expirations" in flags):
            skipped_no_chain += 1
            continue

        dte_val = features.get("nearest_dte")
        try:
            dte = int(float(dte_val)) if dte_val is not None and float(dte_val) >= 0 else None
        except (TypeError, ValueError):
            dte = None
        if dte is not None and dte > max_dte_include:
            skipped_dte += 1
            continue

        has_cat = ticker in catalysts
        quality = score_setup_quality(features, has_catalyst=has_cat, settings=settings)
        if quality["setup_quality"] < min_score and not bool(cfg.get("keep_below_threshold", False)):
            skipped_score += 1
            continue

        ranked.append(
            {
                "ticker": ticker,
                "setup_quality": quality["setup_quality"],
                "sub_scores": quality["sub_scores"],
                "gex_regime": quality["gex_regime"],
                "liquidity_ok": quality["liquidity_ok"],
                "has_catalyst": quality["has_catalyst"],
                "nearest_dte": dte,
                "options_score": result.get("options_score"),
                "options_bias": result.get("options_bias"),
                "spot_price": result.get("spot_price"),
                "max_pain_distance_pct": features.get("max_pain_distance_pct"),
                "iv_rank": features.get("iv_rank"),
                "flow_trend_score": features.get("flow_trend_score"),
                "source_hint": "catalyst" if has_cat else ("seed" if ticker in DEFAULT_0DTE_SEED_TICKERS else "scan"),
            }
        )

    ranked.sort(key=lambda row: float(row.get("setup_quality", 0.0)), reverse=True)
    max_watch = int(cfg.get("max_watchlist_symbols", 40))
    payload = {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "enabled": True,
        "min_setup_score": min_score,
        "max_dte_include": max_dte_include,
        "universe_size": len(universe),
        "skipped_no_chain": skipped_no_chain,
        "skipped_dte": skipped_dte,
        "skipped_score": skipped_score,
        "ranked": ranked[:max_watch],
    }
    save_odte_watchlist(payload)
    return payload


def save_odte_watchlist(payload: Dict[str, Any]) -> None:
    """Atomically write ranked 0DTE watchlist to ``state/odte_watchlist.json``."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = ODTE_WATCHLIST_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(ODTE_WATCHLIST_PATH)


def load_odte_watchlist() -> Dict[str, Any]:
    """Load cached 0DTE watchlist payload; empty ``ranked`` when missing."""
    try:
        if not ODTE_WATCHLIST_PATH.exists():
            return {"ranked": []}
        data = json.loads(ODTE_WATCHLIST_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"ranked": []}
    except Exception:
        return {"ranked": []}


def setup_quality_for_ticker(ticker: str) -> Optional[float]:
    """Lookup cached setup quality for a ticker, or None."""
    data = load_odte_watchlist()
    want = ticker.upper().strip()
    for row in data.get("ranked") or []:
        if str(row.get("ticker", "")).upper() == want:
            try:
                return float(row.get("setup_quality"))
            except (TypeError, ValueError):
                return None
    return None


def is_on_odte_watchlist(ticker: str, min_score: float | None = None) -> bool:
    """True when ``ticker`` appears in ranked list at or above ``min_score``."""
    data = load_odte_watchlist()
    want = ticker.upper().strip()
    floor = float(min_score) if min_score is not None else float(data.get("min_setup_score", 0) or 0)
    for row in data.get("ranked") or []:
        if str(row.get("ticker", "")).upper() != want:
            continue
        try:
            return float(row.get("setup_quality", 0)) >= floor
        except (TypeError, ValueError):
            return False
    return False

"""Path B screener: liquid optionable names for near-expiry options watchlist.

Purpose
-------
Finviz scan filtered for liquid, optionable underlyings plus explicit seed tickers
(SPY, QQQ, mega-caps) so 0DTE names appear even when rel-vol scan misses ETFs.

Pipeline role
-------------
``screen_expiry_candidates_with_stats`` → ``main.refresh_expiry_watchlist`` →
options scoring → ``state/expiry_watchlist.json``. Shared universe builder for
``odte_screener``.

Key outputs
-----------
Expiry row dicts with price/volume/rel-vol; ``enrich_expiry_row_with_options`` adds
chain features (DTE, OI, max-OI strike) from options engine.

Handoff notes
-------------
**Reusable (equity):** Finviz row normalization, seed merge, rel-vol/price floors.

**Options-only:** Entire module assumes listed options chains; for stock/futures
momentum, replace with liquidity/volatility screen without ``sh_opt_option``.

**Futures:** Use continuous contract symbols; drop OI/DTE enrichment or map to
roll-aware chain adapter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from screener.finviz_screener import fetch_finviz_rows, parse_number_with_suffix, parse_percent


DEFAULT_EXPIRY_FILTER_CODES = "ind_stocksonly,sh_opt_option,sh_price_o10,sh_avgvol_o1000,sh_relvol_o1.5"

# Liquid underlyings that usually list same-day options (Path B 0DTE seed).
DEFAULT_0DTE_SEED_TICKERS = [
    "SPY",
    "QQQ",
    "IWM",
    "AAPL",
    "TSLA",
    "NVDA",
    "AMZN",
    "META",
    "MSFT",
    "GOOGL",
]


def build_expiry_filter_codes(cfg: Optional[Dict[str, Any]] = None) -> str:
    """Build Finviz URL filter codes for Path B liquid optionable universe."""
    block = cfg or {}
    return str(block.get("filter_codes", DEFAULT_EXPIRY_FILTER_CODES)).strip() or DEFAULT_EXPIRY_FILTER_CODES


def _seed_list(expiry_cfg: Optional[Dict[str, Any]] = None) -> List[str]:
    expiry = expiry_cfg or {}
    configured = expiry.get("seed_tickers")
    if configured is None:
        return list(DEFAULT_0DTE_SEED_TICKERS) if int(expiry.get("max_dte", 14)) == 0 else []
    return [str(t).upper().strip() for t in configured if str(t).strip()]


def _seed_expiry_row(ticker: str, scanned_at: str) -> Dict[str, Any]:
    return {
        "ticker": ticker.upper().strip(),
        "company_name": "",
        "source": "expiry",
        "current_price": 0.0,
        "percent_change": 0.0,
        "volume": 0,
        "average_volume": None,
        "relative_volume": None,
        "nearest_dte": None,
        "max_oi_strike": None,
        "max_oi_strike_pct_from_spot": None,
        "total_oi": None,
        "volume_oi_spike": None,
        "scanned_at": scanned_at,
        "seeded": True,
    }


def merge_seed_tickers(results: List[Dict[str, Any]], expiry_cfg: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Prepend configured liquid tickers so Path B always sees daily-options names.

    When max_dte is 0, Finviz high-relvol scans often miss SPY/QQQ; seed them explicitly.
    """
    seeds = _seed_list(expiry_cfg)
    if not seeds:
        return results

    seen = {str(row.get("ticker", "")).upper() for row in results}
    now_text = datetime.now(timezone.utc).isoformat()
    prepended = [_seed_expiry_row(ticker, now_text) for ticker in seeds if ticker and ticker not in seen]
    return prepended + results


def screen_expiry_candidates(
    screener_cfg: Optional[Dict[str, Any]] = None,
    expiry_cfg: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Screen liquid optionable names; see screen_expiry_candidates_with_stats for counters."""
    rows, _stats = screen_expiry_candidates_with_stats(screener_cfg=screener_cfg, expiry_cfg=expiry_cfg)
    return rows


def screen_expiry_candidates_with_stats(
    screener_cfg: Optional[Dict[str, Any]] = None,
    expiry_cfg: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Screen Path B universe and return (rows, stats).

    stats keys: finviz_raw, after_filters, seed_count, scrape_error
    """
    expiry = expiry_cfg or {}
    screener = screener_cfg or {}
    max_rows = int(expiry.get("max_rows", screener.get("finviz_max_rows", 200)))
    min_rel_vol = float(expiry.get("min_relative_volume", 1.5))
    min_price = float(expiry.get("min_price", 10.0))
    filter_codes = build_expiry_filter_codes(expiry)

    scrape_cfg = dict(screener)
    scrape_cfg["provider"] = "scraper"

    scrape_error = ""
    rows_raw: List[Dict[str, Any]] = []
    try:
        rows_raw = fetch_finviz_rows(
            max_rows=max_rows,
            screener_cfg=scrape_cfg,
            filter_codes=filter_codes,
        )
    except Exception as error:
        scrape_error = f"{type(error).__name__}: {error}"
        print(f"[expiry_screener] Finviz scrape failed: {scrape_error}")
        rows_raw = []

    finviz_raw = len(rows_raw) if isinstance(rows_raw, list) else 0
    now_text = datetime.now(timezone.utc).isoformat()
    results: List[Dict[str, Any]] = []

    for row in rows_raw or []:
        ticker = str(row.get("Ticker", "")).strip().upper()
        if not ticker:
            continue
        current_price = parse_number_with_suffix(row.get("Price"))
        if current_price < min_price:
            continue
        current_volume = parse_number_with_suffix(row.get("Volume", row.get("Current Volume")))
        average_volume = parse_number_with_suffix(
            row.get("Average Volume", row.get("Avg Volume", row.get("Avg Vol")))
        )
        rel_volume_col = parse_number_with_suffix(row.get("Rel Volume", row.get("Relative Volume")))
        if average_volume > 0:
            relative_volume = round(current_volume / average_volume, 2)
        elif rel_volume_col > 0:
            relative_volume = round(rel_volume_col, 2)
        else:
            relative_volume = None
        if relative_volume is not None and relative_volume < min_rel_vol:
            continue

        results.append(
            {
                "ticker": ticker,
                "company_name": str(row.get("Company", "")).strip(),
                "source": "expiry",
                "current_price": round(current_price, 4),
                "percent_change": round(parse_percent(row.get("Change")), 4),
                "volume": int(current_volume),
                "average_volume": int(average_volume) if average_volume > 0 else None,
                "relative_volume": relative_volume,
                "nearest_dte": None,
                "max_oi_strike": None,
                "max_oi_strike_pct_from_spot": None,
                "total_oi": None,
                "volume_oi_spike": None,
                "scanned_at": now_text,
                "seeded": False,
            }
        )

    after_filters = len(results)
    seed_tickers = _seed_list(expiry)
    merged = merge_seed_tickers(results, expiry)
    seed_count = sum(1 for r in merged if r.get("seeded"))
    stats = {
        "finviz_raw": finviz_raw,
        "after_filters": after_filters,
        "seed_count": seed_count,
        "seed_configured": len(seed_tickers),
        "scrape_error": scrape_error,
        "total_merged": len(merged),
    }
    return merged, stats


def enrich_expiry_row_with_options(row: Dict[str, Any], options_result: Dict[str, Any]) -> Dict[str, Any]:
    """Copy Path B options features onto an expiry watchlist row."""
    features = options_result.get("features") or options_result.get("feature_values") or {}
    if not isinstance(features, dict):
        features = {}
    updated = dict(row)
    if features.get("nearest_dte") is not None:
        updated["nearest_dte"] = int(features.get("nearest_dte"))
    if features.get("max_oi_strike") is not None:
        updated["max_oi_strike"] = float(features.get("max_oi_strike"))
    if features.get("max_oi_strike_pct_from_spot") is not None:
        updated["max_oi_strike_pct_from_spot"] = float(features.get("max_oi_strike_pct_from_spot"))
    if features.get("total_oi") is not None:
        updated["total_oi"] = float(features.get("total_oi"))
    if features.get("volume_oi_spike") is not None:
        updated["volume_oi_spike"] = float(features.get("volume_oi_spike"))
    elif features.get("volume_to_oi_spike") is not None:
        updated["volume_oi_spike"] = float(features.get("volume_to_oi_spike"))
    return updated

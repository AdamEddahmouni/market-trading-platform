"""On-demand options confirmation scoring via the external ``options_engine``.

Pipeline role
-------------
Thin adapter called from the main agent loop when ``options_confirmation.enabled``.
Loads the sibling ``options_engine`` package (path from
``settings.options_confirmation.engine_path``), runs ``run_batch`` for one
ticker, and normalizes the result to the news-agent schema
(``options_score``, ``options_bias``, ``data_quality``, ``features``).

Feeds ``decision_engine`` and ``odte_decision`` as an independent directional
vote. Never raises — returns a safe ``no_data`` fallback on missing engine or
API failure.

Merge notes for stocks/futures
------------------------------
  - **Reusable pattern:** external scoring engine on ``sys.path``, normalized
    fallback payload, offline/replay mode toggle.
  - **Options-specific:** all feature semantics; replace ``options_engine`` with
    your futures/order-flow confirmation module but keep ``score_ticker`` shape.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

_ENGINE_PATHS: set[str] = set()
_NEWS_AGENT_ROOT = Path(__file__).resolve().parent.parent


def _ensure_engine_on_path(engine_path: str) -> None:
    """Append options engine root to sys.path once per resolved path."""
    resolved = str(Path(engine_path).expanduser().resolve())
    if resolved in _ENGINE_PATHS:
        return
    if resolved not in sys.path:
        sys.path.insert(0, resolved)
    _ENGINE_PATHS.add(resolved)


def _fallback_result(ticker: str, error: str) -> Dict[str, Any]:
    """Return a safe no_data payload when options scoring fails."""
    return {
        "ticker": ticker.upper().strip(),
        "options_score": 50.0,
        "options_bias": "no_data",
        "data_quality": {"quality_score": 0.0, "flags": ["client_error"]},
        "reasoning_summary": error,
        "spot_price": 0.0,
        "features": {},
        "feature_values": {},
    }


def _normalize_item(item: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    """Map raw run_batch item to the news-agent schema."""
    data_quality = item.get("data_quality", {})
    if not isinstance(data_quality, dict):
        data_quality = {"quality_score": 0.0, "flags": ["invalid_data_quality"]}
    features = item.get("features") or item.get("feature_values") or {}
    if not isinstance(features, dict):
        features = {}
    return {
        "ticker": str(item.get("ticker", ticker)).upper().strip(),
        "options_score": float(item.get("options_score", 50.0)),
        "options_bias": str(item.get("options_bias", "no_data")),
        "data_quality": data_quality,
        "reasoning_summary": str(item.get("reasoning_summary", "")),
        "spot_price": float(item.get("spot_price", 0.0)),
        "features": features,
        "feature_values": features,
    }


def score_ticker(ticker: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score one ticker via the options confirmation engine.

    Inputs:
    - ticker: stock symbol to score.
    - settings: full news-agent settings (reads options_confirmation block).

    Output:
    - Normalized dict with options_score, options_bias, data_quality, etc.
      On failure returns no_data fallback and logs a warning — never raises.
    """
    normalized_ticker = ticker.upper().strip()
    load_dotenv(_NEWS_AGENT_ROOT / ".env", override=True)
    options_cfg = settings.get("options_confirmation", {})
    engine_path = str(options_cfg.get("engine_path", "")).strip()

    if not engine_path:
        print(f"[options_client] Missing engine_path for {normalized_ticker}; returning no_data.")
        return _fallback_result(normalized_ticker, "Missing options_confirmation.engine_path")

    try:
        _ensure_engine_on_path(engine_path)
        from options_engine.runner import run_batch
        from options_engine.utils import load_settings, merge_nested_dicts

        options_settings = load_settings()
        if bool(options_cfg.get("offline_mode", False)):
            options_settings = merge_nested_dicts(
                options_settings,
                {
                    "chain": {"provider": "replay"},
                    "universe": {"source": "snapshots"},
                    "logging": {"save_raw_snapshot": False},
                },
            )
        else:
            # Unusual Whales (if token) → yfinance. Finviz Elite is not used.
            preferred = str(options_cfg.get("chain_provider", "auto")).lower().strip()
            options_settings = merge_nested_dicts(
                options_settings,
                {"chain": {"provider": preferred or "auto"}},
            )

        request_id = f"news-{normalized_ticker}-{datetime.now(timezone.utc).isoformat()}"
        batch_result = run_batch(
            tickers=[normalized_ticker],
            settings=options_settings,
            request_id=request_id,
        )
        items = batch_result.get("items", [])
        if not isinstance(items, list) or not items:
            print(f"[options_client] Empty options result for {normalized_ticker}; returning no_data.")
            return _fallback_result(normalized_ticker, "Empty options batch result")

        result = _normalize_item(items[0], normalized_ticker)
        flags = result.get("data_quality", {}).get("flags", [])
        provider_used = str(items[0].get("provider", "") or "")
        if not provider_used:
            # runner may not echo provider; infer from flags.
            if isinstance(flags, list) and any("provider_fallback_yfinance" in str(f) for f in flags):
                provider_used = "yfinance_fallback"
        if provider_used:
            result["provider"] = provider_used
            print(f"[options_client] {normalized_ticker}: options provider={provider_used}")

        # Whale-flow enrichment when UW token is present (even if chain came from elsewhere).
        try:
            from options_engine.unusual_whales_provider import fetch_flow_recent, has_unusual_whales_token

            if has_unusual_whales_token(options_settings):
                flow = fetch_flow_recent(normalized_ticker, options_settings)
                if flow:
                    features = dict(result.get("features") or {})
                    features.update(flow)
                    result["features"] = features
                    result["feature_values"] = features
                    # Nudge directional score slightly with net premium flow.
                    net = float(flow.get("uw_net_premium", 0.0))
                    if abs(net) > 0 and result.get("options_bias") != "no_data":
                        score = float(result.get("options_score", 50.0))
                        # Cap nudge at +/- 8 points.
                        nudge = max(-8.0, min(8.0, net / 250_000.0))
                        result["options_score"] = round(max(0.0, min(100.0, score + nudge)), 3)
                        result["reasoning_summary"] = (
                            str(result.get("reasoning_summary", ""))
                            + f" | UW flow net_premium={net:,.0f} nudge={nudge:+.1f}"
                        )
        except Exception as flow_error:
            print(f"[options_client] UW flow enrichment skipped for {normalized_ticker}: {flow_error}")

        return result
    except Exception as error:
        print(f"[options_client] Options scoring failed for {normalized_ticker}: {error}")
        return _fallback_result(normalized_ticker, str(error))

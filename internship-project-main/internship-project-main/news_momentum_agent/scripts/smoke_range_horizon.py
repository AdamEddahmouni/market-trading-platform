#!/usr/bin/env python3
"""Isolated range-horizon smoke test (does not mutate live agent settings).

CLI
---
``python scripts/smoke_range_horizon.py`` — exercises ``lookup_atm_contract`` and
decision gates under ``options_expiry_horizon=range``; writes markdown + JSON
under ``state/``.

When to run
-----------
After changing ``option_contracts`` or expiry-horizon settings; dev/QA only.

Safe vs live agent
------------------
**Safe:** Uses copy of settings in-process; does not start ``main.py`` or
auto-execute trades. May call live chain APIs for quote smoke — no portfolio writes.
"""

from __future__ import annotations

import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.decision_engine import decide_trade_action  # noqa: E402
from agent.market_session import (  # noqa: E402
    effective_options_max_dte,
    effective_options_min_dte,
    normalize_options_expiry_horizon,
    now_et,
)
from agent.option_contracts import lookup_atm_contract  # noqa: E402
from agent import options_client  # noqa: E402

# Recent Path A / quadrant names from this week's live state (+ liquid control).
DEFAULT_TICKERS = ["SITE", "ENLV", "REPL", "FFAI", "FBRX"]


def _load_settings() -> Dict[str, Any]:
    path = PROJECT_ROOT / "settings.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _range_settings(base: Dict[str, Any]) -> Dict[str, Any]:
    settings = copy.deepcopy(base)
    trading = settings.setdefault("trading", {})
    trading["options_expiry_horizon"] = "range"
    trading["options_dte_range"] = [1, 30]
    # Ensure we do not accidentally inherit a Friday deadline constraint.
    trading.pop("deadline_date", None)
    return settings


def _spot_for(ticker: str) -> float:
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).fast_info
        return float(info.get("lastPrice") or 0.0)
    except Exception:
        return 0.0


def _smoke_one(ticker: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "ticker": ticker,
        "horizon": normalize_options_expiry_horizon(settings),
        "dte_window": [
            effective_options_min_dte(settings),
            effective_options_max_dte(settings),
        ],
    }
    spot = _spot_for(ticker)
    row["spot"] = spot
    lookup = lookup_atm_contract(ticker, "call", spot, settings=settings)
    contract = lookup.get("contract") if isinstance(lookup.get("contract"), dict) else None
    row["lookup_status"] = lookup.get("status")
    row["lookup_detail"] = lookup.get("detail")
    row["provider"] = lookup.get("provider")
    row["expiries_seen"] = lookup.get("expiries_seen")
    if contract:
        row["expiration"] = contract.get("expiration")
        row["dte"] = contract.get("dte")
        row["strike"] = contract.get("strike")
        row["premium"] = contract.get("premium")
        row["contract_symbol"] = contract.get("contract_symbol")
        dte = int(contract.get("dte") or -1)
        min_dte, max_dte = row["dte_window"]
        row["dte_in_range"] = min_dte <= dte <= max_dte
        # Not forced to this Friday (2026-07-31): any expiry in [1,30] is valid;
        # record whether selected expiry is beyond the demo deadline.
        row["beyond_demo_deadline"] = str(contract.get("expiration") or "") > "2026-07-31"
    else:
        row["dte_in_range"] = False
        row["beyond_demo_deadline"] = None

    # Liquidity / options score via existing engine (thresholds untouched).
    options_result: Dict[str, Any] = {}
    try:
        options_result = options_client.score_ticker(ticker, settings)
    except Exception as exc:  # pragma: no cover
        options_result = {"options_bias": "no_data", "error": str(exc)}
    feats = options_result.get("features") or options_result.get("feature_values") or {}
    row["options_score"] = options_result.get("options_score")
    row["options_bias"] = options_result.get("options_bias")
    row["liquidity_reject"] = float(feats.get("liquidity_reject", 0.0) or 0.0) >= 1.0
    row["liquidity_reject_detail"] = feats.get("liquidity_reject_detail") or feats.get(
        "liquidity_reject_primary"
    )
    row["atm_median_spread_pct"] = feats.get("atm_median_spread_pct")
    row["nearest_dte_engine"] = feats.get("nearest_dte") or options_result.get("nearest_dte")

    decision, reason, meta = decide_trade_action(
        ticker=ticker,
        social_signal_level="HIGH_ALERT",
        claude_response={
            "score": 0.55,
            "confidence": "medium",
            "reasoning": "range-horizon smoke (synthetic Path A-style news score)",
        },
        news_headline="Range-horizon smoke test (isolated; not live)",
        news_source="smoke_range_horizon",
        options_bias=str(options_result.get("options_bias") or "no_data"),
        options_score=float(options_result.get("options_score") or 50.0),
        options_data_quality=float(
            (options_result.get("data_quality") or {}).get("quality_score") or 0.0
        ),
        options_enabled=bool(settings.get("options_confirmation", {}).get("enabled", False)),
        signal_source="news",
        dte=int(contract["dte"]) if contract and contract.get("dte") is not None else None,
        options_features=feats if isinstance(feats, dict) else None,
        settings=settings,
        apply_odte_layer=True,
    )
    row["decision"] = decision
    row["decision_reason"] = reason
    row["decision_meta_codes"] = {
        k: meta.get(k)
        for k in ("review_reason", "log_reason", "confidence", "action")
        if isinstance(meta, dict) and k in meta
    }
    return row


def _to_markdown(rows: List[Dict[str, Any]], settings: Dict[str, Any], ran_at: str) -> str:
    trading = settings.get("trading") or {}
    lines = [
        "# Range-horizon smoke test",
        "",
        f"- Ran at (UTC): `{ran_at}`",
        f"- Horizon mode: `{normalize_options_expiry_horizon(settings)}`",
        f"- DTE range setting: `{trading.get('options_dte_range')}`",
        f"- Effective window: "
        f"`[{effective_options_min_dte(settings)}, {effective_options_max_dte(settings)}]`",
        f"- Live agent config was NOT modified (override in-memory only).",
        "",
        "## Results",
        "",
    ]
    for row in rows:
        lines.append(f"### {row['ticker']}")
        lines.append("")
        lines.append(f"- Spot: `{row.get('spot')}`")
        lines.append(f"- Lookup: `{row.get('lookup_status')}` — {row.get('lookup_detail')}")
        if row.get("contract_symbol"):
            lines.append(
                f"- Selected: `{row.get('contract_symbol')}` "
                f"exp=`{row.get('expiration')}` dte=`{row.get('dte')}` "
                f"strike=`{row.get('strike')}` premium=`{row.get('premium')}`"
            )
            lines.append(f"- DTE in [1,30] window: `{row.get('dte_in_range')}`")
            lines.append(
                f"- Expiry beyond demo deadline 2026-07-31: `{row.get('beyond_demo_deadline')}`"
            )
        lines.append(
            f"- Liquidity reject: `{row.get('liquidity_reject')}` "
            f"({row.get('liquidity_reject_detail') or 'n/a'})"
        )
        lines.append(
            f"- Options bias/score: `{row.get('options_bias')}` / `{row.get('options_score')}`"
        )
        lines.append(f"- Decision: **{row.get('decision')}** — {row.get('decision_reason')}")
        lines.append("")
    lines.append("## Verdict")
    lines.append("")
    ok_lookups = [r for r in rows if r.get("lookup_status") == "ok"]
    in_range = [r for r in ok_lookups if r.get("dte_in_range")]
    beyond = [r for r in ok_lookups if r.get("beyond_demo_deadline")]
    lines.append(
        f"- Contract lookups ok: **{len(ok_lookups)}/{len(rows)}**; "
        f"in range window: **{len(in_range)}**; "
        f"selected beyond Friday deadline: **{len(beyond)}**."
    )
    if in_range:
        lines.append(
            "- Range mode selected normal (non-deadline-constrained) expiries where chains existed."
        )
    else:
        lines.append(
            "- No in-window contracts found for these names (illiquid/micro-cap chains); "
            "logic still exercised — see lookup statuses above."
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    """CLI entry: smoke-test ``range`` horizon contract selection for tickers."""
    tickers = list(DEFAULT_TICKERS)
    if len(sys.argv) > 1:
        tickers = [t.strip().upper() for t in sys.argv[1:] if t.strip()]

    base = _load_settings()
    settings = _range_settings(base)
    ran_at = datetime.now(timezone.utc).isoformat()
    print(
        f"[smoke_range] horizon={normalize_options_expiry_horizon(settings)} "
        f"window=[{effective_options_min_dte(settings)}, {effective_options_max_dte(settings)}] "
        f"tickers={tickers} et={now_et().isoformat()}"
    )

    rows = []
    for ticker in tickers:
        print(f"[smoke_range] scoring {ticker} ...")
        row = _smoke_one(ticker, settings)
        rows.append(row)
        print(
            f"  status={row.get('lookup_status')} exp={row.get('expiration')} "
            f"dte={row.get('dte')} decision={row.get('decision')}"
        )

    state_dir = PROJECT_ROOT / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    day = now_et().date().isoformat()
    md_path = state_dir / f"range_horizon_smoke_{day}.md"
    json_path = state_dir / f"range_horizon_smoke_{day}.json"
    payload = {
        "ran_at_utc": ran_at,
        "horizon": normalize_options_expiry_horizon(settings),
        "options_dte_range": (settings.get("trading") or {}).get("options_dte_range"),
        "tickers": tickers,
        "results": rows,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(_to_markdown(rows, settings, ran_at), encoding="utf-8")
    print(f"[smoke_range] wrote {md_path}")
    print(f"[smoke_range] wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

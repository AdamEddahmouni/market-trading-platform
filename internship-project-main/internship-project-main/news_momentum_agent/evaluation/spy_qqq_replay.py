"""SPY/QQQ Path B replay harness (research only — does not edit live decision code).

Purpose
-------
Feed historical IVolatility caches through production ``compute_features`` /
``score_options`` and ``decide_trade_action`` (import-only) with TP/SL/EOD labels.

Features / API role
-------------------
``replay_range``, ``score_snapshot``, ``decide_path_b``, ``save_replay_records``,
``sanity_check_against_live``.

How this uses ``options_confirmation_engine``
-----------------------------------------------
``ENGINE_ROOT`` on ``sys.path``; imports ``options_engine.features`` and
``scoring`` inside ``score_snapshot``. Snapshots built via ``historical_chain_adapter``.

Options-specific vs reusable
----------------------------
Path B / SPY-QQQ scope is options-research-specific. Reusable replay outcome
labeling and live-vs-replay sanity check utilities.

Feeds historical Snapshots through production ``compute_features`` / ``score_options``
and ``decide_trade_action`` (import-only). Outcomes use mid-price forward marks with
TP/SL/EOD rules mirrored from paper/near-miss exits.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
ENGINE_ROOT = PROJECT_ROOT.parent / "options_confirmation_engine"
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from agent.decision_engine import decide_trade_action  # noqa: E402
from evaluation.historical_chain_adapter import (  # noqa: E402
    rows_to_snapshot,
    spot_from_stock_rows,
)
from evaluation.ivolatility_client import read_csv  # noqa: E402

PATH_A_EXCLUSION_NOTE = (
    "Path A micro-cap catalyst universe is OUT OF SCOPE for this historical pipeline — "
    "insufficient affordable intraday options history. Path A continues to learn from the "
    "live near-miss tracker only."
)


def _load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def load_settings() -> Dict[str, Any]:
    """Load news-agent ``settings.json`` for decision replay."""
    return _load_json(PROJECT_ROOT / "settings.json", {})


def load_engine_settings() -> Dict[str, Any]:
    """Load sibling ``options_confirmation_engine/settings.json``."""
    path = ENGINE_ROOT / "settings.json"
    data = _load_json(path, {})
    return data if isinstance(data, dict) else {}


def _mid(bid: float, ask: float, last: float) -> float:
    if bid > 0 and ask > 0:
        return (bid + ask) / 2.0
    return max(last, 0.0)


def _atm_contract(snapshot, side: str, *, prefer_forward: bool = True) -> Optional[Dict[str, Any]]:
    """Pick ATM contract. Prefer expirations after as_of so next-day EOD marks exist."""
    spot = float(snapshot.spot_price or 0.0)
    today = str(snapshot.as_of)[:10]
    cands = [c for c in snapshot.contracts if c.side == side]
    if not cands or spot <= 0:
        return None
    forward = [c for c in cands if str(c.expiration or "") > today]
    same_day = [c for c in cands if str(c.expiration or "") == today]
    if prefer_forward and forward:
        # Shortest remaining tenor among forward expiries (typically 1DTE in our cache).
        min_exp = min(str(c.expiration) for c in forward)
        pool = [c for c in forward if str(c.expiration) == min_exp]
    else:
        pool = same_day or forward or cands
    best = min(pool, key=lambda c: abs(float(c.strike) - spot))
    prem = _mid(float(best.bid), float(best.ask), float(best.last_price))
    return {
        "contract_symbol": best.contract_symbol,
        "side": best.side,
        "strike": best.strike,
        "expiration": best.expiration,
        "premium": prem,
        "bid": best.bid,
        "ask": best.ask,
        "last": best.last_price,
    }


def _find_contract_mark(
    later_snapshots: Sequence[Any],
    contract_symbol: str,
    side: str,
    strike: float,
    expiration: str,
) -> Optional[float]:
    for snap in later_snapshots:
        for c in snap.contracts:
            if contract_symbol and c.contract_symbol == contract_symbol:
                return _mid(float(c.bid), float(c.ask), float(c.last_price))
            if c.side == side and abs(float(c.strike) - float(strike)) < 1e-6 and c.expiration == expiration:
                return _mid(float(c.bid), float(c.ask), float(c.last_price))
    return None


def label_replay_outcome(
    entry_premium: float,
    later_marks: Sequence[float],
    *,
    take_profit_pct: float = 0.35,
    stop_loss_pct: float = 0.30,
) -> Tuple[str, Optional[str], Optional[float]]:
    """Return (outcome, exit_rule, exit_pnl_pct) using mid marks. Research fill assumption."""
    if entry_premium <= 0:
        return "unknown", None, None
    for mark in later_marks:
        if mark <= 0:
            continue
        pnl_pct = (mark - entry_premium) / entry_premium
        if pnl_pct >= take_profit_pct:
            return "win", "take_profit", pnl_pct
        if pnl_pct <= -stop_loss_pct:
            return "loss", "stop_loss", pnl_pct
    if later_marks:
        mark = later_marks[-1]
        if mark > 0:
            pnl_pct = (mark - entry_premium) / entry_premium
            if abs(pnl_pct) < 0.02:
                return "flat", "eod_flatten", pnl_pct
            return ("win" if pnl_pct > 0 else "loss"), "eod_flatten", pnl_pct
    return "unknown", None, None


def score_snapshot(snapshot, engine_settings: Dict[str, Any], history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Run production ``compute_features`` + ``score_options`` on one Snapshot."""
    from options_engine.features import compute_features
    from options_engine.scoring import score_options

    features = compute_features(snapshot, history or [], engine_settings)
    scored = score_options(
        snapshot.ticker,
        features,
        list(snapshot.data_quality_flags or []),
        engine_settings,
    )
    return {
        "features": features,
        "options_score": float(scored.get("options_score") or 50.0),
        "options_bias": str(scored.get("options_bias") or "no_data"),
        "data_quality_flags": list(scored.get("data_quality_flags") or snapshot.data_quality_flags or []),
        "reasoning": scored.get("reasoning_summary") or scored.get("reasoning"),
    }


def decide_path_b(
    ticker: str,
    scored: Dict[str, Any],
    *,
    settings: Dict[str, Any],
    dte: int = 0,
) -> Tuple[str, str, Dict[str, Any]]:
    """Invoke ``decide_trade_action`` for Path B replay with neutral news stub."""
    bias = str(scored.get("options_bias") or "no_data")
    score = float(scored.get("options_score") or 50.0)
    features = scored.get("features") or {}
    decision, reason, meta = decide_trade_action(
        ticker=ticker,
        social_signal_level="IGNORE",
        claude_response={"score": 0.0, "confidence": "low", "reasoning": "Path B replay (neutral news)"},
        news_headline="SPY/QQQ historical Path B replay",
        news_source="expiry",
        require_social_signal=False,
        options_enabled=True,
        options_bias=bias if bias != "no_data" else None,
        options_score=score,
        options_data_quality=float(features.get("data_quality_score") or 0.8),
        options_data_flags=list(scored.get("data_quality_flags") or []),
        signal_source="expiry",
        dte=dte,
        volume_oi_spike=float(features.get("volume_oi_spike") or features.get("vol_oi_ratio") or 0.0),
        expiry_override_review=True,
        options_features=features if isinstance(features, dict) else None,
        settings=settings,
        apply_odte_layer=True,
    )
    return decision, reason, meta


def load_cached_day_snapshots(
    cache_dir: Path,
    symbol: str,
    trade_day: date,
) -> Optional[Any]:
    """Build one ``Snapshot`` for ``trade_day`` from IVolatility CSV cache."""
    opt_path = cache_dir / f"{symbol}_options_{trade_day.isoformat()}.csv"
    if not opt_path.exists():
        # fall back to combined file filtered by date
        all_path = cache_dir / f"{symbol}_options_all.csv"
        if not all_path.exists():
            return None
        rows = [r for r in read_csv(all_path) if str(r.get("_trade_date") or r.get("tradeDate") or r.get("date") or "")[:10] == trade_day.isoformat()]
    else:
        rows = read_csv(opt_path)
    if not rows:
        return None
    stock_rows = read_csv(cache_dir / f"{symbol}_stock_prices.csv")
    spot = spot_from_stock_rows(stock_rows, trade_day.isoformat())
    return rows_to_snapshot(symbol, trade_day.isoformat(), rows, spot=spot, provider="ivolatility")


def iter_cache_days(cache_dir: Path, symbol: str = "SPY") -> List[date]:
    """List trading days present in ``{symbol}_options_*.csv`` cache files."""
    days: List[date] = []
    for path in sorted(cache_dir.glob(f"{symbol}_options_20*.csv")):
        stem = path.stem  # SPY_options_YYYY-MM-DD
        parts = stem.split("_")
        if len(parts) >= 3:
            try:
                days.append(date.fromisoformat(parts[-1]))
            except ValueError:
                continue
    if days:
        return sorted(set(days))
    all_path = cache_dir / f"{symbol}_options_all.csv"
    for row in read_csv(all_path):
        text = str(row.get("_trade_date") or row.get("tradeDate") or row.get("date") or "")[:10]
        try:
            days.append(date.fromisoformat(text))
        except ValueError:
            continue
    return sorted(set(days))


def replay_range(
    cache_dir: Path,
    *,
    tickers: Sequence[str] = ("SPY", "QQQ"),
    settings: Optional[Dict[str, Any]] = None,
    engine_settings: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Replay SPY/QQQ cache days through score + decide + outcome labeling."""
    settings = settings or load_settings()
    engine_settings = engine_settings or load_engine_settings()
    trading = settings.get("trading") or {}
    tp = float(trading.get("take_profit_pct", 0.35) or 0.35)
    sl = float(trading.get("stop_loss_pct", 0.30) or 0.30)

    records: List[Dict[str, Any]] = []
    for symbol in tickers:
        days = iter_cache_days(cache_dir, symbol)
        snaps: List[Tuple[date, Any]] = []
        for d in days:
            snap = load_cached_day_snapshots(cache_dir, symbol, d)
            if snap is not None and snap.contracts:
                snaps.append((d, snap))

        history: List[Dict[str, Any]] = []
        for idx, (d, snap) in enumerate(snaps):
            scored = score_snapshot(snap, engine_settings, history=history[-5:])
            history.append({"as_of": snap.as_of, "features": scored["features"], "spot": snap.spot_price})
            today = d.isoformat()
            dte = 0 if any(c.expiration == today for c in snap.contracts) else 1
            decision, reason, meta = decide_path_b(symbol, scored, settings=settings, dte=dte)

            bias = str(scored.get("options_bias") or "").lower()
            side = "call"
            if str(decision).upper() == "SELL" or bias == "bearish":
                side = "put"
            elif str(decision).upper() == "BUY" or bias == "bullish":
                side = "call"
            elif str(meta.get("instrument_hint") or "").lower() in {"call", "put"}:
                side = str(meta.get("instrument_hint")).lower()

            # Prefer forward-dated ATM so next-session EOD marks exist (0DTE vanishes overnight).
            contract = _atm_contract(snap, side, prefer_forward=True)
            outcome, exit_rule, pnl_pct = "unknown", None, None
            shadow_labeled = False
            # Research shadow: label what ATM would have done even when live gates LOGged.
            # Without this, production LOG dominance leaves N≈0 labeled rows and learning is empty.
            if contract and float(contract.get("premium") or 0) > 0:
                later = [s for _, s in snaps[idx + 1 : idx + 4]]
                marks = []
                for s in later:
                    m = _find_contract_mark(
                        [s],
                        str(contract["contract_symbol"]),
                        side,
                        float(contract["strike"]),
                        str(contract["expiration"]),
                    )
                    if m is not None:
                        marks.append(m)
                if marks:
                    outcome, exit_rule, pnl_pct = label_replay_outcome(
                        float(contract["premium"]), marks, take_profit_pct=tp, stop_loss_pct=sl
                    )
                    shadow_labeled = str(decision).upper() not in {"BUY", "SELL"}
                elif str(decision).upper() in {"BUY", "SELL", "REVIEW"}:
                    # Executed-path fallback only — do not invent flat from same-day mid for shadows.
                    outcome, exit_rule, pnl_pct = label_replay_outcome(
                        float(contract["premium"]),
                        [float(contract["premium"])],
                        take_profit_pct=tp,
                        stop_loss_pct=sl,
                    )

            records.append(
                {
                    "id": f"replay:{symbol}:{today}:{decision}",
                    "source_kind": "backtest_replay",
                    "ticker": symbol,
                    "session_date": today,
                    "timestamp": snap.as_of,
                    "decision": decision,
                    "reason": reason,
                    "decision_reason_code": meta.get("decision_reason_code") or meta.get("reason_code"),
                    "signal_source": "expiry",
                    "options_score": scored.get("options_score"),
                    "options_bias": scored.get("options_bias"),
                    "lean": meta.get("lean"),
                    "lean_pct": meta.get("lean_pct"),
                    "confidence_pct": meta.get("confidence_pct") or meta.get("agreement_confidence"),
                    "agreement_confidence": meta.get("agreement_confidence"),
                    "n_dir": meta.get("n_dir"),
                    "herd_urgency": meta.get("herd_urgency"),
                    "dte": dte,
                    "would_be_side": side,
                    "contract_symbol": (contract or {}).get("contract_symbol"),
                    "contract_expiration": (contract or {}).get("expiration"),
                    "entry_premium": (contract or {}).get("premium"),
                    "outcome": outcome,
                    "shadow_labeled": shadow_labeled,
                    "first_exit_rule": exit_rule,
                    "pnl_pct": pnl_pct,
                    "provider": snap.provider,
                    "limitations": [
                        "mid_fill_assumption",
                        "eod_snapshot_frequency_limits_tod",
                        "shadow_labels_include_log_rejects_for_research",
                        PATH_A_EXCLUSION_NOTE,
                    ],
                }
            )
        print(f"[replay] {symbol}: {len([r for r in records if r['ticker']==symbol])} day-rows")
    return records


def sanity_check_against_live(
    replay_rows: Sequence[Dict[str, Any]],
    *,
    sanity_date: str,
    trade_log_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Compare replay vs live Path B rows for SPY/QQQ on one calendar day (rough regime match)."""
    trade_log_path = trade_log_path or (PROJECT_ROOT / "state" / "trade_log.json")
    live = _load_json(trade_log_path, [])
    if not isinstance(live, list):
        live = []
    live_day = [
        r
        for r in live
        if isinstance(r, dict)
        and str(r.get("ticker") or "").upper() in {"SPY", "QQQ"}
        and str(r.get("timestamp") or "").startswith(sanity_date)
        and str(r.get("signal_source") or "").lower() in {"expiry", "path_b", "near_expiry", ""}
    ]
    replay_day = [r for r in replay_rows if str(r.get("session_date")) == sanity_date]

    live_dec = Counter(str(r.get("decision")) for r in live_day)
    replay_dec = Counter(str(r.get("decision")) for r in replay_day)
    live_scores = [float(r.get("options_score") or 0) for r in live_day if r.get("options_score") is not None]
    replay_scores = [float(r.get("options_score") or 0) for r in replay_day if r.get("options_score") is not None]
    replay_dates = sorted({str(r.get("session_date")) for r in replay_rows if r.get("session_date")})

    def _mean(xs: List[float]) -> Optional[float]:
        return sum(xs) / len(xs) if xs else None

    live_mean = _mean(live_scores)
    replay_mean = _mean(replay_scores)
    score_gap = None
    if live_mean is not None and replay_mean is not None:
        score_gap = abs(live_mean - replay_mean)

    ok = True
    reasons = []
    if not live_day:
        reasons.append("no_live_spy_qqq_rows_for_day — cannot validate; treat as inconclusive")
        ok = True
    elif replay_dates and (sanity_date < replay_dates[0] or sanity_date > replay_dates[-1]):
        reasons.append(
            f"sanity_date outside replay cache range [{replay_dates[0]}..{replay_dates[-1]}] — inconclusive"
        )
        ok = True
    elif not replay_day:
        reasons.append("no_replay_rows_for_day")
        ok = False
    elif score_gap is not None and score_gap > 25:
        reasons.append(f"options_score_mean_gap={score_gap:.1f} exceeds 25")
        ok = False
    else:
        reasons.append("rough_regime_match")

    return {
        "sanity_date": sanity_date,
        "ok": ok,
        "live_n": len(live_day),
        "replay_n": len(replay_day),
        "live_decisions": dict(live_dec),
        "replay_decisions": dict(replay_dec),
        "live_options_score_mean": live_mean,
        "replay_options_score_mean": replay_mean,
        "score_mean_abs_gap": score_gap,
        "reasons": reasons,
        "note": (
            "Sanity check is vendor-agnostic rough regime match, not tick-identical. "
            f"Live SPY/QQQ Path B sample is thin historically. {PATH_A_EXCLUSION_NOTE}"
        ),
    }


def save_replay_records(rows: Sequence[Dict[str, Any]], path: Path) -> Path:
    """Write replay panel rows to JSON at ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(rows), indent=2, default=str), encoding="utf-8")
    return path

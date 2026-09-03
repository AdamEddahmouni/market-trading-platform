"""0DTE decision backtest harness (paper / academic).

Purpose
-------
Replay stored options snapshots (and optional synthetic news scores) through
``decide_trade_action`` and report path / time-of-day performance metrics.

Features / API role
-------------------
``run_odte_backtest`` → ``BacktestReport`` with ``summary()`` (win rate, Sharpe, etc.).
Reads ``ENGINE_ROOT/state/raw_snapshots`` when events are not supplied.

How this uses ``options_confirmation_engine``
-----------------------------------------------
Prepends ``options_confirmation_engine`` to ``sys.path``. Events carry precomputed
``features`` / ``options_score`` from snapshots; full recompute is optional via
``_needs_recompute`` flag (honest limitation when chains are raw-only).

Options-specific vs reusable
----------------------------
Options/0DTE decision replay is domain-specific. Reusable: dataclass report +
limitation list pattern for academic writeups.

Limitations (document these in any internship writeup)
-----------------------------------------------------
1. Historical 0DTE chain granularity is only as fine as ``raw_snapshots`` —
   typically sparse intraday samples, not tick-level.
2. GEX is estimated from each snapshot via Black–Scholes gamma proxy; we do
   **not** have a vendor historical GEX tape.
3. News timestamps may be missing; when absent we inject a neutral news score
   (Path B style) or a user-supplied synthetic score series.
4. Fills assume mid / last premium without slippage modeling beyond the
   liquidity reject flag present at decision time.
5. Results are research metrics for the paper agent — not live P&L guarantees.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

ENGINE_ROOT = PROJECT_ROOT.parent / "options_confirmation_engine"
if ENGINE_ROOT.exists() and str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from agent.decision_engine import decide_trade_action  # noqa: E402


LIMITATIONS = [
    "Snapshot-level options history only (not continuous 0DTE tape).",
    "GEX estimated from chain via BS gamma proxy — no historical vendor GEX.",
    "News may be synthetic/neutral when timestamps unavailable.",
    "No realistic bid/ask slippage model beyond liquidity_reject flag.",
    "Paper-trading research metrics only.",
]


@dataclass
class TradeSim:
    """One simulated trade row from the 0DTE backtest harness."""

    ticker: str
    decision: str
    path: str
    timestamp: str
    options_score: float
    confidence_pct: float
    tod_bucket: str
    # Simple R-multiple proxy: +1 if options_score sided with decision strongly, else -1
    r_multiple: float
    won: bool


@dataclass
class BacktestReport:
    """Aggregate backtest results with ``summary()`` for JSON export."""

    trades: List[TradeSim] = field(default_factory=list)
    limitations: List[str] = field(default_factory=lambda: list(LIMITATIONS))

    def summary(self) -> Dict[str, Any]:
        """Return win rate, Sharpe, Sortino, drawdown, and breakdown by path/TOD."""
        if not self.trades:
            return {
                "n_trades": 0,
                "win_rate": None,
                "avg_r": None,
                "sharpe": None,
                "sortino": None,
                "max_drawdown": None,
                "by_path": {},
                "by_tod": {},
                "limitations": self.limitations,
            }
        rs = [t.r_multiple for t in self.trades]
        wins = sum(1 for t in self.trades if t.won)
        equity = 0.0
        peak = 0.0
        max_dd = 0.0
        for r in rs:
            equity += r
            peak = max(peak, equity)
            max_dd = min(max_dd, equity - peak)
        mean_r = sum(rs) / len(rs)
        var = sum((r - mean_r) ** 2 for r in rs) / max(1, len(rs) - 1)
        std = math.sqrt(var) if var > 0 else 0.0
        downside = [min(0.0, r - 0.0) for r in rs]
        dvar = sum(d * d for d in downside) / max(1, len(rs) - 1)
        dstd = math.sqrt(dvar) if dvar > 0 else 0.0
        sharpe = (mean_r / std) if std > 0 else None
        sortino = (mean_r / dstd) if dstd > 0 else None

        def _bucket(key_fn):
            groups: Dict[str, List[TradeSim]] = {}
            for t in self.trades:
                groups.setdefault(key_fn(t), []).append(t)
            out = {}
            for k, rows in groups.items():
                wr = sum(1 for r in rows if r.won) / len(rows)
                out[k] = {
                    "n": len(rows),
                    "win_rate": round(wr, 3),
                    "avg_r": round(sum(r.r_multiple for r in rows) / len(rows), 3),
                }
            return out

        return {
            "n_trades": len(self.trades),
            "win_rate": round(wins / len(self.trades), 3),
            "avg_r": round(mean_r, 3),
            "sharpe": round(sharpe, 3) if sharpe is not None else None,
            "sortino": round(sortino, 3) if sortino is not None else None,
            "max_drawdown": round(max_dd, 3),
            "by_path": _bucket(lambda t: t.path),
            "by_tod": _bucket(lambda t: t.tod_bucket),
            "limitations": self.limitations,
        }


def _tod_bucket(as_of: str) -> str:
    try:
        dt = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        hour = dt.astimezone(timezone.utc).hour  # coarse; fine for bucket stats
        # Convert roughly to ET by -4/-5 is messy; use UTC buckets labeled loosely.
        if hour < 15:
            return "morning_utc"
        if hour < 18:
            return "midday_utc"
        return "late_utc"
    except Exception:
        return "unknown"


def _load_snapshot_feature_rows(snapshot_dir: Path) -> List[Dict[str, Any]]:
    """Load feature caches from raw snapshot JSON files when present."""
    rows: List[Dict[str, Any]] = []
    if not snapshot_dir.exists():
        return rows
    for path in sorted(snapshot_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        ticker = str(data.get("ticker") or path.stem.split("_")[0]).upper()
        as_of = str(data.get("as_of") or "")
        # Prefer embedded feature_cache; else leave empty for scorer skip.
        features = data.get("feature_cache") or data.get("features") or {}
        if not features and "contracts" in data:
            # Minimal: mark that we have a chain but features need engine recompute.
            features = {"_needs_recompute": 1.0}
        rows.append(
            {
                "ticker": ticker,
                "as_of": as_of,
                "features": features if isinstance(features, dict) else {},
                "options_score": data.get("options_score"),
                "options_bias": data.get("options_bias"),
                "path": "expiry",
                "news_score": 0.0,
            }
        )
    return rows


def run_odte_backtest(
    settings: Dict[str, Any],
    *,
    snapshot_dir: Optional[Path] = None,
    events: Optional[List[Dict[str, Any]]] = None,
) -> BacktestReport:
    """
    Replay events through decide_trade_action.

    Each event dict may include:
      ticker, as_of, features, options_score, options_bias, news_score,
      social_signal_level, path ('news'|'expiry')
    """
    if events is None:
        snap = snapshot_dir or (ENGINE_ROOT / "state" / "raw_snapshots")
        events = _load_snapshot_feature_rows(snap)

    report = BacktestReport()
    for event in events:
        ticker = str(event.get("ticker", "")).upper()
        if not ticker:
            continue
        features = event.get("features") or {}
        if features.get("_needs_recompute"):
            # Skip unrecomputed chains — honest limitation.
            continue
        opt_score = float(event.get("options_score") if event.get("options_score") is not None else 50.0)
        opt_bias = str(event.get("options_bias") or "neutral")
        news_score = float(event.get("news_score", 0.0))
        path = str(event.get("path") or ("news" if abs(news_score) > 0.05 else "expiry"))
        social = str(event.get("social_signal_level") or ("HIGH_ALERT" if path == "news" else "IGNORE"))

        decision, _reason, meta = decide_trade_action(
            ticker=ticker,
            social_signal_level=social,
            claude_response={"score": news_score, "confidence": "medium", "reasoning": "backtest"},
            news_headline=str(event.get("headline") or "backtest"),
            news_source="backtest",
            require_social_signal=path == "news",
            options_bias=opt_bias,
            options_score=opt_score,
            options_data_quality=float(event.get("quality", 0.8)),
            options_enabled=True,
            signal_source="news" if path == "news" else "expiry",
            options_features=features,
            settings=settings,
            apply_odte_layer=True,
        )
        if decision not in {"BUY", "SELL"}:
            continue

        # Proxy outcome: did options_score agree with the trade direction?
        if decision == "BUY":
            won = opt_score >= 55
            r = (opt_score - 50.0) / 50.0
        else:
            won = opt_score <= 45
            r = (50.0 - opt_score) / 50.0

        report.trades.append(
            TradeSim(
                ticker=ticker,
                decision=decision,
                path=path,
                timestamp=str(event.get("as_of") or ""),
                options_score=opt_score,
                confidence_pct=float(meta.get("confidence_pct") or 0.0),
                tod_bucket=_tod_bucket(str(event.get("as_of") or "")),
                r_multiple=float(r),
                won=bool(won),
            )
        )
    return report


def main() -> None:
    """CLI entry: run 0DTE backtest from snapshots and print summary + limitations."""
    settings_path = PROJECT_ROOT / "settings.json"
    settings = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    # Ensure ODTE layer configs exist for replay.
    settings.setdefault("execution", {"review_only_on_conflict": True, "min_confidence_for_action": 40})
    settings.setdefault("news_decay", {"enabled": True, "half_life_minutes": 45})
    report = run_odte_backtest(settings)
    summary = report.summary()
    print(json.dumps(summary, indent=2))
    print("\n--- Limitations ---")
    for line in summary.get("limitations") or []:
        print(f"- {line}")


if __name__ == "__main__":
    main()

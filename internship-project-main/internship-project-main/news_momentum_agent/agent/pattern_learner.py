"""Offline win/loss pattern learner from paper history.

Pipeline role
-------------
Research / observation module — **does not mutate live thresholds**. Builds a
labeled panel from:
  - near-miss shadow outcomes (``state/near_miss_tracker_*.json``),
  - closed paper executions (``state/executions.json`` + ``trade_log.json``).

Ranks simple feature patterns that separate wins from losses and writes reports
under ``state/learning/``. A future step can read ``learned_patterns.json`` as
advisory input to ``decision_engine`` or risk sizing.

State outputs
-------------
  - ``state/learning/labeled_panel.json``
  - ``state/learning/learned_patterns.json``
  - ``state/learning/latest_pattern_report.json``
  - ``state/calibration_log.json`` (via backfill helpers)

Merge notes for stocks/futures
------------------------------
  - **Fully reusable** offline learning loop; swap feature columns for futures-
    specific signals (roll date, basis, COT, etc.).
  - Near-miss and option execution pairing logic is options-specific but the
    panel/mining architecture ports directly.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
LEARNING_DIR = STATE_DIR / "learning"
TRADE_LOG_PATH = STATE_DIR / "trade_log.json"
EXECUTIONS_PATH = STATE_DIR / "executions.json"
CALIBRATION_PATH = STATE_DIR / "calibration_log.json"
PATTERNS_PATH = LEARNING_DIR / "learned_patterns.json"
PANEL_PATH = LEARNING_DIR / "labeled_panel.json"

WIN_LABELS = {"win", "would_have_won"}
LOSS_LABELS = {"loss", "would_have_lost"}
FLAT_LABELS = {"flat", "would_have_flattened_flat"}

NUMERIC_FEATURES = (
    "confidence_pct",
    "options_score",
    "lean_pct",
    "agreement_confidence",
    "distance_from_threshold",
    "n_dir",
    "dte",
    "relative_volume",
    "herd_urgency",
)

CATEGORICAL_FEATURES = (
    "signal_source",
    "reason_code",
    "decision",
    "lean",
    "options_bias",
    "social_signal_level",
    "would_be_side",
    "entry_quote_status",
    "source_kind",
)

def analyze_exit_path_breakdown(
    panel: Sequence[Dict[str, Any]],
    *,
    min_group_n: int = 1,
) -> List[Dict[str, Any]]:
    """How wins/losses exited — descriptive only, not a predictor."""
    tagged = []
    for row in panel:
        if row.get("outcome") not in {"win", "loss"}:
            continue
        copy = dict(row)
        copy["exit_path"] = str(row.get("first_exit_rule") or "unknown")
        tagged.append(copy)
    # Temporarily analyze via a synthetic feature name.
    decided = tagged
    base = _win_rate(decided)
    if base is None:
        return []
    buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in decided:
        buckets[str(row.get("exit_path") or "unknown")].append(row)
    out: List[Dict[str, Any]] = []
    for value, group in buckets.items():
        if len(group) < min_group_n:
            continue
        rate = _win_rate(group)
        if rate is None:
            continue
        out.append(
            {
                "exit_path": value,
                "n": len(group),
                "wins": sum(1 for r in group if r["outcome"] == "win"),
                "losses": sum(1 for r in group if r["outcome"] == "loss"),
                "win_rate": round(rate, 3),
            }
        )
    out.sort(key=lambda r: int(r["n"]), reverse=True)
    return out


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_ts(value: Any) -> Optional[datetime]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None


def _load_json(path: Path, default: Any) -> Any:
    try:
        if not path.exists():
            return default
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if data is not None else default
    except Exception:
        return default


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temp.replace(path)
    return path


def _outcome_from_pnl(pnl: float) -> str:
    if pnl > 1e-9:
        return "win"
    if pnl < -1e-9:
        return "loss"
    return "flat"


def _normalize_outcome(raw: Any) -> Optional[str]:
    text = str(raw or "").strip().lower()
    if text in WIN_LABELS:
        return "win"
    if text in LOSS_LABELS:
        return "loss"
    if text in FLAT_LABELS:
        return "flat"
    if text in {"unknown", "none", ""}:
        return None
    return None


def _confidence_band(pct: Optional[float]) -> str:
    if pct is None:
        return "unknown"
    if pct >= 70:
        return "70+"
    if pct >= 60:
        return "60-69"
    if pct >= 45:
        return "45-59"
    return "0-44"


def _options_band(score: Optional[float]) -> str:
    if score is None:
        return "unknown"
    if score >= 70:
        return "bullish_70+"
    if score >= 55:
        return "mild_bull_55-69"
    if score <= 30:
        return "bearish_0-30"
    if score <= 45:
        return "mild_bear_31-45"
    return "neutral_46-54"


# ---------------------------------------------------------------------------
# Panel builders
# ---------------------------------------------------------------------------


def load_near_miss_rows(state_dir: Path = STATE_DIR) -> List[Dict[str, Any]]:
    """Load labeled near-miss shadow rows from ``near_miss_tracker_*.json`` files."""
    rows: List[Dict[str, Any]] = []
    for path in sorted(state_dir.glob("near_miss_tracker_*.json")):
        data = _load_json(path, {})
        items = data.get("items") if isinstance(data, dict) else None
        if isinstance(items, dict):
            iterable: Iterable[Any] = items.values()
        elif isinstance(items, list):
            iterable = items
        else:
            continue
        session = path.stem.replace("near_miss_tracker_", "")
        for item in iterable:
            if not isinstance(item, dict):
                continue
            outcome = _normalize_outcome(item.get("shadow_outcome"))
            if outcome is None:
                continue
            rows.append(
                {
                    "id": f"near_miss:{item.get('id') or path.name}",
                    "source_kind": "near_miss_shadow",
                    "session_date": session,
                    "ticker": str(item.get("ticker") or "").upper(),
                    "timestamp": item.get("rejected_at"),
                    "decision": "REJECTED",
                    "reason_code": item.get("reason_code"),
                    "signal_source": item.get("signal_source"),
                    "confidence_pct": _safe_float(item.get("confidence_pct")),
                    "options_score": _safe_float(item.get("options_score")),
                    "options_bias": item.get("options_bias"),
                    "lean": item.get("lean"),
                    "lean_pct": _safe_float(item.get("lean_pct")),
                    "agreement_confidence": _safe_float(item.get("agreement_confidence")),
                    "distance_from_threshold": _safe_float(item.get("distance_from_threshold")),
                    "n_dir": _safe_float(item.get("n_dir")),
                    "would_be_side": item.get("would_be_side"),
                    "entry_quote_status": item.get("entry_quote_status"),
                    "first_exit_rule": item.get("first_exit_rule"),
                    "dte": None,
                    "relative_volume": None,
                    "herd_urgency": None,
                    "social_signal_level": None,
                    "outcome": outcome,
                    "realized_pnl": None,
                    "contract_symbol": item.get("contract_symbol"),
                }
            )
    return rows


def _pair_execution_closes(executions: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Match open→close by contract_symbol (FIFO)."""
    opens_by_contract: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    closed: List[Dict[str, Any]] = []
    for row in sorted(executions, key=lambda r: str(r.get("timestamp") or "")):
        if not isinstance(row, dict):
            continue
        action = str(row.get("action") or "").lower()
        symbol = str(row.get("contract_symbol") or "")
        if not symbol:
            continue
        if action == "open":
            opens_by_contract[symbol].append(row)
            continue
        if action != "close":
            continue
        open_row = opens_by_contract[symbol].pop(0) if opens_by_contract[symbol] else None
        pnl = _safe_float(row.get("realized_pnl")) or 0.0
        closed.append(
            {
                "open": open_row,
                "close": row,
                "contract_symbol": symbol,
                "ticker": str(row.get("ticker") or (open_row or {}).get("ticker") or "").upper(),
                "realized_pnl": pnl,
                "outcome": _outcome_from_pnl(pnl),
                "exit_reason": row.get("reason"),
                "open_ts": (open_row or {}).get("timestamp"),
                "close_ts": row.get("timestamp"),
            }
        )
    return closed


def _match_trade_log_features(
    ticker: str,
    open_ts: Optional[str],
    trade_log: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Nearest BUY/SELL trade_log row for ticker within ±30 minutes of open."""
    target = _parse_ts(open_ts)
    candidates = [
        r
        for r in trade_log
        if isinstance(r, dict)
        and str(r.get("ticker") or "").upper() == ticker
        and str(r.get("decision") or "").upper() in {"BUY", "SELL"}
    ]
    if not candidates:
        return {}
    if target is None:
        return dict(candidates[-1])

    best = None
    best_delta = None
    for row in candidates:
        ts = _parse_ts(row.get("timestamp"))
        if ts is None:
            continue
        delta = abs((ts - target).total_seconds())
        if delta > 30 * 60:
            continue
        if best_delta is None or delta < best_delta:
            best = row
            best_delta = delta
    return dict(best) if best else {}


def load_execution_rows(
    state_dir: Path = STATE_DIR,
    trade_log_path: Optional[Path] = None,
    executions_path: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Load win/loss labeled rows from paired option open→close executions."""
    trade_log_path = trade_log_path or (state_dir / "trade_log.json")
    executions_path = executions_path or (state_dir / "executions.json")
    executions = _load_json(executions_path, [])
    if not isinstance(executions, list):
        executions = []
    trade_log = _load_json(trade_log_path, [])
    if not isinstance(trade_log, list):
        trade_log = []

    rows: List[Dict[str, Any]] = []
    for paired in _pair_execution_closes(executions):
        ticker = paired["ticker"]
        features = _match_trade_log_features(ticker, paired.get("open_ts"), trade_log)
        meta = features.get("decision_meta") if isinstance(features.get("decision_meta"), dict) else {}
        rows.append(
            {
                "id": f"exec:{paired['contract_symbol']}:{paired.get('close_ts')}",
                "source_kind": "paper_execution",
                "session_date": str(paired.get("close_ts") or "")[:10],
                "ticker": ticker,
                "timestamp": paired.get("open_ts") or paired.get("close_ts"),
                "decision": features.get("decision")
                or ("BUY" if str((paired.get("close") or {}).get("side")) == "call" else "SELL"),
                "reason_code": features.get("decision_reason_code") or features.get("reason_code"),
                "signal_source": features.get("signal_source") or "paper_execution",
                "confidence_pct": _safe_float(features.get("confidence_pct")),
                "options_score": _safe_float(features.get("options_score")),
                "options_bias": features.get("options_bias"),
                "lean": features.get("lean"),
                "lean_pct": _safe_float(features.get("lean_pct")),
                "agreement_confidence": _safe_float(
                    features.get("agreement_confidence")
                    if features.get("agreement_confidence") is not None
                    else meta.get("agreement_confidence")
                ),
                "distance_from_threshold": None,
                "n_dir": _safe_float(features.get("n_dir") if features.get("n_dir") is not None else meta.get("n_dir")),
                "would_be_side": (paired.get("close") or {}).get("side")
                or (paired.get("open") or {}).get("side"),
                "entry_quote_status": "ok",
                "first_exit_rule": paired.get("exit_reason"),
                "dte": _safe_float(features.get("dte")),
                "relative_volume": _safe_float(features.get("relative_volume")),
                "herd_urgency": _safe_float(
                    features.get("herd_urgency")
                    if features.get("herd_urgency") is not None
                    else meta.get("herd_urgency")
                ),
                "social_signal_level": features.get("social_signal_level"),
                "outcome": paired["outcome"],
                "realized_pnl": paired["realized_pnl"],
                "contract_symbol": paired["contract_symbol"],
            }
        )
    return rows


def build_labeled_panel(state_dir: Path = STATE_DIR) -> List[Dict[str, Any]]:
    """Combine near-miss shadows + closed paper trades into one learning panel."""
    panel = load_near_miss_rows(state_dir) + load_execution_rows(state_dir=state_dir)
    for row in panel:
        row["confidence_band"] = _confidence_band(_safe_float(row.get("confidence_pct")))
        row["options_band"] = _options_band(_safe_float(row.get("options_score")))
    panel.sort(key=lambda r: str(r.get("timestamp") or ""))
    return panel


# ---------------------------------------------------------------------------
# Pattern mining
# ---------------------------------------------------------------------------


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def _win_rate(rows: Sequence[Dict[str, Any]]) -> Optional[float]:
    decided = [r for r in rows if r.get("outcome") in {"win", "loss"}]
    if not decided:
        return None
    wins = sum(1 for r in decided if r["outcome"] == "win")
    return wins / len(decided)


def _lift(group_rate: Optional[float], base_rate: Optional[float]) -> Optional[float]:
    if group_rate is None or base_rate is None or base_rate <= 0:
        return None
    return group_rate / base_rate


def analyze_numeric_separators(panel: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compare mean numeric feature values between win and loss rows in the panel."""
    wins = [r for r in panel if r.get("outcome") == "win"]
    losses = [r for r in panel if r.get("outcome") == "loss"]
    out: List[Dict[str, Any]] = []
    for feature in NUMERIC_FEATURES:
        w_vals = [v for v in (_safe_float(r.get(feature)) for r in wins) if v is not None]
        l_vals = [v for v in (_safe_float(r.get(feature)) for r in losses) if v is not None]
        if len(w_vals) < 2 or len(l_vals) < 2:
            continue
        w_mean = _mean(w_vals)
        l_mean = _mean(l_vals)
        assert w_mean is not None and l_mean is not None
        gap = w_mean - l_mean
        out.append(
            {
                "feature": feature,
                "win_mean": round(w_mean, 3),
                "loss_mean": round(l_mean, 3),
                "gap_win_minus_loss": round(gap, 3),
                "n_wins_with_value": len(w_vals),
                "n_losses_with_value": len(l_vals),
                "interpretation": (
                    f"wins average higher {feature}"
                    if gap > 0
                    else f"losses average higher {feature}"
                ),
            }
        )
    out.sort(key=lambda r: abs(float(r["gap_win_minus_loss"])), reverse=True)
    return out


def analyze_categorical_patterns(
    panel: Sequence[Dict[str, Any]],
    *,
    min_group_n: int = 3,
) -> List[Dict[str, Any]]:
    """Find categorical feature values whose win rate diverges from the panel base rate."""
    decided = [r for r in panel if r.get("outcome") in {"win", "loss"}]
    base = _win_rate(decided)
    if base is None:
        return []

    patterns: List[Dict[str, Any]] = []
    feature_names = list(CATEGORICAL_FEATURES) + ["confidence_band", "options_band"]
    for feature in feature_names:
        buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in decided:
            key = str(row.get(feature) if row.get(feature) not in (None, "") else "unknown")
            buckets[key].append(row)
        for value, group in buckets.items():
            if len(group) < min_group_n:
                continue
            rate = _win_rate(group)
            if rate is None:
                continue
            lift = _lift(rate, base)
            wins = sum(1 for r in group if r["outcome"] == "win")
            losses = sum(1 for r in group if r["outcome"] == "loss")
            patterns.append(
                {
                    "feature": feature,
                    "value": value,
                    "n": len(group),
                    "wins": wins,
                    "losses": losses,
                    "win_rate": round(rate, 3),
                    "base_win_rate": round(base, 3),
                    "lift": round(lift, 3) if lift is not None else None,
                    "kind": "protective" if rate < base else "favorable",
                    "summary": (
                        f"when {feature}={value}: win_rate={rate:.0%} "
                        f"(base {base:.0%}, n={len(group)})"
                    ),
                }
            )
    patterns.sort(key=lambda r: (abs(float(r.get("lift") or 1) - 1), r["n"]), reverse=True)
    return patterns


def top_insights(
    categorical: Sequence[Dict[str, Any]],
    numeric: Sequence[Dict[str, Any]],
    *,
    limit: int = 8,
) -> List[str]:
    """Return human-readable advisory insight strings from mined patterns."""
    lines: List[str] = []
    # Strong protective (low lift) and favorable (high lift) first.
    ranked = sorted(
        [p for p in categorical if p.get("lift") is not None],
        key=lambda p: abs(float(p["lift"]) - 1.0) * math.log1p(int(p["n"])),
        reverse=True,
    )
    for pat in ranked[:limit]:
        lift = float(pat["lift"])
        if lift >= 1.15:
            lines.append(
                f"FAVORABLE: {pat['summary']} — consider weighting this pattern more."
            )
        elif lift <= 0.85:
            lines.append(
                f"CAUTION: {pat['summary']} — historically weaker; review before sizing up."
            )
    for row in numeric[:3]:
        lines.append(
            f"FEATURE GAP: {row['feature']} win_mean={row['win_mean']} "
            f"vs loss_mean={row['loss_mean']} ({row['interpretation']})."
        )
    return lines[:limit]


def run_pattern_learning(
    state_dir: Path = STATE_DIR,
    *,
    min_group_n: int = 3,
    persist: bool = True,
) -> Dict[str, Any]:
    """Build panel, mine patterns, optionally persist artifacts under state/learning/."""
    panel = build_labeled_panel(state_dir)
    decided = [r for r in panel if r.get("outcome") in {"win", "loss"}]
    by_source = Counter(str(r.get("source_kind")) for r in panel)
    by_outcome = Counter(str(r.get("outcome")) for r in panel)
    categorical = analyze_categorical_patterns(panel, min_group_n=min_group_n)
    numeric = analyze_numeric_separators(panel)
    insights = top_insights(categorical, numeric)
    exit_paths = analyze_exit_path_breakdown(panel)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_labeled": len(panel),
        "n_win_loss": len(decided),
        "by_source": dict(by_source),
        "by_outcome": dict(by_outcome),
        "base_win_rate": _win_rate(decided),
        "numeric_separators": numeric,
        "categorical_patterns": categorical[:40],
        "exit_path_breakdown": exit_paths,
        "insights": insights,
        "status": "ok" if decided else "insufficient_labels",
        "note": (
            "Advisory only — does not change live thresholds. "
            "Patterns use decision-time features only (exit rule excluded as a predictor). "
            "Re-run after more labeled near-misses / closed trades."
        ),
    }

    patterns_payload = {
        "updated_at": report["generated_at"],
        "base_win_rate": report["base_win_rate"],
        "n_win_loss": report["n_win_loss"],
        "insights": insights,
        "top_favorable": [p for p in categorical if p.get("kind") == "favorable"][:10],
        "top_protective": [p for p in categorical if p.get("kind") == "protective"][:10],
        "numeric_separators": numeric[:10],
        "auto_apply": False,
    }

    if persist:
        learning_dir = state_dir / "learning"
        _write_json(learning_dir / "labeled_panel.json", panel)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        _write_json(learning_dir / f"pattern_report_{stamp}.json", report)
        _write_json(learning_dir / "latest_pattern_report.json", report)
        _write_json(learning_dir / "learned_patterns.json", patterns_payload)

    return report


def format_pattern_report(report: Dict[str, Any]) -> str:
    """Format a pattern-learning report dict as plain text for console or logs."""
    lines = [
        f"Pattern learner: {report.get('n_labeled', 0)} labeled rows "
        f"({report.get('n_win_loss', 0)} win/loss)",
        f"base win rate: {report.get('base_win_rate')}",
        f"sources: {report.get('by_source')}",
        f"outcomes: {report.get('by_outcome')}",
    ]
    insights = report.get("insights") or []
    if insights:
        lines.append("insights:")
        for item in insights:
            lines.append(f"  - {item}")
    else:
        lines.append("insights: none yet (need more labeled wins/losses)")
    lines.append(str(report.get("note") or ""))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Calibration backfill (close the outcome loop)
# ---------------------------------------------------------------------------


def backfill_calibration_outcomes(
    *,
    calibration_path: Path = CALIBRATION_PATH,
    executions_path: Path = EXECUTIONS_PATH,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Attach win/loss outcomes to open calibration rows using closed executions."""
    rows = _load_json(calibration_path, [])
    if not isinstance(rows, list):
        rows = []
    executions = _load_json(executions_path, [])
    if not isinstance(executions, list):
        executions = []
    closed = _pair_execution_closes(executions)

    updated = 0
    already = 0
    unmatched = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("outcome") not in (None, {}, ""):
            already += 1
            continue
        ticker = str(row.get("ticker") or "").upper()
        ts = _parse_ts(row.get("timestamp"))
        match = None
        best_delta = None
        for paired in closed:
            if paired["ticker"] != ticker:
                continue
            open_ts = _parse_ts(paired.get("open_ts"))
            if ts is None or open_ts is None:
                continue
            delta = abs((open_ts - ts).total_seconds())
            if delta > 2 * 60 * 60:
                continue
            if best_delta is None or delta < best_delta:
                best_delta = delta
                match = paired
        if match is None:
            unmatched += 1
            continue
        row["outcome"] = {
            "label": match["outcome"],
            "realized_pnl": match["realized_pnl"],
            "exit_reason": match.get("exit_reason"),
            "contract_symbol": match.get("contract_symbol"),
            "closed_at": match.get("close_ts"),
            "source": "execution_backfill",
        }
        updated += 1

    if updated and not dry_run:
        _write_json(calibration_path, rows)

    return {
        "updated": updated,
        "already_labeled": already,
        "still_unmatched": unmatched,
        "total_rows": len(rows),
        "dry_run": dry_run,
    }


def record_calibration_outcome_for_close(
    *,
    ticker: str,
    realized_pnl: float,
    exit_reason: str,
    contract_symbol: str = "",
    closed_at: Optional[str] = None,
    calibration_path: Path = CALIBRATION_PATH,
) -> bool:
    """Fill the newest unlabeled calibration row for ticker after a paper close."""
    rows = _load_json(calibration_path, [])
    if not isinstance(rows, list) or not rows:
        return False
    ticker_u = ticker.upper().strip()
    for row in reversed(rows):
        if not isinstance(row, dict):
            continue
        if str(row.get("ticker") or "").upper() != ticker_u:
            continue
        if row.get("outcome") not in (None, {}, ""):
            continue
        row["outcome"] = {
            "label": _outcome_from_pnl(float(realized_pnl)),
            "realized_pnl": round(float(realized_pnl), 2),
            "exit_reason": exit_reason,
            "contract_symbol": contract_symbol,
            "closed_at": closed_at or datetime.now(timezone.utc).isoformat(),
            "source": "live_close",
        }
        _write_json(calibration_path, rows)
        return True
    return False

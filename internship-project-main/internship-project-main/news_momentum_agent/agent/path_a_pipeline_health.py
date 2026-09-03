"""Track Path A (news + social) funnel health across scheduler cycles.

Pipeline role
-------------
Path A runs Finviz → StockTwits → herd tagging → news fetch → Claude scoring →
social gate → decisions. This module counts stage outputs each cycle and tracks
**consecutive zero** streaks (e.g. zero Finviz raw rows for N cycles).

When thresholds are hit, sets ``_should_notify`` so the main loop can Telegram
ops (RTH-only by default). ``format_funnel_line`` produces the one-line funnel
summary embedded in EOD reports and dashboards.

State file: ``state/path_a_pipeline_health.json``.

Merge notes: reusable observability pattern for any multi-stage signal pipeline;
stage keys are Path A-specific but the consecutive-zero + latch alert design
ports directly to futures/stock universes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
HEALTH_PATH = STATE_DIR / "path_a_pipeline_health.json"

ZERO_STAGE_KEYS = (
    "finviz_raw",
    "finviz_filtered",
    "stocktwits_keyword_hits",
    "high_alert",
    "news_with_headlines",
    "claude_scored",
    "passed_social_gate",
)


def _default_health() -> Dict[str, Any]:
    return {
        "consecutive_zero": {k: 0 for k in ZERO_STAGE_KEYS},
        "alerted_stages": {k: False for k in ZERO_STAGE_KEYS},
        "alert_threshold": 3,
        "last_screener": {},
        "last_pipeline": {},
        "funnel_line": "",
    }


def load_health() -> Dict[str, Any]:
    """Load Path A funnel health from ``state/path_a_pipeline_health.json``."""
    try:
        if not HEALTH_PATH.exists():
            return _default_health()
        data = json.loads(HEALTH_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return _default_health()
        base = _default_health()
        base.update(data)
        consec = dict(base.get("consecutive_zero") or {})
        for key in ZERO_STAGE_KEYS:
            consec.setdefault(key, 0)
        base["consecutive_zero"] = consec
        alerted = dict(base.get("alerted_stages") or {})
        for key in ZERO_STAGE_KEYS:
            alerted.setdefault(key, False)
        base["alerted_stages"] = alerted
        return base
    except Exception:
        return _default_health()


def save_health(data: Dict[str, Any]) -> None:
    """Persist Path A health state (strips keys prefixed with ``_``)."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = HEALTH_PATH.with_suffix(".json.tmp")
    payload = {k: v for k, v in data.items() if not str(k).startswith("_")}
    temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp.replace(HEALTH_PATH)


PIPELINE_ZERO_STAGES = (
    "news_with_headlines",
    "claude_scored",
    "passed_social_gate",
)


def _live_agent_settings(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Prefer passed settings; refresh enable toggles from disk without full restart."""
    agent = dict((settings or {}).get("agent") or {})
    try:
        disk = json.loads((PROJECT_ROOT / "settings.json").read_text(encoding="utf-8"))
        disk_agent = disk.get("agent") if isinstance(disk, dict) else None
        if isinstance(disk_agent, dict):
            for key in ("path_a_enabled", "path_a_zero_alerts_enabled"):
                if key in disk_agent:
                    agent[key] = disk_agent[key]
    except Exception:
        pass
    return agent


def _alert_threshold(settings: Optional[Dict[str, Any]]) -> int:
    agent = (settings or {}).get("agent") or {}
    return max(1, int(agent.get("path_a_zero_alert_cycles", 3)))


def _alerts_rth_only(settings: Optional[Dict[str, Any]]) -> bool:
    """Default True — overnight empty-news cycles should not Telegram-spam."""
    agent = (settings or {}).get("agent") or {}
    return bool(agent.get("path_a_zero_alerts_rth_only", True))


def _in_rth_for_alerts() -> bool:
    try:
        from agent.market_session import is_equity_rth

        return bool(is_equity_rth())
    except Exception:
        return True


def _telegram_alerts_allowed(settings: Optional[Dict[str, Any]]) -> bool:
    agent = _live_agent_settings(settings)
    if not bool(agent.get("path_a_zero_alerts_enabled", True)):
        return False
    if not bool(agent.get("path_a_enabled", True)):
        return False
    if not _alerts_rth_only(settings):
        return True
    return _in_rth_for_alerts()


def _bump_zero(consec: Dict[str, int], alerted: Dict[str, bool], key: str, count: int) -> None:
    if count > 0:
        consec[key] = 0
        alerted[key] = False
    else:
        consec[key] = int(consec.get(key) or 0) + 1


def _reset_stages(consec: Dict[str, int], alerted: Dict[str, bool], stages: tuple) -> None:
    for key in stages:
        consec[key] = 0
        alerted[key] = False


def _notify_for_stages(
    data: Dict[str, Any],
    *,
    threshold: int,
    candidate_stages: List[str],
    allow_notify: bool,
) -> List[str]:
    """Return stage keys that should fire Telegram this cycle (latch once)."""
    if not allow_notify:
        return []
    consec = data.get("consecutive_zero") or {}
    alerted = data.setdefault("alerted_stages", {})
    messages: List[str] = []
    for stage in candidate_stages:
        n = int(consec.get(stage) or 0)
        if n < threshold:
            continue
        if bool(alerted.get(stage)):
            continue
        alerted[stage] = True
        messages.append(f"{stage}={n}")
    return messages


def format_funnel_line(health: Optional[Dict[str, Any]] = None) -> str:
    """Render a one-line Path A funnel summary from stored screener + pipeline stats."""
    data = health if isinstance(health, dict) else load_health()
    screener = data.get("last_screener") or {}
    pipeline = data.get("last_pipeline") or {}
    finviz = screener.get("finviz") or {}
    tagging = screener.get("tagging") or {}
    news = pipeline.get("news") or {}
    claude = pipeline.get("claude") or {}
    gate = pipeline.get("social_gate") or {}
    decisions = pipeline.get("decisions") or {}

    raw = int(finviz.get("raw") or 0)
    filtered = int(finviz.get("after_filters") or 0)
    ha = int(tagging.get("HIGH_ALERT") or 0)
    watch = int(tagging.get("WATCH") or 0)
    by_path = screener.get("herd_alert_by_path") if isinstance(screener.get("herd_alert_by_path"), dict) else {}
    path_bits: List[str] = []
    for key in ("stocktwits", "news_catalyst", "volume_spike"):
        n = int(by_path.get(key) or 0)
        if n or by_path:
            path_bits.append(f"{key}={n}")
    path_suffix = f" ({', '.join(path_bits)})" if path_bits else ""
    tickers_in = int(pipeline.get("tickers_in") or 0)
    with_news = int(news.get("tickers_with_news") or 0)
    scored = int(claude.get("scored") or 0)
    passed = int(gate.get("passed") or 0)
    blocked = int(gate.get("blocked") or 0)
    actionable = int(decisions.get("BUY") or 0) + int(decisions.get("SELL") or 0)
    log_reasons = pipeline.get("log_reason_codes") if isinstance(pipeline.get("log_reason_codes"), dict) else {}
    downstream = (
        gate.get("cleared_blocked_downstream")
        if isinstance(gate.get("cleared_blocked_downstream"), dict)
        else {}
    )
    # Prefer explicit cleared→downstream map; fall back to cycle LOG reason codes.
    downstream_bits: List[str] = []
    source_map = downstream if downstream else log_reasons
    for key, label in (
        ("liquidity_reject", "liquidity"),
        ("low_confidence", "low_conf"),
        ("options_not_clear", "opts_unclear"),
        ("weak_lean", "weak_lean"),
    ):
        n = int(source_map.get(key) or 0)
        if n:
            downstream_bits.append(f"{n} {label}")
    downstream_suffix = f" → {' / '.join(downstream_bits)} blocked downstream" if downstream_bits else ""

    by_source = news.get("by_source") if isinstance(news.get("by_source"), dict) else {}
    source_bits: List[str] = []
    for key in (
        "Globe Newswire",
        "Newsfile",
        "Access Newswire",
        "SEC EDGAR",
        "PR Newswire",
        "BusinessWire",
        "Yahoo",
        "Benzinga",
        "MarketWatch",
    ):
        count = int(by_source.get(key) or 0)
        if count:
            short = {
                "Globe Newswire": "globe",
                "Newsfile": "newsfile",
                "Access Newswire": "access",
                "SEC EDGAR": "edgar",
                "PR Newswire": "prn",
                "BusinessWire": "bw",
                "Yahoo": "yahoo",
                "Benzinga": "bz",
                "MarketWatch": "mw",
            }.get(key, key.lower())
            source_bits.append(f"{short}={count}")
    source_suffix = f" [{', '.join(source_bits)}]" if source_bits else ""

    return (
        f"Finviz: {raw}→{filtered} filtered → {ha} HIGH_ALERT{path_suffix} / {watch} WATCH → "
        f"pipeline {tickers_in} in → {with_news} news → {scored} scored → "
        f"{passed} cleared social ({blocked} blocked)"
        f"{downstream_suffix} → {actionable} BUY/SELL{source_suffix}"
    )


def record_screener_cycle(
    stats: Dict[str, Any],
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Persist Finviz + StockTwits + tagging counts; bump consecutive zeros.
    """
    threshold = _alert_threshold(settings)
    data = load_health()
    consec = data.setdefault("consecutive_zero", {k: 0 for k in ZERO_STAGE_KEYS})
    alerted = data.setdefault("alerted_stages", {k: False for k in ZERO_STAGE_KEYS})

    finviz = stats.get("finviz") or {}
    stocktwits = stats.get("stocktwits") or {}
    tagging = stats.get("tagging") or {}

    raw = int(finviz.get("raw") or 0)
    filtered = int(finviz.get("after_filters") or 0)
    keyword_hits = int(stocktwits.get("keyword_hits") or 0)
    tickers_checked = int(stocktwits.get("tickers_checked") or 0)
    high_alert = int(tagging.get("HIGH_ALERT") or 0)

    _bump_zero(consec, alerted, "finviz_raw", raw)
    _bump_zero(consec, alerted, "finviz_filtered", filtered)
    # Only count keyword zeros when we actually scanned tickers.
    if tickers_checked > 0:
        _bump_zero(consec, alerted, "stocktwits_keyword_hits", keyword_hits)
    if filtered > 0:
        _bump_zero(consec, alerted, "high_alert", high_alert)

    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    data["alert_threshold"] = threshold
    data["consecutive_zero"] = consec
    data["last_screener"] = {
        "cycle_id": stats.get("cycle_id"),
        "finviz": finviz,
        "stocktwits": stocktwits,
        "tagging": tagging,
        "herd_alert_by_path": stats.get("herd_alert_by_path") or {},
        "herd_alert_thresholds": stats.get("herd_alert_thresholds") or {},
        "zero_reason": stats.get("zero_reason"),
    }
    data["funnel_line"] = format_funnel_line(data)

    allow_notify = _telegram_alerts_allowed(settings)
    notify_stages = _notify_for_stages(
        data,
        threshold=threshold,
        candidate_stages=["finviz_raw", "finviz_filtered", "stocktwits_keyword_hits", "high_alert"],
        allow_notify=allow_notify,
    )
    data["_should_notify"] = bool(notify_stages)
    data["_notify_messages"] = notify_stages
    data["_alerts_suppressed_outside_rth"] = not allow_notify
    save_health(data)
    return data


def record_pipeline_cycle(
    stats: Dict[str, Any],
    settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Persist news/Claude/social-gate/decision counts from a Path A pipeline run."""
    threshold = _alert_threshold(settings)
    data = load_health()
    consec = data.setdefault("consecutive_zero", {k: 0 for k in ZERO_STAGE_KEYS})
    alerted = data.setdefault("alerted_stages", {k: False for k in ZERO_STAGE_KEYS})

    tickers_in = int(stats.get("tickers_in") or 0)
    news = stats.get("news") or {}
    claude = stats.get("claude") or {}
    gate = stats.get("social_gate") or {}

    with_news = int(news.get("tickers_with_news") or 0)
    scored = int(claude.get("scored") or 0)
    passed = int(gate.get("passed") or 0)

    allow_notify = _telegram_alerts_allowed(settings)
    # Overnight empty news is expected — don't accumulate / latch pipeline zeros.
    if not allow_notify:
        _reset_stages(consec, alerted, PIPELINE_ZERO_STAGES)
    elif tickers_in > 0:
        _bump_zero(consec, alerted, "news_with_headlines", with_news)
        _bump_zero(consec, alerted, "claude_scored", scored)
        _bump_zero(consec, alerted, "passed_social_gate", passed)

    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    data["alert_threshold"] = threshold
    data["consecutive_zero"] = consec
    data["last_pipeline"] = {
        "tag": stats.get("tag"),
        "tickers_in": tickers_in,
        "news": news,
        "claude": claude,
        "social_gate": gate,
        "decisions": stats.get("decisions") or {},
        "log_reason_codes": stats.get("log_reason_codes") or {},
    }
    data["funnel_line"] = format_funnel_line(data)

    notify_stages = _notify_for_stages(
        data,
        threshold=threshold,
        candidate_stages=list(PIPELINE_ZERO_STAGES),
        allow_notify=allow_notify,
    )
    data["_should_notify"] = bool(notify_stages)
    data["_notify_messages"] = notify_stages
    data["_alerts_suppressed_outside_rth"] = not allow_notify
    save_health(data)
    return data


def score_bucket(score: float) -> str:
    """Bucket a Claude news score (-1..+1) into histogram labels for pipeline stats."""
    value = float(score)
    if value < -0.5:
        return "lt_-0.5"
    if value < -0.2:
        return "-0.5_to_-0.2"
    if value <= 0.2:
        return "-0.2_to_0.2"
    if value <= 0.5:
        return "0.2_to_0.5"
    return "gt_0.5"


def empty_score_buckets() -> Dict[str, int]:
    """Return a zeroed Claude score histogram dict for pipeline cycle aggregation."""
    return {
        "lt_-0.5": 0,
        "-0.5_to_-0.2": 0,
        "-0.2_to_0.2": 0,
        "0.2_to_0.5": 0,
        "gt_0.5": 0,
    }

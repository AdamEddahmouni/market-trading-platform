"""Live orchestrator for the news-momentum + options-confirmation agent.

Purpose
-------
``main.py`` is the long-running process that wires screener → social → news →
LLM sentiment → options gate → decision → paper/Alpaca execution. It owns the
``schedule`` loop, writes ``state/*.json`` for the Streamlit dashboard, and
enforces single-instance / demo-mode guards.

Pipeline role
-------------
- **Path A (news momentum):** ``refresh_watchlist_and_social`` → HIGH_ALERT /
  WATCH tiers → ``run_news_pipeline_for_tickers`` on a short poll interval.
- **Path A.2 (wire catalyst):** ``run_news_catalyst_cycle`` scans PR wires for
  headline hits without requiring prior social buzz.
- **Path B (expiry / herd):** ``refresh_expiry_watchlist`` + ``run_expiry_pipeline``
  for liquid optionable names near expiry (0DTE when configured).
- **Upstream 0DTE ranker:** ``refresh_odte_screener`` pre-filters setup quality
  before Path A/B spend API budget.
- **Ops:** Telegram poll, EOD summary, portfolio mark-to-market, health metrics.

Key outputs (``state/``)
------------------------
``watchlist.json``, ``high_alert.json``, ``trade_log.json``, ``health.json``,
``expiry_watchlist.json``, ``odte_watchlist.json``, ``quadrant_candidates.json``,
``news_catalyst_watchlist.json``, ``agent.pid``.

Handoff notes (equity/futures vs options-only)
----------------------------------------------
**Reusable for stocks/futures:** Finviz/HTML screener patterns, RSS + EDGAR news
ingest, social keyword funnel, LLM news scoring, scheduler/timeouts, state I/O,
dashboard contract, Telegram notifications, paper portfolio shell.

**Options-specific (replace or stub):** ``options_client`` scoring, Path B expiry
filters, 0DTE setup ranker, options confirmation gate in
``run_news_pipeline_for_tickers``, Alpaca option contract execution paths,
``quadrant_candidates`` herd/urgency axes tied to chain features.

**Futures migration:** Keep Path A news/social loop; swap Finviz equity filters
for futures universe (or continuous symbols); drop ``require_optionable`` gates;
replace options confirmation with volume/OI or cross-asset macro features; retain
``market_session`` RTH gating pattern.

Run
---
``python main.py`` (requires ``.env`` API keys and ``settings.json``).
Do not run alongside ``state/demo.lock`` unless intentionally demo-frozen.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import atexit
import json
import os
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import schedule
from dotenv import load_dotenv

from agent.scheduler_guard import (
    health_age_seconds,
    install_socket_default_timeout,
    run_with_timeout,
    wrap_scheduled_job,
)

from screener.finviz_screener import screen_path_a_universe_with_stats
from screener.expiry_screener import (
    enrich_expiry_row_with_options,
    screen_expiry_candidates_with_stats,
)
from social.stocktwits_scanner import scan_ticker_social_signal
from news.news_aggregator import aggregate_news_for_ticker, extract_primary_headline
from sentiment.claude_scorer import score_news_with_claude
from sentiment.claude_action_advisor import advise_next_action
from sentiment.keyword_boost import apply_keyword_boost
from agent.decision_engine import decide_trade_action
from agent.alert_manager import print_trade_alert
from agent.paper_trader import append_paper_trade_entry
from agent.herd_scorer import build_candidate, classify_herd_stage, merge_sources, social_score_from_level
from agent import options_client
from agent.portfolio import manage_option_exits, refresh_portfolio_prices
from agent.telegram_notifier import (
    load_pending,
    maybe_send_heartbeat,
    poll_telegram_updates,
)


PROJECT_ROOT = Path(__file__).resolve().parent
SETTINGS_PATH = PROJECT_ROOT / "settings.json"
STATE_DIR = PROJECT_ROOT / "state"
DEMO_LOCK_PATH = STATE_DIR / "demo.lock"
WATCHLIST_PATH = STATE_DIR / "watchlist.json"
EXPIRY_WATCHLIST_PATH = STATE_DIR / "expiry_watchlist.json"
QUADRANT_PATH = STATE_DIR / "quadrant_candidates.json"
HIGH_ALERT_PATH = STATE_DIR / "high_alert.json"
NEWS_CATALYST_PATH = STATE_DIR / "news_catalyst_watchlist.json"
HEALTH_PATH = STATE_DIR / "health.json"
RUNTIME_LOCK_PATH = STATE_DIR / "agent.pid"

SCAN_LOCK = threading.Lock()
SOCIAL_CACHE_LOCK = threading.Lock()
SOCIAL_CACHE: Dict[str, Dict[str, Any]] = {}
STATE_SNAPSHOT_LOCK = threading.Lock()
STATE_SNAPSHOT: Dict[str, Any] = {"cycle_id": 0, "watchlist": [], "high_alert": [], "updated_at": None, "pid": os.getpid()}
HIGH_ALERT_REGISTRY_LOCK = threading.Lock()
HIGH_ALERT_REGISTRY: Dict[str, Dict[str, Any]] = {}
SOCIAL_COOLDOWN_LOCK = threading.Lock()
SOCIAL_COOLDOWN: Dict[str, int] = {}


# ---------------------------------------------------------------------------
# Demo mode & settings
# ---------------------------------------------------------------------------


def demo_mode_active() -> bool:
    """Return True when demo.lock is present — live agent should not overwrite state."""
    return DEMO_LOCK_PATH.exists()


def load_settings() -> Dict[str, Any]:
    """
    Load agent settings from JSON with minimal safe defaults.

    Inputs:
    - None.

    Output:
    - Dictionary containing screener/social/news/agent/claude settings.

    Why this exists:
    - Runtime behavior should be configurable without modifying code.
    """
    defaults: Dict[str, Any] = {
        "screener": {
            "scan_interval_seconds": 15,
            "finviz_max_rows": 200,
            "max_watchlist_symbols": 60,
            "provider": "scraper",
            "include_mid_large_cap": True,
            "mid_large": {
                "market_cap_min_billion": 2,
                "price_change_min": -8.0,
                "price_change_max": 8.0,
                "volume_multiplier": 1.5,
                "require_optionable": True,
                "finviz_max_rows": 120,
            },
            "small_quiet_watchlist_share": 0.4,
            "scraper": {
                "request_timeout_seconds": 8,
                "page_sleep_seconds": 0,
                "max_pages": 10,
                "max_workers": 3,
            },
        },
        "expiry_screener": {
            "enabled": True,
            "scan_interval_seconds": 60,
            "max_dte": 0,
            "min_total_oi": 5000,
            "min_relative_volume": 1.5,
            "max_rows": 100,
            "max_watchlist_symbols": 30,
        },
        "unified_decision": {
            "expiry_override_review": True,
            "expiry_buy_min_options_score": 65,
            "expiry_buy_min_urgency": 45,
        },
        "alpaca": {
            "enabled": True,
            "provider": "alpaca_paper",
            "api_key_env": "ALPACA_API_KEY",
            "secret_key_env": "ALPACA_SECRET_KEY",
            "require_broker_ack": False,
            "mirror_local_portfolio": True,
        },
        "notifications": {
            "telegram_enabled": True,
            "notify_on": ["BUY", "SELL", "REVIEW"],
            "notify_review_leans": ["BUY", "SELL"],
            "min_review_lean_pct": 55,
            "cooldown_minutes": 60,
            "heartbeat_minutes": 60,
            "pending_ttl_minutes": 8,
            "confirm_auto_trades": False,
        },
        "news_decay": {"enabled": True, "half_life_minutes": 45},
        "odte_screener": {
            "enabled": True,
            "scan_interval_seconds": 120,
            "min_setup_score": 55,
            "max_universe": 40,
            "max_watchlist_symbols": 24,
            "include_finviz_scan": True,
            "require_watchlist_for_path_a": False,
            "require_watchlist_for_path_b": True,
        },
        "execution": {
            "autonomous_buy_sell": True,
            "force_review_all": False,
            "review_only_on_conflict": True,
            "review_ttl_minutes": 8,
            "conflict_min_sources": 2,
            "min_confidence_for_action": 40,
            "min_confidence_for_path_b": 65,
            "min_lean_pct_for_path_b_execute": 60,
            "min_lean_over_wait_pct": 10,
            "require_options_bias_to_autoresolve": True,
            "market_hours_only": True,
            "no_post_1545_opens": True,
            "exit_on_signal_flip": False,
            "min_hold_minutes_before_flip": 8,
            "flip_min_confidence": 70,
            "flip_reentry_cooldown_minutes": 30,
            "flip_strong_reentry_confidence": 80,
            "require_live_nbbo": True,
            "identical_quote_pause_count": 3,
            "path_b_auto_execute": False,
            "path_a2_auto_execute": False,
        },
        "risk": {
            "enabled": True,
            "risk_fraction_per_trade": 0.01,
            "max_concurrent_0dte": 3,
            "max_correlated_group": 1,
            "daily_loss_circuit_pct": 0.03,
            "max_contracts_per_trade": 10,
            "max_new_0dte_entries_per_day": 5,
            "min_minutes_between_entries_same_ticker": 240,
            "force_review_all": False,
        },
        "social": {
            "stocktwits_posts_to_fetch": 30,
            "high_alert_threshold": 3,
            "watch_threshold": 1,
            "social_max_workers": 8,
            "social_request_timeout_seconds": 8,
            "social_cache_ttl_seconds": 20,
            "max_post_age_hours": 24,
            "max_retries": 1,
            "retry_backoff_ms": 250,
            "quiet_expected_misses": True,
            "enable_keyword_aliases": True,
            "symbol_cooldown_cycles": 2,
        },
        "herd_alert": {
            "enabled": True,
            "news_score_abs_min": 0.5,
            "news_max_age_hours": 4,
            "max_news_score_per_cycle": 6,
            "volume_rvol_percentile_min": 0.9,
            "volume_rvol_floor": 2.0,
            "volume_abs_pct_change_min": 1.0,
        },
        "news": {
            "high_alert_poll_seconds": 15,
            "watch_poll_seconds": 300,
            "article_text_max_chars": 3000,
            "max_article_age_hours": 4,
            "exclude_law_firm_solicitations": True,
            "sources": {
                "pr_newswire": {"enabled": True},
                "globe_newswire": {"enabled": True},
                "business_wire": {"enabled": True},
                "newsfile": {"enabled": True},
                "access_newswire": {"enabled": True},
                "sec_edgar": {"enabled": True, "forms": ["8-K"]},
                "yahoo": {"enabled": True},
                "benzinga": {"enabled": True},
                "marketwatch": {"enabled": True},
            },
        },
        "news_catalyst": {
            "enabled": True,
            "poll_seconds": 90,
            "max_article_age_hours": 4,
            "max_candidates_per_cycle": 12,
            "buy_threshold": 0.55,
            "sell_threshold": -0.55,
            "review_threshold": 0.35,
            "include_finviz_movers": True,
            "max_finviz_movers": 8,
            "finviz_price_change_min": -12.0,
            "finviz_price_change_max": 12.0,
            "finviz_volume_multiplier": 1.2,
            "finviz_max_rows": 80,
            "require_watchlist_for_0dte": False,
            "extra_tickers": [],
        },
        "agent": {
            "buy_threshold": 0.5,
            "sell_threshold": -0.5,
            "require_social_signal": True,
            "paper_trading": True,
            "high_alert_ttl_seconds": 600,
            "path_a_zero_alert_cycles": 3,
            "path_a_zero_alerts_rth_only": True,
            "path_a_enabled": True,
            "path_a_zero_alerts_enabled": True,
        },
        "trading": {
            "auto_execute": True,
            "instrument": "options",
            "options_expiry_horizon": "range",
            "deadline_date": "2026-07-31",
            "options_dte_range": [0, 30],
            "options_max_dte": 5,
            "review_requires_approval": True,
            "starting_cash": 100000,
            "max_positions": 10,
            "allow_short": True,
            "options_exits": {
                "take_profit_pct": 0.40,
                "stop_loss_pct": 0.30,
                "eod_flatten_et": "15:45",
                "deadline_flatten_weekday": 4,
            },
        },
        "runtime": {"single_instance_required": True, "state_write_atomic": True, "stale_buffer_seconds": 90},
        "options_confirmation": {
            "enabled": False,
            "engine_path": "/Users/strzala/Desktop/internship project/options_confirmation_engine",
            "chain_provider": "auto",
            "require_confirmation_for_buy": True,
            "require_confirmation_for_sell": True,
            "min_options_score_bullish": 60,
            "max_options_score_bearish": 40,
            "offline_mode": False,
            "no_data_policy": "block",
            "no_data_strong_news_threshold": 0.75,
            "min_options_quality_to_trust": 0.25,
        },
    }
    try:
        data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            defaults = merge_nested_dicts(defaults, data)
    except Exception as error:
        print(f"[main] Failed loading settings.json, using defaults: {error}")
    return defaults


# ---------------------------------------------------------------------------
# Persisted state I/O & process lock
# ---------------------------------------------------------------------------


def merge_nested_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge dictionaries without dropping nested defaults.

    Inputs:
    - base: default dictionary.
    - override: user-provided dictionary.

    Output:
    - Merged dictionary.

    Why this exists:
    - A shallow `.update()` can accidentally erase nested default keys.
    """
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_nested_dicts(dict(merged[key]), value)
        else:
            merged[key] = value
    return merged


def load_json_file(path: Path, default_value: Any) -> Any:
    """
    Load JSON data from disk and return a fallback if unavailable.

    Inputs:
    - path: target JSON file path.
    - default_value: value returned on missing/invalid file.

    Output:
    - Parsed JSON object or default_value.

    Why this exists:
    - Robust state handling prevents startup crashes from missing files.
    """
    try:
        if not path.exists():
            return default_value
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:
        print(f"[main] Could not load {path.name}: {error}")
        return default_value


def extract_state_items(data: Any) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Normalize either list-only or wrapped state payload format.

    Inputs:
    - data: parsed JSON payload from state file.

    Output:
    - Tuple of (items list, metadata dict).

    Why this exists:
    - We support old list-only and new wrapped formats without breaking reads.
    """
    if isinstance(data, list):
        return data, {}
    if isinstance(data, dict):
        items = data.get("items", [])
        meta = data.get("meta", {})
        return items if isinstance(items, list) else [], meta if isinstance(meta, dict) else {}
    return [], {}


def load_state_list(path: Path) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Load normalized list state and metadata from disk.

    Inputs:
    - path: state file path.

    Output:
    - Tuple of (items, meta).

    Why this exists:
    - Cycle consumers need consistent list payloads regardless of file version.
    """
    raw = load_json_file(path, [])
    return extract_state_items(raw)


def save_state_list(path: Path, items: List[Dict[str, Any]], meta: Dict[str, Any], state_write_atomic: bool) -> None:
    """
    Save state list with metadata, optionally using atomic file replacement.

    Inputs:
    - path: destination file path.
    - items: state list payload.
    - meta: metadata dictionary.
    - state_write_atomic: whether to write temp file and replace.

    Output:
    - None. Writes state file.

    Why this exists:
    - Atomic writes prevent readers from observing partially-written JSON.
    """
    payload = {"meta": meta, "items": items}
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if state_write_atomic:
            temp_path = path.with_suffix(path.suffix + ".tmp")
            temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            temp_path.replace(path)
        else:
            path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception as error:
        print(f"[main] Could not save {path.name}: {error}")


def save_json_file(path: Path, data: Any) -> None:
    """
    Save JSON data to disk with indentation for readability.

    Inputs:
    - path: destination file path.
    - data: serializable Python object.

    Output:
    - None. Writes data to disk.

    Why this exists:
    - Persistent state allows the dashboard and scheduler to share
      watchlist and alert context across loop cycles.
    """
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as error:
        print(f"[main] Could not save {path.name}: {error}")


def save_json_payload(path: Path, data: Dict[str, Any], state_write_atomic: bool) -> None:
    """
    Save a dictionary payload, optionally atomically.

    Inputs:
    - path: output JSON path.
    - data: JSON-serializable dictionary.
    - state_write_atomic: whether to use temp+replace write mode.

    Output:
    - None.

    Why this exists:
    - Health metadata needs the same safe-write behavior as state files.
    """
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if state_write_atomic:
            temp_path = path.with_suffix(path.suffix + ".tmp")
            temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            temp_path.replace(path)
        else:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception as error:
        print(f"[main] Could not save {path.name}: {error}")


def is_process_running(pid: int) -> bool:
    """
    Check whether a process id appears to be alive.

    Inputs:
    - pid: process id integer.

    Output:
    - True if process exists, otherwise False.

    Why this exists:
    - Used by single-instance guard to avoid concurrent writers.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def release_runtime_lockfile() -> None:
    """
    Remove pid lockfile if owned by this process.

    Inputs:
    - None.

    Output:
    - None.

    Why this exists:
    - Prevents stale lockfiles from blocking future clean startups.
    """
    try:
        if not RUNTIME_LOCK_PATH.exists():
            return
        data = json.loads(RUNTIME_LOCK_PATH.read_text(encoding="utf-8"))
        lock_pid = int(data.get("pid", -1))
        if lock_pid == os.getpid():
            RUNTIME_LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass


def acquire_runtime_lockfile(single_instance_required: bool) -> bool:
    """
    Acquire single-instance pid lock for this agent process.

    Inputs:
    - single_instance_required: whether duplicate instance should be blocked.

    Output:
    - True when process can continue, False when it should exit.

    Why this exists:
    - Multiple instances writing `state/*.json` can create contradictory state.
    """
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        if RUNTIME_LOCK_PATH.exists():
            lock = json.loads(RUNTIME_LOCK_PATH.read_text(encoding="utf-8"))
            existing_pid = int(lock.get("pid", -1))
            if existing_pid != os.getpid() and is_process_running(existing_pid):
                if single_instance_required:
                    print(f"[main] Another agent instance is running (pid={existing_pid}). Exiting.")
                    return False
            else:
                RUNTIME_LOCK_PATH.unlink(missing_ok=True)

        lock_payload = {"pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat()}
        RUNTIME_LOCK_PATH.write_text(json.dumps(lock_payload, indent=2), encoding="utf-8")
        atexit.register(release_runtime_lockfile)
        return True
    except Exception as error:
        print(f"[main] Could not acquire runtime lockfile: {error}")
        return not single_instance_required


# ---------------------------------------------------------------------------
# Social scan cache & per-ticker workers
# ---------------------------------------------------------------------------


def get_cached_social_result(ticker: str, cache_ttl_seconds: int) -> Optional[Dict[str, Any]]:
    """
    Return recently cached social scan results if they are still fresh.

    Inputs:
    - ticker: stock symbol key.
    - cache_ttl_seconds: maximum cache age in seconds.

    Output:
    - Cached social result dictionary or None when stale/missing.

    Why this exists:
    - Avoiding repeated API calls for unchanged symbols reduces cycle time.
    """
    now = time.time()
    with SOCIAL_CACHE_LOCK:
        cached = SOCIAL_CACHE.get(ticker)
        if not cached:
            return None
        age = now - float(cached.get("ts", 0))
        if age > cache_ttl_seconds:
            return None
        return dict(cached.get("result", {}))


def set_cached_social_result(ticker: str, result: Dict[str, Any]) -> None:
    """
    Save social scan output in memory for short-term reuse.

    Inputs:
    - ticker: stock symbol key.
    - result: scan result dictionary.

    Output:
    - None.

    Why this exists:
    - In-memory caching cuts duplicate network requests between close cycles.
    """
    with SOCIAL_CACHE_LOCK:
        SOCIAL_CACHE[ticker] = {"ts": time.time(), "result": dict(result)}


def scan_social_for_ticker(
    ticker: str,
    posts_to_fetch: int,
    request_timeout_seconds: int,
    cache_ttl_seconds: int,
    max_post_age_hours: int,
    high_alert_threshold: int,
    watch_threshold: int,
    max_retries: int,
    retry_backoff_ms: int,
    quiet_expected_misses: bool,
    enable_keyword_aliases: bool,
) -> Tuple[str, Dict[str, Any], float, bool]:
    """
    Fetch social signal for one ticker with cache and latency tracking.

    Inputs:
    - ticker: stock symbol.
    - posts_to_fetch: number of posts to fetch.
    - request_timeout_seconds: timeout per HTTP request.
    - cache_ttl_seconds: social-result cache freshness window.
    - max_post_age_hours: maximum age for social posts included in scoring.

    Output:
    - Tuple of (ticker, social_result, latency_seconds, from_cache).

    Why this exists:
    - A single worker function enables simple parallel execution with
      consistent timing and caching behavior.
    """
    cached = get_cached_social_result(ticker=ticker, cache_ttl_seconds=cache_ttl_seconds)
    if cached is not None:
        return ticker, cached, 0.0, True

    start = time.perf_counter()
    result = scan_ticker_social_signal(
        ticker=ticker,
        posts_to_fetch=posts_to_fetch,
        request_timeout_seconds=request_timeout_seconds,
        max_post_age_hours=max_post_age_hours,
        high_alert_threshold=high_alert_threshold,
        watch_threshold=watch_threshold,
        max_retries=max_retries,
        retry_backoff_ms=retry_backoff_ms,
        quiet_expected_misses=quiet_expected_misses,
        enable_keyword_aliases=enable_keyword_aliases,
    )
    latency = time.perf_counter() - start
    set_cached_social_result(ticker=ticker, result=result)
    return ticker, result, latency, False


# ---------------------------------------------------------------------------
# Path A — Finviz universe + StockTwits tagging (scheduled)
# ---------------------------------------------------------------------------


def refresh_watchlist_and_social(settings: Dict[str, Any]) -> None:
    """
    Run FinViz screening and StockTwits scanning to update alert state.

    Inputs:
    - settings: full settings dictionary.

    Output:
    - None. Writes watchlist and high_alert state JSON files.

    Why this exists:
    - This scheduled job populates the ticker universe and social-signal
      intensity used by downstream news polling loops.
    """
    runtime_cfg = settings.get("runtime", {})
    state_write_atomic = bool(runtime_cfg.get("state_write_atomic", True))
    if demo_mode_active():
        print("[main] demo_mode_active: skipping watchlist refresh (remove state/demo.lock to resume live agent).")
        return
    if not bool((settings.get("agent") or {}).get("path_a_enabled", True)):
        # Path A paused (e.g. Claude credits down) — keep Path B-only day quiet.
        return
    if not SCAN_LOCK.acquire(blocking=False):
        print("[main] scan_skipped_due_to_overlap: previous refresh cycle still running.")
        with STATE_SNAPSHOT_LOCK:
            last_cycle_id = int(STATE_SNAPSHOT.get("cycle_id", 0))
        save_json_payload(
            HEALTH_PATH,
            {
                "cycle_id": last_cycle_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "source_pid": os.getpid(),
                "scan_skipped_due_to_overlap": True,
                "state_write_status": "skipped_due_to_overlap",
            },
            state_write_atomic=state_write_atomic,
        )
        return

    cycle_start = time.perf_counter()
    try:
        screener_cfg = settings.get("screener", {})
        social_cfg = settings.get("social", {})
        agent_cfg = settings.get("agent", {})
        runtime_cfg = settings.get("runtime", {})

        finviz_start = time.perf_counter()
        watchlist, finviz_stats = screen_path_a_universe_with_stats(
            price_change_min=float(screener_cfg.get("price_change_min", -0.5)),
            price_change_max=float(screener_cfg.get("price_change_max", 0.5)),
            volume_multiplier=float(screener_cfg.get("volume_multiplier", 1.5)),
            market_cap_max_billion=float(screener_cfg.get("market_cap_max_billion", 2)),
            max_rows=int(screener_cfg.get("finviz_max_rows", 200)),
            screener_cfg=screener_cfg,
        )
        finviz_seconds = time.perf_counter() - finviz_start
        if not finviz_stats.get("scrape_ok", True):
            print(
                f"[path_a][finviz] scrape failed: {finviz_stats.get('scrape_error') or 'unknown'} "
                f"(provider={finviz_stats.get('provider')})"
            )

        max_watchlist_symbols = int(screener_cfg.get("max_watchlist_symbols", 60))
        if max_watchlist_symbols > 0:
            watchlist = watchlist[:max_watchlist_symbols]

        # Add metadata used by dashboard and monitoring loops.
        now_utc = datetime.now(timezone.utc)
        now_text = now_utc.isoformat()
        for stock in watchlist:
            stock["added_at"] = now_text
            stock.setdefault("source", "news")
            # Preserve herd inputs for quadrant / urgency.
            if stock.get("relative_volume") is None and stock.get("average_volume"):
                avg = float(stock.get("average_volume") or 0)
                vol = float(stock.get("volume") or 0)
                if avg > 0:
                    stock["relative_volume"] = round(vol / avg, 2)

        high_alert_data: List[Dict[str, Any]] = []
        posts_to_fetch = int(social_cfg.get("stocktwits_posts_to_fetch", 30))
        social_workers = max(1, int(social_cfg.get("social_max_workers", 8)))
        social_timeout = max(2, int(social_cfg.get("social_request_timeout_seconds", 8)))
        social_ttl = max(0, int(social_cfg.get("social_cache_ttl_seconds", 90)))
        max_post_age_hours = max(1, int(social_cfg.get("max_post_age_hours", 24)))
        high_alert_threshold = max(1, int(social_cfg.get("high_alert_threshold", 3)))
        watch_threshold = max(0, int(social_cfg.get("watch_threshold", 1)))
        max_retries = max(0, int(social_cfg.get("max_retries", 1)))
        retry_backoff_ms = max(0, int(social_cfg.get("retry_backoff_ms", 250)))
        quiet_expected_misses = bool(social_cfg.get("quiet_expected_misses", True))
        enable_keyword_aliases = bool(social_cfg.get("enable_keyword_aliases", True))
        symbol_cooldown_cycles = max(0, int(social_cfg.get("symbol_cooldown_cycles", 2)))

        social_start = time.perf_counter()
        social_latencies: List[Tuple[str, float]] = []
        cache_hits = 0
        social_reason_counts: Dict[str, int] = {}
        total_posts_fetched = 0
        total_recent_posts = 0
        total_posts_matched = 0
        cooldown_skips = 0
        tickers_checked = 0
        keyword_hit_tickers = 0
        keywords_matched: set = set()
        api_ok = 0
        api_errors: Dict[str, int] = {}
        _API_ERROR_REASONS = {
            "rate_limited",
            "symbol_not_found",
            "fetch_error",
            "scan_exception",
        }

        with SOCIAL_COOLDOWN_LOCK:
            for cooldown_ticker in list(SOCIAL_COOLDOWN.keys()):
                remaining = int(SOCIAL_COOLDOWN.get(cooldown_ticker, 0)) - 1
                if remaining <= 0:
                    SOCIAL_COOLDOWN.pop(cooldown_ticker, None)
                else:
                    SOCIAL_COOLDOWN[cooldown_ticker] = remaining

        with ThreadPoolExecutor(max_workers=social_workers) as executor:
            future_map = {}
            for stock in watchlist:
                ticker = str(stock.get("ticker", "")).upper()
                if not ticker:
                    continue
                with SOCIAL_COOLDOWN_LOCK:
                    remaining_cycles = int(SOCIAL_COOLDOWN.get(ticker, 0))
                if remaining_cycles > 0:
                    stock["social_signal_level"] = "IGNORE"
                    stock["social_total_score"] = 0
                    stock["social_triggered_posts"] = []
                    stock["social_reason_code"] = "cooldown_skip"
                    stock["social_posts_fetched"] = 0
                    stock["social_recent_posts_scanned"] = 0
                    stock["social_posts_matched"] = 0
                    social_reason_counts["cooldown_skip"] = social_reason_counts.get("cooldown_skip", 0) + 1
                    cooldown_skips += 1
                    continue
                future_map[
                    executor.submit(
                        scan_social_for_ticker,
                        ticker,
                        posts_to_fetch,
                        social_timeout,
                        social_ttl,
                        max_post_age_hours,
                        high_alert_threshold,
                        watch_threshold,
                        max_retries,
                        retry_backoff_ms,
                        quiet_expected_misses,
                        enable_keyword_aliases,
                    )
                ] = stock
                tickers_checked += 1

            for future in as_completed(future_map):
                stock = future_map[future]
                ticker = str(stock.get("ticker", ""))
                try:
                    _, social_result, latency, from_cache = future.result()
                    if from_cache:
                        cache_hits += 1
                    else:
                        social_latencies.append((ticker, latency))
                    stock["social_signal_level"] = social_result.get("escalation_level", "IGNORE")
                    stock["social_total_score"] = social_result.get("total_score", 0)
                    stock["social_triggered_posts"] = social_result.get("triggered_posts", [])
                    stock["social_posts_fetched"] = int(social_result.get("posts_fetched", 0))
                    stock["social_recent_posts_scanned"] = int(social_result.get("recent_posts_scanned", 0))
                    stock["social_posts_matched"] = int(social_result.get("posts_matched", len(stock["social_triggered_posts"])))
                    reason_code = str(social_result.get("reason_code", "unknown"))
                    stock["social_reason_code"] = reason_code
                    social_reason_counts[reason_code] = social_reason_counts.get(reason_code, 0) + 1
                    total_posts_fetched += int(stock["social_posts_fetched"])
                    total_recent_posts += int(stock["social_recent_posts_scanned"])
                    total_posts_matched += int(stock["social_posts_matched"])

                    if reason_code in _API_ERROR_REASONS or reason_code.startswith("http_"):
                        api_errors[reason_code] = api_errors.get(reason_code, 0) + 1
                    else:
                        api_ok += 1

                    triggered = stock["social_triggered_posts"]
                    if isinstance(triggered, list) and triggered:
                        keyword_hit_tickers += 1
                        for post in triggered:
                            if not isinstance(post, dict):
                                continue
                            for kw in post.get("keywords_found") or []:
                                text = str(kw).strip()
                                if text:
                                    keywords_matched.add(text)

                    if symbol_cooldown_cycles > 0 and reason_code in {"symbol_not_found", "no_recent_posts"}:
                        with SOCIAL_COOLDOWN_LOCK:
                            SOCIAL_COOLDOWN[ticker.upper()] = symbol_cooldown_cycles

                    if stock["social_signal_level"] == "HIGH_ALERT":
                        high_alert_data.append(stock)
                except Exception as error:  # Defensive: one ticker failure should not stop scan.
                    print(f"[main] Social scan failed for {ticker}: {error}")
                    stock["social_signal_level"] = "IGNORE"
                    stock["social_total_score"] = 0
                    stock["social_triggered_posts"] = []
                    stock["social_reason_code"] = "scan_exception"
                    stock["social_posts_fetched"] = 0
                    stock["social_recent_posts_scanned"] = 0
                    stock["social_posts_matched"] = 0
                    social_reason_counts["scan_exception"] = social_reason_counts.get("scan_exception", 0) + 1
                    api_errors["scan_exception"] = api_errors.get("scan_exception", 0) + 1
                    continue

        # Multi-path herd promotion: StockTwits OR news_catalyst OR volume_spike.
        herd_stats: Dict[str, Any] = {}
        try:
            from agent.herd_alert import apply_multi_path_high_alert, collect_news_scores_for_watchlist

            news_scores = collect_news_scores_for_watchlist(watchlist, settings)
            herd_stats = apply_multi_path_high_alert(watchlist, settings, news_by_ticker=news_scores)
            high_alert_data = [
                stock
                for stock in watchlist
                if str(stock.get("social_signal_level") or "").upper() == "HIGH_ALERT"
            ]
            print(
                "[main][herd_alert] HIGH_ALERT="
                f"{herd_stats.get('high_alert_total', 0)} "
                f"by_path={herd_stats.get('by_path')} "
                f"promoted_new={herd_stats.get('promoted_new', 0)} "
                f"news_scored={len(news_scores)}"
            )
        except Exception as herd_error:
            print(f"[main][herd_alert] promotion failed (keeping StockTwits tags): {herd_error}")
            herd_stats = {}

        social_seconds = time.perf_counter() - social_start
        with STATE_SNAPSHOT_LOCK:
            cycle_id = int(STATE_SNAPSHOT.get("cycle_id", 0)) + 1

        # Apply bounded persistence to reduce high-alert flapping between cycles.
        ttl_seconds = max(60, int(agent_cfg.get("high_alert_ttl_seconds", 600)))
        expires_at = now_utc + timedelta(seconds=ttl_seconds)
        with HIGH_ALERT_REGISTRY_LOCK:
            for stock in high_alert_data:
                ticker = str(stock.get("ticker", "")).upper()
                if not ticker:
                    continue
                existing = HIGH_ALERT_REGISTRY.get(ticker)
                first_alert_at = str(existing.get("first_alert_at")) if isinstance(existing, dict) and existing.get("first_alert_at") else now_text
                stock["first_alert_at"] = first_alert_at
                HIGH_ALERT_REGISTRY[ticker] = {
                    "stock": stock,
                    "expires_at": expires_at,
                    "first_alert_at": first_alert_at,
                    "last_seen_at": now_text,
                }

            expired = [ticker for ticker, entry in HIGH_ALERT_REGISTRY.items() if entry["expires_at"] <= now_utc]
            for ticker in expired:
                HIGH_ALERT_REGISTRY.pop(ticker, None)

            stabilized_high_alerts = [entry["stock"] for entry in HIGH_ALERT_REGISTRY.values()]
            stabilized_high_alerts = sorted(stabilized_high_alerts, key=lambda item: str(item.get("ticker", "")))

        state_write_atomic = bool(runtime_cfg.get("state_write_atomic", True))
        watchlist_meta = {"cycle_id": cycle_id, "updated_at": now_text, "source_pid": os.getpid()}
        high_alert_meta = {
            "cycle_id": cycle_id,
            "updated_at": now_text,
            "source_pid": os.getpid(),
            "ttl_seconds": ttl_seconds,
            "herd_alert_by_path": (herd_stats or {}).get("by_path"),
        }
        save_state_list(WATCHLIST_PATH, watchlist, watchlist_meta, state_write_atomic=state_write_atomic)
        save_state_list(HIGH_ALERT_PATH, stabilized_high_alerts, high_alert_meta, state_write_atomic=state_write_atomic)

        with STATE_SNAPSHOT_LOCK:
            STATE_SNAPSHOT["cycle_id"] = cycle_id
            STATE_SNAPSHOT["watchlist"] = list(watchlist)
            STATE_SNAPSHOT["high_alert"] = list(stabilized_high_alerts)
            STATE_SNAPSHOT["updated_at"] = now_text
            STATE_SNAPSHOT["pid"] = os.getpid()

        total_seconds = time.perf_counter() - cycle_start
        slowest = sorted(social_latencies, key=lambda x: x[1], reverse=True)[:5]
        slowest_text = ", ".join([f"{ticker}:{latency:.2f}s" for ticker, latency in slowest]) or "none"
        print(f"[main] Watchlist updated: {len(watchlist)} stocks | High alert: {len(stabilized_high_alerts)} | pid={os.getpid()}")
        print(
            "[main][timing] cycle_total={:.2f}s finviz={:.2f}s social={:.2f}s "
            "social_cache_hits={} social_workers={} slowest_social={}".format(
                total_seconds,
                finviz_seconds,
                social_seconds,
                cache_hits,
                social_workers,
                slowest_text,
            )
        )
        zero_reason = "ok"
        if len(watchlist) == 0:
            zero_reason = "no_screener_matches"
        elif len(stabilized_high_alerts) == 0:
            dominant_social_reason = max(social_reason_counts.items(), key=lambda item: item[1])[0] if social_reason_counts else "no_social_data"
            zero_reason = f"no_herd_high_alerts:{dominant_social_reason}"
        health_payload = {
            "cycle_id": cycle_id,
            "updated_at": now_text,
            "source_pid": os.getpid(),
            "watchlist_count": len(watchlist),
            "high_alert_count": len(stabilized_high_alerts),
            "herd_alert_by_path": (herd_stats or {}).get("by_path") or {},
            "social_reason_counts": social_reason_counts,
            "social_posts_fetched_total": total_posts_fetched,
            "social_posts_recent_total": total_recent_posts,
            "social_posts_matched_total": total_posts_matched,
            "cooldown_skips": cooldown_skips,
            "scan_skipped_due_to_overlap": False,
            "state_write_status": "ok",
            "zero_reason": zero_reason,
            "timing": {
                "cycle_total_seconds": round(total_seconds, 3),
                "finviz_seconds": round(finviz_seconds, 3),
                "social_seconds": round(social_seconds, 3),
            },
            "finviz_provider": str(screener_cfg.get("provider", "scraper")),
            "finviz_ok": finviz_seconds < 15.0,
            "finviz_elite_ok": finviz_seconds < 5.0,
        }
        save_json_payload(HEALTH_PATH, health_payload, state_write_atomic=state_write_atomic)
        print(
            f"[main][health] cycle_id={cycle_id} watchlist_count={len(watchlist)} "
            f"high_alert_count={len(stabilized_high_alerts)} state_write_status=ok reason={zero_reason} "
            f"posts_fetched={total_posts_fetched} posts_recent={total_recent_posts} posts_matched={total_posts_matched}"
        )
        try:
            from agent.path_a_pipeline_health import record_screener_cycle

            tagging_counts = {"HIGH_ALERT": 0, "WATCH": 0, "IGNORE": 0}
            for stock in watchlist:
                level = str(stock.get("social_signal_level", "IGNORE")).upper()
                if level not in tagging_counts:
                    level = "IGNORE"
                tagging_counts[level] += 1

            path_a_health = record_screener_cycle(
                {
                    "cycle_id": cycle_id,
                    "finviz": {
                        "raw": int(finviz_stats.get("raw") or 0),
                        "after_filters": int(finviz_stats.get("after_filters") or len(watchlist)),
                        "scrape_ok": bool(finviz_stats.get("scrape_ok", True)),
                        "scrape_error": finviz_stats.get("scrape_error"),
                        "provider": str(finviz_stats.get("provider") or screener_cfg.get("provider", "scraper")),
                        "elapsed_sec": finviz_stats.get("elapsed_sec")
                        if finviz_stats.get("elapsed_sec") is not None
                        else round(finviz_seconds, 3),
                    },
                    "stocktwits": {
                        "tickers_checked": tickers_checked,
                        "api_ok": api_ok,
                        "api_errors": api_errors,
                        "keyword_hits": keyword_hit_tickers,
                        "keywords_matched": sorted(keywords_matched),
                        "reason_counts": social_reason_counts,
                    },
                    "tagging": tagging_counts,
                    "herd_alert_by_path": (herd_stats or {}).get("by_path") or {},
                    "herd_alert_thresholds": (herd_stats or {}).get("thresholds") or {},
                    "zero_reason": zero_reason,
                },
                settings,
            )
            if path_a_health.get("_should_notify"):
                try:
                    from agent.telegram_notifier import send_text

                    stages = ", ".join(path_a_health.get("_notify_messages") or [])
                    send_text(
                        "Path A pipeline warning: consecutive zero stage(s) "
                        f"[{stages}] (threshold={path_a_health.get('alert_threshold')}). "
                        f"funnel={path_a_health.get('funnel_line')}",
                        settings,
                    )
                except Exception as notify_error:
                    print(f"[main] Path A pipeline Telegram alert failed: {notify_error}")
        except Exception as health_error:
            print(f"[main] Path A screener health update failed: {health_error}")
        try:
            if bool(settings.get("trading", {}).get("auto_execute", True)):
                if _options_session_active(settings):
                    exit_fills = manage_option_exits(settings)
                    if exit_fills:
                        print(f"[main][portfolio] option exits: {len(exit_fills)} close(s)")
                else:
                    print("[main][portfolio] options market closed — skip option exits/marks")
                try:
                    from agent.near_miss_tracker import tick_pending_near_misses

                    nm_updated = tick_pending_near_misses(settings)
                    if nm_updated:
                        print(f"[main][near_miss] updated {nm_updated} shadow checkpoint(s)")
                except Exception as error:
                    print(f"[main][near_miss] tick failed: {error}")
                summary = refresh_portfolio_prices(settings)
                print(
                    f"[main][portfolio] equity=${summary.get('equity', 0):,.0f} "
                    f"return={summary.get('return_pct', 0):+.2f}% "
                    f"positions={summary.get('open_positions', 0)}"
                )
                health_payload["portfolio"] = summary
                save_json_payload(HEALTH_PATH, health_payload, state_write_atomic=state_write_atomic)
        except Exception as error:
            print(f"[main] Portfolio mark-to-market failed: {error}")
    finally:
        SCAN_LOCK.release()


# ---------------------------------------------------------------------------
# Path A — news → LLM → options gate → decision → paper/Telegram
# ---------------------------------------------------------------------------


def run_news_pipeline_for_tickers(tickers: List[Dict[str, Any]], settings: Dict[str, Any], tag: str) -> None:
    """
    Run news->Claude->boost->decision->alert->paper pipeline for tickers.

    Inputs:
    - tickers: list of stock state dictionaries.
    - settings: full settings dictionary.
    - tag: label for logging context (e.g., HIGH_ALERT or WATCH).

    Output:
    - None. Emits alerts and appends paper-trade logs.

    Why this exists:
    - Centralized pipeline logic avoids duplicated code between polling
      loops and ensures consistent decision behavior.
    """
    news_cfg = settings.get("news", {})
    agent_cfg = settings.get("agent", {})
    options_cfg = settings.get("options_confirmation", {})
    article_text_max_chars = int(news_cfg.get("article_text_max_chars", 3000))
    max_article_age_hours = max(1, int(news_cfg.get("max_article_age_hours", 4)))
    buy_threshold = float(agent_cfg.get("buy_threshold", 0.5))
    sell_threshold = float(agent_cfg.get("sell_threshold", -0.5))
    require_social_signal = bool(agent_cfg.get("require_social_signal", True))
    paper_trading_enabled = bool(agent_cfg.get("paper_trading", True))
    options_enabled = bool(options_cfg.get("enabled", False))
    min_options_score_bullish = float(options_cfg.get("min_options_score_bullish", 60))
    max_options_score_bearish = float(options_cfg.get("max_options_score_bearish", 40))
    require_confirmation_for_buy = bool(options_cfg.get("require_confirmation_for_buy", True))
    require_confirmation_for_sell = bool(options_cfg.get("require_confirmation_for_sell", True))
    no_data_policy = str(options_cfg.get("no_data_policy", "block"))
    no_data_strong_news_threshold = float(options_cfg.get("no_data_strong_news_threshold", 0.75))
    min_options_quality_to_trust = float(options_cfg.get("min_options_quality_to_trust", 0.25))
    unified_cfg = settings.get("unified_decision", {})

    from agent.path_a_pipeline_health import empty_score_buckets, record_pipeline_cycle, score_bucket

    tickers_in = len(tickers)
    news_with = 0
    news_without = 0
    by_source: Dict[str, int] = {}
    news_errors: List[Dict[str, Any]] = []
    claude_scored = 0
    claude_errors = 0
    score_buckets = empty_score_buckets()
    social_blocked = 0
    social_passed = 0  # genuine social clears (not IGNORE when required), regardless of later gates
    social_actionable = 0  # cleared social AND reached BUY/SELL/REVIEW
    cleared_social_blocked_downstream: Dict[str, int] = {}
    decisions_counter: Dict[str, int] = {"BUY": 0, "SELL": 0, "REVIEW": 0, "LOG": 0}
    log_reason_codes: Dict[str, int] = {}
    gate_require_social = bool(require_social_signal)

    for stock in tickers:
        ticker = str(stock.get("ticker", "")).upper()
        company_name = str(stock.get("company_name", ticker))
        social_signal_level = str(stock.get("social_signal_level", "IGNORE"))
        social_posts = stock.get("social_triggered_posts", [])
        signal_since = str(stock.get("first_alert_at", stock.get("added_at", "unknown")))
        signal_source = str(stock.get("source", "news")).lower().strip()
        catalyst_cfg = settings.get("news_catalyst") or {}
        ticker_require_social = require_social_signal
        if signal_source == "news_catalyst":
            ticker_require_social = False

        try:
            preloaded_headline = str(stock.get("headline") or "").strip()
            preloaded_source = str(stock.get("news_source") or "wire").strip()
            aggregated = aggregate_news_for_ticker(
                ticker=ticker,
                company_name=company_name,
                article_text_max_chars=article_text_max_chars,
                max_article_age_hours=max_article_age_hours,
                settings=settings,
            )
            source_counts = aggregated.get("source_counts") or {}
            if isinstance(source_counts, dict):
                for src, count in source_counts.items():
                    by_source[str(src)] = by_source.get(str(src), 0) + int(count or 0)
            for err in aggregated.get("errors") or []:
                if isinstance(err, dict):
                    news_errors.append(err)
            if not aggregated.get("has_news") and signal_source == "news_catalyst" and preloaded_headline:
                try:
                    from news.solicitation_filter import is_law_firm_solicitation
                except Exception:
                    is_law_firm_solicitation = lambda *a, **k: False  # type: ignore
                if is_law_firm_solicitation(preloaded_headline):
                    print(
                        f"[path_a][news] {ticker}: skipped law-firm solicitation headline "
                        f"({preloaded_headline[:80]})"
                    )
                    news_without += 1
                    continue
                aggregated = {
                    "has_news": True,
                    "combined_text": (
                        f"[{preloaded_source.upper()}]\n"
                        f"Headline: {preloaded_headline}\n"
                        f"Text: Catalyst headline from Path A.2 scan.\n"
                    ),
                    "matched_articles": [
                        {
                            "headline": preloaded_headline,
                            "source": preloaded_source,
                            "published_at": stock.get("published_at"),
                        }
                    ],
                    "source_counts": {preloaded_source: 1},
                    "errors": [],
                }
                by_source[preloaded_source] = by_source.get(preloaded_source, 0) + 1
            if not aggregated.get("has_news"):
                news_without += 1
                print(f"[path_a][news] {ticker}: no headlines")
                continue

            combined_text = str(aggregated.get("combined_text", ""))
            if not combined_text.strip():
                news_without += 1
                print(f"[path_a][news] {ticker}: no headlines")
                continue

            news_with += 1

            try:
                claude_result = score_news_with_claude(ticker=ticker, news_text=combined_text)
                boosted_score = apply_keyword_boost(
                    base_score=float(claude_result.get("score", 0.0)), news_text=combined_text
                )
                claude_result["score"] = boosted_score
                claude_scored += 1
                bucket = score_bucket(float(boosted_score))
                score_buckets[bucket] = int(score_buckets.get(bucket) or 0) + 1
            except Exception as score_error:
                claude_errors += 1
                print(f"[path_a][claude] {ticker}: score failed: {score_error}")
                continue

            first_article = aggregated.get("matched_articles", [{}])[0] if aggregated.get("matched_articles") else {}
            headline = extract_primary_headline(aggregated)
            source = str(first_article.get("source", "Unknown source"))

            # Post-score news_catalyst promotion into HIGH_ALERT (does not change gates).
            try:
                from agent.herd_alert import news_catalyst_qualifies

                pub_at = first_article.get("published_at") or stock.get("published_at")
                if news_catalyst_qualifies(float(boosted_score), pub_at, settings):
                    reasons = list(stock.get("alert_reason") or [])
                    if "news_catalyst" not in reasons:
                        reasons.append("news_catalyst")
                    prior = str(stock.get("social_signal_level") or "IGNORE").upper()
                    stock["social_signal_level"] = "HIGH_ALERT"
                    stock["alert_reason"] = reasons
                    stock["herd_news_score"] = float(boosted_score)
                    stock["herd_news_published_at"] = pub_at
                    ttl_seconds = max(60, int((settings.get("agent") or {}).get("high_alert_ttl_seconds", 600)))
                    now_promo = datetime.now(timezone.utc)
                    with HIGH_ALERT_REGISTRY_LOCK:
                        existing = HIGH_ALERT_REGISTRY.get(ticker)
                        first_alert_at = (
                            str(existing.get("first_alert_at"))
                            if isinstance(existing, dict) and existing.get("first_alert_at")
                            else now_promo.isoformat()
                        )
                        stock["first_alert_at"] = first_alert_at
                        HIGH_ALERT_REGISTRY[ticker] = {
                            "stock": stock,
                            "expires_at": now_promo + timedelta(seconds=ttl_seconds),
                            "first_alert_at": first_alert_at,
                            "last_seen_at": now_promo.isoformat(),
                        }
                    if prior != "HIGH_ALERT":
                        print(
                            f"[herd_alert] post-score promote {ticker} → HIGH_ALERT "
                            f"(news_catalyst score={boosted_score:+.2f})"
                        )
            except Exception as promo_error:
                print(f"[herd_alert] post-score promote failed for {ticker}: {promo_error}")

            options_result = None
            if options_enabled:
                options_result = options_client.score_ticker(ticker, settings)

            options_data_quality = None
            options_data_flags: List[str] = []
            features: Dict[str, Any] = {}
            if options_result:
                data_quality = options_result.get("data_quality", {})
                if isinstance(data_quality, dict):
                    options_data_quality = float(data_quality.get("quality_score", 0.0))
                    raw_flags = data_quality.get("flags", [])
                    if isinstance(raw_flags, list):
                        options_data_flags = [str(flag) for flag in raw_flags]
                features = options_result.get("features") or options_result.get("feature_values") or {}
                if not isinstance(features, dict):
                    features = {}

            dte_val = features.get("nearest_dte")
            dte = int(dte_val) if dte_val is not None and float(dte_val) >= 0 else None
            volume_oi_spike = features.get("volume_oi_spike", features.get("volume_to_oi_spike"))
            rel_vol = stock.get("relative_volume")
            if rel_vol is not None:
                rel_vol = float(rel_vol)

            setup_q = None
            try:
                from screener.odte_screener import setup_quality_for_ticker

                setup_q = setup_quality_for_ticker(ticker)
                odte_cfg = settings.get("odte_screener") or {}
                require_wl = bool(odte_cfg.get("require_watchlist_for_path_a", False))
                if signal_source == "news_catalyst":
                    require_wl = bool(catalyst_cfg.get("require_watchlist_for_0dte", False))
                if require_wl and setup_q is None:
                    print(f"[path_a] Skip {ticker}: not on 0DTE watchlist")
                    continue
            except Exception:
                setup_q = None

            decision, reason, decision_meta = decide_trade_action(
                ticker=ticker,
                social_signal_level=social_signal_level,
                claude_response=claude_result,
                news_headline=headline,
                news_source=source,
                buy_threshold=buy_threshold,
                sell_threshold=sell_threshold,
                require_social_signal=ticker_require_social,
                options_bias=options_result.get("options_bias") if options_result else None,
                options_score=options_result.get("options_score") if options_result else None,
                options_data_quality=options_data_quality,
                options_data_flags=options_data_flags,
                options_enabled=options_enabled,
                min_options_score_bullish=min_options_score_bullish,
                max_options_score_bearish=max_options_score_bearish,
                require_confirmation_for_buy=require_confirmation_for_buy,
                require_confirmation_for_sell=require_confirmation_for_sell,
                no_data_policy=no_data_policy,
                no_data_strong_news_threshold=no_data_strong_news_threshold,
                min_options_quality_to_trust=min_options_quality_to_trust,
                signal_source=signal_source,
                relative_volume=rel_vol,
                dte=dte,
                volume_oi_spike=float(volume_oi_spike) if volume_oi_spike is not None else None,
                expiry_override_review=bool(unified_cfg.get("expiry_override_review", True)),
                expiry_buy_min_options_score=float(unified_cfg.get("expiry_buy_min_options_score", 65)),
                expiry_buy_min_urgency=float(unified_cfg.get("expiry_buy_min_urgency", 60)),
                options_features=features,
                news_published_at=first_article.get("published_at") if isinstance(first_article, dict) else None,
                setup_quality_score=setup_q,
                settings=settings,
            )

            # Social gate metric: count a genuine clear whenever social itself is not
            # the reject (IGNORE + require_social_signal). Later liquidity/confidence
            # LOG outcomes still count as passed social — they were blocked downstream.
            social_level = str(social_signal_level or "IGNORE").upper().strip()
            social_gate_blocked = (
                decision == "LOG"
                and ticker_require_social
                and social_level == "IGNORE"
                and "require_social_signal is enabled" in str(reason)
            )
            if social_gate_blocked:
                social_blocked += 1
                if isinstance(decision_meta, dict):
                    decision_meta.setdefault("decision_reason_code", "require_social_signal")
                log_reason_codes["require_social_signal"] = log_reason_codes.get("require_social_signal", 0) + 1
            else:
                # Cleared social (or social not required for this path).
                if not (ticker_require_social and social_level == "IGNORE"):
                    social_passed += 1
                    if decision in {"BUY", "SELL", "REVIEW"}:
                        social_actionable += 1
                    elif decision == "LOG":
                        down_code = ""
                        if isinstance(decision_meta, dict):
                            down_code = str(
                                decision_meta.get("decision_reason_code")
                                or decision_meta.get("review_reason_code")
                                or ""
                            ).strip()
                        if not down_code:
                            down_code = "log_other"
                        cleared_social_blocked_downstream[down_code] = (
                            cleared_social_blocked_downstream.get(down_code, 0) + 1
                        )

            decision_key = str(decision).upper()
            if decision_key not in decisions_counter:
                decisions_counter[decision_key] = 0
            decisions_counter[decision_key] += 1
            if decision_key == "LOG":
                code = ""
                if isinstance(decision_meta, dict):
                    code = str(decision_meta.get("decision_reason_code") or "").strip()
                if code and code != "require_social_signal":
                    log_reason_codes[code] = log_reason_codes.get(code, 0) + 1
                # Surface liquidity sub-reason on the cycle console for tonight's visibility.
                if (
                    code == "liquidity_reject"
                    and isinstance(decision_meta, dict)
                    and decision_meta.get("liquidity_reject_detail")
                ):
                    print(
                        f"[main] liquidity_reject {ticker}: {decision_meta.get('liquidity_reject_detail')}"
                    )

            social_score = social_score_from_level(social_signal_level, len(social_posts) if isinstance(social_posts, list) else 0)
            herd_stage = classify_herd_stage(rel_vol, social_score, stock.get("percent_change"))
            candidate = build_candidate(
                ticker=ticker,
                source=decision_meta.get("signal_source", signal_source),
                relative_volume=rel_vol,
                social_signal_level=social_signal_level,
                social_score=social_score,
                percent_change=stock.get("percent_change"),
                news_score=float(claude_result.get("score", 0.0)),
                options_score=options_result.get("options_score") if options_result else None,
                dte=dte,
                volume_oi_spike=float(volume_oi_spike) if volume_oi_spike is not None else None,
                total_oi=features.get("total_oi"),
                decision=decision,
            )
            advisor = advise_next_action(
                ticker=ticker,
                quadrant=str(candidate.get("quadrant", "")),
                herd_stage=herd_stage,
                action_probs=decision_meta.get("action_probs") or {},
                lean=str(decision_meta.get("lean", "WAIT")),
                instrument_hint=str(decision_meta.get("instrument_hint", "stock")),
                options_score=options_result.get("options_score") if options_result else None,
                options_bias=options_result.get("options_bias") if options_result else None,
                news_score=float(claude_result.get("score", 0.0)),
                dte=dte,
                max_oi_strike=features.get("max_oi_strike"),
                relative_volume=rel_vol,
                headline=headline,
                reason=reason,
            )
            decision_meta["instrument_hint"] = advisor.get("instrument_hint", decision_meta.get("instrument_hint"))

            if decision in {"BUY", "SELL", "REVIEW"}:
                print_trade_alert(
                    ticker=ticker,
                    decision=decision,
                    score=float(claude_result.get("score", 0.0)),
                    label=str(claude_result.get("label", "neutral")),
                    confidence=str(claude_result.get("confidence", "low")),
                    source=source,
                    headline=headline,
                    reason=reason,
                    social_signal=social_signal_level,
                    signal_since=signal_since,
                    options_bias=options_result.get("options_bias") if options_result else None,
                    options_score=options_result.get("options_score") if options_result else None,
                    action_probs=decision_meta.get("action_probs"),
                    lean=str(decision_meta.get("lean")),
                    lean_pct=int(decision_meta.get("lean_pct", 0)),
                    instrument_hint=str(decision_meta.get("instrument_hint")),
                )
            else:
                tag_label = "Path A.2" if signal_source == "news_catalyst" else ticker
                print(f"[main] LOG-only decision for {tag_label}: {reason}")

            if paper_trading_enabled:
                price_hint = float(stock.get("current_price", 0.0) or 0.0)
                append_paper_trade_entry(
                    ticker=ticker,
                    decision=decision,
                    claude_response=claude_result,
                    news_headline=headline,
                    news_source=source,
                    social_signal_level=social_signal_level,
                    social_signal_posts=social_posts if isinstance(social_posts, list) else [],
                    options_score=options_result.get("options_score") if options_result else None,
                    options_bias=options_result.get("options_bias") if options_result else None,
                    options_reasoning=options_result.get("reasoning_summary", "") if options_result else "",
                    settings=settings,
                    price_hint=price_hint if price_hint > 0 else None,
                    decision_meta=decision_meta,
                    next_action=str(advisor.get("next_step", "")),
                    signal_source=str(decision_meta.get("signal_source", signal_source)),
                    herd_stage=herd_stage,
                    quadrant=str(candidate.get("quadrant", "")),
                    relative_volume=rel_vol,
                    dte=dte,
                    max_oi_strike=features.get("max_oi_strike"),
                    advisor=advisor,
                    decision_reason=reason,
                )
            upsert_quadrant_candidate(candidate, settings)
        except Exception as error:  # Defensive: one ticker cannot break whole loop.
            print(f"[main] {tag} pipeline failed for {ticker}: {error}")
            continue

    try:
        path_a_health = record_pipeline_cycle(
            {
                "tag": tag,
                "tickers_in": tickers_in,
                "news": {
                    "tickers_with_news": news_with,
                    "tickers_no_news": news_without,
                    "by_source": by_source,
                    "errors": news_errors[:20],
                },
                "claude": {
                    "scored": claude_scored,
                    "score_buckets": score_buckets,
                    "errors": claude_errors,
                },
                "social_gate": {
                    "require_social_signal": gate_require_social,
                    "blocked": social_blocked,
                    "passed": social_passed,
                    "actionable": social_actionable,
                    "cleared_blocked_downstream": cleared_social_blocked_downstream,
                },
                "decisions": decisions_counter,
                "log_reason_codes": log_reason_codes,
            },
            settings,
        )
        if path_a_health.get("_should_notify"):
            try:
                from agent.telegram_notifier import send_text

                stages = ", ".join(path_a_health.get("_notify_messages") or [])
                send_text(
                    "Path A pipeline warning: consecutive zero stage(s) "
                    f"[{stages}] (threshold={path_a_health.get('alert_threshold')}). "
                    f"funnel={path_a_health.get('funnel_line')}",
                    settings,
                )
            except Exception as notify_error:
                print(f"[main] Path A pipeline Telegram alert failed: {notify_error}")
    except Exception as health_error:
        print(f"[main] Path A pipeline health update failed: {health_error}")


# ---------------------------------------------------------------------------
# Path B / 0DTE — expiry screener, quadrant merge, herd pipeline
# ---------------------------------------------------------------------------


def upsert_quadrant_candidate(candidate: Dict[str, Any], settings: Dict[str, Any]) -> None:
    """Merge one candidate into quadrant_candidates.json."""
    runtime_cfg = settings.get("runtime", {})
    state_write_atomic = bool(runtime_cfg.get("state_write_atomic", True))
    payload = load_json_file(QUADRANT_PATH, {"updated_at": None, "items": []})
    items = payload.get("items", []) if isinstance(payload, dict) else []
    if not isinstance(items, list):
        items = []
    ticker = str(candidate.get("ticker", "")).upper()
    merged = False
    for idx, row in enumerate(items):
        if str(row.get("ticker", "")).upper() == ticker:
            existing_source = row.get("source")
            candidate["source"] = merge_sources(str(existing_source), str(candidate.get("source", "news")))
            items[idx] = {**row, **candidate}
            merged = True
            break
    if not merged:
        items.append(candidate)
    # Keep newest 100 candidates.
    items = items[-100:]
    save_json_payload(
        QUADRANT_PATH,
        {"updated_at": datetime.now(timezone.utc).isoformat(), "items": items},
        state_write_atomic=state_write_atomic,
    )


def _options_session_active(settings: Dict[str, Any]) -> bool:
    """False after the equity-options close when market_hours_only is on."""
    try:
        from agent.market_session import is_options_session_open

        return is_options_session_open(settings)
    except Exception:
        return True


def refresh_odte_screener(settings: Dict[str, Any]) -> None:
    """Upstream 0DTE setup-quality ranking (watchlist only — no trade decisions)."""
    if demo_mode_active():
        print("[main] demo_mode_active: skipping 0DTE screener.")
        return
    if not _options_session_active(settings):
        print("[main] options market closed — skipping 0DTE screener.")
        return
    odte_cfg = settings.get("odte_screener") or {}
    if not bool(odte_cfg.get("enabled", True)):
        return
    try:
        from screener.odte_screener import run_odte_screener

        # Seed catalyst set from current high-alert / watch names when present.
        catalysts: set = set()
        try:
            for path in (HIGH_ALERT_PATH, WATCHLIST_PATH):
                if path.exists():
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    items = payload.get("items") if isinstance(payload, dict) else payload
                    if isinstance(items, list):
                        for row in items:
                            if isinstance(row, dict) and row.get("ticker"):
                                catalysts.add(str(row["ticker"]).upper())
        except Exception:
            catalysts = set()
        result = run_odte_screener(settings, catalyst_tickers=catalysts)
        n = len(result.get("ranked") or [])
        print(f"[main] 0DTE screener ranked {n} names (universe={result.get('universe_size')})")
    except Exception as error:
        print(f"[main] 0DTE screener failed: {error}")


def refresh_expiry_watchlist(settings: Dict[str, Any]) -> None:
    """Path B: scan liquid optionable names and score options features."""
    if demo_mode_active():
        print("[main] demo_mode_active: skipping expiry watchlist refresh.")
        return
    if not _options_session_active(settings):
        # Listed equity options are not tradable after RTH — do not score/trade/notify.
        print("[main] options market closed — skipping Path B expiry scan/trades.")
        return
    expiry_cfg = settings.get("expiry_screener", {})
    if not bool(expiry_cfg.get("enabled", True)):
        return

    runtime_cfg = settings.get("runtime", {})
    state_write_atomic = bool(runtime_cfg.get("state_write_atomic", True))
    screener_cfg = settings.get("screener", {})
    options_enabled = bool(settings.get("options_confirmation", {}).get("enabled", False))
    from agent.market_session import effective_options_max_dte, effective_options_min_dte

    max_dte = int(effective_options_max_dte(settings))
    min_dte = int(effective_options_min_dte(settings))
    min_total_oi = float(expiry_cfg.get("min_total_oi", 5000))

    try:
        rows, universe_stats = screen_expiry_candidates_with_stats(
            screener_cfg=screener_cfg, expiry_cfg=expiry_cfg
        )
    except Exception as error:
        print(f"[main] expiry screener failed: {error}")
        import traceback

        traceback.print_exc()
        return

    max_symbols = int(expiry_cfg.get("max_watchlist_symbols", 30))
    if max_symbols > 0:
        rows = rows[:max_symbols]

    enriched: List[Dict[str, Any]] = []
    scored_for_quadrant = 0
    dropped_non_0dte = 0
    kept_0dte = 0
    for row in rows:
        ticker = str(row.get("ticker", "")).upper()
        if options_enabled:
            options_result = options_client.score_ticker(ticker, settings)
            row = enrich_expiry_row_with_options(row, options_result)
            dte = row.get("nearest_dte")
            total_oi = row.get("total_oi")

            # Always plot scored Path B names on the quadrant (including weeklies).
            candidate = build_candidate(
                ticker=ticker,
                source="expiry",
                relative_volume=row.get("relative_volume"),
                social_signal_level="IGNORE",
                percent_change=row.get("percent_change"),
                options_score=options_result.get("options_score"),
                dte=int(dte) if dte is not None else None,
                volume_oi_spike=row.get("volume_oi_spike"),
                total_oi=total_oi,
            )
            upsert_quadrant_candidate(candidate, settings)
            scored_for_quadrant += 1

            if dte is None or int(dte) > max_dte or int(dte) < min_dte:
                dropped_non_0dte += 1
                continue
            kept_0dte += 1
            if total_oi is not None and float(total_oi) < min_total_oi:
                if float(total_oi) > 0:
                    continue
            row["_options_result"] = options_result
        enriched.append(row)

    try:
        from agent.path_b_universe_health import update_universe_health

        health = update_universe_health(
            universe_stats,
            kept_0dte=kept_0dte,
            dropped_non_0dte=dropped_non_0dte,
            settings=settings,
        )
        if health.get("_should_notify"):
            try:
                from agent.telegram_notifier import send_text

                send_text(
                    "Path B universe warning: Finviz dynamic scan returned 0 rows "
                    f"for {health.get('consecutive_zero_finviz')} consecutive cycles "
                    f"(seed_count={universe_stats.get('seed_count')}). "
                    f"scrape_error={universe_stats.get('scrape_error') or 'none'}",
                    settings,
                )
            except Exception as notify_error:
                print(f"[main] Path B universe Telegram alert failed: {notify_error}")
    except Exception as health_error:
        print(f"[main] Path B universe health update failed: {health_error}")

    public_rows = []
    for row in enriched:
        public = {k: v for k, v in row.items() if not k.startswith("_")}
        public_rows.append(public)

    save_json_payload(
        EXPIRY_WATCHLIST_PATH,
        {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "count": len(public_rows),
            "items": public_rows,
            "universe_stats": {
                **universe_stats,
                "kept_0dte": kept_0dte,
                "dropped_non_0dte": dropped_non_0dte,
                "quadrant_scored": scored_for_quadrant,
            },
        },
        state_write_atomic=state_write_atomic,
    )
    print(
        f"[main] Path B universe: finviz_raw={universe_stats.get('finviz_raw')} "
        f"after_filters={universe_stats.get('after_filters')} "
        f"seeds={universe_stats.get('seed_count')} "
        f"kept_0dte={kept_0dte} dropped_non_0dte={dropped_non_0dte} "
        f"watchlist={len(public_rows)} max_dte={max_dte}"
        + (f" scrape_error={universe_stats.get('scrape_error')}" if universe_stats.get("scrape_error") else "")
    )

    # Decision/execute only while new 0DTE entries are allowed (ends at 15:45).
    try:
        from agent.market_session import is_options_entry_allowed

        if not is_options_entry_allowed(settings):
            print("[main] past entry window — Path B research scan done; skipping decision/execute loop")
            return
    except Exception:
        pass

    run_expiry_pipeline(enriched, settings)


def _path_b_is_actionable(decision: str, decision_meta: Dict[str, Any], options_result: Dict[str, Any]) -> bool:
    """Skip quiet WAIT/neutral Path B names so they do not spam phone/trade log."""
    decision_u = str(decision).upper()
    bias = str(options_result.get("options_bias", "no_data")).lower()
    score = float(options_result.get("options_score") or 50.0)
    urgency = float(decision_meta.get("herd_urgency") or 0.0)
    # BUY/SELL still need a clear options lean — seed ETFs otherwise notify every minute.
    if decision_u == "BUY":
        return bias == "bullish" and score >= 65 and urgency >= 45
    if decision_u == "SELL":
        return bias == "bearish" and score <= 35 and urgency >= 45
    if decision_u != "REVIEW":
        return False
    lean = str(decision_meta.get("lean", "WAIT")).upper()
    lean_pct = int(decision_meta.get("lean_pct") or 0)
    if lean not in {"BUY", "SELL"}:
        return False
    if lean_pct < 55:
        return False
    if bias == "bullish" and score >= 65 and urgency >= 45:
        return True
    if bias == "bearish" and score <= 35 and urgency >= 45:
        return True
    return False


def run_expiry_pipeline(rows: List[Dict[str, Any]], settings: Dict[str, Any]) -> None:
    """Path B decision path: options + urgency without StockTwits/news gate."""
    agent_cfg = settings.get("agent", {})
    options_cfg = settings.get("options_confirmation", {})
    unified_cfg = settings.get("unified_decision", {})
    paper_trading_enabled = bool(agent_cfg.get("paper_trading", True))
    options_enabled = bool(options_cfg.get("enabled", False))
    alerted = 0

    for row in rows:
        ticker = str(row.get("ticker", "")).upper()
        options_result = row.get("_options_result")
        if options_result is None and options_enabled:
            options_result = options_client.score_ticker(ticker, settings)
            row = enrich_expiry_row_with_options(row, options_result)
        if not options_result:
            continue

        features = options_result.get("features") or options_result.get("feature_values") or {}
        if not isinstance(features, dict):
            features = {}
        dte_val = row.get("nearest_dte", features.get("nearest_dte"))
        dte = int(dte_val) if dte_val is not None and float(dte_val) >= 0 else None
        volume_oi_spike = row.get("volume_oi_spike", features.get("volume_oi_spike"))
        rel_vol = row.get("relative_volume")
        data_quality = options_result.get("data_quality", {})
        options_data_quality = float(data_quality.get("quality_score", 0.0)) if isinstance(data_quality, dict) else 0.0
        options_data_flags = list(data_quality.get("flags", [])) if isinstance(data_quality, dict) else []

        setup_q = None
        try:
            from screener.odte_screener import setup_quality_for_ticker

            setup_q = setup_quality_for_ticker(ticker)
            odte_cfg = settings.get("odte_screener") or {}
            if bool(odte_cfg.get("require_watchlist_for_path_b", True)) and setup_q is None:
                # Soft skip when watchlist empty (first boot); hard skip once populated.
                from screener.odte_screener import load_odte_watchlist

                wl = load_odte_watchlist()
                if wl.get("ranked"):
                    continue
        except Exception:
            setup_q = None

        decision, reason, decision_meta = decide_trade_action(
            ticker=ticker,
            social_signal_level="IGNORE",
            claude_response={"score": 0.0, "confidence": "low", "reasoning": "Path B expiry scan (no news)."},
            news_headline="Path B near-expiry options scan",
            news_source="expiry_screener",
            require_social_signal=False,
            options_bias=options_result.get("options_bias"),
            options_score=options_result.get("options_score"),
            options_data_quality=options_data_quality,
            options_data_flags=options_data_flags,
            options_enabled=True,
            min_options_score_bullish=float(options_cfg.get("min_options_score_bullish", 60)),
            max_options_score_bearish=float(options_cfg.get("max_options_score_bearish", 40)),
            require_confirmation_for_buy=bool(options_cfg.get("require_confirmation_for_buy", True)),
            require_confirmation_for_sell=bool(options_cfg.get("require_confirmation_for_sell", True)),
            no_data_policy=str(options_cfg.get("no_data_policy", "block")),
            no_data_strong_news_threshold=float(options_cfg.get("no_data_strong_news_threshold", 0.75)),
            min_options_quality_to_trust=float(options_cfg.get("min_options_quality_to_trust", 0.25)),
            signal_source="expiry",
            relative_volume=float(rel_vol) if rel_vol is not None else None,
            dte=dte,
            volume_oi_spike=float(volume_oi_spike) if volume_oi_spike is not None else None,
            expiry_override_review=bool(unified_cfg.get("expiry_override_review", True)),
            expiry_buy_min_options_score=float(unified_cfg.get("expiry_buy_min_options_score", 65)),
            expiry_buy_min_urgency=float(unified_cfg.get("expiry_buy_min_urgency", 60)),
            options_features=features,
            setup_quality_score=setup_q,
            settings=settings,
        )

        herd_stage = classify_herd_stage(
            float(rel_vol) if rel_vol is not None else None,
            0,
            row.get("percent_change"),
        )
        candidate = build_candidate(
            ticker=ticker,
            source="expiry",
            relative_volume=float(rel_vol) if rel_vol is not None else None,
            options_score=options_result.get("options_score"),
            dte=dte,
            volume_oi_spike=float(volume_oi_spike) if volume_oi_spike is not None else None,
            total_oi=row.get("total_oi"),
            decision=decision,
        )
        # Always plot on quadrant; only alert/log actionable Path B setups.
        upsert_quadrant_candidate(candidate, settings)

        if decision == "LOG":
            # Persist lightweight LOG with reason code (no Claude, no Telegram).
            if paper_trading_enabled:
                log_meta = dict(decision_meta)
                log_meta["decision_reason_code"] = (
                    decision_meta.get("review_reason_code")
                    or decision_meta.get("review_reason_code_odte")
                    or "path_b_log"
                )
                append_paper_trade_entry(
                    ticker=ticker,
                    decision="LOG",
                    claude_response={
                        "score": 0.0,
                        "label": "expiry",
                        "confidence": "low",
                        "reasoning": reason,
                    },
                    news_headline="Path B near-expiry options scan",
                    news_source="expiry_screener",
                    social_signal_level="IGNORE",
                    social_signal_posts=[],
                    options_score=options_result.get("options_score"),
                    options_bias=options_result.get("options_bias"),
                    options_reasoning=options_result.get("reasoning_summary", ""),
                    settings=settings,
                    price_hint=float(row.get("current_price") or 0) or None,
                    decision_meta=log_meta,
                    signal_source="expiry",
                    herd_stage=herd_stage,
                    quadrant=str(candidate.get("quadrant", "")),
                    relative_volume=float(rel_vol) if rel_vol is not None else None,
                    dte=dte,
                    decision_reason=reason,
                )
            continue

        if not _path_b_is_actionable(decision, decision_meta, options_result):
            continue

        advisor = advise_next_action(
            ticker=ticker,
            quadrant=str(candidate.get("quadrant", "")),
            herd_stage=herd_stage,
            action_probs=decision_meta.get("action_probs") or {},
            lean=str(decision_meta.get("lean", "WAIT")),
            instrument_hint=str(decision_meta.get("instrument_hint", "stock")),
            options_score=options_result.get("options_score"),
            options_bias=options_result.get("options_bias"),
            dte=dte,
            max_oi_strike=row.get("max_oi_strike"),
            relative_volume=float(rel_vol) if rel_vol is not None else None,
            headline="Path B near-expiry options scan",
            reason=reason,
        )
        decision_meta["instrument_hint"] = advisor.get("instrument_hint", decision_meta.get("instrument_hint"))

        print_trade_alert(
            ticker=ticker,
            decision=decision,
            score=0.0,
            label="expiry",
            confidence=str(decision_meta.get("lean_pct", 0)),
            source="expiry_screener",
            headline="Path B near-expiry options scan",
            reason=reason,
            social_signal="IGNORE",
            options_bias=options_result.get("options_bias"),
            options_score=options_result.get("options_score"),
            action_probs=decision_meta.get("action_probs"),
            lean=str(decision_meta.get("lean")),
            lean_pct=int(decision_meta.get("lean_pct", 0)),
            instrument_hint=str(decision_meta.get("instrument_hint")),
        )

        # Realistic default: Path B is research/quadrant only unless explicitly enabled.
        path_b_auto = bool((settings.get("execution") or {}).get("path_b_auto_execute", False))
        if paper_trading_enabled and path_b_auto:
            append_paper_trade_entry(
                ticker=ticker,
                decision=decision,
                claude_response={"score": 0.0, "label": "expiry", "confidence": "medium", "reasoning": reason},
                news_headline="Path B near-expiry options scan",
                news_source="expiry_screener",
                social_signal_level="IGNORE",
                social_signal_posts=[],
                options_score=options_result.get("options_score"),
                options_bias=options_result.get("options_bias"),
                options_reasoning=options_result.get("reasoning_summary", ""),
                settings=settings,
                price_hint=float(row.get("current_price") or 0) or None,
                decision_meta=decision_meta,
                next_action=str(advisor.get("next_step", "")),
                signal_source="expiry",
                herd_stage=herd_stage,
                quadrant=str(candidate.get("quadrant", "")),
                relative_volume=float(rel_vol) if rel_vol is not None else None,
                dte=dte,
                max_oi_strike=row.get("max_oi_strike"),
                advisor=advisor,
                decision_reason=reason,
            )
            alerted += 1
        elif decision in {"BUY", "SELL", "REVIEW"}:
            print(
                f"[main] Path B research-only {ticker} {decision} "
                f"(options={options_result.get('options_bias')} "
                f"{options_result.get('options_score')}) — no auto trade"
            )
            # Still log REVIEW/BUY/SELL for audit when auto is off (no execute).
            if paper_trading_enabled and decision == "REVIEW":
                rev_meta = dict(decision_meta)
                rev_meta.setdefault("decision_reason_code", "path_b_research_only")
                append_paper_trade_entry(
                    ticker=ticker,
                    decision=decision,
                    claude_response={
                        "score": 0.0,
                        "label": "expiry",
                        "confidence": "medium",
                        "reasoning": reason,
                    },
                    news_headline="Path B near-expiry options scan",
                    news_source="expiry_screener",
                    social_signal_level="IGNORE",
                    social_signal_posts=[],
                    options_score=options_result.get("options_score"),
                    options_bias=options_result.get("options_bias"),
                    options_reasoning=options_result.get("reasoning_summary", ""),
                    settings=settings,
                    price_hint=float(row.get("current_price") or 0) or None,
                    decision_meta=rev_meta,
                    next_action=str(advisor.get("next_step", "")),
                    signal_source="expiry",
                    herd_stage=herd_stage,
                    quadrant=str(candidate.get("quadrant", "")),
                    relative_volume=float(rel_vol) if rel_vol is not None else None,
                    dte=dte,
                    max_oi_strike=row.get("max_oi_strike"),
                    advisor=advisor,
                    decision_reason=reason,
                )

    print(f"[main] Path B actionable alerts: {alerted}/{len(rows)} (auto_execute={bool((settings.get('execution') or {}).get('path_b_auto_execute', False))})")


# ---------------------------------------------------------------------------
# Scheduled news polls (HIGH_ALERT / WATCH / Path A.2 catalyst)
# ---------------------------------------------------------------------------


def poll_notifications(settings: Dict[str, Any]) -> None:
    """Poll Telegram approvals and optional heartbeat."""
    try:
        applied = poll_telegram_updates(settings)
        if applied:
            print(f"[main] telegram approvals applied: {applied}")
        pending = [row for row in load_pending() if row.get("status") == "pending"]
        watchlist = load_json_file(WATCHLIST_PATH, {"items": []})
        items = watchlist.get("items", watchlist) if isinstance(watchlist, dict) else watchlist
        count = len(items) if isinstance(items, list) else 0
        maybe_send_heartbeat(settings, count, len(pending))
    except Exception as error:
        print(f"[main] notification poll failed: {error}")


def run_high_alert_cycle(settings: Dict[str, Any]) -> None:
    """
    Run pipeline for HIGH_ALERT tickers every short interval.

    Inputs:
    - settings: full settings dictionary.

    Output:
    - None.

    Why this exists:
    - High-alert symbols need the fastest reaction cycle.
    """
    if demo_mode_active():
        return
    if not bool((settings.get("agent") or {}).get("path_a_enabled", True)):
        return
    with STATE_SNAPSHOT_LOCK:
        high_alert_tickers = list(STATE_SNAPSHOT.get("high_alert", []))
    if not high_alert_tickers:
        print("[main] No HIGH_ALERT tickers right now.")
        return
    run_news_pipeline_for_tickers(high_alert_tickers, settings, tag="HIGH_ALERT")


def run_watch_cycle(settings: Dict[str, Any]) -> None:
    """
    Run pipeline for WATCH tickers at a slower interval.

    Inputs:
    - settings: full settings dictionary.

    Output:
    - None.

    Why this exists:
    - WATCH symbols still matter but do not require ultra-fast polling.
    """
    if demo_mode_active():
        return
    if not bool((settings.get("agent") or {}).get("path_a_enabled", True)):
        return
    with STATE_SNAPSHOT_LOCK:
        watchlist = list(STATE_SNAPSHOT.get("watchlist", []))
    watch_tickers = [item for item in watchlist if str(item.get("social_signal_level", "")).upper() == "WATCH"]
    if not watch_tickers:
        print("[main] No WATCH tickers right now.")
        return
    run_news_pipeline_for_tickers(watch_tickers, settings, tag="WATCH")


def run_news_catalyst_cycle(settings: Dict[str, Any]) -> None:
    """
    Path A.2 — scan wire headlines + optional Finviz movers; score news without herd requirement.
    """
    catalyst_cfg = settings.get("news_catalyst") or {}
    if not bool(catalyst_cfg.get("enabled", True)):
        return
    if not bool((settings.get("agent") or {}).get("path_a_enabled", True)):
        return
    if demo_mode_active():
        return

    try:
        from news.catalyst_scanner import refresh_catalyst_watchlist

        payload = refresh_catalyst_watchlist(settings)
        items = payload.get("items") or []
    except Exception as error:
        print(f"[main] Path A.2 catalyst scan failed: {error}")
        return

    if not items:
        print("[main] Path A.2: no catalyst candidates this cycle.")
        return

    with STATE_SNAPSHOT_LOCK:
        watch_by_ticker = {
            str(row.get("ticker", "")).upper(): row for row in STATE_SNAPSHOT.get("watchlist", [])
        }

    enriched: List[Dict[str, Any]] = []
    for item in items:
        row = dict(item)
        ticker = str(row.get("ticker", "")).upper()
        if ticker in watch_by_ticker:
            watch_row = watch_by_ticker[ticker]
            row["social_signal_level"] = watch_row.get(
                "social_signal_level", row.get("social_signal_level", "IGNORE")
            )
            row["social_triggered_posts"] = watch_row.get(
                "social_triggered_posts", row.get("social_triggered_posts", [])
            )
            row.setdefault("current_price", watch_row.get("current_price"))
            row.setdefault("percent_change", watch_row.get("percent_change"))
            row.setdefault("relative_volume", watch_row.get("relative_volume"))
            row.setdefault("company_name", watch_row.get("company_name", ticker))
        row["source"] = "news_catalyst"
        enriched.append(row)

    path_a2_auto = bool((settings.get("execution") or {}).get("path_a2_auto_execute", False))
    print(
        f"[main] Path A.2 processing {len(enriched)} candidate(s) "
        f"(auto_execute={path_a2_auto})"
    )
    run_news_pipeline_for_tickers(enriched, settings, tag="NEWS_CATALYST")


# ---------------------------------------------------------------------------
# Background scheduler thread
# ---------------------------------------------------------------------------


def scheduler_loop() -> None:
    """
    Execute pending scheduled jobs in a continuous loop.

    Inputs:
    - None.

    Output:
    - None. Runs indefinitely until interrupted.

    Why this exists:
    - Keeping scheduling in one loop provides predictable timing and
      simplifies startup/shutdown behavior.
    """
    while True:
        schedule.run_pending()
        time.sleep(1)


def start_scheduler_thread() -> threading.Thread:
    """
    Start the scheduler loop in a daemon thread.

    Inputs:
    - None.

    Output:
    - The started Thread object.

    Why this exists:
    - A daemon thread automatically exits when the main process exits,
      which keeps shutdown behavior simple for this agent script.
    """
    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()
    return thread


def hydrate_high_alert_registry(settings: Dict[str, Any]) -> None:
    """
    Seed in-memory HIGH_ALERT registry from persisted state on startup.

    Inputs:
    - settings: full settings dictionary.

    Output:
    - None.

    Why this exists:
    - Restarting the process should not immediately discard recently
      detected high-alert symbols.
    """
    high_alert_items, high_alert_meta = load_state_list(HIGH_ALERT_PATH)
    if not high_alert_items:
        return
    ttl_seconds = max(60, int(settings.get("agent", {}).get("high_alert_ttl_seconds", 600)))
    meta_updated_at = parse_iso_datetime(str(high_alert_meta.get("updated_at", "")))
    now_utc = datetime.now(timezone.utc)
    elapsed_seconds = (now_utc - meta_updated_at).total_seconds() if meta_updated_at else 0.0
    remaining_seconds = max(0, ttl_seconds - int(elapsed_seconds))
    if remaining_seconds <= 0:
        return
    expires_at = now_utc + timedelta(seconds=remaining_seconds)
    with HIGH_ALERT_REGISTRY_LOCK:
        for stock in high_alert_items:
            ticker = str(stock.get("ticker", "")).upper()
            if not ticker:
                continue
            first_alert_at = str(stock.get("first_alert_at", stock.get("added_at", now_utc.isoformat())))
            HIGH_ALERT_REGISTRY[ticker] = {
                "stock": dict(stock),
                "expires_at": expires_at,
                "first_alert_at": first_alert_at,
                "last_seen_at": now_utc.isoformat(),
            }
    with STATE_SNAPSHOT_LOCK:
        STATE_SNAPSHOT["high_alert"] = sorted(high_alert_items, key=lambda item: str(item.get("ticker", "")))


# ---------------------------------------------------------------------------
# Market session helpers (RTH / options entry window)
# ---------------------------------------------------------------------------


def parse_iso_datetime(value: str) -> Optional[datetime]:
    """
    Parse an ISO datetime string into UTC.

    Inputs:
    - value: ISO datetime text.

    Output:
    - UTC datetime object or None on parse failure.

    Why this exists:
    - Startup hydration needs safe timestamp parsing from state metadata.
    """
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _wait_for_market_open(settings: Dict[str, Any]) -> None:
    """Block until equity RTH when execution.market_hours_only is enabled."""
    try:
        from agent.market_session import is_equity_rth, market_hours_only_enabled, now_et
    except Exception:
        return
    if not market_hours_only_enabled(settings):
        return
    while not is_equity_rth():
        now = now_et()
        if now.weekday() >= 5:
            detail = f"weekend ({now.strftime('%A')})"
        elif (now.hour, now.minute) < (9, 30):
            detail = f"pre-market ({now.strftime('%H:%M')} ET, opens 09:30)"
        else:
            detail = f"after-hours ({now.strftime('%H:%M')} ET)"
        print(f"[main] Waiting for market open — {detail}")
        time.sleep(60)
    now = now_et()
    print(f"[main] Market open ({now.strftime('%Y-%m-%d %H:%M')} ET) — trading window active")


def _is_premarket_or_closed(settings: Dict[str, Any]) -> bool:
    """True when listed options are not in RTH (news can still run)."""
    try:
        from agent.market_session import is_options_session_open, market_hours_only_enabled

        if not market_hours_only_enabled(settings):
            return False
        return not is_options_session_open(settings)
    except Exception:
        return False


def _log_session_mode(settings: Dict[str, Any]) -> None:
    """Print whether we are in overnight scan vs live trading mode."""
    try:
        from agent.market_session import is_equity_rth, now_et
    except Exception:
        return
    now = now_et()
    if is_equity_rth():
        print(f"[main] Session mode: RTH — news + trading active ({now.strftime('%H:%M')} ET)")
    elif _is_premarket_or_closed(settings):
        print(
            f"[main] Session mode: overnight/pre-market — news + screener active, "
            f"trades blocked until 09:30 ET ({now.strftime('%A %H:%M')} ET now)"
        )
    else:
        print("[main] Session mode: after-hours — news scanning continues, trades blocked")


# ---------------------------------------------------------------------------
# Entry point — startup reconcile, schedule registration, main thread wait
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Initialize settings, run startup scan, and launch recurring jobs.

    Inputs:
    - None.

    Output:
    - None. Runs until interrupted.

    Why this exists:
    - This is the orchestration entry point that wires all modules into
      the full end-to-end trading-research workflow.
    """
    load_dotenv(PROJECT_ROOT / ".env", override=True)
    settings = load_settings()
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not acquire_runtime_lockfile(bool(settings.get("runtime", {}).get("single_instance_required", True))):
        return

    runtime_cfg = settings.get("runtime") or {}
    # Safety net: libraries that omit per-request timeouts (some yfinance paths)
    # can hang forever in SSL_read and freeze the schedule thread.
    install_socket_default_timeout(
        float(runtime_cfg.get("socket_default_timeout_seconds", 30))
    )

    job_timeouts = {
        "odte": float(runtime_cfg.get("job_timeout_odte_seconds", 180)),
        "watchlist": float(runtime_cfg.get("job_timeout_watchlist_seconds", 180)),
        "high_alert": float(runtime_cfg.get("job_timeout_high_alert_seconds", 120)),
        "watch": float(runtime_cfg.get("job_timeout_watch_seconds", 180)),
        "catalyst": float(runtime_cfg.get("job_timeout_catalyst_seconds", 240)),
        "expiry": float(runtime_cfg.get("job_timeout_expiry_seconds", 180)),
        "notifications": float(runtime_cfg.get("job_timeout_notifications_seconds", 45)),
        "eod": float(runtime_cfg.get("job_timeout_eod_seconds", 120)),
        "announce": 15.0,
    }

    print("=" * 80)
    print("News Momentum Agent starting up")
    print(f"UTC startup time: {datetime.now(timezone.utc).isoformat()}")
    print(f"Project root: {PROJECT_ROOT}")
    print("=" * 80)
    # Fresh stamp so the health watchdog has a baseline before long startup scans.
    try:
        save_json_payload(
            HEALTH_PATH,
            {
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "cycle_id": 0,
                "pid": os.getpid(),
                "phase": "startup",
                "state_write_status": "ok",
                "reason": "startup_heartbeat",
            },
            state_write_atomic=True,
        )
    except Exception as error:
        print(f"[main] startup health heartbeat failed: {error}")
    provider = str(settings.get("screener", {}).get("provider", "scraper"))
    options_provider = str(
        settings.get("options_confirmation", {}).get("chain_provider", "auto")
    )
    print(f"[main] Finviz screener: {provider} (HTML scrape — no Elite token)")
    print(
        f"[main] Options chain provider: {options_provider} "
        "(Unusual Whales if token set, else yfinance — Finviz Elite disabled)"
    )
    print("=" * 80)
    try:
        from agent.alpaca_broker import status_line

        print(f"[main] {status_line(settings)}")
        print(
            "[main] Alpaca paper UI: https://app.alpaca.markets/paper/dashboard/overview "
            "(set ALPACA_API_KEY + ALPACA_SECRET_KEY in .env)"
        )
    except Exception as error:
        print(f"[main] Alpaca status unavailable: {error}")
    print("=" * 80)
    hydrate_high_alert_registry(settings)
    _log_session_mode(settings)

    # Paper reconcile before any opens (portfolio file is source of truth).
    # Safe to run pre-market — actual opens are gated by market_hours_only in portfolio.
    settings.setdefault("_runtime", {})["portfolio_reconciled"] = False
    try:
        from agent.portfolio import reconcile_portfolio_on_startup

        reconcile_portfolio_on_startup(settings)
    except Exception as error:
        print(f"[main] Portfolio reconcile failed (allowing cautiously): {error}")
        settings.setdefault("_runtime", {})["portfolio_reconciled"] = True

    # Only seed the watchlist on startup. ODTE/expiry Path B scans are heavy
    # (many serial Unusual Whales calls) and used to block the scheduler for
    # minutes — or forever if one HTTPS call hung. Let the schedule thread own them.
    run_with_timeout(
        refresh_watchlist_and_social,
        settings,
        name="startup_watchlist",
        timeout_sec=job_timeouts["watchlist"],
    )
    print("[main] Skipping blocking startup ODTE/expiry scans — schedule will run them with timeouts")

    # Schedule recurring jobs according to required frequencies.
    # Floor 15s: faster than Finviz's ~1m data resolution, but we still catch
    # new names / social / news as soon as they appear on the board.
    scan_interval_seconds = max(15, int(settings.get("screener", {}).get("scan_interval_seconds", 15)))
    high_alert_poll_seconds = max(10, int(settings.get("news", {}).get("high_alert_poll_seconds", 15)))
    watch_poll_seconds = max(30, int(settings.get("news", {}).get("watch_poll_seconds", 120)))
    expiry_interval = max(60, int(settings.get("expiry_screener", {}).get("scan_interval_seconds", 120)))
    odte_interval = max(60, int(settings.get("odte_screener", {}).get("scan_interval_seconds", 120)))

    catalyst_poll_seconds = max(
        60, int(settings.get("news_catalyst", {}).get("poll_seconds", 90))
    )

    # 0DTE screener runs upstream of Path A/B (scheduled more frequently than expiry).
    schedule.every(odte_interval).seconds.do(
        wrap_scheduled_job(refresh_odte_screener, name="odte", timeout_sec=job_timeouts["odte"]),
        settings=settings,
    )
    schedule.every(scan_interval_seconds).seconds.do(
        wrap_scheduled_job(
            refresh_watchlist_and_social, name="watchlist", timeout_sec=job_timeouts["watchlist"]
        ),
        settings=settings,
    )
    schedule.every(high_alert_poll_seconds).seconds.do(
        wrap_scheduled_job(
            run_high_alert_cycle, name="high_alert", timeout_sec=job_timeouts["high_alert"]
        ),
        settings=settings,
    )
    schedule.every(watch_poll_seconds).seconds.do(
        wrap_scheduled_job(run_watch_cycle, name="watch", timeout_sec=job_timeouts["watch"]),
        settings=settings,
    )
    schedule.every(catalyst_poll_seconds).seconds.do(
        wrap_scheduled_job(
            run_news_catalyst_cycle, name="catalyst", timeout_sec=job_timeouts["catalyst"]
        ),
        settings=settings,
    )
    schedule.every(expiry_interval).seconds.do(
        wrap_scheduled_job(
            refresh_expiry_watchlist, name="expiry", timeout_sec=job_timeouts["expiry"]
        ),
        settings=settings,
    )
    schedule.every(15).seconds.do(
        wrap_scheduled_job(
            poll_notifications, name="notifications", timeout_sec=job_timeouts["notifications"]
        ),
        settings=settings,
    )

    def _eod_summary_job() -> None:
        try:
            from agent.eod_summary import maybe_run_eod_summary

            maybe_run_eod_summary(settings)
        except Exception as error:
            print(f"[main] EOD summary job failed: {error}")

    schedule.every(60).seconds.do(
        wrap_scheduled_job(_eod_summary_job, name="eod", timeout_sec=job_timeouts["eod"])
    )

    _trading_window_announced = {"done": False}

    def _market_open_announcement() -> None:
        if _trading_window_announced["done"]:
            return
        try:
            from agent.market_session import is_equity_rth, market_hours_only_enabled, now_et
        except Exception:
            return
        if not market_hours_only_enabled(settings):
            return
        if not is_equity_rth():
            return
        _trading_window_announced["done"] = True
        now = now_et()
        print(
            f"[main] Market open ({now.strftime('%Y-%m-%d %H:%M')} ET) — "
            "trading window active (news scanning already running)"
        )

    schedule.every(30).seconds.do(
        wrap_scheduled_job(
            _market_open_announcement, name="announce", timeout_sec=job_timeouts["announce"]
        )
    )

    start_scheduler_thread()
    print(
        f"[main] Scheduler started (scan={scan_interval_seconds}s, odte={odte_interval}s, "
        f"expiry={expiry_interval}s, job_timeouts=on). Press Ctrl+C to stop."
    )
    print(
        f"[main] Safety gates: market_hours_only={bool((settings.get('execution') or {}).get('market_hours_only', True))} "
        f"no_post_1545_opens={bool((settings.get('execution') or {}).get('no_post_1545_opens', True))} "
        f"path_b_auto_execute={bool((settings.get('execution') or {}).get('path_b_auto_execute', False))} "
        f"path_a2_auto_execute={bool((settings.get('execution') or {}).get('path_a2_auto_execute', False))} "
        f"exit_on_signal_flip={bool((settings.get('execution') or {}).get('exit_on_signal_flip', False))}"
    )
    path_a_on = bool((settings.get("agent") or {}).get("path_a_enabled", True))
    llm_cfg = settings.get("llm") or {}
    llm_provider = str(llm_cfg.get("provider") or "openai")
    llm_on = bool(llm_cfg.get("enabled", True))
    claude_on = bool((settings.get("claude") or {}).get("enabled", True))
    print(
        f"[main] LLM: provider={llm_provider} enabled={llm_on} "
        f"(legacy claude.enabled={claude_on}, path_a_enabled={path_a_on})"
    )

    # If health.json stops updating, a worker is stuck outside the schedule thread
    # (or the process is otherwise wedged). Self-restart so RTH trading recovers.
    stale_limit = float(runtime_cfg.get("health_stale_restart_seconds", 240))
    watchdog_grace = float(runtime_cfg.get("health_watchdog_grace_seconds", 90))
    started_monotonic = time.monotonic()
    last_watchdog_check = 0.0

    try:
        while True:
            time.sleep(1)
            now_m = time.monotonic()
            if now_m - last_watchdog_check < 30:
                continue
            last_watchdog_check = now_m
            if now_m - started_monotonic < watchdog_grace:
                continue
            age = health_age_seconds(HEALTH_PATH)
            if age is None:
                continue
            if age <= stale_limit:
                continue
            print(
                f"[main] HEALTH STALE age={age:.0f}s (limit={stale_limit:.0f}s) — "
                "self-restarting to clear hung network workers"
            )
            release_runtime_lockfile()
            os.execv(sys.executable, [sys.executable, *sys.argv])
    except KeyboardInterrupt:
        print("\n[main] Agent stopped by user.")
    finally:
        release_runtime_lockfile()


if __name__ == "__main__":
    main()

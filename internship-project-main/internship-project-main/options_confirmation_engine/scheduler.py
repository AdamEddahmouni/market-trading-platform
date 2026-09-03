"""Continuous polling runner for near-real-time options confirmation.

Re-runs the batch on a fixed interval (default 5 minutes), pulling the ticker
universe from a Finviz screener each cycle and writing fresh state that the
dashboard reads. Holds the single-instance PID lock for the whole session so it
won't collide with itself or an ad-hoc CLI run.

Run with the Finviz token in the environment::

    export FINVIZ_AUTH_TOKEN="$(cat .finviz_token)"
    python scheduler.py            # respects market hours from settings
    python scheduler.py --once     # run a single cycle and exit
    python scheduler.py --interval 60 --ignore-market-hours

Offline demo (no token/network)::

    python scheduler.py --once --offline
    python scheduler.py --offline

Stop with Ctrl+C; the PID lock is released on exit.
"""

from __future__ import annotations

import argparse
import copy
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from options_engine.finviz_screener import resolve_universe
from options_engine.paper_trader import portfolio_summary, update as update_portfolio
from options_engine.runner import run_batch
from options_engine.utils import acquire_pid_lock, load_settings, release_pid_lock

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9
    ZoneInfo = None  # type: ignore[assignment]


def apply_offline_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Force replay provider and snapshot universe for offline demos."""
    cfg = copy.deepcopy(settings)
    cfg.setdefault("chain", {})["provider"] = "replay"
    cfg.setdefault("universe", {})["source"] = "snapshots"
    cfg.setdefault("logging", {})["save_raw_snapshot"] = False
    return cfg


def is_market_open(settings: Dict[str, Any], now_utc: datetime | None = None) -> bool:
    """Return True during US regular trading hours (Mon-Fri, 9:30-16:00 ET).

    Closed on weekends and on any date listed in ``scheduler.market_holidays``
    (US market holidays, e.g. Juneteenth). Early-close days are treated as full
    sessions, which is conservative for a polling loop.
    """
    sched_cfg = settings.get("scheduler", {})
    tz_name = str(sched_cfg.get("timezone", "America/New_York"))
    holidays = set(sched_cfg.get("market_holidays", []))
    now_utc = now_utc or datetime.now(timezone.utc)
    if ZoneInfo is None:
        return True
    local = now_utc.astimezone(ZoneInfo(tz_name))
    if local.weekday() >= 5:
        return False
    if local.date().isoformat() in holidays:
        return False
    minutes = local.hour * 60 + local.minute
    return (9 * 60 + 30) <= minutes <= (16 * 60)


def run_cycle(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the universe and run one scoring batch (+ optional paper trades)."""
    tickers: List[str] = resolve_universe(settings)
    request_id = datetime.now(timezone.utc).isoformat()
    if not tickers:
        print(f"[{request_id}] no tickers resolved; skipping cycle", flush=True)
        return {"items": []}
    result = run_batch(tickers=tickers, settings=settings, request_id=request_id)
    items = result.get("items", [])

    auth_failures = sum(
        1 for item in items if "invalid_auth_token" in item.get("data_quality", {}).get("flags", [])
    )
    if items and auth_failures == len(items):
        print(
            f"[{request_id}] ERROR: Finviz rejected the token (Invalid export API token) for all tickers. "
            "Refresh FINVIZ_AUTH_TOKEN (finviz.com -> Settings -> API).",
            flush=True,
        )
        return result

    biases: Dict[str, int] = {}
    for item in items:
        b = str(item.get("options_bias", "unknown"))
        biases[b] = biases.get(b, 0) + 1
    top = sorted(items, key=lambda r: float(r.get("options_score", 0)), reverse=True)[:3]
    top_text = ", ".join(f"{r['ticker']}:{float(r.get('options_score',0)):.0f}/{r.get('options_bias')}" for r in top)
    print(f"[{request_id}] scored {len(items)} tickers {biases} | top: {top_text}", flush=True)

    if bool(settings.get("trading", {}).get("enabled", True)) and items:
        trade_result = update_portfolio(items, settings, request_id=request_id)
        prices = {str(i["ticker"]): float(i.get("spot_price", 0)) for i in items if i.get("spot_price")}
        summary = portfolio_summary(trade_result["portfolio"], prices)
        fills_n = len(trade_result.get("fills", []))
        print(
            f"[{request_id}] portfolio equity=${summary['equity']:,.0f} "
            f"return={summary['return_pct']:+.2f}% positions={summary['open_positions']} "
            f"fills={fills_n} cycle_pnl={trade_result.get('cycle_pnl', 0):+.2f}",
            flush=True,
        )
        result["portfolio"] = trade_result

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Near-real-time options confirmation scheduler")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    parser.add_argument("--offline", action="store_true", help="Replay saved snapshots (no network/token)")
    parser.add_argument("--interval", type=int, default=None, help="Override interval seconds")
    parser.add_argument("--ignore-market-hours", action="store_true", help="Run regardless of market hours")
    args = parser.parse_args()

    settings = load_settings()
    if args.offline:
        settings = apply_offline_settings(settings)

    sched_cfg = settings.get("scheduler", {})
    interval = int(args.interval if args.interval is not None else sched_cfg.get("interval_seconds", 300))
    market_hours_only = bool(sched_cfg.get("market_hours_only", True)) and not args.ignore_market_hours and not args.offline

    if args.once:
        run_cycle(settings)
        return

    if not acquire_pid_lock(bool(settings.get("runtime", {}).get("single_instance_required", True))):
        return

    mode = "offline/replay" if args.offline else "live"
    print(
        f"[scheduler] started ({mode}): interval={interval}s market_hours_only={market_hours_only}. Ctrl+C to stop.",
        flush=True,
    )
    try:
        while True:
            cycle_start = time.time()
            if market_hours_only and not is_market_open(settings):
                print(f"[{datetime.now(timezone.utc).isoformat()}] market closed; sleeping", flush=True)
            else:
                try:
                    run_cycle(settings)
                except Exception as exc:  # keep the loop alive on transient errors
                    print(f"[scheduler] cycle error: {exc!r}", flush=True)
            elapsed = time.time() - cycle_start
            time.sleep(max(1.0, interval - elapsed))
    except KeyboardInterrupt:
        print("\n[scheduler] stopping", flush=True)
    finally:
        release_pid_lock()


if __name__ == "__main__":
    main()

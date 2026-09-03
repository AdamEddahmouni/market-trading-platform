"""Read-only live observational smoke. Never opens a trade context."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools" / "moomoo"))

from check_live_environment import run_check
from market_platform_foundation.market_data.live_runtime import LiveObservationalRuntime, reset_live_runtime
from market_platform_foundation.market_data.subscription_manager import SubscriptionPriority


def main() -> int:
    os.environ.setdefault("IMP_LIVE_OBSERVATIONAL", "1")
    os.environ.setdefault("IMP_MOOMOO_LIVE", "1")
    env = run_check()
    if not env.get("ready_for_live_observational"):
        print(env.get("operator_message"))
        return 1
    reset_live_runtime()
    runtime = LiveObservationalRuntime()
    runtime.configure()
    symbols = ["AAPL", "NVDA"]
    for symbol in symbols:
        runtime.subscribe(
            instrument_id=symbol,
            capabilities=["BASIC_QUOTE", "TRADES", "ORDER_BOOK"],
            consumer_id="smoke",
            priority=SubscriptionPriority.ACTIVE_WORKSPACE,
        )
    deadline = time.time() + 12
    while time.time() < deadline:
        quotes_ready = all(runtime.state.quote_for(symbol) is not None for symbol in symbols)
        bid_ready = all(
            (runtime.state.quote_for(symbol) is not None and runtime.state.quote_for(symbol).bid_price is not None)
            for symbol in symbols
        )
        if quotes_ready and runtime._fresh_event_count > 0 and bid_ready:
            break
        time.sleep(0.25)
    quotes = {symbol: runtime.state.quote_for(symbol) for symbol in symbols}
    trades = {symbol: runtime.state.trades_for(symbol) for symbol in symbols}
    books = {symbol: runtime.state.book_for(symbol) for symbol in symbols}
    for symbol in symbols:
        runtime.unsubscribe(
            instrument_id=symbol,
            capabilities=["BASIC_QUOTE", "TRADES", "ORDER_BOOK"],
            consumer_id="smoke",
        )
    runtime.stop()
    counters = (runtime.feed_metrics or {}).get("trade_api_counters") or {}
    report = {
        "connection": runtime.lifecycle.connection_state.value,
        "fresh_events": runtime._fresh_event_count,
        "quotes": {key: None if value is None else value.to_dict() for key, value in quotes.items()},
        "trade_counts": {key: len(value) for key, value in trades.items()},
        "book_depths": {key: None if value is None else value.get("returned_depth") for key, value in books.items()},
        "metrics": runtime.state.metrics_report(),
        "feed_metrics": runtime.feed_metrics,
        "trade_api_counters": counters,
        "environment": env.get("status"),
    }
    print(report)
    if any(quotes[symbol] is None for symbol in symbols):
        return 1
    if any(int(counters.get(key) or 0) for key in counters):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

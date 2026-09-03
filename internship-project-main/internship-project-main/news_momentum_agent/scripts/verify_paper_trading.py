#!/usr/bin/env python3
"""Quick check that paper trading settings and execution path are wired correctly.

CLI
---
``python scripts/verify_paper_trading.py`` — prints trading flags, runs one
synthetic BUY through ``execute_decision``, restores portfolio files.

When to run
-----------
After changing ``settings.json`` trading/alpaca blocks or ``agent/portfolio.py``.
Once per environment setup.

Safe vs live agent
------------------
**Mostly safe:** Temporarily overwrites ``state/portfolio.json`` and
``state/executions.json`` with test data, then restores backups. Does not
require live ``main.py``; uses local sim only (no Alpaca unless configured).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent.portfolio import default_portfolio, execute_decision, load_portfolio, PORTFOLIO_PATH, EXECUTIONS_PATH


def main() -> None:
    """Print paper-trading config and optionally smoke-test a local stock fill."""
    settings = json.loads((PROJECT_ROOT / "settings.json").read_text(encoding="utf-8"))
    trading = settings.get("trading", {})
    agent = settings.get("agent", {})
    options = settings.get("options_confirmation", {})

    print("Paper trading configuration")
    print(f"  agent.paper_trading:     {agent.get('paper_trading', False)}")
    print(f"  trading.auto_execute:    {trading.get('auto_execute', False)}")
    print(f"  trading.instrument:      {trading.get('instrument', 'stock')}  (stock | options)")
    print(f"  options_confirmation:    {options.get('enabled', False)}")
    print("")

    backup_portfolio = PORTFOLIO_PATH.read_text(encoding="utf-8") if PORTFOLIO_PATH.exists() else None
    backup_executions = EXECUTIONS_PATH.read_text(encoding="utf-8") if EXECUTIONS_PATH.exists() else None
    PORTFOLIO_PATH.parent.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_PATH.write_text(json.dumps(default_portfolio(100000)), encoding="utf-8")
    EXECUTIONS_PATH.write_text("[]", encoding="utf-8")

    try:
        result = execute_decision("TEST", "BUY", 25.0, "verify script", settings)
        portfolio = load_portfolio(settings)
        instrument = trading.get("instrument", "stock")
        if instrument == "options":
            ok = result is not None and any(
                str(p.get("instrument_type")) == "option" for p in portfolio.get("positions", {}).values()
            )
            detail = "option contract opened (or chain unavailable for TEST — try a liquid ticker)"
        else:
            ok = "TEST" in portfolio.get("positions", {})
            detail = "stock long opened"
        print(f"Dry-run BUY TEST @ $25: {'OK' if ok else 'FAILED'} — {detail}")
        if result:
            print(f"  fills: {len(result.get('fills', []))}")
    finally:
        if backup_portfolio is None:
            PORTFOLIO_PATH.unlink(missing_ok=True)
        else:
            PORTFOLIO_PATH.write_text(backup_portfolio, encoding="utf-8")
        if backup_executions is None:
            EXECUTIONS_PATH.unlink(missing_ok=True)
        else:
            EXECUTIONS_PATH.write_text(backup_executions, encoding="utf-8")

    print("")
    print("For real trades overnight you need:")
    print("  1. ./scripts/exit_demo.sh  (no demo.lock)")
    print("  2. main.py running")
    print("  3. HIGH_ALERT ticker + fresh news + Claude score > 0.5")
    print("  4. Options bullish (for BUY) or bearish (for SELL)")
    print("")
    print("To paper-trade OPTIONS contracts instead of stock, set in settings.json:")
    print('  "trading": { "instrument": "options", ... }')


if __name__ == "__main__":
    main()

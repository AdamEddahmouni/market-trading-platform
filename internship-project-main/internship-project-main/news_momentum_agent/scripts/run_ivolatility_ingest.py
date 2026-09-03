#!/usr/bin/env python3
"""IVolatility ingest: tiny SPY test pull, then gated full SPY+QQQ pull.

CLI
---
``python scripts/run_ivolatility_ingest.py --tiny-spy [--tiny-days N]``
``python scripts/run_ivolatility_ingest.py --full --from DATE --to DATE --confirm-full-pull``

Pulls historical option chains to ``evaluation/`` cache for replay/research.

When to run
-----------
One-time or periodic data refresh before ``run_spy_qqq_replay`` / research pipeline.
Review cost estimate before ``--full``.

Safe vs live agent
------------------
**Safe / offline:** External API ingest only; no interaction with ``main.py`` or
paper portfolio. Requires IVolatility credentials in ``.env``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.historical_chain_adapter import schema_mapping_report  # noqa: E402
from evaluation.ivolatility_client import (  # noqa: E402
    IVolatilityAuthError,
    estimate_pull_cost_usd,
    parse_iso_date,
    pull_full_spy_qqq,
    pull_tiny_spy_test,
    read_csv,
    _daterange_trading_approx,
)


def main() -> int:
    """CLI entry: tiny SPY test pull or gated full SPY+QQQ historical ingest."""
    parser = argparse.ArgumentParser(description="IVolatility SPY/QQQ historical ingest")
    parser.add_argument("--tiny-spy", action="store_true", help="Pull ~10 SPY days and validate schema")
    parser.add_argument("--tiny-days", type=int, default=10)
    parser.add_argument("--full", action="store_true", help="Prepare/run full SPY+QQQ pull")
    parser.add_argument("--from", dest="from_date", default="")
    parser.add_argument("--to", dest="to_date", default="")
    parser.add_argument(
        "--confirm-full-pull",
        action="store_true",
        help="Required to execute the full pull after reviewing cost estimate",
    )
    parser.add_argument("--options-path", default="/equities/eod/stock-opts-by-param")
    parser.add_argument("--stock-path", default="/equities/eod/stock-prices")
    args = parser.parse_args()

    if not args.tiny_spy and not args.full:
        parser.print_help()
        print("\nStart with: --tiny-spy  (requires IVOLATILITY_API_KEY in .env)")
        return 2

    try:
        if args.tiny_spy:
            print("[ivol] tiny SPY test pull…")
            meta = pull_tiny_spy_test(
                trading_days=max(2, int(args.tiny_days)),
                options_path=args.options_path,
                stock_path=args.stock_path,
            )
            print(json.dumps({k: meta[k] for k in meta if k != "days"}, indent=2, default=str))
            out_dir = Path(meta["out_dir"])
            sample = read_csv(out_dir / "SPY_options_all.csv")[:50]
            report = schema_mapping_report(sample)
            print("[ivol] schema mapping:", json.dumps(report, indent=2, default=str)[:2000])
            if not report.get("ok"):
                print("[ivol] SCHEMA MAPPING FAILED — do not run --full until this passes.")
                return 1
            print("[ivol] tiny pull + schema OK. Review cost_estimate before --full --confirm-full-pull.")
            return 0

        to_d = parse_iso_date(args.to_date) if args.to_date else date.today()
        from_d = parse_iso_date(args.from_date) if args.from_date else (to_d - timedelta(days=190))
        days = _daterange_trading_approx(from_d, to_d)
        cost = estimate_pull_cost_usd(
            tickers=["SPY", "QQQ"],
            trading_days=len(days),
            datasets=["stock_prices", "options_eod"],
        )
        print("[ivol] FULL pull cost estimate:", json.dumps(cost, indent=2))
        result = pull_full_spy_qqq(
            from_date=from_d,
            to_date=to_d,
            confirm=bool(args.confirm_full_pull),
            options_path=args.options_path,
            stock_path=args.stock_path,
        )
        print(json.dumps(result, indent=2, default=str)[:4000])
        if result.get("status") == "blocked":
            return 3
        return 0 if not result.get("errors") else 1
    except IVolatilityAuthError as error:
        print(f"[ivol] AUTH: {error}")
        return 4
    except Exception as error:
        print(f"[ivol] ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

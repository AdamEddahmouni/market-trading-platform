"""Bounded live probe of official CFTC COT Public Reporting API."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cftc.transport import CotTransport  # noqa: E402
from market_platform_foundation.cftc.datasets import CotDataset, CotPositionScope  # noqa: E402


def main() -> int:
    transport = CotTransport()
    results: dict[str, object] = {"reachable": False}
    try:
        tff = transport.query_dataset(
            CotDataset.TFF_FUTURES_ONLY,
            where="market_and_exchange_names like '%E-MINI S&P 500%'",
            limit=2,
            order="report_date_as_yyyy_mm_dd DESC",
        )
        results["reachable"] = True
        results["tff_futures_only_sample_count"] = len(tff)
        if tff:
            results["tff_futures_only_fields"] = sorted(tff[0].keys())
            results["tff_futures_only_latest"] = {
                k: tff[0].get(k)
                for k in (
                    "market_and_exchange_names",
                    "report_date_as_yyyy_mm_dd",
                    "cftc_contract_market_code",
                    "open_interest_all",
                    "lev_money_positions_long",
                    "lev_money_positions_short",
                )
            }
        disagg = transport.query_dataset(
            CotDataset.DISAGGREGATED_FUTURES_ONLY,
            where="market_and_exchange_names like '%CRUDE OIL%'",
            limit=1,
            order="report_date_as_yyyy_mm_dd DESC",
        )
        results["disaggregated_futures_only_sample_count"] = len(disagg)
        hierarchy = transport.query_product_hierarchy(limit=3)
        results["product_hierarchy_sample_count"] = len(hierarchy)
        if hierarchy:
            results["product_hierarchy_fields"] = sorted(hierarchy[0].keys())
        print(json.dumps(results, indent=2))
        return 0
    except Exception as exc:  # pragma: no cover - probe diagnostic
        results["error"] = str(exc)
        print(json.dumps(results, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

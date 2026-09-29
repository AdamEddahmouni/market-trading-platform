"""Screener S15 developer audit: does every Futures root have a CFTC coverage decision?

Reads the Futures universe through the canonical Screener query path (or a saved
root list) and classifies every root with ``cftc.root_coverage``: MAPPED,
single-stock (no COT market), no CFTC market, ambiguous, or UNCLASSIFIED. It is a
governance/testing tool, not an operator feature, and it writes nothing unless
``--save-catalog`` is given. Exit status: 0 clean, 1 an UNCLASSIFIED root or a
mapping invariant failed, 2 the catalog did not load (acceptance incomplete).

A root the provider adds later is UNCLASSIFIED until someone records a decision
for it: the audit fails rather than map it to a nearby market.

Live (needs Moomoo OpenD, like the Screener)::

    python tools/screener/cftc_coverage_audit.py --detail
    python tools/screener/cftc_coverage_audit.py --verify-cftc     # also query CFTC Public Reporting

Offline, over a saved ``[{"root", "exchange", "symbol"}]`` list::

    python tools/screener/cftc_coverage_audit.py --catalog tests/fixtures/cftc/s15_futures_roots_20260929.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.cftc.root_coverage import (  # noqa: E402
    EXCHANGE_VENUES, UNMAPPED_ROOTS, CoverageStatus, cftc_exchange, classify_root, coverage_summary,
)
from market_platform_foundation.cftc.screener_positioning import (  # noqa: E402
    DATASETS, POSITIONING_MARKETS, build_positioning, where_clause,
)

MAX_PAGES = 20


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 2)


def invariant_findings() -> list[str]:
    """Registry invariants that hold independent of any catalog."""

    findings = []
    codes = Counter(market.code for market in POSITIONING_MARKETS.values())
    findings += [f"DUPLICATE_MARKET_CODE {code}" for code, count in codes.items() if count > 1]
    findings += [f"ROOT_BOTH_MAPPED_AND_UNMAPPED {root}" for root in sorted(set(POSITIONING_MARKETS) & set(UNMAPPED_ROOTS))]
    for root, market in POSITIONING_MARKETS.items():
        if root != market.root:
            findings.append(f"REGISTRY_KEY_MISMATCH {root}")
        if cftc_exchange(market) not in EXCHANGE_VENUES:
            findings.append(f"UNKNOWN_CFTC_EXCHANGE {root} {cftc_exchange(market)}")
        if market.report not in DATASETS:
            findings.append(f"UNSUPPORTED_REPORT_FAMILY {root} {market.report.value}")
    return findings


def live_catalog() -> tuple[list[dict[str, Any]], str | None, float]:
    from market_platform_foundation.ui_api.screener_projections import read_screener
    from market_platform_foundation.ui_api.screener_query import MAX_PAGE_LIMIT

    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    offset, result_set, error = 0, None, None
    for _ in range(MAX_PAGES):
        page = read_screener(universe="FUTURES", offset=offset, limit=MAX_PAGE_LIMIT, result_set=result_set)
        error = error or page.get("source_error")
        rows.extend(page.get("rows") or [])
        result_set = page.get("result_set_id")
        if not page.get("has_more") or not result_set:
            break
        offset += len(page.get("rows") or [])
    # Only public contract identity is kept: no quote, account, or provider session data.
    roots = [{"root": str(row.get("root") or "").upper(), "exchange": row.get("exchange"), "symbol": row.get("symbol")}
             for row in rows if row.get("root")]
    return roots, (str(error) if error and not roots else None), _ms(started)


def verify_cftc(roots: set[str], now: datetime) -> dict[str, Any]:
    """Query CFTC Public Reporting for the mapped markets and report what each one's latest public report is."""

    from market_platform_foundation.cftc.live import transport_from_env

    transport = transport_from_env()
    since = now.date() - timedelta(days=35)
    out: dict[str, Any] = {}
    started = time.perf_counter()
    for family, dataset in DATASETS.items():
        markets = [market for market in POSITIONING_MARKETS.values() if market.report == family and market.root in roots]
        rows = transport.query_dataset(dataset, where=where_clause([market.code for market in markets], since),
                                       order="report_date_as_yyyy_mm_dd DESC", limit=1000)
        for market in markets:
            report = build_positioning(rows, market, now=now)
            out[market.root] = None if report is None else {
                "code": market.code, "report": report["report"], "market_name": report["market_name"],
                "report_date": report["report_date"], "publication_time": report["publication_time"],
                "publication_basis": report["publication_basis"], "quality_flags": report["quality_flags"],
                "quality_state": report["quality_state"], "categories": [item["id"] for item in report["categories"]],
            }
    return {"reports": out, "latency_ms": _ms(started)}


def audit(roots: list[dict[str, Any]]) -> dict[str, Any]:
    started = time.perf_counter()
    pairs = [(item["root"], item.get("exchange")) for item in roots]
    summary = coverage_summary(pairs)
    decisions = {item["root"]: classify_root(item["root"], exchange=item.get("exchange")) for item in roots}
    elapsed = _ms(started)
    findings = invariant_findings()
    findings += [f"UNCLASSIFIED_ROOT {root}" for root, item in sorted(decisions.items())
                 if item["status"] == CoverageStatus.UNCLASSIFIED.value]
    findings += [f"EXCHANGE_MISMATCH {root} {item['provider_exchange']}" for root, item in sorted(decisions.items())
                 if item["reason"] == "EXCHANGE_MISMATCH"]
    duplicates = [root for root, count in Counter(root for root, _ in pairs).items() if count > 1]
    findings += [f"ROOT_LISTED_TWICE {root}" for root in sorted(duplicates)]
    return {"summary": {key: value for key, value in summary.items() if key != "unmapped"}, "decisions": decisions,
            "symbols": {item["root"]: item.get("symbol") for item in roots}, "findings": findings,
            "latency_ms": {"classify_all_roots": elapsed},
            "registry_not_in_catalog": sorted((set(POSITIONING_MARKETS) | set(UNMAPPED_ROOTS)) - set(decisions))}


def main() -> int:
    parser = argparse.ArgumentParser(description="Screener S15 Futures CFTC coverage audit")
    parser.add_argument("--catalog", help="classify a saved root list instead of reading OpenD")
    parser.add_argument("--save-catalog", help="write the observed root list (root, exchange, symbol) to this path")
    parser.add_argument("--detail", action="store_true", help="print one line per root")
    parser.add_argument("--verify-cftc", action="store_true", help="query CFTC Public Reporting for every mapped root")
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    args = parser.parse_args()
    catalog_ms = None
    close = None
    if args.catalog:
        roots, error = json.loads(Path(args.catalog).read_text(encoding="utf-8")), None
    else:
        from market_platform_foundation.market_data.current_bars import current_bars_service

        close = getattr(current_bars_service().transport(), "close", None)
        try:
            roots, error, catalog_ms = live_catalog()
        except Exception as exc:  # noqa: BLE001 — any provider failure is "catalog did not load"
            roots, error = [], f"{type(exc).__name__}: {exc}"
    try:
        if error:
            print(f"Futures catalog did not load: {error}")
            return 2
        if args.save_catalog:
            Path(args.save_catalog).write_text(json.dumps(sorted(roots, key=lambda item: item["root"]), indent=1) + "\n",
                                               encoding="utf-8", newline="\n")
        now = datetime.now(UTC)
        report = audit(roots)
        report["observed_at"] = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        report["latency_ms"]["catalog"] = catalog_ms
        if args.verify_cftc:
            mapped = {root for root, item in report["decisions"].items() if item["status"] == CoverageStatus.MAPPED.value}
            report["cftc"] = verify_cftc(mapped, now)
            missing = sorted(root for root in mapped if report["cftc"]["reports"].get(root) is None)
            report["cftc"]["mapped_without_public_report"] = missing
            report["findings"] += [f"CONFLICTING_DUPLICATE_ROWS {root}" for root, item in report["cftc"]["reports"].items()
                                   if item and item["quality_state"] != "OK"]
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True, default=str))
            return 1 if report["findings"] else 0
        summary = report["summary"]
        print(f"Futures CFTC coverage · observed {report['observed_at']} · registry verified {summary['registry_verified']}")
        print(f"  roots {summary['universe_roots']}")
        for item in summary["breakdown"]:
            print(f"  {item['label']:<40} {item['count']:>4}")
        unclassified = summary["by_status"][CoverageStatus.UNCLASSIFIED.value]
        print(f"  {'Unclassified':<40} {unclassified:>4}")
        print(f"  latency: catalog {catalog_ms} ms · classify {report['latency_ms']['classify_all_roots']} ms")
        if args.detail:
            print(f"\n{'root':<7} {'contract':<10} {'venue':<9} {'status':<15} {'reason / code':<28} note")
            for root, item in sorted(report["decisions"].items()):
                market = item["market"] or {}
                code = market.get("cftc_contract_market_code") or item["reason"] or ""
                note = market.get("market_name") or item["note"] or ""
                print(f"{root:<7} {str(report['symbols'].get(root) or ''):<10} {str(item['provider_exchange'] or '-'):<9} "
                      f"{item['status']:<15} {code:<28} {note[:90]}")
        if "cftc" in report:
            reports = report["cftc"]["reports"]
            print(f"\nCFTC Public Reporting ({report['cftc']['latency_ms']} ms):")
            for root, item in sorted(reports.items()):
                if item is None:
                    print(f"  {root:<6} no public report in the last 35 days")
                    continue
                flags = "".join(f" · {flag}" for flag in item["quality_flags"])
                print(f"  {root:<6} {item['code']:<7} {item['report']:<13} as of {item['report_date']} · released "
                      f"{item['publication_time']} ({item['publication_basis']}) · {item['market_name']}{flags}")
            dates = Counter(item["report_date"] for item in reports.values() if item)
            print(f"  report dates: {dict(dates)}")
        if report["registry_not_in_catalog"]:
            print(f"\nregistry roots not in this catalog ({len(report['registry_not_in_catalog'])}): "
                  f"{', '.join(report['registry_not_in_catalog'])}")
        for finding in report["findings"]:
            print(f"  FINDING {finding}")
        return 1 if report["findings"] else 0
    finally:
        if callable(close):
            close()


if __name__ == "__main__":
    raise SystemExit(main())

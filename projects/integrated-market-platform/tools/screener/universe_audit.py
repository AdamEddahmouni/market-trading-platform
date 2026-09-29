"""Screener S13 developer audit: why is each row in its universe?

Reads all five Main Screener universes through the canonical query path and
reports, per universe, the provider raw count, accepted and rejected rows, the
rejection reasons, ambiguous rows, row-contract violations, cross-universe
duplicates, sampled per-symbol decisions, and cold/warm catalog and query
latency. It is a governance/testing tool, not an operator feature, and it
writes nothing. Exit status: 0 clean, 1 integrity finding, 2 a universe did
not load (acceptance incomplete).

Live (needs the same gates and providers as the UI API: Moomoo OpenD,
``IMP_FINVIZ_LIVE``, ``IMP_TREASURY_LIVE``, ``IMP_CRYPTO_LIVE``)::

    python tools/screener/universe_audit.py --sample EQIX,WY,AIO,SPY,AGG,GLD,TQQQ,SH,JEPI

Offline performance measurement over a synthetic catalog (no network)::

    python tools/screener/universe_audit.py --synthetic 4000
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.ui_api.screener_admission import integrity_report  # noqa: E402
from market_platform_foundation.ui_api.screener_multi import MultiUniverseScreener  # noqa: E402
from market_platform_foundation.ui_api.screener_projections import ScreenerService  # noqa: E402
from market_platform_foundation.ui_api.screener_query import MAX_PAGE_LIMIT  # noqa: E402
from market_platform_foundation.ui_api.screener_universes import UNIVERSES, US_EQUITIES, US_ETFS  # noqa: E402

MAX_PAGES = 60  # bounded: 30,000 rows per universe


def _ms(started: float) -> float:
    return round((time.perf_counter() - started) * 1000.0, 2)


def _all_rows(read: Callable[..., dict[str, Any]], universe: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    first: dict[str, Any] = {}
    offset, result_set = 0, None
    for _ in range(MAX_PAGES):
        page = read(universe=universe, offset=offset, limit=MAX_PAGE_LIMIT, result_set=result_set)
        first = first or page
        rows.extend(page.get("rows") or [])
        result_set = page.get("result_set_id")
        if not page.get("has_more") or not result_set:
            break
        offset += len(page.get("rows") or [])
    return rows, first


def audit(read: Callable[..., dict[str, Any]], *, equities: ScreenerService, multi: MultiUniverseScreener,
          sample: list[str]) -> dict[str, Any]:
    catalogs: dict[str, list[dict[str, Any]]] = {}
    universes: dict[str, Any] = {}
    for universe in UNIVERSES:
        started = time.perf_counter()
        rows, first = _all_rows(read, universe)
        cold_ms = _ms(started)
        started = time.perf_counter()
        read(universe=universe, limit=1)
        warm_ms = _ms(started)
        started = time.perf_counter()
        read(universe=universe, search="A", limit=MAX_PAGE_LIMIT)
        query_ms = _ms(started)
        catalogs[universe] = rows
        admission = (equities.admission_audit() if universe == US_EQUITIES else
                     multi.admission_audit(universe) if universe == US_ETFS else None)
        universes[universe] = {
            "accepted": len(rows), "source_error": first.get("source_error"),
            "provider_health": first.get("provider_health"),
            "admission": admission or {"note": "admission is the provider projection's explicit filter; "
                                               "see SCREENER_S13_UNIVERSE_INTEGRITY.md"},
            "latency_ms": {"cold_catalog_all_pages": cold_ms, "warm_first_page": warm_ms, "warm_search": query_ms},
        }
    where: dict[str, list[str]] = {}
    for universe, rows in catalogs.items():
        for row in rows:
            where.setdefault(str(row.get("symbol") or "").upper(), []).append(universe)
    findings: list[str] = []
    equity_admission = universes[US_EQUITIES]["admission"]
    if equity_admission.get("provider_raw_count") and not equity_admission.get("rejection_reasons"):
        # The export always holds thousands of ETFs; none classified means the reference industry
        # spelling changed: ETFs would sit in US Equities while the ETF universe fails closed.
        findings.append("REFERENCE_HAS_NO_ETF_INDUSTRY")
    samples = {symbol: {"universes": where.get(symbol.upper(), []), "etf_decision": multi.explain_etf(symbol)}
               for symbol in sample}
    return {"universes": universes, "integrity": integrity_report(catalogs), "findings": findings,
            "samples": samples}


def _synthetic(size: int) -> tuple[ScreenerService, MultiUniverseScreener]:
    """A Finviz-shaped export and an OpenD-shaped "ETF" catalog with REIT/CEF contamination."""

    industries = ("Exchange Traded Fund", "REIT - Specialty", "Closed-End Fund - Equity", "Software - Application")
    finviz = [SimpleNamespace(ticker=f"S{index:05d}", company=f"Synthetic {index}", sector="Financial",
                              industry=industries[index % len(industries)], country="USA", price=10.0 + index,
                              change_pct=0.1, volume=1000 + index, **{name: None for name in (
                                  "avg_volume", "rel_volume", "market_cap", "shares_outstanding", "float_shares",
                                  "short_float_pct", "short_ratio", "eps_ttm", "pe", "fwd_pe", "rsi_14",
                                  "perf_week")}, earnings_date=None, recommendation=None)
              for index in range(size)]

    class Finviz:
        def fetch_export(self, *, filter_expr: str, columns: str) -> dict[str, Any]:
            time.sleep(0.25)  # stands in for the export download, paid once per TTL
            return {"success": True, "received_at": "2026-09-29T12:58:00Z", "rows": finviz}

    class OpenD:
        def fetch_etf_catalog(self) -> dict[str, Any]:
            rows = [{"code": f"US.S{index:05d}", "name": f"Synthetic {index}", "stock_type": "ETF",
                     "exchange_type": "US_NYSE", "delisting": False} for index in range(size) if index % 4 != 3]
            return {"rows": rows, "reason_code": None}

        def fetch_future_contracts(self, codes: list[str]) -> dict[str, Any]:
            return {"rows": [], "reason_code": None}

    equities = ScreenerService(source_factory=Finviz, runtime_getter=lambda **_: None)
    multi = MultiUniverseScreener(transport_getter=OpenD, reference_getter=equities.classification_reference)
    return equities, multi


def main() -> int:
    parser = argparse.ArgumentParser(description="Screener S13 universe integrity audit")
    parser.add_argument("--sample", default="EQIX,WY,AIO,SPY,AGG,GLD,TQQQ,SH,JEPI,TLT",
                        help="comma-separated symbols to explain")
    parser.add_argument("--synthetic", type=int, default=0,
                        help="measure US Equities/ETF admission on N synthetic listings (offline)")
    parser.add_argument("--json", action="store_true", help="print the full JSON report")
    args = parser.parse_args()
    sample = [item.strip().upper() for item in args.sample.split(",") if item.strip()]
    if args.synthetic:
        return _run(args, sample)
    from market_platform_foundation.market_data.current_bars import current_bars_service

    try:
        return _run(args, sample)
    finally:
        # The OpenD quote context runs non-daemon SDK threads: without close() the report
        # prints and the process never exits (found in the S13 live acceptance).
        close = getattr(current_bars_service().transport(), "close", None)
        if callable(close):
            close()


def _run(args: argparse.Namespace, sample: list[str]) -> int:
    if args.synthetic:
        equities, multi = _synthetic(args.synthetic)

        def read(**kwargs: Any) -> dict[str, Any]:
            universe = kwargs.pop("universe")
            if universe == US_EQUITIES:
                return equities.read(**kwargs)
            if universe == US_ETFS:
                return multi.read(universe=universe, **kwargs)
            return {"rows": [], "has_more": False, "source_error": "NOT_IN_SYNTHETIC_RUN"}
    else:
        from market_platform_foundation.ui_api.screener_multi import multi_screener_service
        from market_platform_foundation.ui_api.screener_projections import read_screener, screener_service

        equities, multi, read = screener_service(), multi_screener_service(), read_screener
    report = audit(read, equities=equities, multi=multi, sample=sample)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
        return 0
    print(f"{'universe':<12} {'raw':>7} {'accepted':>9} {'rejected':>9} {'ambiguous':>9}  "
          f"{'cold ms':>9} {'warm ms':>8} {'query ms':>9}  top rejection reasons")
    for universe, item in report["universes"].items():
        admission = item["admission"]
        latency = item["latency_ms"]
        reasons = ", ".join(f"{key}={value}" for key, value in list(admission.get("rejection_reasons", {}).items())[:5])
        print(f"{universe:<12} {admission.get('provider_raw_count', '-')!s:>7} {item['accepted']:>9} "
              f"{admission.get('rejected', '-')!s:>9} {admission.get('ambiguous', '-')!s:>9}  "
              f"{latency['cold_catalog_all_pages']:>9} {latency['warm_first_page']:>8} {latency['warm_search']:>9}  "
              f"{reasons or '-'}{'  [' + str(item['source_error']) + ']' if item['source_error'] else ''}")
    integrity = report["integrity"]
    print(f"\nrow-contract violations: {len(integrity['violations'])}; "
          f"cross-universe duplicates: {len(integrity['cross_universe_duplicates'])}")
    for finding in integrity["cross_universe_duplicates"][:20]:
        print(f"  DUPLICATE {finding['kind']} {finding['key']}: {', '.join(finding['universes'])}")
    for finding in integrity["violations"][:20]:
        print(f"  VIOLATION {finding['universe']} {finding['symbol']}: {finding['problem']}")
    for finding in report["findings"]:
        print(f"  FINDING {finding}")
    print("\nsamples:")
    for symbol, item in report["samples"].items():
        decision = item["etf_decision"] or {}
        reference = decision.get("reference") or {}
        print(f"  {symbol:<6} in {', '.join(item['universes']) or '(none)':<24} provider-ETF-typed="
              f"{'yes' if decision else 'no':<3} ETF decision={decision.get('status', '-')}"
              f"{'/' + decision['reason'] if decision.get('reason') else ''} industry={reference.get('industry')}")
    if not integrity["clean"] or report["findings"]:
        return 1
    # A universe that did not load is not evidence of integrity: acceptance is incomplete.
    loaded = (US_EQUITIES, US_ETFS) if args.synthetic else tuple(report["universes"])
    return 2 if any(report["universes"][universe]["source_error"] for universe in loaded) else 0


if __name__ == "__main__":
    raise SystemExit(main())

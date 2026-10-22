"""Stage-level performance profile for the Live Screener -> AI analysis path.

The profile answers one question per pipeline stage: where does the CPU and
allocation time actually go? It measures the production functions against
frozen, deterministic, shape-accurate fixtures -- no provider, no network, no
model, no spend -- so a later run on any machine produces a comparable record.

Usage::

    python tools/screener_ai_perf_profile.py                 # full profile
    python tools/screener_ai_perf_profile.py --quick         # fewer repeats
    python tools/screener_ai_perf_profile.py --out FILE.json

The record carries its own fixture identity, source SHA, environment and
comparison status so a later report can tell COMPARABLE from INCOMPATIBLE.
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
from pathlib import Path
from typing import Any, Callable

TOOL_PATH = Path(__file__).resolve()
_source_parser = argparse.ArgumentParser(add_help=False)
_source_parser.add_argument("--source-root", type=Path)
_source_args, _ = _source_parser.parse_known_args()
ROOT = (_source_args.source_root or TOOL_PATH.parents[1]).resolve()
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

PROFILE_VERSION = "screener-ai-perf-profile/2.0.0"

# The portable workstation admitted ~4,622 US equity rows; the profile keeps
# that as the headline universe so before/after numbers stay comparable with
# anything already recorded.
HEADLINE_ROWS = 4622
PAGE_LIMIT = 200
MAX_PAGE_LIMIT = 500
#: Universes this profile actually exercises. The ETF, futures, bonds and crypto
#: services need a live vendor catalog and transport, so this profile does not
#: claim to measure them; they are recorded as out of scope, not as fast.
PROFILED_UNIVERSES = ("US_EQUITIES",)
UNPROFILED_UNIVERSES = ("US_ETFS", "FUTURES", "BONDS", "CRYPTO")

_SECTORS = ("Basic Materials", "Technology", "Financial", "Healthcare", "Consumer Cyclical",
            "Communication Services", "Industrials", "Energy", "Consumer Defensive",
            "Real Estate", "Utilities")
_INDUSTRIES = ("Software - Infrastructure", "Semiconductors", "Banks - Diversified",
               "Biotechnology", "Major Pharmaceuticals", "Auto Manufacturers",
               "Internet Content & Information", "Oil & Gas Integrated", "Retail - General",
               "REIT - Industrial", "Utilities - Regulated Electric")


# --------------------------------------------------------------------------- fixture

def _symbol(index: int) -> str:
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return letters[index // 676 % 26] + letters[index // 26 % 26] + letters[index % 26] + (str(index // 17576) or "")


def _finviz_rows(count: int) -> list:
    """A deterministic export-shaped list. Values are spread over realistic ranges so
    ordering, filtering and missing-value handling are all exercised."""

    from market_platform_foundation.finviz.screener import FinvizScreenerRow

    rows = []
    for index in range(count):
        strong = index % 7 == 0
        # ~1 in 11 listings is an ETF and is rejected by US Equities admission.
        etf = index % 11 == 0
        rows.append(FinvizScreenerRow(
            ticker=f"{_symbol(index)}{'X' if index % 11 == 0 else ''}",
            company=f"{_symbol(index)} Holdings {index}",
            sector=_SECTORS[index % len(_SECTORS)],
            industry="Exchange Traded Fund" if etf else _INDUSTRIES[index % len(_INDUSTRIES)],
            country="USA",
            price=None if index % 53 == 0 else round(4.0 + (index % 997) * 1.37, 2),
            change_pct=round(-9.5 + (index % 191) * 0.1, 2),
            volume=(index * 7919) % 90_000_000,
            avg_volume=1_200_000 + (index % 640) * 9_000,
            rel_volume=round(0.3 + (index % 90) * 0.1, 2),
            market_cap=1.0e8 + (index % 5000) * 3.1e7,
            shares_outstanding=1.0e8 + (index % 3000) * 1.4e7,
            float_shares=5.0e7 + (index % 2900) * 9.0e6,
            short_float_pct=None if index % 71 == 0 else round(0.5 + (index % 60) * 0.5, 2),
            short_ratio=None if index % 71 == 0 else round(0.4 + (index % 30) * 0.3, 2),
            eps_ttm=round(-2.0 + (index % 400) * 0.15, 2),
            pe=None if index % 67 == 0 else round(-30.0 + (index % 900) * 0.9, 2),
            fwd_pe=None if index % 67 == 0 else round(-30.0 + (index % 800) * 0.8, 1),
            rsi_14=round(15.0 + (index % 700) * 0.1, 1),
            earnings_date=None if index % 3 else f"2026-1{index % 9 + 1}-1{index % 9}",
            perf_week=round(-25.0 + (index % 500) * 0.1, 1),
            recommendation=None if index % 5 else "Outperform",
            provider_columns=("Ticker", "Company"),
            raw_fields={},
        ))
    return rows


def _fixture_identity(rows: list) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(json.dumps(row.as_dict(), sort_keys=True, allow_nan=False).encode())
    digest.update(f"|n={len(rows)}".encode())
    return "finviz-export/" + digest.hexdigest()


class FrozenExport:
    """The Finviz export contract, served from memory. No credential, no request."""

    def __init__(self, rows: list, *, received_at: str) -> None:
        self.payload = {"success": True, "error": None, "rows": rows, "columns": ["Ticker", "Company"],
                        "received_at": received_at, "available_time_ns": 0}

    def fetch_export(self, **_: Any) -> dict:
        return self.payload


def _snapshot_source(rows: list, as_of: str):
    """A ScreenerService whose refresh and quote lookup are both frozen."""

    from market_platform_foundation.ui_api import screener_projections as sp

    service = sp.ScreenerService(source_factory=lambda: FrozenExport(rows, received_at=as_of),
                                runtime_getter=lambda **_k: None, quote_transport_getter=lambda: None)
    service._refresh(force=True)
    return service


# --------------------------------------------------------------------------- timing

def _measure(label: str, fn: Callable[[], Any], *, repeat: int, warmup: int = 1,
             memory: bool = False, keep: Callable[[Any], Any] | None = None) -> dict[str, Any]:
    """Time first, then memory.

    ``tracemalloc`` instruments every allocation and inflates wall time several
    times over, so peak memory is measured in its own separate pass and never
    mixed into the timing samples.
    """

    if repeat < 1:
        raise ValueError("repeat must be positive")
    for _ in range(warmup):
        keep(fn()) if keep else fn()
    samples: list[float] = []
    result: Any = None
    for _ in range(repeat):
        start = time.perf_counter()
        result = fn()
        samples.append((time.perf_counter() - start) * 1000.0)
    samples.sort()
    peak = 0
    if memory:
        gc.collect()
        tracemalloc.start()
        tracemalloc.reset_peak()
        fn()
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
    return {
        "stage": label,
        "repeat": repeat,
        "warmup": warmup,
        "samples_ms": samples,
        "stddev_ms": statistics.stdev(samples) if len(samples) > 1 else 0.0,
        "median_ms": round(statistics.median(samples), 4),
        "mean_ms": round(statistics.fmean(samples), 4),
        "min_ms": round(samples[0], 4),
        "p95_ms": round(samples[min(len(samples) - 1, int(len(samples) * 0.95))], 4),
        "max_ms": round(samples[-1], 4),
        "peak_traced_bytes": peak,
        "value": keep(result) if keep else None,
    }


# --------------------------------------------------------------------------- profile

def profile(*, repeat: int, quick: bool) -> dict[str, Any]:
    from market_platform_foundation.finviz.screener import FinvizScreenerRow  # noqa: F401
    from market_platform_foundation.intelligence.inference import candidate_reduction as cr
    from market_platform_foundation.intelligence.inference import coverage_plan as cp
    from market_platform_foundation.market_data.freshness_contract import evaluate
    from market_platform_foundation.market_data.live_runtime import provider_symbol_for
    from market_platform_foundation.ui_api import screener_ai as sai
    from market_platform_foundation.ui_api import screener_filters as sf
    from market_platform_foundation.ui_api import screener_freshness as freshness
    from market_platform_foundation.ui_api import screener_projections as sp
    from market_platform_foundation.ui_api import screener_query as sq
    from market_platform_foundation.ui_api.screener_ai_universe import enumerate_universe
    from market_platform_foundation.ui_api.screener_news_evidence import attach_news, fit_news

    as_of = "2026-10-02T15:00:00Z"
    now = as_of
    # Size the export so the *admitted* count matches the workstation's real universe.
    # The fixture rejects exactly one listing in eleven (ETF industry), so the export
    # is solvable: admitted = provider - ceil(provider / 11).
    admitted_target = 800 if quick else HEADLINE_ROWS
    universe_size = -(-admitted_target * 11 // 10)
    raw = _finviz_rows(universe_size)
    fixture_id = _fixture_identity(raw)
    service = _snapshot_source(raw, as_of)
    rows = list(service._rows)
    admitted = len(rows)
    stages: list[dict[str, Any]] = []

    def add(label, fn, *, memory=False, keep=None, rep=None):
        stages.append(_measure(label, fn, repeat=rep or repeat, memory=memory, keep=keep))

    # ---------------------------------------------------------------- ingestion
    def ingest():
        decisions = [(row, sp.admit_equity(row, as_of=as_of)) for row in raw]
        return [sp._snapshot_row(row, as_of, decision.classification)
                for row, decision in decisions if decision.admitted]

    add("ingest.finviz_export_parse", lambda: [_finviz_rows(400)], rep=3 if not quick else 2)
    add("ingest.admission_and_projection", ingest, memory=True,
        keep=lambda out: {"rows": len(out)})
    add("ingest.classification_reference", lambda: sp.ClassificationReference.build(raw, as_of=as_of),
        keep=lambda ref: {"entries": len(ref.entries)})
    # The whole production refresh: fetch is frozen, so this is the CPU a cold or
    # 120-second-old universe load pays on top of the export round trip.
    add("ingest.universe_refresh_cpu", lambda: service._refresh(force=True), rep=max(3, repeat // 3),
        memory=True, keep=lambda out: len(service._rows))

    # ---------------------------------------------------------------- filtering
    rules = [
        {"id": "p1", "field": "price", "operator": "gte", "value": 10.0},
        {"id": "p2", "field": "rel_volume", "operator": "gt", "value": 1.0},
        {"id": "p3", "field": "sector", "operator": "eq", "value": "Technology"},
    ]
    validated = sf.validate_filters(rules)
    add("filter.validate_filters", lambda: sf.validate_filters(rules), keep=lambda v: len(v))

    def observe(row, name):
        return sf.field_value(row, name)

    add("filter.field_value_x_rows", lambda: [observe(row, "price") for row in rows], keep=None)
    add("filter.apply_filters_3_rules", lambda: sf.apply_filters(rows, validated, observe),
        keep=lambda out: {"matched": len(out)})

    matched = sf.apply_filters(rows, validated, observe)
    add("filter.apply_filters_0_rules", lambda: sf.apply_filters(rows, [], observe),
        keep=lambda out: {"matched": len(out)})

    # ---------------------------------------------------------------- ordering
    add("order.order_rows_full", lambda: sq.order_rows(rows, "volume", True, observe),
        keep=lambda out: {"ordered": len(out)})
    add("order.order_rows_string_sort", lambda: sq.order_rows(rows, "sector", False, observe),
        keep=lambda out: {"ordered": len(out)})

    needle = "aa"
    searched = [row for row in rows
                if needle in row["symbol"].casefold() or needle in (row["company"] or "").casefold()]
    ordered = sq.order_rows(matched, "volume", True, observe)
    add("search.symbol_company_scan", lambda: [row for row in rows
                                               if needle in row["symbol"].casefold() or needle in (row["company"] or "").casefold()],
        keep=lambda out: {"matched": len(out)})
    add("search.exact_matches_first", lambda: sq.exact_matches_first(ordered, needle),
        keep=lambda out: {"ordered": len(out)})

    query = sq.parse_query(universe="US_EQUITIES", sort="volume", descending=True,
                           offset=0, limit=PAGE_LIMIT, filters=[])
    add("page.page_payload", lambda: sq.page_payload(query, ordered), keep=lambda p: p["result_count"])
    page = sq.page_payload(query, ordered)
    add("page.window_slice", lambda: ordered[query.offset:query.offset + query.limit], keep=lambda p: len(p))

    # ---------------------------------------------------------------- page projection
    from market_platform_foundation.ui_api.screener_snapshot import MarketSnapshot

    snapshot = MarketSnapshot(
        id="snap-1", as_of=as_of, catalog_as_of=as_of, total=len(rows),
        values={row["instrument"]["instrument_id"]: {"bid": 10.0, "ask": 10.1, "spread_pct": 0.99}
                for row in rows},
        row_as_of={row["instrument"]["instrument_id"]: as_of for row in rows},
        refused=frozenset(), calls=12, duration_ms=180.0, taken_monotonic=1.0)
    window = ordered[:PAGE_LIMIT]
    add("page.quote_snapshot_overlay", lambda: [sp._with_quote_snapshot(row, snapshot) for row in window],
        keep=lambda out: len(out))

    quote_payload = {"state": "LIVE", "age_ms": 120, "reason": None, "quality": "PASS", "admission": "PASS",
                     "fields": {name: {"value": 10.0, "source": "MOOMOO", "state": "LIVE",
                                       "as_of_ns": 1, "event_time_ns": 1,
                                       "provider_as_of": as_of, "received_ns": 1}
                                for name in ("price", "volume", "bid", "ask", "spread_pct")}}
    add("page.quote_view_over_window", lambda: [sp.quote_view(None, _FakeQuote()) for _ in window],
        keep=lambda out: len(out))
    add("page.with_current_quote_over_window",
        lambda: [sp.with_current_quote(row, quote_payload) for row in window], keep=lambda out: len(out))
    add("page.provider_symbol_map_all_rows",
        lambda: [{"provider_symbol": provider_symbol_for(row["instrument"]["instrument_id"]),
                  "instrument": row["instrument"]} for row in rows], keep=lambda out: len(out))

    # ---------------------------------------------------------------- API serialization
    import json as _json

    envelope = dict(page)
    add("api.serialize_page_json", lambda: _json.dumps(envelope, default=str),
        keep=lambda text: len(text.encode()))
    from market_platform_foundation.ui_api.server import canonical_response_bytes, with_engine_lock

    add("api.canonical_response_bytes", lambda: canonical_response_bytes({"payload": envelope}),
        keep=lambda raw: len(raw) if isinstance(raw, (bytes, bytearray)) else None)

    # ---- what one /screener response actually costs the server ----
    from market_platform_foundation.platform.security import leak_audit

    full_page = {"market_session": "REGULAR", "rows": ordered[:PAGE_LIMIT], **page}
    add("api.leak_scan_structural", lambda: leak_audit.scan_snapshot(full_page),
        keep=lambda out: len(out))
    add("api.leak_render_json", lambda: _json.dumps(full_page, sort_keys=True, default=str),
        keep=lambda text: len(text.encode()))
    rendered = _json.dumps(full_page, sort_keys=True, default=str)
    add("api.leak_audit_text_rules", lambda: leak_audit.audit_text(rendered),
        keep=lambda rules: len(rules))
    add("api.leak_assert_full", lambda: leak_audit.assert_no_secrets_in_payload(full_page),
        keep=lambda out: None)
    add("api.freshness_projection_for_response",
        lambda: freshness.project_screener_response("/screener", full_page, now=now),
        keep=lambda out: len(out["rows"]))

    def serve_page():
        # Exactly what UiApiHandler._send_json does for a /screener response.
        payload = freshness.project_screener_response("/screener", full_page, now=now)
        payload = with_engine_lock(payload, lambda: None)
        leak_audit.assert_no_secrets_in_payload(payload)
        return canonical_response_bytes(payload)

    add("api.serve_screener_page_total", serve_page,
        keep=lambda body: len(body))

    # ---------------------------------------------------------------- freshness projection
    projected_payload = {"market_session": "REGULAR", "rows": ordered[:PAGE_LIMIT]}
    add("evidence.project_screener_response_page",
        lambda: freshness.project_screener_response("/screener", projected_payload, now=now),
        keep=lambda out: {"rows": len(out["rows"])})

    projected_rows = freshness.project_screener_response("/screener", projected_payload, now=now)["rows"]
    add("evidence.observations_for_row",
        lambda: [sai.observations_for_row(row, now=now) for row in projected_rows],
        keep=lambda out: {"observations": sum(len(item) for item in out)})

    add("evidence.build_candidate",
        lambda: [cr.build_candidate(row["instrument"], sai.observations_for_row(row, now=now), now=now)
                 for row in projected_rows],
        keep=lambda out: {"candidates": len(out)})

    candidates = [cr.build_candidate(row["instrument"], sai.observations_for_row(row, now=now), now=now)
                  for row in projected_rows]
    add("evidence.market_freshness_evaluate",
        lambda: [evaluate(capability="market_snapshot", source="MOOMOO_OPEND_SNAPSHOT",
                          delivery_mode="SNAPSHOT", now=now, as_of=as_of, stale_after_ms=60000,
                          policy="L1_EVENT_V1", basis="PROVIDER_AS_OF", state="AVAILABLE")
                 for _ in projected_rows], keep=lambda out: len(out))

    # ---------------------------------------------------------------- AI planning
    scope = {"universe": "US_EQUITIES", "search": "", "sort": "volume", "descending": True,
             "filters": [], "result_set": as_of, "matched_count": admitted}
    eligible = [c["instrument"]["instrument_id"] for c in candidates]
    add("plan.fair_order", lambda: cp.fair_order(as_of, eligible), keep=lambda out: len(out))
    add("plan.chunks", lambda: cp.chunks(cp.fair_order(as_of, eligible)), keep=lambda out: len(out))
    add("plan.reduction_rounds", lambda: cp.reduction_rounds(len(cp.chunks(cp.fair_order(as_of, eligible)))),
        keep=lambda out: out)
    add("plan.classify_all_rows",
        lambda: {c["instrument"]["instrument_id"]: cp.classify(c) for c in candidates},
        keep=lambda out: cp.tally(out))
    add("plan.tally_reconciles",
        lambda: cp.reconciles(cp.tally({c["instrument"]["instrument_id"]: cp.classify(c)
                                        for c in candidates}), len(candidates)),
        keep=lambda out: out)

    empty_news = {}
    add("plan.fit_news", lambda: fit_news(scope, list(candidates), empty_news, now=now), keep=lambda out: out)
    add("plan.attach_news_noop",
        lambda: [attach_news(c, {"stories": [], "retrieved_at": now}, now=now) for c in candidates],
        keep=lambda out: len(out))

    # ---------------------------------------------------------------- enumeration
    from tests.support.coverage_universe import PagingReader, row as controlled_row

    enum_scope = {"universe": "US_EQUITIES", "search": "", "sort": "volume", "descending": True,
                   "filters": [], "result_set": None}
    controlled = [controlled_row(index) for index in range(admitted)]
    add("coverage.enumerate_universe",
        lambda: enumerate_universe(PagingReader(controlled, result_set="set-1"), enum_scope),
        keep=lambda out: {"rows": len(out.rows), "pages": out.pages})

    class _ServiceReader:
        """Reads the frozen production service page by page, as the coverage run does."""

        def __init__(self) -> None:
            self.calls = 0

        def read(self, **kwargs):
            self.calls += 1
            kwargs.setdefault("universe", "US_EQUITIES")
            kwargs.setdefault("result_set", as_of)
            return service.read(**kwargs)

    if not quick:
        add("coverage.enumerate_universe_from_service",
            lambda: enumerate_universe(_ServiceReader(), enum_scope),
            keep=lambda out: {"rows": len(out.rows), "pages": out.pages})

    # ---------------------------------------------------------------- end-to-end read
    def read_cached():
        return service.read(universe="US_EQUITIES", sort="volume", descending=True,
                            offset=0, limit=PAGE_LIMIT, filters=[], result_set=as_of)

    add("e2e.screener_read_cached_page", read_cached, keep=lambda out: out["result_count"])

    def read_uncached():
        service._ordered.clear()
        return service.read(universe="US_EQUITIES", sort="volume", descending=True,
                            offset=0, limit=PAGE_LIMIT, filters=[], result_set=as_of)

    add("e2e.screener_read_uncached_page", read_uncached, keep=lambda out: out["result_count"])

    def read_filtered_uncached():
        service._ordered.clear()
        return service.read(universe="US_EQUITIES", sort="volume", descending=True, offset=0,
                            limit=PAGE_LIMIT, filters=rules, result_set=as_of)

    add("e2e.screener_read_filtered_uncached", read_filtered_uncached,
        keep=lambda out: out["result_count"])

    full_enumeration = enumerate_universe(_ServiceReader(), enum_scope)
    full_ordered = sq.order_rows(rows, "volume", True, observe)
    if _digest(list(full_enumeration.rows)) != _digest(full_ordered):
        raise AssertionError("full-universe paging changed rows, values, or order")
    if len(full_enumeration.rows) != admitted or len({row["instrument"]["instrument_id"] for row in full_enumeration.rows}) != admitted:
        raise AssertionError("full-universe admission accounting does not reconcile")
    ordered_rows = sq.order_rows(matched, "volume", True, observe)
    # Parity covers identity *and* values: a change that kept the same rows in the
    # same order while altering any field value would otherwise pass undetected.
    ordered_digest = hashlib.sha256(json.dumps(
        [[row["instrument"]["instrument_id"], row["symbol"], row.get("sector"),
          sorted((name, (field or {}).get("value")) for name, field in (row.get("fields") or {}).items())]
         for row in ordered_rows], sort_keys=True, default=str).encode()).hexdigest()

    return {
        "profile_version": PROFILE_VERSION,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": _source_identity(),
        "methodology": {
            "tool_sha256": hashlib.sha256(TOOL_PATH.read_bytes()).hexdigest(),
            "clock": "perf_counter", "warmup": 1, "gc_enabled": gc.isenabled(),
            "memory": "separate tracemalloc pass", "cache": "per-stage explicit warm/clear",
            "measurement": "production functions on deterministic synthetic Finviz rows",
            "source_cleanliness_scope": ["src", "tools", "ui"],
            "excluded": ["HTTP transport", "provider requests", "browser frames", "inference"],
        },
        "environment": _environment(),
        "fixture": {
            "identity": fixture_id,
            "provider_rows": len(raw),
            "admitted_rows": admitted,
            "admitted_target": admitted_target,
            "requested_universe": universe_size,
            "page_limit": PAGE_LIMIT,
            "profiled_universes": list(PROFILED_UNIVERSES),
            "unprofiled_universes": list(UNPROFILED_UNIVERSES),
            "quick_mode": quick,
        },
        "parity": {
            "ordered_match_digest": ordered_digest,
            "full_universe_values_digest": _digest(sq.order_rows(rows, "volume", True, observe)),
            "api_payload_digest": hashlib.sha256(serve_page()).hexdigest(),
            "enumerated_rows": len(full_enumeration.rows),
            "enumerated_pages": full_enumeration.pages,
            "observations_digest": _digest([sai.observations_for_row(row, now=now) for row in projected_rows]),
            "ordered_matched": len(matched),
            "filtered_by": validated,
        },
        "stages": stages,
    }


class _FakeQuote:
    received_ns = 1
    event_time_ns = 1
    book_received_ns = 1
    quality = "PASS"
    admission = "PASS"
    provider = "MOOMOO"
    bid_price, ask_price, last_price, volume = 10.0, 10.1, 10.05, 1_000_000


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, allow_nan=False).encode()).hexdigest()


def _source_identity() -> dict[str, Any]:
    def git(*args: str) -> str:
        result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise RuntimeError("source identity unavailable")
        return result.stdout.strip()
    status = git("status", "--porcelain", "--untracked-files=all", "--", "src", "tools", "ui")
    return {"sha": git("rev-parse", "HEAD"), "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "dirty": bool(status), "dirty_scope": ["src", "tools", "ui"], "dirty_paths": sorted(line[3:] for line in status.splitlines()),
            "tool_sha256": hashlib.sha256(TOOL_PATH.read_bytes()).hexdigest()}


def _physical_memory() -> int | None:
    if os.name == "nt":
        import ctypes
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in ("total_physical", "available_physical", "total_page", "available_page", "total_virtual", "available_virtual", "extended")]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return status.total_physical
    elif hasattr(os, "sysconf"):
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    return None


def _environment() -> dict[str, Any]:
    return {"python": sys.version.split()[0], "implementation": platform.python_implementation(),
            "platform": platform.platform(), "processor": platform.processor() or platform.machine(),
            "cpu_count": os.cpu_count(), "physical_memory_bytes": _physical_memory(),
            "machine_identity": hashlib.sha256(platform.node().encode()).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, help="read production functions from this clean IMP source tree")
    parser.add_argument("--quick", action="store_true", help="smaller universe and fewer repeats")
    parser.add_argument("--repeat", type=int, default=9)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.repeat < 1:
        parser.error("--repeat must be positive")
    record = profile(repeat=args.repeat, quick=args.quick)
    out = args.out or (ROOT / "artifacts" / "screener-ai-performance-profile.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2), encoding="utf-8")

    print(f"{'stage':44s} {'median ms':>11s} {'p95 ms':>10s} {'peak KiB':>10s}")
    for stage in record["stages"]:
        print(f"{stage['stage']:44s} {stage['median_ms']:11.3f} {stage['p95_ms']:10.3f} "
              f"{stage['peak_traced_bytes'] / 1024:10.1f}")
    print(f"\nfixture={record['fixture']['identity']} admitted={record['fixture']['admitted_rows']}")
    print(f"sha={record['source']['sha'][:12]} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
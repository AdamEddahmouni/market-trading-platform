"""Screener S12: Institutional, Whale, Congressional & Government intelligence.

A cross-universe *intelligence layer*, never a universe. Four evidence families stay
separate and are never blended into a score:

* INSTITUTIONAL — SEC beneficial-ownership (Schedule 13D/13G) and insider (Form 4)
  filings; 13F holdings when an operator-built index is present;
* WHALE / LARGE PARTICIPANT — disclosed large holders (13D/13G), CFTC Commitments of
  Traders categories (Futures), and large-print market activity whose participant is
  UNKNOWN (the Order Flow panel's evidence; never attributed to an institution);
* CONGRESSIONAL — House Periodic Transaction Reports from the House Clerk (official
  PDFs; transaction rows only where the filer disclosed a ticker);
* GOVERNMENT — USAspending federal award transactions (contracts, grants kept
  separate) and Lobbying Disclosure Act filings.

Read models:

* ``ownership_view``   — Institutional view (US Equities): recent Form 4 / 13D / 13G
  filings for the universe from the EDGAR daily form index;
* ``positioning_view`` — Institutional view (Futures): latest public COT report per root;
* ``congress_view``    — Congress view (US Equities, ETFs): disclosed transactions;
* ``instrument``       — the two dock panels and the Quick Preview (``compact``).

Every disclosure keeps its clocks apart — event/transaction date, filing date,
publication/availability, retrieval, ingestion — and availability is never the
event date. Nothing here reads fixture, replay, or donor data; nothing ranks people.
"""

from __future__ import annotations

import os
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

from ..cftc.screener_positioning import DATASETS, POSITIONING_MARKETS, build_positioning, where_clause
from ..congressional_ptr import house
from ..public_records.http import PublicRecordsError, PublicRecordsHttp
from ..public_records.http import live_state as public_live_state
from ..sec_edgar import ownership as sec_ownership
from .screener_squeeze_sources import BackgroundCache
from .screener_universes import FUTURES, UNIVERSES, US_EQUITIES, US_ETFS

SCHEMA_VERSION = "screener-participants/1.0.0"
ET = ZoneInfo("America/New_York")

INSTITUTIONAL_PANEL, GOVERNMENT_PANEL = "institutional", "congress_gov"
#: Views per universe (from the universe capability registry); a view exists only where universe-wide evidence exists.
VIEWS = {spec.id: spec.intelligence_views for spec in UNIVERSES.values() if spec.intelligence_views}

OWNERSHIP_WINDOWS = {"1d": 1, "3d": 3, "5d": 5, "10d": 10}           # business days of daily indexes
CONGRESS_WINDOWS = {"30d": 30, "60d": 60, "90d": 90}                 # calendar days by filing date
INSTRUMENT_CONGRESS_DAYS = 90
AWARD_WINDOW_DAYS = 90
DEFAULT_LIMIT, MAX_LIMIT = 100, 200
MAX_PTR_DOCUMENTS = 160
MAX_FORM4_DOCS, MAX_13DG_DOCS = 8, 6
PROVIDER_WAIT_S = 6.0

TTL = {"house_index": 6 * 3600.0, "sec_index_today": 1800.0, "sec_index_past": 24 * 3600.0,
       "submissions": 1800.0, "cot": 3 * 3600.0, "usaspending": 12 * 3600.0, "usaspending_updated": 6 * 3600.0,
       "lobbying": 24 * 3600.0, "universe_index": 600.0}
AMOUNT_FLOORS = (1_001, 15_001, 50_001, 100_001, 250_001, 1_000_001)
CONGRESS_TYPES = ("PURCHASE", "SALE", "SALE_PARTIAL", "EXCHANGE")
OWNERSHIP_FAMILIES = {"INSIDER": sec_ownership.INSIDER_FORMS,
                      "BENEFICIAL_13D": frozenset({"SCHEDULE 13D", "SCHEDULE 13D/A", "SC 13D", "SC 13D/A"}),
                      "BENEFICIAL_13G": frozenset({"SCHEDULE 13G", "SCHEDULE 13G/A", "SC 13G", "SC 13G/A"})}
SENATE_REASON = "SENATE_EFD_REQUIRES_INTERACTIVE_TERMS_ACCEPTANCE"
SENATE_URL = "https://efdsearch.senate.gov/search/"
HOUSE_SEARCH_URL = "https://disclosures-clerk.house.gov/FinancialDisclosure"

PROVIDERS = {
    "sec_ownership": ("SEC EDGAR ownership filings", "INSTITUTIONAL", "Filing-driven; EDGAR acceptance time"),
    "sec_daily_index": ("SEC EDGAR daily form index", "INSTITUTIONAL", "Daily; filing date only"),
    "thirteen_f": ("SEC Form 13F data sets", "INSTITUTIONAL", "Quarterly; ~45 days after quarter end"),
    "cftc_cot": ("CFTC Commitments of Traders", "WHALE", "Weekly; Tuesday positions, Friday 15:30 ET release"),
    "order_flow": ("Large prints (Order Flow panel)", "WHALE", "Live session; participant unknown"),
    "house_ptr": ("House Clerk financial disclosures", "CONGRESSIONAL", "Filing-driven; index refreshed by the Clerk"),
    "senate_efd": ("Senate eFD", "CONGRESSIONAL", "Filing-driven"),
    "usaspending": ("USAspending.gov", "GOVERNMENT", "Daily loads; FPDS contract actions lag several days"),
    "lobbying": ("Lobbying Disclosure Act (lda.gov)", "GOVERNMENT", "Quarterly LD-2 reports; posted when filed"),
}

EVIDENCE_BOUNDARIES = (
    "A 13F holding is a quarter-end position disclosed weeks later, not a live position.",
    "A congressional transaction date is not its disclosure date; the amount is a disclosed range, not an exact size.",
    "A government award or grant is not revenue and not a bullish signal; lobbying is not government support.",
    "A large print is market activity with an unknown participant; it is not an institution or accumulation.",
    "CFTC positioning describes reported categories; it is not a price forecast.",
)


def _iso(moment: datetime | None) -> str | None:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def _norm_ticker(value: str | None) -> str:
    return re.sub(r"[./]", "-", (value or "").strip().upper())


def provider(pid: str, state: str, reason: str | None = None, *, fetched_at: str | None = None,
             published: str | None = None, items: int | None = None, scope: str = "INSTRUMENT") -> dict[str, Any]:
    label, family, cadence = PROVIDERS[pid]
    return {"id": pid, "label": label, "family": family, "scope": scope, "state": state, "reason": reason,
            "fetched_at": fetched_at, "published": published, "item_count": items, "cadence": cadence}


def _section(state: str, reason: str | None = None, **extra: Any) -> dict[str, Any]:
    return {"state": state, "reason": reason, **extra}


# ------------------------------------------------------------------ defaults (live wiring)
def _default_catalog(universe: str) -> tuple[list[dict[str, Any]], str | None]:
    from .screener_news import _default_catalog as news_catalog

    return news_catalog(universe)


def _default_row(instrument_id: str, universe: str) -> dict[str, Any] | None:
    from .screener_multi import multi_screener_service

    row, _error = multi_screener_service().row_for(instrument_id, universe=universe)
    return row


def _default_sec_transport():
    from ..sec_edgar.transport import SecTransport

    return SecTransport(user_agent=os.environ.get("SEC_USER_AGENT", ""))


def _default_cot_query(dataset: Any, where: str) -> list[dict[str, Any]]:
    from ..cftc.live import transport_from_env

    return transport_from_env().query_dataset(dataset, where=where, order="report_date_as_yyyy_mm_dd DESC", limit=1000)


# ------------------------------------------------------------------ House PTR loader
@dataclass(slots=True)
class _HouseState:
    started: bool = False
    running: bool = False
    index_error: str | None = None
    index_fetched_at: str | None = None
    filings: list[house.HouseFiling] = field(default_factory=list)
    documents: dict[str, house.PtrDocument] = field(default_factory=dict)
    retrieved: dict[str, str] = field(default_factory=dict)
    doc_errors: dict[str, str] = field(default_factory=dict)
    built_at: float = 0.0


class HousePtrLoader:
    """Loads the House filing index and PTR documents off the request thread, progressively.

    Documents are immutable per DocID and kept for the process lifetime; the index is
    re-read every ``TTL["house_index"]``. Views read a consistent snapshot while loading.
    """

    def __init__(self, *, http: PublicRecordsHttp, clock: Callable[[], float],
                 spawn: Callable[[Callable[[], None]], None] | None = None,
                 window_days: int = max(CONGRESS_WINDOWS.values())) -> None:
        self._http = http
        self._clock = clock
        self._spawn = spawn or (lambda job: threading.Thread(target=job, daemon=True).start())
        self._window_days = window_days
        self._lock = threading.Lock()
        self._state = _HouseState()

    def ensure(self) -> None:
        with self._lock:
            fresh = self._state.started and self._state.built_at + TTL["house_index"] > self._clock()
            if fresh or self._state.running:
                return
            self._state.started = True
            self._state.running = True
        self._spawn(self._run)

    def _run(self) -> None:
        try:
            today = datetime.fromtimestamp(self._clock(), tz=ET).date()
            since = today - timedelta(days=self._window_days)
            filings: list[house.HouseFiling] = []
            for year in sorted({since.year, today.year}):
                payload = self._http.get_bytes(house.INDEX_URL.format(year=year), accept="application/zip")
                filings.extend(house.parse_filing_index(payload, year=year))
            ptrs = [item for item in house.periodic_transaction_reports(filings) if item.filing_date >= since]
            with self._lock:
                self._state.filings = ptrs[:MAX_PTR_DOCUMENTS]
                self._state.index_error = None
                self._state.index_fetched_at = _iso(datetime.fromtimestamp(self._clock(), tz=UTC))
                self._state.built_at = self._clock()
                pending = [item for item in self._state.filings if item.doc_id not in self._state.documents]
            for filing in pending:
                try:
                    data = self._http.get_bytes(filing.document_url, accept="application/pdf")
                    document = house.parse_ptr_pdf(filing.doc_id, data)
                    with self._lock:
                        self._state.documents[filing.doc_id] = document
                        self._state.retrieved[filing.doc_id] = _iso(datetime.fromtimestamp(self._clock(), tz=UTC)) or ""
                except PublicRecordsError as exc:
                    with self._lock:
                        self._state.doc_errors[filing.doc_id] = str(exc)
        except (PublicRecordsError, ValueError) as exc:
            with self._lock:
                self._state.index_error = str(exc) if str(exc).isupper() else "HOUSE_INDEX_UNAVAILABLE"
                self._state.built_at = self._clock() - TTL["house_index"] + 300.0  # retry in 5 minutes
        finally:
            with self._lock:
                self._state.running = False

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            state = self._state
            return {"filings": list(state.filings), "documents": dict(state.documents), "retrieved": dict(state.retrieved),
                    "doc_errors": dict(state.doc_errors), "index_error": state.index_error,
                    "index_fetched_at": state.index_fetched_at, "running": state.running, "started": state.started}


# ------------------------------------------------------------------ universe index
@dataclass(slots=True)
class _Index:
    built_at: float
    error: str | None
    by_ticker: dict[str, dict[str, Any]]     # normalized ticker → row summary
    pending: bool = False                    # the universe catalog is still loading off-request


class ScreenerParticipantService:
    def __init__(self, *, catalog: Callable[[str], tuple[list[dict[str, Any]], str | None]] = _default_catalog,
                 row_for: Callable[[str, str], dict[str, Any] | None] = _default_row,
                 sec_transport_factory: Callable[[], Any] = _default_sec_transport,
                 public_http: PublicRecordsHttp | None = None,
                 cot_query: Callable[[Any, str], list[dict[str, Any]]] = _default_cot_query,
                 house_loader: HousePtrLoader | None = None, usaspending: Any = None, lobbying: Any = None,
                 thirteen_f: Any = None, cache: BackgroundCache | None = None, clock: Callable[[], float] = time.time,
                 wait_s: float = PROVIDER_WAIT_S, env: Callable[[str], str | None] = os.environ.get) -> None:
        from ..public_records.lobbying import LobbyingClient
        from ..public_records.usaspending import UsaSpendingClient

        self._catalog = catalog
        self._row_for = row_for
        self._sec_transport_factory = sec_transport_factory
        self._sec_transport: Any = None
        self._http = public_http or PublicRecordsHttp(min_interval_s=0.25)
        self._cot_query = cot_query
        self._house = house_loader or HousePtrLoader(http=self._http, clock=clock)
        self._spending = usaspending or UsaSpendingClient(PublicRecordsHttp(min_interval_s=0.5))
        self._lda = lobbying or LobbyingClient()
        self._thirteen_f = thirteen_f
        self._cache = cache or BackgroundCache(clock=clock)
        self._clock = clock
        self._wait_s = wait_s
        self._env = env
        self._lock = threading.Lock()
        self._indexes: dict[str, tuple[str, _Index]] = {}
        self._documents: dict[str, Any] = {}          # accession → parsed SEC document (immutable)
        self._tickers: tuple[float, dict[str, str]] | None = None
        self.provider_requests: Counter[str] = Counter()

    # -------------------------------------------------------------- clocks & gates
    def _now(self) -> datetime:
        return datetime.fromtimestamp(self._clock(), tz=UTC)

    def _today(self) -> date:
        return self._now().astimezone(ET).date()

    def _sec_state(self) -> tuple[str, str | None]:
        if (self._env("IMP_EDGAR_LIVE") or "") != "1":
            return "LIVE_DISABLED", "IMP_EDGAR_LIVE_NOT_SET"
        agent = (self._env("SEC_USER_AGENT") or "").strip()
        if not agent or "@" not in agent or " " not in agent:
            return "NOT_CONFIGURED", "SEC_USER_AGENT_NOT_SET"
        return "CURRENT", None

    def _public_state(self) -> tuple[str, str | None]:
        return public_live_state(self._env)

    def _await(self, key: tuple[Any, ...], job: Callable[[], Any], ttl_s: float) -> Any:
        entry = self._cache.get(key, job, ttl_s=ttl_s)
        deadline = time.monotonic() + self._wait_s
        while entry is None and time.monotonic() < deadline:
            time.sleep(0.05)
            entry = self._cache.get(key, job, ttl_s=ttl_s)
        return entry

    def _sec(self) -> Any:
        if self._sec_transport is None:
            self._sec_transport = self._sec_transport_factory()
        return self._sec_transport

    def _sec_get(self, url: str, *, immutable: bool = False) -> bytes:
        self.provider_requests["sec"] += 1
        return self._sec().get(url, immutable=immutable)

    # -------------------------------------------------------------- universe index
    def _index(self, universe: str) -> _Index:
        # The universe catalog loads off the request thread like every other source: a slow or
        # unreachable catalog provider makes a view PENDING or SOURCE_ERROR, never a hung request.
        entry = self._await(("universe_index", universe), lambda: self._catalog(universe), TTL["universe_index"])
        now = self._clock()
        if entry is None:
            return _Index(now, "UNIVERSE_INDEX_LOADING", {}, pending=True)
        if not entry.ok:
            return _Index(now, entry.reason or "UNIVERSE_INDEX_FAILED", {})
        with self._lock:
            cached = self._indexes.get(universe)
        if cached is not None and cached[0] == entry.fetched_at:
            return cached[1]
        rows, error = entry.value
        by_ticker: dict[str, dict[str, Any]] = {}
        for row in rows:
            symbol = str(row.get("symbol") or "")
            instrument_id = str((row.get("instrument") or {}).get("instrument_id") or row.get("instrument_id") or "")
            if symbol and instrument_id:
                by_ticker.setdefault(_norm_ticker(symbol), {"instrument_id": instrument_id, "symbol": symbol,
                                                            "company": row.get("company"), "root": row.get("root")})
        index = _Index(now, error, by_ticker)
        with self._lock:
            self._indexes[universe] = (entry.fetched_at, index)
        return index

    @staticmethod
    def _index_override(index: _Index) -> tuple[str, str] | None:
        """A universe view cannot match anything without its catalog: that is a source state, not "no disclosures"."""
        if index.pending:
            return "PENDING", "UNIVERSE_INDEX_LOADING"
        if index.error and not index.by_ticker:
            return "SOURCE_ERROR", index.error
        return None

    def _ticker_ciks(self) -> dict[str, str]:
        """SEC ``company_tickers.json``: ticker → zero-padded CIK (24 h)."""

        now = self._clock()
        with self._lock:
            cached = self._tickers
        if cached is not None and cached[0] > now:
            return cached[1]
        import json

        body = self._sec_get("https://www.sec.gov/files/company_tickers.json")
        payload = json.loads(body.decode("utf-8"))
        mapping = {_norm_ticker(str(row.get("ticker"))): str(row.get("cik_str", "")).zfill(10)
                   for row in (payload.values() if isinstance(payload, dict) else payload) if isinstance(row, dict)}
        with self._lock:
            self._tickers = (now + 24 * 3600.0, mapping)
        return mapping

    # ============================================================== views
    def views(self, universe: str) -> list[str]:
        return list(VIEWS.get(universe, ()))

    # -------------------------------------------------------------- ownership view (US Equities)
    def _daily_index(self, day: date) -> Any:
        def job() -> list[sec_ownership.IndexEntry]:
            quarter = (day.month - 1) // 3 + 1
            url = f"https://www.sec.gov/Archives/edgar/daily-index/{day.year}/QTR{quarter}/form.{day:%Y%m%d}.idx"
            try:
                body = self._sec_get(url, immutable=day < self._today())
            except OSError as exc:
                if "SEC_HTTP_404" in str(exc) or "SEC_HTTP_403" in str(exc):
                    return []  # no index for the day (weekend/holiday or not yet published)
                raise
            forms = frozenset().union(*OWNERSHIP_FAMILIES.values())
            return sec_ownership.parse_daily_form_index(body.decode("latin-1"), forms=forms)

        ttl = TTL["sec_index_today"] if day >= self._today() else TTL["sec_index_past"]
        return self._await(("sec_index", day.isoformat()), job, ttl)

    @staticmethod
    def _business_days(end: date, count: int) -> list[date]:
        days, cursor = [], end
        while len(days) < count:
            if cursor.weekday() < 5:
                days.append(cursor)
            cursor -= timedelta(days=1)
        return days

    def ownership_view(self, *, universe: str, window: str = "5d", family: str | None = None, sort: str = "latest",
                       offset: int = 0, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        self._validate_view(universe, "ownership")
        if window not in OWNERSHIP_WINDOWS:
            raise ValueError("INVALID_WINDOW")
        if family is not None and family not in OWNERSHIP_FAMILIES:
            raise ValueError("INVALID_FAMILY")
        if sort not in ("latest", "symbol"):
            raise ValueError("INVALID_SORT")
        self._validate_page(offset, limit)
        now = self._now()
        state, reason = self._sec_state()
        base = {"schema_version": SCHEMA_VERSION, "generated_at": _iso(now), "universe": universe, "view": "ownership",
                "window": {"id": window, "business_days": OWNERSHIP_WINDOWS[window]},
                "sorts": [{"id": "latest", "label": "Latest filed"}, {"id": "symbol", "label": "Symbol"}], "sort": sort,
                "families": [{"id": key, "label": label} for key, label in (
                    ("INSIDER", "Insider (Form 4)"), ("BENEFICIAL_13D", "Beneficial owner 13D"),
                    ("BENEFICIAL_13G", "Beneficial owner 13G"))],
                "applied": {"family": family}, "boundaries": list(EVIDENCE_BOUNDARIES),
                "time_note": ("Filing date from the EDGAR daily form index (date only; the index carries no acceptance "
                              "time). The transaction or event date is inside each document.")}
        if state != "CURRENT":
            return {**base, "state": state, "reason": reason, "providers": [provider("sec_daily_index", state, reason, scope="UNIVERSE")],
                    "rows": [], "result_count": 0, "offset": offset, "limit": limit, "has_more": False, "coverage": None}
        index = self._index(universe)
        try:
            ciks = self._ticker_ciks()
        except OSError as exc:
            code = "SEC_UNREACHABLE" if "UNREACHABLE" in str(exc) else "SOURCE_ERROR"
            return {**base, "state": "SOURCE_ERROR", "reason": code,
                    "providers": [provider("sec_daily_index", "SOURCE_ERROR", code, scope="UNIVERSE")], "rows": [],
                    "result_count": 0, "offset": offset, "limit": limit, "has_more": False, "coverage": None}
        issuers: dict[str, dict[str, Any]] = {}
        for ticker, summary in index.by_ticker.items():
            cik = ciks.get(ticker)
            if cik:
                issuers.setdefault(cik, summary)
        entries: list[sec_ownership.IndexEntry] = []
        pending = errors = 0
        days = self._business_days(self._today(), OWNERSHIP_WINDOWS[window])
        fetched = []
        for day in days:
            entry = self._daily_index(day)
            if entry is None:
                pending += 1
            elif not entry.ok:
                errors += 1
            else:
                entries.extend(entry.value)
                fetched.append(entry.fetched_at)
        grouped = sec_ownership.group_index_filings(entries, issuers, listed_ciks=set(ciks.values()))
        rows = []
        for item in grouped:
            fam = next((key for key, forms in OWNERSHIP_FAMILIES.items() if item["form_type"] in forms), None)
            if fam is None:
                continue
            summary = issuers[item["issuer_cik"]]
            rows.append({
                "accession": item["accession"], "form_type": item["form_type"], "family": fam,
                "is_amendment": item["form_type"].endswith("/A"), "filed_date": item["date_filed"].isoformat(),
                "instrument": {"instrument_id": summary["instrument_id"], "symbol": summary["symbol"]},
                "issuer_name": item["issuer_name"], "issuer_cik": item["issuer_cik"], "filers": item["filers"][:6],
                "filer_count": len(item["filers"]),
                "match": {"basis": "SEC_CIK", "confidence": "MATCH_EXACT" if item["role_basis"] == "SINGLE_CANDIDATE"
                          else "ROLE_UNVERIFIED", "role_basis": item["role_basis"]},
                "source_url": sec_ownership.filing_index_url(item["issuer_cik"], item["accession"]),
                "class": "OBSERVED",
            })
        counts = Counter(row["family"] for row in rows)
        if family:
            rows = [row for row in rows if row["family"] == family]
        rows.sort(key=(lambda row: (row["instrument"]["symbol"], row["filed_date"])) if sort == "symbol"
                  else (lambda row: (row["filed_date"], row["accession"])), reverse=sort != "symbol")
        page = rows[offset:offset + limit]
        view_state = ("PENDING" if pending and not fetched else "PARTIAL" if pending or errors else "CURRENT_AS_FILED")
        view_reason = "INDEX_LOADING" if pending else "SOME_DAILY_INDEXES_FAILED" if errors else None
        if view_state == "CURRENT_AS_FILED" and not rows:
            view_state, view_reason = "NO_DISCLOSURES", "NO_OWNERSHIP_FILINGS_IN_WINDOW"
        if (override := self._index_override(index)) is not None:
            view_state, view_reason = override
        return {**base, "state": view_state, "reason": view_reason,
                "providers": [provider("sec_daily_index", view_state if view_state in ("PENDING", "PARTIAL") else "CURRENT_AS_FILED",
                                       view_reason,
                                       fetched_at=max(fetched) if fetched else None, items=len(entries), scope="UNIVERSE")],
                "family_counts": dict(counts), "rows": page, "result_count": len(rows), "offset": offset, "limit": limit,
                "has_more": offset + limit < len(rows),
                "coverage": {"days": [day.isoformat() for day in days], "universe_instruments": len(index.by_ticker),
                             "instruments_with_cik": len(issuers), "index_error": index.error}}

    # -------------------------------------------------------------- positioning view (Futures)
    def _cot(self) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
        state, reason = self._public_state()
        if state != "CURRENT":
            return {}, provider("cftc_cot", state, reason, scope="UNIVERSE")
        since = self._today() - timedelta(days=35)
        out: dict[str, list[dict[str, Any]]] = {}
        fetched, errors, pending = [], [], False
        for family, dataset in DATASETS.items():
            codes = [market.code for market in POSITIONING_MARKETS.values() if market.report == family]

            def job(dataset: Any = dataset, codes: list[str] = codes) -> list[dict[str, Any]]:
                self.provider_requests["cftc"] += 1
                return self._cot_query(dataset, where_clause(codes, since))

            entry = self._await(("cot", family.value, since.isoformat()), job, TTL["cot"])
            if entry is None:
                pending = True
            elif not entry.ok:
                errors.append(entry.reason)
            else:
                out[family.value] = entry.value
                fetched.append(entry.fetched_at)
        if pending and not fetched:
            return out, provider("cftc_cot", "PENDING", "FETCHING", scope="UNIVERSE")
        if errors and not fetched:
            return out, provider("cftc_cot", "SOURCE_ERROR", errors[0], scope="UNIVERSE")
        return out, provider("cftc_cot", "PARTIAL" if errors or pending else "PUBLICATION_CURRENT",
                             errors[0] if errors else None, fetched_at=max(fetched), scope="UNIVERSE",
                             items=sum(len(rows) for rows in out.values()))

    def _positioning_for_root(self, root: str, cot: dict[str, list[dict[str, Any]]]) -> dict[str, Any] | None:
        market = POSITIONING_MARKETS.get(root.upper())
        if market is None:
            return None
        return build_positioning(cot.get(market.report.value, []), market, now=self._now())

    def positioning_view(self, *, universe: str) -> dict[str, Any]:
        self._validate_view(universe, "positioning")
        now = self._now()
        index = self._index(universe)
        roots = sorted({str(item.get("root") or "").upper() for item in index.by_ticker.values() if item.get("root")})
        cot, status = self._cot()
        groups: dict[str, list[dict[str, Any]]] = {"TFF": [], "DISAGGREGATED": []}
        unmapped = []
        for root in roots:
            market = POSITIONING_MARKETS.get(root)
            if market is None:
                unmapped.append(root)
                continue
            report = self._positioning_for_root(root, cot)
            if report is not None:
                groups[market.report.value].append(report)
        state = status["state"]
        if state in ("PUBLICATION_CURRENT", "PARTIAL") and not any(groups.values()):
            state = "NO_DISCLOSURES"
        reason = status["reason"] or ("SOME_ROOTS_NOT_MAPPED_TO_A_CFTC_MARKET" if unmapped else None)
        state = "PARTIAL" if state == "PUBLICATION_CURRENT" and unmapped else state
        if (override := self._index_override(index)) is not None:
            state, reason = override
        return {"schema_version": SCHEMA_VERSION, "generated_at": _iso(now), "universe": universe, "view": "positioning",
                "state": state, "reason": reason,
                "providers": [status],
                "groups": [{"report": "TFF", "label": "Traders in Financial Futures (futures only)", "rows": groups["TFF"]},
                           {"report": "DISAGGREGATED", "label": "Disaggregated (futures only)",
                            "rows": groups["DISAGGREGATED"]}],
                "coverage": {"universe_roots": len(roots), "mapped_roots": len(roots) - len(unmapped),
                             "unmapped_roots": unmapped},
                "boundaries": [EVIDENCE_BOUNDARIES[4]],
                "time_note": "Positions as of the report date (Tuesday); public from the official release time."}

    # -------------------------------------------------------------- Congress view
    def _house_transactions(self) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
        """All parsed transactions in the loaded window, plus provider status and coverage."""

        state, reason = self._public_state()
        if state != "CURRENT":
            return [], provider("house_ptr", state, reason, scope="UNIVERSE"), {}
        self._house.ensure()
        snap = self._house.snapshot()
        if snap["index_error"] and not snap["filings"]:
            return [], provider("house_ptr", "SOURCE_ERROR", snap["index_error"], scope="UNIVERSE"), {}
        if not snap["filings"] and snap["running"]:
            return [], provider("house_ptr", "PENDING", "LOADING_INDEX", scope="UNIVERSE"), {}
        rows: list[dict[str, Any]] = []
        states = Counter()
        for filing in snap["filings"]:
            document = snap["documents"].get(filing.doc_id)
            if document is None:
                states["DOCUMENT_ERROR" if filing.doc_id in snap["doc_errors"] else "LOADING"] += 1
                continue
            states[document.state] += 1
            retrieved = snap["retrieved"].get(filing.doc_id)
            available, basis = house.filing_available_at(
                filing.filing_date, retrieved_at=datetime.fromisoformat(retrieved.replace("Z", "+00:00")) if retrieved else None)
            for txn in document.transactions:
                rows.append({
                    "id": f"house:{filing.doc_id}:{txn.row_index}", "chamber": house.CHAMBER,
                    "member": {"name": filing.member_name, "state_district": filing.state_district,
                               "member_id": filing.member_id, "identity_basis": "HOUSE_INDEX_NAME_AND_DISTRICT"},
                    "owner": txn.owner, "asset_description": txn.asset_description, "asset_type_code": txn.asset_type_code,
                    "disclosed_ticker": txn.disclosed_ticker, "matchable_ticker": txn.matchable_ticker,
                    "transaction_type": txn.transaction_type, "transaction_type_code": txn.transaction_type_code,
                    "transaction_date": txn.transaction_date.isoformat() if txn.transaction_date else None,
                    "notification_date": txn.notification_date.isoformat() if txn.notification_date else None,
                    "filing_date": filing.filing_date.isoformat(), "available_at": _iso(available),
                    "available_basis": basis, "retrieved_at": retrieved,
                    "amount": txn.amount.to_dict() if txn.amount else None,
                    "disclosure_lag_days": house.disclosure_lag_days(txn.transaction_date, filing.filing_date),
                    "doc_id": filing.doc_id, "source_url": filing.document_url, "quality_flags": list(txn.quality_flags),
                })
        loading = states["LOADING"]
        status_state = "PARTIAL" if loading or states["DOCUMENT_ERROR"] else "PUBLICATION_CURRENT"
        status_reason = "LOADING_DOCUMENTS" if loading else "SOME_DOCUMENTS_FAILED" if states["DOCUMENT_ERROR"] else None
        coverage = {"filings": len(snap["filings"]), "parsed": states["PARSED"],
                    "not_machine_readable": states["TRANSACTIONS_NOT_MACHINE_READABLE"],
                    "parse_errors": states["PARSE_ERROR"], "loading": loading, "document_errors": states["DOCUMENT_ERROR"],
                    "index_fetched_at": snap["index_fetched_at"], "max_documents": MAX_PTR_DOCUMENTS}
        return rows, provider("house_ptr", status_state, status_reason, fetched_at=snap["index_fetched_at"],
                              items=len(rows), scope="UNIVERSE"), coverage

    @staticmethod
    def _senate_status(scope: str) -> dict[str, Any]:
        return {**provider("senate_efd", "NOT_CONFIGURED", SENATE_REASON, scope=scope), "source_url": SENATE_URL}

    def _match_row(self, row: dict[str, Any], universe: str, index: _Index) -> dict[str, Any] | None:
        ticker = row.get("disclosed_ticker")
        allowed = {"ST", "OP"} if universe == US_EQUITIES else {"ST", "EF"}
        if not ticker or row.get("asset_type_code") not in allowed:
            return None
        summary = index.by_ticker.get(_norm_ticker(ticker))
        if summary is None:
            return None
        return {"instrument_id": summary["instrument_id"], "symbol": summary["symbol"], "basis": "DISCLOSED_TICKER",
                "confidence": "MATCH_EXACT", "is_option": row.get("asset_type_code") == "OP"}

    def congress_view(self, *, universe: str, window: str = "60d", transaction_type: str | None = None,
                      min_amount: int | None = None, member: str | None = None, sort: str = "filed",
                      offset: int = 0, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        self._validate_view(universe, "congress")
        if window not in CONGRESS_WINDOWS:
            raise ValueError("INVALID_WINDOW")
        if transaction_type is not None and transaction_type not in CONGRESS_TYPES:
            raise ValueError("INVALID_TRANSACTION_TYPE")
        if min_amount is not None and min_amount not in AMOUNT_FLOORS:
            raise ValueError("INVALID_AMOUNT")
        if sort not in ("filed", "traded", "amount"):
            raise ValueError("INVALID_SORT")
        if member is not None and len(member) > 120:
            raise ValueError("INVALID_MEMBER")
        self._validate_page(offset, limit)
        now = self._now()
        index = self._index(universe)
        rows, status, coverage = self._house_transactions()
        since = self._today() - timedelta(days=CONGRESS_WINDOWS[window])
        in_window = [row for row in rows if row["filing_date"] >= since.isoformat()]
        matched, unmatched, outside = [], 0, 0
        for row in in_window:
            match = self._match_row(row, universe, index)
            if match is None:
                if row["disclosed_ticker"]:
                    outside += 1
                else:
                    unmatched += 1
                continue
            matched.append({**row, "instrument": match})
        members = sorted({(row["member"]["member_id"], row["member"]["name"], row["member"]["state_district"])
                          for row in matched}, key=lambda item: item[1])
        type_counts = Counter(row["transaction_type"] for row in matched)
        filtered = matched
        if transaction_type:
            filtered = [row for row in filtered if row["transaction_type"] == transaction_type]
        if min_amount is not None:
            filtered = [row for row in filtered if row["amount"] and (row["amount"]["min_amount"] or 0) >= min_amount]
        if member:
            filtered = [row for row in filtered if row["member"]["member_id"] == member]
        if sort == "traded":
            filtered.sort(key=lambda row: (row["transaction_date"] or "", row["id"]), reverse=True)
        elif sort == "amount":
            filtered.sort(key=lambda row: ((row["amount"] or {}).get("max_amount") or 10**12,
                                           (row["amount"] or {}).get("min_amount") or 0, row["filing_date"]), reverse=True)
        else:
            filtered.sort(key=lambda row: (row["filing_date"], row["id"]), reverse=True)
        page = filtered[offset:offset + limit]
        state = status["state"]
        if state == "PUBLICATION_CURRENT" and not matched:
            state = "NO_DISCLOSURES"
        reason = status["reason"] or "HOUSE_ONLY"
        state = "PARTIAL" if state == "PUBLICATION_CURRENT" else state
        if (override := self._index_override(index)) is not None:
            state, reason = override
        return {
            "schema_version": SCHEMA_VERSION, "generated_at": _iso(now), "universe": universe, "view": "congress",
            "window": {"id": window, "days": CONGRESS_WINDOWS[window], "since": since.isoformat(), "basis": "FILING_DATE"},
            "state": state, "reason": reason,
            "providers": [status, self._senate_status("UNIVERSE")],
            "sorts": [{"id": "filed", "label": "Latest filed"}, {"id": "traded", "label": "Latest transaction"},
                      {"id": "amount", "label": "Largest disclosed band"}], "sort": sort,
            "filters": {"transaction_types": [{"id": key, "count": type_counts.get(key, 0)} for key in CONGRESS_TYPES],
                        "amount_floors": list(AMOUNT_FLOORS),
                        "members": [{"id": key, "name": name, "state_district": district} for key, name, district in members],
                        "applied": {"transaction_type": transaction_type, "min_amount": min_amount, "member": member}},
            "rows": page, "result_count": len(filtered), "offset": offset, "limit": limit,
            "has_more": offset + limit < len(filtered),
            "coverage": {**coverage, "transactions_in_window": len(in_window), "matched": len(matched),
                         "ticker_outside_universe": outside, "no_disclosed_ticker": unmatched,
                         "chambers": ["HOUSE"], "universe_index_error": index.error},
            "boundaries": [EVIDENCE_BOUNDARIES[1]],
            "time_note": ("Transaction date = when the trade happened; filing date = when the report was filed; "
                          "available = the later of the end of the filing day (UTC) and IMP's first retrieval. "
                          "Disclosure lag is DERIVED (transaction → filing, calendar days)."),
            "neutrality_note": ("Disclosures are shown as filed. No member is scored, ranked, or characterized; party is "
                                "not part of the official index and is not shown."),
        }

    # ============================================================== instrument panels
    def instrument(self, *, universe: str, instrument_id: str, lens: str, compact: bool = False) -> dict[str, Any] | None:
        if universe not in UNIVERSES:
            raise ValueError("UNKNOWN_UNIVERSE")
        if lens not in (INSTITUTIONAL_PANEL, GOVERNMENT_PANEL):
            raise ValueError("INVALID_LENS")
        if lens not in UNIVERSES[universe].panels:
            raise ValueError("LENS_UNAVAILABLE_FOR_UNIVERSE")
        if not instrument_id or len(instrument_id) > 128:
            raise ValueError("INVALID_INSTRUMENT")
        row = self._row_for(instrument_id, universe)
        if row is None:
            return None
        symbol = str(row.get("symbol") or "")
        header = {"schema_version": SCHEMA_VERSION, "generated_at": _iso(self._now()), "universe": universe,
                  "lens": lens, "compact": compact,
                  "instrument": {"instrument_id": instrument_id, "symbol": symbol, "label": row.get("company") or symbol}}
        if lens == INSTITUTIONAL_PANEL:
            return {**header, **self._institutional(universe, row, compact)}
        return {**header, **self._government(universe, row, compact)}

    # -------------------------------------------------------------- institutional & whale
    def _submissions(self, cik: str) -> Any:
        def job() -> list[Any]:
            from ..sec_edgar.live import fetch_submissions

            self.provider_requests["sec"] += 1
            return list(fetch_submissions(self._sec(), cik))

        return self._await(("sec_submissions", cik), job, TTL["submissions"])

    def _sec_document(self, cik: str, filing: Any, parser: Callable[[bytes], Any]) -> tuple[Any, str | None]:
        key = filing.normalized_accession
        with self._lock:
            if key in self._documents:
                return self._documents[key], None
        try:
            name = sec_ownership.raw_xml_document(filing.primary_document)
        except ValueError:
            return None, "LEGACY_TEXT_FILING_NOT_PARSED"
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{key.replace('-', '')}/{name}"
        try:
            parsed = parser(self._sec_get(url, immutable=True))
        except (OSError, ValueError) as exc:
            return None, str(exc) if str(exc).startswith("SEC_") else "DOCUMENT_UNAVAILABLE"
        with self._lock:
            self._documents[key] = parsed
        return parsed, None

    def _ownership_documents(self, cik: str, filings: list[Any]) -> Any:
        """Parse the newest Form 4 and 13D/13G documents for one issuer (immutable per accession)."""

        form4 = [item for item in filings if item.form_type in sec_ownership.INSIDER_FORMS][:MAX_FORM4_DOCS]
        beneficial = [item for item in filings if item.form_type in sec_ownership.BENEFICIAL_FORMS
                      and not self._self_submitted(item, cik)][:MAX_13DG_DOCS]
        key = ("sec_docs", cik, tuple(item.normalized_accession for item in form4 + beneficial))

        def job() -> dict[str, Any]:
            parsed = {"form4": [], "beneficial": []}
            for filing in form4:
                document, error = self._sec_document(cik, filing, sec_ownership.parse_form4)
                parsed["form4"].append((filing, document, error))
            for filing in beneficial:
                document, error = self._sec_document(cik, filing, sec_ownership.parse_schedule_13dg)
                parsed["beneficial"].append((filing, document, error))
            return parsed

        return self._await(key, job, 24 * 3600.0)

    @staticmethod
    def _filing_clock(filing: Any) -> dict[str, Any]:
        accepted = (filing.acceptance_datetime or "").replace(".000Z", "Z") or None
        return {"filing_date": filing.filing_date or None, "accepted_at": accepted,
                "available_at": accepted or (f"{filing.filing_date}T23:59:59Z" if filing.filing_date else None),
                "available_basis": "SEC_ACCEPTANCE_TIME" if accepted else "SEC_FILING_DATE_END_OF_DAY",
                "report_date": filing.report_date or None}

    @staticmethod
    def _self_submitted(filing: Any, cik: str) -> bool:
        """A 13D/13G submitted under the company's own CIK is its stake in another issuer."""

        return filing.normalized_accession.split("-", 1)[0].lstrip("0") == cik.lstrip("0")

    @staticmethod
    def _about_issuer(document: Any, cik: str) -> bool:
        """The parsed document names ``cik`` as its subject issuer (the submissions feed also lists
        filings the company made *as a filer*, e.g. its own 13G stake in another company)."""

        issuer = str(getattr(document, "issuer_cik", "") or "").lstrip("0")
        return not issuer or issuer == cik.lstrip("0")

    def _insiders(self, parsed: list[tuple[Any, Any, str | None]], compact: bool, cik: str) -> dict[str, Any]:
        rows, errors = [], 0
        for filing, document, error in parsed:
            if document is not None and not self._about_issuer(document, cik):
                continue
            if document is None:
                errors += 1
                rows.append({"accession": filing.normalized_accession, "form_type": filing.form_type,
                             **self._filing_clock(filing), "state": "UNAVAILABLE", "reason": error,
                             "source_url": filing.archive_index_url(), "owners": [], "transactions": []})
                continue
            rows.append({
                "accession": filing.normalized_accession, "form_type": filing.form_type, **self._filing_clock(filing),
                "state": "CURRENT_AS_FILED", "reason": None, "source_url": filing.archive_index_url(),
                "owners": [{"name": owner["name"], "roles": owner["roles"], "officer_title": owner["officer_title"]}
                           for owner in document.owners],
                "rule_10b5_1": document.rule_10b5_1,
                "transactions": [{
                    "security_title": txn.security_title, "derivative": txn.derivative,
                    "transaction_date": txn.transaction_date, "code": txn.code, "code_label": txn.code_label,
                    "acquired_disposed": txn.acquired_disposed, "shares": txn.shares, "price": txn.price_per_share,
                    "shares_owned_after": txn.shares_owned_after, "ownership": txn.direct_or_indirect,
                } for txn in document.transactions][: 4 if compact else 20],
            })
        codes = Counter(txn["code"] for row in rows for txn in row["transactions"] if not txn["derivative"])
        return _section("CURRENT_AS_FILED" if rows else "NO_DISCLOSURES", None if rows else "NO_RECENT_FORM4",
                        filings=rows[: 2 if compact else MAX_FORM4_DOCS], unparsed=errors,
                        code_counts={"P": codes.get("P", 0), "S": codes.get("S", 0), "other": sum(codes.values()) - codes.get("P", 0) - codes.get("S", 0)},
                        note=("Counts of reported non-derivative transaction codes in the loaded filings (P = open-market "
                              "or private purchase, S = sale). A transaction is a disclosed fact, not a view on the stock."))

    def _beneficial(self, parsed: list[tuple[Any, Any, str | None]], compact: bool,
                    cik: str) -> tuple[dict[str, Any], list[str]]:
        rows, cusips = [], []
        for filing, document, error in parsed:
            if document is not None and not self._about_issuer(document, cik):
                continue
            if document is None:
                rows.append({"accession": filing.normalized_accession, "form_type": filing.form_type,
                             **self._filing_clock(filing), "state": "UNAVAILABLE", "reason": error,
                             "source_url": filing.archive_index_url(), "reporting_persons": []})
                continue
            cusips.extend(document.issuer_cusips)
            rows.append({
                "accession": filing.normalized_accession, "form_type": filing.form_type, "schedule": document.schedule,
                "is_amendment": document.is_amendment, **self._filing_clock(filing), "event_date": document.event_date,
                "state": "CURRENT_AS_FILED", "reason": None, "class_title": document.class_title,
                "issuer_cusips": list(document.issuer_cusips), "source_url": filing.archive_index_url(),
                "reporting_persons": [{"name": person.name, "aggregate_shares": person.aggregate_shares,
                                       "percent_of_class": person.percent_of_class, "person_types": list(person.person_types)}
                                      for person in document.reporting_persons],
                "quality_flags": list(document.quality_flags),
                "evidence_basis": "BENEFICIAL_OWNER",
            })
        section = _section("CURRENT_AS_FILED" if rows else "NO_DISCLOSURES", None if rows else "NO_RECENT_13D_13G",
                           filings=rows[: 2 if compact else MAX_13DG_DOCS],
                           note=("Percent of class and shares as reported on the cover page as of the event date. Joint "
                                 "filers often report the same shares — rows are never summed. 13G is the passive/exempt "
                                 "schedule; intent is not inferred beyond what a filing states."))
        return section, list(dict.fromkeys(cusips))

    def _large_activity(self, universe: str) -> dict[str, Any]:
        if "order_flow" not in UNIVERSES[universe].panels:
            return _section("NOT_APPLICABLE", "NO_TRADE_PRINTS_FOR_UNIVERSE")
        return _section("SEE_ORDER_FLOW", "LIVE_SUBSCRIPTION_PANEL", evidence_basis="UNKNOWN_LARGE_MARKET_ACTIVITY",
                        participant_identity="UNKNOWN",
                        method=("The Order Flow panel marks prints ≥ 10× the session's median trade size (at least 20 "
                                "trades). Print size is market activity; the counterparty is not disclosed, so it is "
                                "never attributed to an institution or read as accumulation."))

    def _thirteen_f_section(self, cusips: list[str]) -> dict[str, Any]:
        if self._thirteen_f is None:
            return _section("NOT_CONFIGURED", "THIRTEEN_F_INDEX_NOT_BUILT",
                            note=("13F holdings come from the SEC's quarterly Form 13F data sets (~100 MB per quarter); "
                                  "build the local index with tools/sec_edgar/thirteen_f_index.py to enable this section."))
        if not cusips:
            return _section("NO_MATCH", "ISSUER_CUSIP_UNKNOWN",
                            note="No issuer CUSIP is known from an official filing, so 13F lines cannot be matched exactly.")
        return self._thirteen_f.section(cusips, now=self._now())

    def _institutional(self, universe: str, row: dict[str, Any], compact: bool) -> dict[str, Any]:
        providers: list[dict[str, Any]] = []
        sections: dict[str, Any] = {}
        identity: dict[str, Any] = {"ticker": row.get("symbol"), "cik": None, "cusips": [], "cusip_basis": None}
        if universe == FUTURES:
            cot, status = self._cot()
            providers.append(status)
            root = str(row.get("root") or "").upper()
            market = POSITIONING_MARKETS.get(root)
            if market is None:
                sections["futures_positioning"] = _section("NO_MATCH", "ROOT_NOT_MAPPED_TO_A_CFTC_MARKET", root=root)
            elif status["state"] not in ("PUBLICATION_CURRENT", "PARTIAL"):
                sections["futures_positioning"] = _section(status["state"], status["reason"], root=root)
            else:
                report = self._positioning_for_root(root, cot)
                sections["futures_positioning"] = (_section("PUBLICATION_CURRENT", None, report=report, evidence_basis="CFTC_LARGE_TRADER_CONTEXT")
                                                   if report else _section("NO_DISCLOSURES", "NO_PUBLIC_REPORT_IN_WINDOW", root=root))
            sections["large_activity"] = self._large_activity(universe)
            return {"state": sections["futures_positioning"]["state"], "providers": providers, "identity": identity,
                    "sections": sections, "boundaries": [EVIDENCE_BOUNDARIES[4], EVIDENCE_BOUNDARIES[3]]}
        sec_state, sec_reason = self._sec_state()
        cusips: list[str] = []
        if universe == US_EQUITIES:
            if sec_state != "CURRENT":
                providers.append(provider("sec_ownership", sec_state, sec_reason))
                sections["beneficial_ownership"] = _section(sec_state, sec_reason)
                sections["insiders"] = _section(sec_state, sec_reason)
            else:
                try:
                    cik = self._ticker_ciks().get(_norm_ticker(row.get("symbol")))
                except OSError:
                    cik = None
                    providers.append(provider("sec_ownership", "SOURCE_ERROR", "SEC_TICKER_MAP_UNAVAILABLE"))
                if cik is None:
                    sections["beneficial_ownership"] = _section("NO_MATCH", "TICKER_NOT_IN_SEC_MAP")
                    sections["insiders"] = _section("NO_MATCH", "TICKER_NOT_IN_SEC_MAP")
                    providers.append(provider("sec_ownership", "NO_MATCH", "TICKER_NOT_IN_SEC_MAP"))
                else:
                    identity["cik"] = cik
                    entry = self._submissions(cik)
                    if entry is None:
                        providers.append(provider("sec_ownership", "PENDING", "FETCHING"))
                        sections["beneficial_ownership"] = _section("PENDING", "FETCHING")
                        sections["insiders"] = _section("PENDING", "FETCHING")
                    elif not entry.ok:
                        providers.append(provider("sec_ownership", "SOURCE_ERROR", entry.reason))
                        sections["beneficial_ownership"] = _section("SOURCE_ERROR", entry.reason)
                        sections["insiders"] = _section("SOURCE_ERROR", entry.reason)
                    else:
                        filings = entry.value
                        docs = self._ownership_documents(cik, filings)
                        if docs is None or not docs.ok:
                            reason = "FETCHING" if docs is None else docs.reason
                            state = "PENDING" if docs is None else "SOURCE_ERROR"
                            sections["beneficial_ownership"] = _section(state, reason)
                            sections["insiders"] = _section(state, reason)
                        else:
                            sections["beneficial_ownership"], cusips = self._beneficial(docs.value["beneficial"], compact, cik)
                            sections["insiders"] = self._insiders(docs.value["form4"], compact, cik)
                        providers.append(provider("sec_ownership", "CURRENT_AS_FILED", None, fetched_at=entry.fetched_at,
                                                  items=len(filings)))
                        recent = [item for item in filings
                                  if item.form_type in sec_ownership.INSIDER_FORMS
                                  or (item.form_type in sec_ownership.BENEFICIAL_FORMS and not self._self_submitted(item, cik))]
                        sections["recent_filings"] = _section(
                            "CURRENT_AS_FILED" if recent else "NO_DISCLOSURES", None,
                            filings=[{"form_type": item.form_type, "accession": item.normalized_accession,
                                      **self._filing_clock(item), "source_url": item.archive_index_url()}
                                     for item in recent[: 3 if compact else 12]])
            identity["cusips"] = cusips
            identity["cusip_basis"] = "SEC_13DG_ISSUER_CUSIP" if cusips else None
        sections["holdings_13f"] = self._thirteen_f_section(cusips)
        providers.append(provider("thirteen_f", sections["holdings_13f"]["state"], sections["holdings_13f"]["reason"]))
        sections["large_activity"] = self._large_activity(universe)
        providers.append(provider("order_flow", sections["large_activity"]["state"], sections["large_activity"]["reason"]))
        states = {section["state"] for key, section in sections.items() if key not in ("large_activity",)}
        return {"state": self._overall(states), "providers": providers, "identity": identity, "sections": sections,
                "boundaries": [EVIDENCE_BOUNDARIES[0], EVIDENCE_BOUNDARIES[3]]}

    # -------------------------------------------------------------- congress & government
    def _entity(self, row: dict[str, Any]) -> tuple[str | None, str | None]:
        from ..news.instrument_matching import _GENERIC_NAMES, entity_name

        name = entity_name(row.get("company"))
        if not name or len(name) < 4:
            return None, "NO_COMPANY_NAME"
        if len(name.split()) == 1 and name.lower() in _GENERIC_NAMES:
            return None, "ENTITY_NAME_TOO_GENERIC"
        return name, None

    def _award_jobs(self, name: str) -> list[tuple[tuple[Any, ...], Callable[[], Any], float]]:
        def job() -> dict[str, Any]:
            self.provider_requests["usaspending"] += 1
            return {"families": self._spending.recipient_transactions(name, today=self._today(), window_days=AWARD_WINDOW_DAYS)}

        def updated() -> str | None:
            self.provider_requests["usaspending"] += 1
            return self._spending.last_updated()

        return [(("usaspending", name.upper()), job, TTL["usaspending"]),
                (("usaspending_updated",), updated, TTL["usaspending_updated"])]

    def _lobbying_job(self, name: str) -> tuple[tuple[Any, ...], Callable[[], Any], float]:
        def job() -> dict[str, Any]:
            self.provider_requests["lobbying"] += 1
            filings, total = self._lda.client_filings(name, today=self._today())
            return {"filings": filings, "total": total}

        return ("lobbying", name.upper()), job, TTL["lobbying"]

    def _awards(self, name: str) -> dict[str, Any]:
        (award_key, job, award_ttl), (updated_key, updated, updated_ttl) = self._award_jobs(name)
        entry = self._await(award_key, job, award_ttl)
        stamp = self._await(updated_key, updated, updated_ttl)
        published = stamp.value if stamp is not None and stamp.ok else None
        if entry is None:
            return _section("PENDING", "FETCHING", provider=provider("usaspending", "PENDING", "FETCHING"))
        if not entry.ok:
            return _section("SOURCE_ERROR", entry.reason, provider=provider("usaspending", "SOURCE_ERROR", entry.reason))
        families = entry.value["families"]
        out = {}
        for family, page in families.items():
            rows = page["rows"]
            out[family.lower()] = {"count": len(rows), "has_more": page["has_more"], "rows": [row.to_dict() for row in rows],
                                   "recipients": sorted({row.recipient_name for row in rows}),
                                   # A sum over a truncated page would understate the window: only complete pages sum.
                                   "obligation_sum": (round(sum(row.obligation_amount or 0.0 for row in rows), 2)
                                                      if rows and not page["has_more"] else None)}
        total = sum(len(page["rows"]) for page in families.values())
        return _section("PUBLICATION_CURRENT" if total else "NO_DISCLOSURES", None if total else "NO_ACTIONS_IN_WINDOW",
                        window_days=AWARD_WINDOW_DAYS, query=name, published=published, families=out,
                        match={"basis": "USASPENDING_RECIPIENT_SEARCH", "confidence": "MATCH_ENTITY",
                               "note": "USAspending's recipient search includes parent-linked recipients; each row names its recipient."},
                        sum_note=("DERIVED: sum of the listed actions' signed obligations in the window (de-obligations "
                                  "subtract), shown only when every action in the window is listed. Not revenue, not a "
                                  "ceiling, and not comparable to company revenue without matching periods."),
                        provider=provider("usaspending", "PUBLICATION_CURRENT", None, fetched_at=entry.fetched_at,
                                          published=published, items=total))

    def _lobbying(self, name: str) -> dict[str, Any]:
        key, job, ttl = self._lobbying_job(name)
        entry = self._await(key, job, ttl)
        if entry is None:
            return _section("PENDING", "FETCHING", provider=provider("lobbying", "PENDING", "FETCHING"))
        if not entry.ok:
            return _section("SOURCE_ERROR", entry.reason, provider=provider("lobbying", "SOURCE_ERROR", entry.reason))
        filings = entry.value["filings"]
        issues = Counter(issue["label"] for filing in filings for issue in filing.issues)
        return _section("PUBLICATION_CURRENT" if filings else "NO_DISCLOSURES", None if filings else "NO_FILINGS_FOUND",
                        query=name, total_filings=entry.value["total"], clients=sorted({filing.client_name for filing in filings}),
                        filings=[filing.to_dict() for filing in filings[:12]],
                        top_issues=[{"label": label, "filings": count} for label, count in issues.most_common(8)],
                        match={"basis": "LDA_CLIENT_NAME_CONTAINS", "confidence": "MATCH_ENTITY",
                               "note": "Client names are typed by registrants; each row shows the client as filed."},
                        provider=provider("lobbying", "PUBLICATION_CURRENT", None, fetched_at=entry.fetched_at,
                                          items=len(filings)))

    def _government(self, universe: str, row: dict[str, Any], compact: bool) -> dict[str, Any]:
        providers: list[dict[str, Any]] = []
        sections: dict[str, Any] = {}
        index = self._index(universe)
        rows, status, coverage = self._house_transactions()
        providers.extend([status, self._senate_status("INSTRUMENT")])
        since = (self._today() - timedelta(days=INSTRUMENT_CONGRESS_DAYS)).isoformat()
        symbol_key = _norm_ticker(row.get("symbol"))
        matched = []
        for item in rows:
            if item["filing_date"] < since:
                continue
            match = self._match_row(item, universe, index)
            if match is not None and _norm_ticker(match["symbol"]) == symbol_key:
                matched.append({**item, "instrument": match})
        matched.sort(key=lambda item: (item["filing_date"], item["id"]), reverse=True)
        if (override := self._index_override(index)) is not None:
            sections["congressional"] = _section(*override)
        elif status["state"] in ("PUBLICATION_CURRENT", "PARTIAL"):
            congress_state = ("PARTIAL" if status["state"] == "PARTIAL" and not matched else
                              "PUBLICATION_CURRENT" if matched else "NO_DISCLOSURES")
            sections["congressional"] = _section(
                congress_state, status["reason"] if congress_state == "PARTIAL" else None if matched else "NO_DISCLOSED_TRANSACTIONS",
                window_days=INSTRUMENT_CONGRESS_DAYS, transactions=matched[: 3 if compact else 40], total=len(matched),
                chambers=["HOUSE"], coverage=coverage,
                note="House transactions whose filer disclosed this ticker. Senate eFD is not integrated (see provenance).")
        else:
            sections["congressional"] = _section(status["state"], status["reason"])
        if universe == US_EQUITIES:
            name, reason = self._entity(row)
            public_state, public_reason = self._public_state()
            if public_state != "CURRENT":
                sections["awards"] = _section(public_state, public_reason)
                sections["lobbying"] = _section(public_state, public_reason)
                providers.extend([provider("usaspending", public_state, public_reason),
                                  provider("lobbying", public_state, public_reason)])
            elif name is None:
                sections["awards"] = _section("NO_MATCH", reason)
                sections["lobbying"] = _section("NO_MATCH", reason)
            else:
                # Start every government source before waiting on any: a cold panel waits for the
                # slowest source, not the sum of them.
                jobs = self._award_jobs(name) + ([] if compact else [self._lobbying_job(name)])
                for key, job, ttl in jobs:
                    self._cache.get(key, job, ttl_s=ttl)
                sections["awards"] = self._awards(name)
                providers.append(sections["awards"].pop("provider"))
                if compact:
                    sections["lobbying"] = _section("NOT_LOADED", "COMPACT_VIEW")
                else:
                    sections["lobbying"] = self._lobbying(name)
                    providers.append(sections["lobbying"].pop("provider"))
                if compact:
                    for family in (sections["awards"].get("families") or {}).values():
                        family["rows"] = family["rows"][:2]
        states = {section["state"] for section in sections.values()}
        return {"state": self._overall(states), "providers": providers, "sections": sections,
                "boundaries": [EVIDENCE_BOUNDARIES[1], EVIDENCE_BOUNDARIES[2]],
                "neutrality_note": ("Public records are shown as filed. Nothing here ranks, scores, or characterizes a "
                                    "member of Congress, an agency, or a company's government relationships.")}

    # -------------------------------------------------------------- helpers
    @staticmethod
    def _overall(states: set[str]) -> str:
        good = states & {"CURRENT_AS_FILED", "PUBLICATION_CURRENT", "NO_DISCLOSURES", "NO_MATCH", "SEE_ORDER_FLOW",
                         "NOT_APPLICABLE", "NOT_LOADED"}
        if not states - {"NOT_APPLICABLE"}:
            return "NOT_APPLICABLE"
        if states & {"PENDING"} and not states & {"CURRENT_AS_FILED", "PUBLICATION_CURRENT"}:
            return "PENDING"
        if states <= {"LIVE_DISABLED", "NOT_CONFIGURED", "NOT_APPLICABLE", "SEE_ORDER_FLOW"}:
            return "NOT_CONFIGURED"
        if states - good:
            return "PARTIAL"
        if states & {"CURRENT_AS_FILED", "PUBLICATION_CURRENT"}:
            # Filings are current as filed; publications (COT, awards, lobbying, PTRs) as published.
            # A mix reports the narrower claim.
            return "CURRENT_AS_FILED" if "CURRENT_AS_FILED" in states else "PUBLICATION_CURRENT"
        return "NO_DISCLOSURES"

    @staticmethod
    def _validate_view(universe: str, view: str) -> None:
        if universe not in UNIVERSES:
            raise ValueError("UNKNOWN_UNIVERSE")
        if view not in VIEWS.get(universe, ()):
            raise ValueError("VIEW_UNAVAILABLE_FOR_UNIVERSE")

    @staticmethod
    def _validate_page(offset: int, limit: int) -> None:
        if not 0 <= offset <= 100_000 or not 1 <= limit <= MAX_LIMIT:
            raise ValueError("INVALID_PAGE")


_SERVICE: ScreenerParticipantService | None = None
_SERVICE_LOCK = threading.Lock()


def participant_service() -> ScreenerParticipantService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            thirteen_f = None
            path = os.environ.get("IMP_13F_INDEX_PATH", "").strip()
            if path:
                from ..sec_edgar.thirteen_f_index import ThirteenFIndex

                thirteen_f = ThirteenFIndex.load(path)
            _SERVICE = ScreenerParticipantService(thirteen_f=thirteen_f)
        return _SERVICE


__all__ = ["AMOUNT_FLOORS", "CONGRESS_WINDOWS", "EVIDENCE_BOUNDARIES", "GOVERNMENT_PANEL", "HousePtrLoader",
           "INSTITUTIONAL_PANEL", "OWNERSHIP_WINDOWS", "SCHEMA_VERSION", "ScreenerParticipantService", "VIEWS",
           "participant_service"]

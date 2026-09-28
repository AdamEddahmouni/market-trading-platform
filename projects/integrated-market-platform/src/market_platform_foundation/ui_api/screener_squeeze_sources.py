"""Publication-clock short evidence for the Screener Short Squeeze assessment (S8).

Each family keeps its own source and clock and is never merged with another:

* Reg SHO threshold lists (Nasdaq, NYSE Group, Cboe BZX) — daily official
  status/membership; not short interest and not an FTD quantity.
* FINRA consolidated short interest — twice-monthly outstanding position.
* FINRA Reg SHO daily short-sale volume — short-marked trading flow; not
  short interest.
* SEC fails-to-deliver — delayed, half-monthly aggregate balances; not proof of
  naked shorting.
* Securities lending (borrow fee / availability) — no current source exists.

Every source is opt-in through the existing ``IMP_*_LIVE`` flags and uses the
existing IMP transports and parsers. Fetches run in the background, so the
Screener endpoint never waits on a publication download: the first read of an
uncached source reports ``PENDING``. A failure is reported as the failure; it
is never a zero, never negative evidence, and never replaced by a fixture.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Callable
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
THRESHOLD_TTL_S = 3 * 3600
FINRA_TTL_S = 6 * 3600
FTD_TTL_S = 12 * 3600
FAILURE_TTL_S = 10 * 60
THRESHOLD_LOOKBACK_DAYS = 6
#: A list whose trade date is older than this is shown as stale.
THRESHOLD_STALE_DAYS = 5

# Presentation states shared with the Screener contract.
NOT_CONFIGURED = "NOT_CONFIGURED"
NOT_ENTITLED = "NOT_ENTITLED"
PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
PENDING = "PENDING"
PUBLICATION_CURRENT = "PUBLICATION_CURRENT"
STALE = "STALE"
NO_RECORD = "NO_RECORD"
PARTIAL = "PARTIAL"


def _now_iso(clock: Callable[[], float]) -> str:
    return datetime.fromtimestamp(clock(), tz=UTC).isoformat().replace("+00:00", "Z")


@dataclass
class _Entry:
    ok: bool
    value: Any
    reason: str | None
    fetched_at: str
    expires_at: float


class BackgroundCache:
    """Keyed results computed off the request thread; one job per key at a time."""

    def __init__(self, *, clock: Callable[[], float] = time.time,
                 spawn: Callable[[Callable[[], None]], None] | None = None) -> None:
        self._clock = clock
        self._spawn = spawn or (lambda job: threading.Thread(target=job, daemon=True).start())
        self._lock = threading.Lock()
        self._entries: dict[Any, _Entry] = {}
        self._running: set[Any] = set()
        self.jobs_started = 0

    def get(self, key: Any, job: Callable[[], Any], *, ttl_s: float) -> _Entry | None:
        """The cached entry (possibly expired, still shown while refreshing) or None while pending."""

        with self._lock:
            entry = self._entries.get(key)
            fresh = entry is not None and entry.expires_at > self._clock()
            if fresh or key in self._running:
                return entry
            self._running.add(key)
            self.jobs_started += 1

        def run() -> None:
            try:
                value = job()
                result = _Entry(True, value, None, _now_iso(self._clock), self._clock() + ttl_s)
            except Exception as exc:  # noqa: BLE001 — classified, never re-raised into the request
                result = _Entry(False, None, _failure_code(exc), _now_iso(self._clock), self._clock() + FAILURE_TTL_S)
            with self._lock:
                previous = self._entries.get(key)
                # A failed refresh keeps an earlier good value visible (marked by the caller).
                if result.ok or previous is None or not previous.ok:
                    self._entries[key] = result
                else:
                    previous.expires_at = result.expires_at
                    previous.reason = result.reason
                self._running.discard(key)

        self._spawn(run)
        with self._lock:
            return self._entries.get(key)


def _failure_code(exc: BaseException) -> str:
    """A stable code only: exception text can hold URLs and is never surfaced."""

    text = str(exc)
    for code in ("FINRA_CREDENTIALS_MISSING", "AUTH_UNAVAILABLE", "AUTH_FAILED", "FINRA_HTTP_401", "FINRA_HTTP_403",
                 "NASDAQ_THRESHOLD_FILE_MISSING", "SEC_FTD_DISCOVERY_EMPTY", "THRESHOLD_FILE_NOT_FOUND"):
        if code in text:
            return code
    return "SOURCE_UNAVAILABLE"


def _et_today(clock: Callable[[], float]) -> date:
    return datetime.fromtimestamp(clock(), tz=UTC).astimezone(ET).date()


def _recent_weekdays(today: date, count: int) -> list[str]:
    days: list[str] = []
    cursor = today
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor.isoformat())
        cursor -= timedelta(days=1)
    return days


# ---------------------------------------------------------------- Reg SHO lists
@dataclass(frozen=True, slots=True)
class ThresholdList:
    authority: str
    trade_date: str
    file_created_at: str
    symbols: frozenset[str]
    markets: tuple[str, ...] = ()


def _nasdaq_list(day: str) -> ThresholdList:
    from ..nasdaq_regsho.threshold import parse_threshold_file
    from ..nasdaq_regsho.transport import NasdaqTransport

    parsed = parse_threshold_file(NasdaqTransport().fetch_threshold_file(day), trade_date=day)
    return ThresholdList("NASDAQ", parsed.trade_date, parsed.file_creation_time,
                         frozenset(row["symbol"] for row in parsed.rows if row.get("reg_sho_threshold_flag") != "N"))


def _nyse_list(day: str) -> ThresholdList:
    from ..nyse_regsho.threshold import parse_threshold_file
    from ..nyse_regsho.transport import NyseTransport

    transport = NyseTransport()
    markets = transport.discover_markets()
    if not markets:
        raise OSError("SOURCE_UNAVAILABLE")
    symbols: set[str] = set()
    created = ""
    for market in markets:
        parsed = parse_threshold_file(transport.fetch_threshold_file(day, market=market), trade_date=day, source_market=market)
        symbols.update(row["symbol"] for row in parsed.rows if row.get("reg_sho_threshold_flag") != "N")
        created = max(created, parsed.file_creation_time)
    return ThresholdList("NYSE_GROUP", day, created, frozenset(symbols), tuple(markets))


def _cboe_list(day: str) -> ThresholdList:
    from ..cboe_regsho.threshold import parse_threshold_file
    from ..cboe_regsho.transport import CboeTransport

    parsed = parse_threshold_file(CboeTransport().fetch_threshold_file(day), trade_date=day)
    return ThresholdList("CBOE_BZX", parsed.trade_date, parsed.file_creation_time,
                         frozenset(row["symbol"] for row in parsed.rows))


@dataclass(frozen=True, slots=True)
class ThresholdAuthoritySource:
    authority: str
    label: str
    flag: str
    fetch: Callable[[str], ThresholdList]


THRESHOLD_AUTHORITIES: tuple[ThresholdAuthoritySource, ...] = (
    ThresholdAuthoritySource("NASDAQ", "Nasdaq", "IMP_NASDAQ_REGSHO_LIVE", _nasdaq_list),
    ThresholdAuthoritySource("NYSE_GROUP", "NYSE Group", "IMP_NYSE_REGSHO_LIVE", _nyse_list),
    ThresholdAuthoritySource("CBOE_BZX", "Cboe BZX", "IMP_CBOE_REGSHO_LIVE", _cboe_list),
)


class ThresholdLists:
    """Latest official list per authority; one download per authority per day serves every symbol."""

    def __init__(self, *, authorities: tuple[ThresholdAuthoritySource, ...] = THRESHOLD_AUTHORITIES,
                 cache: BackgroundCache | None = None, clock: Callable[[], float] = time.time,
                 env: Callable[[str], str | None] = os.environ.get) -> None:
        self._authorities = authorities
        self._cache = cache or BackgroundCache(clock=clock)
        self._clock = clock
        self._env = env

    def _latest(self, source: ThresholdAuthoritySource) -> ThresholdList:
        last: BaseException | None = None
        for day in _recent_weekdays(_et_today(self._clock), THRESHOLD_LOOKBACK_DAYS):
            try:
                return source.fetch(day)
            except (OSError, ValueError) as exc:  # a list not yet published for that date
                last = exc
        raise OSError("THRESHOLD_FILE_NOT_FOUND") from last

    def status(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.upper()
        rows: list[dict[str, Any]] = []
        for source in self._authorities:
            row: dict[str, Any] = {"sro": source.authority, "label": source.label, "trade_date": None,
                                   "file_created_at": None, "fetched_at": None, "member": None, "state": NOT_CONFIGURED,
                                   "reason": f"{source.flag}_NOT_SET"}
            if self._env(source.flag) == "1":
                entry = self._cache.get(("threshold", source.authority), lambda s=source: self._latest(s), ttl_s=THRESHOLD_TTL_S)
                if entry is None:
                    row.update(state=PENDING, reason="FETCHING_LATEST_LIST")
                elif not entry.ok:
                    row.update(state=PROVIDER_UNAVAILABLE, reason=entry.reason, fetched_at=entry.fetched_at)
                else:
                    listing: ThresholdList = entry.value
                    age = (_et_today(self._clock) - date.fromisoformat(listing.trade_date)).days
                    row.update(state=STALE if age > THRESHOLD_STALE_DAYS or entry.reason else PUBLICATION_CURRENT,
                               reason=entry.reason, trade_date=listing.trade_date, file_created_at=listing.file_created_at,
                               fetched_at=entry.fetched_at, member=symbol in listing.symbols)
            rows.append(row)
        read = [row for row in rows if row["member"] is not None]
        members = [row for row in read if row["member"]]
        if members:
            member, state = True, PUBLICATION_CURRENT
        elif read and len(read) == len(rows):
            # Absent from every exchange list retrieved for its latest date.
            member, state = False, PUBLICATION_CURRENT
        elif read:
            member, state = None, PARTIAL
        elif any(row["state"] == PENDING for row in rows):
            member, state = None, PENDING
        elif all(row["state"] == NOT_CONFIGURED for row in rows):
            member, state = None, NOT_CONFIGURED
        else:
            member, state = None, PROVIDER_UNAVAILABLE
        if any(row["state"] == STALE for row in read) and state == PUBLICATION_CURRENT:
            state = STALE
        dates = sorted({row["trade_date"] for row in read if row["trade_date"]})
        return {"state": state, "member": member, "trade_date": dates[-1] if dates else None,
                "member_of": [row["sro"] for row in members], "lists": rows}


# ---------------------------------------------------------------------- FINRA
def _symbol_map(symbol: str) -> Any:
    from ..short_intelligence.identity import SymbolMap

    return SymbolMap(({"provider_symbol": symbol, "instrument_id": symbol},))


def _finra_fetch(symbol: str) -> dict[str, Any]:
    from ..finra.live import probe_short_interest, probe_short_sale_volume, transport_from_env
    from ..finra.short_sale_volume import aggregate_short_sale_rows

    transport = transport_from_env()
    symbol_map = _symbol_map(symbol)
    interest = [row for row in probe_short_interest(transport, symbol_map, symbol) if row.provider_symbol == symbol]
    latest = max(interest, key=lambda row: (row.settlement_date, row.record_version), default=None)
    flow_rows = [row for row in probe_short_sale_volume(transport, symbol_map, symbol) if row.provider_symbol == symbol]
    flow = None
    if flow_rows:
        day = max(row.trade_report_date for row in flow_rows)
        aggregate = aggregate_short_sale_rows([row for row in flow_rows if row.trade_report_date == day])
        flow = {"trade_report_date": day, "short_sale_volume": aggregate.get("short_sale_volume"),
                "total_volume": aggregate.get("finra_reported_total_volume"),
                "short_sale_ratio": aggregate.get("finra_reported_short_sale_ratio")}
    return {
        "short_interest": None if latest is None else {
            "settlement_date": latest.settlement_date, "publication_date": latest.publication_date,
            "current": latest.current_short_position_quantity, "previous": latest.previous_short_position_quantity,
            "change": latest.short_position_delta, "change_pct": latest.short_position_pct_change,
            "days_to_cover": latest.days_to_cover_provider, "revision_flag": latest.revision_flag,
        },
        "short_sale_volume": flow,
    }


class FinraShortData:
    def __init__(self, *, cache: BackgroundCache | None = None, fetch: Callable[[str], dict[str, Any]] = _finra_fetch,
                 env: Callable[[str], str | None] = os.environ.get,
                 credentials_present: Callable[[], bool] | None = None) -> None:
        self._cache = cache or BackgroundCache()
        self._fetch = fetch
        self._env = env
        self._credentials_present = credentials_present or _finra_credentials_present

    def status(self, symbol: str) -> dict[str, Any]:
        base = {"state": NOT_CONFIGURED, "reason": None, "fetched_at": None, "short_interest": None, "short_sale_volume": None}
        if self._env("IMP_FINRA_LIVE") != "1":
            return {**base, "reason": "IMP_FINRA_LIVE_NOT_SET"}
        if not self._credentials_present():
            return {**base, "reason": "FINRA_CREDENTIALS_MISSING"}
        entry = self._cache.get(("finra", symbol.upper()), lambda: self._fetch(symbol.upper()), ttl_s=FINRA_TTL_S)
        if entry is None:
            return {**base, "state": PENDING, "reason": "FETCHING"}
        if not entry.ok:
            auth = entry.reason in ("AUTH_FAILED", "FINRA_HTTP_401", "FINRA_HTTP_403", "AUTH_UNAVAILABLE")
            return {**base, "state": NOT_ENTITLED if auth else PROVIDER_UNAVAILABLE, "reason": entry.reason,
                    "fetched_at": entry.fetched_at}
        return {**base, **entry.value, "state": STALE if entry.reason else PUBLICATION_CURRENT, "reason": entry.reason,
                "fetched_at": entry.fetched_at}


def _finra_credentials_present() -> bool:
    try:
        from ..finra.client_config import load_finra_credentials

        return load_finra_credentials().present()
    except Exception:  # noqa: BLE001 — an unreadable config is simply not configured
        return False


# ------------------------------------------------------------------------ FTD
def _ftd_fetch() -> dict[str, Any]:
    from ..local_state.paths import state_dir
    from ..sec_ftd.discovery import latest_discovered_period
    from ..sec_ftd.live import transport_from_env
    from ..sec_ftd.parser import parse_archive_bytes
    from ..sec_ftd.transport import FtdTransport

    sec = transport_from_env()
    latest = latest_discovered_period(sec)
    if latest is None:
        raise OSError("SEC_FTD_DISCOVERY_EMPTY")
    observed = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    # Archives are cached under the local state directory, never the working tree.
    capture = FtdTransport(sec, cache_root=state_dir(create=True) / "sec_ftd").fetch_archive(latest.period, retrieved_time=observed)
    parsed = parse_archive_bytes(capture.content_bytes, period_key=latest.period.period_key)
    by_symbol: dict[str, list[tuple[str, int]]] = {}
    for row in parsed.rows:
        by_symbol.setdefault(row.symbol.upper(), []).append((row.settlement_date, row.ftd_balance_quantity))
    return {"period": latest.period.period_key, "period_label": latest.period.label,
            "period_start": latest.period.source_period_start, "period_end": latest.period.source_period_end,
            "by_symbol": {symbol: sorted(values) for symbol, values in by_symbol.items()}}


class SecFailsToDeliver:
    def __init__(self, *, cache: BackgroundCache | None = None, fetch: Callable[[], dict[str, Any]] = _ftd_fetch,
                 env: Callable[[str], str | None] = os.environ.get) -> None:
        self._cache = cache or BackgroundCache()
        self._fetch = fetch
        self._env = env

    def status(self, symbol: str) -> dict[str, Any]:
        base = {"state": NOT_CONFIGURED, "reason": None, "fetched_at": None, "period": None, "period_label": None,
                "period_end": None, "settlement_date": None, "balance": None, "settlement_days_with_fails": None}
        if self._env("IMP_SEC_FTD_LIVE") != "1":
            return {**base, "reason": "IMP_SEC_FTD_LIVE_NOT_SET"}
        if not (self._env("SEC_USER_AGENT") or "").strip():
            return {**base, "reason": "SEC_USER_AGENT_NOT_SET"}
        entry = self._cache.get(("ftd",), self._fetch, ttl_s=FTD_TTL_S)
        if entry is None:
            return {**base, "state": PENDING, "reason": "FETCHING"}
        if not entry.ok:
            return {**base, "state": PROVIDER_UNAVAILABLE, "reason": entry.reason, "fetched_at": entry.fetched_at}
        value = entry.value
        rows = value["by_symbol"].get(symbol.upper()) or []
        common = {"fetched_at": entry.fetched_at, "period": value["period"], "period_label": value["period_label"],
                  "period_end": value.get("period_end")}
        if not rows:
            # The SEC file lists reported balances only: absence is "no record", not a zero balance.
            return {**base, **common, "state": NO_RECORD, "reason": "NO_FTD_RECORD_IN_PERIOD"}
        settlement, balance = rows[-1]
        return {**base, **common, "state": STALE if entry.reason else PUBLICATION_CURRENT, "reason": entry.reason,
                "settlement_date": settlement, "balance": balance, "settlement_days_with_fails": len(rows)}


# -------------------------------------------------------------------- lending
def lending_status(symbol: str) -> dict[str, Any]:
    """No current securities-lending provider exists in IMP (the donor's live borrow provider is an
    unimplemented stub and ``donor_bridge.lending_adapter`` reads fixtures). Missing stays missing."""

    return {"state": NOT_CONFIGURED, "reason": "NO_CURRENT_LENDING_SOURCE", "fee_pct": None, "available_shares": None,
            "provider": None, "as_of": None}


__all__ = ["BackgroundCache", "FinraShortData", "SecFailsToDeliver", "THRESHOLD_AUTHORITIES", "ThresholdAuthoritySource",
           "ThresholdList", "ThresholdLists", "lending_status"]

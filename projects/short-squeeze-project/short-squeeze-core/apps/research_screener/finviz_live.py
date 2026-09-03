"""Finviz Elite official export API adapter.

Uses the official Finviz Elite export endpoint with a legitimate API key. Does NOT:
- spoof browser TLS fingerprints
- bypass bot protection
- scrape login forms or credential-protected HTML
- execute any archived authentication-helper script

Official endpoint: https://elite.finviz.com/export/screener (CSV export)
Confirmed via Finviz api_explanation page (2026-07-09).
"""
from __future__ import annotations

import csv
import io
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import requests

FINVIZ_EXPORT_URL = "https://elite.finviz.com/export/screener"
FINVIZ_NEWS_URL = "https://elite.finviz.com/news_export.ashx"
FINVIZ_EXPORT_VERSION = "152"

FINVIZ_COLUMNS = "1,25,26,30,31,84,42,43,49,50,52,53,55,59,56,60,61,64,65,66,57,81,86,87"
DEFAULT_FILTER = "sh_float_u50,sh_price_u50"

CACHE_TTL_S = 120
SYMBOL_CACHE_TTL_S = 300
NEWS_CACHE_TTL_S = 180

HEADERS = {"User-Agent": "Mozilla/5.0"}

#: Core squeeze fields — rows missing any of these are skipped for top-N selection.
_FINVIZ_CORE_FIELDS = ("short_float_pct", "float_shares", "rel_volume")
#: Preferred fill fields used for completeness preference among eligible rows.
_FINVIZ_FILL_FIELDS = (
    "short_float_pct", "float_shares", "rel_volume", "price", "change_pct",
)


def _redact(message: object, secret: str | None) -> str:
    text = str(message)
    return text.replace(secret, "[REDACTED]") if secret else text


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def finviz_row_is_usable(row: FinvizRow) -> bool:
    """True when a row has the core short-squeeze fields needed for ranking."""
    return bool(row.ticker) and all(
        getattr(row, name) is not None for name in _FINVIZ_CORE_FIELDS
    )


def finviz_row_completeness(row: FinvizRow) -> int:
    """Count of preferred fill fields that are non-null."""
    return sum(1 for name in _FINVIZ_FILL_FIELDS if getattr(row, name) is not None)


def finviz_rank_key(row: FinvizRow) -> tuple[float, ...]:
    """Sort key for Finviz top-N: completeness, short float, rel volume, |change|.

    More negative values sort first (descending preference).
    """
    change = abs(row.change_pct) if row.change_pct is not None else 0.0
    return (
        -float(finviz_row_completeness(row)),
        -float(row.short_float_pct or 0.0),
        -float(row.rel_volume or 0.0),
        -change,
    )


def select_ranked_finviz_top_n(
    rows: list[FinvizRow] | tuple[FinvizRow, ...] | None,
    *,
    exclude: set[str] | frozenset[str] | None = None,
    limit: int = 15,
) -> list[FinvizRow]:
    """Pick up to ``limit`` usable Finviz rows not already in ``exclude``.

    Sparse rows (missing core squeeze fields) are skipped. Remaining rows are
    ranked by completeness, then short_float_pct, rel_volume, and |change_pct|.
    """
    if not rows or limit <= 0:
        return []
    skip = {symbol.upper() for symbol in (exclude or set()) if symbol}
    eligible = [
        row for row in rows
        if finviz_row_is_usable(row) and row.ticker.upper() not in skip
    ]
    eligible.sort(key=finviz_rank_key)
    return eligible[:limit]


@dataclass(slots=True)
class FinvizRow:
    ticker: str = ""
    company: str = ""
    sector: str = ""
    industry: str = ""
    country: str = ""
    price: float | None = None
    change_pct: float | None = None
    volume: int | None = None
    avg_volume: int | None = None
    rel_volume: float | None = None
    market_cap: float | None = None
    shares_outstanding: float | None = None
    float_shares: float | None = None
    short_float_pct: float | None = None
    short_ratio: float | None = None
    eps_ttm: float | None = None
    pe: float | None = None
    fwd_pe: float | None = None
    rsi_14: float | None = None
    earnings_date: str | None = None
    perf_week: float | None = None
    recommendation: str | None = None
    provider_columns: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker, "company": self.company,
            "sector": self.sector, "industry": self.industry, "country": self.country,
            "price": self.price, "change_pct": self.change_pct,
            "volume": self.volume, "avg_volume": self.avg_volume,
            "rel_volume": self.rel_volume, "market_cap": self.market_cap,
            "shares_outstanding": self.shares_outstanding,
            "float_shares": self.float_shares, "short_float_pct": self.short_float_pct,
            "short_ratio": self.short_ratio,
            "eps_ttm": self.eps_ttm, "pe": self.pe, "fwd_pe": self.fwd_pe,
            "rsi_14": self.rsi_14, "earnings_date": self.earnings_date,
            "perf_week": self.perf_week, "recommendation": self.recommendation,
            "provider_columns": list(self.provider_columns),
        }


def _parse_float(raw: str | None) -> float | None:
    if raw is None or raw.strip() in ("", "-", "N/A"):
        return None
    try:
        return float(raw.replace("%", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _parse_int(raw: str | None) -> int | None:
    if raw is None or raw.strip() in ("", "-", "N/A"):
        return None
    try:
        return int(raw.replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _parse_suffix(raw: str | None) -> float | None:
    if raw is None or raw.strip() in ("", "-", "N/A"):
        return None
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}
    try:
        value = raw.strip().upper()
        for suffix, mult in multipliers.items():
            if value.endswith(suffix):
                return float(value[:-1]) * mult
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_row(row: dict[str, str]) -> FinvizRow:
    return FinvizRow(
        ticker=(row.get("Ticker", "") or "").strip().upper(),
        company=(row.get("Company", "") or "").strip(),
        sector=(row.get("Sector", "") or "").strip(),
        industry=(row.get("Industry", "") or "").strip(),
        country=(row.get("Country", "") or "").strip(),
        price=_parse_float(row.get("Price")),
        change_pct=_parse_float(row.get("Change")),
        volume=_parse_int(row.get("Volume")),
        avg_volume=_parse_int(row.get("Average Volume")),
        rel_volume=_parse_float(row.get("Relative Volume")),
        market_cap=_parse_suffix(row.get("Market Cap.")),
        shares_outstanding=_parse_suffix(row.get("Shares Out.")),
        float_shares=_parse_suffix(row.get("Shares Float") or row.get("Float")),
        short_float_pct=_parse_float(row.get("Short Float")),
        short_ratio=_parse_float(row.get("Short Ratio")),
        eps_ttm=_parse_float(row.get("EPS ttm")),
        pe=_parse_float(row.get("P/E")),
        fwd_pe=_parse_float(row.get("Fwd P/E")),
        rsi_14=_parse_float(row.get("RSI (14)")),
        earnings_date=row.get("Earnings"),
        perf_week=_parse_float(row.get("Perf Week")),
        recommendation=row.get("Recommendation"),
        provider_columns=tuple(row),
    )


class FinvizClient:
    def __init__(self, api_key: str | None = None) -> None:
        self._cache: list[FinvizRow] | None = None
        self._cache_by_symbol: dict[str, FinvizRow] = {}
        self._cache_at: str | None = None
        self._cache_error: str | None = None
        self._cache_stale = False
        self._cache_columns: tuple[str, ...] = ()
        self._last_success_at: str | None = None
        self._last_fetch_duration_s: float | None = None
        self._last_parse_duration_s: float | None = None
        self._mapping_conflicts: tuple[str, ...] = ()
        self._news_cache: list[dict[str, Any]] | None = None
        self._news_cache_at: str | None = None
        self._lock = threading.Lock()
        self._api_key = api_key
        self._symbol_fetched_at: dict[str, float] = {}

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    @property
    def api_key(self) -> str | None:
        return self._api_key

    @property
    def cached_at(self) -> str | None:
        return self._cache_at

    def status(self) -> dict[str, Any]:
        return {
            "provider": "Finviz Elite",
            "configured": self.configured,
            "cached": self._cache is not None,
            "cached_at": self._cache_at,
            "last_error": self._cache_error,
            "row_count": len(self._cache) if self._cache else 0,
            "stale": self._cache_stale,
            "ttl_seconds": CACHE_TTL_S,
            "columns": list(self._cache_columns),
            "last_success_at": self._last_success_at,
            "last_fetch_duration_s": self._last_fetch_duration_s,
            "last_parse_duration_s": self._last_parse_duration_s,
            "mapping_conflict_symbols": list(self._mapping_conflicts),
            "symbol_cache_size": len(self._cache_by_symbol),
        }

    def _export_csv(self, *, filter_expr: str) -> tuple[list[FinvizRow], str | None]:
        api_key = self.api_key
        if not api_key:
            return [], "FINVIZ_API_KEY not configured"
        resp = requests.get(
            FINVIZ_EXPORT_URL,
            params={
                "v": FINVIZ_EXPORT_VERSION,
                "f": filter_expr,
                "c": FINVIZ_COLUMNS,
                "auth": api_key,
            },
            headers=HEADERS,
            timeout=15,
        )
        if resp.status_code != 200:
            return [], _redact(f"HTTP {resp.status_code}: {resp.text[:200]}", api_key)
        text = resp.text or ""
        lowered = text[:10_000].lower()
        if "<html" in lowered or ("<form" in lowered and "login" in lowered):
            return [], "FINVIZ_EXPORT_LOGIN_PAGE"
        reader = csv.DictReader(io.StringIO(text))
        rows = [_parse_row(castdict(r)) for r in reader if r.get("Ticker")]
        if "Ticker" not in tuple(reader.fieldnames or ()):
            return [], "FINVIZ_EXPORT_NOT_CSV"
        return rows, None

    def _store_symbol_row(self, row: FinvizRow) -> None:
        if not row.ticker:
            return
        symbol = row.ticker.upper()
        self._cache_by_symbol[symbol] = row
        self._symbol_fetched_at[symbol] = time.time()
        if self._cache is None:
            self._cache = [row]
        elif not any(existing.ticker == symbol for existing in self._cache):
            self._cache.append(row)

    def fetch_symbol(self, symbol: str, *, force: bool = False) -> dict[str, Any]:
        """On-demand Elite export for one ticker (``f=t=SYMBOL``)."""
        needle = symbol.strip().upper()
        if not needle:
            return {"success": False, "symbol": needle, "error": "empty symbol"}
        with self._lock:
            now = time.time()
            cached = self._cache_by_symbol.get(needle)
            fetched_at = self._symbol_fetched_at.get(needle, 0.0)
            if (
                not force
                and cached is not None
                and (now - fetched_at) < SYMBOL_CACHE_TTL_S
            ):
                return {
                    "success": True,
                    "symbol": needle,
                    "fresh": False,
                    "row": cached.as_dict(),
                    "error": None,
                }
            rows, error = self._export_csv(filter_expr=f"t={needle}")
            if error:
                return {"success": False, "symbol": needle, "error": error}
            match = next((row for row in rows if row.ticker == needle), None)
            if match is None and rows:
                match = rows[0]
            if match is None:
                return {
                    "success": False,
                    "symbol": needle,
                    "error": "FINVIZ_SYMBOL_NOT_IN_EXPORT",
                }
            self._store_symbol_row(match)
            self._last_success_at = _now()
            return {
                "success": True,
                "symbol": needle,
                "fresh": True,
                "row": match.as_dict(),
                "error": None,
            }

    def ensure_symbols(
        self, symbols: list[str], *, force: bool = False
    ) -> dict[str, Any]:
        """Fill cache gaps for screen symbols not present in the bulk screener."""
        missing = []
        for symbol in symbols:
            needle = symbol.strip().upper()
            if not needle:
                continue
            if needle in self._cache_by_symbol and not force:
                fetched_at = self._symbol_fetched_at.get(needle, 0.0)
                if (time.time() - fetched_at) < SYMBOL_CACHE_TTL_S:
                    continue
            missing.append(needle)
        fetched = 0
        errors: list[str] = []
        for symbol in missing:
            result = self.fetch_symbol(symbol, force=force)
            if result.get("success"):
                fetched += 1
            elif result.get("error"):
                errors.append(f"{symbol}:{result['error']}")
        return {
            "requested": len(symbols),
            "missing_before": len(missing),
            "fetched": fetched,
            "errors": errors[:10],
        }

    def _failure(self, error: str) -> dict[str, Any]:
        self._cache_error = error
        self._cache_stale = self._cache is not None
        return {
            "success": False,
            "fresh": False,
            "stale": self._cache_stale,
            "rows": len(self._cache) if self._cache else 0,
            "retained_last_good": self._cache is not None,
            "retrieved_at": self._cache_at,
            "error": error,
        }

    def fetch_screener(self, force: bool = False) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            if (
                not force
                and self._cache is not None
                and self._cache_at
                and (now - _parse_epoch(self._cache_at)) < CACHE_TTL_S
            ):
                return {
                    "success": True, "fresh": False, "rows": len(self._cache),
                    "stale": False, "retained_last_good": False,
                    "mapping_conflicts": len(self._mapping_conflicts),
                    "retrieved_at": self._cache_at, "error": None,
                }
            api_key = self.api_key
            if not api_key:
                return self._failure("FINVIZ_API_KEY not configured")
            try:
                fetch_started = time.perf_counter()
                resp = requests.get(
                    FINVIZ_EXPORT_URL,
                    params={
                        "v": FINVIZ_EXPORT_VERSION, "f": DEFAULT_FILTER,
                        "c": FINVIZ_COLUMNS, "auth": api_key,
                    },
                    headers=HEADERS, timeout=15,
                )
                self._last_fetch_duration_s = time.perf_counter() - fetch_started
                if resp.status_code != 200:
                    return self._failure(_redact(
                        f"HTTP {resp.status_code}: {resp.text[:200]}", api_key,
                    ))
                text = resp.text or ""
                lowered = text[:10_000].lower()
                if "<html" in lowered or "<form" in lowered and "login" in lowered:
                    return self._failure("FINVIZ_EXPORT_LOGIN_PAGE")
                parse_started = time.perf_counter()
                reader = csv.DictReader(io.StringIO(resp.text))
                rows = [_parse_row(castdict(r)) for r in reader if r.get("Ticker")]
                columns = tuple(reader.fieldnames or ())
                self._last_parse_duration_s = time.perf_counter() - parse_started
                if "Ticker" not in columns:
                    return self._failure("FINVIZ_EXPORT_NOT_CSV")
                if not rows:
                    return self._failure("FINVIZ_EXPORT_EMPTY")
                symbol_counts = Counter(row.ticker for row in rows)
                self._mapping_conflicts = tuple(sorted(
                    symbol for symbol, count in symbol_counts.items() if count > 1
                ))
                by_symbol = {
                    row.ticker: row for row in rows
                    if symbol_counts[row.ticker] == 1
                }
                # Replace both lookup structures only after the whole response validates.
                self._cache = rows
                self._cache_by_symbol = by_symbol
                self._cache_columns = columns
                self._cache_at = _now()
                self._last_success_at = self._cache_at
                self._cache_error = None
                self._cache_stale = False
                return {"success": True, "fresh": True, "stale": False,
                        "retained_last_good": False, "rows": len(rows),
                        "mapping_conflicts": len(self._mapping_conflicts),
                        "retrieved_at": self._cache_at, "error": None}
            except Exception as exc:
                return self._failure(
                    _redact(f"{type(exc).__name__}: {exc}", api_key)
                )

    def get_row(self, symbol: str) -> FinvizRow | None:
        needle = symbol.strip().upper()
        # Mapping conflicts are ambiguous — withhold rather than guessing.
        if needle in self._mapping_conflicts:
            return None
        row = self._cache_by_symbol.get(needle)
        if row is not None:
            return row
        if self.configured:
            result = self.fetch_symbol(needle)
            if result.get("success"):
                return self._cache_by_symbol.get(needle)
        return None

    def get_cached_rows(self) -> list[FinvizRow]:
        if not self._cache:
            return []
        conflicts = set(self._mapping_conflicts)
        if not conflicts:
            return list(self._cache)
        return [row for row in self._cache if row.ticker not in conflicts]

    def fetch_news(self, force: bool = False) -> dict[str, Any]:
        with self._lock:
            now = time.time()
            if (
                not force
                and self._news_cache is not None
                and self._news_cache_at
                and (now - _parse_epoch(self._news_cache_at)) < NEWS_CACHE_TTL_S
            ):
                return {"success": True, "fresh": False,
                        "count": len(self._news_cache), "error": None}
            api_key = self.api_key
            if not api_key:
                return {"success": False, "fresh": False, "count": 0,
                        "error": "FINVIZ_API_KEY not configured"}
            try:
                resp = requests.get(
                    FINVIZ_NEWS_URL,
                    params={"v": 3, "auth": api_key},
                    headers=HEADERS, timeout=15,
                )
                resp.raise_for_status()
                reader = csv.DictReader(io.StringIO(resp.text))
                headlines = []
                for row in reader:
                    tickers_raw = (row.get("Ticker", "") or "").strip()
                    tickers = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]
                    headlines.append({
                        "headline": row.get("Title", ""),
                        "timestamp": _normalize_finviz_news_timestamp(row.get("Date", "")),
                        "url": row.get("Url", ""),
                        "tickers": tickers,
                        "provider": "Finviz Elite",
                        "provider_news_id": f"finviz:{row.get('Title','')[:80]}",
                    })
                self._news_cache = headlines
                self._news_cache_at = _now()
                return {"success": True, "fresh": True,
                        "count": len(headlines), "error": None}
            except Exception as exc:
                return {"success": False, "fresh": False, "count": 0,
                        "error": _redact(f"{type(exc).__name__}: {exc}", api_key)}

    def get_news_for(self, symbol: str) -> list[dict[str, Any]]:
        if self._news_cache is None:
            return []
        needle = symbol.strip().upper()
        return [h for h in self._news_cache if needle in h.get("tickers", [])]


def _normalize_finviz_news_timestamp(raw: str | None) -> str:
    if not raw:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError):
        pass
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
        "%b-%d-%y %I:%M%p",
        "%b-%d-%y",
        "%b-%d-%Y %I:%M%p",
        "%b-%d-%Y",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            return parsed.isoformat().replace("+00:00", "Z")
        except ValueError:
            continue
    return text


def _parse_epoch(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return 0.0


def castdict(entries: dict[str, str]) -> dict[str, str]:
    return dict(entries)


_FINVIZ: FinvizClient | None = None
_FV_LOCK = threading.Lock()


def get_finviz_client() -> FinvizClient:
    global _FINVIZ
    with _FV_LOCK:
        if _FINVIZ is None:
            _FINVIZ = FinvizClient()
        return _FINVIZ

"""Finviz screener CSV parse and normalization."""

from __future__ import annotations

import csv
import hashlib
import io
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .config import (
    DEFAULT_SCREENER_COLUMNS,
    FINVIZ_EXPORT_URL,
    FINVIZ_EXPORT_VERSION,
    SCREENER_CACHE_TTL_S,
    SYMBOL_CACHE_TTL_S,
    finviz_api_key,
)
from .request_manager import FinvizRequestManager, RequestPriority, get_finviz_request_manager, redact_text
from .symbols import finviz_to_canonical


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_float(raw: str | None) -> float | None:
    if raw is None or str(raw).strip() in ("", "-", "N/A"):
        return None
    try:
        return float(str(raw).replace("%", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _parse_int(raw: str | None) -> int | None:
    if raw is None or str(raw).strip() in ("", "-", "N/A"):
        return None
    try:
        return int(str(raw).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def _parse_suffix(raw: str | None) -> float | None:
    if raw is None or str(raw).strip() in ("", "-", "N/A"):
        return None
    multipliers = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}
    try:
        value = str(raw).strip().upper()
        for suffix, mult in multipliers.items():
            if value.endswith(suffix):
                return float(value[:-1]) * mult
        return float(value)
    except (ValueError, TypeError):
        return None


@dataclass(slots=True)
class FinvizScreenerRow:
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
    raw_fields: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "company": self.company,
            "sector": self.sector,
            "industry": self.industry,
            "country": self.country,
            "price": self.price,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "avg_volume": self.avg_volume,
            "rel_volume": self.rel_volume,
            "market_cap": self.market_cap,
            "shares_outstanding": self.shares_outstanding,
            "float_shares": self.float_shares,
            "short_float_pct": self.short_float_pct,
            "short_ratio": self.short_ratio,
            "eps_ttm": self.eps_ttm,
            "pe": self.pe,
            "fwd_pe": self.fwd_pe,
            "rsi_14": self.rsi_14,
            "earnings_date": self.earnings_date,
            "perf_week": self.perf_week,
            "recommendation": self.recommendation,
            "provider_columns": list(self.provider_columns),
            "raw_fields": dict(self.raw_fields),
        }

    def canonical_metrics(self) -> dict[str, Any]:
        return {
            "price": self.price,
            "change_pct": self.change_pct,
            "rel_volume": self.rel_volume,
            "short_float_pct": self.short_float_pct,
            "short_ratio": self.short_ratio,
            "float_shares": self.float_shares,
            "market_cap": self.market_cap,
            "volume": self.volume,
            "avg_volume": self.avg_volume,
            "rsi_14": self.rsi_14,
            "perf_week": self.perf_week,
        }


def parse_screener_csv(text: str) -> tuple[list[FinvizScreenerRow], tuple[str, ...], str | None]:
    lowered = text[:10_000].lower()
    if "<html" in lowered or ("<form" in lowered and "login" in lowered):
        return [], (), "FINVIZ_EXPORT_LOGIN_PAGE"
    reader = csv.DictReader(io.StringIO(text))
    columns = tuple(reader.fieldnames or ())
    if "Ticker" not in columns:
        return [], columns, "FINVIZ_EXPORT_NOT_CSV"
    rows = [_parse_row(dict(r)) for r in reader if (r.get("Ticker") or "").strip()]
    if not rows:
        return [], columns, "FINVIZ_EXPORT_EMPTY"
    return rows, columns, None


def _parse_row(row: dict[str, str]) -> FinvizScreenerRow:
    return FinvizScreenerRow(
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
        raw_fields=dict(row),
    )


class FinvizScreenerClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        request_manager: FinvizRequestManager | None = None,
    ) -> None:
        self._api_key = api_key or finviz_api_key()
        self._manager = request_manager or get_finviz_request_manager()

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def fetch_export(
        self,
        *,
        filter_expr: str,
        columns: str = DEFAULT_SCREENER_COLUMNS,
        cache_ttl_s: float = SCREENER_CACHE_TTL_S,
        force: bool = False,
    ) -> dict[str, Any]:
        received_at = _utc_iso()
        received_ns = time.time_ns()
        if not self._api_key:
            return {
                "success": False,
                "error": "NOT_CONFIGURED",
                "rows": [],
                "columns": [],
                "received_at": received_at,
                "available_time_ns": received_ns,
            }
        if force:
            self._manager.clear_cache()
        params = {
            "v": FINVIZ_EXPORT_VERSION,
            "f": filter_expr,
            "c": columns,
            "auth": self._api_key,
        }
        status, body, meta = self._manager.get(
            FINVIZ_EXPORT_URL,
            params=params,
            priority=RequestPriority.DISCOVERY_REFRESH,
            cache_ttl_s=None if force else cache_ttl_s,
            api_key=self._api_key,
        )
        available_ns = time.time_ns()
        if status != 200:
            return {
                "success": False,
                "error": redact_text(f"HTTP_{status}", self._api_key),
                "rows": [],
                "columns": [],
                "received_at": received_at,
                "available_time_ns": available_ns,
                "meta": redact_text(str(meta), self._api_key),
            }
        parsed, columns, parse_error = parse_screener_csv(body)
        if parse_error:
            return {
                "success": False,
                "error": parse_error,
                "rows": [],
                "columns": list(columns),
                "received_at": received_at,
                "available_time_ns": available_ns,
            }
        return {
            "success": True,
            "error": None,
            "rows": parsed,
            "columns": list(columns),
            "received_at": received_at,
            "available_time_ns": available_ns,
            "raw_response_hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
            "meta": meta,
        }

    def fetch_symbol(self, symbol: str, *, force: bool = False) -> dict[str, Any]:
        needle = symbol.strip().upper()
        result = self.fetch_export(filter_expr=f"t={needle}", cache_ttl_s=SYMBOL_CACHE_TTL_S, force=force)
        if not result.get("success"):
            return result
        rows = result.get("rows") or []
        match = next((row for row in rows if row.ticker == needle), rows[0] if rows else None)
        if match is None:
            result["success"] = False
            result["error"] = "FINVIZ_SYMBOL_NOT_IN_EXPORT"
        else:
            mapping = finviz_to_canonical(match.ticker)
            result["row"] = match
            result["instrument_id"] = mapping.instrument_id
        return result

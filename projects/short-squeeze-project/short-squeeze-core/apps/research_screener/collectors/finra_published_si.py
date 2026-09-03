from __future__ import annotations

import csv
import io
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from squeeze_core.adapters import AdapterContext
from squeeze_core.adapters.finra import normalize_finra_short_interest_record
from squeeze_core.contracts import EntitlementState, IngestionMethod

from .base import EvidenceCollector
from .models import CollectorRecord

_SOURCE = "FinraPublishedSI"
_NOW_FMT = "%Y-%m-%dT%H:%M:%S"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _adapter_context() -> AdapterContext:
    return AdapterContext(
        ingested_at=datetime.now(tz=UTC),
        source_timezone=None,
        provider="FINRA_PUBLISHED_SHORT_INTEREST",
        adapter_version="1.0.0",
        normalization_version="finra-short-interest-v1",
        entitlement_status=EntitlementState.UNKNOWN,
        collection_method=IngestionMethod.DOWNLOADED,
        source_endpoint_name="finra-published-short-interest",
    )


def _row_to_finra_record(row: dict[str, str], line_no: int) -> dict[str, object] | None:
    symbol = (
        row.get("Symbol")
        or row.get("symbol")
        or row.get("SYMBOL")
        or row.get("Issue Name")
        or ""
    ).strip()
    if not symbol:
        return None
    short_shares = (
        row.get("Current Short Position")
        or row.get("Short Shares")
        or row.get("short_shares")
        or row.get("ShortVolume")
        or ""
    ).strip()
    settlement = (
        row.get("Settlement Date")
        or row.get("settlement_date")
        or row.get("SettlementDate")
        or ""
    ).strip()
    if not short_shares or not settlement:
        return None
    pct = row.get("short_float_percent") or row.get("Short % of Float") or ""
    return {
        "source_record_id": f"finra-si-line-{line_no}",
        "provider_schema": "FINRA_SHORT_INTEREST_V1",
        "record_type": "PUBLISHED_SHORT_INTEREST",
        "fixture_origin": "SANITIZED_REPRESENTATIVE_SAMPLE",
        "symbol": symbol.upper(),
        "short_shares": short_shares.replace(",", ""),
        "settlement_date": settlement,
        "publication_date": row.get("Publication Date") or _now(),
        "short_float_percent": pct or None,
        "short_float_percent_unit": "FORMATTED_PERCENT_STRING" if pct else None,
        "revision_status": row.get("record_status") or "ORIGINAL",
    }


def parse_finra_si_text(text: str) -> dict[str, dict[str, object]]:
    """Parse pipe- or comma-delimited FINRA short-interest shaped files."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return {}
    delimiter = "|" if "|" in lines[0] else ","
    reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
    out: dict[str, dict[str, object]] = {}
    for idx, row in enumerate(reader, start=2):
        parsed = _row_to_finra_record(row, idx)
        if parsed is None:
            continue
        symbol = str(parsed["symbol"]).upper()
        out[symbol] = parsed
    return out


class FinraPublishedSICollector(EvidenceCollector):
    name = _SOURCE

    def __init__(
        self,
        *,
        enabled: bool = True,
        data_url: str | None = None,
        fixture_path: str | None = None,
        cache_ttl_s: int = 21_600,
    ) -> None:
        self._enabled = enabled
        self._data_url = data_url
        self._fixture_path = fixture_path
        self._cache_ttl_s = cache_ttl_s
        self._index: dict[str, dict[str, object]] = {}
        self._fetched_at: float = 0.0
        self._last_error: str | None = None

    @property
    def configured(self) -> bool:
        return self._enabled and bool(self._data_url or self._fixture_path)

    @property
    def capabilities(self) -> list[str]:
        return ["published_short_interest", "finra_si_shares", "short_float"]

    def _load_file(self, *, force: bool) -> None:
        now = time.time()
        if not force and self._index and (now - self._fetched_at) < self._cache_ttl_s:
            return
        text = ""
        if self._fixture_path:
            text = Path(self._fixture_path).read_text(encoding="utf-8")
        elif self._data_url:
            response = requests.get(self._data_url, timeout=60)
            response.raise_for_status()
            text = response.text
        self._index = parse_finra_si_text(text)
        self._fetched_at = now
        self._last_error = None

    def poll(
        self, symbols: list[str], *, force: bool = False
    ) -> list[CollectorRecord]:
        if not self.configured:
            return []
        try:
            self._load_file(force=force)
        except Exception as exc:  # noqa: BLE001
            self._last_error = f"{type(exc).__name__}: {exc}"
            return []

        ctx = _adapter_context()
        received = _now()
        records: list[CollectorRecord] = []
        for symbol in symbols:
            raw = self._index.get(symbol.strip().upper())
            if raw is None:
                continue
            norm = normalize_finra_short_interest_record(raw, ctx)
            if norm.rejection is not None or not norm.observations:
                continue
            obs = norm.observations[0]
            payload = obs.payload
            shares = payload.short_shares
            pct = payload.short_float_percent
            hints: dict[str, Any] = {
                "finra_si_shares": shares,
                "published_short_interest": float(pct) if pct is not None else None,
                "research_admissibility": "RESEARCH_ADMISSIBLE",
            }
            records.append(
                CollectorRecord(
                    symbol=symbol.upper(),
                    payload={"observation_id": obs.observation_id},
                    received_at=received,
                    source_id=_SOURCE,
                    field_hints=hints,
                    dedupe_key=f"{_SOURCE}:{symbol}:{getattr(payload, 'settlement_date', '')}",
                )
            )
        return records

    @property
    def rate_limit_state(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "cached_symbols": len(self._index),
            "last_error": self._last_error,
        }


def default_finra_daily_url(for_date: datetime | None = None) -> str:
    day = (for_date or datetime.now(tz=UTC) - timedelta(days=1)).strftime("%Y%m%d")
    template = os.environ.get(
        "FINRA_DAILY_VOLUME_URL_TEMPLATE",
        "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{date}.txt",
    )
    return template.replace("{date}", day)


def parse_finra_daily_volume_text(text: str) -> dict[str, dict[str, str]]:
    """Parse FINRA daily short-sale volume file (pipe-delimited)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
    if not lines:
        return {}
    out: dict[str, dict[str, str]] = {}
    for line in lines[1:]:
        parts = line.split("|")
        if len(parts) < 3:
            continue
        date_part, symbol, short_vol = parts[0], parts[1], parts[2]
        out[symbol.strip().upper()] = {
            "trade_date": date_part.strip(),
            "short_volume": short_vol.strip(),
        }
    return out


class FinraDailyVolumeCollector(EvidenceCollector):
    name = "FinraDailyVolume"

    def __init__(
        self,
        *,
        enabled: bool = True,
        url_template: str | None = None,
        cache_ttl_s: int = 3600,
    ) -> None:
        self._enabled = enabled
        self._url_template = url_template
        self._cache_ttl_s = cache_ttl_s
        self._index: dict[str, dict[str, str]] = {}
        self._fetched_at: float = 0.0
        self._last_error: str | None = None

    @property
    def configured(self) -> bool:
        return self._enabled

    @property
    def capabilities(self) -> list[str]:
        return ["finra_daily_short_volume"]

    def _load(self, *, force: bool) -> None:
        now = time.time()
        if not force and self._index and (now - self._fetched_at) < self._cache_ttl_s:
            return
        url = (
            self._url_template.replace("{date}", (datetime.now(tz=UTC) - timedelta(days=1)).strftime("%Y%m%d"))
            if self._url_template
            else default_finra_daily_url()
        )
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        self._index = parse_finra_daily_volume_text(response.text)
        self._fetched_at = now
        self._last_error = None

    def poll(
        self, symbols: list[str], *, force: bool = False
    ) -> list[CollectorRecord]:
        if not self.configured:
            return []
        try:
            self._load(force=force)
        except Exception as exc:  # noqa: BLE001
            self._last_error = f"{type(exc).__name__}: {exc}"
            return []
        received = _now()
        records: list[CollectorRecord] = []
        for symbol in symbols:
            row = self._index.get(symbol.strip().upper())
            if row is None:
                continue
            records.append(
                CollectorRecord(
                    symbol=symbol.upper(),
                    payload=row,
                    received_at=received,
                    source_id=self.name,
                    field_hints={
                        "finra_daily_short_volume": row.get("short_volume"),
                        "research_admissibility": "RESEARCH_INADMISSIBLE",
                    },
                    dedupe_key=f"{self.name}:{symbol}:{row.get('trade_date')}",
                )
            )
        return records

    @property
    def rate_limit_state(self) -> dict[str, Any]:
        return {
            "configured": self.configured,
            "cached_symbols": len(self._index),
            "last_error": self._last_error,
        }


__all__ = [
    "FinraDailyVolumeCollector",
    "FinraPublishedSICollector",
    "parse_finra_daily_volume_text",
    "parse_finra_si_text",
]

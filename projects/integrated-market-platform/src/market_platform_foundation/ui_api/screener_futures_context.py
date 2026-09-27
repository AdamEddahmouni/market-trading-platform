"""Contextual futures for a selected US equity.

This is cross-asset context only; it is not a Futures screener universe.
Relevance comes from canonical sector/industry/size metadata and every entry
states why it is shown. Contract identity is the provider's current main
contract, validated against its last trade date; an expired or unresolvable
contract is never presented as current. Prices come only from a current feed:
Moomoo futures snapshots when entitled, and the FuturesX ES depth bridge when
it is running and on the same contract. Otherwise price is unavailable.
"""

from __future__ import annotations

import math
import re
import threading
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
SCHEMA_VERSION = "screener-futures-context/1.0.0"
MAPPING_VERSION = "FUTURES_CONTEXT_MAP_V1"
MONTHS = {"JAN": ("F", 1), "FEB": ("G", 2), "MAR": ("H", 3), "APR": ("J", 4), "MAY": ("K", 5), "JUN": ("M", 6),
          "JUL": ("N", 7), "AUG": ("Q", 8), "SEP": ("U", 9), "OCT": ("V", 10), "NOV": ("X", 11), "DEC": ("Z", 12)}
CAUSAL_NOTE = "Context only; futures movement is not evidence of what moved this instrument."
LIVE_MAX_AGE_SECONDS = 15.0
CONTRACT_TTL_SECONDS = 1800.0
QUOTE_TTL_SECONDS = 5.0
REFUSAL_TTL_SECONDS = 300.0
SMALL_CAP_MAX_USD = 2_000_000_000


@dataclass(frozen=True, slots=True)
class Relation:
    root: str
    name: str
    relationship_type: str
    reason: str
    requires_current_data: bool = False


ROOTS: dict[str, tuple[str, str, str]] = {
    "ES": ("E-mini S&P 500", "BROAD_MARKET", "Broad US equity market context."),
    "NQ": ("E-mini Nasdaq-100", "SECTOR", "Technology/growth index context."),
    "RTY": ("E-mini Russell 2000", "STYLE_FACTOR", "Small-cap index context."),
    "CL": ("Crude Oil", "UNDERLYING", "Crude-oil underlying/sector context."),
    "NG": ("Henry Hub Natural Gas", "UNDERLYING", "Natural-gas industry context."),
    "GC": ("Gold", "UNDERLYING", "Gold/miner underlying commodity context."),
    "SI": ("Silver", "UNDERLYING", "Silver/miner underlying commodity context."),
    "HG": ("Copper", "UNDERLYING", "Copper/miner underlying commodity context."),
    "ZN": ("10-Year T-Note", "MACRO_FACTOR", "Interest-rate context for rate-sensitive lenders."),
}


def _relation(root: str, requires_current_data: bool = False) -> Relation:
    name, kind, reason = ROOTS[root]
    return Relation(root, name, kind, reason, requires_current_data)


def related_futures(*, sector: str | None, industry: str | None, market_cap: float | None) -> list[Relation]:
    """Deterministic relevance map (FUTURES_CONTEXT_MAP_V1), most specific first.

    Underlying commodities come from explicit industry names; NQ from the
    Technology and Communication Services sectors; RTY from market cap below
    $2B (a documented small-cap proxy, not index membership); ZN only for banks
    and mortgage finance and only when current rates data exists; ES for every
    US equity as broad-market context.
    """

    industry_key = (industry or "").strip().casefold()
    sector_key = (sector or "").strip().casefold()
    roots: list[Relation] = []
    if industry_key.startswith("oil & gas"):
        roots.append(_relation("CL"))
    if industry_key == "oil & gas e&p" or "natural gas" in industry_key:
        roots.append(_relation("NG"))
    if industry_key in ("gold", "other precious metals & mining"):
        roots.append(_relation("GC"))
    if industry_key in ("silver", "other precious metals & mining"):
        roots.append(_relation("SI"))
    if industry_key == "copper":
        roots.append(_relation("HG"))
    if sector_key in ("technology", "communication services"):
        roots.append(_relation("NQ"))
    if isinstance(market_cap, (int, float)) and math.isfinite(market_cap) and 0 < market_cap < SMALL_CAP_MAX_USD:
        roots.append(_relation("RTY"))
    if industry_key.startswith("banks") or industry_key == "mortgage finance":
        roots.append(_relation("ZN", requires_current_data=True))
    roots.append(_relation("ES"))
    return roots


_MAIN_MONTH = re.compile(r"\(([A-Z]{3})(\d)\)\s*$")


def resolve_contract(root: str, main_row: dict[str, Any] | None, contract_rows: dict[str, dict[str, Any]],
                     today: date) -> dict[str, Any]:
    """Provider main contract → validated dated contract identity."""

    name = str((main_row or {}).get("name") or "")
    match = _MAIN_MONTH.search(name.upper())
    if not main_row or not match or match.group(1) not in MONTHS:
        return {"state": "UNRESOLVED", "reason": "MAIN_CONTRACT_UNKNOWN"}
    letter, month = MONTHS[match.group(1)]
    digit = int(match.group(2))
    year = today.year + (digit - today.year % 10) % 10
    provider_code = f"US.{root}{year % 100:02d}{month:02d}"
    row = contract_rows.get(provider_code)
    expiry_text = str((row or {}).get("last_trade_time") or "")[:10]
    try:
        expiry = date.fromisoformat(expiry_text)
    except ValueError:
        return {"state": "UNRESOLVED", "reason": "CONTRACT_REFERENCE_UNAVAILABLE", "provider_code": provider_code}
    identity = {"contract_id": f"{root}{letter}{year % 100:02d}", "provider_code": provider_code,
                "contract_month": f"{year}{month:02d}", "last_trade_date": expiry.isoformat(),
                "exchange": str((row or {}).get("exchange_type") or "") or None}
    if expiry < today:
        return {"state": "EXPIRED", "reason": "CONTRACT_EXPIRED", **identity}
    return {"state": "CURRENT", "reason": None, **identity}


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _vendor_time_s(text: Any) -> float | None:
    raw = str(text or "").strip()
    try:
        return datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=ET).timestamp()
    except ValueError:
        return None


def _bridge_es_quote(contract_month: str, fetch: Callable[[], dict[str, Any] | None], now_s: float) -> dict[str, Any] | None:
    """ES mid from the FuturesX depth bridge, only when on the same contract."""

    try:
        bridge = fetch()
    except (ConnectionError, OSError, ValueError):
        return None
    if not isinstance(bridge, dict) or not bridge.get("available") or str(bridge.get("contract_month")) != contract_month:
        return None
    snapshot = bridge.get("snapshot") if isinstance(bridge.get("snapshot"), dict) else {}
    bids, asks = snapshot.get("bids") or [], snapshot.get("asks") or []
    bid = _number(bids[0].get("price")) if bids and isinstance(bids[0], dict) else None
    ask = _number(asks[0].get("price")) if asks and isinstance(asks[0], dict) else None
    try:
        event_s = datetime.fromisoformat(str(snapshot.get("event_time")).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None
    if bid is None or ask is None or ask < bid:
        return None
    age = max(0.0, now_s - event_s)
    return {"price": round((bid + ask) / 2, 4), "price_basis": "MID", "change_pct": None,
            "provider": "FUTURESX_BRIDGE", "as_of": datetime.fromtimestamp(event_s, tz=UTC).isoformat().replace("+00:00", "Z"),
            "age_ms": int(age * 1000), "state": "LIVE" if age <= LIVE_MAX_AGE_SECONDS else "STALE"}


def _default_bridge() -> dict[str, Any] | None:
    from ..donor_bridge.futures_client import fetch_depth_latest, is_available

    return fetch_depth_latest() if is_available() else None


class FuturesContextService:
    def __init__(self, *, transport_getter: Callable[[], Any | None], bridge: Callable[[], dict[str, Any] | None] = _default_bridge,
                 monotonic: Callable[[], float] = time.monotonic, now_s: Callable[[], float] = time.time,
                 today: Callable[[], date] = lambda: datetime.now(ET).date()) -> None:
        self._transport_getter = transport_getter
        self._bridge = bridge
        self._monotonic = monotonic
        self._now_s = now_s
        self._today = today
        self._lock = threading.RLock()
        self._contracts: dict[str, tuple[float, dict[str, Any]]] = {}
        self._quotes: tuple[float, frozenset[str], dict[str, Any]] | None = None
        self._quote_refusal: tuple[float, str] | None = None

    def _resolve(self, roots: list[str], transport: Any | None) -> dict[str, dict[str, Any]]:
        now = self._monotonic()
        missing = [root for root in roots if root not in self._contracts or now - self._contracts[root][0] >= CONTRACT_TTL_SECONDS]
        if missing:
            if transport is None:
                return {root: self._contracts.get(root, (0, {"state": "UNRESOLVED", "reason": "PROVIDER_UNAVAILABLE"}))[1] for root in roots}
            mains = transport.fetch_future_contracts([f"US.{root}main" for root in missing])
            main_rows = {str(row.get("code")): row for row in mains.get("rows") or []}
            today = self._today()
            candidates: dict[str, str] = {}
            for root in missing:
                probe = resolve_contract(root, main_rows.get(f"US.{root}main"), {}, today)
                if probe.get("provider_code"):
                    candidates[root] = probe["provider_code"]
            dated = transport.fetch_future_contracts(sorted(candidates.values())) if candidates else {"rows": []}
            dated_rows = {str(row.get("code")): row for row in dated.get("rows") or []}
            for root in missing:
                reason = mains.get("reason_code")
                result = ({"state": "UNRESOLVED", "reason": "PROVIDER_UNAVAILABLE", "provider_reason": reason} if reason
                          else resolve_contract(root, main_rows.get(f"US.{root}main"), dated_rows, today))
                self._contracts[root] = (now, result)
        return {root: self._contracts[root][1] for root in roots}

    def _vendor_quotes(self, codes: list[str], transport: Any | None) -> tuple[dict[str, Any], str | None]:
        now = self._monotonic()
        if self._quote_refusal and now - self._quote_refusal[0] < REFUSAL_TTL_SECONDS:
            return {}, self._quote_refusal[1]
        if self._quotes and self._quotes[1] >= frozenset(codes) and now - self._quotes[0] < QUOTE_TTL_SECONDS:
            return self._quotes[2], None
        if transport is None or not codes:
            return {}, "PROVIDER_UNAVAILABLE"
        result = transport.fetch_future_quotes(codes)
        if result.get("reason_code"):
            reason = "NOT_ENTITLED" if result["reason_code"] == "MOOMOO_QUOTE_NOT_ENTITLED" else str(result["reason_code"])
            self._quote_refusal = (now, reason)
            return {}, reason
        rows = {str(row.get("code")): row for row in result.get("rows") or []}
        self._quotes = (now, frozenset(codes), rows)
        return rows, None

    def read(self, *, sector: str | None, industry: str | None, market_cap: float | None) -> dict[str, Any]:
        relations = related_futures(sector=sector, industry=industry, market_cap=market_cap)
        with self._lock:
            transport = self._transport_getter()
            contracts = self._resolve([relation.root for relation in relations], transport)
            codes = [c["provider_code"] for c in contracts.values() if c["state"] == "CURRENT"]
            vendor, vendor_reason = self._vendor_quotes(codes, transport)
        now_s = self._now_s()
        items: list[dict[str, Any]] = []
        for relation in relations:
            contract = contracts[relation.root]
            quote: dict[str, Any] | None = None
            reason = contract.get("reason") or vendor_reason
            if contract["state"] == "CURRENT":
                row = vendor.get(contract["provider_code"])
                price = _number((row or {}).get("last_price"))
                if price is not None:
                    previous = _number(row.get("prev_close_price"))
                    event_s = _vendor_time_s(row.get("update_time"))
                    age = None if event_s is None else max(0.0, now_s - event_s)
                    quote = {"price": price, "price_basis": "LAST",
                             "change_pct": round((price - previous) / previous * 100, 4) if previous else None,
                             "provider": "MOOMOO_OPEND", "age_ms": None if age is None else int(age * 1000),
                             "as_of": None if event_s is None else datetime.fromtimestamp(event_s, tz=UTC).isoformat().replace("+00:00", "Z"),
                             "state": "LIVE" if age is not None and age <= LIVE_MAX_AGE_SECONDS else "STALE"}
                elif relation.root == "ES":
                    quote = _bridge_es_quote(contract["contract_month"], self._bridge, now_s)
            if relation.requires_current_data and (quote is None or quote["state"] != "LIVE"):
                continue
            items.append({
                "root": relation.root, "name": relation.name, "relationship_type": relation.relationship_type,
                "relationship_reason": relation.reason, "contract": contract,
                "quote": quote, "availability": "AVAILABLE" if quote else "UNAVAILABLE",
                "unavailable_reason": None if quote else reason or "NO_CURRENT_FEED",
            })
        return {"schema_version": SCHEMA_VERSION, "mapping_version": MAPPING_VERSION, "items": items,
                "causal_note": CAUSAL_NOTE}


__all__ = ["FuturesContextService", "MAPPING_VERSION", "Relation", "related_futures", "resolve_contract"]

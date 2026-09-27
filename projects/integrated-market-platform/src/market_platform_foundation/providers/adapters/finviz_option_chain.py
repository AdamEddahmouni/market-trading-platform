"""Current Finviz Elite option chain adapter (S7 selected-underlying options).

The Finviz options export is a per-underlying current snapshot, fetched through
the shared Finviz request manager (rate limit, cache, single flight, credential
redaction). Raw CSV strings are normalized once here into typed contract rows;
nothing downstream parses provider text.

Observed export columns (2026-09-27, SPY/AAPL): ``Contract Name, Last Trade,
Expiry, Strike, Last Close, Bid, Ask, Change $, Change %, Volume, Open Int.,
Type, IV, Delta, Gamma, Theta, Vega, Rho``. ``IV`` is a decimal fraction
(0.2414 = 24.14 %); ``-1`` and ``0`` are provider sentinels for "no IV".
Blank cells are unavailable, never zero. ``Volume`` is always supplied; a
literal ``0`` is the provider's own zero. ``Change $``/``Change %`` are not
mapped. Expired expiries are included by the provider and removed here.

This adapter is current-only: it has no history, so a point-in-time request is
refused rather than answered with today's chain.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
from zoneinfo import ZoneInfo

from ...contracts.options_quality import OptionQualityFlag
from ..contracts import PROVIDER_UNAVAILABLE, ProviderResult
from .option_contract_builder import canonical_option_id

ET = ZoneInfo("America/New_York")
PROVIDER_ID = "options.finviz.elite_export"
PROVIDER_LABEL = "Finviz Elite"
#: Provider columns S7 maps into the canonical row; the rest stay diagnostic.
MAPPED_COLUMNS = ("Contract Name", "Last Trade", "Expiry", "Strike", "Last Close", "Bid", "Ask", "Volume",
                  "Open Int.", "Type", "IV", "Delta", "Gamma", "Theta", "Vega", "Rho")
REQUIRED_COLUMNS = ("Expiry", "Strike", "Type")
#: Market fields a consumer may show only when the provider supplied the column.
FIELD_COLUMNS = {"bid": "Bid", "ask": "Ask", "last": "Last Close", "volume": "Volume", "open_interest": "Open Int.",
                 "iv": "IV", "delta": "Delta", "gamma": "Gamma", "theta": "Theta", "vega": "Vega", "rho": "Rho"}
#: Same threshold as the options-lane liquidity gate: a spread above 25 % of mid is wide.
WIDE_SPREAD_PCT = 25.0
#: Equity options stop trading at 16:00 ET (some index ETFs at 16:15); after that a same-day expiry is over.
EXPIRY_CUTOFF_MINUTES = 16 * 60 + 15
_OCC_TAIL = re.compile(r"(\d{6})([CP])(\d{8})$")
_TICKER = re.compile(r"[A-Z0-9]{1,10}(-[A-Z0-9]{1,4})?")


@dataclass(frozen=True, slots=True)
class OptionRow:
    """One normalized current contract. ``None`` always means unavailable."""

    option_id: str
    provider_symbol: str
    underlying_id: str
    option_type: str  # CALL | PUT
    expiration: str  # ISO date
    dte: int
    strike: float
    bid: float | None
    ask: float | None
    mid: float | None
    spread: float | None
    spread_pct: float | None
    last: float | None
    volume: int | None
    open_interest: int | None
    iv: float | None  # decimal fraction
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    rho: float | None
    last_trade_at: str | None
    quality_flags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        volume_oi = (self.volume / self.open_interest
                     if self.volume is not None and self.open_interest else None)
        return {
            "option_id": self.option_id, "provider_symbol": self.provider_symbol, "type": self.option_type,
            "expiration": self.expiration, "dte": self.dte, "strike": self.strike,
            "bid": self.bid, "ask": self.ask, "mid": self.mid, "spread": self.spread, "spread_pct": self.spread_pct,
            "last": self.last, "volume": self.volume, "open_interest": self.open_interest,
            "volume_oi_ratio": round(volume_oi, 4) if volume_oi is not None else None,
            "iv": self.iv, "delta": self.delta, "gamma": self.gamma, "theta": self.theta, "vega": self.vega,
            "rho": self.rho, "last_trade_at": self.last_trade_at, "quality_flags": list(self.quality_flags),
        }


@dataclass(frozen=True, slots=True)
class NormalizedChain:
    underlying_id: str
    symbol: str
    rows: tuple[OptionRow, ...]
    provider_rows: int
    expired_excluded: int
    dropped: dict[str, int] = field(default_factory=dict)
    columns: tuple[str, ...] = ()
    unmapped_columns: tuple[str, ...] = ()
    latest_contract_trade_at: str | None = None

    @property
    def supplied_fields(self) -> dict[str, bool]:
        return {name: column in self.columns for name, column in FIELD_COLUMNS.items()}


def _cell(raw: dict[str, Any], column: str) -> str:
    value = raw.get(column)
    return "" if value is None else str(value).strip()


def _number(text: str) -> float | None:
    """A finite number, or None for blank/unparseable text. Never zero-fills."""

    if not text or text in {"-", "N/A", "n/a"}:
        return None
    try:
        value = float(text.replace(",", "").replace("%", "").replace("$", ""))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _count(text: str) -> tuple[int | None, bool]:
    """(integer count, valid). Blank is (None, True); negative or fractional is invalid."""

    value = _number(text)
    if value is None:
        return None, not text
    if value < 0 or value != int(value):
        return None, False
    return int(value), True


def _price(text: str) -> tuple[float | None, bool]:
    value = _number(text)
    if value is None:
        return None, not text
    if value < 0:
        return None, False
    return value, True


def _expiry(text: str) -> date | None:
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _trade_time(text: str) -> str | None:
    """``9/18/2026 3:30:10 PM`` in ET → ISO UTC."""

    if not text:
        return None
    try:
        local = datetime.strptime(text, "%m/%d/%Y %I:%M:%S %p").replace(tzinfo=ET)
    except ValueError:
        return None
    return local.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _expired(expiration: date, now_et: datetime) -> bool:
    today = now_et.date()
    if expiration < today:
        return True
    return expiration == today and now_et.hour * 60 + now_et.minute >= EXPIRY_CUTOFF_MINUTES


def normalize_row(raw: dict[str, Any], *, symbol: str, underlying_id: str,
                  now_et: datetime) -> tuple[OptionRow | None, str | None]:
    """(row, None) or (None, drop reason). ``EXPIRED`` is a classification, not a defect."""

    option_type = _cell(raw, "Type").lower()
    if option_type not in ("call", "put"):
        return None, "INVALID_TYPE"
    strike = _number(_cell(raw, "Strike"))
    if strike is None or strike <= 0:
        return None, "INVALID_STRIKE"
    expiration = _expiry(_cell(raw, "Expiry"))
    if expiration is None:
        return None, "INVALID_EXPIRY"
    provider_symbol = _cell(raw, "Contract Name").upper()
    match = _OCC_TAIL.search(provider_symbol) if provider_symbol else None
    if provider_symbol and (match is None or match.group(1) != expiration.strftime("%y%m%d")
                            or match.group(2) != option_type[0].upper()
                            or int(match.group(3)) != int(round(strike * 1000))):
        # The provider's own contract symbol disagrees with its columns: identity is not trusted.
        return None, "IDENTITY_MISMATCH"
    if _expired(expiration, now_et):
        return None, "EXPIRED"

    flags: list[str] = []
    bid, bid_ok = _price(_cell(raw, "Bid"))
    ask, ask_ok = _price(_cell(raw, "Ask"))
    last, last_ok = _price(_cell(raw, "Last Close"))
    if not (bid_ok and ask_ok and last_ok):
        flags.append("INVALID_PRICE_FIELD")
    volume, volume_ok = _count(_cell(raw, "Volume"))
    open_interest, oi_ok = _count(_cell(raw, "Open Int."))
    if not volume_ok:
        flags.append("INVALID_VOLUME")
    if not oi_ok:
        flags.append("INVALID_OPEN_INTEREST")

    mid = spread = spread_pct = None
    if bid is not None and ask is not None and bid > ask:
        flags.append(OptionQualityFlag.CROSSED_OPTION_MARKET.value)
    elif bid is not None and ask is not None and ask > 0:
        mid = round((bid + ask) / 2, 4)
        spread = round(ask - bid, 4)
        spread_pct = round(spread / mid * 100, 2) if mid > 0 else None
        if spread_pct is not None and spread_pct > WIDE_SPREAD_PCT:
            flags.append(OptionQualityFlag.WIDE_OPTION_SPREAD.value)
    if bid is None or ask is None or bid == 0:
        flags.append(OptionQualityFlag.NO_TWO_SIDED_MARKET.value)
    if bid == 0:
        flags.append(OptionQualityFlag.ZERO_BID.value)

    iv_text = _cell(raw, "IV")
    iv = _number(iv_text)
    if iv is not None and iv <= 0:
        # Observed sentinels: -1 and 0 mean the provider has no IV for the contract.
        iv = None
        flags.append(OptionQualityFlag.IV_INVALID.value)
    elif iv is None and iv_text:
        flags.append(OptionQualityFlag.IV_INVALID.value)
    delta = _number(_cell(raw, "Delta"))
    if delta is not None and (abs(delta) > 1 or (option_type == "call" and delta < 0) or (option_type == "put" and delta > 0)):
        delta = None
        flags.append(OptionQualityFlag.GREEKS_INCONSISTENT.value)

    iso = expiration.isoformat()
    return OptionRow(
        option_id=canonical_option_id(symbol, iso, option_type, Decimal(str(strike))),
        provider_symbol=provider_symbol, underlying_id=underlying_id,
        option_type=option_type.upper(), expiration=iso, dte=(expiration - now_et.date()).days,
        strike=strike, bid=bid, ask=ask, mid=mid, spread=spread, spread_pct=spread_pct, last=last,
        volume=volume, open_interest=open_interest, iv=iv, delta=delta,
        gamma=_number(_cell(raw, "Gamma")), theta=_number(_cell(raw, "Theta")),
        vega=_number(_cell(raw, "Vega")), rho=_number(_cell(raw, "Rho")),
        last_trade_at=_trade_time(_cell(raw, "Last Trade")), quality_flags=tuple(dict.fromkeys(flags)),
    ), None


def normalize_chain(raw_rows: list[dict[str, Any]], columns: list[str] | tuple[str, ...], *, symbol: str,
                    underlying_id: str, now: datetime | None = None) -> NormalizedChain:
    """Normalize a provider chain; a malformed row is dropped and counted, never fatal."""

    now_et = (now or datetime.now(UTC)).astimezone(ET)
    rows: list[OptionRow] = []
    dropped: dict[str, int] = {}
    expired = 0
    seen: set[str] = set()
    for raw in raw_rows:
        try:
            row, reason = normalize_row(raw, symbol=symbol, underlying_id=underlying_id, now_et=now_et)
        except (ArithmeticError, InvalidOperation, ValueError, TypeError):
            row, reason = None, "MALFORMED_ROW"
        if reason == "EXPIRED":
            expired += 1
            continue
        if row is None:
            dropped[reason or "MALFORMED_ROW"] = dropped.get(reason or "MALFORMED_ROW", 0) + 1
            continue
        if row.option_id in seen:
            dropped["DUPLICATE_CONTRACT"] = dropped.get("DUPLICATE_CONTRACT", 0) + 1
            continue
        seen.add(row.option_id)
        rows.append(row)
    rows.sort(key=lambda item: (item.expiration, item.strike, item.option_type))
    trades = [row.last_trade_at for row in rows if row.last_trade_at]
    return NormalizedChain(
        underlying_id=underlying_id, symbol=symbol.upper(), rows=tuple(rows), provider_rows=len(raw_rows),
        expired_excluded=expired, dropped=dropped, columns=tuple(columns),
        unmapped_columns=tuple(column for column in columns if column not in MAPPED_COLUMNS),
        latest_contract_trade_at=max(trades) if trades else None,
    )


def finviz_ticker(symbol: str) -> str:
    """Finviz writes share classes with a dash (BRK-B); OpenD ETF codes may use a dot."""

    return symbol.strip().upper().replace(".", "-").replace("/", "-")


def _default_client() -> Any:
    from ...finviz.options import FinvizOptionsClient

    return FinvizOptionsClient()


def _transport_error(exc: BaseException) -> str:
    """The HTTP status behind a raised transport error (urllib raises for 4xx/5xx), else a network error.

    Only the status code is kept: exception text may carry the request URL.
    """

    cause: BaseException | None = exc
    while cause is not None:
        code = getattr(cause, "code", None) or getattr(cause, "status_code", None)
        if isinstance(code, int) and 100 <= code <= 599:
            return f"HTTP_{code}"
        cause = cause.__cause__ or cause.__context__
    return "NETWORK_ERROR"


def _error_reason(error: str | None) -> tuple[str, str]:
    """Provider error → (ProviderResult status, reason code)."""

    code = str(error or "")
    if code == "NOT_CONFIGURED":
        return "unavailable", PROVIDER_UNAVAILABLE
    if code in ("FINVIZ_OPTIONS_LOGIN_PAGE", "HTTP_401", "HTTP_403"):
        return "not_entitled", "FINVIZ_OPTIONS_AUTH_REJECTED"
    if code == "HTTP_429":
        return "unavailable", "FINVIZ_RATE_LIMITED"
    if code == "NETWORK_ERROR":
        return "unavailable", "FINVIZ_NETWORK_ERROR"
    if code == "FINVIZ_OPTIONS_NOT_CSV":
        return "unavailable", "FINVIZ_OPTIONS_INVALID_RESPONSE"
    return "unavailable", "FINVIZ_OPTIONS_HTTP_ERROR" if code.startswith("HTTP_") else "FINVIZ_OPTIONS_UNAVAILABLE"


class FinvizOptionChainProvider:
    """``OptionChainProvider`` over the Finviz Elite options export — current snapshots only."""

    provider_id = PROVIDER_ID
    capability = "option_chain_current"
    label = PROVIDER_LABEL
    delivery = "SNAPSHOT"

    def __init__(self, *, client_factory: Callable[[], Any] | None = None,
                 clock: Callable[[], datetime] | None = None) -> None:
        # The client is built per fetch so a credential rotation takes effect without a restart.
        self._client_factory = client_factory or _default_client
        self._clock = clock or (lambda: datetime.now(UTC))

    def fetch_chain(self, symbol: str, *, expiration: str | None = None,
                    as_of_time_ns: int | None = None, underlying_id: str | None = None) -> ProviderResult:
        ticker = finviz_ticker(symbol)
        base = {"provider_id": self.provider_id, "capability": self.capability, "instrument_id": underlying_id or ticker}
        if as_of_time_ns is not None:
            return ProviderResult(status="unavailable", reason_code="OPTION_CHAIN_CURRENT_ONLY", **base)
        if not _TICKER.fullmatch(ticker):
            return ProviderResult(status="unavailable", reason_code="INVALID_UNDERLYING", **base)
        started = time.perf_counter()
        try:
            result = self._client_factory().fetch_chain(ticker)
        except Exception as exc:  # noqa: BLE001 — a transport failure is an unavailable chain, never a crash
            result = {"success": False, "error": _transport_error(exc), "contracts": [], "columns": []}
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        meta = result.get("meta") or {}
        if not result.get("success"):
            status, reason = _error_reason(result.get("error"))
            return ProviderResult(status=status, reason_code=reason, details={"latency_ms": latency_ms}, **base)
        chain = normalize_chain(result.get("contracts") or [], result.get("columns") or [], symbol=ticker,
                                underlying_id=underlying_id or ticker, now=self._clock())
        missing = [column for column in REQUIRED_COLUMNS if column not in chain.columns]
        if missing and chain.provider_rows:
            return ProviderResult(status="unavailable", reason_code="FINVIZ_OPTIONS_INVALID_RESPONSE",
                                  details={"latency_ms": latency_ms}, **base)
        rows = [row for row in chain.rows if expiration is None or row.expiration == expiration]
        # The provider clock is this adapter's clock minus the age of a cached export.
        available_ns = int(result.get("available_time_ns") or 0)
        cache_age_ns = max(0, available_ns - int(result.get("fetched_time_ns") or available_ns))
        fetched_ns = int(self._clock().timestamp() * 1_000_000_000) - cache_age_ns
        return ProviderResult(
            status="available" if rows else "empty", reason_code=None if rows else "NO_CHAIN",
            events=tuple(row.to_dict() for row in rows),
            details={"chain": chain, "fetched_time_ns": fetched_ns, "latency_ms": latency_ms,
                     "cache_hit": bool(meta.get("cache_hit") or meta.get("coalesced"))},
            **base,
        )


__all__ = ["FIELD_COLUMNS", "FinvizOptionChainProvider", "MAPPED_COLUMNS", "NormalizedChain", "OptionRow",
           "PROVIDER_ID", "PROVIDER_LABEL", "WIDE_SPREAD_PCT", "finviz_ticker", "normalize_chain", "normalize_row"]

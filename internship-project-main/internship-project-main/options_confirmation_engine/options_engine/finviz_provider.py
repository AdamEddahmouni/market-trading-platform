"""Fetch and normalize options chain snapshots from the Finviz Elite export API.

Purpose
-------
Authenticated CSV export → ``Snapshot`` with greeks (delta) when Elite token present.

Features / API role
-------------------
``fetch_options_snapshot_finviz``, ``parse_options_csv``, ``estimate_spot_from_contracts``.

How ``news_momentum_agent`` consumes it
---------------------------------------
**Not** used in agent ``chain_provider: auto`` (Unusual Whales → yfinance only).
Available for explicit ``finviz`` engine runs or standalone scheduler experiments.

Options-specific vs reusable
----------------------------
Options-specific CSV column aliasing. Reusable retry/throttle HTTP fetch pattern.

Finviz Elite exposes an authenticated CSV export for options chains at
``https://finviz.com/export/options?t=TICKER&auth=TOKEN``. This module pulls that
CSV, maps it onto the engine's normalized :class:`Snapshot` / :class:`ContractRow`
model, and attaches data-quality flags instead of raising on failure.

The exact CSV header names are not officially documented and have varied over time,
so column resolution is done defensively via fuzzy header matching. If Finviz
changes a header, only ``_HEADER_ALIASES`` needs updating.
"""

from __future__ import annotations

import csv
import io
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from options_engine.data_models import ContractRow, Snapshot


# Module-level throttle so rapid multi-ticker batches don't trip Finviz rate limits.
_LAST_REQUEST_TS = 0.0
_THROTTLE_LOCK = threading.Lock()


DEFAULT_BASE_URL = "https://elite.finviz.com/export/options"
DEFAULT_TOKEN_ENV = "FINVIZ_AUTH_TOKEN"

# Finviz sits behind Cloudflare; a browser-like User-Agent is required to avoid a
# 403 challenge page on the export endpoint.
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/csv,text/plain,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Normalized-header -> canonical-field aliases. Headers are normalized by
# lowercasing and stripping all non-alphanumeric characters before matching.
# Verified against the Finviz Elite options export columns:
#   Contract Name, Last Trade, Expiry, Strike, Last Close, Bid, Ask,
#   Change $, Change %, Volume, Open Int., Type, IV, Delta, Gamma, Theta, Vega, Rho
_HEADER_ALIASES: Dict[str, List[str]] = {
    "contract_symbol": ["contractname", "contract", "contractsymbol", "optionsymbol", "symbol"],
    "side": ["type", "optiontype", "side", "callput", "putcall"],
    "strike": ["strike", "strikeprice"],
    "expiration": ["expiry", "expiration", "expdate", "expirationdate"],
    "implied_volatility": ["iv", "impliedvolatility", "impvol", "impliedvol"],
    "volume": ["volume", "vol"],
    "open_interest": ["openint", "openinterest", "oi"],
    "bid": ["bid"],
    "ask": ["ask"],
    "last_price": ["lastclose", "lastprice", "last"],
    "in_the_money": ["inthemoney", "itm"],
    "delta": ["delta"],
}


def _normalize_header(header: str) -> str:
    return "".join(ch for ch in header.lower() if ch.isalnum())


def _build_column_map(fieldnames: List[str]) -> Dict[str, str]:
    """Map canonical field names to the actual CSV header for this response."""
    normalized = {_normalize_header(name): name for name in fieldnames if name}
    column_map: Dict[str, str] = {}
    for field, aliases in _HEADER_ALIASES.items():
        for alias in aliases:
            if alias in normalized:
                column_map[field] = normalized[alias]
                break
    return column_map


def _safe_float(value: Any) -> float:
    if value is None:
        return 0.0
    text = str(value).strip().replace(",", "").replace("%", "")
    if text in {"", "-", "n/a", "N/A", "nan", "None"}:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def _parse_side(raw: str) -> str:
    text = str(raw).strip().lower()
    if text.startswith("c"):
        return "call"
    if text.startswith("p"):
        return "put"
    return text or "unknown"


def _parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "yes", "1", "y"}


def _throttle(min_interval: float) -> None:
    """Block until at least ``min_interval`` seconds have passed since last request."""
    global _LAST_REQUEST_TS
    if min_interval <= 0:
        return
    with _THROTTLE_LOCK:
        wait = min_interval - (time.monotonic() - _LAST_REQUEST_TS)
        if wait > 0:
            time.sleep(wait)
        _LAST_REQUEST_TS = time.monotonic()


def _looks_like_csv(response: requests.Response) -> bool:
    return "text/csv" in response.headers.get("content-type", "") or "," in response.text[:200]


def _is_invalid_token(response: requests.Response) -> bool:
    return response.status_code in (401, 403) and "invalid export api token" in response.text[:200].lower()


def _get_with_retry(
    url: str, params: Dict[str, Any], timeout: float, finviz_cfg: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str]]:
    """GET the export with throttling and retry/backoff.

    Returns ``(csv_text, error_reason)`` where error_reason is ``None`` on success,
    ``"auth"`` for an invalid token (not retried), or ``"fetch"`` for any other
    failure after retries are exhausted.
    """
    max_retries = max(0, int(finviz_cfg.get("max_retries", 3)))
    backoff = float(finviz_cfg.get("retry_backoff_seconds", 1.0))
    min_interval = float(finviz_cfg.get("min_request_interval_seconds", 0.3))

    for attempt in range(max_retries + 1):
        _throttle(min_interval)
        try:
            response = requests.get(url, params=params, headers=DEFAULT_HEADERS, timeout=timeout)
            if _is_invalid_token(response):
                return None, "auth"  # auth won't fix itself; don't retry
            if response.status_code == 200 and _looks_like_csv(response):
                return response.text, None
            retryable = response.status_code in (429, 500, 502, 503, 504) or not _looks_like_csv(response)
            if not retryable:
                return None, "fetch"
        except requests.RequestException:
            pass
        if attempt < max_retries:
            time.sleep(backoff * (2 ** attempt))
    return None, "fetch"


def _resolve_token(settings: Dict[str, Any]) -> Optional[str]:
    """Resolve the Finviz auth token from env var first, then settings."""
    finviz_cfg = settings.get("chain", {}).get("finviz", {})
    env_name = str(finviz_cfg.get("auth_token_env", DEFAULT_TOKEN_ENV))
    token = os.environ.get(env_name)
    if token:
        return token.strip()
    inline = finviz_cfg.get("auth_token")
    if inline:
        return str(inline).strip()
    return None


def _derive_in_the_money(side: str, has_itm_column: bool, itm_raw: str, delta: float) -> bool:
    """Resolve ITM status from an explicit column, else from option delta.

    The Finviz export has no ITM column but does provide Delta. A call is ITM when
    its delta is above ~0.5; a put is ITM when its delta is below ~-0.5.
    """
    if has_itm_column and str(itm_raw).strip():
        return _parse_bool(itm_raw)
    if side == "call":
        return delta >= 0.5
    if side == "put":
        return delta <= -0.5
    return False


def _row_to_contract(row: Dict[str, str], column_map: Dict[str, str]) -> ContractRow:
    def get(field: str) -> str:
        header = column_map.get(field)
        return row.get(header, "") if header else ""

    side = _parse_side(get("side"))
    delta = _safe_float(get("delta"))
    in_the_money = _derive_in_the_money(
        side=side,
        has_itm_column="in_the_money" in column_map,
        itm_raw=get("in_the_money"),
        delta=delta,
    )
    return ContractRow(
        contract_symbol=str(get("contract_symbol")).strip(),
        side=side,
        strike=_safe_float(get("strike")),
        expiration=str(get("expiration")).strip(),
        implied_volatility=_safe_float(get("implied_volatility")),
        volume=_safe_float(get("volume")),
        open_interest=_safe_float(get("open_interest")),
        bid=_safe_float(get("bid")),
        ask=_safe_float(get("ask")),
        last_price=_safe_float(get("last_price")),
        in_the_money=in_the_money,
        delta=delta,
    )


def _parse_expiry_date(expiration: str):
    """Parse a Finviz ``M/D/YYYY`` expiration string into a date, or None."""
    text = str(expiration).strip()
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _expiry_sort_key(expiration: str) -> tuple:
    """Sort key that orders expirations chronologically.

    Finviz returns expirations as ``M/D/YYYY`` strings, which must not be sorted
    lexically. Returns ``(0, date)`` for parseable dates so they precede any
    unparseable values, which fall back to ``(1, original_string)``.
    """
    parsed = _parse_expiry_date(expiration)
    if parsed is not None:
        return (0, parsed.isoformat())
    return (1, str(expiration).strip())


def _as_of_date(as_of: str | None):
    """Extract a date from the as-of timestamp; falls back to today (UTC)."""
    if as_of:
        try:
            return datetime.fromisoformat(str(as_of).replace("Z", "+00:00")).date()
        except ValueError:
            parsed = _parse_expiry_date(as_of)
            if parsed is not None:
                return parsed
    return datetime.now(timezone.utc).date()


def estimate_spot_from_contracts(contracts: List[ContractRow]) -> float:
    """Approximate the underlying spot price from the in-the-money boundary.

    The Finviz options export does not include the underlying price, so we infer
    it from strikes: for calls, ITM means ``strike < spot``; for puts, ITM means
    ``strike > spot``. The spot therefore sits between the highest ITM-call strike
    and the lowest OTM-call strike. Returns 0.0 if it cannot be estimated.
    """
    calls = [c for c in contracts if c.side == "call" and c.strike > 0]
    if not calls:
        return 0.0
    itm_call_strikes = [c.strike for c in calls if c.in_the_money]
    otm_call_strikes = [c.strike for c in calls if not c.in_the_money]
    if itm_call_strikes and otm_call_strikes:
        return (max(itm_call_strikes) + min(otm_call_strikes)) / 2.0
    return 0.0


def parse_options_csv(csv_text: str) -> List[ContractRow]:
    """Parse a Finviz options export CSV into normalized contract rows."""
    if not csv_text or not csv_text.strip():
        return []
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames or []
    column_map = _build_column_map(list(fieldnames))
    rows: List[ContractRow] = []
    for raw_row in reader:
        if not any((value or "").strip() for value in raw_row.values()):
            continue
        rows.append(_row_to_contract(raw_row, column_map))
    return rows


def fetch_options_snapshot_finviz(
    ticker: str,
    settings: Dict[str, Any],
    as_of: str | None = None,
) -> Snapshot:
    """Fetch an options chain snapshot for one ticker from Finviz Elite.

    Returns a normalized :class:`Snapshot`. On any failure the snapshot is
    returned with appropriate ``data_quality_flags`` rather than raising.
    """
    chain_cfg = settings.get("chain", {})
    finviz_cfg = chain_cfg.get("finviz", {})
    base_url = str(finviz_cfg.get("base_url", DEFAULT_BASE_URL))
    timeout = float(chain_cfg.get("request_timeout_seconds", 10))
    max_expiries = max(1, int(chain_cfg.get("expiries_to_scan", 2)))
    min_oi = float(chain_cfg.get("min_open_interest", 50))
    min_volume = float(chain_cfg.get("min_contract_volume", 10))

    now_text = as_of or datetime.now(timezone.utc).isoformat()
    normalized_ticker = ticker.upper().strip()
    snapshot = Snapshot(ticker=normalized_ticker, as_of=now_text, spot_price=0.0, provider="finviz")

    token = _resolve_token(settings)
    if not token:
        snapshot.data_quality_flags.append("missing_auth_token")
        return snapshot

    csv_text, error_reason = _get_with_retry(
        base_url,
        params={"t": normalized_ticker, "auth": token},
        timeout=timeout,
        finviz_cfg=finviz_cfg,
    )
    if csv_text is None:
        snapshot.data_quality_flags.append("invalid_auth_token" if error_reason == "auth" else "fetch_error")
        return snapshot
    try:
        contracts = parse_options_csv(csv_text)
    except Exception:
        snapshot.data_quality_flags.append("fetch_error")
        return snapshot

    if not contracts:
        snapshot.data_quality_flags.append("empty_chain")
        return snapshot

    # Keep only the nearest N expirations (chronologically) to mirror yfinance.
    # The Finviz export retains recently-expired contracts (with blank greeks),
    # so drop expirations before the as-of date before selecting the nearest N.
    unique_expirations = {c.expiration for c in contracts if c.expiration}
    if not unique_expirations:
        snapshot.data_quality_flags.append("no_expirations")
        return snapshot

    as_of_date = _as_of_date(as_of)
    future_expirations = [
        exp for exp in unique_expirations
        if (_parse_expiry_date(exp) is None or _parse_expiry_date(exp) >= as_of_date)
    ]
    candidates = future_expirations or list(unique_expirations)
    ordered_expirations = sorted(candidates, key=_expiry_sort_key)
    selected = set(ordered_expirations[:max_expiries])
    snapshot.expirations = sorted(selected, key=_expiry_sort_key)
    snapshot.contracts = [c for c in contracts if c.expiration in selected]

    snapshot.spot_price = estimate_spot_from_contracts(snapshot.contracts)
    if snapshot.spot_price <= 0:
        snapshot.data_quality_flags.append("missing_spot_price")

    liquid = [c for c in snapshot.contracts if c.open_interest >= min_oi and c.volume >= min_volume]
    if not liquid:
        snapshot.data_quality_flags.append("illiquid_chain")

    return snapshot

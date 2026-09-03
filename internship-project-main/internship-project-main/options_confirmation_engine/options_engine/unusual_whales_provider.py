"""Fetch options chain snapshots from the Unusual Whales API.

Purpose
-------
Primary live chain provider when ``UNUSUAL_WHALES_API_TOKEN`` is set; optional
whale-flow summary for agent urgency enrichment.

Features / API role
-------------------
- ``fetch_options_snapshot_unusual_whales`` → ``Snapshot`` (option-contracts API).
- ``fetch_flow_recent`` → compact premium skew dict (not part of core score).
- ``resolve_unusual_whales_token`` / ``has_unusual_whales_token`` for auth checks.

How ``news_momentum_agent`` consumes it
---------------------------------------
``data_ingestor`` uses UW in ``auto`` mode. ``options_client`` calls
``fetch_flow_recent`` after scoring to nudge ``options_score`` when flow data exists.

Options-specific vs reusable
----------------------------
Options-specific API mapping (OCC symbols, greeks). Reusable HTTP + token resolution
pattern shared with other providers.

Uses documented endpoints only:
- GET /api/stock/{ticker}/option-contracts
- GET /api/stock/{ticker}/options-volume  (optional enrichment)
- GET /api/stock/{ticker}/flow-recent     (optional whale-flow enrichment)

Auth: Authorization: Bearer <token>
Client: UW-CLIENT-API-ID: 100001
Env: UNUSUAL_WHALES_API_TOKEN (or UNUSUAL_WHALES_API_KEY)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

from options_engine.data_models import ContractRow, Snapshot


DEFAULT_BASE_URL = "https://api.unusualwhales.com"
DEFAULT_TOKEN_ENVS = ("UNUSUAL_WHALES_API_TOKEN", "UNUSUAL_WHALES_API_KEY")
DEFAULT_CLIENT_ID = "100001"


def resolve_unusual_whales_token(settings: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Resolve UW API token from env or settings."""
    # Prefer project .env files (news agent + options engine).
    for root in (
        Path(__file__).resolve().parents[1],
        Path(__file__).resolve().parents[2] / "news_momentum_agent",
    ):
        env_path = root / ".env"
        if env_path.exists():
            load_dotenv(env_path, override=True)

    chain_cfg = (settings or {}).get("chain", {})
    uw_cfg = chain_cfg.get("unusual_whales", {}) if isinstance(chain_cfg.get("unusual_whales"), dict) else {}
    env_name = str(uw_cfg.get("auth_token_env", "")).strip()
    if env_name and os.environ.get(env_name):
        return os.environ[env_name].strip()
    for key in DEFAULT_TOKEN_ENVS:
        value = os.environ.get(key)
        if value:
            return value.strip()
    inline = uw_cfg.get("auth_token")
    if inline:
        return str(inline).strip()
    return None


def has_unusual_whales_token(settings: Optional[Dict[str, Any]] = None) -> bool:
    """Return True when a UW API token resolves from env or settings."""
    return bool(resolve_unusual_whales_token(settings))


def _headers(token: str, client_id: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "UW-CLIENT-API-ID": client_id,
        "User-Agent": "news-momentum-agent/1.0",
    }


def _safe_float(value: Any) -> float:
    try:
        if value is None or value == "":
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _pick(row: Dict[str, Any], *keys: str) -> Any:
    lower = {str(k).lower(): v for k, v in row.items()}
    for key in keys:
        if key.lower() in lower and lower[key.lower()] not in (None, ""):
            return lower[key.lower()]
    return None


def _normalize_side(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"call", "c", "calls"}:
        return "call"
    if text in {"put", "p", "puts"}:
        return "put"
    return ""


def _normalize_expiry(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    # Accept YYYY-MM-DD or ISO timestamps.
    if "T" in text:
        text = text.split("T", 1)[0]
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    # YYYYMMDD
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) == 8:
        return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
    return text


def _parse_occ_symbol(symbol: str) -> Tuple[str, float, str]:
    """
    Parse OCC option symbol into (side, strike, expiration YYYY-MM-DD).

    Example: AAPL260702C00310000 -> call, 310.0, 2026-07-02
    """
    text = str(symbol or "").strip().upper()
    if len(text) < 15:
        return "", 0.0, ""
    # Root is letters; then YYMMDD, C/P, 8-digit strike*1000.
    i = 0
    while i < len(text) and text[i].isalpha():
        i += 1
    body = text[i:]
    if len(body) < 15:
        return "", 0.0, ""
    yymmdd = body[:6]
    cp = body[6]
    strike_raw = body[7:15]
    if cp not in {"C", "P"} or not yymmdd.isdigit() or not strike_raw.isdigit():
        return "", 0.0, ""
    try:
        year = 2000 + int(yymmdd[:2])
        month = int(yymmdd[2:4])
        day = int(yymmdd[4:6])
        expiration = f"{year:04d}-{month:02d}-{day:02d}"
        strike = int(strike_raw) / 1000.0
    except ValueError:
        return "", 0.0, ""
    side = "call" if cp == "C" else "put"
    return side, strike, expiration


def _row_to_contract(row: Dict[str, Any]) -> Optional[ContractRow]:
    symbol = str(
        _pick(row, "option_symbol", "optionSymbol", "contract_symbol", "symbol", "id") or ""
    ).strip()
    side = _normalize_side(_pick(row, "type", "option_type", "side", "put_call", "call_put"))
    strike = _safe_float(_pick(row, "strike", "strike_price"))
    expiration = _normalize_expiry(_pick(row, "expiry", "expiration", "expires", "expiration_date", "date"))
    # Unusual Whales option-contracts often only include OCC option_symbol.
    if side not in {"call", "put"} or strike <= 0 or not expiration:
        occ_side, occ_strike, occ_exp = _parse_occ_symbol(symbol)
        if side not in {"call", "put"}:
            side = occ_side
        if strike <= 0:
            strike = occ_strike
        if not expiration:
            expiration = occ_exp
    if side not in {"call", "put"} or strike <= 0 or not expiration:
        return None
    bid = _safe_float(_pick(row, "bid", "bid_price", "nbbo_bid"))
    ask = _safe_float(_pick(row, "ask", "ask_price", "nbbo_ask"))
    last = _safe_float(_pick(row, "last", "last_price", "close", "mark", "avg_price"))
    iv = _safe_float(_pick(row, "iv", "implied_volatility", "impliedVolatility", "volatility"))
    if iv > 3:  # sometimes returned as percent
        iv = iv / 100.0
    delta = _safe_float(_pick(row, "delta"))
    volume = _safe_float(_pick(row, "volume", "vol", "total_volume"))
    oi = _safe_float(_pick(row, "open_interest", "openInterest", "oi", "open_int"))
    spot = _safe_float(_pick(row, "stock_price", "underlying_price", "spot", "spot_price"))
    itm = bool(_pick(row, "in_the_money", "itm"))
    if not itm and spot > 0:
        itm = strike <= spot if side == "call" else strike >= spot
    return ContractRow(
        contract_symbol=symbol or f"{side}_{strike}_{expiration}",
        side=side,
        strike=strike,
        expiration=expiration,
        implied_volatility=iv,
        volume=volume,
        open_interest=oi,
        bid=bid,
        ask=ask,
        last_price=last,
        in_the_money=itm,
        delta=delta,
    )


def _get_json(
    path: str,
    token: str,
    *,
    base_url: str,
    client_id: str,
    timeout: float,
    params: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Any], str]:
    url = f"{base_url.rstrip('/')}{path}"
    try:
        response = requests.get(
            url,
            headers=_headers(token, client_id),
            params=params or {},
            timeout=timeout,
        )
        if response.status_code in (401, 403):
            return None, "auth"
        if response.status_code == 404:
            return None, "not_found"
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and "data" in payload:
            return payload.get("data"), "ok"
        return payload, "ok"
    except requests.RequestException:
        return None, "fetch_error"
    except ValueError:
        return None, "fetch_error"


def fetch_flow_recent(ticker: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """Return compact whale-flow summary for herd urgency enrichment."""
    token = resolve_unusual_whales_token(settings)
    if not token:
        return {}
    chain_cfg = settings.get("chain", {})
    uw_cfg = chain_cfg.get("unusual_whales", {}) if isinstance(chain_cfg.get("unusual_whales"), dict) else {}
    base_url = str(uw_cfg.get("base_url", DEFAULT_BASE_URL))
    client_id = str(uw_cfg.get("client_api_id", DEFAULT_CLIENT_ID))
    timeout = float(chain_cfg.get("request_timeout_seconds", 10))
    data, status = _get_json(
        f"/api/stock/{ticker.upper().strip()}/flow-recent",
        token,
        base_url=base_url,
        client_id=client_id,
        timeout=timeout,
    )
    if status != "ok" or not isinstance(data, list):
        return {}

    call_prem = 0.0
    put_prem = 0.0
    trade_count = 0
    for row in data:
        if not isinstance(row, dict):
            continue
        trade_count += 1
        premium = _safe_float(_pick(row, "total_premium", "premium", "price"))
        side = _normalize_side(_pick(row, "type", "option_type", "put_call", "side"))
        if side == "call":
            call_prem += premium
        elif side == "put":
            put_prem += premium
    net = call_prem - put_prem
    total = call_prem + put_prem
    return {
        "uw_flow_trade_count": float(trade_count),
        "uw_call_premium": call_prem,
        "uw_put_premium": put_prem,
        "uw_net_premium": net,
        "uw_call_premium_share": (call_prem / total) if total > 0 else 0.5,
    }


def fetch_options_snapshot_unusual_whales(
    ticker: str,
    settings: Dict[str, Any],
    as_of: str | None = None,
) -> Snapshot:
    """Fetch options chain via Unusual Whales option-contracts endpoint."""
    chain_cfg = settings.get("chain", {})
    uw_cfg = chain_cfg.get("unusual_whales", {}) if isinstance(chain_cfg.get("unusual_whales"), dict) else {}
    base_url = str(uw_cfg.get("base_url", DEFAULT_BASE_URL))
    client_id = str(uw_cfg.get("client_api_id", DEFAULT_CLIENT_ID))
    timeout = float(chain_cfg.get("request_timeout_seconds", 10))
    max_expiries = max(1, int(chain_cfg.get("expiries_to_scan", 2)))
    min_oi = float(chain_cfg.get("min_open_interest", 50))
    min_volume = float(chain_cfg.get("min_contract_volume", 10))

    now_text = as_of or datetime.now(timezone.utc).isoformat()
    symbol = ticker.upper().strip()
    snapshot = Snapshot(ticker=symbol, as_of=now_text, spot_price=0.0, provider="unusual_whales")

    token = resolve_unusual_whales_token(settings)
    if not token:
        snapshot.data_quality_flags.append("missing_auth_token")
        return snapshot

    data, status = _get_json(
        f"/api/stock/{symbol}/option-contracts",
        token,
        base_url=base_url,
        client_id=client_id,
        timeout=timeout,
    )
    if status == "auth":
        snapshot.data_quality_flags.append("invalid_auth_token")
        return snapshot
    if status != "ok" or data is None:
        snapshot.data_quality_flags.append("fetch_error")
        return snapshot

    rows = data if isinstance(data, list) else []
    contracts: List[ContractRow] = []
    spot_guess = 0.0
    for row in rows:
        if not isinstance(row, dict):
            continue
        spot_guess = max(
            spot_guess,
            _safe_float(_pick(row, "stock_price", "underlying_price", "spot", "spot_price")),
        )
        contract = _row_to_contract(row)
        if contract:
            contracts.append(contract)

    if not contracts:
        snapshot.data_quality_flags.append("empty_chain")
        return snapshot

    expirations = sorted({c.expiration for c in contracts if c.expiration})
    if not expirations:
        snapshot.data_quality_flags.append("no_expirations")
        return snapshot

    selected = set(expirations[:max_expiries])
    snapshot.expirations = sorted(selected)
    snapshot.contracts = [c for c in contracts if c.expiration in selected]
    snapshot.spot_price = spot_guess
    if snapshot.spot_price <= 0:
        # UW option-contracts often omit underlying price; use yfinance spot only.
        try:
            import yfinance as yf

            hist = yf.Ticker(symbol).history(period="1d", interval="1m")
            if not hist.empty:
                snapshot.spot_price = float(hist["Close"].iloc[-1])
        except Exception:
            pass
    if snapshot.spot_price <= 0:
        strikes = sorted({c.strike for c in snapshot.contracts})
        if strikes:
            # Prefer strikes near median as a weak ATM proxy.
            snapshot.spot_price = strikes[len(strikes) // 2]
        else:
            snapshot.data_quality_flags.append("missing_spot_price")

    liquid = [c for c in snapshot.contracts if c.open_interest >= min_oi or c.volume >= min_volume]
    if not liquid:
        snapshot.data_quality_flags.append("illiquid_chain")

    # Optional volume endpoint enrichment is best-effort only.
    vol_data, vol_status = _get_json(
        f"/api/stock/{symbol}/options-volume",
        token,
        base_url=base_url,
        client_id=client_id,
        timeout=timeout,
    )
    vol_row: Optional[Dict[str, Any]] = None
    if vol_status == "ok":
        if isinstance(vol_data, list) and vol_data and isinstance(vol_data[0], dict):
            vol_row = vol_data[0]
        elif isinstance(vol_data, dict):
            vol_row = vol_data
    if vol_row:
        call_vol = _safe_float(_pick(vol_row, "call_volume", "callVolume"))
        put_vol = _safe_float(_pick(vol_row, "put_volume", "putVolume"))
        if call_vol + put_vol > 0:
            snapshot.data_quality_flags.append("uw_options_volume_ok")

    return snapshot

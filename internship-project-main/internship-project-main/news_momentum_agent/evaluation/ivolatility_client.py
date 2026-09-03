"""IVolatility Data Cloud REST client (research / backtest ingest only).

Purpose
-------
Download historical EOD options and stock CSVs into ``data/historical/ivolatility/``
for SPY/QQQ replay — never used in the live agent loop.

Features / API role
-------------------
``IVolatilityClient``, ``pull_tiny_spy_test``, ``pull_full_spy_qqq``,
``read_csv`` / ``write_csv``, ``estimate_pull_cost_usd``.

How this uses ``options_confirmation_engine``
-----------------------------------------------
Downstream: ``historical_chain_adapter`` + ``spy_qqq_replay`` import engine
``Snapshot`` types after CSV ingest. This module does not import the engine.

Options-specific vs reusable
----------------------------
Vendor client is reusable; cached CSVs feed options-specific replay only.

Auth: ``IVOLATILITY_API_KEY`` from env (or ``IVOLATILITY_APIKEY``).
Base URL: https://restapi.ivolatility.com

Trial-friendly default options endpoint is ``/equities/eod/stock-opts-by-param``
(``/equities/eod/options-rawiv`` often returns 403 on retail/trial tariffs).
Large results follow status.urlForDetails → urlForDownload (gzip CSV).
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = PROJECT_ROOT / "data" / "historical" / "ivolatility"
DEFAULT_BASE_URL = "https://restapi.ivolatility.com"
DEFAULT_UNIT_COST_USD = float(os.getenv("IVOLATILITY_UNIT_COST_USD", "0.05"))
DEFAULT_OPTIONS_PATH = "/equities/eod/stock-opts-by-param"
ENV_KEY_NAMES = ("IVOLATILITY_API_KEY", "IVOLATILITY_APIKEY", "IVOL_API_KEY")


class IVolatilityAuthError(RuntimeError):
    """Raised when no API key is configured."""


class IVolatilityRequestError(RuntimeError):
    """Raised on non-recoverable API failures."""


def load_project_dotenv() -> None:
    """Load ``news_momentum_agent/.env`` for IVolatility API key resolution."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)


def resolve_api_key() -> str:
    """Return IVolatility API key from env or raise ``IVolatilityAuthError``."""
    load_project_dotenv()
    for name in ENV_KEY_NAMES:
        value = str(os.getenv(name) or "").strip()
        if value:
            return value
    raise IVolatilityAuthError(
        "Missing IVolatility API key. Add IVOLATILITY_API_KEY to news_momentum_agent/.env "
        "(generate from the IVolatility dashboard). No pull will run without it."
    )


def estimate_pull_cost_usd(
    *,
    tickers: Sequence[str],
    trading_days: int,
    datasets: Sequence[str],
    unit_cost: float = DEFAULT_UNIT_COST_USD,
) -> Dict[str, Any]:
    """Estimate retail pull cost (ticker × day × dataset × unit cost)."""
    n_ticker = len({t.upper() for t in tickers})
    n_ds = len(list(datasets))
    units = n_ticker * max(0, int(trading_days)) * n_ds
    return {
        "tickers": n_ticker,
        "trading_days": int(trading_days),
        "datasets": list(datasets),
        "units": units,
        "unit_cost_usd": unit_cost,
        "estimated_usd": round(units * unit_cost, 2),
        "note": (
            "Rough retail estimate (ticker × day × dataset). Confirm live rates on the "
            "IVolatility account before --confirm-full-pull."
        ),
    }


def _daterange_trading_approx(start: date, end: date) -> List[date]:
    out: List[date] = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def parse_iso_date(text: str) -> date:
    """Parse ``YYYY-MM-DD`` (or longer ISO prefix) into a ``date``."""
    return date.fromisoformat(str(text).strip()[:10])


def _auth_headers(api_key: str) -> Dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "news-momentum-agent-research/1.0",
    }


def _parse_csv_text(text: str) -> List[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _decode_download_bytes(content: bytes) -> List[Dict[str, Any]]:
    if not content:
        return []
    if content[:2] == b"\x1f\x8b":
        text = gzip.decompress(content).decode("utf-8", errors="replace")
    else:
        text = content.decode("utf-8", errors="replace")
    stripped = text.lstrip()
    if stripped.startswith("[") or stripped.startswith("{"):
        try:
            return _normalize_rows(json.loads(text))
        except Exception:
            pass
    return _parse_csv_text(text)


class IVolatilityClient:
    """Thin REST client for IVolatility async CSV download workflow."""

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        timeout_sec: float = 90.0,
        sleep_between_sec: float = 1.25,
    ) -> None:
        self.api_key = api_key or resolve_api_key()
        self.base_url = base_url.rstrip("/")
        self.timeout_sec = timeout_sec
        self.sleep_between_sec = sleep_between_sec
        self.session = requests.Session()

    def _request(self, path_or_url: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        query = dict(params or {})
        query.setdefault("apiKey", self.api_key)
        url = path_or_url if path_or_url.startswith("http") else f"{self.base_url}{path_or_url}"
        resp = self.session.get(
            url, params=query, headers=_auth_headers(self.api_key), timeout=self.timeout_sec
        )
        if resp.status_code in {401, 403}:
            raise IVolatilityRequestError(
                f"IVolatility auth/entitlement failure {resp.status_code} for {path_or_url}: "
                f"{resp.text[:300]}"
            )
        if resp.status_code == 429:
            raise IVolatilityRequestError(
                f"IVolatility HTTP 429 for {path_or_url}: rate limit — slow down and retry"
            )
        if resp.status_code >= 400:
            raise IVolatilityRequestError(
                f"IVolatility HTTP {resp.status_code} for {path_or_url}: {resp.text[:400]}"
            )
        return resp

    def _download_from_details_url(self, url: str, *, max_wait_sec: float = 180.0) -> List[Dict[str, Any]]:
        """Poll /data/info until gzip CSV is ready, then download + decode."""
        deadline = time.time() + max_wait_sec
        last_info: Any = None
        while time.time() < deadline:
            resp = self._request(url)
            try:
                info = resp.json()
            except Exception:
                return _decode_download_bytes(resp.content)
            last_info = info

            download_url = None
            status_code = ""
            if isinstance(info, list) and info:
                first = info[0] if isinstance(info[0], dict) else {}
                meta = first.get("meta") if isinstance(first.get("meta"), dict) else {}
                status_code = str(meta.get("status") or "").upper()
                files = first.get("data") if isinstance(first.get("data"), list) else []
                if files and isinstance(files[0], dict):
                    download_url = files[0].get("urlForDownload") or files[0].get("url")
                    # fileSize 0 means not ready yet
                    if download_url and int(files[0].get("fileSize") or 0) <= 0 and status_code == "PENDING":
                        download_url = None
            elif isinstance(info, dict):
                status_code = str((info.get("meta") or {}).get("status") or info.get("status") or "").upper()
                download_url = info.get("urlForDownload") or info.get("url")
                if not download_url and isinstance(info.get("data"), list) and info["data"]:
                    download_url = info["data"][0].get("urlForDownload")

            if download_url:
                dl = self._request(str(download_url))
                rows = _decode_download_bytes(dl.content)
                if rows:
                    return rows
                # empty decode — wait and retry if still pending
                if status_code == "PENDING":
                    time.sleep(1.5)
                    continue
                return rows

            if status_code in {"FAILED", "ERROR"}:
                raise IVolatilityRequestError(f"Async job failed: {info}")
            time.sleep(1.5)

        raise IVolatilityRequestError(
            f"Timed out waiting for download at {url}; last={str(last_info)[:300]}"
        )

    def _resolve_payload(self, payload: Any) -> Any:
        if not isinstance(payload, dict):
            return payload
        status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
        query = payload.get("query") if isinstance(payload.get("query"), dict) else {}
        data = payload.get("data")
        url_details = status.get("urlForDetails") or payload.get("urlForDetails")
        records_found = int(status.get("recordsFound") or 0)
        if (not data) and url_details and records_found > 0:
            return self._download_from_details_url(str(url_details))
        if payload.get("requestUUID"):
            return self._poll_async(str(payload["requestUUID"]))
        if query.get("requestUUID") and (not data) and records_found > 0:
            return self._poll_async(str(query["requestUUID"]))
        return payload

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        resp = self._request(path, params)
        try:
            payload = resp.json()
        except Exception:
            text = resp.text.strip()
            return text if text else []
        return self._resolve_payload(payload)

    def _poll_async(self, request_uuid: str, *, max_wait_sec: float = 180.0) -> Any:
        deadline = time.time() + max_wait_sec
        info_url = f"{self.base_url}/data/info/{request_uuid}"
        while time.time() < deadline:
            time.sleep(1.5)
            try:
                return self._download_from_details_url(info_url)
            except Exception:
                continue
        raise IVolatilityRequestError(f"Timed out waiting for async result {request_uuid}")

    def fetch_stock_prices(
        self,
        symbol: str,
        *,
        from_date: date,
        to_date: date,
        path: str = "/equities/eod/stock-prices",
    ) -> List[Dict[str, Any]]:
        payload = self._get(
            path,
            {"symbol": symbol.upper(), "from": from_date.isoformat(), "to": to_date.isoformat()},
        )
        time.sleep(self.sleep_between_sec)
        return _normalize_rows(payload)

    def fetch_options_eod(
        self,
        symbol: str,
        *,
        trade_date: date,
        path: str = DEFAULT_OPTIONS_PATH,
        dte_from: int = 0,
        dte_to: int = 7,
        moneyness_from: float = -30.0,
        moneyness_to: float = 30.0,
    ) -> List[Dict[str, Any]]:
        """Fetch EOD options for one trade date (calls + puts)."""
        if "options-rawiv" in path and "stock-opts" not in path:
            payload = self._get(
                path,
                {
                    "symbol": symbol.upper(),
                    "tradeDate": trade_date.isoformat(),
                    "date": trade_date.isoformat(),
                    "from": trade_date.isoformat(),
                    "to": trade_date.isoformat(),
                },
            )
            time.sleep(self.sleep_between_sec)
            return _normalize_rows(payload)

        merged: List[Dict[str, Any]] = []
        for cp in ("C", "P"):
            payload = self._get(
                path,
                {
                    "symbol": symbol.upper(),
                    "tradeDate": trade_date.isoformat(),
                    "dteFrom": int(dte_from),
                    "dteTo": int(dte_to),
                    "cp": cp,
                    "moneynessFrom": moneyness_from,
                    "moneynessTo": moneyness_to,
                },
            )
            time.sleep(self.sleep_between_sec)
            for row in _normalize_rows(payload):
                row = dict(row)
                row.setdefault("_trade_date", trade_date.isoformat())
                row.setdefault("call_put", cp)
                row.setdefault("stock_symbol", symbol.upper())
                row.setdefault("symbol", symbol.upper())
                merged.append(row)
        return merged


def _normalize_rows(payload: Any) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        if payload and isinstance(payload[0], dict) and "meta" in payload[0] and "data" in payload[0]:
            return []
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ("data", "rows", "result", "results", "records"):
            inner = payload.get(key)
            if isinstance(inner, list):
                return [r for r in inner if isinstance(r, dict)]
        if any(
            k in payload
            for k in ("symbol", "strike", "bid", "close", "expiration", "price_strike")
        ):
            return [payload]
        return []
    if isinstance(payload, str):
        return _parse_csv_text(payload)
    return []


def cache_dir_for_range(from_date: date, to_date: date) -> Path:
    """Return/create cache directory for a date-range pull."""
    name = f"spy_qqq_{from_date.strftime('%Y%m%d')}_{to_date.strftime('%Y%m%d')}"
    path = DATA_ROOT / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_csv(path: Path, rows: Sequence[Dict[str, Any]]) -> Path:
    """Write dict rows to CSV with union of all keys as header."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    keys: List[str] = []
    seen = set()
    for row in rows:
        for k in row.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=keys, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def read_csv(path: Path) -> List[Dict[str, Any]]:
    """Read CSV file into list of dicts (empty list if missing)."""
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as fh:
        return [dict(r) for r in csv.DictReader(fh)]


def pull_tiny_spy_test(
    *,
    trading_days: int = 10,
    end: Optional[date] = None,
    options_path: str = DEFAULT_OPTIONS_PATH,
    stock_path: str = "/equities/eod/stock-prices",
) -> Dict[str, Any]:
    """Pull ~N SPY trading days of stock + options EOD CSVs for schema validation."""
    client = IVolatilityClient()
    end_d = end or date.today()
    start_d = end_d - timedelta(days=int(trading_days * 1.8) + 5)
    days = _daterange_trading_approx(start_d, end_d)[-trading_days:]
    if not days:
        raise IVolatilityRequestError("No trading days in tiny-pull window")

    out_dir = DATA_ROOT / f"tiny_spy_{days[0].strftime('%Y%m%d')}_{days[-1].strftime('%Y%m%d')}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cost = estimate_pull_cost_usd(
        tickers=["SPY"],
        trading_days=len(days),
        datasets=["stock_prices", "options_eod"],
    )
    meta: Dict[str, Any] = {
        "mode": "tiny_spy_test",
        "symbol": "SPY",
        "days": [d.isoformat() for d in days],
        "options_path": options_path,
        "stock_path": stock_path,
        "cost_estimate": cost,
        "pulled_at": datetime.utcnow().isoformat() + "Z",
        "errors": [],
    }

    stock_rows = client.fetch_stock_prices("SPY", from_date=days[0], to_date=days[-1], path=stock_path)
    write_csv(out_dir / "SPY_stock_prices.csv", stock_rows)

    option_rows_all: List[Dict[str, Any]] = []
    for d in days:
        try:
            rows = client.fetch_options_eod("SPY", trade_date=d, path=options_path)
            for row in rows:
                row = dict(row)
                row.setdefault("_trade_date", d.isoformat())
                option_rows_all.append(row)
            write_csv(out_dir / f"SPY_options_{d.isoformat()}.csv", rows)
        except Exception as error:
            meta["errors"].append({"date": d.isoformat(), "error": str(error)})
            time.sleep(2.0)
    write_csv(out_dir / "SPY_options_all.csv", option_rows_all)
    (out_dir / "pull_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    meta["out_dir"] = str(out_dir)
    meta["n_stock_rows"] = len(stock_rows)
    meta["n_option_rows"] = len(option_rows_all)
    return meta


def pull_full_spy_qqq(
    *,
    from_date: date,
    to_date: date,
    confirm: bool,
    options_path: str = DEFAULT_OPTIONS_PATH,
    stock_path: str = "/equities/eod/stock-prices",
) -> Dict[str, Any]:
    """Pull SPY+QQQ stock and options EOD CSVs for a date range (requires ``confirm=True``)."""
    days = _daterange_trading_approx(from_date, to_date)
    cost = estimate_pull_cost_usd(
        tickers=["SPY", "QQQ"],
        trading_days=len(days),
        datasets=["stock_prices", "options_eod"],
    )
    if not confirm:
        return {
            "status": "blocked",
            "reason": "Pass --confirm-full-pull after reviewing the cost estimate.",
            "cost_estimate": cost,
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "n_days": len(days),
        }

    client = IVolatilityClient()
    out_dir = cache_dir_for_range(from_date, to_date)
    meta: Dict[str, Any] = {
        "mode": "full_spy_qqq",
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
        "n_days": len(days),
        "cost_estimate": cost,
        "options_path": options_path,
        "stock_path": stock_path,
        "pulled_at": datetime.utcnow().isoformat() + "Z",
        "errors": [],
        "out_dir": str(out_dir),
    }

    for symbol in ("SPY", "QQQ"):
        stock_path_out = out_dir / f"{symbol}_stock_prices.csv"
        try:
            if stock_path_out.exists() and stock_path_out.stat().st_size > 0:
                stock_rows = read_csv(stock_path_out)
                print(f"[ivol] {symbol} stock: resume cache n={len(stock_rows)}")
            else:
                stock_rows = client.fetch_stock_prices(
                    symbol, from_date=from_date, to_date=to_date, path=stock_path
                )
                write_csv(stock_path_out, stock_rows)
                print(f"[ivol] {symbol} stock: n={len(stock_rows)}")
        except Exception as error:
            meta["errors"].append({"symbol": symbol, "dataset": "stock", "error": str(error)})
            print(f"[ivol] {symbol} stock ERROR: {error}")

        all_opts: List[Dict[str, Any]] = []
        for i, d in enumerate(days, start=1):
            day_path = out_dir / f"{symbol}_options_{d.isoformat()}.csv"
            try:
                if day_path.exists() and day_path.stat().st_size > 0:
                    rows = read_csv(day_path)
                    print(f"[ivol] {symbol} {d.isoformat()} ({i}/{len(days)}): resume n={len(rows)}")
                else:
                    rows = client.fetch_options_eod(symbol, trade_date=d, path=options_path)
                    write_csv(day_path, rows)
                    print(f"[ivol] {symbol} {d.isoformat()} ({i}/{len(days)}): n={len(rows)}")
                for row in rows:
                    row = dict(row)
                    row.setdefault("_trade_date", d.isoformat())
                    all_opts.append(row)
            except Exception as error:
                meta["errors"].append(
                    {
                        "symbol": symbol,
                        "date": d.isoformat(),
                        "dataset": "options",
                        "error": str(error),
                    }
                )
                print(f"[ivol] {symbol} {d.isoformat()} ERROR: {error}")
                time.sleep(2.0)
            # Persist progress so a crash mid-symbol still leaves usable day files.
            if i % 10 == 0 or i == len(days):
                (out_dir / "pull_meta.json").write_text(
                    json.dumps(meta, indent=2), encoding="utf-8"
                )
        write_csv(out_dir / f"{symbol}_options_all.csv", all_opts)
        print(f"[ivol] {symbol} options total n={len(all_opts)}")

    meta["status"] = "ok" if not meta["errors"] else "completed_with_errors"
    meta["n_errors"] = len(meta["errors"])
    (out_dir / "pull_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta

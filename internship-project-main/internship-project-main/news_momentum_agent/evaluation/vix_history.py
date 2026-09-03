"""Historical VIX helpers for research panel enrichment (EOD).

Purpose
-------
Cache and attach daily VIX level and prior-close→close change to panel rows.

Features / API role
-------------------
``fetch_vix_history``, ``load_vix_cache``, ``enrich_rows_with_vix``.

How this uses ``options_confirmation_engine``
-----------------------------------------------
Independent; parallels ``features_regime`` live VIX fetch but uses cached EOD
for historical panels.

Options-specific vs reusable
----------------------------
Reusable VIX cache; ``vix_change_intraday`` is an EOD proxy (not true intraday).

``vix_change_intraday`` is proxied by prior-close → close % change because the
IVolatility SPY/QQQ research cache is EOD-only.
"""

from __future__ import annotations

import csv
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = PROJECT_ROOT / "data" / "historical" / "vix_daily.csv"


def _parse_day(text: str) -> Optional[date]:
    try:
        return date.fromisoformat(str(text)[:10])
    except ValueError:
        return None


def load_vix_cache(path: Path = DEFAULT_CACHE) -> Dict[date, Dict[str, float]]:
    """Load cached VIX daily rows keyed by date."""
    if not path.exists() or path.stat().st_size == 0:
        return {}
    out: Dict[date, Dict[str, float]] = {}
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            day = _parse_day(row.get("date") or "")
            if day is None:
                continue
            try:
                close = float(row["close"])
                prev = float(row["prev_close"]) if row.get("prev_close") not in (None, "") else None
            except (KeyError, TypeError, ValueError):
                continue
            change = None
            if prev and prev > 0:
                change = (close / prev - 1.0) * 100.0
            elif row.get("change_pct") not in (None, ""):
                try:
                    change = float(row["change_pct"])
                except ValueError:
                    change = None
            out[day] = {
                "vix_level": close,
                "vix_change_intraday": float(change) if change is not None else 0.0,
            }
    return out


def write_vix_cache(rows: Sequence[Dict[str, Any]], path: Path = DEFAULT_CACHE) -> Path:
    """Write VIX CSV cache to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["date", "close", "prev_close", "change_pct"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def fetch_vix_history(
    *,
    start: date,
    end: date,
    cache_path: Path = DEFAULT_CACHE,
    force_refresh: bool = False,
) -> Dict[date, Dict[str, float]]:
    """Load VIX EOD from cache, or download via yfinance and cache."""
    cached = load_vix_cache(cache_path)
    if cached and not force_refresh:
        # Accept cache if it covers most of the window.
        needed = (end - start).days
        covered = sum(1 for d in cached if start <= d <= end)
        if covered >= max(10, int(needed * 0.5)):
            return cached

    try:
        import yfinance as yf
    except Exception as error:
        if cached:
            return cached
        raise RuntimeError(f"yfinance unavailable and no VIX cache: {error}") from error

    # Pad a few days for prev_close.
    start_pad = start - timedelta(days=10)
    hist = yf.Ticker("^VIX").history(
        start=start_pad.isoformat(),
        end=(end + timedelta(days=1)).isoformat(),
        interval="1d",
        auto_adjust=False,
    )
    if hist is None or hist.empty:
        if cached:
            return cached
        raise RuntimeError("Empty ^VIX history from yfinance")

    closes: List[Tuple[date, float]] = []
    for idx, row in hist.iterrows():
        try:
            if hasattr(idx, "date"):
                d = idx.date()
            else:
                d = datetime.fromisoformat(str(idx)[:10]).date()
            closes.append((d, float(row["Close"])))
        except Exception:
            continue
    closes.sort(key=lambda x: x[0])

    csv_rows: List[Dict[str, Any]] = []
    by_day: Dict[date, Dict[str, float]] = {}
    for i, (d, close) in enumerate(closes):
        prev = closes[i - 1][1] if i > 0 else None
        change = ((close / prev - 1.0) * 100.0) if prev and prev > 0 else 0.0
        csv_rows.append(
            {
                "date": d.isoformat(),
                "close": round(close, 4),
                "prev_close": round(prev, 4) if prev is not None else "",
                "change_pct": round(change, 4),
            }
        )
        by_day[d] = {"vix_level": close, "vix_change_intraday": change}

    write_vix_cache(csv_rows, cache_path)
    return by_day


def enrich_rows_with_vix(
    rows: Sequence[Dict[str, Any]],
    vix_by_day: Dict[date, Dict[str, float]],
) -> List[Dict[str, Any]]:
    """Attach ``vix_level`` and ``vix_change_intraday`` from ``vix_by_day`` map."""
    out: List[Dict[str, Any]] = []
    for row in rows:
        copy = dict(row)
        text = str(copy.get("session_date") or copy.get("timestamp") or "")[:10]
        day = _parse_day(text)
        stats = vix_by_day.get(day) if day else None
        if stats:
            copy["vix_level"] = float(stats["vix_level"])
            copy["vix_change_intraday"] = float(stats["vix_change_intraday"])
        else:
            copy.setdefault("vix_level", None)
            copy.setdefault("vix_change_intraday", None)
        out.append(copy)
    return out

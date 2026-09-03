"""Stale and identical option-quote circuit breaker for entry marks.

Pipeline role
-------------
Guards option *opens* against bad NBBO data before ``portfolio`` commits premium:
  - reject missing bid/ask when ``require_live_nbbo`` is on,
  - pause a ticker after N identical premiums in a row (frozen quote feed).

``validate_entry_quote(record=False)`` is also used by ``near_miss_tracker``
for shadow logging without tripping the live circuit.

State file: ``state/quote_sanity.json`` (per-ticker premium history + pause flag).

Merge notes for stocks/futures
------------------------------
  - **Options-specific** — tied to option premium marks and NBBO semantics.
  - **Reusable pattern:** per-symbol circuit breaker state file; adapt thresholds
    for futures bid/ask width or last-trade staleness checks on equities.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATE_DIR = PROJECT_ROOT / "state"
QUOTE_SANITY_PATH = STATE_DIR / "quote_sanity.json"


def _load() -> Dict[str, Any]:
    try:
        if not QUOTE_SANITY_PATH.exists():
            return {"tickers": {}}
        data = json.loads(QUOTE_SANITY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"tickers": {}}
    except Exception:
        return {"tickers": {}}


def _save(data: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temp = QUOTE_SANITY_PATH.with_suffix(".json.tmp")
    temp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temp.replace(QUOTE_SANITY_PATH)


def validate_entry_quote(
    ticker: str,
    contract_symbol: str,
    premium: float,
    *,
    settings: Optional[Dict[str, Any]] = None,
    has_nbbo: bool = True,
    record: bool = True,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validate an entry quote.

    When record=False, reads pause/history state but does not persist changes
    (for shadow near-miss logging without tripping the live circuit breaker).

    Returns (ok, reason_code, details).
    """
    exec_cfg = (settings or {}).get("execution") or {}
    require_nbbo = bool(exec_cfg.get("require_live_nbbo", True))
    identical_n = int(exec_cfg.get("identical_quote_pause_count", 3))
    key = ticker.upper().strip()
    premium_r = round(float(premium), 4)

    details: Dict[str, Any] = {
        "ticker": key,
        "contract_symbol": contract_symbol,
        "premium": premium_r,
        "has_nbbo": has_nbbo,
    }

    if require_nbbo and not has_nbbo:
        return False, "stale_quote", {**details, "why": "missing_bid_ask"}

    if premium_r <= 0:
        return False, "stale_quote", {**details, "why": "non_positive_premium"}

    data = _load()
    tickers = data.setdefault("tickers", {})
    hist: List[float] = list(tickers.get(key, {}).get("recent_premiums") or [])
    paused_until_change = bool(tickers.get(key, {}).get("paused_until_change"))

    if paused_until_change:
        last = hist[-1] if hist else None
        if last is not None and round(float(last), 4) == premium_r:
            return False, "identical_quote_pause", {
                **details,
                "recent": hist[-identical_n:],
            }
        paused_until_change = False

    hist_next = list(hist)
    hist_next.append(premium_r)
    if len(hist_next) > 20:
        hist_next = hist_next[-20:]

    if len(hist_next) >= identical_n and all(
        round(float(x), 4) == premium_r for x in hist_next[-identical_n:]
    ):
        if record:
            tickers[key] = {
                "recent_premiums": hist_next,
                "paused_until_change": True,
                "contract_symbol": contract_symbol,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            _save(data)
        return False, "identical_quote_pause", {
            **details,
            "recent": hist_next[-identical_n:],
            "why": f"{identical_n}_identical",
        }

    if record:
        tickers[key] = {
            "recent_premiums": hist_next,
            "paused_until_change": paused_until_change,
            "contract_symbol": contract_symbol,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        _save(data)
    return True, "ok", details


def check_and_record_quote(
    ticker: str,
    contract_symbol: str,
    premium: float,
    *,
    settings: Optional[Dict[str, Any]] = None,
    has_nbbo: bool = True,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Validate an entry quote and persist history / pause state."""
    return validate_entry_quote(
        ticker,
        contract_symbol,
        premium,
        settings=settings,
        has_nbbo=has_nbbo,
        record=True,
    )


def paused_tickers() -> List[str]:
    """Return tickers currently paused until their entry quote changes."""
    data = _load()
    out = []
    for key, row in (data.get("tickers") or {}).items():
        if isinstance(row, dict) and row.get("paused_until_change"):
            out.append(str(key))
    return sorted(out)

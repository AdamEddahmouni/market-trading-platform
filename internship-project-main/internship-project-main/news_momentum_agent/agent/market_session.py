"""US equity / equity-options session helpers.

Equity options only have real two-sided markets during regular trading hours.
After the close you cannot reliably open or short via listed options — so the
agent must not paper-trade or spam exits then.

Expiry horizon modes (``trading.options_expiry_horizon``)
---------------------------------------------------------
Motivated by Path A small-caps having no usable *same-day* options liquidity
and by 0DTE mark noise (e.g. COIN stop on a flat underlying). Modes:

  - **same_day** — 0DTE only; EOD flatten on expiry day. Original internship
    target; harsh on thin single names.
  - **deadline** — nearest eligible expiry on or before ``trading.deadline_date``
    (legacy aliases: through_friday / this_friday). Enables overnight holds
    through that calendar date; deadline-day flatten applies.
  - **range** — nearest eligible expiry with DTE in ``trading.options_dte_range``
    (e.g. [0, 30]). Overnight holds allowed; **no** deadline flatten — exits
    are TP/SL (and EOD flatten only if the chosen contract expires *today*).

Live paper agent was switched to ``range`` after same_day → deadline experiments.
Helpers below normalize aliases and compute effective min/max DTE for contract
selection and Path B keep filters. Threshold values live in settings — do not
change them from this module.

Merge notes for stocks/futures
------------------------------
  - **Highly reusable** for any US equity-session agent (RTH gates, EOD flatten time).
  - **Options-specific:** DTE horizon modes and deadline flatten — map to futures
    roll/expiry calendars in a larger system.
  - No state files; reads ``settings.trading`` and ``settings.execution`` only.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple


def now_et(now: Optional[datetime] = None) -> datetime:
    """Return ``now`` (or current time) as America/New_York; UTC fallback if zoneinfo fails."""
    try:
        from zoneinfo import ZoneInfo

        et = ZoneInfo("America/New_York")
        current = now or datetime.now(et)
        if current.tzinfo is None:
            return current.replace(tzinfo=et)
        return current.astimezone(et)
    except Exception:
        return now or datetime.now(timezone.utc)


def this_friday_date_et(now: Optional[datetime] = None) -> date:
    """Return this week's Friday (ET). Sat/Sun map to the upcoming Friday."""
    current = now_et(now).date()
    days_ahead = 4 - current.weekday()  # Mon=0 … Fri=4
    if days_ahead < 0:
        days_ahead += 7
    return current + timedelta(days=days_ahead)


def options_dte_cap_through_friday_et(now: Optional[datetime] = None) -> int:
    """Calendar DTE cap from today ET through this Friday (0 on Friday)."""
    current = now_et(now).date()
    friday = this_friday_date_et(now)
    return max(0, (friday - current).days)


def options_expiry_horizon(settings: Optional[Dict[str, Any]] = None) -> str:
    """Raw ``trading.options_expiry_horizon`` string from settings (may be an alias)."""
    trading = (settings or {}).get("trading") or {}
    return str(trading.get("options_expiry_horizon") or "").strip().lower()


_DEADLINE_ALIASES = frozenset({"deadline", "through_friday", "this_friday", "friday"})
_SAME_DAY_ALIASES = frozenset({"same_day", "same-day", "0dte", "zero_dte", ""})
_RANGE_ALIASES = frozenset({"range", "dte_range", "window"})


def normalize_options_expiry_horizon(settings: Optional[Dict[str, Any]] = None) -> str:
    """
    Return canonical horizon mode: ``same_day``, ``deadline``, or ``range``.

    Legacy aliases: through_friday/this_friday/friday → deadline;
    empty/0dte → same_day.

    Unknown values fall back to conservative ``same_day`` so a typo does not
    silently open multi-day risk.
    """
    raw = options_expiry_horizon(settings)
    if raw in _DEADLINE_ALIASES:
        return "deadline"
    if raw in _RANGE_ALIASES:
        return "range"
    if raw in _SAME_DAY_ALIASES:
        return "same_day"
    # Unknown value: treat positive options_max_dte as legacy open window → same_day
    # unless explicitly set; default conservative same_day.
    return "same_day"


def through_friday_horizon_enabled(settings: Optional[Dict[str, Any]] = None) -> bool:
    """Backward-compatible alias: True when horizon normalizes to deadline."""
    return normalize_options_expiry_horizon(settings) == "deadline"


def resolve_deadline_date_et(
    settings: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> date:
    """
    Deadline calendar date (ET) for deadline-horizon selection and flatten.

    Uses ``trading.deadline_date`` (YYYY-MM-DD) when set; otherwise this Friday.
    """
    trading = (settings or {}).get("trading") or {}
    raw = str(trading.get("deadline_date") or "").strip()
    if raw:
        try:
            return date.fromisoformat(raw[:10])
        except ValueError:
            pass
    return this_friday_date_et(now)


def options_dte_range_bounds(settings: Optional[Dict[str, Any]] = None) -> Tuple[int, int]:
    """Return (min_dte, max_dte) for range mode; defaults to [1, 30]."""
    trading = (settings or {}).get("trading") or {}
    raw = trading.get("options_dte_range")
    min_dte, max_dte = 1, 30
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        try:
            min_dte = max(0, int(raw[0]))
            max_dte = max(min_dte, int(raw[1]))
        except (TypeError, ValueError):
            pass
    return min_dte, max_dte


def allows_overnight_holds(settings: Optional[Dict[str, Any]] = None) -> bool:
    """True when horizon is deadline or range (multi-day option holds allowed)."""
    return normalize_options_expiry_horizon(settings) in {"deadline", "range"}


def deadline_flatten_enabled(settings: Optional[Dict[str, Any]] = None) -> bool:
    """True when horizon is deadline and positions should flatten on deadline_date."""
    return normalize_options_expiry_horizon(settings) == "deadline"


def options_horizon_label(settings: Optional[Dict[str, Any]] = None) -> str:
    """Short user-facing label for Telegram / rationale copy."""
    mode = normalize_options_expiry_horizon(settings)
    if mode == "deadline":
        return "deadline"
    if mode == "range":
        return "range"
    return "0DTE"


def effective_options_min_dte(
    settings: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> int:
    """Floor DTE for contract selection (range mode only; else 0)."""
    del now  # unused; signature mirrors max helper
    mode = normalize_options_expiry_horizon(settings)
    if mode == "range":
        min_dte, _ = options_dte_range_bounds(settings)
        return min_dte
    return 0


def effective_options_max_dte(
    settings: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> int:
    """
    Effective max DTE for contract selection / Path B keep filter.

    - same_day → 0
    - deadline → days until deadline_date (optionally capped by positive options_max_dte)
    - range → options_dte_range max
    """
    trading = (settings or {}).get("trading") or {}
    configured = int(trading.get("options_max_dte", 0) or 0)
    mode = normalize_options_expiry_horizon(settings)

    if mode == "same_day":
        return 0

    if mode == "deadline":
        current = now_et(now).date()
        deadline = resolve_deadline_date_et(settings, now)
        cap = max(0, (deadline - current).days)
        if configured > 0:
            return min(configured, cap)
        return cap

    if mode == "range":
        _, max_dte = options_dte_range_bounds(settings)
        return max_dte

    return configured


def parse_hhmm(value: str, default_hour: int = 15, default_minute: int = 45) -> tuple[int, int]:
    """Parse ``HH:MM`` ET clock string; return defaults on empty or invalid input."""
    text = str(value or "").strip()
    parts = text.split(":")
    try:
        hour = int(parts[0]) if parts else default_hour
        minute = int(parts[1]) if len(parts) > 1 else default_minute
        return hour, minute
    except (TypeError, ValueError):
        return default_hour, default_minute


def is_equity_rth(now: Optional[datetime] = None) -> bool:
    """Mon–Fri 09:30–15:59 America/New_York (cash equity / equity-options RTH)."""
    try:
        current = now_et(now)
        if current.weekday() >= 5:
            return False
        minutes = current.hour * 60 + current.minute
        return (9 * 60 + 30) <= minutes < (16 * 60)
    except Exception:
        return False


def is_past_eod_flatten(settings: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None) -> bool:
    """True at or after ``options_exits.eod_flatten_et`` (default 15:45 ET)."""
    exits_cfg = ((settings or {}).get("trading") or {}).get("options_exits") or {}
    hour, minute = parse_hhmm(str(exits_cfg.get("eod_flatten_et", "15:45")))
    current = now_et(now)
    return (current.hour, current.minute) >= (hour, minute)


def market_hours_only_enabled(settings: Optional[Dict[str, Any]] = None) -> bool:
    """True when ``execution.market_hours_only`` gates trading to equity RTH."""
    return bool(((settings or {}).get("execution") or {}).get("market_hours_only", True))


def is_options_session_open(settings: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None) -> bool:
    """
    True when listed equity options are in their normal trading session.

    When execution.market_hours_only is false, always True (tests / research).
    """
    if not market_hours_only_enabled(settings):
        return True
    return is_equity_rth(now)


def no_post_1545_opens_enabled(settings: Optional[Dict[str, Any]] = None) -> bool:
    """Alias for blocking new opens at/after eod_flatten_et (default 15:45 ET)."""
    exec_cfg = (settings or {}).get("execution") or {}
    # Default true when market_hours_only is on; explicit key wins when set.
    if "no_post_1545_opens" in exec_cfg:
        return bool(exec_cfg.get("no_post_1545_opens"))
    return market_hours_only_enabled(settings)


def is_options_entry_allowed(settings: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None) -> bool:
    """
    True when new 0DTE / options entries are allowed.

    Entry window ends at eod_flatten_et so we never reopen into an immediate flatten.
    """
    if not market_hours_only_enabled(settings):
        # Still honor explicit no_post_1545_opens when set.
        if no_post_1545_opens_enabled(settings) and is_past_eod_flatten(settings, now):
            return False
        return True
    if not is_equity_rth(now):
        return False
    if no_post_1545_opens_enabled(settings) and is_past_eod_flatten(settings, now):
        return False
    return True

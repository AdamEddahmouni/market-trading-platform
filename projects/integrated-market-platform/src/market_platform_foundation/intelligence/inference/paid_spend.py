"""Hard daily and monthly dollar caps for every paid AI call, enforced before the call is sent.

``DollarLedger`` keeps what paid AI has cost today (UTC) and this calendar month (UTC), in integer micro-dollars,
in the external IMP cache (``quota/paid-ai-dollars.json``). Before a call it sets aside the call's worst case: the
input estimate (or the provider's exact count) plus the whole output allowance, thinking included, at the model's
pinned list price (``paid_prices``). A call that could cross either cap is refused with a stable reason. After the
call the set-aside amount is replaced by the cost of the usage the vendor reported; with no usage reported, the
worst case stays charged.

The caps are operator settings, ``IMP_PAID_AI_DAILY_USD`` and ``IMP_PAID_AI_MONTHLY_USD`` (process environment or
the private provider file, written from Setup). Both default to 0, and a cap of 0 refuses every paid call, so paid
AI is off until the operator types in both caps. Every paid engine and the assistant share this one ledger.

The file is read and written under a cross-process lock and fails closed: unreadable state refuses every call
rather than becoming a fresh allowance.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import threading
import time
from collections.abc import Callable
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from .paid_prices import MICRO, cost_micro, price_for

DAILY_USD_ENV, MONTHLY_USD_ENV = "IMP_PAID_AI_DAILY_USD", "IMP_PAID_AI_MONTHLY_USD"
LEDGER_RELATIVE = Path("quota") / "paid-ai-dollars.json"
MAX_CAP_USD = 10_000
CAP_NOT_SET = "PAID_AI_CAP_NOT_SET"
PRICE_UNKNOWN = "PAID_MODEL_PRICE_UNKNOWN"
DAILY_CAP = "PAID_AI_DAILY_DOLLAR_CAP"
MONTHLY_CAP = "PAID_AI_MONTHLY_DOLLAR_CAP"
OVERRUN = "PAID_AI_USAGE_EXCEEDED_RESERVATION"
UNREADABLE = "PAID_AI_LEDGER_UNREADABLE"
# Reason prefixes of a call refused before it was sent (token budget or dollar caps): nothing was billed.
REFUSED_BEFORE_SEND = ("SYNTHESIS_", "PAID_AI_", "PAID_MODEL_")
DOLLAR_REFUSALS = frozenset({CAP_NOT_SET, PRICE_UNKNOWN, DAILY_CAP, MONTHLY_CAP, OVERRUN, UNREADABLE})
_COUNTERS = ("day_micro", "month_micro", "day_reserved", "month_reserved")
_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_LOCK = threading.Lock()


def parse_cap(text: str | None) -> float | None:
    """A cap in dollars: finite, 0 to ``MAX_CAP_USD``, at most cent precision. None for anything else."""

    raw = (text or "").strip()
    if not raw:
        return 0.0
    if not re.fullmatch(r"\d{1,5}(\.\d{1,2})?", raw):
        return None
    amount = float(raw)
    return amount if math.isfinite(amount) and amount <= MAX_CAP_USD else None


def caps_micro(value: Callable[[str], str | None]) -> tuple[int, int]:
    """(daily, monthly) caps in micro-dollars. A missing or malformed cap is 0, which refuses every paid call."""

    caps = []
    for name in (DAILY_USD_ENV, MONTHLY_USD_ENV):
        amount = parse_cap(value(name))
        caps.append(round((amount or 0.0) * MICRO))
    return caps[0], caps[1]


def paid_gate(value: Callable[[str], str | None], model: str | None, *, day: date | None = None) -> str | None:
    """Why a paid model cannot be used at all (no caps, no pinned price), or None. Calls nothing."""

    daily, monthly = caps_micro(value)
    if daily <= 0 or monthly <= 0:
        return CAP_NOT_SET
    if price_for(model, day or datetime.now(UTC).date()) is None:
        return PRICE_UNKNOWN
    return None


def usd(micro: int) -> float:
    return round(micro / MICRO, 6)


class DollarLedger:
    """Persisted UTC-day and UTC-month dollar totals with worst-case reservations."""

    def __init__(self, path: Path | None, *, daily_micro: int, monthly_micro: int,
                 clock: Callable[[], float] = time.time) -> None:
        self._path = path
        self.daily_micro = max(0, int(daily_micro))
        self.monthly_micro = max(0, int(monthly_micro))
        self._clock = clock
        with _LOCKS_LOCK:
            self._lock = _LOCKS.setdefault(str(path.resolve()), threading.RLock()) if path is not None else threading.RLock()
        self._memory: dict[str, Any] = {}

    @contextmanager
    def _locked(self):
        with self._lock:
            connection = None
            try:
                if self._path is not None:
                    self._path.parent.mkdir(parents=True, exist_ok=True)
                    connection = sqlite3.connect(str(self._path) + ".lock.sqlite", timeout=10)
                    connection.execute("BEGIN IMMEDIATE")
                yield
            except sqlite3.Error as exc:
                raise ValueError("PAID_AI_LEDGER_LOCK_UNAVAILABLE") from exc
            finally:
                if connection is not None:
                    connection.rollback()
                    connection.close()

    def today(self) -> date:
        return datetime.fromtimestamp(self._clock(), tz=UTC).date()

    def _load(self) -> dict[str, Any]:
        if self._path is None:
            return dict(self._memory)
        try:
            loaded = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            raise ValueError(UNREADABLE) from exc
        if (not isinstance(loaded, dict) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(loaded.get("day")))
                or not re.fullmatch(r"\d{4}-\d{2}", str(loaded.get("month")))
                or any(type(loaded.get(key)) is not int or loaded[key] < 0 for key in _COUNTERS)
                or type(loaded.get("overrun", False)) is not bool):
            raise ValueError(UNREADABLE)
        return loaded

    def _rolled(self) -> dict[str, Any]:
        state = self._load()
        today = self.today()
        day, month = today.isoformat(), today.isoformat()[:7]
        if state.get("month") != month:
            state = {"month": month, "month_micro": 0, "month_reserved": 0}
        if state.get("day") != day:
            # A reservation open across midnight is settled against the new day; it can only lower the count.
            state.update(day=day, day_micro=0, day_reserved=0, overrun=False)
        return state

    def _save(self, state: dict[str, Any]) -> None:
        if self._path is None:
            self._memory = dict(state)
            return
        from ...local_state.external_cache import write_json_atomic

        # A reservation that cannot be persisted must not permit a paid call.
        write_json_atomic(self._path, {**state, "daily_cap_micro": self.daily_micro,
                                       "monthly_cap_micro": self.monthly_micro})

    def worst_case_micro(self, model: str | None, input_tokens: int, output_tokens: int) -> int | None:
        return cost_micro(model, input_tokens, output_tokens, self.today())

    def reserve(self, model: str | None, input_tokens: int, output_tokens: int) -> tuple[int, str | None]:
        """(micro-dollars set aside, None), or (0, reason) when the call must not be sent."""

        if self.daily_micro <= 0 or self.monthly_micro <= 0:
            return 0, CAP_NOT_SET
        amount = self.worst_case_micro(model, input_tokens, output_tokens)
        if amount is None:
            return 0, PRICE_UNKNOWN
        try:
            with self._locked():
                state = self._rolled()
                if state.get("overrun"):
                    return 0, OVERRUN
                if state["day_micro"] + state["day_reserved"] + amount > self.daily_micro:
                    return 0, DAILY_CAP
                if state["month_micro"] + state["month_reserved"] + amount > self.monthly_micro:
                    return 0, MONTHLY_CAP
                state["day_reserved"] += amount
                state["month_reserved"] += amount
                self._save(state)
        except (OSError, ValueError) as exc:
            return 0, str(exc) if str(exc).startswith("PAID_AI_") else UNREADABLE
        return amount, None

    def settle(self, reserved_micro: int, model: str | None, tokens_input: int | None,
               tokens_output: int | None) -> int:
        """Replace a reservation with the reported usage's cost; with no usage, the worst case stays. Returns the
        micro-dollars charged."""

        reserved_micro = max(0, int(reserved_micro))
        known = all(type(value) is int and value >= 0 for value in (tokens_input, tokens_output))
        actual = cost_micro(model, tokens_input, tokens_output, self.today()) if known else None
        charged = reserved_micro if actual is None else actual
        try:
            with self._locked():
                state = self._rolled()
                for key in ("day_reserved", "month_reserved"):
                    state[key] = max(0, state[key] - reserved_micro)
                state["day_micro"] += charged
                state["month_micro"] += charged
                if charged > reserved_micro:
                    state["overrun"] = True
                self._save(state)
        except (OSError, ValueError):
            return reserved_micro  # not settled: the persisted worst-case reservation stays charged
        return charged

    def release(self, reserved_micro: int) -> None:
        """Return a reservation for a call that was never sent."""

        try:
            with self._locked():
                state = self._rolled()
                for key in ("day_reserved", "month_reserved"):
                    state[key] = max(0, state[key] - max(0, int(reserved_micro)))
                self._save(state)
        except (OSError, ValueError):
            pass  # the reservation stays set aside until the UTC day ends: it can only refuse, never overspend

    def status(self) -> dict[str, Any]:
        try:
            with self._locked():
                state = self._rolled()
        except (OSError, ValueError):
            return {"state": "UNREADABLE", "reason": UNREADABLE, "daily_cap_usd": usd(self.daily_micro),
                    "monthly_cap_usd": usd(self.monthly_micro)}
        return {"state": "AVAILABLE" if self.daily_micro > 0 and self.monthly_micro > 0 else "CAP_NOT_SET",
                "reason": None if self.daily_micro > 0 and self.monthly_micro > 0 else CAP_NOT_SET,
                "day": state["day"], "month": state["month"],
                "spent_today_usd": usd(state["day_micro"]), "spent_month_usd": usd(state["month_micro"]),
                "reserved_usd": usd(state["day_reserved"]), "daily_cap_usd": usd(self.daily_micro),
                "monthly_cap_usd": usd(self.monthly_micro), "overrun": bool(state.get("overrun"))}


def ledger_for(value: Callable[[str], str | None], cache_dir: Path | None) -> DollarLedger:
    daily, monthly = caps_micro(value)
    return DollarLedger(cache_dir / LEDGER_RELATIVE if cache_dir is not None else None,
                        daily_micro=daily, monthly_micro=monthly)


__all__ = ["CAP_NOT_SET", "DAILY_CAP", "DAILY_USD_ENV", "DOLLAR_REFUSALS", "DollarLedger", "LEDGER_RELATIVE",
           "MAX_CAP_USD", "MONTHLY_CAP", "MONTHLY_USD_ENV", "OVERRUN", "PRICE_UNKNOWN", "REFUSED_BEFORE_SEND",
           "caps_micro", "ledger_for", "paid_gate", "parse_cap", "usd"]

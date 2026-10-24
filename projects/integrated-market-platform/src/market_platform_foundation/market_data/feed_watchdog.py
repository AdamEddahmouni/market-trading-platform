"""Moomoo data-flow watchdog — judges the feed by what arrives, from outside the feed thread.

The push feed's own stall check runs on the session thread, after an SDK call returns. On 2026-10-19..22
that thread blocked inside a call that never returned, so the feed reported CONNECTED for hours while
nothing arrived. This watchdog runs on its own thread and looks only at receipts: the feed polls a
market snapshot every two seconds while any quote is subscribed, so a healthy session receives records
whatever the market does. Silence while data is expected is a dead session.

Escalation, each step logged in ``events``:
1. alarm — the provider is DEGRADED with ``MOOMOO_FEED_SILENT`` (health stops saying CONNECTED) and the
   market writer records a ``MOOMOO_FEED_SILENT`` gap;
2. reconnect — ``feed.force_reconnect`` closes the stuck context, or abandons a thread that stays stuck;
3. in a collection-only process, when silence survives two reconnects or the hourly reconnect budget
   is spent: ``unrecoverable`` is set, supply reports it, and the process exits so its supervisor
   restarts it with fresh SDK state. A serving process only alarms and reconnects.

Collection eligibility only: this grants no trading authority and contacts no provider itself.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable

from .live_config import (
    moomoo_silence_seconds,
    moomoo_watchdog_interval_seconds,
    moomoo_watchdog_restarts_per_hour,
)
from .provider_lifecycle import ProviderConnectionState

SILENT_REASON = "MOOMOO_FEED_SILENT"
UNRECOVERABLE_REASON = "MOOMOO_FEED_UNRECOVERABLE"
RECONNECTS_BEFORE_ESCALATION = 2
BUDGET_WINDOW_NS = 3_600_000_000_000
_NS = 1_000_000_000
_EXPECTED_LABELS = frozenset({"PREMARKET", "REGULAR", "AFTER_HOURS"})
# The feed is already reconnecting on its own in these states; forcing it again would only race that.
_SELF_RECOVERING = frozenset({ProviderConnectionState.DISCONNECTED, ProviderConnectionState.RECONNECTING,
                              ProviderConnectionState.CONNECTING})


def data_expected(epoch_ns: int) -> tuple[bool, str, bool]:
    """(expected, session label, calendar fallback used) for US equities at ``epoch_ns``.

    Past the holiday table the collection calendar reports CALENDAR_UNAVAILABLE; the weekday session
    is used instead so the watchdog keeps working, and escalation beyond a reconnect is withheld."""
    from .headless_supply import collection_session

    session = collection_session("moomoo", epoch_ns / _NS)
    if session["label"] != "CALENDAR_UNAVAILABLE":
        return bool(session["data_expected"]), str(session["label"]), False
    from ..market_sessions import ET, us_equity_session_label

    label = us_equity_session_label(datetime.fromtimestamp(epoch_ns / _NS, timezone.utc).astimezone(ET))
    return label in _EXPECTED_LABELS, label, True


class MoomooDataFlowWatchdog:
    def __init__(
        self,
        runtime: Any,
        *,
        clock: Callable[[], int] = time.time_ns,
        expected: Callable[[int], tuple[bool, str, bool]] = data_expected,
        escalate: bool | None = None,
        reconnect_join_seconds: float | None = None,
    ) -> None:
        self.runtime, self.clock, self.expected = runtime, clock, expected
        # Only a supervised collection-only process may end itself; a serving process has no restarter yet.
        self.escalate = os.environ.get("IMP_MARKET_SUPPLY_ENABLED") == "1" if escalate is None else escalate
        self.reconnect_join_seconds = reconnect_join_seconds
        self.state = "IDLE"
        self.fault: str | None = None
        self.silent_since_ns: int | None = None
        self.unrecoverable: str | None = None
        self.reconnect_times: list[int] = []
        self.unanswered_reconnects = 0
        self.checks = 0
        self.check_errors = 0
        self.events: deque[dict[str, Any]] = deque(maxlen=50)
        self._watch_since_ns: int | None = None
        self._last_action_ns: int | None = None
        self._budget_alarm_ns: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ lifecycle

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="moomoo-dataflow-watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def _loop(self) -> None:
        while not self._stop.wait(moomoo_watchdog_interval_seconds()):
            try:
                self.check()
            except Exception:  # noqa: BLE001 - the watchdog must outlive whatever it is watching
                self.check_errors += 1

    # ------------------------------------------------------------ judgement

    def _quotes_wanted(self) -> bool:
        rows = self.runtime.subscriptions.active_subscriptions()
        return any(row.get("capability") == "US_EQUITY_L1" for row in rows)

    def check(self) -> str:
        """One judgement; returns the resulting state. Safe to call from tests with an injected clock."""
        self.checks += 1
        feed = self.runtime.feed
        now = self.clock()
        if feed is None or feed._stop_event.is_set():
            return self._idle()
        expected, label, fallback = self.expected(now)
        if not expected or not self._quotes_wanted():
            return self._idle()
        if self._watch_since_ns is None:
            self._watch_since_ns = now
        threshold = int(moomoo_silence_seconds() * _NS)
        # Silence counts from the latest of: a receipt, the window opening, and the watchdog's own last action.
        baseline = max(t for t in (self._watch_since_ns, self._last_action_ns) if t is not None)
        latest = max(feed.last_receipt_ns or 0, baseline)
        silence = now - latest
        heartbeat = feed.loop_heartbeat_ns
        in_session = feed._quote_ctx is not None
        connection = feed._connection_thread
        fault = None
        if connection is not None and not connection.is_alive():
            fault = "CONNECTION_THREAD_DEAD"
        elif silence >= threshold:
            fault = "NO_RECEIPTS"
        elif in_session and heartbeat is not None and now - max(heartbeat, baseline) >= threshold:
            fault = "SESSION_LOOP_BLOCKED"
        if self.unrecoverable is not None:
            return self.state  # terminal: the supervising process restarts this one
        if fault is None:
            if self.state != "SILENT":
                self.state = "WATCHING"
            elif feed.last_receipt_ns is not None and feed.last_receipt_ns > (self._last_action_ns or self.silent_since_ns or 0):
                self._recovered(now)
                self.state = "WATCHING"
            # else: a reconnect was just made and has not delivered yet; still silent
            return self.state
        if self.state != "SILENT":
            self._alarm(now, fault, silence, label)
        self.fault = fault
        self._assert_degraded(fault, silence)
        if fault != "CONNECTION_THREAD_DEAD" and self.runtime.lifecycle.connection_state in _SELF_RECOVERING:
            return self.state  # the feed's own reconnect loop is already working on it
        self._act(now, feed, fault, fallback)
        return self.state

    def _idle(self) -> str:
        # Outside the window nothing is owed; the next window starts a fresh count.
        self._watch_since_ns = None
        self._last_action_ns = None
        if self.state == "SILENT":
            self._clear_degraded()
        if self.state != "UNRECOVERABLE":
            self.state, self.fault, self.silent_since_ns, self.unanswered_reconnects = "IDLE", None, None, 0
        return self.state

    def _alarm(self, now: int, fault: str, silence: int, label: str) -> None:
        self.state = "SILENT"
        self.silent_since_ns = now - silence
        self._event(now, SILENT_REASON, fault=fault, silent_seconds=silence // _NS, session=label)
        from .persistence import active_writer

        writer = active_writer()
        if writer is not None and "moomoo" in writer.sources:
            writer.gap(SILENT_REASON, received_ns=self.silent_since_ns)

    def _assert_degraded(self, fault: str, silence: int) -> None:
        lifecycle = self.runtime.lifecycle
        if lifecycle.connection_state in _SELF_RECOVERING:
            return  # already reported as not connected; that is the more specific truth
        lifecycle.connection_state = ProviderConnectionState.DEGRADED
        lifecycle.last_error = f"{SILENT_REASON}: {fault}, nothing received for {silence // _NS}s"

    def _clear_degraded(self) -> None:
        lifecycle = self.runtime.lifecycle
        if lifecycle.connection_state == ProviderConnectionState.DEGRADED and str(lifecycle.last_error or "").startswith(SILENT_REASON):
            lifecycle.connection_state = ProviderConnectionState.CONNECTED_DEGRADED
            lifecycle.last_error = None

    def _recovered(self, now: int) -> None:
        gap = (now - self.silent_since_ns) // _NS if self.silent_since_ns is not None else None
        self._event(now, "MOOMOO_FEED_RECOVERED", silent_seconds=gap, reconnects=self.unanswered_reconnects)
        self._clear_degraded()
        self.fault, self.silent_since_ns, self.unanswered_reconnects = None, None, 0

    def _act(self, now: int, feed: Any, fault: str, fallback: bool) -> None:
        self.reconnect_times = [t for t in self.reconnect_times if now - t < BUDGET_WINDOW_NS]
        spent = len(self.reconnect_times) >= moomoo_watchdog_restarts_per_hour()
        if self.unanswered_reconnects >= RECONNECTS_BEFORE_ESCALATION or spent:
            if self.escalate and not fallback:
                self.unrecoverable = UNRECOVERABLE_REASON
                self.state = "UNRECOVERABLE"
                self._event(now, UNRECOVERABLE_REASON, fault=fault, reconnects=self.unanswered_reconnects,
                            budget_spent=spent, action="PROCESS_RESTART_REQUESTED")
                return
            if spent:
                if self._budget_alarm_ns is None or now - self._budget_alarm_ns >= BUDGET_WINDOW_NS:
                    self._budget_alarm_ns = now  # once, then hourly, while waiting for the budget to renew
                    self._event(now, "MOOMOO_WATCHDOG_BUDGET_SPENT", fault=fault)
                return
        kwargs = {} if self.reconnect_join_seconds is None else {"join_seconds": self.reconnect_join_seconds}
        outcome = feed.force_reconnect(f"WATCHDOG_{fault}", **kwargs)
        self.reconnect_times.append(now)
        self.unanswered_reconnects += 1
        self._last_action_ns = now
        self._event(now, "MOOMOO_WATCHDOG_RECONNECT", fault=fault, outcome=outcome, attempt=self.unanswered_reconnects)

    # ------------------------------------------------------------ evidence

    def _event(self, now: int, event: str, **fields: Any) -> None:
        row = {"at_ns": now, "event": event, **fields}
        self.events.append(row)
        # The process log is the operator's timeline; reason codes and counts only.
        print(json.dumps({"event": "moomoo.feed_watchdog", **row}), file=sys.stderr, flush=True)

    def status(self) -> dict[str, Any]:
        feed = self.runtime.feed
        now = self.clock()
        receipt = getattr(feed, "last_receipt_ns", None)
        heartbeat = getattr(feed, "loop_heartbeat_ns", None)
        return {
            "state": self.state,
            "fault": self.fault,
            "unrecoverable": self.unrecoverable,
            "escalates_to_process_restart": self.escalate,
            "silence_threshold_seconds": moomoo_silence_seconds(),
            "receipt_age_seconds": None if receipt is None else round((now - receipt) / _NS, 1),
            "loop_heartbeat_age_seconds": None if heartbeat is None else round((now - heartbeat) / _NS, 1),
            "silent_since_ns": self.silent_since_ns,
            "reconnects_last_hour": len([t for t in self.reconnect_times if now - t < BUDGET_WINDOW_NS]),
            "reconnect_budget_per_hour": moomoo_watchdog_restarts_per_hour(),
            "forced_reconnects": getattr(feed, "forced_reconnects", 0),
            "abandoned_sessions": getattr(feed, "abandoned_sessions", 0),
            "checks": self.checks,
            "check_errors": self.check_errors,
            "alive": bool(self._thread and self._thread.is_alive()),
            "events": list(self.events)[-10:],
            "basis": "RECEIPTS_NOT_CONNECTION_STATE",
        }

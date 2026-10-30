"""IMP keeper: brings Moomoo OpenD, the collector and the platform back after a reboot or a frozen feed.

Owner decision 3 (2026-10-23): "Platform, collector and Moomoo OpenD restart unattended and the Paper
controller resumes; every restart is logged for review. Fake money only."

Every ``TICK_SECONDS`` it looks at the three in dependency order and brings back what is missing:

1. OpenD, the local Moomoo gateway. Healthy means the API port answers and the quote login is valid. The
   check runs in a child process with a timeout, because an SDK call can block for ever (2026-10-19..22).
   ``OPEND_FAILURES_BEFORE_RESTART`` unhealthy checks in a row, or no OpenD process at all, close it politely,
   then by force, and start it again; the GUI build logs in with its remembered session. This replaces the
   operator file collector/OPEND_WATCHDOG.py and keeps its constants.
2. The collector: ``collector/RUN_COLLECTOR.py run``, the PF-01 supervisor's operator entry. Started when no
   such process exists, unless ``collector/DISABLED`` says the owner stopped it, or its supervisor latched a
   block that has not expired.
3. The platform: ``RUN_IMP.py start``, which builds the platform's environment itself. Restarted when the API
   stops answering, or when its own feed watchdog reports the Moomoo feed unrecoverable while OpenD is healthy
   (only a fresh process clears a wedged SDK session). A platform that does not answer while a whole-store
   integrity check is visibly running (local_state/integrity_receipt.py) is waited for, not restarted: a restart
   would only start the same check again (2026-10-27). Also restarted, stopping it first, when the API answers but
   the Paper controller is armed and RUNNING with no live worker anywhere (``CONTROLLER_NOT_ALIVE``) for longer than
   ``CONTROLLER_DEAD_RESTART_SECONDS``: on 2026-10-29 /context answered all night while the controller was dead
   (AUD-045/046), and only a fresh process resumes it, through every start check of ``resume_on_startup``.
4. The store: once per night, inside ``STORE_VERIFY_WINDOW`` (US/Eastern), when the verified-store receipt is
   missing, invalid or older than ``STORE_VERIFY_FRESH_SECONDS``, tools/platform/verify_state_store.py checks the
   whole store read-only and renews the receipt, so a daytime restart only checks the critical tables. Once the
   market stream has its own file (imp-market-stream.sqlite3), both files are checked and the oldest receipt counts.

Every restart is bounded: a backoff between tries, a few tries per window, then a cool-off and a fresh
allowance. Nothing loops tightly and nothing gives up for good. Every action and its outcome goes to the
restart log (tools/platform/restart_log.py).

The keeper never arms, starts, pauses or stops the Paper controller. After a platform restart the controller
resumes itself if, and only if, it was armed and running (``resume_on_startup``); the keeper only records
what happened. It sets no execution gate: RUN_IMP.py builds that environment.

  imp_keeper.py run                long-running loop (scheduled task IMP-Keeper; one instance)
  imp_keeper.py once [--dry-run]   one pass; --dry-run starts nothing, writes nothing and reads no store
  imp_keeper.py status             the keeper's state file
  imp_keeper.py pause | resume     withhold or allow actions (deploys and planned stops pause first)
  imp_keeper.py stop               end a running keeper (its scheduled task starts a fresh one)
  imp_keeper.py report [--days N]  the restart log as a table
  imp_keeper.py opend-check        one OpenD health check (the child process the keeper runs)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.platform.local_launcher import VERIFY_WAIT_CAP_SECONDS  # noqa: E402
from tools.platform.restart_log import RestartLog, report  # noqa: E402

STATE_SCHEMA = "imp-keeper-state/1.0.0"
TICK_SECONDS = 30
OPEND_HOST, OPEND_PORT = "127.0.0.1", 11111
OPEND_EXE_NAME = "moomoo_OpenD.exe"
OPEND_CHECK_SECONDS = 60
OPEND_FAILURES_BEFORE_RESTART = 3
OPEND_CHECK_TIMEOUT_SECONDS = 45
OPEND_CLOSE_WAIT_SECONDS = 20
OPEND_LOGIN_WAIT_SECONDS = 240
OPEND_LOGIN_POLL_SECONDS = 10
PLATFORM_FAILURES_BEFORE_RESTART = 3
PLATFORM_FEED_CHECK_SECONDS = 60
# RUN_IMP.py start may legitimately wait out a whole-store integrity check; killing it then restarts the check.
PLATFORM_START_TIMEOUT_SECONDS = max(900, VERIFY_WAIT_CAP_SECONDS + 300)
PLATFORM_STOP_TIMEOUT_SECONDS = 180
API_BASE = "http://127.0.0.1:8766"
COLLECTOR_CONFIRM_SECONDS = 15
PAPER_OUTCOME_SECONDS = 600
CONTROLLER_LIVENESS_CHECK_SECONDS = 60
# Longer than the platform's own bounded boot-resume retry (900 s), so a process still retrying is not restarted.
CONTROLLER_DEAD_RESTART_SECONDS = 960
# The launcher's output, kept for the restart log (it was discarded; START_FAILED reasons were lost on 2026-10-29).
PLATFORM_START_LOG_MAX_BYTES = 2 * 1024 * 1024
# AUD-047 close-window guard. Off unless the owner creates .local/keeper/close-window-guard.enabled. The mandatory
# exits (EOD flatten 15:50-16:00 ET, next-open close of carried positions) run only inside a live controller cycle;
# on 2026-10-29 no cycle ran through the close because the platform was hung and the keeper was cooling off. Inside
# these windows a dead controller is restarted sooner, and one restart per window may use a reserve beyond the
# allowance. The keeper still only restarts the platform: the exits run in the controller's own cycle, under its
# own policy, risk checks and idempotent submit path; nothing here can place, size or cancel an order.
CLOSE_WINDOW_GUARD_FILE = "close-window-guard.enabled"
CLOSE_WINDOW_LEAD_SECONDS = 40 * 60  # from 40 min before the session close the platform last reported ...
CLOSE_WINDOW_TAIL_SECONDS = 5 * 60   # ... to 5 min before it (a restart needs ~2 min to be ready)
OPEN_WINDOW = ((9, 20), (9, 50))      # US/Eastern, Monday-Friday, only while carried positions are pending
CLOSE_WINDOW_DEAD_RESTART_SECONDS = 120
REBOOT_TOLERANCE_SECONDS = 120
# A component restarted this soon after a detected reboot is recorded with the reboot as its cause.
REBOOT_CAUSE_SECONDS = 900
BACKOFF_SECONDS = (60, 120, 240, 480)
COOL_OFF_SECONDS = 3600
# (restarts, window seconds) per component; OpenD keeps the old watchdog's 4 per 6 h.
ALLOWANCES = {"OPEND": (4, 6 * 3600), "COLLECTOR": (6, 3600), "PLATFORM": (4, 3600)}
# The PF-01 supervisor clears this latch by itself after its expiry (news/supervision.py); the others stay manual.
EXPIRING_LATCH = "PERSISTENT_CHILD_FAILURE"
# The nightly whole-store check: (start, end) as (hour, minute) US/Eastern, after the 20:00 close of extended hours
# and before the 04:00 pre-market.
STORE_VERIFY_WINDOW = ((20, 15), (3, 45))
STORE_VERIFY_FRESH_SECONDS = 20 * 3600
STORE_VERIFY_TIMEOUT_SECONDS = 3 * 3600
STORE_VERIFY_OUTCOMES = {0: "OK", 2: "INVALIDATED", 3: "BUSY", 4: "STORE_MISSING"}
NO_WINDOW = int(getattr(subprocess, "CREATE_NO_WINDOW", 0) or 0)
_COLLECTOR_COMMAND = re.compile(r"RUN_COLLECTOR\.py\"?\s+run\b", re.IGNORECASE)


@dataclass(frozen=True)
class KeeperPaths:
    """Where the keeper reads and writes. ``app`` holds the keeper's own state; ``portable`` holds the operator
    files it starts (RUN_IMP.py, collector/RUN_COLLECTOR.py) and the runtime they use."""

    app: Path
    portable: Path

    @property
    def state_dir(self) -> Path:
        return self.app / ".local" / "keeper"

    @property
    def state_file(self) -> Path:
        return self.state_dir / "state.json"

    @property
    def lock_file(self) -> Path:
        return self.state_dir / "keeper.lock"

    @property
    def paused_file(self) -> Path:
        return self.state_dir / "PAUSED"

    @property
    def stop_file(self) -> Path:
        return self.state_dir / "STOP"

    @property
    def log_file(self) -> Path:
        return self.state_dir / "restarts.jsonl"

    @property
    def collector_disabled(self) -> Path:
        return self.portable / "collector" / "DISABLED"

    @property
    def run_imp(self) -> Path:
        return self.portable / "RUN_IMP.py"

    @property
    def run_collector(self) -> Path:
        return self.portable / "collector" / "RUN_COLLECTOR.py"

    @property
    def serving_app(self) -> Path:
        return self.portable / "projects" / "integrated-market-platform"

    def python(self, *, windowless: bool = False) -> Path:
        candidate = self.portable / "runtime" / "python-3.11" / ("pythonw.exe" if windowless else "python.exe")
        return candidate if candidate.is_file() else Path(sys.executable)

    def site_packages(self) -> Path | None:
        """The backup's packages (moomoo SDK and friends), as RUN_IMP.py and the old watchdog find them."""
        try:
            config = json.loads((self.portable / "PORTABLE-CONFIG.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        path = self.portable.parent / str(config.get("backup_folder") or "") / \
            "payload/monorepo/projects/integrated-market-platform/.venv/Lib/site-packages"
        return path if path.is_dir() else None

    def state_directory(self) -> Path | None:
        """The canonical store directory from NORMAL-CONFIG.json (read-only use: supervision status only)."""
        try:
            config = json.loads((self.portable / "NORMAL-CONFIG.json").read_text(encoding="utf-8"))
            return (self.portable / str(config["state_directory"])).resolve()
        except (OSError, ValueError, KeyError, TypeError):
            return None

    @classmethod
    def discover(cls, portable: str | Path | None = None) -> "KeeperPaths":
        """The serving copy lives at <portable>/projects/integrated-market-platform, two levels below the
        portable root. A checkout elsewhere must name the portable root."""
        if portable:
            return cls(app=ROOT, portable=Path(portable).resolve())
        guess = ROOT.parents[1]
        if not (guess / "RUN_IMP.py").is_file():
            raise SystemExit("PORTABLE_ROOT_NOT_FOUND: pass --portable-root <folder holding RUN_IMP.py>")
        return cls(app=ROOT, portable=guess)


class Operations(Protocol):
    """What the keeper observes and does. Tests replace all of it; nothing here decides anything."""

    def boot_epoch(self) -> float | None: ...
    def opend_pids(self) -> list[int]: ...
    def opend_health(self) -> dict[str, Any]: ...
    def opend_close(self, pid: int, *, force: bool) -> None: ...
    def opend_launch(self) -> None: ...
    def collector_pids(self) -> list[int]: ...
    def collector_supervision(self) -> dict[str, Any]: ...
    def collector_spawn(self) -> int: ...
    def platform_answering(self) -> bool: ...
    def platform_health(self) -> dict[str, Any] | None: ...
    def platform_start(self, *, stop_first: bool) -> int: ...
    def paper_status(self) -> dict[str, Any] | None: ...
    def store_verifying(self) -> bool: ...
    def store_receipt_age(self) -> float | None: ...
    def store_verify_spawn(self) -> Any: ...
    def sleep(self, seconds: float) -> None: ...


class Allowance:
    """Restart allowance for one component: a backoff between tries, at most ``limit`` per ``window``, then a
    cool-off -- at least ``COOL_OFF_SECONDS``, and until the window has rolled -- after which a fresh allowance
    starts. Never a permanent block. Its state is the keeper's state."""

    def __init__(self, state: dict[str, Any], *, limit: int, window: float) -> None:
        self.state, self.limit, self.window = state, limit, window
        state.setdefault("attempts", [])
        state.setdefault("cool_off_until", 0.0)

    def check(self, now: float) -> tuple[bool, str | None]:
        """(may restart now, why not). ``BUDGET_SPENT`` is returned once, when the cool-off begins."""
        if now < self.state["cool_off_until"]:
            return False, "COOLING_OFF"
        # A clock set backwards must not keep old attempts inside the window for ever.
        attempts = [min(at, now) for at in self.state["attempts"] if now - min(at, now) < self.window]
        self.state["attempts"] = attempts
        if len(attempts) >= self.limit:
            self.state.update(attempts=[], cool_off_until=max(now + COOL_OFF_SECONDS, attempts[0] + self.window))
            return False, "BUDGET_SPENT"
        if attempts and now < attempts[-1] + BACKOFF_SECONDS[min(len(attempts), len(BACKOFF_SECONDS)) - 1]:
            return False, "BACKOFF"
        return True, None

    def spend(self, now: float) -> int:
        self.state["attempts"] = self.state["attempts"] + [now]
        return len(self.state["attempts"])


class _PrintedLog:
    """A dry run writes nothing: the entries it would have recorded are printed instead."""

    def __init__(self, clock: Callable[[], float]) -> None:
        self.clock, self.entries = clock, []

    def record(self, component: str, event: str, **fields: Any) -> dict[str, Any]:
        entry = {"component": component, "event": event, **fields}
        self.entries.append(entry)
        print(json.dumps({"would_record": entry}, sort_keys=True, default=str), flush=True)
        return entry


def _fresh_state() -> dict[str, Any]:
    return {"schema": STATE_SCHEMA, "boot_epoch": None, "heartbeat_epoch": None, "paused": False,
            "allowances": {name: {} for name in ALLOWANCES},
            "opend": {"failures": 0, "last_check": 0.0, "healthy": None, "down_since": None, "cause": None},
            "collector": {"down_since": None, "waiting_for": None, "disabled": False},
            "platform": {"failures": 0, "down_since": None, "last_feed_check": 0.0, "feed_wait_logged": False,
                         "verify_wait_logged": False, "last_controller_check": 0.0, "controller_dead_since": None,
                         "session_close_epoch": None, "session_date": None, "carry_pending": False,
                         "reserve_window": None},
            "store_verify": {"window": None, "started_at": None, "pid": None},
            "paper_watch": None}


class Keeper:
    def __init__(self, ops: Operations, paths: KeeperPaths, *, log: Any = None, clock: Callable[[], float] = time.time,
                 dry_run: bool = False) -> None:
        self.ops, self.paths, self.clock, self.dry_run = ops, paths, clock, dry_run
        self.log = log if log is not None else (_PrintedLog(clock) if dry_run else RestartLog(paths.log_file, clock=clock))
        self.state = _fresh_state() if dry_run else self._load()
        self.started = False
        self.reboot_at: float | None = None
        self._verify_process: Any = None
        self._platform_process: Any = None
        self.last_seen: float | None = None
        # A dry run reports what one failed observation would lead to; the real loop waits for the full count.
        self.opend_threshold = 1 if dry_run else OPEND_FAILURES_BEFORE_RESTART
        self.platform_threshold = 1 if dry_run else PLATFORM_FAILURES_BEFORE_RESTART

    # ------------------------------------------------------------------ state
    def _load(self) -> dict[str, Any]:
        state = _fresh_state()
        try:
            stored = json.loads(self.paths.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return state
        if isinstance(stored, dict) and stored.get("schema") == STATE_SCHEMA:
            for key, value in stored.items():
                if isinstance(state.get(key), dict) and isinstance(value, dict):
                    state[key].update(value)
                else:
                    state[key] = value
        return state

    def _save(self) -> None:
        if self.dry_run:
            return
        self.paths.state_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.paths.state_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.state, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.paths.state_file)

    def _allowance(self, component: str) -> Allowance:
        limit, window = ALLOWANCES[component]
        return Allowance(self.state["allowances"].setdefault(component, {}), limit=limit, window=window)

    def _cause(self, now: float, default: str) -> str:
        return "REBOOT" if self.reboot_at is not None and now - self.reboot_at < REBOOT_CAUSE_SECONDS else default

    def _down_since(self, now: float) -> float:
        # On the first pass after a reboot or a keeper outage, a component found down has been down at least since
        # the keeper last looked.
        return self.last_seen if self.last_seen is not None else now

    def _may_restart(self, component: str, now: float, cause: str) -> int | None:
        """The attempt number when a restart may go ahead now; None (with the budget recorded once) when not."""
        allowance = self._allowance(component)
        ready, why = allowance.check(now)
        if not ready:
            if why == "BUDGET_SPENT":
                self.log.record(component, "BUDGET_SPENT", cause=cause, outcome="COOLING_OFF",
                                retry_at_epoch=round(allowance.state["cool_off_until"], 1), limit=allowance.limit,
                                window_seconds=allowance.window)
            return None
        return allowance.spend(now)

    # ------------------------------------------------------------------ the pass
    def tick(self) -> dict[str, Any]:
        now = self.clock()
        if not self.started:
            self._on_start(now)
        paused = self.paths.paused_file.exists()
        if paused != bool(self.state.get("paused")):
            self.log.record("KEEPER", "PAUSED" if paused else "RESUMED", cause="OPERATOR")
            self.state["paused"] = paused
        summary: dict[str, Any] = {"paused": paused}
        if not paused:
            summary["opend_healthy"] = self._opend(now)
            summary["collector"] = self._collector(self.clock())
            summary["platform"] = self._platform(self.clock(), summary["opend_healthy"])
            self._paper(self.clock())
            summary["store_verify"] = self._store_verify(self.clock())
            self.last_seen = None  # only the first pass inherits the time the keeper was away
        self.state["heartbeat_epoch"] = self.clock()
        self._save()
        return summary

    def _on_start(self, now: float) -> None:
        self.started = True
        previous_boot, previous_beat = self.state.get("boot_epoch"), self.state.get("heartbeat_epoch")
        boot = self.ops.boot_epoch()
        if boot is not None and previous_boot is not None and abs(boot - float(previous_boot)) > REBOOT_TOLERANCE_SECONDS:
            down = boot - float(previous_beat) if previous_beat is not None else None
            self.log.record("PC", "REBOOT", cause="REBOOT", outcome="DETECTED", down_seconds=down, booted_at_epoch=round(boot, 1))
            self.reboot_at = now
        if previous_beat is not None and (self.reboot_at is not None or now - float(previous_beat) > 5 * TICK_SECONDS):
            self.last_seen = float(previous_beat)
        self.log.record("KEEPER", "STARTED", outcome="RUNNING" if not self.dry_run else "DRY_RUN", pid=os.getpid(),
                        last_seen_seconds_ago=None if previous_beat is None else round(now - float(previous_beat), 1))
        self.state["boot_epoch"] = boot

    # ------------------------------------------------------------------ OpenD
    def _opend(self, now: float) -> bool | None:
        s = self.state["opend"]
        if now - float(s.get("last_check") or 0) < OPEND_CHECK_SECONDS and s.get("healthy") is not None:
            return s["healthy"]
        s["last_check"] = now
        pids = self.ops.opend_pids()
        health = self.ops.opend_health() if pids else {"healthy": False, "reason": "OPEND_NOT_RUNNING"}
        if health.get("healthy"):
            if s.get("down_since") is not None:
                self.log.record("OPEND", "RECOVERED", cause=s.get("cause"), outcome="RECOVERED_WITHOUT_RESTART",
                                down_seconds=now - float(s["down_since"]))
            s.update(failures=0, healthy=True, down_since=None, cause=None)
            return True
        s["failures"] = int(s.get("failures") or 0) + 1
        s["healthy"], s["cause"] = False, str(health.get("reason") or "OPEND_UNHEALTHY")
        if s.get("down_since") is None:
            s["down_since"] = self._down_since(now)
        if s["failures"] < self.opend_threshold and s["cause"] != "OPEND_NOT_RUNNING":
            return False
        cause = self._cause(now, s["cause"])
        attempt = self._may_restart("OPEND", now, cause)
        if attempt is None:
            return False
        outcome, detail = self._restart_opend(pids)
        self.log.record("OPEND", "RESTART", cause=cause, outcome=outcome, attempt=attempt,
                        down_seconds=self.clock() - float(s["down_since"]), **detail)
        if outcome == "RECOVERED":
            s.update(failures=0, healthy=True, down_since=None, cause=None)
            return True
        return False

    def _restart_opend(self, pids: list[int]) -> tuple[str, dict[str, Any]]:
        if self.dry_run:
            return "DRY_RUN_NOT_STARTED", {"pids": len(pids)}
        for pid in pids:  # politely first, so OpenD can save its session, then by force
            self.ops.opend_close(pid, force=False)
        waited = 0
        while self.ops.opend_pids() and waited < OPEND_CLOSE_WAIT_SECONDS:
            self.ops.sleep(1)
            waited += 1
        for pid in self.ops.opend_pids():
            self.ops.opend_close(pid, force=True)
        self.ops.sleep(3)
        try:
            self.ops.opend_launch()
        except OSError as exc:
            return "LAUNCH_FAILED", {"error": type(exc).__name__, "message": str(exc)}
        health: dict[str, Any] = {}
        for elapsed in range(OPEND_LOGIN_POLL_SECONDS, OPEND_LOGIN_WAIT_SECONDS + 1, OPEND_LOGIN_POLL_SECONDS):
            self.ops.sleep(OPEND_LOGIN_POLL_SECONDS)
            health = self.ops.opend_health()
            if health.get("healthy"):
                return "RECOVERED", {"login_wait_seconds": elapsed}
        return "NOT_RECOVERED", {"last_reason": health.get("reason")}

    # ------------------------------------------------------------------ collector
    def _collector(self, now: float) -> str:
        s = self.state["collector"]
        if self.paths.collector_disabled.exists():
            if not s.get("disabled"):
                self.log.record("COLLECTOR", "LEFT_STOPPED", cause="DISABLED_BY_OWNER", outcome="NOT_STARTED")
                s["disabled"] = True
            return "DISABLED"
        s["disabled"] = False
        if self.ops.collector_pids():
            s.update(down_since=None, waiting_for=None)
            return "RUNNING"
        if s.get("down_since") is None:
            s["down_since"] = self._down_since(now)
        supervision = {} if self.dry_run else self.ops.collector_supervision()
        latched = supervision.get("latched")
        if latched:
            if latched != EXPIRING_LATCH:
                expires = None  # a rejected configuration needs the owner: restarting cannot help
            elif supervision.get("latched_at") is None:
                expires = now  # latched before expiry existed: the supervisor itself starts the clock on its next run
            else:
                expires = float(supervision["latched_at"]) + float(supervision.get("latch_expiry_seconds") or 0)
            if expires is None or now < expires:
                if s.get("waiting_for") != latched:
                    self.log.record("COLLECTOR", "WAITING", cause=str(latched), outcome="SUPERVISOR_LATCHED",
                                    clears_at_epoch=None if expires is None else round(expires, 1),
                                    manual_reset_needed=expires is None)
                    s["waiting_for"] = latched
                return "LATCHED"
        cause = self._cause(now, "PROCESS_GONE")
        attempt = self._may_restart("COLLECTOR", now, cause)
        if attempt is None:
            return "WAITING_FOR_ALLOWANCE"
        if self.dry_run:
            outcome, detail = "DRY_RUN_NOT_STARTED", {}
        else:
            try:
                pid = self.ops.collector_spawn()
            except OSError as exc:
                outcome, detail = "SPAWN_FAILED", {"error": type(exc).__name__, "message": str(exc)}
            else:
                self.ops.sleep(COLLECTOR_CONFIRM_SECONDS)
                outcome, detail = ("RUNNING" if self.ops.collector_pids() else "EXITED_AT_ONCE"), {"pid": pid}
        self.log.record("COLLECTOR", "START", cause=cause, outcome=outcome, attempt=attempt,
                        down_seconds=self.clock() - float(s["down_since"]), **detail)
        if outcome == "RUNNING":
            s.update(down_since=None, waiting_for=None)
        return outcome

    # ------------------------------------------------------------------ platform
    def _platform(self, now: float, opend_healthy: bool | None) -> str:
        s = self.state["platform"]
        pending = self._platform_pending(now)
        if pending is not None:
            return pending
        cause = None
        if self.ops.platform_answering():
            s["failures"] = 0
            if now - float(s.get("last_feed_check") or 0) >= PLATFORM_FEED_CHECK_SECONDS:
                s["last_feed_check"] = now
                flow = (self.ops.platform_health() or {}).get("data_flow") or {}
                if flow.get("state") == "UNRECOVERABLE":
                    if opend_healthy:
                        cause = "FEED_UNRECOVERABLE"
                    elif not s.get("feed_wait_logged"):
                        # Restarting the platform cannot help while OpenD itself is down; OpenD is brought back first.
                        self.log.record("PLATFORM", "WAITING", cause="FEED_UNRECOVERABLE", outcome="WAITING_FOR_OPEND")
                        s["feed_wait_logged"] = True
                else:
                    s["feed_wait_logged"] = False
            if cause is None:
                cause = self._controller_liveness(now)
            if cause is None:
                s["down_since"] = None
                return "ANSWERING"
            down_since = float(s.get("controller_dead_since") or now) if cause == "CONTROLLER_NOT_ALIVE" else now
        else:
            if s.get("down_since") is None:
                s["down_since"] = self._down_since(now)
            if self.ops.store_verifying():
                # The API (or the opener ahead of it) is reading the whole store; it answers when that ends.
                if not s.get("verify_wait_logged"):
                    self.log.record("PLATFORM", "WAITING", cause="NOT_ANSWERING", outcome="WAITING_FOR_STORE_VERIFY")
                    s["verify_wait_logged"] = True
                s["failures"] = 0
                return "WAITING_FOR_STORE_VERIFY"
            s["verify_wait_logged"] = False
            s["failures"] = int(s.get("failures") or 0) + 1
            if s["failures"] < self.platform_threshold:
                return "NOT_ANSWERING"
            cause, down_since = "NOT_ANSWERING", float(s["down_since"])
        restart_condition = cause
        cause = self._cause(now, cause)
        attempt = self._may_restart("PLATFORM", now, cause)
        if attempt is None:
            attempt = self._close_window_reserve(now, restart_condition)
        if attempt is None:
            return "WAITING_FOR_ALLOWANCE"
        # An answering API would make 'start' report "already running": both restart causes stop it first.
        stop_first = restart_condition in ("FEED_UNRECOVERABLE", "CONTROLLER_NOT_ALIVE")
        if self.dry_run:
            return self._platform_finished("DRY_RUN_NOT_STARTED", None, cause=cause, attempt=attempt,
                                           down_since=down_since, stop_first=stop_first)
        spawn = getattr(self.ops, "platform_start_spawn", None)
        if spawn is None:
            code = self.ops.platform_start(stop_first=stop_first)
            return self._platform_finished("READY" if code == 0 else "START_FAILED", code, cause=cause,
                                           attempt=attempt, down_since=down_since, stop_first=stop_first)
        # The start runs beside the loop: a platform start may wait hours for a whole-store scan, and OpenD and the
        # collector must stay watched meanwhile (each tick polls it in _platform_pending).
        try:
            self._platform_process = spawn(stop_first=stop_first)
        except OSError as exc:
            return self._platform_finished("START_FAILED", -2, cause=cause, attempt=attempt, down_since=down_since,
                                           stop_first=stop_first, error=type(exc).__name__)
        s["start"] = {"started_at": self.clock(), "pid": getattr(self._platform_process, "pid", None),
                      "attempt": attempt, "cause": cause, "down_since": down_since, "stop_first": stop_first}
        self.log.record("PLATFORM", "RESTART_STARTED", cause=cause, outcome="STARTING", attempt=attempt,
                        pid=s["start"]["pid"], stopped_first=stop_first)
        return "STARTING"

    def _controller_liveness(self, now: float) -> str | None:
        """``CONTROLLER_NOT_ALIVE`` once the Paper controller has been wanted running with no live worker anywhere for
        ``CONTROLLER_DEAD_RESTART_SECONDS``; otherwise None. Read only (the status GET), at most once a minute, and
        never while a restart's own resume outcome is still being awaited."""
        s = self.state["platform"]
        if self.state.get("paper_watch") or now - float(s.get("last_controller_check") or 0) < CONTROLLER_LIVENESS_CHECK_SECONDS:
            return None
        s["last_controller_check"] = now
        status = self.ops.paper_status()
        self._remember_session(now, status)
        if not controller_not_alive(status):
            if s.get("controller_dead_since") is not None:
                self.log.record("PAPER_CONTROLLER", "LIVENESS", cause="CONTROLLER_NOT_ALIVE", outcome="ALIVE_AGAIN",
                                dead_seconds=round(now - float(s["controller_dead_since"]), 1))
            s["controller_dead_since"] = None
            return None
        if s.get("controller_dead_since") is None:
            s["controller_dead_since"] = now
            self.log.record("PAPER_CONTROLLER", "LIVENESS", cause="CONTROLLER_NOT_ALIVE", outcome="OBSERVED",
                            restart_after_seconds=CONTROLLER_DEAD_RESTART_SECONDS)
            return None
        threshold = CLOSE_WINDOW_DEAD_RESTART_SECONDS if self._close_window(now) else CONTROLLER_DEAD_RESTART_SECONDS
        if now - float(s["controller_dead_since"]) < threshold:
            return None
        return "CONTROLLER_NOT_ALIVE"

    def _remember_session(self, now: float, status: dict[str, Any] | None) -> None:
        """The session close and carried positions as the platform last reported them (its calendar, early closes
        included), so the close window is still known while the platform itself is not answering."""
        if not isinstance(status, dict):
            return
        s = self.state["platform"]
        session = status.get("session") or {}
        minutes = session.get("minutes_to_close")
        if session.get("label") == "REGULAR" and isinstance(minutes, (int, float)):
            s.update(session_close_epoch=now + float(minutes) * 60, session_date=session.get("session_date"))
        s["carry_pending"] = bool((status.get("carry") or {}).get("pending"))

    def _close_window(self, now: float) -> str | None:
        """The current close-out window's key when the guard is enabled, else None."""
        if self.dry_run or not (self.paths.state_dir / CLOSE_WINDOW_GUARD_FILE).exists():
            return None
        s = self.state["platform"]
        close = s.get("session_close_epoch")
        if close and float(close) - CLOSE_WINDOW_LEAD_SECONDS <= now <= float(close) - CLOSE_WINDOW_TAIL_SECONDS:
            return f"CLOSE:{s.get('session_date')}"
        eastern = _eastern(now)
        (start_h, start_m), (end_h, end_m) = OPEN_WINDOW
        if (s.get("carry_pending")
                and (start_h, start_m) <= (eastern.hour, eastern.minute) < (end_h, end_m)):
            # A weekday can be a holiday. Use the versioned execution calendar, and fail closed
            # when its coverage or timezone support is unavailable. This import is opt-in only.
            try:
                source = str(ROOT / "src")
                if source not in sys.path:
                    sys.path.insert(0, source)
                from market_platform_foundation.nyse_calendar import is_trading_day
                if is_trading_day(eastern.date()):
                    return f"OPEN:{eastern.date().isoformat()}"
            except (ImportError, LookupError, OSError, ValueError):
                return None
        return None

    def _close_window_reserve(self, now: float, cause: str) -> int | None:
        """One restart per close-out window beyond the spent allowance, for a hung platform or a dead controller."""
        window = self._close_window(now)
        s = self.state["platform"]
        if window is None or cause not in ("NOT_ANSWERING", "CONTROLLER_NOT_ALIVE") or s.get("reserve_window") == window:
            return None
        s["reserve_window"] = window
        allowance = self._allowance("PLATFORM")
        allowance.state["attempts"] = allowance.state["attempts"] + [now]
        self.log.record("PLATFORM", "CLOSE_WINDOW_RESERVE", cause=cause, outcome="RESTARTING", window=window)
        return len(allowance.state["attempts"])

    def _platform_pending(self, now: float) -> str | None:
        """The state of a start this keeper launched: None when there is none, else STARTING or its outcome."""
        s = self.state["platform"]
        if self._platform_process is None:
            if s.pop("start", None) is not None:
                # Launched by an earlier keeper process, which cannot be polled from here; the normal checks resume.
                self.log.record("PLATFORM", "START_ORPHANED", outcome="NOT_TRACKED")
            return None
        start = s.get("start") or {}
        code = self._platform_process.poll()
        if code is None:
            if now - float(start.get("started_at") or now) < PLATFORM_START_TIMEOUT_SECONDS:
                return "STARTING"
            try:
                self._platform_process.kill()
            except OSError:
                pass
            code = -1
        self._platform_process = None
        s.pop("start", None)
        return self._platform_finished("READY" if code == 0 else "START_FAILED", int(code),
                                       cause=start.get("cause"), attempt=start.get("attempt"),
                                       down_since=float(start.get("down_since") or now),
                                       stop_first=bool(start.get("stop_first")))

    def _platform_finished(self, outcome: str, code: int | None, *, cause: str | None, attempt: int | None,
                           down_since: float, stop_first: bool, **extra: Any) -> str:
        s = self.state["platform"]
        self.log.record("PLATFORM", "RESTART", cause=cause, outcome=outcome, attempt=attempt,
                        down_seconds=self.clock() - down_since, exit_code=code, stopped_first=stop_first, **extra)
        if outcome == "READY":
            s.update(failures=0, down_since=None, last_feed_check=self.clock(), feed_wait_logged=False,
                     controller_dead_since=None, last_controller_check=self.clock())
            self.state["paper_watch"] = {"since": self.clock()}
        return outcome

    # ------------------------------------------------------------------ Paper outcome (read only)
    def _paper(self, now: float) -> None:
        watch = self.state.get("paper_watch")
        if not watch:
            return
        status = self.ops.paper_status()
        outcome, detail = paper_outcome(status, since=float(watch["since"]))
        if outcome is None and now - float(watch["since"]) < PAPER_OUTCOME_SECONDS:
            return
        if outcome is None:
            outcome = "STATUS_UNREADABLE" if status is None else "NOT_RESUMED_IN_TIME"
        self.log.record("PAPER_CONTROLLER", "RESUME", cause="PLATFORM_RESTART", outcome=outcome,
                        waited_seconds=round(now - float(watch["since"]), 1), **detail)
        self.state["paper_watch"] = None

    # ------------------------------------------------------------------ store integrity (nightly)
    def _store_verify(self, now: float) -> str:
        s = self.state.setdefault("store_verify", {"window": None, "started_at": None, "pid": None})
        if self._verify_process is not None:
            code = self._verify_process.poll()
            elapsed = now - float(s.get("started_at") or now)
            if code is None:
                if elapsed < STORE_VERIFY_TIMEOUT_SECONDS:
                    return "RUNNING"
                try:
                    self._verify_process.kill()
                except OSError:
                    pass
                outcome = "TIMED_OUT"
            else:
                outcome = STORE_VERIFY_OUTCOMES.get(int(code), "FAILED")
            self.log.record("STORE", "VERIFY", cause="NIGHTLY", outcome=outcome, exit_code=code,
                            elapsed_seconds=round(elapsed, 1), pid=s.get("pid"))
            self._verify_process = None
            s.update(started_at=None, pid=None)
            return outcome
        window = store_verify_window(now)
        if window is None:
            return "OUTSIDE_WINDOW"
        if s.get("window") == window:
            return "DONE_THIS_WINDOW"
        age = self.ops.store_receipt_age()
        if age is not None and age < STORE_VERIFY_FRESH_SECONDS:
            return "RECEIPT_FRESH"
        if self.dry_run:
            return "DRY_RUN_NOT_STARTED"
        s["window"] = window  # at most one try per night, whatever its outcome
        try:
            self._verify_process = self.ops.store_verify_spawn()
        except OSError as exc:
            self.log.record("STORE", "VERIFY", cause="NIGHTLY", outcome="SPAWN_FAILED", error=type(exc).__name__,
                            message=str(exc))
            return "SPAWN_FAILED"
        s.update(started_at=now, pid=getattr(self._verify_process, "pid", None))
        self.log.record("STORE", "VERIFY_STARTED", cause="RECEIPT_STALE" if age is None else "RECEIPT_AGING",
                        outcome="RUNNING", pid=s["pid"], receipt_age_seconds=None if age is None else round(age, 1))
        return "STARTED"

    # ------------------------------------------------------------------ loop
    def run(self, stop: threading.Event | None = None) -> int:
        stop = stop or threading.Event()
        while not stop.is_set() and not self.paths.stop_file.exists():
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001 - one failed pass is recorded; the keeper itself carries on
                try:
                    self.log.record("KEEPER", "TICK_FAILED", outcome="CONTINUING", error=type(exc).__name__, message=str(exc))
                except Exception:  # noqa: BLE001
                    pass
            stop.wait(TICK_SECONDS)
        self.log.record("KEEPER", "STOPPED", cause="STOP_FILE" if self.paths.stop_file.exists() else "STOP_REQUESTED")
        return 0


def _eastern(now: float):
    from datetime import datetime

    try:
        from zoneinfo import ZoneInfo

        return datetime.fromtimestamp(now, ZoneInfo("America/New_York"))
    except Exception:  # noqa: BLE001 - no tz database: this PC keeps Eastern time
        return datetime.fromtimestamp(now)


def store_verify_window(now: float) -> str | None:
    """The evening date (YYYY-MM-DD) of the nightly window ``now`` falls in, or None outside it."""
    from datetime import timedelta

    local = _eastern(now)
    (start_hour, start_minute), (end_hour, end_minute) = STORE_VERIFY_WINDOW
    minutes = local.hour * 60 + local.minute
    if minutes >= start_hour * 60 + start_minute:
        return local.date().isoformat()
    if minutes < end_hour * 60 + end_minute:
        return (local.date() - timedelta(days=1)).isoformat()
    return None


def paper_outcome(status: dict[str, Any] | None, *, since: float) -> tuple[str | None, dict[str, Any]]:
    """What the Paper controller did after a platform restart, from its read-only status. None while undecided."""
    if not isinstance(status, dict):
        return None, {}
    if status.get("status") == "NOT_CONFIGURED":
        return "NOT_CONFIGURED", {}
    if status.get("emergency"):
        return "EMERGENCY_STOPPED", {}
    if not status.get("armed"):
        return "NOT_ARMED", {}
    if status.get("desired_state") != "RUNNING":
        return "NOT_RUNNING_BEFORE_RESTART", {"desired_state": status.get("desired_state")}
    liveness = status.get("liveness") or {}
    run_id = (status.get("run") or {}).get("run_id")
    if liveness.get("owner") == "THIS_PROCESS" and liveness.get("worker_alive"):
        return "RESUMED", {"run_id": run_id}
    error = liveness.get("last_error") or {}
    if error.get("code") and _after(error.get("at"), since):
        return "REFUSED", {"reason": error.get("code")}
    return None, {}


def controller_not_alive(status: dict[str, Any] | None) -> bool:
    """Armed, wanted RUNNING, not latched, and the platform itself reports no live worker anywhere.

    ``RUNNING_ELSEWHERE`` (another live owner holds the lease) is not this: restarting would not help."""
    if not isinstance(status, dict) or not status.get("armed") or status.get("emergency"):
        return False
    if status.get("desired_state") != "RUNNING":
        return False
    codes = {blocker.get("code") for blocker in status.get("blockers") or [] if isinstance(blocker, dict)}
    return "CONTROLLER_NOT_ALIVE" in codes


def _after(iso: Any, since: float) -> bool:
    from datetime import datetime

    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp() >= since - 1
    except ValueError:
        return False


# ---------------------------------------------------------------------- the real machine
class WindowsOperations:
    """The keeper's eyes and hands on this PC. Every call is bounded by a timeout."""

    def __init__(self, paths: KeeperPaths) -> None:
        self.paths = paths

    def boot_epoch(self) -> float | None:
        if os.name == "nt":
            import ctypes

            tick = ctypes.windll.kernel32.GetTickCount64
            tick.restype = ctypes.c_ulonglong
            return time.time() - tick() / 1000.0
        try:
            return time.time() - float(Path("/proc/uptime").read_text().split()[0])
        except (OSError, ValueError, IndexError):
            return None

    def opend_pids(self) -> list[int]:
        try:
            out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {OPEND_EXE_NAME}", "/FO", "CSV", "/NH"],
                                 capture_output=True, text=True, timeout=15, creationflags=NO_WINDOW).stdout
        except (OSError, subprocess.TimeoutExpired):
            return []
        return [int(line.split('","')[1]) for line in out.splitlines() if line.startswith(f'"{OPEND_EXE_NAME}"')]

    def _child_env(self) -> dict[str, str]:
        env = dict(os.environ)
        parts = [str(self.paths.app / "src"), str(self.paths.app)]
        packages = self.paths.site_packages()
        if packages is not None:
            parts.append(str(packages))
        env["PYTHONPATH"] = os.pathsep.join(parts)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return env

    def opend_health(self) -> dict[str, Any]:
        # A child process, so an SDK call that never returns costs a timeout, not the keeper.
        try:
            result = subprocess.run([str(self.paths.python()), "-B", str(Path(__file__).resolve()), "opend-check"],
                                    capture_output=True, text=True, timeout=OPEND_CHECK_TIMEOUT_SECONDS,
                                    env=self._child_env(), cwd=str(self.paths.app), creationflags=NO_WINDOW)
        except subprocess.TimeoutExpired:
            return {"healthy": False, "reason": "OPEND_CHECK_TIMEOUT"}
        except OSError as exc:
            return {"healthy": False, "reason": f"OPEND_CHECK_ERROR:{type(exc).__name__}"}
        for line in reversed(result.stdout.splitlines()):
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict) and "healthy" in value:
                return value
        return {"healthy": False, "reason": "OPEND_CHECK_UNREADABLE"}

    def opend_close(self, pid: int, *, force: bool) -> None:
        command = ["taskkill", *(["/F"] if force else []), "/PID", str(int(pid))]
        try:
            subprocess.run(command, capture_output=True, timeout=30, creationflags=NO_WINDOW)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def opend_launch(self) -> None:
        override = os.environ.get("IMP_OPEND_EXE")
        if override:
            exe = Path(override)
        else:
            from tools.moomoo.check_live_environment import opend_executable_path

            exe = opend_executable_path()
        if not exe.is_file():
            raise FileNotFoundError(f"OPEND_NOT_INSTALLED: {exe}")
        # The flags collector/OPEND_WATCHDOG.py used: OpenD outlives the keeper and opens its own window.
        flags = int(getattr(subprocess, "DETACHED_PROCESS", 0)) | int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        subprocess.Popen([str(exe)], cwd=str(exe.parent), close_fds=True, creationflags=flags)

    def collector_pids(self) -> list[int]:
        if os.name != "nt":
            return []
        script = ("Get-CimInstance Win32_Process -Filter \"Name='python.exe' OR Name='pythonw.exe'\" | "
                  "ForEach-Object { \"$($_.ProcessId)`t$($_.CommandLine)\" }")
        try:
            out = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                                 capture_output=True, text=True, timeout=30, creationflags=NO_WINDOW).stdout
        except (OSError, subprocess.TimeoutExpired):
            return []
        pids = []
        for line in out.splitlines():
            pid, _, command = line.partition("\t")
            if pid.strip().isdigit() and _COLLECTOR_COMMAND.search(command):
                pids.append(int(pid))
        return pids

    def collector_supervision(self) -> dict[str, Any]:
        directory = self.paths.state_directory()
        if directory is None:
            return {}
        if str(self.paths.app / "src") not in sys.path:
            sys.path.insert(0, str(self.paths.app / "src"))
        from market_platform_foundation.news.supervision import supervision_status  # read-only (mode=ro)

        return supervision_status({"IMP_STATE_DIR": str(directory)})

    def collector_spawn(self) -> int:
        # The same command the IMP-PF01-Collector task ran; RUN_COLLECTOR.py builds its own environment and log.
        flags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) | NO_WINDOW
        process = subprocess.Popen([str(self.paths.python(windowless=True)), "-B", str(self.paths.run_collector), "run"],
                                   cwd=str(self.paths.serving_app), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, close_fds=True, creationflags=flags)
        process._child_created = False  # type: ignore[attr-defined]  # detached on purpose; never reaped here
        return int(process.pid)

    def _get(self, path: str, timeout: float) -> tuple[int, bytes] | None:
        request = urllib.request.Request(API_BASE + path, headers={"User-Agent": "imp-keeper/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return int(response.status), response.read()
        except urllib.error.HTTPError as exc:
            return int(exc.code), b""
        except (OSError, ValueError):
            return None

    def platform_answering(self) -> bool:
        answer = self._get("/context", 10)
        return answer is not None and 200 <= answer[0] < 500

    def _json(self, path: str, timeout: float) -> dict[str, Any] | None:
        answer = self._get(path, timeout)
        if answer is None or answer[0] != 200:
            return None
        try:
            value = json.loads(answer[1].decode("utf-8"))
        except ValueError:
            return None
        return value if isinstance(value, dict) else None

    def platform_health(self) -> dict[str, Any] | None:
        return self._json("/provider/health", 20)

    def paper_status(self) -> dict[str, Any] | None:
        return self._json("/paper/automation/status", 15)

    def platform_start(self, *, stop_first: bool) -> int:
        # RUN_IMP.py strips inherited IMP_* settings and builds the platform's own; it keeps only this marker,
        # which lets the serving feed watchdog report an unrecoverable session for the keeper to restart.
        env = dict(os.environ, IMP_PLATFORM_RESTARTER="keeper", PYTHONDONTWRITEBYTECODE="1")
        python = str(self.paths.python())
        try:
            if stop_first:
                subprocess.run([python, "-B", str(self.paths.run_imp), "stop"], cwd=str(self.paths.portable), env=env,
                               capture_output=True, timeout=PLATFORM_STOP_TIMEOUT_SECONDS, creationflags=NO_WINDOW)
            result = subprocess.run([python, "-B", str(self.paths.run_imp), "start", "--no-browser"],
                                    cwd=str(self.paths.portable), env=env, capture_output=True,
                                    timeout=PLATFORM_START_TIMEOUT_SECONDS, creationflags=NO_WINDOW)
        except subprocess.TimeoutExpired:
            return -1
        except OSError:
            return -2
        return int(result.returncode)

    def platform_start_spawn(self, *, stop_first: bool) -> subprocess.Popen:
        """``RUN_IMP start`` as a child the keeper polls each tick (Keeper._platform_pending), instead of waiting
        inside one tick for up to PLATFORM_START_TIMEOUT_SECONDS. A requested stop still runs first, bounded."""
        env = dict(os.environ, IMP_PLATFORM_RESTARTER="keeper", PYTHONDONTWRITEBYTECODE="1")
        python = str(self.paths.python())
        if stop_first:
            try:
                subprocess.run([python, "-B", str(self.paths.run_imp), "stop"], cwd=str(self.paths.portable), env=env,
                               capture_output=True, timeout=PLATFORM_STOP_TIMEOUT_SECONDS, creationflags=NO_WINDOW)
            except subprocess.TimeoutExpired:
                pass  # the start below reports whatever state the stop left
        # No pipes: nobody reads them while the child runs, and a full pipe would stall it. The output goes to a
        # bounded file instead of DEVNULL, so a START_FAILED keeps its reason (CA-9).
        output = self._start_log()
        try:
            return subprocess.Popen([python, "-B", str(self.paths.run_imp), "start", "--no-browser"],
                                    cwd=str(self.paths.portable), env=env, stdin=subprocess.DEVNULL,
                                    stdout=output, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        finally:
            output.close()  # the child holds its own handle

    def _start_log(self) -> Any:
        path = self.paths.state_dir / "platform-start.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if path.stat().st_size > PLATFORM_START_LOG_MAX_BYTES:
                os.replace(path, path.with_suffix(".log.1"))
        except OSError:
            pass
        output = open(path, "ab")
        stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        output.write(f"\n=== {stamp} RUN_IMP.py start (keeper) ===\n".encode("utf-8"))
        output.flush()
        return output

    def _store(self) -> Path | None:
        directory = self.paths.state_directory()
        if directory is None:
            return None
        if str(self.paths.app / "src") not in sys.path:
            sys.path.insert(0, str(self.paths.app / "src"))
        return directory / "imp-state.sqlite3"

    def _stores(self) -> list[Path]:
        """The state store, and the market stream store beside it once the stream has been split out."""
        store = self._store()
        if store is None:
            return []
        stream = store.with_name("imp-market-stream.sqlite3")
        return [store, stream] if stream.is_file() else [store]

    def store_verifying(self) -> bool:
        from market_platform_foundation.local_state.integrity_receipt import verification_in_progress

        return any(verification_in_progress(store) is not None for store in self._stores())

    def store_receipt_age(self) -> float | None:
        """Seconds since the oldest store last checked ok, while every receipt still stands; None otherwise."""
        stores = self._stores()
        if not stores:
            return None
        from market_platform_foundation.local_state import integrity_receipt as receipts

        ages = []
        for store in stores:
            receipt = receipts.read_receipt(store)
            if receipt is None or receipts.receipt_problem(store, receipt=receipt) is not None:
                return None
            ages.append(max(0.0, time.time() - float(receipt["checked_at_epoch"])))
        return max(ages)

    def store_verify_spawn(self) -> Any:
        stores = self._stores()
        if not stores:
            raise FileNotFoundError("STATE_DIRECTORY_UNKNOWN")
        script = self.paths.app / "tools" / "platform" / "verify_state_store.py"
        targets = [arg for store in stores for arg in ("--store", str(store))]
        return subprocess.Popen([str(self.paths.python(windowless=True)), "-B", str(script), *targets,
                                 "--label", "imp-keeper-nightly"], cwd=str(self.paths.app), env=self._child_env(),
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=NO_WINDOW)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def opend_check(host: str = OPEND_HOST, port: int = OPEND_PORT) -> dict[str, Any]:
    """One health check, run in the keeper's child process. Quote context only; never a trade context."""
    try:
        socket.create_connection((host, port), timeout=3).close()
    except OSError:
        return {"healthy": False, "reason": "API_PORT_REFUSED"}
    from tools.moomoo.check_live_environment import _quote_context_check

    result = _quote_context_check(host, port)
    if not result.get("ok"):
        return {"healthy": False, "reason": "GLOBAL_STATE_ERROR", "detail": str(result.get("error") or "")[:200]}
    logged_in = str(result.get("qot_logined")).lower() in ("true", "1")
    return {"healthy": logged_in, "reason": None if logged_in else "QUOTE_NOT_LOGGED_IN", "server_ver": result.get("server_ver")}


class InstanceLock:
    """One keeper per PC: an OS lock on one byte of the lock file, released when the process ends."""

    def __init__(self, path: Path) -> None:
        self.path, self.handle = path, None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+")
        try:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            handle.close()
            return False
        self.handle = handle
        return True

    def release(self) -> None:
        if self.handle is not None:
            self.handle.close()
            self.handle = None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="IMP keeper: unattended restart of OpenD, collector and platform.")
    parser.add_argument("--portable-root", default=os.environ.get("IMP_PORTABLE_ROOT"))
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("run")
    once = sub.add_parser("once")
    once.add_argument("--dry-run", action="store_true")
    for name in ("status", "pause", "resume", "stop", "opend-check"):
        sub.add_parser(name)
    report_parser = sub.add_parser("report")
    report_parser.add_argument("--days", type=float, default=None)
    args = parser.parse_args(argv)
    if args.action == "opend-check":
        print(json.dumps(opend_check()), flush=True)
        return 0
    paths = KeeperPaths.discover(args.portable_root)
    if args.action == "report":
        print(report(RestartLog(paths.log_file).read(args.days)))
        return 0
    if args.action == "status":
        try:
            print(paths.state_file.read_text(encoding="utf-8"))
        except OSError:
            print(json.dumps({"state": "NEVER_RUN"}))
        print(json.dumps({"paused": paths.paused_file.exists(), "stop_requested": paths.stop_file.exists()}))
        return 0
    if args.action in ("pause", "resume", "stop"):
        paths.state_dir.mkdir(parents=True, exist_ok=True)
        target = paths.stop_file if args.action == "stop" else paths.paused_file
        if args.action == "resume":
            target.unlink(missing_ok=True)
        else:
            target.write_text(time.strftime("%Y-%m-%dT%H:%M:%S%z") + "\n", encoding="utf-8")
        print(json.dumps({"action": args.action, "paused": paths.paused_file.exists()}))
        return 0
    if args.action == "once" and args.dry_run:
        keeper = Keeper(WindowsOperations(paths), paths, dry_run=True)
        print(json.dumps({"observed": keeper.tick()}, default=str), flush=True)
        return 0
    if sys.stdout is None:  # pythonw: nowhere to print; the restart log is the record
        sys.stdout = sys.stderr = open(os.devnull, "w", encoding="utf-8")
    lock = InstanceLock(paths.lock_file)
    if not lock.acquire():
        print(json.dumps({"state": "NOT_STARTED", "reason": "ANOTHER_KEEPER_RUNNING"}))
        return 0
    try:
        keeper = Keeper(WindowsOperations(paths), paths)
        if args.action == "once":
            print(json.dumps({"observed": keeper.tick()}, default=str))
            return 0
        paths.stop_file.unlink(missing_ok=True)
        return keeper.run()
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())

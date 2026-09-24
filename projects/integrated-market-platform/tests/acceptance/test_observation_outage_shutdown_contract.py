"""SOFTWARE_CONTROLLED contract for outage intervals and shutdown determinism.

Not market evidence. Disposable state only. Execution stays BLOCKED.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.platform.operator_diagnostics.campaign_supervision import (  # noqa: E402
    CampaignOwnership,
    ProcessIdentity,
    active_outage_records,
    read_outage_records,
    write_heartbeat,
    write_ownership,
)
from tools.platform.detached_process import spawn_detached  # noqa: E402

SUPERVISOR = ROOT / "tools" / "platform" / "campaign_supervisor.py"


def _utc(offset_seconds: float = 0.0) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    ).isoformat().replace("+00:00", "Z")


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT), env.get("PYTHONPATH", "")])
    env["PYTHONUNBUFFERED"] = "1"
    return subprocess.run(
        [sys.executable, str(SUPERVISOR), *argv],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )


def _armed(state: Path, *, children: list[ProcessIdentity] | None = None) -> None:
    ownership = CampaignOwnership(
        campaign_id="SW-OUTAGE-CONTRACT",
        runtime_sha="cccccccccccccccccccccccccccccccccccccccc",
        supervisor_pid=os.getpid(),
        supervisor_identity="imp-campaign-supervisor",
        child_processes=children
        or [
            ProcessIdentity(role="poller", pid=os.getpid()),
            ProcessIdentity(role="api", pid=os.getpid()),
        ],
        arm_timestamp_utc=_utc(-30),
        observation_window_id="OBS-SW",
        expected_poll_cadence_seconds=30.0,
        expected_next_cycle_utc=_utc(30),
        state_directory=str(state),
        arm_status="ARMED_RUNNING",
        required_roles=["supervisor", "poller", "api"],
    )
    write_ownership(ownership)
    write_heartbeat(
        state,
        {
            "last_heartbeat_utc": _utc(),
            "last_successful_poll_utc": _utc(),
            "application_ready": True,
            "stale_after_seconds": 90,
            "synthetic_poll_generated": False,
        },
    )


class OutageShutdownContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="imp-outage-contract-")
        self.state = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def _rows(self) -> list[dict]:
        return read_outage_records(self.state)

    def test_failure_open_is_idempotent_and_names_dead_role(self) -> None:
        _armed(self.state, children=[ProcessIdentity(role="api", pid=os.getpid())])
        first = _run("status", "--state-dir", str(self.state))
        self.assertEqual(first.returncode, 2, msg=first.stdout + first.stderr)
        view = json.loads(first.stdout)
        self.assertEqual(view["outage_ledger"], "APPENDED")
        self.assertEqual(view["status"], "PROCESS_DEAD")
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["interval_end_utc"])
        self.assertEqual(rows[0]["root_cause"], "POLL_PROCESS_DEAD")
        self.assertEqual(rows[0]["record_kind"], "INTERVAL_OPEN")
        second = _run("status", "--state-dir", str(self.state))
        self.assertEqual(json.loads(second.stdout)["outage_ledger"], "OPEN_UNCHANGED")
        self.assertEqual(len(self._rows()), 1)

    def test_recovery_closes_without_rewriting_the_open_row(self) -> None:
        _armed(self.state, children=[ProcessIdentity(role="api", pid=os.getpid())])
        self.assertEqual(_run("status", "--state-dir", str(self.state)).returncode, 2)
        opened = self._rows()[0]
        _armed(self.state)
        recovered = _run("status", "--state-dir", str(self.state))
        self.assertEqual(recovered.returncode, 0, msg=recovered.stdout + recovered.stderr)
        view = json.loads(recovered.stdout)
        self.assertEqual(view["outage_ledger"], "CLOSED")
        self.assertEqual(view["status"], "HEALTHY")
        self.assertEqual(view["active_outages"], [])
        rows = self._rows()
        self.assertEqual(rows[0]["interval_end_utc"], opened["interval_end_utc"])
        self.assertIsNone(rows[0]["interval_end_utc"])
        close = rows[1]
        self.assertEqual(close["record_kind"], "INTERVAL_CLOSED")
        self.assertEqual(close["close_reason"], "RECOVERED")
        self.assertTrue(close["recovered"])
        self.assertEqual(close["closes_outage_id"], opened["outage_id"])
        self.assertTrue(close["interval_end_utc"])
        again = _run("status", "--state-dir", str(self.state))
        self.assertEqual(json.loads(again.stdout)["outage_ledger"], "NO_ACTIVE_OUTAGE")
        self.assertEqual(len(self._rows()), 2)

    def test_later_failure_is_a_new_interval(self) -> None:
        self.test_recovery_closes_without_rewriting_the_open_row()
        _armed(self.state, children=[ProcessIdentity(role="poller", pid=os.getpid())])
        failed = _run("status", "--state-dir", str(self.state))
        self.assertEqual(failed.returncode, 2)
        rows = self._rows()
        opens = [row for row in rows if row.get("record_kind") == "INTERVAL_OPEN"]
        self.assertEqual(len(opens), 2)
        self.assertEqual(opens[1]["root_cause"], "API_UNAVAILABLE")
        self.assertEqual(len(active_outage_records(rows)), 1)

    def test_shutdown_terminates_open_outage_without_claiming_recovery(self) -> None:
        _armed(self.state, children=[ProcessIdentity(role="api", pid=os.getpid())])
        self.assertEqual(_run("status", "--state-dir", str(self.state)).returncode, 2)
        shutdown = _run("shutdown", "--state-dir", str(self.state), "--rth-close")
        self.assertEqual(shutdown.returncode, 0, msg=shutdown.stdout + shutdown.stderr)
        payload = json.loads(shutdown.stdout)
        self.assertEqual(payload["status"], "RTH_CLOSE_SHUTDOWN")
        self.assertGreaterEqual(payload["active_outages_terminated"], 1)
        rows = self._rows()
        close = [row for row in rows if row.get("record_kind") == "INTERVAL_CLOSED"][0]
        self.assertEqual(close["close_reason"], "CAMPAIGN_TERMINATED")
        self.assertFalse(close["recovered"])
        self.assertEqual(close["termination_reason"], "SHUTDOWN_TERMINATED")
        again = _run("shutdown", "--state-dir", str(self.state), "--rth-close")
        self.assertEqual(again.returncode, 0)
        self.assertEqual(len([row for row in self._rows() if row.get("record_kind") == "INTERVAL_CLOSED"]), 1)
        status = json.loads(_run("status", "--state-dir", str(self.state)).stdout)
        self.assertEqual(status["status"], "NOT_APPLICABLE")
        self.assertFalse(status["progress"].get("outage"))
        self.assertEqual(status["active_outages"], [])

    def test_malformed_ledger_fails_closed(self) -> None:
        _armed(self.state)
        path = self.state / "campaign-supervision" / "outages.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"record_kind":"INTERVAL_OPEN"}\nnot-json\n', encoding="utf-8")
        status = _run("status", "--state-dir", str(self.state))
        self.assertEqual(status.returncode, 2, msg=status.stdout + status.stderr)
        view = json.loads(status.stdout)
        self.assertEqual(view["outage_ledger"], "MALFORMED")
        self.assertIn("MALFORMED_LINE:2", view["outage_ledger_defects"])
        self.assertTrue(path.read_text(encoding="utf-8").endswith("not-json\n"))

    def test_idle_poller_wakes_on_shutdown_without_a_new_cycle(self) -> None:
        arm = _run(
            "arm",
            "--state-dir",
            str(self.state),
            "--campaign-id",
            "SW-SHUTDOWN-WAKE",
            "--observation-window-id",
            "OBS-SW",
            "--skip-environment-preflight",
            "--poll-cadence-seconds",
            "30",
            "--required-roles",
            "supervisor",
        )
        self.assertEqual(arm.returncode, 0, msg=arm.stdout + arm.stderr)
        proc = subprocess.Popen(
            [
                sys.executable,
                str(SUPERVISOR),
                "poll-loop",
                "--state-dir",
                str(self.state),
                "--poll-cadence-seconds",
                "30",
                "--iterations",
                "3",
            ],
            cwd=str(ROOT),
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
                "PYTHONUNBUFFERED": "1",
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(proc.kill)
        deadline = time.time() + 8
        marker = self.state / "campaign-supervision" / "poller.alive"
        while time.time() < deadline and not marker.is_file():
            time.sleep(0.05)
        self.assertTrue(marker.is_file())
        attempts_before = self.state / "campaign-supervision" / "poll-attempts.jsonl"
        before = attempts_before.read_text(encoding="utf-8").count("\n") if attempts_before.is_file() else 0
        issued = time.perf_counter()
        shutdown = _run("shutdown", "--state-dir", str(self.state))
        self.assertEqual(shutdown.returncode, 0, msg=shutdown.stdout + shutdown.stderr)
        proc.wait(timeout=5)
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            proc.stderr.close()
        elapsed = time.perf_counter() - issued
        self.assertLess(elapsed, 2.0, msg=f"poller exit latency {elapsed:.3f}s")
        self.assertEqual(proc.returncode, 0)
        after = attempts_before.read_text(encoding="utf-8").count("\n")
        self.assertLessEqual(after, before + 1)
        heartbeat = json.loads(
            (self.state / "campaign-supervision" / "heartbeat.json").read_text(encoding="utf-8")
        )
        self.assertEqual(heartbeat["phase"], "CLEAN_SHUTDOWN")
        refused = _run("heartbeat", "--state-dir", str(self.state))
        self.assertEqual(refused.returncode, 0)
        self.assertFalse(json.loads(refused.stdout)["heartbeat_advanced"])
        self.assertEqual(
            json.loads((self.state / "campaign-supervision" / "heartbeat.json").read_text(encoding="utf-8"))["phase"],
            "CLEAN_SHUTDOWN",
        )

    def test_in_flight_block_interrupts_before_receipt(self) -> None:
        arm = _run(
            "arm",
            "--state-dir",
            str(self.state),
            "--campaign-id",
            "SW-INFLIGHT",
            "--observation-window-id",
            "OBS-SW",
            "--skip-environment-preflight",
            "--required-roles",
            "supervisor",
        )
        self.assertEqual(arm.returncode, 0, msg=arm.stdout + arm.stderr)
        proc = subprocess.Popen(
            [
                sys.executable,
                str(SUPERVISOR),
                "poll-loop",
                "--state-dir",
                str(self.state),
                "--iterations",
                "1",
                "--block-seconds",
                "30",
                "--poll-cadence-seconds",
                "30",
            ],
            cwd=str(ROOT),
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
                "PYTHONUNBUFFERED": "1",
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(proc.kill)
        time.sleep(0.4)
        issued = time.perf_counter()
        _run("shutdown", "--state-dir", str(self.state))
        proc.wait(timeout=5)
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            proc.stderr.close()
        self.assertLess(time.perf_counter() - issued, 2.0)
        attempts = (self.state / "campaign-supervision" / "poll-attempts.jsonl").read_text(encoding="utf-8")
        self.assertIn("SHUTDOWN_INTERRUPTED", attempts)
        self.assertIn("INTERRUPTED_BEFORE_RECEIPT", attempts)
        self.assertNotIn("counts_as_in_window_observation\":true", attempts.replace(" ", ""))

    def test_session_boundary_does_not_start_a_poll(self) -> None:
        arm = _run(
            "arm",
            "--state-dir",
            str(self.state),
            "--campaign-id",
            "SW-BOUNDARY",
            "--observation-window-id",
            "OBS-SW",
            "--skip-environment-preflight",
            "--session-end-utc",
            _utc(-5),
            "--required-roles",
            "supervisor",
            "--poll-cadence-seconds",
            "30",
        )
        self.assertEqual(arm.returncode, 0, msg=arm.stdout + arm.stderr)
        proc = subprocess.Popen(
            [
                sys.executable,
                str(SUPERVISOR),
                "poll-loop",
                "--state-dir",
                str(self.state),
                "--poll-cadence-seconds",
                "30",
                "--iterations",
                "2",
            ],
            cwd=str(ROOT),
            env={
                **os.environ,
                "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)]),
                "PYTHONUNBUFFERED": "1",
            },
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(proc.kill)
        time.sleep(0.5)
        heartbeat = json.loads(
            (self.state / "campaign-supervision" / "heartbeat.json").read_text(encoding="utf-8")
        )
        self.assertEqual(heartbeat["phase"], "SESSION_BOUNDARY_HOLD")
        attempts = self.state / "campaign-supervision" / "poll-attempts.jsonl"
        self.assertFalse(attempts.is_file())
        _run("shutdown", "--state-dir", str(self.state), "--rth-close")
        proc.wait(timeout=5)
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            proc.stderr.close()
        self.assertEqual(proc.returncode, 0)

    def test_spawn_labels_shim_and_keeps_role_logs(self) -> None:
        script = self.state / "child.py"
        script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
        log_a = self.state / "logs" / "supervisor.log"
        log_b = self.state / "logs" / "poller.log"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            pid_a = spawn_detached([sys.executable, str(script)], cwd=self.state, log_path=log_a, role="supervisor")
            pid_b = spawn_detached([sys.executable, str(script)], cwd=self.state, log_path=log_b, role="poller")
            time.sleep(0.2)
        self.addCleanup(self._kill, pid_a)
        self.addCleanup(self._kill, pid_b)
        self.assertNotEqual(pid_a, pid_b)
        self.assertTrue(log_a.is_file())
        self.assertTrue(log_b.is_file())
        flags = (self.state / "logs" / "detach-flags.jsonl").read_text(encoding="utf-8")
        self.assertEqual(flags.count("\n"), 2)
        self.assertIn("supervisor", flags)
        self.assertIn("poller", flags)
        file_warnings = [item for item in caught if "unclosed file" in str(item.message).lower()]
        self.assertEqual(file_warnings, [])

    def test_register_child_does_not_clobber_supervisor(self) -> None:
        _armed(self.state)
        before = json.loads(
            (self.state / "campaign-supervision" / "ownership.json").read_text(encoding="utf-8")
        )["supervisor_pid"]
        registered = _run(
            "register-child",
            "--state-dir",
            str(self.state),
            "--role",
            "poller",
            "--pid",
            str(os.getpid()),
        )
        self.assertEqual(registered.returncode, 0, msg=registered.stdout + registered.stderr)
        after = json.loads(
            (self.state / "campaign-supervision" / "ownership.json").read_text(encoding="utf-8")
        )
        self.assertEqual(after["supervisor_pid"], before)
        dead = _run(
            "register-child",
            "--state-dir",
            str(self.state),
            "--role",
            "api",
            "--pid",
            "999999",
        )
        self.assertEqual(dead.returncode, 2)
        self.assertEqual(json.loads(dead.stdout)["detail"], "CHILD_PID_NOT_ALIVE")

    @staticmethod
    def _kill(pid: int) -> None:
        if os.name == "nt":
            subprocess.run(["taskkill.exe", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True)
        else:
            try:
                os.kill(pid, 15)
            except OSError:
                pass


if __name__ == "__main__":
    unittest.main()

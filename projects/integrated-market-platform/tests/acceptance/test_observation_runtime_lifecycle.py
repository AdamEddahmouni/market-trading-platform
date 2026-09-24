"""Outage intervals, shutdown wake, PID contract, and detached logs.

Evidence class: SOFTWARE_CONTROLLED_EVIDENCE. No provider network. No campaign arm.
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
    safe_command_fingerprint,
    write_heartbeat,
    write_ownership,
)
from tools.platform.detached_process import spawn_detached  # noqa: E402
from tools.platform.service_health import process_alive  # noqa: E402

SUPERVISOR = ROOT / "tools" / "platform" / "campaign_supervisor.py"


def _utc(offset_seconds: float = 0.0) -> str:
    moment = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    return moment.isoformat().replace("+00:00", "Z")


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SUPERVISOR), *argv],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def _arm(state: Path, **extra: str) -> None:
    argv = [
        "arm",
        "--state-dir",
        str(state),
        "--campaign-id",
        "SW-LIFECYCLE",
        "--observation-window-id",
        "OBS-SW",
        "--skip-environment-preflight",
        "--poll-cadence-seconds",
        "30",
        "--heartbeat-cadence-seconds",
        "30",
        "--stale-after-seconds",
        "90",
    ]
    for key, value in extra.items():
        argv.extend([f"--{key.replace('_', '-')}", value])
    result = _run(*argv)
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)


def _ownership_dead_poller(state: Path) -> None:
    ownership = CampaignOwnership(
        campaign_id="SW-LIFECYCLE",
        runtime_sha="abc",
        supervisor_pid=os.getpid(),
        supervisor_identity="imp-campaign-supervisor",
        child_processes=[ProcessIdentity(role="api", pid=os.getpid(), create_time_utc=_utc())],
        arm_timestamp_utc=_utc(-10),
        observation_window_id="OBS-SW",
        expected_poll_cadence_seconds=30.0,
        expected_next_cycle_utc=_utc(30),
        state_directory=str(state),
        arm_status="ARMED_RUNNING",
        launch_command_fingerprint=safe_command_fingerprint(["supervisor"]),
        required_roles=["supervisor", "poller", "api"],
    )
    write_ownership(ownership)
    write_heartbeat(
        state,
        {
            "last_heartbeat_utc": _utc(),
            "application_ready": True,
            "stale_after_seconds": 90,
            "synthetic_poll_generated": False,
        },
    )


class ObservationRuntimeLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.state = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _rows(self) -> list[dict]:
        return read_outage_records(self.state)

    def test_recovery_closes_interval_without_rewriting_open_row(self) -> None:
        _ownership_dead_poller(self.state)
        first = _run("status", "--state-dir", str(self.state))
        self.assertEqual(first.returncode, 2, msg=first.stdout + first.stderr)
        opened = self._rows()
        self.assertEqual(len(opened), 1)
        self.assertIsNone(opened[0]["interval_end_utc"])
        self.assertEqual(opened[0]["root_cause"], "POLL_PROCESS_DEAD")
        self.assertEqual(opened[0]["record_kind"], "INTERVAL_OPEN")
        again = _run("status", "--state-dir", str(self.state))
        self.assertEqual(json.loads(again.stdout)["outage_ledger"], "OPEN_UNCHANGED")
        self.assertEqual(len(self._rows()), 1)

        owned = CampaignOwnership(
            campaign_id="SW-LIFECYCLE",
            runtime_sha="abc",
            supervisor_pid=os.getpid(),
            supervisor_identity="imp-campaign-supervisor",
            child_processes=[
                ProcessIdentity(role="api", pid=os.getpid(), create_time_utc=_utc()),
                ProcessIdentity(role="poller", pid=os.getpid(), create_time_utc=_utc()),
            ],
            arm_timestamp_utc=_utc(-10),
            observation_window_id="OBS-SW",
            expected_poll_cadence_seconds=30.0,
            expected_next_cycle_utc=_utc(30),
            state_directory=str(self.state),
            arm_status="ARMED_RUNNING",
            required_roles=["supervisor", "poller", "api"],
        )
        write_ownership(owned)
        recovered = _run("status", "--state-dir", str(self.state))
        self.assertEqual(recovered.returncode, 0, msg=recovered.stdout + recovered.stderr)
        view = json.loads(recovered.stdout)
        self.assertEqual(view["status"], "HEALTHY")
        self.assertEqual(view["outage_ledger"], "CLOSED")
        self.assertEqual(view["active_outages"], [])
        rows = self._rows()
        self.assertEqual(len(rows), 2)
        self.assertIsNone(rows[0]["interval_end_utc"])
        self.assertEqual(rows[1]["record_kind"], "INTERVAL_CLOSED")
        self.assertEqual(rows[1]["close_reason"], "RECOVERED")
        self.assertTrue(rows[1]["recovered"])
        self.assertEqual(rows[1]["interval_start_utc"], rows[0]["interval_start_utc"])
        self.assertIsNotNone(rows[1]["interval_end_utc"])
        idempotent = _run("status", "--state-dir", str(self.state))
        self.assertEqual(json.loads(idempotent.stdout)["outage_ledger"], "NO_ACTIVE_OUTAGE")
        self.assertEqual(len(self._rows()), 2)
        self.assertEqual(active_outage_records(self._rows()), [])

    def test_second_failure_opens_a_new_interval(self) -> None:
        self.test_recovery_closes_interval_without_rewriting_open_row()
        _ownership_dead_poller(self.state)
        third = _run("status", "--state-dir", str(self.state))
        self.assertEqual(third.returncode, 2)
        rows = self._rows()
        opens = [row for row in rows if row.get("record_kind") == "INTERVAL_OPEN"]
        self.assertEqual(len(opens), 2)
        self.assertNotEqual(opens[0]["outage_id"], opens[1]["outage_id"])
        self.assertEqual(len(active_outage_records(rows)), 1)

    def test_shutdown_terminates_open_outage_without_claiming_recovery(self) -> None:
        _ownership_dead_poller(self.state)
        _run("status", "--state-dir", str(self.state))
        shutdown = _run("shutdown", "--state-dir", str(self.state), "--rth-close")
        self.assertEqual(shutdown.returncode, 0, msg=shutdown.stdout + shutdown.stderr)
        payload = json.loads(shutdown.stdout)
        self.assertEqual(payload["status"], "RTH_CLOSE_SHUTDOWN")
        self.assertFalse(payload["recovered"])
        self.assertEqual(payload["active_outages_terminated"], 1)
        rows = self._rows()
        self.assertEqual(rows[1]["close_reason"], "CAMPAIGN_TERMINATED")
        self.assertFalse(rows[1]["recovered"])
        self.assertEqual(rows[1]["termination_reason"], "SHUTDOWN_TERMINATED")
        self.assertIsNone(rows[0]["interval_end_utc"])
        second = _run("shutdown", "--state-dir", str(self.state), "--rth-close")
        self.assertEqual(second.returncode, 0)
        self.assertEqual(json.loads(second.stdout)["active_outages_terminated"], 0)
        self.assertEqual(len(self._rows()), 2)

    def test_malformed_final_line_does_not_hide_open_outage(self) -> None:
        _ownership_dead_poller(self.state)
        _run("status", "--state-dir", str(self.state))
        ledger = self.state / "campaign-supervision" / "outages.jsonl"
        with ledger.open("a", encoding="utf-8") as handle:
            handle.write("{not-json\n")
        status = _run("status", "--state-dir", str(self.state))
        self.assertEqual(json.loads(status.stdout)["outage_ledger"], "MALFORMED")
        self.assertIn("MALFORMED_LINE:2", json.loads(status.stdout)["outage_ledger_defects"])
        self.assertEqual(len(active_outage_records(read_outage_records(self.state))), 1)

    def test_unwritable_ledger_fails_status(self) -> None:
        _ownership_dead_poller(self.state)
        ledger = self.state / "campaign-supervision" / "outages.jsonl"
        ledger.mkdir()
        status = _run("status", "--state-dir", str(self.state))
        self.assertEqual(status.returncode, 2)
        self.assertEqual(json.loads(status.stdout)["outage_ledger"], "UNAVAILABLE")

    def test_idle_poller_wakes_on_shutdown(self) -> None:
        _arm(self.state)
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
                "0",
            ],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.addCleanup(proc.kill)
        self.addCleanup(lambda: proc.stdout.close() if proc.stdout else None)
        deadline = time.time() + 5
        marker = self.state / "campaign-supervision" / "poller.alive"
        while time.time() < deadline and not marker.is_file():
            time.sleep(0.05)
        self.assertTrue(marker.is_file())
        issued = time.perf_counter()
        shutdown = _run("shutdown", "--state-dir", str(self.state))
        self.assertEqual(shutdown.returncode, 0, msg=shutdown.stdout + shutdown.stderr)
        proc.wait(timeout=5)
        if proc.stdout is not None:
            proc.stdout.close()
        elapsed = time.perf_counter() - issued
        self.assertLess(elapsed, 2.0, msg=f"shutdown latency {elapsed}")
        self.assertEqual(proc.returncode, 0)
        attempts = self.state / "campaign-supervision" / "poll-attempts.jsonl"
        count = 0
        if attempts.is_file():
            count = len([line for line in attempts.read_text(encoding="utf-8").splitlines() if line.strip()])
        self.assertLessEqual(count, 1)
        heartbeat = json.loads(
            (self.state / "campaign-supervision" / "heartbeat.json").read_text(encoding="utf-8")
        )
        self.assertEqual(heartbeat["phase"], "CLEAN_SHUTDOWN")
        self.assertFalse(heartbeat["application_ready"])

    def test_in_flight_block_interrupts_without_a_following_cycle(self) -> None:
        _arm(self.state)
        proc = subprocess.Popen(
            [
                sys.executable,
                str(SUPERVISOR),
                "poll-loop",
                "--state-dir",
                str(self.state),
                "--block-seconds",
                "30",
                "--poll-cadence-seconds",
                "30",
                "--iterations",
                "0",
            ],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        self.addCleanup(proc.kill)
        time.sleep(0.4)
        issued = time.perf_counter()
        _run("shutdown", "--state-dir", str(self.state), "--rth-close")
        proc.wait(timeout=5)
        if proc.stdout is not None:
            proc.stdout.close()
        elapsed = time.perf_counter() - issued
        self.assertLess(elapsed, 2.0, msg=f"in-flight latency {elapsed}")
        text = (self.state / "campaign-supervision" / "poll-attempts.jsonl").read_text(encoding="utf-8")
        self.assertIn("SHUTDOWN_INTERRUPTED", text)
        self.assertIn("INTERRUPTED_BEFORE_RECEIPT", text)
        self.assertEqual(text.count("SHUTDOWN_INTERRUPTED"), 1)

    def test_session_boundary_does_not_start_a_poll(self) -> None:
        past = _utc(-5)
        _arm(self.state, session_end_utc=past)
        result = _run(
            "poll-loop",
            "--state-dir",
            str(self.state),
            "--iterations",
            "1",
            "--poll-cadence-seconds",
            "0.2",
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("SESSION_BOUNDARY_HOLD", result.stdout)
        attempts = self.state / "campaign-supervision" / "poll-attempts.jsonl"
        self.assertFalse(attempts.is_file())

    def test_register_rejects_dead_wrong_role_and_shim(self) -> None:
        _arm(self.state)
        dead = _run(
            "register-child",
            "--state-dir",
            str(self.state),
            "--role",
            "api",
            "--pid",
            "4194303",
        )
        self.assertEqual(dead.returncode, 2)
        self.assertIn("CHILD_PID_NOT_ALIVE", dead.stdout)
        wrong = _run(
            "register-child",
            "--state-dir",
            str(self.state),
            "--role",
            "not-a-role",
            "--pid",
            str(os.getpid()),
        )
        self.assertEqual(wrong.returncode, 2)
        self.assertIn("ROLE_NOT_ALLOWED", wrong.stdout)
        supervisor = _run(
            "register-child",
            "--state-dir",
            str(self.state),
            "--role",
            "supervisor",
            "--pid",
            str(os.getpid()),
        )
        self.assertIn("SUPERVISOR_ROLE_REQUIRES_ADOPT", supervisor.stdout)
        book = self.state / "campaign-supervision" / "spawn-identity.json"
        book.parent.mkdir(parents=True, exist_ok=True)
        book.write_text(
            json.dumps({"spawns": [{"spawn_shim_pid": os.getpid(), "durable_pid": os.getpid() + 1, "role": "poller"}]}),
            encoding="utf-8",
        )
        shim = _run(
            "register-child",
            "--state-dir",
            str(self.state),
            "--role",
            "poller",
            "--pid",
            str(os.getpid()),
        )
        self.assertEqual(shim.returncode, 2)
        self.assertIn("SPAWN_SHIM_PID_IS_NOT_DURABLE_ROLE", shim.stdout)

    def test_spawn_log_handle_closes_and_roles_do_not_share_a_log(self) -> None:
        log_dir = self.state / "logs"
        supervisor_log = log_dir / "supervisor.log"
        poller_log = log_dir / "poller.log"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            supervisor_pid = spawn_detached(
                [sys.executable, "-c", "print('supervisor-line')"],
                cwd=ROOT,
                log_path=supervisor_log,
                role="supervisor",
            )
            poller_pid = spawn_detached(
                [sys.executable, "-c", "print('poller-line')"],
                cwd=ROOT,
                log_path=poller_log,
                role="poller",
            )
            deadline = time.time() + 5
            while time.time() < deadline and (
                not supervisor_log.is_file() or b"supervisor-line" not in supervisor_log.read_bytes()
            ):
                time.sleep(0.05)
            while time.time() < deadline and (
                not poller_log.is_file() or b"poller-line" not in poller_log.read_bytes()
            ):
                time.sleep(0.05)
        self.assertNotEqual(supervisor_pid, 0)
        self.assertNotEqual(poller_pid, 0)
        self.assertIn(b"supervisor-line", supervisor_log.read_bytes())
        self.assertIn(b"poller-line", poller_log.read_bytes())
        self.assertNotIn(b"poller-line", supervisor_log.read_bytes())
        flags = (log_dir / "detach-flags.jsonl").read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(flags), 2)
        self.assertNotIn(
            "unclosed file",
            " ".join(str(item.message) for item in caught if issubclass(item.category, ResourceWarning)),
        )


if __name__ == "__main__":
    unittest.main()

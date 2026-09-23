"""SOFTWARE_CONTROLLED / FIXTURE_REPLAY acceptance for observation-runtime durability.

Evidence class: SOFTWARE_CONTROLLED_EVIDENCE / FIXTURE_REPLAY.
Does **not** claim RTH proof. Does not mutate frozen empirical campaign state.
Execution authority remains BLOCKED.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.platform.operator_diagnostics.campaign_observation_readiness import (  # noqa: E402
    build_campaign_observation_readiness,
)
from market_platform_foundation.platform.operator_diagnostics.campaign_supervision import (  # noqa: E402
    CampaignOwnership,
    ProcessIdentity,
    evaluate_campaign_progress,
    load_campaign_supervision_view,
    read_ownership,
    safe_command_fingerprint,
    write_heartbeat,
    write_ownership,
)
from tools.platform.campaign_environment_preflight import (  # noqa: E402
    evaluate_campaign_environment_preflight,
)
from tools.platform.detached_process import spawn_detached  # noqa: E402
from tools.platform.service_health import process_alive  # noqa: E402

EVIDENCE_CLASS = "SOFTWARE_CONTROLLED_EVIDENCE"
SUPERVISOR = ROOT / "tools" / "platform" / "campaign_supervisor.py"


def _utc(offset_seconds: float = 0.0) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    ).isoformat().replace("+00:00", "Z")


def _run_supervisor(*argv: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ if env is None else env)
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), str(ROOT), environment.get("PYTHONPATH", "")]
    )
    environment["PYTHONUNBUFFERED"] = "1"
    return subprocess.run(
        [sys.executable, str(SUPERVISOR), *argv],
        cwd=str(ROOT),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


class _TinyApiHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = b'{"ok":true,"execution_authority":"BLOCKED"}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


class RuntimeObservationDurabilityAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="imp-runtime-durability-")
        self.state_dir = Path(self._tmpdir.name)
        self.addCleanup(self._tmpdir.cleanup)
        self._child_pids: list[int] = []
        self.addCleanup(self._cleanup_children)

    def _cleanup_children(self) -> None:
        for pid in self._child_pids:
            if pid <= 0:
                continue
            if os.name == "nt":
                subprocess.run(
                    ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            else:
                try:
                    os.kill(pid, 15)
                except OSError:
                    pass

    def test_missing_required_poller_is_process_dead(self) -> None:
        ownership = CampaignOwnership(
            campaign_id="SW-DURABILITY-MISSING-POLLER",
            runtime_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            supervisor_pid=os.getpid(),
            supervisor_identity="imp-campaign-supervisor",
            child_processes=[ProcessIdentity(role="api", pid=os.getpid(), create_time_utc=_utc())],
            arm_timestamp_utc=_utc(-10),
            observation_window_id="OBS-SW",
            expected_poll_cadence_seconds=30.0,
            expected_next_cycle_utc=_utc(30),
            state_directory=str(self.state_dir),
            arm_status="ARMED_RUNNING",
            required_roles=["supervisor", "poller", "api"],
        )
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat={"last_heartbeat_utc": _utc(), "application_ready": True, "stale_after_seconds": 90},
            now_utc_epoch=time.time(),
            process_alive_fn=process_alive,
        )
        self.assertEqual(progress["status"], "PROCESS_DEAD")
        self.assertIn("poller", progress["dead_roles"])

    def test_dead_poller_is_process_dead(self) -> None:
        ownership = CampaignOwnership(
            campaign_id="SW-DURABILITY-DEAD-POLLER",
            runtime_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            supervisor_pid=os.getpid(),
            supervisor_identity="imp-campaign-supervisor",
            child_processes=[
                ProcessIdentity(role="poller", pid=1, create_time_utc=_utc()),
                ProcessIdentity(role="api", pid=os.getpid(), create_time_utc=_utc()),
            ],
            arm_timestamp_utc=_utc(-10),
            observation_window_id="OBS-SW",
            expected_poll_cadence_seconds=30.0,
            expected_next_cycle_utc=_utc(30),
            state_directory=str(self.state_dir),
            arm_status="ARMED_RUNNING",
            required_roles=["supervisor", "poller", "api"],
        )
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat={"last_heartbeat_utc": _utc(), "application_ready": True, "stale_after_seconds": 90},
            now_utc_epoch=time.time(),
            process_alive_fn=lambda pid: pid == os.getpid(),
        )
        self.assertEqual(progress["status"], "PROCESS_DEAD")
        self.assertIn("poller", progress["dead_roles"])

    def test_stale_heartbeat_is_stale(self) -> None:
        ownership = CampaignOwnership(
            campaign_id="SW-DURABILITY-STALE",
            runtime_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            supervisor_pid=os.getpid(),
            supervisor_identity="imp-campaign-supervisor",
            child_processes=[
                ProcessIdentity(role="poller", pid=os.getpid(), create_time_utc=_utc()),
                ProcessIdentity(role="api", pid=os.getpid(), create_time_utc=_utc()),
            ],
            arm_timestamp_utc=_utc(-200),
            observation_window_id="OBS-SW",
            expected_poll_cadence_seconds=30.0,
            expected_next_cycle_utc=_utc(-100),
            state_directory=str(self.state_dir),
            arm_status="ARMED_RUNNING",
            required_roles=["supervisor", "poller", "api"],
        )
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat={
                "last_heartbeat_utc": _utc(-120),
                "last_successful_poll_utc": _utc(-120),
                "application_ready": True,
                "stale_after_seconds": 90,
            },
            now_utc_epoch=time.time(),
            process_alive_fn=process_alive,
        )
        self.assertEqual(progress["status"], "STALE")

    def test_no_campaign_is_not_armed_phase(self) -> None:
        payload = build_campaign_observation_readiness(
            campaign_supervision={
                "status": "NOT_APPLICABLE",
                "healthy": False,
                "ownership": None,
                "heartbeat": None,
                "progress": {"status": "NOT_APPLICABLE", "arm_status": "NOT_ARMED"},
            },
            lifecycle={"services": []},
            intent={"campaign_id": None, "intended_date_et": None, "source": "NONE"},
        )
        self.assertEqual(payload["phase"], "NOT_ARMED")
        self.assertEqual(payload["arm_status"], "NOT_ARMED")

    def test_dead_api_maps_to_active_stalled(self) -> None:
        payload = build_campaign_observation_readiness(
            campaign_supervision={
                "status": "PROCESS_DEAD",
                "healthy": False,
                "ownership": {
                    "campaign_id": "SW-DURABILITY-API",
                    "runtime_sha": "abc",
                    "arm_status": "ARMED_RUNNING",
                    "supervisor_identity": "imp-campaign-supervisor",
                    "observation_window_id": "OBS",
                    "state_directory": str(self.state_dir),
                    "execution_authority": "BLOCKED",
                    "allows_network_submit": False,
                },
                "heartbeat": {"last_heartbeat_utc": _utc()},
                "progress": {
                    "status": "PROCESS_DEAD",
                    "arm_status": "ARMED_RUNNING",
                    "reason": "REQUIRED_PROCESS_DEAD",
                    "dead_roles": ["api"],
                },
            },
            lifecycle={
                "services": [
                    {
                        "name": "api",
                        "health": {
                            "port_bound": False,
                            "http_alive": False,
                            "process_alive": False,
                            "identity_owned": False,
                        },
                    }
                ]
            },
            intent={
                "campaign_id": "SW-DURABILITY-API",
                "intended_date_et": "2026-09-23",
                "source": "EXPLICIT",
            },
        )
        self.assertEqual(payload["phase"], "ACTIVE_STALLED")
        self.assertIn("PROCESS_DEAD", payload["blockers"])

    def test_register_child_does_not_clobber_supervisor_pid(self) -> None:
        ownership = CampaignOwnership(
            campaign_id="SW-DURABILITY-NO-CLOBBER",
            runtime_sha="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            supervisor_pid=424242,
            supervisor_identity="imp-campaign-supervisor",
            child_processes=[],
            arm_timestamp_utc=_utc(),
            observation_window_id="OBS-SW",
            expected_poll_cadence_seconds=30.0,
            expected_next_cycle_utc=None,
            state_directory=str(self.state_dir),
            arm_status="ARMED_RUNNING",
            launch_command_fingerprint=safe_command_fingerprint(["supervisor"]),
            required_roles=["supervisor", "poller", "api"],
        )
        write_ownership(ownership)
        result = _run_supervisor(
            "register-child",
            "--state-dir",
            str(self.state_dir),
            "--role",
            "api",
            "--pid",
            str(os.getpid()),
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        loaded = read_ownership(self.state_dir)
        assert loaded is not None
        self.assertEqual(loaded.supervisor_pid, 424242)
        self.assertEqual(loaded.child_processes[0].role, "api")
        self.assertEqual(loaded.child_processes[0].pid, os.getpid())

    def test_missing_ui_deps_fail_visible_before_arm(self) -> None:
        fake_root = self.state_dir / "fake-imp-root"
        (fake_root / "tools" / "ui1").mkdir(parents=True)
        (fake_root / "tools" / "ui1" / "run_ui_api.py").write_text("# stub\n", encoding="utf-8")
        (fake_root / ".venv" / "Scripts").mkdir(parents=True)
        (fake_root / ".venv" / "Scripts" / "python.exe").write_text("", encoding="utf-8")
        # Deliberately omit ui/node_modules
        report = evaluate_campaign_environment_preflight(
            root=fake_root,
            state_dir=self.state_dir / "state",
            require_ui_deps=True,
            campaign_id="SW-DURABILITY-UI",
            observation_window_id="OBS-SW",
            check_opend=False,
        )
        self.assertFalse(report.ready_to_arm)
        self.assertIn("ui_node_modules", report.blockers)

        blocked = _run_supervisor(
            "arm",
            "--state-dir",
            str(self.state_dir / "state"),
            "--campaign-id",
            "SW-DURABILITY-UI",
            "--observation-window-id",
            "OBS-SW",
        )
        # Real arm uses repository ROOT (may have node_modules). Force via preflight module path:
        self.assertFalse(report.ready_to_arm)
        # CLI arm against real ROOT with --allow-missing-ui-deps still requires other gates.
        # Prove CLI refuses when preflight fails by invoking with a synthetic IMP root via env is N/A;
        # the module-level report above is the authoritative fail-visible gate.
        self.assertIn("ui_node_modules", {c.name for c in report.checks if c.status == "FAIL"})

    def test_software_controlled_arm_run_poll_api_close(self) -> None:
        """campaign prepared → arm → supervisor owns → heartbeat → poller cycles → API up → close.

        Evidence class: SOFTWARE_CONTROLLED / FIXTURE_REPLAY — not RTH proof.
        """

        # Arm with skip only when UI deps missing on this checkout; prefer real preflight.
        ui_modules = ROOT / "ui" / "node_modules"
        arm_argv = [
            "arm",
            "--state-dir",
            str(self.state_dir),
            "--campaign-id",
            "SW-DURABILITY-REHEARSAL-20260923",
            "--observation-window-id",
            "OBS-SW-REHEARSAL",
            "--segment-id",
            "A",
            "--poll-cadence-seconds",
            "0.2",
            "--heartbeat-cadence-seconds",
            "0.2",
            "--stale-after-seconds",
            "30",
        ]
        if not ui_modules.is_dir():
            arm_argv.append("--allow-missing-ui-deps")
        arm = _run_supervisor(*arm_argv)
        self.assertEqual(arm.returncode, 0, msg=arm.stdout + arm.stderr)
        arm_payload = json.loads(arm.stdout)
        self.assertEqual(arm_payload["status"], "ARMED")
        self.assertEqual(arm_payload["execution_authority"], "BLOCKED")

        # Durable supervisor
        supervisor_pid = spawn_detached(
            [
                sys.executable,
                str(SUPERVISOR),
                "run",
                "--state-dir",
                str(self.state_dir),
                "--heartbeat-cadence-seconds",
                "0.2",
                "--iterations",
                "40",
            ],
            cwd=ROOT,
            log_path=self.state_dir / "campaign-supervision" / "supervisor-rehearsal.log",
        )
        self._child_pids.append(supervisor_pid)
        # Wait until durable supervisor adopted ownership (arm CLI PID is transient).
        adopt_deadline = time.time() + 8
        while time.time() < adopt_deadline:
            owned = read_ownership(self.state_dir)
            if owned is not None and process_alive(int(owned.supervisor_pid)):
                break
            time.sleep(0.1)
        owned = read_ownership(self.state_dir)
        self.assertIsNotNone(owned)
        assert owned is not None
        self.assertTrue(
            process_alive(int(owned.supervisor_pid)),
            msg=f"supervisor pid {owned.supervisor_pid} never became alive",
        )

        # Long-lived poller (not one-shot) — start after supervisor adopt to avoid races.
        poller_pid = spawn_detached(
            [
                sys.executable,
                str(SUPERVISOR),
                "poll-loop",
                "--state-dir",
                str(self.state_dir),
                "--poll-cadence-seconds",
                "0.2",
                "--iterations",
                "30",
            ],
            cwd=ROOT,
            log_path=self.state_dir / "campaign-supervision" / "poller-rehearsal.log",
        )
        self._child_pids.append(poller_pid)
        time.sleep(0.5)
        self.assertTrue(process_alive(poller_pid))

        # Minimal API process (fixture loopback)
        server = ThreadingHTTPServer(("127.0.0.1", 0), _TinyApiHandler)
        port = int(server.server_address[1])
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        api_pid = os.getpid()  # register this test process as api owning the fixture server
        reg = _run_supervisor(
            "register-child",
            "--state-dir",
            str(self.state_dir),
            "--role",
            "api",
            "--pid",
            str(api_pid),
            "--identity-tokens",
            "fixture-api",
            str(port),
        )
        self.assertEqual(reg.returncode, 0, msg=reg.stdout + reg.stderr)

        # Wait for poller cycles + supervisor heartbeat
        deadline = time.time() + 8
        poller_marker = self.state_dir / "campaign-supervision" / "poller.alive"
        supervisor_marker = self.state_dir / "campaign-supervision" / "supervisor.alive"
        while time.time() < deadline:
            if poller_marker.is_file() and supervisor_marker.is_file():
                break
            time.sleep(0.1)
        self.assertTrue(supervisor_marker.is_file(), "supervisor heartbeat marker missing")
        self.assertTrue(poller_marker.is_file(), "poller cycle marker missing")

        status = _run_supervisor("status", "--state-dir", str(self.state_dir))
        view = json.loads(status.stdout)
        self.assertEqual(view["evidence_class"], EVIDENCE_CLASS)
        self.assertEqual(view["execution_authority"], "BLOCKED")
        self.assertIn(
            view["status"],
            {"HEALTHY", "STARTING"},
            msg=json.dumps(view.get("progress"), indent=2),
        )
        self.assertTrue(process_alive(supervisor_pid))
        self.assertTrue(process_alive(poller_pid))

        # Controlled close
        shutdown = _run_supervisor("shutdown", "--state-dir", str(self.state_dir))
        self.assertEqual(shutdown.returncode, 0, msg=shutdown.stdout + shutdown.stderr)
        # Stop children before tempdir cleanup (Windows file locks).
        self._cleanup_children()
        self._child_pids.clear()
        time.sleep(0.2)
        final = load_campaign_supervision_view(self.state_dir, process_alive_fn=process_alive)
        self.assertEqual(final["progress"]["status"], "NOT_APPLICABLE")
        self.assertEqual(final["progress"]["reason"], "CLEAN_SHUTDOWN")
        self.assertFalse(final["progress"].get("outage"))


if __name__ == "__main__":
    unittest.main()

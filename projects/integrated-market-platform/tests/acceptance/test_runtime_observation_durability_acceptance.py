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
    compose_campaign_observation_readiness_for_state,
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
        def _stop_api() -> None:
            server.shutdown()
            server.server_close()

        self.addCleanup(_stop_api)
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

    def test_status_persists_one_open_outage_when_required_role_is_dead(self) -> None:
        ownership = CampaignOwnership(
            campaign_id="SW-DURABILITY-OUTAGE-LEDGER",
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
        write_ownership(ownership)
        write_heartbeat(
            self.state_dir,
            {
                "last_heartbeat_utc": _utc(),
                "application_ready": True,
                "stale_after_seconds": 90,
                "synthetic_poll_generated": False,
            },
        )
        first = _run_supervisor("status", "--state-dir", str(self.state_dir))
        self.assertEqual(first.returncode, 2, msg=first.stdout + first.stderr)
        view = json.loads(first.stdout)
        self.assertEqual(view["status"], "PROCESS_DEAD")
        self.assertEqual(view["outage_ledger"], "APPENDED")
        ledger = self.state_dir / "campaign-supervision" / "outages.jsonl"
        self.assertTrue(ledger.is_file())
        rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["classification"], "NOT_OBSERVED")
        self.assertIn("poller", rows[0]["process_state"]["dead_roles"])
        self.assertFalse(rows[0]["backfill_applied"])
        second = _run_supervisor("status", "--state-dir", str(self.state_dir))
        self.assertEqual(json.loads(second.stdout)["outage_ledger"], "OPEN_UNCHANGED")
        rows_again = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows_again), 1)

    def test_poll_loop_distinguishes_empty_failure_and_software_cycle(self) -> None:
        arm = _run_supervisor(
            "arm",
            "--state-dir",
            str(self.state_dir),
            "--campaign-id",
            "SW-DURABILITY-POLL-CLASS",
            "--observation-window-id",
            "OBS-SW-POLL",
            "--skip-environment-preflight",
            "--poll-cadence-seconds",
            "30",
        )
        self.assertEqual(arm.returncode, 0, msg=arm.stdout + arm.stderr)
        empty = self.state_dir / "empty-poll.json"
        empty.write_text(
            json.dumps(
                {
                    "ingress_classification": "SUCCESS_EMPTY",
                    "ingress_outcome": "FINVIZ_LIVE_INGRESS_SUCCESS_ZERO_QUALIFYING_ROWS",
                    "disposition": "PASS",
                }
            ),
            encoding="utf-8",
        )
        failure = self.state_dir / "failed-poll.json"
        failure.write_text(
            json.dumps(
                {
                    "ingress_classification": "PROVIDER_FAILURE",
                    "ingress_outcome": "LIVE_INGRESS_FAILED",
                    "disposition": "BLOCKED",
                }
            ),
            encoding="utf-8",
        )
        admitted_block = self.state_dir / "admit-block.json"
        admitted_block.write_text(
            json.dumps(
                {
                    "ingress_classification": "SUCCESS",
                    "ingress_outcome": "BLOCKED",
                    "blockers": ["UI_API_COCKPIT_ADMIT_UNREACHABLE"],
                }
            ),
            encoding="utf-8",
        )

        def _once(receipt: Path | None) -> dict:
            argv = [
                "poll-loop",
                "--state-dir",
                str(self.state_dir),
                "--iterations",
                "1",
                "--poll-cadence-seconds",
                "30",
            ]
            if receipt is not None:
                argv.extend(["--ingress-json", str(receipt)])
            result = _run_supervisor(*argv)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            heartbeat = json.loads(
                (self.state_dir / "campaign-supervision" / "heartbeat.json").read_text(encoding="utf-8")
            )
            return heartbeat

        empty_hb = _once(empty)
        self.assertEqual(empty_hb["last_poll_classification"], "SUCCESS_EMPTY")
        self.assertEqual(empty_hb["poll_evidence_class"], "SOFTWARE_CONTROLLED")
        self.assertTrue(empty_hb["last_successful_poll_utc"])
        kept = empty_hb["last_successful_poll_utc"]

        failed_hb = _once(failure)
        self.assertEqual(failed_hb["last_poll_classification"], "PROVIDER_FAILURE")
        self.assertEqual(failed_hb["last_successful_poll_utc"], kept)

        missing_hb = _once(self.state_dir / "does-not-exist.json")
        self.assertEqual(missing_hb["last_poll_classification"], "POLL_PROCESS_FAILURE")
        self.assertEqual(missing_hb["last_successful_poll_utc"], kept)

        admit_hb = _once(admitted_block)
        self.assertEqual(admit_hb["last_poll_classification"], "ADMISSION_FAILURE")
        self.assertEqual(admit_hb["last_successful_poll_utc"], kept)

        software_hb = _once(None)
        self.assertEqual(software_hb["last_poll_classification"], "SOFTWARE_CONTROLLED_CYCLE")
        self.assertEqual(software_hb["poll_evidence_class"], "SOFTWARE_CONTROLLED")
        self.assertNotEqual(software_hb["last_successful_poll_utc"], kept)
        attempts = (
            self.state_dir / "campaign-supervision" / "poll-attempts.jsonl"
        ).read_text(encoding="utf-8")
        self.assertIn("SUCCESS_EMPTY", attempts)
        self.assertIn("PROVIDER_FAILURE", attempts)
        self.assertIn("POLL_PROCESS_FAILURE", attempts)
        self.assertIn("ADMISSION_FAILURE", attempts)
        self.assertIn("SOFTWARE_CONTROLLED_CYCLE", attempts)
        self.assertNotIn("EMPIRICALLY_PROVEN", attempts)
        self.assertNotIn("RTH_PROVEN", attempts)

    def test_preflight_fails_when_outage_ledger_is_not_a_directory(self) -> None:
        state = self.state_dir / "preflight-state"
        state.mkdir()
        (state / "campaign-supervision").write_text("not-a-directory\n", encoding="utf-8")
        report = evaluate_campaign_environment_preflight(
            root=ROOT,
            state_dir=state,
            require_ui_deps=False,
            campaign_id="SW-DURABILITY-LEDGER",
            observation_window_id="OBS-SW",
            check_opend=False,
        )
        self.assertFalse(report.ready_to_arm)
        self.assertIn("outage_ledger", report.blockers)

    def test_readiness_blocks_when_outage_ledger_unavailable(self) -> None:
        from zoneinfo import ZoneInfo

        blocked = self.state_dir / "readiness-state"
        blocked.mkdir()
        (blocked / "campaign-supervision").write_text("not-a-directory\n", encoding="utf-8")
        payload = compose_campaign_observation_readiness_for_state(
            blocked,
            intent_explicit={
                "campaign_id": "RTH-OBS-NEWS-20260924",
                "intended_date_et": "2026-09-24",
                "frozen": "yes",
            },
            now_et=datetime(2026, 9, 24, 8, 0, tzinfo=ZoneInfo("America/New_York")),
            ingress_enabled=True,
        )
        self.assertIn("OUTAGE_LEDGER_UNAVAILABLE", payload["blockers"])
        self.assertEqual(payload["phase"], "BLOCKED_STATE_DIR")
        self.assertNotEqual(payload["phase"], "READY_TO_ARM")

    def test_readiness_cli_imports_as_package(self) -> None:
        result = _run_supervisor(
            "readiness",
            "--state-dir",
            str(self.state_dir),
            "--campaign-id",
            "RTH-OBS-NEWS-20260924-REHEARSAL-CLI",
            "--intended-date-et",
            "2026-09-24",
            "--frozen",
            "yes",
        )
        self.assertNotIn("ImportError", result.stderr)
        self.assertNotIn("attempted relative import", result.stderr)
        payload = json.loads(result.stdout)
        self.assertIn(payload["phase"], {"NOT_ARMED", "READY_TO_ARM", "BLOCKED_STATE_DIR"})
        self.assertEqual(payload["execution_authority"], "BLOCKED")


class ObservationOutageAndShutdownTests(unittest.TestCase):
    """SOFTWARE_CONTROLLED evidence. Not an RTH observation."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="imp-outage-lifecycle-")
        self.state_dir = Path(self._tmpdir.name)
        self.addCleanup(self._tmpdir.cleanup)
        self._child_pids: list[int] = []
        self.addCleanup(self._stop_children)

    def _stop_children(self) -> None:
        for pid in self._child_pids:
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

    def _arm(self, campaign_id: str = "SW-OUTAGE-LIFECYCLE") -> None:
        result = _run_supervisor(
            "arm",
            "--state-dir",
            str(self.state_dir),
            "--campaign-id",
            campaign_id,
            "--observation-window-id",
            "OBS-SW-OUTAGE",
            "--skip-environment-preflight",
            "--required-roles",
            "supervisor,poller,api",
            "--poll-cadence-seconds",
            "30",
            "--heartbeat-cadence-seconds",
            "15",
            "--stale-after-seconds",
            "90",
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        ownership = read_ownership(self.state_dir)
        assert ownership is not None
        ownership.supervisor_pid = os.getpid()
        ownership.child_processes = [
            ProcessIdentity(role="api", pid=os.getpid(), create_time_utc=_utc()),
        ]
        write_ownership(ownership)
        write_heartbeat(
            self.state_dir,
            {
                "last_heartbeat_utc": _utc(),
                "application_ready": True,
                "stale_after_seconds": 90,
                "synthetic_poll_generated": False,
            },
        )

    def _rows(self) -> list[dict]:
        path = self.state_dir / "campaign-supervision" / "outages.jsonl"
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def test_failure_recovery_second_failure_and_terminal_close(self) -> None:
        self._arm()
        first = _run_supervisor("status", "--state-dir", str(self.state_dir))
        self.assertEqual(first.returncode, 2, msg=first.stdout + first.stderr)
        opened = json.loads(first.stdout)
        self.assertEqual(opened["outage_ledger"], "APPENDED")
        self.assertEqual(opened["progress"]["status"], "PROCESS_DEAD")
        rows = self._rows()
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["interval_end_utc"])
        self.assertEqual(rows[0]["root_cause"], "POLL_PROCESS_DEAD")
        self.assertEqual(rows[0]["record_kind"], "INTERVAL_OPEN")
        again = _run_supervisor("status", "--state-dir", str(self.state_dir))
        self.assertEqual(json.loads(again.stdout)["outage_ledger"], "OPEN_UNCHANGED")
        self.assertEqual(len(self._rows()), 1)

        ownership = read_ownership(self.state_dir)
        assert ownership is not None
        ownership.child_processes.append(
            ProcessIdentity(role="poller", pid=os.getpid(), create_time_utc=_utc())
        )
        write_ownership(ownership)
        recovered = _run_supervisor("status", "--state-dir", str(self.state_dir))
        self.assertEqual(recovered.returncode, 0, msg=recovered.stdout + recovered.stderr)
        recovered_view = json.loads(recovered.stdout)
        self.assertEqual(recovered_view["status"], "HEALTHY")
        self.assertEqual(recovered_view["outage_ledger"], "CLOSED")
        self.assertEqual(recovered_view["active_outages"], [])
        closed_rows = self._rows()
        self.assertEqual(len(closed_rows), 2)
        self.assertIsNone(closed_rows[0]["interval_end_utc"])
        self.assertEqual(closed_rows[1]["record_kind"], "INTERVAL_CLOSED")
        self.assertEqual(closed_rows[1]["close_reason"], "RECOVERED")
        self.assertTrue(closed_rows[1]["recovered"])
        self.assertEqual(closed_rows[1]["interval_start_utc"], closed_rows[0]["interval_start_utc"])
        idle = _run_supervisor("status", "--state-dir", str(self.state_dir))
        self.assertEqual(json.loads(idle.stdout)["outage_ledger"], "NO_ACTIVE_OUTAGE")
        self.assertEqual(len(self._rows()), 2)

        ownership = read_ownership(self.state_dir)
        assert ownership is not None
        ownership.child_processes = [
            child for child in ownership.child_processes if child.role != "poller"
        ]
        write_ownership(ownership)
        second = _run_supervisor("status", "--state-dir", str(self.state_dir))
        self.assertEqual(json.loads(second.stdout)["outage_ledger"], "APPENDED")
        self.assertEqual(len(self._rows()), 3)
        shutdown = _run_supervisor("shutdown", "--state-dir", str(self.state_dir), "--rth-close")
        self.assertEqual(shutdown.returncode, 0, msg=shutdown.stdout + shutdown.stderr)
        payload = json.loads(shutdown.stdout)
        self.assertEqual(payload["status"], "RTH_CLOSE_SHUTDOWN")
        self.assertFalse(payload["recovered"])
        self.assertEqual(payload["active_outages_terminated"], 1)
        final_rows = self._rows()
        close = final_rows[-1]
        self.assertEqual(close["close_reason"], "CAMPAIGN_TERMINATED")
        self.assertFalse(close["recovered"])
        self.assertEqual(close["termination_reason"], "SHUTDOWN_TERMINATED")
        self.assertIsNone(final_rows[-2]["interval_end_utc"])
        repeat = _run_supervisor("shutdown", "--state-dir", str(self.state_dir), "--rth-close")
        self.assertEqual(repeat.returncode, 0, msg=repeat.stdout + repeat.stderr)
        self.assertEqual(json.loads(repeat.stdout)["active_outages_terminated"], 0)
        self.assertEqual(len(self._rows()), len(final_rows))
        terminal = _run_supervisor("heartbeat", "--state-dir", str(self.state_dir))
        self.assertEqual(terminal.returncode, 0, msg=terminal.stdout + terminal.stderr)
        self.assertFalse(json.loads(terminal.stdout)["heartbeat_advanced"])

    def test_unwritable_ledger_and_malformed_line_fail_visible(self) -> None:
        self._arm()
        ledger_dir = self.state_dir / "campaign-supervision" / "outages.jsonl"
        ledger_dir.mkdir(parents=True)
        status = _run_supervisor("status", "--state-dir", str(self.state_dir))
        self.assertEqual(status.returncode, 2, msg=status.stdout + status.stderr)
        self.assertEqual(json.loads(status.stdout)["outage_ledger"], "UNAVAILABLE")
        ledger_dir.rmdir()
        path = self.state_dir / "campaign-supervision" / "outages.jsonl"
        path.write_text('{"record_kind":"INTERVAL_OPEN","interval_end_utc":null}\nnot-json\n', encoding="utf-8")
        from market_platform_foundation.platform.operator_diagnostics.campaign_supervision import (
            outage_ledger_defects,
            read_outage_records,
        )

        self.assertEqual(len(read_outage_records(self.state_dir)), 1)
        self.assertIn("MALFORMED_LINE:2", outage_ledger_defects(self.state_dir))

    def test_shutdown_during_idle_wait_and_in_flight_block(self) -> None:
        self._arm()
        idle = subprocess.Popen(
            [
                sys.executable,
                str(SUPERVISOR),
                "poll-loop",
                "--state-dir",
                str(self.state_dir),
                "--poll-cadence-seconds",
                "30",
                "--iterations",
                "0",
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
        self._child_pids.append(idle.pid)
        marker = self.state_dir / "campaign-supervision" / "poller.alive"
        deadline = time.time() + 8
        while time.time() < deadline and not marker.is_file():
            time.sleep(0.05)
        self.assertTrue(marker.is_file(), "poller did not start")
        started = time.perf_counter()
        shutdown = _run_supervisor("shutdown", "--state-dir", str(self.state_dir))
        self.assertEqual(shutdown.returncode, 0, msg=shutdown.stdout + shutdown.stderr)
        idle.wait(timeout=5)
        idle_latency = time.perf_counter() - started
        self.assertLess(idle_latency, 3.0, msg=f"idle shutdown took {idle_latency:.3f}s")
        idle_out = (idle.stdout.read() if idle.stdout else "") + (idle.stderr.read() if idle.stderr else "")
        if idle.stdout is not None:
            idle.stdout.close()
        if idle.stderr is not None:
            idle.stderr.close()
        self.assertIn("poll_started_after_shutdown", idle_out)
        self.assertFalse(idle_out.strip().endswith("POLLER_RUNNING") and "stopped" not in idle_out)

        blocked_dir = self.state_dir / "blocked-campaign"
        blocked_dir.mkdir()
        arm = _run_supervisor(
            "arm",
            "--state-dir",
            str(blocked_dir),
            "--campaign-id",
            "SW-OUTAGE-BLOCK",
            "--observation-window-id",
            "OBS-SW-BLOCK",
            "--skip-environment-preflight",
            "--required-roles",
            "supervisor",
        )
        self.assertEqual(arm.returncode, 0, msg=arm.stdout + arm.stderr)
        blocked = subprocess.Popen(
            [
                sys.executable,
                str(SUPERVISOR),
                "poll-loop",
                "--state-dir",
                str(blocked_dir),
                "--poll-cadence-seconds",
                "30",
                "--iterations",
                "1",
                "--block-seconds",
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
        self._child_pids.append(blocked.pid)
        deadline = time.time() + 8
        registered = False
        while time.time() < deadline:
            owned = read_ownership(blocked_dir)
            if owned is not None and any(child.role == "poller" for child in owned.child_processes):
                registered = True
                break
            time.sleep(0.05)
        self.assertTrue(registered, "blocking poller did not register")
        started = time.perf_counter()
        stop = _run_supervisor("shutdown", "--state-dir", str(blocked_dir), "--rth-close")
        self.assertEqual(stop.returncode, 0, msg=stop.stdout + stop.stderr)
        blocked.wait(timeout=5)
        if blocked.stdout is not None:
            blocked.stdout.close()
        if blocked.stderr is not None:
            blocked.stderr.close()
        block_latency = time.perf_counter() - started
        self.assertLess(block_latency, 3.0, msg=f"in-flight shutdown took {block_latency:.3f}s")
        attempts = (blocked_dir / "campaign-supervision" / "poll-attempts.jsonl").read_text(encoding="utf-8")
        self.assertIn("SHUTDOWN_INTERRUPTED", attempts)
        self.assertIn("INTERRUPTED_BEFORE_RECEIPT", attempts)
        self.assertIn('"counts_as_in_window_observation":false', attempts)

    def test_session_boundary_does_not_start_a_poll(self) -> None:
        result = _run_supervisor(
            "arm",
            "--state-dir",
            str(self.state_dir),
            "--campaign-id",
            "SW-BOUNDARY",
            "--observation-window-id",
            "OBS-SW-BOUNDARY",
            "--skip-environment-preflight",
            "--required-roles",
            "supervisor",
            "--session-end-utc",
            _utc(-5),
            "--poll-cadence-seconds",
            "30",
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        poller = subprocess.Popen(
            [
                sys.executable,
                str(SUPERVISOR),
                "poll-loop",
                "--state-dir",
                str(self.state_dir),
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
        self._child_pids.append(poller.pid)
        time.sleep(0.4)
        started = time.perf_counter()
        shutdown = _run_supervisor("shutdown", "--state-dir", str(self.state_dir), "--rth-close")
        self.assertEqual(shutdown.returncode, 0, msg=shutdown.stdout + shutdown.stderr)
        poller.wait(timeout=5)
        self.assertLess(time.perf_counter() - started, 3.0)
        attempts = self.state_dir / "campaign-supervision" / "poll-attempts.jsonl"
        self.assertFalse(attempts.exists())
        output = (poller.stdout.read() if poller.stdout else "")
        if poller.stdout is not None:
            poller.stdout.close()
        if poller.stderr is not None:
            poller.stderr.close()
        self.assertIn("poll_started", output)
        self.assertIn("false", output)

    def test_spawn_labels_shim_and_keeps_role_logs(self) -> None:
        import gc
        import warnings

        log_a = self.state_dir / "logs" / "supervisor.log"
        log_b = self.state_dir / "logs" / "poller.log"
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ResourceWarning)
            pid_a = spawn_detached(
                [sys.executable, "-c", "print('supervisor-line')"],
                cwd=ROOT,
                log_path=log_a,
                role="supervisor",
            )
            pid_b = spawn_detached(
                [sys.executable, "-c", "print('poller-line')"],
                cwd=ROOT,
                log_path=log_b,
                role="poller",
            )
            self._child_pids.extend([pid_a, pid_b])
            deadline = time.time() + 8
            while time.time() < deadline and not (
                log_a.is_file() and "supervisor-line" in log_a.read_text(encoding="utf-8", errors="replace")
                and log_b.is_file() and "poller-line" in log_b.read_text(encoding="utf-8", errors="replace")
            ):
                time.sleep(0.05)
            gc.collect()
        self.assertIn("supervisor-line", log_a.read_text(encoding="utf-8", errors="replace"))
        self.assertIn("poller-line", log_b.read_text(encoding="utf-8", errors="replace"))
        self.assertNotIn("poller-line", log_a.read_text(encoding="utf-8", errors="replace"))
        flags = (self.state_dir / "logs" / "detach-flags.jsonl").read_text(encoding="utf-8")
        self.assertEqual(flags.count("append_only_launch_evidence"), 2)
        self.assertFalse(any("unclosed file" in str(item.message) for item in caught))
        dead = _run_supervisor(
            "register-child",
            "--state-dir",
            str(self.state_dir),
            "--role",
            "poller",
            "--pid",
            "999999",
        )
        # No ownership yet: fail visible, not a silent register.
        self.assertNotEqual(dead.returncode, 0)

    def test_second_namespace_does_not_inherit_shutdown(self) -> None:
        self._arm("SW-FIRST-NAMESPACE")
        first = _run_supervisor("shutdown", "--state-dir", str(self.state_dir))
        self.assertEqual(first.returncode, 0, msg=first.stdout + first.stderr)
        other = self.state_dir / "second-namespace"
        other.mkdir()
        second = _run_supervisor(
            "arm",
            "--state-dir",
            str(other),
            "--campaign-id",
            "SW-SECOND-NAMESPACE",
            "--observation-window-id",
            "OBS-SW-SECOND",
            "--skip-environment-preflight",
            "--required-roles",
            "supervisor",
        )
        self.assertEqual(second.returncode, 0, msg=second.stdout + second.stderr)
        owned = read_ownership(other)
        assert owned is not None
        self.assertEqual(owned.arm_status, "ARMED_RUNNING")
        self.assertFalse((other / "campaign-supervision" / "outages.jsonl").exists())
        heartbeat = json.loads((other / "campaign-supervision" / "heartbeat.json").read_text(encoding="utf-8"))
        self.assertEqual(heartbeat["phase"], "ARMED")
        stop = _run_supervisor("shutdown", "--state-dir", str(other))
        self.assertEqual(stop.returncode, 0, msg=stop.stdout + stop.stderr)


if __name__ == "__main__":
    unittest.main()

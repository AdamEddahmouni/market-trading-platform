"""Campaign supervision heartbeat / ownership / shell-exit acceptance.

Evidence class: SOFTWARE_CONTROLLED_EVIDENCE.

Does not mutate historical September 22 campaign evidence. Does not claim the
Sep 22 outage root cause was reproduced. Execution authority remains BLOCKED.
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.live_execution_safety.preflight_controls import (  # noqa: E402
    evaluate_live_preflight_bundle,
)
from market_platform_foundation.platform.operator_diagnostics.campaign_supervision import (  # noqa: E402
    CampaignOwnership,
    ProcessIdentity,
    append_outage_record,
    build_outage_interval,
    evaluate_campaign_progress,
    load_campaign_supervision_view,
    preserve_arm_for_recovery,
    read_outage_records,
    read_ownership,
    redact_command_token,
    safe_command_fingerprint,
    write_heartbeat,
    write_ownership,
)
from tools.platform.detached_process import (  # noqa: E402
    mechanism_description,
    spawn_detached,
    windows_detached_creationflags,
)
from tools.platform.service_health import process_alive  # noqa: E402

EVIDENCE_CLASS = "SOFTWARE_CONTROLLED_EVIDENCE"
SUPERVISOR = ROOT / "tools" / "platform" / "campaign_supervisor.py"


def _utc(offset_seconds: float = 0.0) -> str:
    return (
        datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    ).isoformat().replace("+00:00", "Z")


def _ownership(
    state_dir: Path,
    *,
    arm_status: str = "ARMED_RUNNING",
    supervisor_pid: int | None = None,
    children: list[ProcessIdentity] | None = None,
    required_roles: list[str] | None = None,
) -> CampaignOwnership:
    child_list = list(children) if children is not None else [
        ProcessIdentity(role="poller", pid=os.getpid(), create_time_utc=_utc(-30)),
        ProcessIdentity(role="api", pid=os.getpid(), create_time_utc=_utc(-30)),
    ]
    return CampaignOwnership(
        campaign_id="RTH-OBS-TEST-SW-001",
        runtime_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        supervisor_pid=int(supervisor_pid if supervisor_pid is not None else os.getpid()),
        supervisor_identity="imp-campaign-supervisor",
        child_processes=child_list,
        arm_timestamp_utc=_utc(-30),
        observation_window_id="OBS-WINDOW-TEST",
        expected_poll_cadence_seconds=30.0,
        expected_next_cycle_utc=_utc(30),
        state_directory=str(state_dir),
        arm_status=arm_status,
        launch_command_fingerprint=safe_command_fingerprint(["python", "tools/platform/campaign_supervisor.py"]),
        segment_id="SEGMENT-A",
        required_roles=required_roles or ["supervisor", "poller", "api"],
    )


class CampaignSupervisionAcceptanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(prefix="imp-campaign-supervision-")
        self.state_dir = Path(self._tmpdir.name)
        self.addCleanup(self._tmpdir.cleanup)

    def test_01_normal_supervisor_launch(self) -> None:
        ownership = _ownership(self.state_dir)
        write_ownership(ownership)
        loaded = read_ownership(self.state_dir)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.campaign_id, "RTH-OBS-TEST-SW-001")
        self.assertEqual(loaded.runtime_sha, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
        self.assertTrue(process_alive(loaded.supervisor_pid))
        self.assertEqual(loaded.execution_authority, "BLOCKED")
        self.assertFalse(loaded.allows_network_submit)

    def test_02_normal_heartbeat_progression(self) -> None:
        ownership = _ownership(self.state_dir)
        write_ownership(ownership)
        hb = {
            "last_heartbeat_utc": _utc(),
            "last_successful_poll_utc": _utc(),
            "expected_next_poll_utc": _utc(30),
            "stale_after_seconds": 90,
            "application_ready": True,
        }
        write_heartbeat(self.state_dir, hb)
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat=hb,
            now_utc_epoch=time.time(),
        )
        self.assertEqual(progress["status"], "HEALTHY")
        self.assertTrue(progress["healthy"])

    def test_03_stale_heartbeat(self) -> None:
        ownership = _ownership(self.state_dir)
        write_ownership(ownership)
        hb = {
            "last_heartbeat_utc": _utc(-120),
            "last_successful_poll_utc": _utc(-120),
            "stale_after_seconds": 90,
            "application_ready": True,
        }
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat=hb,
            now_utc_epoch=time.time(),
        )
        self.assertEqual(progress["status"], "STALE")
        self.assertTrue(progress["outage"])

    def test_04_poller_process_death(self) -> None:
        children = [
            ProcessIdentity(role="poller", pid=1),
            ProcessIdentity(role="api", pid=os.getpid()),
        ]
        ownership = _ownership(self.state_dir, children=children)
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat={"last_heartbeat_utc": _utc(), "application_ready": True, "stale_after_seconds": 90},
            now_utc_epoch=time.time(),
            process_alive_fn=lambda pid: pid == os.getpid(),
        )
        self.assertEqual(progress["status"], "PROCESS_DEAD")
        self.assertIn("poller", progress["dead_roles"])

    def test_05_api_process_death(self) -> None:
        children = [
            ProcessIdentity(role="poller", pid=os.getpid()),
            ProcessIdentity(role="api", pid=1),
        ]
        ownership = _ownership(self.state_dir, children=children)
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat={"last_heartbeat_utc": _utc(), "application_ready": True, "stale_after_seconds": 90},
            now_utc_epoch=time.time(),
            process_alive_fn=lambda pid: pid == os.getpid(),
        )
        self.assertEqual(progress["status"], "PROCESS_DEAD")
        self.assertIn("api", progress["dead_roles"])

    def test_06_ui_process_death_when_required(self) -> None:
        children = [
            ProcessIdentity(role="poller", pid=os.getpid()),
            ProcessIdentity(role="api", pid=os.getpid()),
            ProcessIdentity(role="ui", pid=1),
        ]
        ownership = _ownership(
            self.state_dir,
            children=children,
            required_roles=["supervisor", "poller", "api", "ui"],
        )
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat={"last_heartbeat_utc": _utc(), "application_ready": True, "stale_after_seconds": 90},
            now_utc_epoch=time.time(),
            process_alive_fn=lambda pid: pid == os.getpid(),
            ui_required=True,
        )
        self.assertEqual(progress["status"], "PROCESS_DEAD")
        self.assertIn("ui", progress["dead_roles"])

    def test_07_bound_port_dead_application(self) -> None:
        ownership = _ownership(
            self.state_dir,
            children=[
                ProcessIdentity(role="poller", pid=os.getpid()),
                ProcessIdentity(role="api", pid=os.getpid()),
            ],
        )
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat={
                "last_heartbeat_utc": _utc(),
                "application_ready": False,
                "port_bound_without_progress": True,
                "stale_after_seconds": 90,
            },
            now_utc_epoch=time.time(),
        )
        self.assertEqual(progress["status"], "APPLICATION_UNREADY")
        self.assertFalse(progress["healthy"])

    def test_08_stalled_expected_cycle_without_progress(self) -> None:
        ownership = _ownership(self.state_dir)
        ownership.expected_next_cycle_utc = _utc(-200)
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat={
                "last_heartbeat_utc": _utc(-10),
                "last_successful_poll_utc": _utc(-200),
                "expected_next_poll_utc": _utc(-200),
                "stale_after_seconds": 90,
                "application_ready": True,
            },
            now_utc_epoch=time.time(),
        )
        self.assertEqual(progress["status"], "STALE")
        self.assertIn(
            progress["reason"],
            {"EXPECTED_CYCLE_ELAPSED_WITHOUT_PROGRESS", "HEARTBEAT_OR_PROGRESS_STALE"},
        )

    def test_09_stale_armed_running_fails_closed(self) -> None:
        ownership = _ownership(self.state_dir, arm_status="ARMED_RUNNING", supervisor_pid=1)
        # Manifest says armed, but supervisor PID is dead and heartbeat is stale.
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat={
                "last_heartbeat_utc": _utc(-500),
                "last_successful_poll_utc": _utc(-500),
                "stale_after_seconds": 90,
                "application_ready": True,
            },
            now_utc_epoch=time.time(),
            process_alive_fn=lambda pid: False,
        )
        self.assertEqual(ownership.arm_status, "ARMED_RUNNING")
        self.assertNotEqual(progress["status"], "HEALTHY")
        self.assertEqual(progress["status"], "PROCESS_DEAD")
        self.assertTrue(progress["outage"])

    def test_10_deliberate_clean_shutdown(self) -> None:
        ownership = _ownership(self.state_dir, arm_status="CLEAN_SHUTDOWN")
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat={"last_heartbeat_utc": _utc(-500)},
            now_utc_epoch=time.time(),
            process_alive_fn=lambda pid: False,
        )
        self.assertEqual(progress["status"], "NOT_APPLICABLE")
        self.assertEqual(progress["reason"], "CLEAN_SHUTDOWN")
        self.assertFalse(progress.get("outage"))

    def test_11_rth_close_not_misclassified_as_outage(self) -> None:
        ownership = _ownership(self.state_dir, arm_status="RTH_CLOSE_SHUTDOWN")
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat={"last_heartbeat_utc": _utc(-500)},
            now_utc_epoch=time.time(),
            process_alive_fn=lambda pid: False,
        )
        self.assertEqual(progress["status"], "NOT_APPLICABLE")
        self.assertEqual(progress["reason"], "RTH_CLOSE_SHUTDOWN")
        self.assertFalse(progress.get("outage"))

    def test_12_recovery_preserves_original_arm_and_segment(self) -> None:
        ownership = _ownership(self.state_dir)
        original_arm = ownership.arm_timestamp_utc
        original_segment = ownership.segment_id
        original_sha = ownership.runtime_sha
        recovered = preserve_arm_for_recovery(
            ownership,
            supervisor_pid=os.getpid(),
            child_processes=[ProcessIdentity(role="poller", pid=os.getpid())],
        )
        self.assertEqual(recovered.arm_timestamp_utc, original_arm)
        self.assertEqual(recovered.segment_id, original_segment)
        self.assertEqual(recovered.runtime_sha, original_sha)
        self.assertEqual(recovered.arm_status, "ARMED_RUNNING")
        self.assertNotEqual(recovered.segment_id, "SEGMENT-C")

    def test_13_outage_interval_classified_not_observed(self) -> None:
        ownership = _ownership(self.state_dir)
        progress = {
            "status": "STALE",
            "expected_next_poll_utc": _utc(-100),
            "last_successful_poll_utc": "2026-09-22T18:26:00.749Z",
            "supervisor_alive": True,
            "child_states": [],
        }
        record = build_outage_interval(
            ownership=ownership,
            progress=progress,
            detected_at_utc="2026-09-22T18:57:27.624Z",
            interval_start_utc="2026-09-22T18:26:00.749Z",
            interval_end_utc="2026-09-22T18:57:27.624Z",
        )
        self.assertEqual(record["classification"], "NOT_OBSERVED")
        self.assertEqual(record["root_cause"], "UNKNOWN")
        append_outage_record(self.state_dir, record)
        rows = read_outage_records(self.state_dir)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["classification"], "NOT_OBSERVED")

    def test_14_no_synthetic_poll_generation(self) -> None:
        ownership = _ownership(self.state_dir)
        write_ownership(ownership)
        write_heartbeat(
            self.state_dir,
            {
                "last_heartbeat_utc": _utc(),
                "last_successful_poll_utc": None,
                "synthetic_poll_generated": False,
                "application_ready": True,
                "stale_after_seconds": 90,
            },
        )
        view = load_campaign_supervision_view(self.state_dir)
        self.assertFalse((view.get("heartbeat") or {}).get("synthetic_poll_generated"))
        # Stale/starting without inventing a poll timestamp.
        self.assertIsNone((view.get("heartbeat") or {}).get("last_successful_poll_utc"))

    def test_15_no_backfill(self) -> None:
        ownership = _ownership(self.state_dir)
        record = build_outage_interval(
            ownership=ownership,
            progress={"status": "STALE", "last_successful_poll_utc": _utc(-100)},
            detected_at_utc=_utc(),
            interval_start_utc=_utc(-100),
        )
        self.assertFalse(record["backfill_applied"])
        self.assertFalse(record["new_segment_created"])
        self.assertFalse(record["synthetic_poll_generated"])

    def test_16_runtime_sha_retained(self) -> None:
        ownership = _ownership(self.state_dir)
        write_ownership(ownership)
        recovered = preserve_arm_for_recovery(
            ownership,
            supervisor_pid=os.getpid(),
            child_processes=[],
        )
        write_ownership(recovered)
        loaded = read_ownership(self.state_dir)
        assert loaded is not None
        self.assertEqual(loaded.runtime_sha, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")

    def test_17_process_metadata_safe_from_secret_leakage(self) -> None:
        argv = [
            "python",
            "tools/platform/campaign_supervisor.py",
            "--token",
            "super-secret-value",
            "API_KEY=abcd1234secret",
            "normal-flag",
        ]
        fingerprint = safe_command_fingerprint(argv)
        self.assertTrue(fingerprint.startswith("sha256:"))
        self.assertNotIn("super-secret-value", fingerprint)
        self.assertNotIn("abcd1234secret", fingerprint)
        self.assertEqual(redact_command_token("API_KEY=abcd1234secret"), "<redacted>")
        ownership = _ownership(self.state_dir)
        ownership.launch_command_fingerprint = fingerprint
        write_ownership(ownership)
        text = (self.state_dir / "campaign-supervision" / "ownership.json").read_text(encoding="utf-8")
        self.assertNotIn("super-secret-value", text)
        self.assertNotIn("abcd1234secret", text)

    def test_18_restart_readback_from_durable_state(self) -> None:
        ownership = _ownership(self.state_dir)
        write_ownership(ownership)
        write_heartbeat(
            self.state_dir,
            {
                "last_heartbeat_utc": _utc(),
                "last_successful_poll_utc": _utc(),
                "application_ready": True,
                "stale_after_seconds": 90,
            },
        )
        # Simulate process restart: new interpreter loads the same state dir.
        view = load_campaign_supervision_view(self.state_dir)
        self.assertEqual(view["ownership"]["campaign_id"], "RTH-OBS-TEST-SW-001")
        self.assertEqual(view["status"], "HEALTHY")
        self.assertEqual(view["evidence_class"], EVIDENCE_CLASS)

    def test_19_finviz_current_historical_semantics_untouched_marker(self) -> None:
        # Campaign supervision must not redefine Finviz current vs historical.
        # Guard: module does not import or monkeypatch Finviz ingest mode helpers.
        import market_platform_foundation.platform.operator_diagnostics.campaign_supervision as mod

        source = Path(mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("finviz", source.lower())
        self.assertNotIn("ingest_mode", source.lower())

    def test_20_execution_authority_remains_blocked(self) -> None:
        ownership = _ownership(self.state_dir)
        self.assertEqual(ownership.execution_authority, "BLOCKED")
        self.assertEqual(ownership.execution_mode, "NONE")
        self.assertFalse(ownership.allows_network_submit)
        self.assertTrue(ownership.live_submit_forbidden)
        report = evaluate_live_preflight_bundle(
            reference_price_minor=100,
            quote_as_of_ns=1,
            decision_time_ns=2,
            max_quote_age_ns=10_000_000_000,
            quantity=1,
            max_quantity=10,
            required_notional_minor=100,
            buying_power_minor=1_000_000,
            session_state="RTH_OPEN",
            side="BUY",
            order_type="LIMIT",
            limit_price_minor=100,
            confirmation_present=True,
            confirmation_expired=False,
            confirmation_matches_intent=True,
        )
        self.assertFalse(report.allows_network_submit)
        self.assertTrue(report.blocked)
        self.assertTrue(
            any(f.reason_code == "BUILD28_LIVE_SUBMIT_FORBIDDEN" for f in report.findings)
        )

    def test_00_shell_exit_supervisor_survives_parent_process_exit(self) -> None:
        """Parent-process exit only (no breakaway).

        Proves: supervisor spawned with CREATE_NEW_PROCESS_GROUP |
        CREATE_NO_WINDOW (allow_breakaway=False) stays alive and heartbeats
        after a Python Popen parent calls SystemExit(0).

        Does **not** prove: CREATE_BREAKAWAY_FROM_JOB, Windows job-kill, or
        terminal-independent durability. Sep 22 root cause remains UNKNOWN.
        """

        marker = self.state_dir / "campaign-supervision" / "supervisor.alive"
        marker.parent.mkdir(parents=True, exist_ok=True)
        ownership = _ownership(self.state_dir, supervisor_pid=0, children=[], required_roles=["supervisor"])
        write_ownership(ownership)

        flags = windows_detached_creationflags(allow_breakaway=False)
        breakaway_flags = windows_detached_creationflags(allow_breakaway=True)
        supervisor_log = marker.parent / f"supervisor-{os.getpid()}-{int(time.time())}.log"
        spawned_path = marker.parent / "spawned_pid.txt"
        mech = mechanism_description(allow_breakaway=False)
        selected = mech["selected_mechanism"]
        mechanism_payload = {
            "selected_mechanism": selected,
            "start_process_hidden_assumed_durable": False,
            "shell_exit_test_flags": int(flags),
            "breakaway_flags_available_but_unused": int(breakaway_flags),
            "shell_exit_test_used_breakaway": False,
            "proven": "parent_process_exit_survival_without_breakaway",
            "unproven": "job_or_terminal_kill_survival_and_breakaway",
        }
        (marker.parent / "mechanism.json").write_text(
            json.dumps(mechanism_payload, sort_keys=True),
            encoding="utf-8",
        )
        coordinator = f"""
import os, subprocess, sys
from pathlib import Path
state = {str(self.state_dir)!r}
root = {str(ROOT)!r}
log = Path({str(supervisor_log)!r})
log.parent.mkdir(parents=True, exist_ok=True)
env = dict(os.environ)
env['PYTHONPATH'] = os.pathsep.join([str(Path(root)/'src'), root, env.get('PYTHONPATH','')])
env['PYTHONUNBUFFERED'] = '1'
cmd = [{sys.executable!r}, {str(SUPERVISOR)!r}, 'run', '--state-dir', state,
       '--heartbeat-cadence-seconds', '0.2', '--iterations', '40', '--auto-poll']
flags = {int(flags)}
with log.open('ab') as handle:
    proc = subprocess.Popen(
        cmd, cwd=root, env=env, stdin=subprocess.DEVNULL,
        stdout=handle, stderr=subprocess.STDOUT,
        creationflags=flags, close_fds=True,
    )
Path({str(spawned_path)!r}).write_text(str(proc.pid), encoding='utf-8')
raise SystemExit(0)
"""
        coord_path = self.state_dir / "coordinator.py"
        coord_path.write_text(coordinator, encoding="utf-8")
        launched = subprocess.Popen(
            [sys.executable, str(coord_path)],
            cwd=str(ROOT),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.time() + 15
            while time.time() < deadline and not spawned_path.is_file():
                if launched.poll() is not None and not spawned_path.is_file():
                    break
                time.sleep(0.05)
            self.assertTrue(spawned_path.is_file(), "supervisor pid file missing after coordinator launch")
            spawned_pid = int(spawned_path.read_text(encoding="utf-8").strip())
            self.addCleanup(self._kill_pid_tree, spawned_pid)
            # Coordinator must exit (parent-process exit surface only).
            try:
                launched.wait(timeout=10)
            except subprocess.TimeoutExpired:
                launched.kill()
                self.fail("coordinator did not exit after launching supervisor")
            self.assertEqual(launched.returncode, 0)

            time.sleep(0.5)
            self.assertTrue(
                process_alive(spawned_pid),
                msg=(
                    "Supervisor did not survive parent process exit. "
                    f"mechanism={mechanism_description(allow_breakaway=False)} flags={flags}"
                ),
            )
            alive_deadline = time.time() + 10
            while time.time() < alive_deadline and not marker.is_file():
                time.sleep(0.1)
            log_tail = ""
            if supervisor_log.is_file():
                log_tail = supervisor_log.read_text(encoding="utf-8", errors="replace")[-2000:]
            self.assertTrue(
                marker.is_file(),
                f"supervisor heartbeat marker missing; alive={process_alive(spawned_pid)}; log={log_tail!r}",
            )
            view = load_campaign_supervision_view(self.state_dir, process_alive_fn=process_alive)
            self.assertEqual(view["ownership"]["runtime_sha"], "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
            self.assertIn(view["status"], {"HEALTHY", "STARTING"})
            reported = mechanism_description(allow_breakaway=False)
            self.assertFalse(reported["start_process_hidden_assumed_durable"])
            self.assertFalse(reported["job_or_terminal_kill_survival_proven"])
            self.assertTrue(reported["parent_process_exit_survival_proven_without_breakaway"])
            self.assertEqual(
                reported["selected_mechanism"],
                "IMP_OWNED_SUPERVISOR_CREATE_NEW_PROCESS_GROUP_NO_WINDOW",
            )
            self.assertNotIn("BREAKAWAY", str(reported["selected_mechanism"]))
        finally:
            if launched.poll() is None:
                launched.kill()

    @staticmethod
    def _kill_pid_tree(pid: int) -> None:
        if pid <= 0:
            return
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

    def test_start_process_hidden_not_labeled_durable_without_proof(self) -> None:
        mech = mechanism_description()
        self.assertFalse(mech["start_process_hidden_assumed_durable"])

    def test_service_liveness_separate_from_data_freshness(self) -> None:
        ownership = _ownership(self.state_dir)
        write_ownership(ownership)
        write_heartbeat(
            self.state_dir,
            {
                "last_heartbeat_utc": _utc(),
                "last_successful_poll_utc": _utc(),
                "application_ready": True,
                "stale_after_seconds": 90,
            },
        )
        view = load_campaign_supervision_view(self.state_dir)
        self.assertTrue(view["service_liveness_separate_from_data_freshness"])
        self.assertTrue(view["does_not_imply_data_freshness"])
        self.assertTrue(view["does_not_imply_opportunity_quality"])
        self.assertEqual(view["execution_authority"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()

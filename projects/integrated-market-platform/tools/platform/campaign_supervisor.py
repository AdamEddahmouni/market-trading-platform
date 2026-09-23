"""IMP-owned minimal campaign supervisor (RTH15-09).

Owns durable campaign ownership + heartbeat files under IMP_STATE_DIR.
Does not auto-backfill, does not mint synthetic polls, does not grant Live
authority, and does not reset the original arm on process recovery.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import importlib.util


def _load_campaign_supervision():
    """Load campaign_supervision without importing operator_diagnostics package __init__.

    Cold supervisor processes must not pull snapshot → local_state circular imports.
    """

    module_path = (
        SRC
        / "market_platform_foundation"
        / "platform"
        / "operator_diagnostics"
        / "campaign_supervision.py"
    )
    spec = importlib.util.spec_from_file_location(
        "imp_campaign_supervision_standalone",
        module_path,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load campaign_supervision from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_cs = _load_campaign_supervision()
DEFAULT_HEARTBEAT_CADENCE_SECONDS = _cs.DEFAULT_HEARTBEAT_CADENCE_SECONDS
DEFAULT_POLL_CADENCE_SECONDS = _cs.DEFAULT_POLL_CADENCE_SECONDS
DEFAULT_STALE_AFTER_SECONDS = _cs.DEFAULT_STALE_AFTER_SECONDS
CampaignOwnership = _cs.CampaignOwnership
ProcessIdentity = _cs.ProcessIdentity
append_outage_record = _cs.append_outage_record
build_outage_interval = _cs.build_outage_interval
evaluate_campaign_progress = _cs.evaluate_campaign_progress
load_campaign_supervision_view = _cs.load_campaign_supervision_view
preserve_arm_for_recovery = _cs.preserve_arm_for_recovery
process_alive = _cs.process_alive
read_heartbeat = _cs.read_heartbeat
read_ownership = _cs.read_ownership
safe_command_fingerprint = _cs.safe_command_fingerprint
write_heartbeat = _cs.write_heartbeat
write_ownership = _cs.write_ownership
from tools.platform.detached_process import mechanism_description, spawn_detached  # noqa: E402


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _resolve_runtime_sha(explicit: str | None) -> str:
    if explicit:
        return explicit.strip()
    env_sha = str(os.environ.get("IMP_RUNTIME_GIT_SHA") or "").strip()
    if env_sha:
        return env_sha
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return "UNKNOWN"


def _state_dir(explicit: str | None) -> Path:
    raw = (explicit or os.environ.get("IMP_STATE_DIR") or "").strip()
    if not raw:
        raise SystemExit("IMP_STATE_DIR or --state-dir is required")
    path = Path(raw).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def cmd_mechanism(_: argparse.Namespace) -> int:
    print(json.dumps(mechanism_description(), indent=2, sort_keys=True))
    return 0


def cmd_arm(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args.state_dir)
    runtime_sha = _resolve_runtime_sha(args.runtime_sha)
    argv = list(args.launch_argv or ["python", "-m", "tools.platform.campaign_supervisor", "run"])
    fingerprint = safe_command_fingerprint(argv)
    arm_ts = _utc_now()
    ownership = CampaignOwnership(
        campaign_id=str(args.campaign_id),
        runtime_sha=runtime_sha,
        supervisor_pid=os.getpid(),
        supervisor_identity="imp-campaign-supervisor",
        child_processes=[],
        arm_timestamp_utc=arm_ts,
        observation_window_id=str(args.observation_window_id),
        expected_poll_cadence_seconds=float(args.poll_cadence_seconds),
        expected_next_cycle_utc=None,
        state_directory=str(state_dir),
        arm_status="ARMED_RUNNING",
        launch_command_fingerprint=fingerprint,
        segment_id=(str(args.segment_id) if args.segment_id else None),
        required_roles=[r.strip() for r in str(args.required_roles).split(",") if r.strip()],
    )
    write_ownership(ownership)
    write_heartbeat(
        state_dir,
        {
            "campaign_id": ownership.campaign_id,
            "runtime_sha": ownership.runtime_sha,
            "supervisor_pid": ownership.supervisor_pid,
            "last_heartbeat_utc": arm_ts,
            "last_successful_poll_utc": None,
            "expected_next_heartbeat_utc": None,
            "expected_next_poll_utc": None,
            "heartbeat_cadence_seconds": float(args.heartbeat_cadence_seconds),
            "poll_cadence_seconds": float(args.poll_cadence_seconds),
            "stale_after_seconds": float(args.stale_after_seconds),
            "application_ready": False,
            "port_bound_without_progress": False,
            "phase": "ARMED",
        },
    )
    print(
        json.dumps(
            {
                "status": "ARMED",
                "campaign_id": ownership.campaign_id,
                "runtime_sha": ownership.runtime_sha,
                "state_directory": str(state_dir),
                "launch_command_fingerprint": fingerprint,
                "execution_authority": "BLOCKED",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def cmd_register_child(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args.state_dir)
    ownership = read_ownership(state_dir)
    if ownership is None:
        print(json.dumps({"status": "ERROR", "detail": "NO_OWNERSHIP"}))
        return 1
    children = list(ownership.child_processes)
    children = [c for c in children if c.role != args.role]
    children.append(
        ProcessIdentity(
            role=str(args.role),
            pid=int(args.pid),
            create_time_utc=_utc_now(),
            parent_pid=os.getpid(),
            command_fingerprint=safe_command_fingerprint(list(args.identity_tokens or [args.role])),
            identity_tokens=list(args.identity_tokens or [args.role]),
        )
    )
    ownership.child_processes = children
    ownership.supervisor_pid = os.getpid()
    write_ownership(ownership)
    print(json.dumps({"status": "REGISTERED", "role": args.role, "pid": int(args.pid)}, sort_keys=True))
    return 0


def cmd_heartbeat(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args.state_dir)
    ownership = read_ownership(state_dir)
    if ownership is None:
        print(json.dumps({"status": "ERROR", "detail": "NO_OWNERSHIP"}))
        return 1
    now = _utc_now()
    now_epoch = time.time()
    prior = read_heartbeat(state_dir) or {}
    poll_cadence = float(args.poll_cadence_seconds or ownership.expected_poll_cadence_seconds)
    hb_cadence = float(args.heartbeat_cadence_seconds or DEFAULT_HEARTBEAT_CADENCE_SECONDS)
    successful_poll = bool(args.successful_poll)
    last_poll = now if successful_poll else prior.get("last_successful_poll_utc")
    expected_next_poll = (
        datetime.fromtimestamp(now_epoch + poll_cadence, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        if successful_poll or prior.get("expected_next_poll_utc") is None
        else prior.get("expected_next_poll_utc")
    )
    if successful_poll:
        expected_next_poll = (
            datetime.fromtimestamp(now_epoch + poll_cadence, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        )
        ownership.expected_next_cycle_utc = expected_next_poll
        write_ownership(ownership)
    heartbeat = {
        "campaign_id": ownership.campaign_id,
        "runtime_sha": ownership.runtime_sha,
        "supervisor_pid": os.getpid(),
        "last_heartbeat_utc": now,
        "last_successful_poll_utc": last_poll,
        "expected_next_heartbeat_utc": datetime.fromtimestamp(
            now_epoch + hb_cadence, tz=timezone.utc
        )
        .isoformat()
        .replace("+00:00", "Z"),
        "expected_next_poll_utc": expected_next_poll,
        "heartbeat_cadence_seconds": hb_cadence,
        "poll_cadence_seconds": poll_cadence,
        "stale_after_seconds": float(args.stale_after_seconds or DEFAULT_STALE_AFTER_SECONDS),
        "application_ready": bool(args.application_ready),
        "port_bound_without_progress": bool(args.port_bound_without_progress),
        "phase": "RUNNING",
        "synthetic_poll_generated": False,
    }
    write_heartbeat(state_dir, heartbeat)
    progress = evaluate_campaign_progress(
        ownership=ownership,
        heartbeat=heartbeat,
        now_utc_epoch=now_epoch,
    )
    if progress.get("outage") and args.record_outage:
        record = build_outage_interval(
            ownership=ownership,
            progress=progress,
            detected_at_utc=now,
            interval_start_utc=str(last_poll or ownership.arm_timestamp_utc),
        )
        append_outage_record(state_dir, record)
    print(json.dumps({"status": "HEARTBEAT", "progress": progress}, indent=2, sort_keys=True))
    return 0 if progress.get("status") in {"HEALTHY", "STARTING"} else 2


def cmd_status(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args.state_dir)
    view = load_campaign_supervision_view(state_dir)
    print(json.dumps(view, indent=2, sort_keys=True))
    status = str(view.get("status") or "UNKNOWN")
    if status == "HEALTHY":
        return 0
    if status in {"NOT_APPLICABLE", "STARTING"}:
        return 0
    return 2


def cmd_shutdown(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args.state_dir)
    ownership = read_ownership(state_dir)
    if ownership is None:
        print(json.dumps({"status": "ALREADY_STOPPED"}))
        return 0
    reason = "RTH_CLOSE_SHUTDOWN" if args.rth_close else "CLEAN_SHUTDOWN"
    ownership.arm_status = reason
    write_ownership(ownership)
    now = _utc_now()
    prior = read_heartbeat(state_dir) or {}
    prior.update(
        {
            "last_heartbeat_utc": now,
            "phase": reason,
            "application_ready": False,
            "shutdown_reason": reason,
        }
    )
    write_heartbeat(state_dir, prior)
    print(json.dumps({"status": reason, "campaign_id": ownership.campaign_id, "outage": False}, sort_keys=True))
    return 0


def cmd_recover(args: argparse.Namespace) -> int:
    """Deliberate recovery: refresh PIDs, preserve original arm/segment/outages."""

    state_dir = _state_dir(args.state_dir)
    ownership = read_ownership(state_dir)
    if ownership is None:
        print(json.dumps({"status": "ERROR", "detail": "NO_OWNERSHIP"}))
        return 1
    if ownership.arm_status in {"CLEAN_SHUTDOWN", "RTH_CLOSE_SHUTDOWN"} and not args.force:
        print(json.dumps({"status": "BLOCKED", "detail": "CAMPAIGN_SHUT_DOWN", "arm_status": ownership.arm_status}))
        return 1
    children = list(ownership.child_processes)
    if args.child_pid and args.child_role:
        children = [c for c in children if c.role != args.child_role]
        children.append(
            ProcessIdentity(
                role=str(args.child_role),
                pid=int(args.child_pid),
                create_time_utc=_utc_now(),
                parent_pid=os.getpid(),
                command_fingerprint=safe_command_fingerprint([args.child_role]),
                identity_tokens=[str(args.child_role)],
            )
        )
    recovered = preserve_arm_for_recovery(
        ownership,
        supervisor_pid=os.getpid(),
        child_processes=children,
        expected_next_cycle_utc=ownership.expected_next_cycle_utc,
    )
    write_ownership(recovered)
    print(
        json.dumps(
            {
                "status": "RECOVERED_PRESERVING_ARM",
                "campaign_id": recovered.campaign_id,
                "arm_timestamp_utc": recovered.arm_timestamp_utc,
                "segment_id": recovered.segment_id,
                "runtime_sha": recovered.runtime_sha,
                "new_segment_created": False,
                "backfill_applied": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def cmd_spawn_detached(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args.state_dir)
    log_path = state_dir / "campaign-supervision" / "detached-child.log"
    argv = list(args.spawn_argv or [])
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        print(json.dumps({"status": "ERROR", "detail": "COMMAND_REQUIRED"}))
        return 2
    pid = spawn_detached(argv, cwd=ROOT, log_path=log_path)
    print(
        json.dumps(
            {
                "status": "SPAWNED",
                "pid": pid,
                "mechanism": mechanism_description(),
                "log_path": str(log_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Foreground supervisor loop for software-controlled acceptance tests."""

    state_dir = _state_dir(args.state_dir)
    ownership = read_ownership(state_dir)
    if ownership is None:
        print(json.dumps({"status": "ERROR", "detail": "ARM_REQUIRED"}))
        return 1
    ownership.supervisor_pid = os.getpid()
    write_ownership(ownership)
    cadence = float(args.heartbeat_cadence_seconds or DEFAULT_HEARTBEAT_CADENCE_SECONDS)
    stale_after = float(args.stale_after_seconds or DEFAULT_STALE_AFTER_SECONDS)
    iterations = int(args.iterations)
    count = 0
    while iterations <= 0 or count < iterations:
        now = _utc_now()
        now_epoch = time.time()
        ownership = read_ownership(state_dir)
        if ownership is None:
            return 1
        if ownership.arm_status in {"CLEAN_SHUTDOWN", "RTH_CLOSE_SHUTDOWN"}:
            print(json.dumps({"status": ownership.arm_status, "stopped": True}))
            return 0
        ownership.supervisor_pid = os.getpid()
        write_ownership(ownership)
        prior = read_heartbeat(state_dir) or {}
        heartbeat = {
            **prior,
            "campaign_id": ownership.campaign_id,
            "runtime_sha": ownership.runtime_sha,
            "supervisor_pid": os.getpid(),
            "last_heartbeat_utc": now,
            "expected_next_heartbeat_utc": datetime.fromtimestamp(
                now_epoch + cadence, tz=timezone.utc
            )
            .isoformat()
            .replace("+00:00", "Z"),
            "heartbeat_cadence_seconds": cadence,
            "stale_after_seconds": stale_after,
            "application_ready": True,
            "port_bound_without_progress": False,
            "phase": "SUPERVISOR_RUNNING",
            "synthetic_poll_generated": False,
        }
        if args.auto_poll:
            heartbeat["last_successful_poll_utc"] = now
            heartbeat["expected_next_poll_utc"] = (
                datetime.fromtimestamp(
                    now_epoch + float(ownership.expected_poll_cadence_seconds),
                    tz=timezone.utc,
                )
                .isoformat()
                .replace("+00:00", "Z")
            )
            ownership.expected_next_cycle_utc = heartbeat["expected_next_poll_utc"]
            write_ownership(ownership)
        write_heartbeat(state_dir, heartbeat)
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat=heartbeat,
            now_utc_epoch=now_epoch,
        )
        if progress.get("outage"):
            append_outage_record(
                state_dir,
                build_outage_interval(
                    ownership=ownership,
                    progress=progress,
                    detected_at_utc=now,
                    interval_start_utc=str(
                        heartbeat.get("last_successful_poll_utc") or ownership.arm_timestamp_utc
                    ),
                ),
            )
        marker = state_dir / "campaign-supervision" / "supervisor.alive"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{os.getpid()}\n{now}\n", encoding="utf-8")
        count += 1
        if iterations > 0 and count >= iterations:
            break
        time.sleep(max(0.05, cadence))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IMP campaign supervisor (minimal)")
    sub = parser.add_subparsers(dest="command", required=True)

    mech = sub.add_parser("mechanism", help="Describe detachment mechanism")
    mech.set_defaults(func=cmd_mechanism)

    arm = sub.add_parser("arm", help="Write durable campaign ownership")
    arm.add_argument("--state-dir")
    arm.add_argument("--campaign-id", required=True)
    arm.add_argument("--observation-window-id", required=True)
    arm.add_argument("--segment-id")
    arm.add_argument("--runtime-sha")
    arm.add_argument("--poll-cadence-seconds", type=float, default=DEFAULT_POLL_CADENCE_SECONDS)
    arm.add_argument("--heartbeat-cadence-seconds", type=float, default=DEFAULT_HEARTBEAT_CADENCE_SECONDS)
    arm.add_argument("--stale-after-seconds", type=float, default=DEFAULT_STALE_AFTER_SECONDS)
    arm.add_argument("--required-roles", default="supervisor,poller,api")
    arm.add_argument("--launch-argv", nargs="*")
    arm.set_defaults(func=cmd_arm)

    reg = sub.add_parser("register-child", help="Record a supervised child process")
    reg.add_argument("--state-dir")
    reg.add_argument("--role", required=True)
    reg.add_argument("--pid", type=int, required=True)
    reg.add_argument("--identity-tokens", nargs="*")
    reg.set_defaults(func=cmd_register_child)

    hb = sub.add_parser("heartbeat", help="Record heartbeat / optional poll progress")
    hb.add_argument("--state-dir")
    hb.add_argument("--successful-poll", action="store_true")
    hb.add_argument("--application-ready", action=argparse.BooleanOptionalAction, default=True)
    hb.add_argument("--port-bound-without-progress", action="store_true")
    hb.add_argument("--poll-cadence-seconds", type=float)
    hb.add_argument("--heartbeat-cadence-seconds", type=float)
    hb.add_argument("--stale-after-seconds", type=float)
    hb.add_argument("--record-outage", action="store_true")
    hb.set_defaults(func=cmd_heartbeat)

    status = sub.add_parser("status", help="Evaluate durable campaign progress")
    status.add_argument("--state-dir")
    status.set_defaults(func=cmd_status)

    shutdown = sub.add_parser("shutdown", help="Deliberate clean or RTH-close shutdown")
    shutdown.add_argument("--state-dir")
    shutdown.add_argument("--rth-close", action="store_true")
    shutdown.set_defaults(func=cmd_shutdown)

    recover = sub.add_parser("recover", help="Deliberate recovery preserving original arm")
    recover.add_argument("--state-dir")
    recover.add_argument("--child-role")
    recover.add_argument("--child-pid", type=int)
    recover.add_argument("--force", action="store_true")
    recover.set_defaults(func=cmd_recover)

    spawn = sub.add_parser(
        "spawn-detached",
        help="Spawn argv with default CREATE_NEW_PROCESS_GROUP|CREATE_NO_WINDOW flags",
    )
    spawn.add_argument("--state-dir")
    spawn.add_argument("spawn_argv", nargs=argparse.REMAINDER)
    spawn.set_defaults(func=cmd_spawn_detached)

    run = sub.add_parser("run", help="Run supervisor heartbeat loop")
    run.add_argument("--state-dir")
    run.add_argument("--heartbeat-cadence-seconds", type=float, default=0.2)
    run.add_argument("--stale-after-seconds", type=float, default=DEFAULT_STALE_AFTER_SECONDS)
    run.add_argument("--iterations", type=int, default=0, help="0 = until shutdown")
    run.add_argument("--auto-poll", action="store_true")
    run.set_defaults(func=cmd_run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

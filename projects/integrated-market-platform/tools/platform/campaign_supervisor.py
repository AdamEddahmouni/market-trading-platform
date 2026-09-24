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
from typing import Any, Sequence

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
read_outage_records = _cs.read_outage_records
outage_ledger_defects = _cs.outage_ledger_defects
record_open_outage_if_changed = _cs.record_open_outage_if_changed
reconcile_outage_ledger = _cs.reconcile_outage_ledger
close_active_outages = _cs.close_active_outages
OUTAGE_CLOSE_CAMPAIGN_TERMINATED = _cs.OUTAGE_CLOSE_CAMPAIGN_TERMINATED
TERMINAL_ARM_STATUSES = ("CLEAN_SHUTDOWN", "RTH_CLOSE_SHUTDOWN")
close_active_outages = _cs.close_active_outages
active_outage_records = _cs.active_outage_records
OUTAGE_CLOSE_RECOVERED = _cs.OUTAGE_CLOSE_RECOVERED
OUTAGE_CLOSE_CAMPAIGN_TERMINATED = _cs.OUTAGE_CLOSE_CAMPAIGN_TERMINATED
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
from tools.platform.service_health import process_alive as platform_process_alive  # noqa: E402


def _alive_fn(pid: int) -> bool:
    """Launcher-grade process probe (ctypes OpenProcess on Windows)."""

    return platform_process_alive(pid)


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
    from tools.platform.campaign_environment_preflight import (
        evaluate_campaign_environment_preflight,
    )

    # Fail-visible before ARM: missing UI/API deps must not become a mid-campaign surprise.
    skip_preflight = bool(getattr(args, "skip_environment_preflight", False))
    require_ui = not bool(getattr(args, "allow_missing_ui_deps", False))
    if not skip_preflight:
        preflight = evaluate_campaign_environment_preflight(
            root=ROOT,
            state_dir=state_dir,
            require_ui_deps=require_ui,
            campaign_id=str(args.campaign_id),
            observation_window_id=str(args.observation_window_id),
            require_finviz_live_ingress=bool(
                getattr(args, "require_finviz_live_ingress", False)
            ),
        )
        if not preflight.ready_to_arm:
            print(
                json.dumps(
                    {
                        "status": "BLOCKED",
                        "detail": "ENVIRONMENT_PREFLIGHT_FAILED",
                        "ready_to_arm": False,
                        "blockers": preflight.blockers,
                        "preflight": preflight.to_dict(),
                        "execution_authority": "BLOCKED",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2

    freeze_path = str(getattr(args, "freeze", "") or "").strip()
    if freeze_path:
        from tools.platform.campaign_go_no_go import evaluate_campaign_go_no_go

        gate = evaluate_campaign_go_no_go(
            freeze_path=freeze_path,
            root=ROOT,
            state_dir=state_dir,
            probe_network=True,
        )
        if gate.get("arm_allowed") and (
            str(args.campaign_id) != gate.get("campaign_id")
            or str(args.observation_window_id) != gate.get("observation_window_id")
        ):
            gate["arm_allowed"] = False
            gate["disposition"] = "BLOCKED"
            gate["blockers"] = ["ARM_ARGUMENTS_FREEZE_MISMATCH"]
        if not gate.get("arm_allowed"):
            print(
                json.dumps(
                    {
                        "status": "BLOCKED",
                        "detail": "GO_NO_GO_REFUSED",
                        "armed": False,
                        "disposition": gate.get("disposition"),
                        "blockers": gate.get("blockers"),
                        "execution_authority": "BLOCKED",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2
        runtime_sha = str(gate.get("runtime_sha") or "")
    else:
        runtime_sha = None
    if not runtime_sha:
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
        session_end_utc=(str(args.session_end_utc).strip() if getattr(args, "session_end_utc", None) else None),
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
                "environment_preflight_skipped": skip_preflight,
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
    pid = int(args.pid)
    role = str(args.role)
    allowed_roles = {"supervisor", "poller", "api", "ui"}
    if role not in allowed_roles:
        print(json.dumps({"status": "ERROR", "detail": "ROLE_NOT_ALLOWED", "role": role}, sort_keys=True))
        return 2
    if not _alive_fn(pid):
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "detail": "CHILD_PID_NOT_ALIVE",
                    "role": str(args.role),
                    "pid": pid,
                },
                sort_keys=True,
            )
        )
        return 2
    spawn_book = state_dir / "campaign-supervision" / "spawn-identity.json"
    shim_pids: set[int] = set()
    if spawn_book.is_file():
        try:
            book = json.loads(spawn_book.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            book = {}
        if isinstance(book, dict):
            for item in book.get("spawns") or []:
                if isinstance(item, dict) and item.get("spawn_shim_pid") is not None:
                    shim = int(item["spawn_shim_pid"])
                    durable = item.get("durable_pid")
                    if durable is None or int(durable) != shim:
                        shim_pids.add(shim)
    if pid in shim_pids and not bool(getattr(args, "adopt_as_supervisor", False)):
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "detail": "SPAWN_SHIM_PID_IS_NOT_DURABLE_ROLE",
                    "role": role,
                    "pid": pid,
                },
                sort_keys=True,
            )
        )
        return 2
    if role == "supervisor" and not bool(getattr(args, "adopt_as_supervisor", False)):
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "detail": "SUPERVISOR_ROLE_REQUIRES_ADOPT",
                    "pid": pid,
                },
                sort_keys=True,
            )
        )
        return 2
    for existing in ownership.child_processes:
        if existing.role == role and int(existing.pid) == pid:
            print(
                json.dumps(
                    {"status": "REGISTERED_UNCHANGED", "role": role, "pid": pid},
                    sort_keys=True,
                )
            )
            return 0
    children = list(ownership.child_processes)
    children = [c for c in children if c.role != role]
    children.append(
        ProcessIdentity(
            role=role,
            pid=pid,
            create_time_utc=_utc_now(),
            parent_pid=os.getpid(),
            command_fingerprint=safe_command_fingerprint(list(args.identity_tokens or [args.role])),
            identity_tokens=list(args.identity_tokens or [args.role]),
        )
    )
    ownership.child_processes = children
    # Do NOT clobber ownership.supervisor_pid with the registering shell/CLI PID.
    # That was the Sep 23 defect: register-child from a transient parent made the
    # durable supervisor appear PROCESS_DEAD after the parent exited.
    if role == "supervisor" and bool(getattr(args, "adopt_as_supervisor", False)):
        ownership.supervisor_pid = pid
    write_ownership(ownership)
    print(
        json.dumps(
            {
                "status": "REGISTERED",
                "role": role,
                "pid": pid,
                "supervisor_pid_preserved": ownership.supervisor_pid,
            },
            sort_keys=True,
        )
    )
    return 0


def cmd_heartbeat(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args.state_dir)
    ownership = read_ownership(state_dir)
    if ownership is None:
        print(json.dumps({"status": "ERROR", "detail": "NO_OWNERSHIP"}))
        return 1
    if ownership.arm_status in {"CLEAN_SHUTDOWN", "RTH_CLOSE_SHUTDOWN"}:
        print(
            json.dumps(
                {
                    "status": ownership.arm_status,
                    "phase": "TERMINAL",
                    "heartbeat_advanced": False,
                },
                sort_keys=True,
            )
        )
        return 0
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
        process_alive_fn=_alive_fn,
    )
    if progress.get("outage") and args.record_outage:
        record_open_outage_if_changed(
            state_dir,
            ownership=ownership,
            progress=progress,
            detected_at_utc=now,
            interval_start_utc=str(last_poll or ownership.arm_timestamp_utc),
        )
    print(json.dumps({"status": "HEARTBEAT", "progress": progress}, indent=2, sort_keys=True))
    return 0 if progress.get("status") in {"HEALTHY", "STARTING"} else 2


def cmd_status(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args.state_dir)
    view = load_campaign_supervision_view(state_dir, process_alive_fn=_alive_fn)
    progress = view.get("progress") if isinstance(view.get("progress"), dict) else {}
    ownership = read_ownership(state_dir)
    defects = outage_ledger_defects(state_dir)
    if "LEDGER_UNREADABLE" in defects:
        view["outage_ledger_defects"] = defects
        view["outage_ledger"] = "UNAVAILABLE"
        print(json.dumps(view, indent=2, sort_keys=True))
        return 2
    if defects:
        view["outage_ledger_defects"] = defects
        view["outage_ledger"] = "MALFORMED"
        print(json.dumps(view, indent=2, sort_keys=True))
        return 2
    ledger = "NOT_APPLICABLE"
    if ownership is not None and progress.get("outage"):
        try:
            written = record_open_outage_if_changed(
                state_dir,
                ownership=ownership,
                progress=progress,
                detected_at_utc=str(view.get("as_of_utc") or _utc_now()),
                interval_start_utc=str(
                    progress.get("last_successful_poll_utc") or ownership.arm_timestamp_utc
                ),
            )
            ledger = "APPENDED" if written is not None else "OPEN_UNCHANGED"
            view["outages"] = read_outage_records(state_dir)
            view["active_outages"] = active_outage_records(view["outages"])
        except OSError:
            ledger = "UNAVAILABLE"
    elif ownership is not None and progress.get("healthy") and ownership.arm_status == "ARMED_RUNNING":
        try:
            closed = close_active_outages(
                state_dir,
                ownership=ownership,
                closed_at_utc=str(view.get("as_of_utc") or _utc_now()),
                close_reason=OUTAGE_CLOSE_RECOVERED,
                recovery_detected_by="STATUS_HEALTHY",
            )
            view["outages"] = read_outage_records(state_dir)
            view["active_outages"] = active_outage_records(view["outages"])
            ledger = "CLOSED" if closed else "NO_ACTIVE_OUTAGE"
        except OSError:
            ledger = "UNAVAILABLE"
    defects = outage_ledger_defects(state_dir)
    view["outage_ledger_defects"] = defects
    if defects and ledger != "UNAVAILABLE":
        ledger = "MALFORMED"
    view["outage_ledger"] = ledger
    print(json.dumps(view, indent=2, sort_keys=True))
    if ledger in {"UNAVAILABLE", "MALFORMED"}:
        return 2
    status = str(view.get("status") or "UNKNOWN")
    if status == "HEALTHY":
        return 0
    if status in {"NOT_APPLICABLE", "STARTING"}:
        return 0
    return 2


def cmd_environment_preflight(args: argparse.Namespace) -> int:
    from tools.platform.campaign_environment_preflight import (
        evaluate_campaign_environment_preflight,
    )

    raw_state = (args.state_dir or os.environ.get("IMP_STATE_DIR") or "").strip()
    report = evaluate_campaign_environment_preflight(
        root=ROOT,
        state_dir=raw_state or None,
        require_ui_deps=not bool(args.allow_missing_ui_deps),
        campaign_id=args.campaign_id,
        observation_window_id=args.observation_window_id,
        check_opend=not bool(args.skip_opend_check),
        require_finviz_live_ingress=bool(
            getattr(args, "require_finviz_live_ingress", False)
        ),
    )
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.ready_to_arm else 2


def cmd_go_no_go(args: argparse.Namespace) -> int:
    from tools.platform.campaign_go_no_go import evaluate_campaign_go_no_go

    raw_state = (args.state_dir or os.environ.get("IMP_STATE_DIR") or "").strip()
    report = evaluate_campaign_go_no_go(
        freeze_path=args.freeze,
        root=ROOT,
        state_dir=raw_state or None,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("go") else 2


def cmd_readiness(args: argparse.Namespace) -> int:
    """Read observation start-gate contract (same model as Operator Control)."""

    readiness_mod = _load_campaign_observation_readiness()
    state_dir = _state_dir(args.state_dir)
    intent_explicit = {
        "campaign_id": args.campaign_id,
        "intended_date_et": args.intended_date_et,
        "frozen": args.frozen,
        "runtime_sha": args.runtime_sha,
        "observation_window_id": args.observation_window_id,
    }
    # Drop unset CLI fields so env/intent-file can still supply them.
    intent_explicit = {k: v for k, v in intent_explicit.items() if v is not None and str(v).strip() != ""}
    payload = readiness_mod.compose_campaign_observation_readiness_for_state(
        state_dir,
        intent_explicit=intent_explicit or None,
        ingress_enabled=None,
        process_alive_fn=_alive_fn,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    if payload.get("has_blocking_alert"):
        return 2
    if payload.get("phase") in {"ACTIVE_STALLED", "BLOCKED_AUTHORITY", "BLOCKED_RUNTIME", "BLOCKED_STATE_DIR"}:
        return 2
    return 0


def _load_campaign_observation_readiness():
    """Import the readiness model as a package leaf.

    A standalone ``spec_from_file_location`` load breaks relative imports and
    crashes the operator ``readiness`` command. Package ``__init__`` keeps the
    snapshot lazy. This import does not grant execution authority.
    """

    from market_platform_foundation.platform.operator_diagnostics import (
        campaign_observation_readiness as module,
    )

    return module


def cmd_shutdown(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args.state_dir)
    ownership = read_ownership(state_dir)
    if ownership is None:
        print(json.dumps({"status": "ALREADY_STOPPED"}))
        return 0
    reason = "RTH_CLOSE_SHUTDOWN" if args.rth_close else "CLEAN_SHUTDOWN"
    now = _utc_now()
    terminated: list[dict[str, Any]] = []
    try:
        terminated = close_active_outages(
            state_dir,
            ownership=ownership,
            closed_at_utc=now,
            close_reason=OUTAGE_CLOSE_CAMPAIGN_TERMINATED,
            recovery_detected_by=None,
        )
    except OSError as exc:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "detail": "OUTAGE_LEDGER_UNAVAILABLE",
                    "error": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return 2
    ownership.arm_status = reason
    write_ownership(ownership)
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
    print(
        json.dumps(
            {
                "status": reason,
                "campaign_id": ownership.campaign_id,
                "outage": False,
                "active_outages_terminated": len(terminated),
                "recovered": False,
            },
            sort_keys=True,
        )
    )
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
        if not _alive_fn(int(args.child_pid)):
            print(
                json.dumps(
                    {
                        "status": "ERROR",
                        "detail": "CHILD_PID_NOT_ALIVE",
                        "role": str(args.child_role),
                        "pid": int(args.child_pid),
                    },
                    sort_keys=True,
                )
            )
            return 2
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
    # Preserve durable supervisor ownership unless explicitly adopting this process
    # as the long-lived supervisor (must remain alive after recover returns).
    if bool(getattr(args, "adopt_as_supervisor", False)):
        new_supervisor_pid = os.getpid()
    elif _alive_fn(int(ownership.supervisor_pid)):
        new_supervisor_pid = int(ownership.supervisor_pid)
    else:
        # Fail visible: do not silently claim the short-lived recover CLI is supervisor.
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "detail": "SUPERVISOR_PID_DEAD_USE_ADOPT_OR_RUN",
                    "prior_supervisor_pid": ownership.supervisor_pid,
                    "hint": "Spawn `run` (durable) or pass --adopt-as-supervisor only from a long-lived process",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    recovered = preserve_arm_for_recovery(
        ownership,
        supervisor_pid=new_supervisor_pid,
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
                "supervisor_pid": recovered.supervisor_pid,
                "new_segment_created": False,
                "backfill_applied": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _infer_spawn_role(argv: Sequence[str]) -> str | None:
    tokens = [str(part) for part in argv]
    if "poll-loop" in tokens:
        return "poller"
    if "run" in tokens:
        return "supervisor"
    return None


def _remember_spawn(state_dir: Path, record: dict[str, Any]) -> None:
    path = state_dir / "campaign-supervision" / "spawn-identity.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    book: dict[str, Any] = {"spawns": []}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        if isinstance(loaded, dict) and isinstance(loaded.get("spawns"), list):
            book = loaded
    book.setdefault("spawns", []).append(record)
    _cs._atomic_write_json(path, book)


def _wait_durable_pid(state_dir: Path, role: str | None, shim_pid: int, timeout: float = 8.0) -> int | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        ownership = read_ownership(state_dir)
        if ownership is None:
            time.sleep(0.1)
            continue
        if role == "supervisor" and _alive_fn(int(ownership.supervisor_pid)):
            return int(ownership.supervisor_pid)
        if role == "poller":
            for child in ownership.child_processes:
                if child.role == "poller" and _alive_fn(int(child.pid)):
                    return int(child.pid)
        if role is None and _alive_fn(shim_pid):
            return shim_pid
        time.sleep(0.1)
    if _alive_fn(shim_pid):
        return shim_pid
    return None


def cmd_spawn_detached(args: argparse.Namespace) -> int:
    state_dir = _state_dir(args.state_dir)
    argv = list(args.spawn_argv or [])
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        print(json.dumps({"status": "ERROR", "detail": "COMMAND_REQUIRED"}))
        return 2
    role = _infer_spawn_role(argv)
    log_name = f"{role}.log" if role else "detached-other.log"
    log_path = state_dir / "campaign-supervision" / "logs" / log_name
    shim_pid = spawn_detached(
        argv,
        cwd=ROOT,
        log_path=log_path,
        role=role or "other",
    )
    durable_pid = _wait_durable_pid(state_dir, role, shim_pid)
    if durable_pid is None:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "detail": "DURABLE_PID_UNRESOLVED",
                    "spawn_shim_pid": shim_pid,
                    "role": role,
                    "log_path": str(log_path),
                },
                sort_keys=True,
            )
        )
        return 2
    record = {
        "spawn_shim_pid": shim_pid,
        "durable_pid": durable_pid,
        "role": role,
        "log_path": str(log_path),
        "spawned_at_utc": _utc_now(),
        "pid_contract": "spawn_shim_pid_is_not_the_durable_role_pid",
    }
    _remember_spawn(state_dir, record)
    print(
        json.dumps(
            {
                "status": "SPAWNED",
                "spawn_shim_pid": shim_pid,
                "durable_pid": durable_pid,
                "role": role,
                "pids_differ": shim_pid != durable_pid,
                "pid_contract": "use_durable_pid_not_spawn_shim_pid",
                "mechanism": mechanism_description(),
                "log_path": str(log_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


_TERMINAL_ARM = frozenset({"CLEAN_SHUTDOWN", "RTH_CLOSE_SHUTDOWN"})
_SHUTDOWN_POLL_SECONDS = 0.2


def _shutdown_requested(state_dir: Path) -> str | None:
    ownership = read_ownership(state_dir)
    if ownership is None:
        return "NO_OWNERSHIP"
    if ownership.arm_status in _TERMINAL_ARM:
        return str(ownership.arm_status)
    return None


def _session_boundary_reached(ownership: CampaignOwnership, now_epoch: float) -> bool:
    end = _cs._parse_utc_seconds(ownership.session_end_utc)
    if end is None:
        return False
    return now_epoch >= end


def wait_until_shutdown_or_deadline(state_dir: Path, seconds: float) -> str | None:
    """Sleep until cadence elapses or governed shutdown is visible.

    Returns the shutdown reason, or None when the wait completed.
    Slices are 0.2s so this does not busy-loop and does not sleep the full cadence.
    """

    deadline = time.monotonic() + max(0.0, seconds)
    while True:
        reason = _shutdown_requested(state_dir)
        if reason is not None:
            return reason
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        time.sleep(min(_SHUTDOWN_POLL_SECONDS, remaining))


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
        # Only rewrite ownership when supervisor identity drifts — avoid Windows
        # atomic-replace races with poll-loop / register-child.
        if int(ownership.supervisor_pid) != os.getpid():
            ownership.supervisor_pid = os.getpid()
            write_ownership(ownership)
        if _shutdown_requested(state_dir) is not None:
            print(json.dumps({"status": _shutdown_requested(state_dir), "stopped": True, "phase": "TERMINAL"}))
            return 0
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
            if ownership.expected_next_cycle_utc != heartbeat["expected_next_poll_utc"]:
                ownership.expected_next_cycle_utc = heartbeat["expected_next_poll_utc"]
                write_ownership(ownership)
        if _shutdown_requested(state_dir) is not None:
            print(json.dumps({"status": ownership.arm_status, "stopped": True, "phase": "TERMINAL", "heartbeat_advanced": False}))
            return 0
        write_heartbeat(state_dir, heartbeat)
        progress = evaluate_campaign_progress(
            ownership=ownership,
            heartbeat=heartbeat,
            now_utc_epoch=now_epoch,
            process_alive_fn=_alive_fn,
        )
        if progress.get("outage"):
            record_open_outage_if_changed(
                state_dir,
                ownership=ownership,
                progress=progress,
                detected_at_utc=now,
                interval_start_utc=str(
                    heartbeat.get("last_successful_poll_utc") or ownership.arm_timestamp_utc
                ),
            )
        elif progress.get("healthy"):
            close_active_outages(
                state_dir,
                ownership=ownership,
                closed_at_utc=now,
                close_reason=OUTAGE_CLOSE_RECOVERED,
                recovery_detected_by="SUPERVISOR_HEALTHY",
            )
        marker = state_dir / "campaign-supervision" / "supervisor.alive"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{os.getpid()}\n{now}\n", encoding="utf-8")
        count += 1
        if iterations > 0 and count >= iterations:
            break
        stopped = wait_until_shutdown_or_deadline(state_dir, max(0.05, cadence))
        if stopped is not None:
            print(json.dumps({"status": stopped, "stopped": True, "phase": "TERMINAL"}))
            return 0
    return 0


_SUCCESSFUL_POLL_CLASSES = frozenset({"SUCCESS", "SUCCESS_EMPTY", "SOFTWARE_CONTROLLED_CYCLE"})
_PROVIDER_FAILURE_CLASSES = frozenset(
    {
        "PROVIDER_FAILURE",
        "HTTP_429",
        "TIMEOUT",
        "MALFORMED_RESPONSE",
        "TOKEN_ABSENT",
        "GATES_INACTIVE",
        "SECRET_DIR_MISSING",
        "SESSION_UNAVAILABLE",
    }
)
_ADMISSION_MARKERS = (
    "UI_API_COCKPIT_ADMIT_UNREACHABLE",
    "COCKPIT_ADMIT_UI_API_UNAVAILABLE",
    "ADMISSION_FAILURE",
)


def classify_observed_poll(
    payload: dict[str, Any] | None,
    *,
    invoked: bool,
    process_ok: bool,
) -> str:
    """Separate a real empty poll from failure, no poll, and process death.

    ``SOFTWARE_CONTROLLED_CYCLE`` is only assigned by the caller for the
    fixture loop. This function never upgrades a payload into market proof.
    """

    if not invoked:
        return "NO_POLL"
    if payload is None:
        return "POLL_PROCESS_FAILURE"
    blockers = payload.get("blockers")
    blocker_text = " ".join(str(item) for item in blockers) if isinstance(blockers, list) else ""
    outcome = str(payload.get("ingress_outcome") or "")
    prospective = payload.get("prospective_ingress")
    nested = prospective if isinstance(prospective, dict) else {}
    classification = str(
        payload.get("ingress_classification")
        or nested.get("classification")
        or payload.get("classification")
        or ""
    ).strip()
    marker_blob = " ".join((classification, outcome, blocker_text))
    if any(marker in marker_blob for marker in _ADMISSION_MARKERS):
        return "ADMISSION_FAILURE"
    if classification in _PROVIDER_FAILURE_CLASSES:
        return classification
    if classification in {"SUCCESS_EMPTY", "SUCCESS"}:
        return classification
    if "SUCCESS_ZERO_QUALIFYING" in outcome or "SUCCESS_EMPTY" in outcome:
        return "SUCCESS_EMPTY"
    if not process_ok:
        return "POLL_PROCESS_FAILURE"
    if classification:
        return "POLL_UNCLASSIFIED"
    return "POLL_PROCESS_FAILURE" if not process_ok else "POLL_UNCLASSIFIED"


def _parse_poll_json(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            payload = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    return payload if isinstance(payload, dict) else None


def _append_poll_attempt(state_dir: Path, record: dict[str, Any]) -> None:
    path = state_dir / "campaign-supervision" / "poll-attempts.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(record)
    body.setdefault("synthetic_poll_generated", False)
    body.setdefault("backfill_applied", False)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(body, sort_keys=True, separators=(",", ":")))
        handle.write("\n")


def _live_ingress_argv(ownership: CampaignOwnership, campaign_slug: str) -> list[str]:
    """Canonical prospective Finviz watch. Does not grant execution authority."""

    argv = [
        sys.executable,
        str(ROOT / "tools" / "ftep_watch_catalysts.py"),
        campaign_slug,
        "--live-ingress",
        "--json",
        "--current-segment-session-id",
        str(ownership.observation_window_id),
    ]
    arm = str(ownership.arm_timestamp_utc or "")
    if arm:
        text = arm[:-1] + "+00:00" if arm.endswith("Z") else arm
        try:
            arm_dt = datetime.fromisoformat(text)
            argv.extend(["--current-segment-start-ns", str(int(arm_dt.timestamp() * 1_000_000_000))])
        except ValueError:
            pass
    return argv


def _invoke_poll_payload(
    args: argparse.Namespace,
    ownership: CampaignOwnership,
    state_dir: Path,
) -> tuple[dict[str, Any] | None, bool, bool, str, str | None]:
    """Return payload, invoked, process_ok, evidence class, interrupt reason.

    Interrupt reason is set only when governed shutdown cancels work before a
    response is persisted. A finished response is returned even if shutdown
    landed while the process was exiting; the caller stamps the boundary.
    """

    ingress_json = str(getattr(args, "ingress_json", "") or "").strip()
    if ingress_json:
        path = Path(ingress_json)
        if not path.is_file():
            return None, True, False, "SOFTWARE_CONTROLLED", None
        try:
            payload = _parse_poll_json(path.read_text(encoding="utf-8"))
        except OSError:
            return None, True, False, "SOFTWARE_CONTROLLED", None
        return payload, True, payload is not None, "SOFTWARE_CONTROLLED", None
    block_seconds = float(getattr(args, "block_seconds", 0) or 0)
    if block_seconds > 0:
        deadline = time.monotonic() + block_seconds
        while True:
            stopped = _shutdown_requested(state_dir)
            if stopped is not None:
                return None, True, False, "SOFTWARE_CONTROLLED", stopped
            if _session_boundary_reached(ownership, time.time()):
                return None, True, False, "SOFTWARE_CONTROLLED", "SESSION_BOUNDARY"
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(_SHUTDOWN_POLL_SECONDS, remaining))
        return {
            "classification": "SOFTWARE_CONTROLLED_BLOCK",
            "ingress_classification": "SOFTWARE_CONTROLLED_BLOCK",
        }, True, True, "SOFTWARE_CONTROLLED", None
    if bool(getattr(args, "live_ingress", False)):
        import subprocess

        argv = _live_ingress_argv(ownership, str(getattr(args, "campaign_slug", "") or "FTEP-V1-002"))
        try:
            process = subprocess.Popen(
                argv,
                cwd=str(ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError:
            return None, True, False, "LIVE_OBSERVATIONAL_ATTEMPT", None
        deadline = time.monotonic() + 120
        while process.poll() is None:
            stop = _shutdown_requested(state_dir)
            if stop is None and _session_boundary_reached(ownership, time.time()):
                stop = "SESSION_BOUNDARY"
            if stop is not None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
                return None, True, False, "LIVE_OBSERVATIONAL_ATTEMPT", stop
            if time.monotonic() >= deadline:
                process.kill()
                process.wait(timeout=2)
                return None, True, False, "LIVE_OBSERVATIONAL_ATTEMPT", None
            time.sleep(_SHUTDOWN_POLL_SECONDS)
        stdout, _stderr = process.communicate()
        payload = _parse_poll_json(stdout or "")
        return payload, True, process.returncode == 0 and payload is not None, "LIVE_OBSERVATIONAL_ATTEMPT", None
    return None, False, True, "SOFTWARE_CONTROLLED", None


def cmd_poll_loop(args: argparse.Namespace) -> int:
    """Long-lived poller role. One-shot ingress must not register as this role.

    Default cycles are ``SOFTWARE_CONTROLLED_CYCLE`` and are not market polls.
    ``--ingress-json`` classifies a fixture receipt. ``--live-ingress`` runs the
    canonical Finviz watch once per cycle and records empty success separately
    from provider failure, admission failure, and process failure.
    """

    state_dir = _state_dir(args.state_dir)
    ownership = read_ownership(state_dir)
    if ownership is None:
        print(json.dumps({"status": "ERROR", "detail": "ARM_REQUIRED"}))
        return 1
    children = [c for c in ownership.child_processes if c.role != "poller"]
    children.append(
        ProcessIdentity(
            role="poller",
            pid=os.getpid(),
            create_time_utc=_utc_now(),
            parent_pid=os.getppid() if hasattr(os, "getppid") else None,
            command_fingerprint=safe_command_fingerprint(
                ["python", "tools/platform/campaign_supervisor.py", "poll-loop"]
            ),
            identity_tokens=["poller", "poll-loop"],
        )
    )
    ownership.child_processes = children
    write_ownership(ownership)
    cadence = float(args.poll_cadence_seconds or ownership.expected_poll_cadence_seconds)
    hb_cadence = float(args.heartbeat_cadence_seconds or DEFAULT_HEARTBEAT_CADENCE_SECONDS)
    stale_after = float(args.stale_after_seconds or DEFAULT_STALE_AFTER_SECONDS)
    iterations = int(args.iterations)
    count = 0
    print(
        json.dumps(
            {
                "status": "POLLER_RUNNING",
                "pid": os.getpid(),
                "campaign_id": ownership.campaign_id,
                "evidence_class": "SOFTWARE_CONTROLLED_EVIDENCE",
                "execution_authority": "BLOCKED",
            },
            sort_keys=True,
        )
    )
    while iterations <= 0 or count < iterations:
        ownership = read_ownership(state_dir)
        if ownership is None:
            return 1
        if ownership.arm_status in _TERMINAL_ARM:
            print(json.dumps({"status": ownership.arm_status, "stopped": True, "phase": "TERMINAL"}))
            return 0
        now_epoch = time.time()
        if _session_boundary_reached(ownership, now_epoch):
            prior = read_heartbeat(state_dir) or {}
            held = {
                **prior,
                "campaign_id": ownership.campaign_id,
                "runtime_sha": ownership.runtime_sha,
                "last_heartbeat_utc": _utc_now(),
                "phase": "SESSION_BOUNDARY_HOLD",
                "application_ready": True,
                "poller_pid": os.getpid(),
                "synthetic_poll_generated": False,
            }
            write_heartbeat(state_dir, held)
            count += 1
            if iterations > 0 and count >= iterations:
                print(json.dumps({"status": "SESSION_BOUNDARY_HOLD", "poll_started": False, "stopped": False}))
                return 0
            stopped = wait_until_shutdown_or_deadline(state_dir, max(0.05, cadence))
            if stopped is not None:
                print(json.dumps({"status": stopped, "stopped": True, "phase": "TERMINAL", "poll_started": False}))
                return 0
            continue
        now = _utc_now()
        prior = read_heartbeat(state_dir) or {}
        payload, invoked, process_ok, evidence_class, interrupted = _invoke_poll_payload(args, ownership, state_dir)
        boundary = None
        if interrupted is not None:
            classification = "SHUTDOWN_INTERRUPTED"
            evidence_class = evidence_class or "SOFTWARE_CONTROLLED"
            invoked = True
            boundary = {
                "poll_boundary": "INTERRUPTED_BEFORE_RECEIPT",
                "counts_as_in_window_observation": False,
                "shutdown_reason": interrupted,
            }
        elif _shutdown_requested(state_dir) is not None and invoked:
            boundary = {
                "poll_boundary": "INITIATED_BEFORE_CLOSE_COMPLETED_AFTER",
                "counts_as_in_window_observation": False,
                "shutdown_reason": _shutdown_requested(state_dir),
            }
            classification = classify_observed_poll(payload, invoked=True, process_ok=process_ok)
        elif invoked and _session_boundary_reached(ownership, time.time()):
            boundary = {
                "poll_boundary": "INITIATED_BEFORE_CLOSE_COMPLETED_AFTER",
                "counts_as_in_window_observation": False,
                "shutdown_reason": "SESSION_BOUNDARY",
            }
            classification = classify_observed_poll(payload, invoked=True, process_ok=process_ok)
        elif invoked:
            classification = classify_observed_poll(payload, invoked=True, process_ok=process_ok)
        else:
            classification = "SOFTWARE_CONTROLLED_CYCLE"
            evidence_class = "SOFTWARE_CONTROLLED"
        advances = classification in _SUCCESSFUL_POLL_CLASSES
        if boundary is not None and boundary.get("counts_as_in_window_observation") is False:
            advances = False
        next_poll = (
            datetime.fromtimestamp(now_epoch + cadence, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
        last_success = now if advances else prior.get("last_successful_poll_utc")
        heartbeat = {
            **prior,
            "campaign_id": ownership.campaign_id,
            "runtime_sha": ownership.runtime_sha,
            "supervisor_pid": ownership.supervisor_pid,
            "last_heartbeat_utc": now,
            "last_poll_attempt_utc": now,
            "last_poll_classification": classification,
            "last_successful_poll_utc": last_success,
            "poll_evidence_class": evidence_class,
            "expected_next_heartbeat_utc": datetime.fromtimestamp(
                now_epoch + hb_cadence, tz=timezone.utc
            )
            .isoformat()
            .replace("+00:00", "Z"),
            "expected_next_poll_utc": next_poll if advances else prior.get("expected_next_poll_utc"),
            "heartbeat_cadence_seconds": hb_cadence,
            "poll_cadence_seconds": cadence,
            "stale_after_seconds": stale_after,
            "application_ready": True,
            "port_bound_without_progress": False,
            "phase": "POLLER_CYCLE" if boundary is None else "POLLER_BOUNDARY",
            "synthetic_poll_generated": False,
            "poller_pid": os.getpid(),
            "poll_boundary": None if boundary is None else boundary.get("poll_boundary"),
            "counts_as_in_window_observation": None if boundary is None else boundary.get("counts_as_in_window_observation"),
        }
        _append_poll_attempt(
            state_dir,
            {
                "campaign_id": ownership.campaign_id,
                "runtime_sha": ownership.runtime_sha,
                "attempted_at_utc": now,
                "classification": classification,
                "evidence_class": evidence_class,
                "advances_successful_poll": advances,
                "provider_invoked": bool(getattr(args, "live_ingress", False)),
                "fixture_receipt": bool(str(getattr(args, "ingress_json", "") or "").strip()),
                "process_ok": process_ok,
                "poll_boundary": None if boundary is None else boundary.get("poll_boundary"),
                "counts_as_in_window_observation": (
                    True if boundary is None else boundary.get("counts_as_in_window_observation")
                ),
            },
        )
        if interrupted is not None or _shutdown_requested(state_dir) is not None:
            heartbeat["phase"] = _shutdown_requested(state_dir) or "TERMINAL"
            heartbeat["application_ready"] = False
        # Heartbeat-only updates in the loop — do not contend on ownership.json.
        write_heartbeat(state_dir, heartbeat)
        marker = state_dir / "campaign-supervision" / "poller.alive"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(f"{os.getpid()}\n{now}\n{count}\n", encoding="utf-8")
        count += 1
        if interrupted is not None or _shutdown_requested(state_dir) is not None:
            print(json.dumps({"status": _shutdown_requested(state_dir) or interrupted, "stopped": True, "phase": "TERMINAL", "poll_started_after_shutdown": False}))
            return 0
        if iterations > 0 and count >= iterations:
            break
        stopped = wait_until_shutdown_or_deadline(state_dir, max(0.05, cadence))
        if stopped is not None:
            print(json.dumps({"status": stopped, "stopped": True, "phase": "TERMINAL", "poll_started_after_shutdown": False}))
            return 0
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="IMP campaign supervisor (minimal)")
    sub = parser.add_subparsers(dest="command", required=True)

    mech = sub.add_parser("mechanism", help="Describe detachment mechanism")
    mech.set_defaults(func=cmd_mechanism)

    arm = sub.add_parser(
        "arm",
        help="ARM OBSERVATION: write durable campaign ownership (execution stays BLOCKED; never GO LIVE)",
    )
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
    arm.add_argument(
        "--skip-environment-preflight",
        action="store_true",
        help="Escape hatch for unit fixtures only; production arm should not skip",
    )
    arm.add_argument(
        "--allow-missing-ui-deps",
        action="store_true",
        help="Allow arm when ui/node_modules is absent (UI remains optional runtime role)",
    )
    arm.add_argument(
        "--require-finviz-live-ingress",
        action="store_true",
        help="Fail arm when the live Finviz ingress resolver has no credential or gates are off",
    )
    arm.add_argument(
        "--freeze",
        default=None,
        help="Campaign freeze JSON. When set, arm runs GO/NO-GO and refuses unless READY_FOR_PRE_RTH_ARM.",
    )
    arm.add_argument(
        "--session-end-utc",
        default=None,
        help="UTC instant at which poll-loop must not start a new cycle (RTH close boundary)",
    )
    arm.set_defaults(func=cmd_arm)

    pref = sub.add_parser(
        "environment-preflight",
        help="Fail-visible environment readiness before ARM OBSERVATION",
    )
    pref.add_argument("--state-dir")
    pref.add_argument("--campaign-id")
    pref.add_argument("--observation-window-id")
    pref.add_argument("--allow-missing-ui-deps", action="store_true")
    pref.add_argument("--skip-opend-check", action="store_true")
    pref.add_argument(
        "--require-finviz-live-ingress",
        action="store_true",
        help="Fail when live Finviz ingress cannot resolve a credential or its gates are off",
    )
    pref.set_defaults(func=cmd_environment_preflight)

    reg = sub.add_parser("register-child", help="Record a supervised child process")
    reg.add_argument("--state-dir")
    reg.add_argument("--role", required=True)
    reg.add_argument("--pid", type=int, required=True)
    reg.add_argument("--identity-tokens", nargs="*")
    reg.add_argument(
        "--adopt-as-supervisor",
        action="store_true",
        help="Only when registering a durable supervisor PID; never from a one-shot shell",
    )
    reg.set_defaults(func=cmd_register_child)

    hb = sub.add_parser("heartbeat", help="Record heartbeat / optional poll progress")
    hb.add_argument("--state-dir")
    hb.add_argument("--successful-poll", "--mark-poll-success", action="store_true", dest="successful_poll")
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

    readiness = sub.add_parser(
        "readiness",
        help="Observation start-gate read model (fail-visible NOT_ARMED / API / UI / heartbeat)",
    )
    readiness.add_argument("--state-dir")
    readiness.add_argument("--campaign-id")
    readiness.add_argument("--intended-date-et", help="YYYY-MM-DD America/New_York")
    readiness.add_argument("--frozen", choices=["yes", "no"])
    readiness.add_argument("--runtime-sha")
    readiness.add_argument("--observation-window-id")
    readiness.set_defaults(func=cmd_readiness)

    go = sub.add_parser(
        "go-no-go",
        help="Fail-closed pre-open GO/NO-GO. Does not arm.",
    )
    go.add_argument("--freeze", required=True)
    go.add_argument("--state-dir")
    go.set_defaults(func=cmd_go_no_go)

    shutdown = sub.add_parser("shutdown", help="Deliberate clean or RTH-close shutdown")
    shutdown.add_argument("--state-dir")
    shutdown.add_argument("--rth-close", action="store_true")
    shutdown.set_defaults(func=cmd_shutdown)

    recover = sub.add_parser("recover", help="Deliberate recovery preserving original arm")
    recover.add_argument("--state-dir")
    recover.add_argument("--child-role")
    recover.add_argument("--child-pid", type=int)
    recover.add_argument("--force", action="store_true")
    recover.add_argument(
        "--adopt-as-supervisor",
        action="store_true",
        help="Adopt this long-lived process as supervisor; never from a one-shot recover shell",
    )
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
    run.add_argument(
        "--heartbeat-cadence-seconds",
        type=float,
        default=DEFAULT_HEARTBEAT_CADENCE_SECONDS,
    )
    run.add_argument("--stale-after-seconds", type=float, default=DEFAULT_STALE_AFTER_SECONDS)
    run.add_argument("--iterations", type=int, default=0, help="0 = until shutdown")
    run.add_argument("--auto-poll", action="store_true")
    run.set_defaults(func=cmd_run)

    poll = sub.add_parser(
        "poll-loop",
        help="Long-lived SOFTWARE_CONTROLLED poller role (not one-shot ingress)",
    )
    poll.add_argument("--state-dir")
    poll.add_argument("--poll-cadence-seconds", type=float)
    poll.add_argument("--heartbeat-cadence-seconds", type=float, default=DEFAULT_HEARTBEAT_CADENCE_SECONDS)
    poll.add_argument("--stale-after-seconds", type=float, default=DEFAULT_STALE_AFTER_SECONDS)
    poll.add_argument("--iterations", type=int, default=0, help="0 = until shutdown")
    poll.add_argument(
        "--block-seconds",
        type=float,
        default=0,
        help="Software-controlled stand-in for an in-flight provider call. No network.",
    )
    poll.add_argument(
        "--ingress-json",
        default="",
        help="SOFTWARE_CONTROLLED fixture receipt. Does not call a provider.",
    )
    poll.add_argument(
        "--live-ingress",
        action="store_true",
        help="Each cycle runs ftep_watch_catalysts --live-ingress. Not an off-hours market proof.",
    )
    poll.add_argument("--campaign-slug", default="FTEP-V1-002")
    poll.set_defaults(func=cmd_poll_loop)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())

"""Authoritative pre-open GO/NO-GO for a frozen prospective RTH campaign.

This command does not arm. Arm remains ``campaign_supervisor.py arm --freeze``.
Secrets are never printed. Evidence class stays software coordination.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Callable, Mapping
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)
SCHEMA_VERSION = "campaign-go-no-go/1.0.0"
FREEZE_SCHEMA = "campaign-freeze/1.1.0"
EVIDENCE_CLASS = "SOFTWARE_COORDINATION"

DISPOSITIONS = (
    "READY_FOR_PRE_RTH_ARM",
    "BLOCKED",
    "NOT_YET_IN_WINDOW",
    "ALREADY_ARMED",
    "TERMINAL",
    "MISSED_WINDOW",
)

_TERMINAL = {"CLEAN_SHUTDOWN", "RTH_CLOSE_SHUTDOWN"}
_LIVE_ENV = (
    "IMP_LIVE_EXECUTION",
    "IMP_ALLOW_NETWORK_SUBMIT",
    "IMP_LIVE_SUBMIT",
)
_HASH_EXCLUDED = {"freeze_sha256"}


def canonical_freeze_sha256(document: Mapping[str, Any]) -> str:
    body = {k: document[k] for k in sorted(document) if k not in _HASH_EXCLUDED}
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def next_trading_session(after: date) -> date:
    from market_platform_foundation.intelligence.forward_qualification.evidence01.continuity import (
        is_trading_day,
    )

    day = after
    while True:
        day = date.fromordinal(day.toordinal() + 1)
        if is_trading_day(day):
            return day


def campaign_id_for_session(session: date) -> str:
    return f"RTH-OBS-NEWS-{session.strftime('%Y%m%d')}"


def _flag_on(environ: Mapping[str, str], name: str) -> bool:
    return str(environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_day(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _git(cwd: Path, *args: str, allow_empty: bool = False) -> str | None:
    git = shutil.which("git.exe") or shutil.which("git")
    if not git:
        return None
    try:
        result = subprocess.run(
            [git, *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    text = (result.stdout or "").strip()
    return text if text or allow_empty else None


def _port_open(host: str, port: int) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _ownership(state_dir: Path | None) -> dict[str, Any] | None:
    if state_dir is None:
        return None
    path = state_dir / "campaign-supervision" / "ownership.json"
    if not path.is_file():
        return None
    return _read_json(path)


def _heartbeat(state_dir: Path | None) -> dict[str, Any] | None:
    if state_dir is None:
        return None
    path = state_dir / "campaign-supervision" / "heartbeat.json"
    if not path.is_file():
        return None
    return _read_json(path)


def evaluate_campaign_go_no_go(
    *,
    freeze_path: Path | str,
    root: Path,
    state_dir: Path | str | None = None,
    now_et: datetime | None = None,
    environ: Mapping[str, str] | None = None,
    git_head: str | None = None,
    git_tree: str | None = None,
    worktree_dirty: bool | None = None,
    port_open: bool | None = None,
    api_identity_sha: str | None = None,
    credential_available: bool | None = None,
    credential_source: str | None = None,
    probe_network: bool = True,
) -> dict[str, Any]:
    """Return a fail-closed GO/NO-GO report. Does not arm or mutate config."""

    env = dict(environ if environ is not None else os.environ)
    now = now_et or datetime.now(ET)
    if now.tzinfo is None:
        now = now.replace(tzinfo=ET)
    else:
        now = now.astimezone(ET)

    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, detail: str) -> None:
        checks.append({"name": name, "status": status, "detail": detail, "blocking": status == "FAIL"})

    path = Path(freeze_path)
    document = _read_json(path) if path.is_file() else None
    if document is None:
        add("freeze_exists", "FAIL", "FREEZE_MISSING_OR_UNREADABLE")
        return _finish(checks, now, document=None, campaign_id=None, session=None)

    expected_hash = str(document.get("freeze_sha256") or "")
    actual_hash = canonical_freeze_sha256(document)
    if not expected_hash or expected_hash != actual_hash:
        add("freeze_sha256", "FAIL", "FREEZE_HASH_MISMATCH")
    else:
        add("freeze_sha256", "PASS", actual_hash)

    if str(document.get("schema_version") or "") != FREEZE_SCHEMA:
        add("freeze_schema", "FAIL", "FREEZE_SCHEMA_MISMATCH")
    else:
        add("freeze_schema", "PASS", FREEZE_SCHEMA)

    campaign_id = str(document.get("campaign_id") or "")
    session = _parse_day(str(document.get("session_date") or ""))
    expected_id = campaign_id_for_session(session) if session else ""
    if not campaign_id or campaign_id != expected_id:
        add("campaign_id", "FAIL", "CAMPAIGN_ID_MISMATCH")
    else:
        add("campaign_id", "PASS", campaign_id)

    if session is None:
        add("session_date", "FAIL", "SESSION_DATE_INVALID")
    else:
        from market_platform_foundation.intelligence.forward_qualification.evidence01.continuity import (
            is_trading_day,
        )

        if not is_trading_day(session):
            add("session_date", "FAIL", "SESSION_DATE_NOT_TRADING_DAY")
        else:
            add("session_date", "PASS", session.isoformat())

    if str(document.get("campaign_state") or "") != "FROZEN_NOT_ARMED":
        add("campaign_state", "FAIL", "FREEZE_NOT_FROZEN_NOT_ARMED")
    else:
        add("campaign_state", "PASS", "FROZEN_NOT_ARMED")

    if document.get("arm_performed") is not False or document.get("empirically_proven") is not False:
        add("empirical_claims", "FAIL", "FREEZE_CLAIMS_ARM_OR_EMPIRICAL")
    else:
        add("empirical_claims", "PASS", "not armed; not empirical")

    head = git_head if git_head is not None else _git(root, "rev-parse", "HEAD")
    tree = git_tree if git_tree is not None else _git(root, "rev-parse", "HEAD^{tree}")
    runtime = str(document.get("runtime_sha") or "")
    runtime_tree = str(document.get("runtime_tree_sha") or "")
    if not head or head != runtime:
        add("runtime_sha", "FAIL", "RUNTIME_SHA_MISMATCH")
    else:
        add("runtime_sha", "PASS", head)
    if not tree or tree != runtime_tree:
        add("runtime_tree", "FAIL", "RUNTIME_TREE_MISMATCH")
    else:
        add("runtime_tree", "PASS", tree)

    if worktree_dirty is None:
        porcelain = _git(root, "status", "--porcelain", "--untracked-files=no", allow_empty=True)
        if porcelain is None:
            add("worktree", "FAIL", "WORKTREE_STATUS_UNAVAILABLE")
        worktree_dirty = bool(porcelain)
    if worktree_dirty:
        add("worktree", "FAIL", "DIRTY_WORKTREE")
    elif not any(c["name"] == "worktree" for c in checks):
        add("worktree", "PASS", "clean tracked tree")

    evidence = str(document.get("evidence_namespace") or "")
    rehearsal = str(document.get("rehearsal_namespace") or "")
    if not evidence or not rehearsal or evidence == rehearsal:
        add("evidence_namespace", "FAIL", "REHEARSAL_EMPIRICAL_PATH_COLLISION")
    else:
        add("evidence_namespace", "PASS", evidence)
        add("rehearsal_namespace", "PASS", rehearsal)

    state_path = Path(state_dir).expanduser() if state_dir else None
    if state_path is None:
        add("state_directory", "FAIL", "STATE_DIR_MISSING")
    else:
        resolved = str(state_path)
        if rehearsal and rehearsal.replace("\\", "/") in resolved.replace("\\", "/"):
            add("state_directory", "FAIL", "STATE_DIR_IS_REHEARSAL")
        elif evidence and not resolved.replace("\\", "/").endswith(evidence.replace("\\", "/")):
            # Allow the absolute form of the campaign namespace.
            tail = evidence.replace("\\", "/").split("/")[-1]
            if tail and tail not in resolved.replace("\\", "/"):
                add("state_directory", "FAIL", "STATE_DIR_NOT_CAMPAIGN_NAMESPACE")
            else:
                _writable(state_path, add)
        else:
            _writable(state_path, add)

    for name in _LIVE_ENV:
        if _flag_on(env, name):
            add("live_execution", "FAIL", "LIVE_UNEXPECTEDLY_ON")
            break
    else:
        if str(document.get("live_execution") or "") != "OFF":
            add("live_execution", "FAIL", "FREEZE_LIVE_NOT_OFF")
        else:
            add("live_execution", "PASS", "OFF")

    calib = str(env.get("ITEM9_CALIBRATION_RUN") or document.get("item9_calibration_run") or "")
    if _flag_on(env, "ITEM9_CALIBRATION_RUN") or calib not in {"", "FORBIDDEN"}:
        add("item9_calibration_run", "FAIL", "CALIBRATION_UNEXPECTEDLY_ENABLED")
    else:
        add("item9_calibration_run", "PASS", "FORBIDDEN")

    full30 = str(env.get("FULL30") or document.get("full30") or "")
    if _flag_on(env, "FULL30") or full30 not in {"", "NOT_RUN"}:
        add("full30", "FAIL", "FULL30_UNEXPECTEDLY_ENABLED")
    else:
        add("full30", "PASS", "NOT_RUN")

    if credential_available is None:
        from market_platform_foundation.intelligence.paper_forward_bridge.ftep_prospective_catalyst_ingress import (
            describe_finviz_ingress_credential_availability,
        )

        cred = describe_finviz_ingress_credential_availability(root, env=env)
        credential_available = bool(cred.available)
        credential_source = cred.source if cred.available else cred.classification
    if credential_available:
        add("provider_credential", "PASS", f"source={credential_source or 'recognized'}")
    else:
        add("provider_credential", "FAIL", "PROVIDER_CREDENTIAL_ABSENT")

    if not _flag_on(env, "IMP_FINVIZ_LIVE"):
        add("provider_enabled", "FAIL", "PROVIDER_DISABLED")
    else:
        add("provider_enabled", "PASS", "IMP_FINVIZ_LIVE")
    if not _flag_on(env, "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS"):
        add("ingress_gate", "FAIL", "INGRESS_NOT_ENABLED")
    else:
        add("ingress_gate", "PASS", "IMP_FTEP_PROSPECTIVE_CATALYST_INGRESS")

    supervisor = root / "tools" / "platform" / "campaign_supervisor.py"
    if supervisor.is_file():
        add("supervisor_tool", "PASS", "campaign_supervisor.py")
    else:
        add("supervisor_tool", "FAIL", "SUPERVISOR_TOOL_MISSING")

    api = root / "tools" / "ui1" / "run_ui_api.py"
    if api.is_file():
        add("api_entrypoint", "PASS", "run_ui_api.py")
    else:
        add("api_entrypoint", "FAIL", "API_ENTRYPOINT_MISSING")

    occupied = port_open if port_open is not None else (_port_open("127.0.0.1", 8766) if probe_network else False)
    if not occupied:
        add("api_port", "PASS", "127.0.0.1:8766 free")
    elif api_identity_sha and api_identity_sha == runtime:
        add("api_port", "PASS", "8766 bound by frozen runtime")
    elif api_identity_sha:
        add("api_port", "FAIL", "API_RUNTIME_MISMATCH")
    else:
        add("api_port", "FAIL", "API_PORT_OCCUPIED_UNIDENTIFIED")

    ownership_file = state_path / "campaign-supervision" / "ownership.json" if state_path else None
    own = _ownership(state_path)
    ownership_unreadable = bool(ownership_file and ownership_file.is_file() and own is None)
    arm_status = str(own.get("arm_status") or "") if own else "NOT_ARMED"
    if ownership_unreadable:
        add("foreign_campaign", "FAIL", "OWNERSHIP_UNREADABLE")
    elif own and str(own.get("campaign_id") or "") != campaign_id:
        add("foreign_campaign", "FAIL", "FOREIGN_CAMPAIGN_STATE")
    else:
        add("foreign_campaign", "PASS", arm_status)
    if ownership_unreadable:
        add("arm_state", "FAIL", "OWNERSHIP_UNREADABLE")
    elif arm_status in _TERMINAL:
        add("arm_state", "FAIL", "TERMINAL")
    elif arm_status == "ARMED_RUNNING":
        add("arm_state", "FAIL", "ALREADY_ARMED")
    elif arm_status == "NOT_ARMED":
        add("arm_state", "PASS", "NOT_ARMED")
    else:
        add("arm_state", "FAIL", "ARM_STATUS_UNKNOWN")

    beat = _heartbeat(state_path)
    if arm_status == "ARMED_RUNNING":
        if not beat or not beat.get("last_heartbeat_utc"):
            add("heartbeat", "FAIL", "HEARTBEAT_MISSING")
        else:
            add("heartbeat", "PASS", str(beat.get("last_heartbeat_utc")))
    else:
        add("heartbeat", "PASS", "NOT_APPLICABLE_UNTIL_ARM")

    if session is not None:
        if now.date() < session:
            add("session_window", "FAIL", "NOT_YET_IN_WINDOW")
        elif now.date() > session or (now.date() == session and now.time() >= RTH_OPEN):
            add("session_window", "FAIL", "MISSED_WINDOW")
        else:
            add("session_window", "PASS", f"before {RTH_OPEN.isoformat()} ET")

    return _finish(checks, now, document=document, campaign_id=campaign_id, session=session)


def _writable(path: Path, add: Callable[[str, str, str], None]) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".imp-go-nogo-write-probe"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError:
        add("state_directory", "FAIL", "STATE_DIR_UNWRITABLE")
        return
    add("state_directory", "PASS", "writable")


def _finish(
    checks: list[dict[str, Any]],
    now: datetime,
    *,
    document: Mapping[str, Any] | None,
    campaign_id: str | None,
    session: date | None,
) -> dict[str, Any]:
    blockers = list(dict.fromkeys(c["detail"] for c in checks if c["status"] == "FAIL"))
    if not blockers:
        disposition = "READY_FOR_PRE_RTH_ARM"
    elif blockers == ["NOT_YET_IN_WINDOW"]:
        disposition = "NOT_YET_IN_WINDOW"
    elif blockers == ["MISSED_WINDOW"]:
        disposition = "MISSED_WINDOW"
    elif blockers == ["ALREADY_ARMED"]:
        disposition = "ALREADY_ARMED"
    elif blockers == ["TERMINAL"]:
        disposition = "TERMINAL"
    else:
        disposition = "BLOCKED"
    go = disposition == "READY_FOR_PRE_RTH_ARM"
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_class": EVIDENCE_CLASS,
        "disposition": disposition,
        "go": go,
        "arm_allowed": go,
        "execution_authority": "BLOCKED",
        "allows_network_submit": False,
        "live_execution": "OFF",
        "as_of_et": now.isoformat(),
        "campaign_id": campaign_id,
        "observation_window_id": None if document is None else document.get("observation_window_id"),
        "session_date": session.isoformat() if session else None,
        "runtime_sha": None if document is None else document.get("runtime_sha"),
        "blockers": blockers,
        "checks": checks,
        "does_not_arm": True,
    }


def build_freeze_document(
    *,
    session: date,
    runtime_sha: str,
    runtime_tree_sha: str,
    source_main: str,
    prior_campaign_id: str,
    prior_runtime_sha: str,
    prior_classification: str,
) -> dict[str, Any]:
    campaign_id = campaign_id_for_session(session)
    stamp = session.strftime("%Y%m%d")
    document: dict[str, Any] = {
        "allows_network_submit": False,
        "arm_performed": False,
        "artifact_kind": "imp_rth_campaign_freeze",
        "calendar_authority": "market_platform_foundation.intelligence.forward_qualification.evidence01.continuity.is_trading_day",
        "campaign_id": campaign_id,
        "campaign_purpose": "Prospective US equity cash RTH news observation. Not empirical until armed inside the window.",
        "campaign_question": "Can provider receipts become canonical events, detections, opportunities, and operator decisions inside one immutable RTH window?",
        "campaign_slug": "FTEP-V1-002",
        "campaign_state": "FROZEN_NOT_ARMED",
        "empirically_proven": False,
        "evidence_class": "SOFTWARE_COORDINATION",
        "evidence_namespace": f"projects/integrated-market-platform/.local/rth-campaign-{stamp}",
        "rehearsal_namespace": f"projects/integrated-market-platform/.local/rth-rehearsal-{stamp}",
        "execution_authority": "BLOCKED",
        "ftep_empirical_active": False,
        "full30": "NOT_RUN",
        "item7_governed_corpus": "NOT_ESTABLISHED",
        "item9_calibrated": False,
        "item9_calibration_run": "FORBIDDEN",
        "item9_status": "PARTIAL_NOT_CALIBRATED",
        "live_execution": "OFF",
        "observation_window_id": f"{campaign_id}-A",
        "preparation_verdict": "FROZEN_NOT_ARMED",
        "provider_lane": "finviz_prospective_news",
        "provider_role": "prospective_news_ingress",
        "required_roles": ["supervisor", "poller", "api"],
        "rth_close_et": "16:00:00",
        "rth_open_et": "09:30:00",
        "latest_safe_arm_et": "09:30:00",
        "runtime_sha": runtime_sha,
        "runtime_tree_sha": runtime_tree_sha,
        "schema_version": FREEZE_SCHEMA,
        "prior_campaign_id": prior_campaign_id,
        "prior_campaign_classification": prior_classification,
        "prior_runtime_sha": prior_runtime_sha,
        "backfill": "FORBIDDEN",
        "historical_mutation": "FORBIDDEN",
        "session_date": session.isoformat(),
        "source_main_at_freeze": source_main,
        "timezone": "America/New_York",
        "target_evidence_class": "prospective_forward_test",
    }
    document["freeze_sha256"] = canonical_freeze_sha256(document)
    return document

"""Armed-campaign ownership, heartbeat, and outage honesty (RTH15-09).

Extends existing operator-diagnostics / service-liveness contracts. Does not
replace platform service liveness or market-data freshness. A durable
``ARMED_RUNNING`` arm token is never sufficient proof that the campaign is
alive.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

# Campaign-supervision progress tokens. Complementary to loopback service
# liveness (HEALTHY/UNREADY/UNAVAILABLE/NOT_APPLICABLE) and FTEP
# SESSION_UNAVAILABLE — not a parallel platform health taxonomy.
CAMPAIGN_PROGRESS_STATUSES = (
    "HEALTHY",
    "STARTING",
    "STALE",
    "PROCESS_DEAD",
    "APPLICATION_UNREADY",
    "SESSION_UNAVAILABLE",
    "NOT_APPLICABLE",
    "UNKNOWN",
)

ARM_STATUSES = (
    "ARMED_RUNNING",
    "CLEAN_SHUTDOWN",
    "RTH_CLOSE_SHUTDOWN",
    "NOT_ARMED",
)

OUTAGE_CLASSIFICATION = "NOT_OBSERVED"
OUTAGE_ROOT_CAUSE = "UNKNOWN"
EVIDENCE_CLASS = "SOFTWARE_CONTROLLED_EVIDENCE"
SCHEMA_VERSION = "campaign-supervision/1.0.0"

DEFAULT_POLL_CADENCE_SECONDS = 30.0
DEFAULT_HEARTBEAT_CADENCE_SECONDS = 15.0
DEFAULT_STALE_AFTER_SECONDS = 90.0
DEFAULT_STARTING_GRACE_SECONDS = 60.0

_SECRET_TOKEN_RE = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|authorization|bearer|credential)"
)
_SECRET_ASSIGN_RE = re.compile(
    r"(?i)(--?(?:password|passwd|secret|token|api[_-]?key|authorization)|"
    r"(?:PASSWORD|PASSWD|SECRET|TOKEN|API_KEY|AUTHORIZATION)\s*=)\S+"
)

OWNERSHIP_FILENAME = "ownership.json"
HEARTBEAT_FILENAME = "heartbeat.json"
OUTAGES_FILENAME = "outages.jsonl"
SUBDIR_NAME = "campaign-supervision"


@dataclass
class ProcessIdentity:
    role: str
    pid: int
    create_time_utc: str | None = None
    parent_pid: int | None = None
    command_fingerprint: str | None = None
    identity_tokens: list[str] = field(default_factory=list)


@dataclass
class CampaignOwnership:
    campaign_id: str
    runtime_sha: str
    supervisor_pid: int
    supervisor_identity: str
    child_processes: list[ProcessIdentity]
    arm_timestamp_utc: str
    observation_window_id: str
    expected_poll_cadence_seconds: float
    expected_next_cycle_utc: str | None
    state_directory: str
    arm_status: str = "ARMED_RUNNING"
    launch_command_fingerprint: str | None = None
    segment_id: str | None = None
    required_roles: list[str] = field(default_factory=lambda: ["supervisor", "poller", "api"])
    schema_version: str = SCHEMA_VERSION
    evidence_class: str = EVIDENCE_CLASS
    execution_authority: str = "BLOCKED"
    execution_mode: str = "NONE"
    allows_network_submit: bool = False
    live_submit_forbidden: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["child_processes"] = [asdict(child) for child in self.child_processes]
        return payload

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "CampaignOwnership":
        children_raw = raw.get("child_processes") if isinstance(raw.get("child_processes"), list) else []
        children: list[ProcessIdentity] = []
        for item in children_raw:
            if not isinstance(item, dict):
                continue
            children.append(
                ProcessIdentity(
                    role=str(item.get("role") or "unknown"),
                    pid=int(item.get("pid") or 0),
                    create_time_utc=(str(item["create_time_utc"]) if item.get("create_time_utc") else None),
                    parent_pid=(int(item["parent_pid"]) if item.get("parent_pid") is not None else None),
                    command_fingerprint=(
                        str(item["command_fingerprint"]) if item.get("command_fingerprint") else None
                    ),
                    identity_tokens=[str(t) for t in (item.get("identity_tokens") or [])],
                )
            )
        required = raw.get("required_roles")
        return cls(
            campaign_id=str(raw.get("campaign_id") or ""),
            runtime_sha=str(raw.get("runtime_sha") or ""),
            supervisor_pid=int(raw.get("supervisor_pid") or 0),
            supervisor_identity=str(raw.get("supervisor_identity") or "imp-campaign-supervisor"),
            child_processes=children,
            arm_timestamp_utc=str(raw.get("arm_timestamp_utc") or ""),
            observation_window_id=str(raw.get("observation_window_id") or ""),
            expected_poll_cadence_seconds=float(
                raw.get("expected_poll_cadence_seconds") or DEFAULT_POLL_CADENCE_SECONDS
            ),
            expected_next_cycle_utc=(
                str(raw["expected_next_cycle_utc"]) if raw.get("expected_next_cycle_utc") else None
            ),
            state_directory=str(raw.get("state_directory") or ""),
            arm_status=str(raw.get("arm_status") or "NOT_ARMED"),
            launch_command_fingerprint=(
                str(raw["launch_command_fingerprint"]) if raw.get("launch_command_fingerprint") else None
            ),
            segment_id=(str(raw["segment_id"]) if raw.get("segment_id") else None),
            required_roles=[str(r) for r in required] if isinstance(required, list) else ["supervisor", "poller", "api"],
            schema_version=str(raw.get("schema_version") or SCHEMA_VERSION),
            evidence_class=str(raw.get("evidence_class") or EVIDENCE_CLASS),
            execution_authority=str(raw.get("execution_authority") or "BLOCKED"),
            execution_mode=str(raw.get("execution_mode") or "NONE"),
            allows_network_submit=bool(raw.get("allows_network_submit", False)),
            live_submit_forbidden=bool(raw.get("live_submit_forbidden", True)),
        )


def campaign_supervision_dir(state_directory: str | Path) -> Path:
    return Path(state_directory) / SUBDIR_NAME


def ownership_path(state_directory: str | Path) -> Path:
    return campaign_supervision_dir(state_directory) / OWNERSHIP_FILENAME


def heartbeat_path(state_directory: str | Path) -> Path:
    return campaign_supervision_dir(state_directory) / HEARTBEAT_FILENAME


def outages_path(state_directory: str | Path) -> Path:
    return campaign_supervision_dir(state_directory) / OUTAGES_FILENAME


def redact_command_token(token: str) -> str:
    text = str(token)
    if _SECRET_TOKEN_RE.search(text) and ("=" in text or len(text) > 24):
        return "<redacted>"
    redacted = _SECRET_ASSIGN_RE.sub(r"\1<redacted>", text)
    return redacted


def safe_command_fingerprint(argv: Sequence[str]) -> str:
    safe = [redact_command_token(part) for part in argv]
    digest = hashlib.sha256("\0".join(safe).encode("utf-8")).hexdigest()
    return f"sha256:{digest[:32]}"


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    last_error: OSError | None = None
    for attempt in range(8):
        fd, temporary_name = tempfile.mkstemp(
            prefix=".campaign-supervision.", suffix=".tmp", dir=str(path.parent)
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(dict(payload), handle, sort_keys=True, separators=(",", ":"))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
            return
        except OSError as exc:
            last_error = exc
            temporary.unlink(missing_ok=True)
            # Windows: concurrent replace against a reader/writer can deny access.
            import time as _time

            _time.sleep(0.02 * (attempt + 1))
    if last_error is not None:
        raise last_error
    raise OSError(f"unable to atomically write {path}")


def write_ownership(ownership: CampaignOwnership) -> Path:
    path = ownership_path(ownership.state_directory)
    _atomic_write_json(path, ownership.to_dict())
    return path


def read_ownership(state_directory: str | Path) -> CampaignOwnership | None:
    path = ownership_path(state_directory)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return CampaignOwnership.from_dict(payload)


def write_heartbeat(state_directory: str | Path, heartbeat: Mapping[str, Any]) -> Path:
    path = heartbeat_path(state_directory)
    body = dict(heartbeat)
    body.setdefault("schema_version", SCHEMA_VERSION)
    body.setdefault("evidence_class", EVIDENCE_CLASS)
    body.setdefault("secrets_included", False)
    _atomic_write_json(path, body)
    return path


def read_heartbeat(state_directory: str | Path) -> dict[str, Any] | None:
    path = heartbeat_path(state_directory)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def append_outage_record(state_directory: str | Path, record: Mapping[str, Any]) -> Path:
    path = outages_path(state_directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(record)
    body.setdefault("classification", OUTAGE_CLASSIFICATION)
    body.setdefault("root_cause", OUTAGE_ROOT_CAUSE)
    body.setdefault("synthetic_poll_generated", False)
    body.setdefault("backfill_applied", False)
    body.setdefault("evidence_class", EVIDENCE_CLASS)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(body, sort_keys=True, separators=(",", ":")))
        handle.write("\n")
    return path


def read_outage_records(state_directory: str | Path) -> list[dict[str, Any]]:
    path = outages_path(state_directory)
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def process_alive(pid: int) -> bool:
    """Best-effort liveness probe without ``ctypes`` in governed src.

    On Windows, ``os.kill(pid, 0)`` is **not** a reliable existence probe
    (commonly raises ``WinError 87`` even for live processes). This fallback
    uses ``tasklist``. Prefer injecting
    ``tools.platform.service_health.process_alive`` from the tools layer.
    """

    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import subprocess

            result = subprocess.run(
                ["tasklist.exe", "/FI", f"PID eq {int(pid)}", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        out = result.stdout or ""
        if "No tasks are running" in out or out.strip().startswith("INFO:"):
            return False
        return str(int(pid)) in out
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    except SystemError:
        return False
    return True


def _parse_utc_seconds(value: str | None) -> float | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Accept Z and +00:00; keep stdlib-only.
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        from datetime import datetime

        return datetime.fromisoformat(text).timestamp()
    except ValueError:
        return None


def evaluate_campaign_progress(
    *,
    ownership: CampaignOwnership | None,
    heartbeat: Mapping[str, Any] | None,
    now_utc_epoch: float,
    process_alive_fn=process_alive,
    ui_required: bool | None = None,
) -> dict[str, Any]:
    """Classify campaign progress independent of market-data freshness."""

    if ownership is None:
        return {
            "status": "NOT_APPLICABLE",
            "healthy": False,
            "reason": "NO_CAMPAIGN_OWNERSHIP",
            "arm_status": "NOT_ARMED",
            "service_liveness_separate_from_data_freshness": True,
        }

    arm_status = str(ownership.arm_status or "NOT_ARMED")
    if arm_status in {"CLEAN_SHUTDOWN", "RTH_CLOSE_SHUTDOWN"}:
        return {
            "status": "NOT_APPLICABLE",
            "healthy": False,
            "reason": arm_status,
            "arm_status": arm_status,
            "outage": False,
            "campaign_id": ownership.campaign_id,
            "runtime_sha": ownership.runtime_sha,
            "service_liveness_separate_from_data_freshness": True,
        }

    if not ownership.state_directory:
        return {
            "status": "SESSION_UNAVAILABLE",
            "healthy": False,
            "reason": "STATE_DIRECTORY_MISSING",
            "arm_status": arm_status,
            "campaign_id": ownership.campaign_id,
            "runtime_sha": ownership.runtime_sha,
            "service_liveness_separate_from_data_freshness": True,
        }

    roles_required = list(ownership.required_roles)
    if ui_required is True and "ui" not in roles_required:
        roles_required = [*roles_required, "ui"]

    supervisor_alive = process_alive_fn(int(ownership.supervisor_pid))
    child_states: list[dict[str, Any]] = []
    dead_roles: list[str] = []
    registered_roles = {child.role for child in ownership.child_processes}
    for child in ownership.child_processes:
        alive = process_alive_fn(int(child.pid))
        child_states.append({"role": child.role, "pid": child.pid, "alive": alive})
        if child.role in roles_required and not alive:
            dead_roles.append(child.role)
    if "supervisor" in roles_required and not supervisor_alive:
        dead_roles.append("supervisor")
    # Required observation roles must be registered as live processes (except
    # supervisor, which is tracked via ownership.supervisor_pid). Missing
    # registration is PROCESS_DEAD — do not treat an absent poller/api as healthy.
    for role in roles_required:
        if role == "supervisor":
            continue
        if role == "ui" and ui_required is not True and "ui" not in ownership.required_roles:
            continue
        if role not in registered_roles:
            dead_roles.append(role)
            child_states.append({"role": role, "pid": None, "alive": False, "registered": False})

    hb = dict(heartbeat or {})
    last_heartbeat_utc = hb.get("last_heartbeat_utc")
    last_successful_poll_utc = hb.get("last_successful_poll_utc")
    expected_next_heartbeat_utc = hb.get("expected_next_heartbeat_utc")
    expected_next_poll_utc = hb.get("expected_next_poll_utc") or ownership.expected_next_cycle_utc
    stale_after = float(hb.get("stale_after_seconds") or DEFAULT_STALE_AFTER_SECONDS)
    starting_grace = float(hb.get("starting_grace_seconds") or DEFAULT_STARTING_GRACE_SECONDS)
    application_ready = hb.get("application_ready")
    port_bound_without_progress = bool(hb.get("port_bound_without_progress"))

    last_hb_ts = _parse_utc_seconds(str(last_heartbeat_utc) if last_heartbeat_utc else None)
    last_poll_ts = _parse_utc_seconds(str(last_successful_poll_utc) if last_successful_poll_utc else None)
    expected_poll_ts = _parse_utc_seconds(str(expected_next_poll_utc) if expected_next_poll_utc else None)
    arm_ts = _parse_utc_seconds(ownership.arm_timestamp_utc)

    base = {
        "arm_status": arm_status,
        "campaign_id": ownership.campaign_id,
        "runtime_sha": ownership.runtime_sha,
        "supervisor_alive": supervisor_alive,
        "child_states": child_states,
        "last_heartbeat_utc": last_heartbeat_utc,
        "last_successful_poll_utc": last_successful_poll_utc,
        "expected_next_heartbeat_utc": expected_next_heartbeat_utc,
        "expected_next_poll_utc": expected_next_poll_utc,
        "stale_after_seconds": stale_after,
        "service_liveness_separate_from_data_freshness": True,
        "data_freshness_not_implied": True,
    }

    # Fail closed: ARMED_RUNNING alone is never HEALTHY.
    if dead_roles:
        return {
            **base,
            "status": "PROCESS_DEAD",
            "healthy": False,
            "reason": "REQUIRED_PROCESS_DEAD",
            "dead_roles": sorted(set(dead_roles)),
            "outage": arm_status == "ARMED_RUNNING",
        }

    if port_bound_without_progress or application_ready is False:
        return {
            **base,
            "status": "APPLICATION_UNREADY",
            "healthy": False,
            "reason": "PORT_OR_PROCESS_WITHOUT_PROGRESS",
            "outage": arm_status == "ARMED_RUNNING",
        }

    if last_hb_ts is None and last_poll_ts is None:
        if arm_ts is not None and (now_utc_epoch - arm_ts) <= starting_grace:
            return {
                **base,
                "status": "STARTING",
                "healthy": False,
                "reason": "AWAITING_FIRST_HEARTBEAT",
                "outage": False,
            }
        return {
            **base,
            "status": "STALE" if arm_status == "ARMED_RUNNING" else "UNKNOWN",
            "healthy": False,
            "reason": "NO_HEARTBEAT_OR_PROGRESS",
            "outage": arm_status == "ARMED_RUNNING",
        }

    progress_ts = max(t for t in (last_hb_ts, last_poll_ts) if t is not None)
    age = now_utc_epoch - progress_ts
    if age >= stale_after:
        return {
            **base,
            "status": "STALE",
            "healthy": False,
            "reason": "HEARTBEAT_OR_PROGRESS_STALE",
            "age_seconds": age,
            "outage": arm_status == "ARMED_RUNNING",
        }

    if expected_poll_ts is not None and now_utc_epoch > expected_poll_ts + stale_after:
        return {
            **base,
            "status": "STALE",
            "healthy": False,
            "reason": "EXPECTED_CYCLE_ELAPSED_WITHOUT_PROGRESS",
            "outage": arm_status == "ARMED_RUNNING",
        }

    if arm_status != "ARMED_RUNNING":
        return {
            **base,
            "status": "UNKNOWN",
            "healthy": False,
            "reason": f"UNEXPECTED_ARM_STATUS:{arm_status}",
            "outage": False,
        }

    return {
        **base,
        "status": "HEALTHY",
        "healthy": True,
        "reason": None,
        "outage": False,
        "age_seconds": age,
    }


def build_outage_interval(
    *,
    ownership: CampaignOwnership,
    progress: Mapping[str, Any],
    detected_at_utc: str,
    interval_start_utc: str | None,
    interval_end_utc: str | None = None,
) -> dict[str, Any]:
    """Additive outage record. Missed evidence remains NOT_OBSERVED."""

    return {
        "campaign_id": ownership.campaign_id,
        "segment_id": ownership.segment_id,
        "runtime_sha": ownership.runtime_sha,
        "arm_status": ownership.arm_status,
        "arm_timestamp_utc": ownership.arm_timestamp_utc,
        "detected_at_utc": detected_at_utc,
        "interval_start_utc": interval_start_utc or ownership.arm_timestamp_utc,
        "interval_end_utc": interval_end_utc,
        "expected_next_cycle_utc": progress.get("expected_next_poll_utc") or ownership.expected_next_cycle_utc,
        "process_state": {
            "status": progress.get("status"),
            "dead_roles": progress.get("dead_roles"),
            "supervisor_alive": progress.get("supervisor_alive"),
            "child_states": progress.get("child_states"),
        },
        "last_successful_observation_utc": progress.get("last_successful_poll_utc"),
        "classification": OUTAGE_CLASSIFICATION,
        "root_cause": OUTAGE_ROOT_CAUSE,
        "synthetic_poll_generated": False,
        "backfill_applied": False,
        "new_segment_created": False,
        "evidence_class": EVIDENCE_CLASS,
    }


def preserve_arm_for_recovery(
    ownership: CampaignOwnership,
    *,
    supervisor_pid: int,
    child_processes: Sequence[ProcessIdentity],
    expected_next_cycle_utc: str | None = None,
) -> CampaignOwnership:
    """Update process identity after deliberate recovery without resetting the arm."""

    return CampaignOwnership(
        campaign_id=ownership.campaign_id,
        runtime_sha=ownership.runtime_sha,
        supervisor_pid=int(supervisor_pid),
        supervisor_identity=ownership.supervisor_identity,
        child_processes=list(child_processes),
        arm_timestamp_utc=ownership.arm_timestamp_utc,
        observation_window_id=ownership.observation_window_id,
        expected_poll_cadence_seconds=ownership.expected_poll_cadence_seconds,
        expected_next_cycle_utc=expected_next_cycle_utc or ownership.expected_next_cycle_utc,
        state_directory=ownership.state_directory,
        arm_status="ARMED_RUNNING",
        launch_command_fingerprint=ownership.launch_command_fingerprint,
        segment_id=ownership.segment_id,
        required_roles=list(ownership.required_roles),
        schema_version=ownership.schema_version,
        evidence_class=ownership.evidence_class,
        execution_authority=ownership.execution_authority,
        execution_mode=ownership.execution_mode,
        allows_network_submit=False,
        live_submit_forbidden=True,
    )


def load_campaign_supervision_view(
    state_directory: str | Path | None,
    *,
    now_utc_epoch: float | None = None,
    process_alive_fn=None,
) -> dict[str, Any]:
    """Operator-facing composition for diagnostics."""

    import time
    from datetime import datetime, timezone

    alive_fn = process_alive_fn or process_alive

    if not state_directory:
        return {
            "status": "NOT_APPLICABLE",
            "healthy": False,
            "reason": "NO_STATE_DIRECTORY",
            "ownership": None,
            "heartbeat": None,
            "outages": [],
            "service_liveness_separate_from_data_freshness": True,
        }

    ownership = read_ownership(state_directory)
    heartbeat = read_heartbeat(state_directory)
    outages = read_outage_records(state_directory)
    now = float(now_utc_epoch if now_utc_epoch is not None else time.time())
    progress = evaluate_campaign_progress(
        ownership=ownership,
        heartbeat=heartbeat,
        now_utc_epoch=now,
        process_alive_fn=alive_fn,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_class": EVIDENCE_CLASS,
        "as_of_utc": datetime.fromtimestamp(now, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
        "ownership": ownership.to_dict() if ownership else None,
        "heartbeat": heartbeat,
        "progress": progress,
        "status": progress.get("status"),
        "healthy": bool(progress.get("healthy")),
        "outages": outages,
        "service_liveness_separate_from_data_freshness": True,
        "does_not_imply_data_freshness": True,
        "does_not_imply_opportunity_quality": True,
        "execution_authority": "BLOCKED",
    }


__all__ = [
    "ARM_STATUSES",
    "CAMPAIGN_PROGRESS_STATUSES",
    "CampaignOwnership",
    "DEFAULT_HEARTBEAT_CADENCE_SECONDS",
    "DEFAULT_POLL_CADENCE_SECONDS",
    "DEFAULT_STALE_AFTER_SECONDS",
    "EVIDENCE_CLASS",
    "OUTAGE_CLASSIFICATION",
    "OUTAGE_ROOT_CAUSE",
    "ProcessIdentity",
    "SCHEMA_VERSION",
    "append_outage_record",
    "build_outage_interval",
    "campaign_supervision_dir",
    "evaluate_campaign_progress",
    "heartbeat_path",
    "load_campaign_supervision_view",
    "ownership_path",
    "preserve_arm_for_recovery",
    "process_alive",
    "read_heartbeat",
    "read_outage_records",
    "read_ownership",
    "redact_command_token",
    "safe_command_fingerprint",
    "write_heartbeat",
    "write_ownership",
]

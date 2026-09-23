"""Campaign observation readiness / start gate (fail-visible).

ONE backend read model composed from existing campaign-supervision,
platform service liveness, provider readiness, and ingress signals.

Does not grant broker execution authority. Does not start Item 9
calibration, Full30, or live submit. Arming remains the existing
``campaign_supervisor.py arm`` path (observation-safe; execution BLOCKED).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, time
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from .campaign_supervision import (
    ARM_STATUSES,
    CAMPAIGN_PROGRESS_STATUSES,
    EVIDENCE_CLASS,
    campaign_supervision_dir,
    load_campaign_supervision_view,
)
from .service_liveness import classify_platform_services_liveness

ET = ZoneInfo("America/New_York")
SCHEMA_VERSION = "campaign-observation-readiness/1.0.0"

# Overall gate phases. Prefer existing ARM / progress tokens in field values;
# these labels only compose the start-gate summary.
READINESS_PHASES = (
    "READY_TO_ARM",
    "ARMED_WAITING_WINDOW",
    "ACTIVE_PROGRESSING",
    "ACTIVE_STALLED",
    "NOT_ARMED",
    "MISSED_WINDOW",
    "BLOCKED_PROVIDER",
    "BLOCKED_RUNTIME",
    "BLOCKED_STATE_DIR",
    "BLOCKED_AUTHORITY",
)

INTENT_FILENAME = "observation-intent.json"
DEFAULT_RTH_SOON_MINUTES = 60
RTH_OPEN = time(9, 30)
RTH_CLOSE = time(16, 0)

BLOCKING_ALERT_NOT_ARMED = "CAMPAIGN_NOT_ARMED_BEFORE_RTH"

ARM_OBSERVATION_CLI = (
    "python tools/platform/campaign_supervisor.py arm "
    "--state-dir $env:IMP_STATE_DIR "
    "--campaign-id <campaign_id> "
    "--observation-window-id <window_id>"
)


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes)) else []


def _parse_et_date(value: str | None) -> datetime.date | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _service_status(platform_liveness: Mapping[str, Any], service_name: str) -> str:
    for row in _as_list(platform_liveness.get("services")):
        if not isinstance(row, Mapping):
            continue
        if str(row.get("service") or "") == service_name:
            return str(row.get("status") or "UNKNOWN")
    return "NOT_APPLICABLE"


def _service_ready(status: str) -> bool:
    return status == "HEALTHY"


def load_observation_intent(
    state_directory: str | Path | None,
    *,
    env: Mapping[str, str] | None = None,
    explicit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load optional observation intent (freeze / intended-day declaration).

    Sources (later override earlier): empty → env → intent file → explicit.
    Never invents a campaign when none is declared.
    """

    intent: dict[str, Any] = {
        "campaign_id": None,
        "intended_date_et": None,
        "frozen": None,
        "runtime_sha": None,
        "observation_window_id": None,
        "owner": None,
        "source": "NONE",
    }
    mapping = env if env is not None else os.environ

    env_campaign = str(mapping.get("IMP_OBS_CAMPAIGN_ID") or "").strip()
    if env_campaign:
        intent.update(
            {
                "campaign_id": env_campaign,
                "intended_date_et": str(mapping.get("IMP_OBS_INTENDED_DATE_ET") or "").strip() or None,
                "frozen": _parse_frozen_flag(mapping.get("IMP_OBS_FROZEN")),
                "runtime_sha": str(mapping.get("IMP_OBS_RUNTIME_SHA") or "").strip() or None,
                "observation_window_id": str(mapping.get("IMP_OBS_WINDOW_ID") or "").strip() or None,
                "owner": str(mapping.get("IMP_OBS_OWNER") or "").strip() or None,
                "source": "ENV",
            }
        )

    if state_directory:
        path = campaign_supervision_dir(state_directory) / INTENT_FILENAME
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                payload = None
            if isinstance(payload, dict):
                intent.update(
                    {
                        "campaign_id": str(payload.get("campaign_id") or intent["campaign_id"] or "")
                        or None,
                        "intended_date_et": str(
                            payload.get("intended_date_et") or intent["intended_date_et"] or ""
                        )
                        or None,
                        "frozen": (
                            _parse_frozen_flag(payload.get("frozen"))
                            if payload.get("frozen") is not None
                            else intent["frozen"]
                        ),
                        "runtime_sha": str(payload.get("runtime_sha") or intent["runtime_sha"] or "")
                        or None,
                        "observation_window_id": str(
                            payload.get("observation_window_id")
                            or intent["observation_window_id"]
                            or ""
                        )
                        or None,
                        "owner": str(payload.get("owner") or intent["owner"] or "") or None,
                        "source": "INTENT_FILE",
                    }
                )

    if explicit:
        for key in (
            "campaign_id",
            "intended_date_et",
            "runtime_sha",
            "observation_window_id",
            "owner",
        ):
            if explicit.get(key) is not None and str(explicit.get(key)).strip():
                intent[key] = str(explicit[key]).strip()
        if explicit.get("frozen") is not None:
            intent["frozen"] = _parse_frozen_flag(explicit.get("frozen"))
        if any(explicit.get(k) is not None for k in ("campaign_id", "intended_date_et", "frozen")):
            intent["source"] = "EXPLICIT"

    return intent


def _parse_frozen_flag(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "frozen", "frozen_not_armed"}:
        return True
    if text in {"0", "false", "no", "unfrozen"}:
        return False
    return None


def _rth_timing(now_et: datetime) -> dict[str, Any]:
    local = now_et.astimezone(ET) if now_et.tzinfo else now_et.replace(tzinfo=ET)
    weekday = local.weekday()
    open_dt = datetime.combine(local.date(), RTH_OPEN, tzinfo=ET)
    close_dt = datetime.combine(local.date(), RTH_CLOSE, tzinfo=ET)
    if weekday >= 5:
        return {
            "session_label": "CLOSED",
            "rth_open": False,
            "rth_closed_for_day": True,
            "minutes_until_rth_open": None,
            "minutes_since_rth_open": None,
            "rth_starts_soon": False,
            "trading_day": False,
        }

    minutes_until: float | None
    minutes_since: float | None
    if local < open_dt:
        minutes_until = (open_dt - local).total_seconds() / 60.0
        minutes_since = None
        rth_open = False
        rth_closed = False
        session = "PREMARKET" if local.time() >= time(4, 0) else "CLOSED"
    elif local < close_dt:
        minutes_until = 0.0
        minutes_since = (local - open_dt).total_seconds() / 60.0
        rth_open = True
        rth_closed = False
        session = "REGULAR"
    else:
        minutes_until = None
        minutes_since = (local - open_dt).total_seconds() / 60.0
        rth_open = False
        rth_closed = True
        session = "AFTER_HOURS"

    soon = bool(
        minutes_until is not None and 0 <= minutes_until <= DEFAULT_RTH_SOON_MINUTES
    ) or rth_open

    return {
        "session_label": session,
        "rth_open": rth_open,
        "rth_closed_for_day": rth_closed,
        "minutes_until_rth_open": minutes_until,
        "minutes_since_rth_open": minutes_since,
        "rth_starts_soon": soon,
        "trading_day": True,
        "rth_open_et": open_dt.isoformat(),
        "rth_close_et": close_dt.isoformat(),
    }


def build_campaign_observation_readiness(
    *,
    campaign_supervision: Mapping[str, Any] | None = None,
    lifecycle: Mapping[str, Any] | None = None,
    provider_readiness: Mapping[str, Any] | None = None,
    provider_health: Mapping[str, Any] | None = None,
    ingress_enabled: bool | None = None,
    item9_collector: Mapping[str, Any] | None = None,
    intent: Mapping[str, Any] | None = None,
    now_et: datetime | None = None,
    state_directory: str | Path | None = None,
    rth_soon_minutes: float = DEFAULT_RTH_SOON_MINUTES,
) -> dict[str, Any]:
    """Derive the observation start-gate read model from existing signals."""

    now = now_et or datetime.now(ET)
    if now.tzinfo is None:
        now = now.replace(tzinfo=ET)
    else:
        now = now.astimezone(ET)

    supervision = _as_dict(campaign_supervision)
    ownership = _as_dict(supervision.get("ownership"))
    progress = _as_dict(supervision.get("progress"))
    heartbeat = _as_dict(supervision.get("heartbeat"))
    intent_view = dict(intent or {})

    arm_status = str(
        ownership.get("arm_status")
        or progress.get("arm_status")
        or "NOT_ARMED"
    )
    if arm_status not in ARM_STATUSES:
        # Unknown arm token stays explicit; treat as not armed for the gate.
        arm_effective = "NOT_ARMED" if arm_status in {"", "NONE", "UNKNOWN"} else arm_status
    else:
        arm_effective = arm_status

    armed = arm_effective == "ARMED_RUNNING"
    campaign_id = (
        str(ownership.get("campaign_id") or intent_view.get("campaign_id") or "").strip() or None
    )
    runtime_sha = (
        str(ownership.get("runtime_sha") or intent_view.get("runtime_sha") or "").strip() or None
    )
    owner = (
        str(ownership.get("supervisor_identity") or intent_view.get("owner") or "").strip() or None
    )
    observation_window = (
        str(
            ownership.get("observation_window_id")
            or intent_view.get("observation_window_id")
            or ""
        ).strip()
        or None
    )
    frozen_flag = intent_view.get("frozen")
    if frozen_flag is None and ownership:
        # Ownership present after arm does not imply unfrozen; freeze is intent-only.
        frozen_flag = None
    frozen_display: bool | str
    if frozen_flag is True:
        frozen_display = True
    elif frozen_flag is False:
        frozen_display = False
    else:
        frozen_display = "UNKNOWN"

    intended_date = _parse_et_date(
        str(intent_view.get("intended_date_et") or "") or None
    )
    intended_today = bool(intended_date and intended_date == now.date() and campaign_id)

    timing = _rth_timing(now)
    # Allow caller override of "soon" window without changing session math.
    if timing.get("minutes_until_rth_open") is not None:
        timing["rth_starts_soon"] = bool(
            0 <= float(timing["minutes_until_rth_open"]) <= float(rth_soon_minutes)
        ) or bool(timing.get("rth_open"))

    services_raw = None
    if lifecycle is not None:
        raw = lifecycle.get("services")
        if isinstance(raw, list):
            services_raw = raw
    platform = classify_platform_services_liveness(services_raw)
    api_status = _service_status(platform, "api")
    ui_status = _service_status(platform, "ui")
    api_ready = _service_ready(api_status)
    ui_ready = _service_ready(ui_status)

    readiness = _as_dict(provider_readiness)
    health = _as_dict(provider_health)
    provider_status = str(
        readiness.get("status")
        or health.get("reason")
        or ("AVAILABLE" if health.get("available") else None)
        or "UNKNOWN"
    )

    if ingress_enabled is None:
        ingress_value: bool | str = "UNKNOWN"
    else:
        ingress_value = bool(ingress_enabled)

    item9 = _as_dict(item9_collector)
    item9_status = str(
        item9.get("process_probe_status")
        or item9.get("disposition")
        or item9.get("status")
        or "NOT_OBSERVED"
    )

    progress_status = str(
        progress.get("status") or supervision.get("status") or "NOT_APPLICABLE"
    )
    if progress_status not in CAMPAIGN_PROGRESS_STATUSES and progress_status:
        pass  # keep raw existing token

    heartbeat_status = progress_status
    if not heartbeat and not armed:
        heartbeat_status = "NOT_APPLICABLE"
    elif not heartbeat and armed:
        heartbeat_status = str(progress.get("status") or "UNKNOWN")

    if ownership.get("state_directory"):
        # Snapshot path redacts absolute dirs; keep ownership value when already public.
        state_dir = str(ownership.get("state_directory"))
    elif state_directory:
        state_dir = "<IMP_STATE_DIR>/campaign-supervision"
    else:
        state_dir = None

    blockers: list[str] = []
    if intended_today or campaign_id:
        if not armed and arm_effective == "NOT_ARMED":
            blockers.append("NOT_ARMED")
        if progress_status == "PROCESS_DEAD":
            blockers.append("PROCESS_DEAD")
            if progress.get("reason"):
                blockers.append(str(progress["reason"]))
        if progress_status == "STALE":
            blockers.append("STALE")
        if progress_status == "APPLICATION_UNREADY":
            blockers.append("APPLICATION_UNREADY")
        if progress.get("reason") == "NO_HEARTBEAT_OR_PROGRESS":
            blockers.append("NO_HEARTBEAT_OR_PROGRESS")
        if not api_ready and api_status not in {"NOT_APPLICABLE"}:
            blockers.append(f"API_{api_status}")
        if not ui_ready and ui_status not in {"NOT_APPLICABLE"}:
            blockers.append(f"UI_{ui_status}")
        if ingress_value is False:
            blockers.append("INGRESS_NOT_ENABLED")
        if provider_status in {"ACTION_REQUIRED", "NOT_READY", "ERROR"}:
            blockers.append(f"PROVIDER_{provider_status}")
        if str(ownership.get("state_directory") or "") == "" and armed:
            blockers.append("STATE_DIRECTORY_MISSING")
        expected_runtime = str(intent_view.get("runtime_sha") or "").strip()
        if expected_runtime and runtime_sha and expected_runtime != runtime_sha:
            blockers.append("RUNTIME_SHA_MISMATCH")
        exec_auth = str(ownership.get("execution_authority") or "BLOCKED")
        if exec_auth not in {"BLOCKED", ""}:
            blockers.append("EXECUTION_AUTHORITY_NOT_BLOCKED")
        if ownership.get("allows_network_submit") is True:
            blockers.append("NETWORK_SUBMIT_NOT_FORBIDDEN")

    # Deduplicate while preserving order.
    blockers = list(dict.fromkeys(blockers))

    blocking_alerts: list[dict[str, Any]] = []
    if (
        intended_today
        and not armed
        and arm_effective == "NOT_ARMED"
        and bool(timing.get("rth_starts_soon") or timing.get("rth_open"))
        and not bool(timing.get("rth_closed_for_day"))
    ):
        blocking_alerts.append(
            {
                "code": BLOCKING_ALERT_NOT_ARMED,
                "severity": "ACTION_REQUIRED",
                "message": (
                    f"RTH starts soon (or is open) and campaign {campaign_id} is NOT_ARMED."
                ),
                "campaign_id": campaign_id,
                "arm_status": arm_effective,
                "minutes_until_rth_open": timing.get("minutes_until_rth_open"),
            }
        )

    phase = _derive_phase(
        armed=armed,
        arm_status=arm_effective,
        progress_status=progress_status,
        intended_today=intended_today,
        timing=timing,
        blockers=blockers,
        provider_status=provider_status,
        runtime_mismatch="RUNTIME_SHA_MISMATCH" in blockers,
        state_dir_blocked="STATE_DIRECTORY_MISSING" in blockers,
        authority_blocked=(
            "EXECUTION_AUTHORITY_NOT_BLOCKED" in blockers
            or "NETWORK_SUBMIT_NOT_FORBIDDEN" in blockers
        ),
    )

    arm_action = {
        "label": "ARM OBSERVATION",
        "never_label": "GO LIVE",
        "wires_existing_cli_arm": True,
        "grants_execution_authority": False,
        "execution_authority_after_arm": "BLOCKED",
        "ui_mutation_wired": False,
        "ui_mutation_reason": (
            "Observation arm is CLI-owned (campaign_supervisor.py arm). "
            "UI does not POST arm to avoid a parallel arm path or accidental "
            "mutation of an active campaign state directory."
        ),
        "cli_command": ARM_OBSERVATION_CLI,
        "available": (not armed) and phase in {"READY_TO_ARM", "NOT_ARMED", "MISSED_WINDOW"}
        and "EXECUTION_AUTHORITY_NOT_BLOCKED" not in blockers,
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "evidence_class": EVIDENCE_CLASS,
        "as_of_et": now.isoformat(),
        "phase": phase,
        "campaign_id": campaign_id,
        "runtime_sha": runtime_sha,
        "frozen": frozen_display,
        "armed": armed,
        "arm_status": arm_effective,
        "owner": owner,
        "heartbeat": heartbeat_status,
        "heartbeat_detail": {
            "status": heartbeat_status,
            "last_heartbeat_utc": heartbeat.get("last_heartbeat_utc") or progress.get("last_heartbeat_utc"),
            "reason": progress.get("reason"),
        },
        "state_dir": state_dir or None,
        "provider_status": provider_status,
        "ingress_enabled": ingress_value,
        "api_ready": api_ready,
        "api_status": api_status,
        "ui_ready": ui_ready,
        "ui_status": ui_status,
        "item9_collector_status": item9_status,
        "item9_display_only": True,
        "does_not_start_item9": True,
        "execution_authority": "BLOCKED",
        "execution_mode": "NONE",
        "allows_network_submit": False,
        "live_submit_forbidden": True,
        "observation_window": observation_window,
        "observation_timing": timing,
        "intended_today": intended_today,
        "intent": {
            "campaign_id": intent_view.get("campaign_id"),
            "intended_date_et": intent_view.get("intended_date_et"),
            "frozen": frozen_flag,
            "runtime_sha": intent_view.get("runtime_sha"),
            "observation_window_id": intent_view.get("observation_window_id"),
            "source": intent_view.get("source") or "NONE",
        },
        "blockers": blockers,
        "blocking_alerts": blocking_alerts,
        "has_blocking_alert": bool(blocking_alerts),
        "arm_observation": arm_action,
        "campaign_supervision_status": progress_status,
        "reused_statuses": {
            "arm_statuses": list(ARM_STATUSES),
            "campaign_progress_statuses": list(CAMPAIGN_PROGRESS_STATUSES),
            "platform_service_liveness": ["HEALTHY", "UNREADY", "UNAVAILABLE", "NOT_APPLICABLE"],
        },
        "does_not_imply_data_freshness": True,
        "does_not_imply_opportunity_quality": True,
    }


def _derive_phase(
    *,
    armed: bool,
    arm_status: str,
    progress_status: str,
    intended_today: bool,
    timing: Mapping[str, Any],
    blockers: Sequence[str],
    provider_status: str,
    runtime_mismatch: bool,
    state_dir_blocked: bool,
    authority_blocked: bool,
) -> str:
    if authority_blocked:
        return "BLOCKED_AUTHORITY"
    if state_dir_blocked:
        return "BLOCKED_STATE_DIR"
    if runtime_mismatch:
        return "BLOCKED_RUNTIME"
    if provider_status in {"ACTION_REQUIRED", "NOT_READY"} and "PROVIDER_" in ",".join(blockers):
        return "BLOCKED_PROVIDER"

    if armed:
        if progress_status == "HEALTHY":
            return "ACTIVE_PROGRESSING"
        if progress_status in {"STALE", "PROCESS_DEAD", "APPLICATION_UNREADY", "SESSION_UNAVAILABLE"}:
            return "ACTIVE_STALLED"
        if progress_status in {"STARTING", "UNKNOWN", "NOT_APPLICABLE"}:
            return "ARMED_WAITING_WINDOW"
        return "ARMED_WAITING_WINDOW"

    if intended_today and bool(timing.get("rth_closed_for_day")) and arm_status == "NOT_ARMED":
        return "MISSED_WINDOW"

    if arm_status == "NOT_ARMED":
        hard = {
            b
            for b in blockers
            if b
            not in {
                "NOT_ARMED",
                "INGRESS_NOT_ENABLED",
                "API_UNREADY",
                "API_UNAVAILABLE",
                "UI_UNREADY",
                "UI_UNAVAILABLE",
            }
            and not b.startswith("API_")
            and not b.startswith("UI_")
            and not b.startswith("PROVIDER_")
        }
        if not hard and intended_today:
            return "READY_TO_ARM"
        return "NOT_ARMED"

    if arm_status in {"CLEAN_SHUTDOWN", "RTH_CLOSE_SHUTDOWN"}:
        return "NOT_ARMED"
    return "NOT_ARMED"


def compose_campaign_observation_readiness_for_state(
    state_directory: str | Path | None,
    *,
    lifecycle: Mapping[str, Any] | None = None,
    provider_readiness: Mapping[str, Any] | None = None,
    provider_health: Mapping[str, Any] | None = None,
    ingress_enabled: bool | None = None,
    item9_collector: Mapping[str, Any] | None = None,
    intent_explicit: Mapping[str, Any] | None = None,
    now_et: datetime | None = None,
    now_utc_epoch: float | None = None,
    process_alive_fn=None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Load supervision + intent and build the readiness contract."""

    supervision = load_campaign_supervision_view(
        state_directory,
        now_utc_epoch=now_utc_epoch,
        process_alive_fn=process_alive_fn,
    )
    intent = load_observation_intent(
        state_directory,
        env=env,
        explicit=intent_explicit,
    )
    return build_campaign_observation_readiness(
        campaign_supervision=supervision,
        lifecycle=lifecycle,
        provider_readiness=provider_readiness,
        provider_health=provider_health,
        ingress_enabled=ingress_enabled,
        item9_collector=item9_collector,
        intent=intent,
        now_et=now_et,
        state_directory=state_directory,
    )


__all__ = [
    "ARM_OBSERVATION_CLI",
    "BLOCKING_ALERT_NOT_ARMED",
    "DEFAULT_RTH_SOON_MINUTES",
    "INTENT_FILENAME",
    "READINESS_PHASES",
    "SCHEMA_VERSION",
    "build_campaign_observation_readiness",
    "compose_campaign_observation_readiness_for_state",
    "load_observation_intent",
]

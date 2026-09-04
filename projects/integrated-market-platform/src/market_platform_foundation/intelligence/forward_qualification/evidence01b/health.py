"""Campaign health assessment for EVIDENCE-01B."""

from __future__ import annotations

import time
from typing import Any

from ..evidence01.continuity import is_trading_day
from ..evidence01.types import EVIDENCE01_MAX_ADMISSIBLE_GAP_NS
from ..evidence01a.types import ForwardObservationCampaignState
from .types import (
    CampaignHealthAssessmentV1,
    CampaignHealthState,
    DiagnosticCode,
    HealthSeverity,
    RuntimeHeartbeatState,
    RuntimeHeartbeatV1,
    STALE_HEARTBEAT_NS,
)


def _is_market_open(now_ns: int) -> bool:
    from datetime import datetime

    from zoneinfo import ZoneInfo

    et = ZoneInfo("America/New_York")
    dt = datetime.fromtimestamp(now_ns / 1_000_000_000, tz=et)
    if not is_trading_day(dt.date()):
        return False
    minutes = dt.hour * 60 + dt.minute
    return 9 * 60 + 30 <= minutes < 16 * 60


def assess_heartbeat(
    heartbeat: RuntimeHeartbeatV1,
    *,
    now_ns: int | None = None,
) -> RuntimeHeartbeatState:
    now = now_ns if now_ns is not None else time.time_ns()
    if heartbeat.last_heartbeat_ns == 0:
        return RuntimeHeartbeatState.PROCESS_STOPPED
    if now - heartbeat.last_heartbeat_ns > STALE_HEARTBEAT_NS:
        return RuntimeHeartbeatState.ACTIVE_BUT_STALE
    if not _is_market_open(now):
        return RuntimeHeartbeatState.MARKET_CLOSED
    if heartbeat.last_provider_event_ns is None:
        return RuntimeHeartbeatState.PROVIDER_IDLE
    return RuntimeHeartbeatState.ACTIVE_AND_HEALTHY


def assess_campaign_health(
    *,
    campaign_state: ForwardObservationCampaignState,
    provider_connected: bool,
    provider_degraded: bool,
    settlement_backlog: int,
    qualifying_continuity_gap_ns: int,
    clock_drift_exclusions: int,
    eligible_predictions: int,
    paused: bool = False,
    invalidated: bool = False,
    now_ns: int | None = None,
) -> CampaignHealthAssessmentV1:
    now = now_ns if now_ns is not None else time.time_ns()
    diagnostics: list[str] = []
    codes: list[DiagnosticCode] = []

    if invalidated:
        return CampaignHealthAssessmentV1(
            health_state=CampaignHealthState.INVALIDATED,
            severity=HealthSeverity.BLOCKING,
            diagnostics=("campaign invalidated",),
            diagnostic_codes=(),
            provider_state="INVALIDATED",
            settlement_backlog=settlement_backlog,
            qualifying_continuity_gap_ns=qualifying_continuity_gap_ns,
        )

    if paused or campaign_state == ForwardObservationCampaignState.PAUSED:
        return CampaignHealthAssessmentV1(
            health_state=CampaignHealthState.PAUSED,
            severity=HealthSeverity.INFO,
            diagnostics=("campaign paused by operator",),
            diagnostic_codes=(),
            provider_state="PAUSED",
            settlement_backlog=settlement_backlog,
            qualifying_continuity_gap_ns=qualifying_continuity_gap_ns,
        )

    if not provider_connected:
        diagnostics.append("provider disconnected")
        return CampaignHealthAssessmentV1(
            health_state=CampaignHealthState.PROVIDER_DISCONNECTED,
            severity=HealthSeverity.DEGRADED,
            diagnostics=tuple(diagnostics),
            diagnostic_codes=(DiagnosticCode.NO_PROVIDER_EVENTS,),
            provider_state="DISCONNECTED",
            settlement_backlog=settlement_backlog,
            qualifying_continuity_gap_ns=qualifying_continuity_gap_ns,
        )

    if provider_degraded:
        diagnostics.append("provider degraded")
        health = CampaignHealthState.PROVIDER_DEGRADED
        severity = HealthSeverity.WARNING
    elif clock_drift_exclusions > 0:
        diagnostics.append(f"clock drift exclusions: {clock_drift_exclusions}")
        health = CampaignHealthState.CLOCK_INTEGRITY_FAILURE
        severity = HealthSeverity.BLOCKING
    elif qualifying_continuity_gap_ns > EVIDENCE01_MAX_ADMISSIBLE_GAP_NS:
        diagnostics.append("continuity gap exceeds policy threshold")
        health = CampaignHealthState.CONTINUITY_AT_RISK
        severity = HealthSeverity.DEGRADED
    elif settlement_backlog > 10:
        diagnostics.append(f"settlement backlog: {settlement_backlog}")
        codes.append(DiagnosticCode.SETTLEMENT_BACKLOG)
        health = CampaignHealthState.SETTLEMENT_BACKLOG
        severity = HealthSeverity.WARNING
    elif not _is_market_open(now):
        diagnostics.append("market closed")
        codes.append(DiagnosticCode.MARKET_CLOSED)
        health = CampaignHealthState.WAITING_FOR_MARKET
        severity = HealthSeverity.INFO
    elif eligible_predictions == 0:
        diagnostics.append("no eligible predictions yet")
        codes.append(DiagnosticCode.NO_VALID_CANDIDATES)
        health = CampaignHealthState.NO_ELIGIBLE_PREDICTIONS
        severity = HealthSeverity.INFO
    else:
        health = CampaignHealthState.HEALTHY_AND_ACCUMULATING
        severity = HealthSeverity.INFO

    return CampaignHealthAssessmentV1(
        health_state=health,
        severity=severity,
        diagnostics=tuple(diagnostics) if diagnostics else ("accumulating evidence",),
        diagnostic_codes=tuple(codes),
        provider_state="DEGRADED" if provider_degraded else "CONNECTED",
        settlement_backlog=settlement_backlog,
        qualifying_continuity_gap_ns=qualifying_continuity_gap_ns,
    )


def format_health_status(
    *,
    campaign_id: str,
    campaign_state: str,
    health: CampaignHealthAssessmentV1,
    config_fingerprint: str,
    source_sha: str,
    policy_id: str,
    provider_id: str,
    session_id: str | None,
    metrics: dict[str, Any],
    progress: dict[str, Any],
    disposition: str,
    remaining: tuple[str, ...],
    heartbeat: RuntimeHeartbeatV1 | None = None,
) -> str:
    lines = [
        "EVIDENCE-01B CAMPAIGN STATUS",
        "",
        f"Campaign ID:            {campaign_id}",
        f"Campaign state:         {campaign_state}",
        f"Health state:           {health.health_state.value}",
        f"Health severity:        {health.severity.value}",
        f"Source SHA:             {source_sha}",
        f"Config fingerprint:     {config_fingerprint}",
        f"Policy ID:              {policy_id}",
        f"Provider:               {provider_id} ({health.provider_state})",
        f"Current session:        {session_id or 'none'}",
        f"Settlement backlog:     {health.settlement_backlog}",
        f"Qualifying gap:         {health.qualifying_continuity_gap_ns // 3_600_000_000_000}h max",
        "",
        "Progress:",
        f"  Calendar span:        {progress.get('calendar_span_days', {}).get('actual', 0)} / {progress.get('calendar_span_days', {}).get('required', 0)} days",
        f"  Trading days:         {progress.get('trading_days', {}).get('actual', 0)} / {progress.get('trading_days', {}).get('required', 0)}",
        f"  Sessions:             {progress.get('sessions', {}).get('actual', 0)} / {progress.get('sessions', {}).get('required', 0)}",
        f"  Eligible predictions: {progress.get('eligible_predictions', {}).get('actual', 0)} / {progress.get('eligible_predictions', {}).get('required', 0)}",
        f"  Settled predictions:  {progress.get('settled_predictions', {}).get('actual', 0)} / {progress.get('settled_predictions', {}).get('required', 0)}",
        "",
        "Metrics:",
        f"  Provider events:      {metrics.get('provider_events_received', 0)} received, {metrics.get('provider_events_accepted', 0)} accepted",
        f"  Predictions emitted:  {metrics.get('predictions_emitted', 0)}",
        f"  Reconnects:           {metrics.get('reconnects', 0)}",
        f"  Runtime restarts:     {metrics.get('runtime_restarts', 0)}",
        "",
        "Disposition:",
        disposition,
    ]
    if health.diagnostics:
        lines.extend(["", "Diagnostics:"])
        lines.extend(f"  - {d}" for d in health.diagnostics)
    if remaining:
        lines.extend(["", "Remaining requirements:"])
        lines.extend(f"  - {item}" for item in remaining)
    if heartbeat is not None:
        lines.extend(["", f"Heartbeat: {heartbeat.state.value}"])
    return "\n".join(lines)

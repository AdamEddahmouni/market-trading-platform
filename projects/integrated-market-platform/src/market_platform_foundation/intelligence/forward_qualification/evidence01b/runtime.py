"""EVIDENCE-01B campaign runtime orchestration."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from market_platform_foundation.git_ref import read_git_head

from ..evidence01a.service import CampaignService
from ..evidence01a.types import (
    CampaignEvidenceOrigin,
    ForwardObservationCampaignState,
    SessionTerminationReason,
)
from .config import build_configuration_snapshot
from .continuity import maximum_qualifying_session_gap
from .events import derive_event_id
from .health import assess_campaign_health, assess_heartbeat
from .provider_bridge import FakeProviderAdapter, ProviderEventV1, build_provider_provenance
from .settlement_worker import SettlementWorker
from .store import CampaignRuntimeStore
from .types import (
    CHECKPOINT_INTERVAL_NS,
    CampaignMetricsV1,
    HealthSeverity,
    OperationalEventType,
    RuntimeHeartbeatState,
    RuntimeHeartbeatV1,
    ShakedownStatus,
)


@dataclass
class CampaignRuntime:
    """Long-running campaign runtime with provider, settlement, and checkpoint loops."""

    service: CampaignService
    store: CampaignRuntimeStore
    provider: FakeProviderAdapter = field(default_factory=FakeProviderAdapter)
    _running: bool = False
    _paused: bool = False
    _decision_times: list[int] = field(default_factory=list)
    _metrics: CampaignMetricsV1 = field(default_factory=CampaignMetricsV1)
    _process_started_at_ns: int = 0
    _last_settlement_ns: int = 0
    _last_checkpoint_ns: int = 0
    _last_provider_event_ns: int | None = None
    _last_accepted_observation_ns: int | None = None
    _provider_degraded: bool = False

    @classmethod
    def open(cls, campaign_dir: Path) -> CampaignRuntime:
        store = CampaignRuntimeStore(campaign_dir)
        service = CampaignService.open(campaign_dir)
        service.repository = __import__(
            "market_platform_foundation.intelligence.forward_qualification.evidence01a.observations",
            fromlist=["load_campaign_repository"],
        ).load_campaign_repository(store)
        return cls(service=service, store=store)

    def recover(self) -> None:
        """Recover from crash: reload state, classify incomplete session."""
        state = self.store.read_runtime_state()
        self._metrics = self.store.read_metrics()
        self._metrics.runtime_restarts += 1
        if state.active_session_id is not None:
            try:
                session = self.store.read_session(state.active_session_id)
                if session.ended_at_ns is None:
                    self.service.stop_session(
                        reason=SessionTerminationReason.CRASH_RECOVERY,
                        now_ns=time.time_ns(),
                    )
            except Exception:
                state = replace(state, active_session_id=None)
                self.store.write_runtime_state(state)
        self._record_event(
            OperationalEventType.RUNTIME_STARTED,
            "runtime recovered after restart",
            severity=HealthSeverity.INFO,
        )
        self.store.write_metrics(self._metrics)

    def start_runtime(self, *, now_ns: int | None = None) -> None:
        now = now_ns if now_ns is not None else time.time_ns()
        self._running = True
        self._process_started_at_ns = now
        spec = self.store.read_spec()
        config = build_configuration_snapshot(spec)
        self.store.write_configuration_snapshot(config)
        state = self.store.read_runtime_state()
        if state.campaign_state not in {
            ForwardObservationCampaignState.ACTIVE,
            ForwardObservationCampaignState.PAUSED,
        }:
            self.service.start_campaign()
        self._record_event(OperationalEventType.CAMPAIGN_STARTED, "campaign runtime started")
        self._write_heartbeat(now)

    def stop_runtime(self, *, now_ns: int | None = None) -> None:
        now = now_ns if now_ns is not None else time.time_ns()
        if self.service._active_session is not None:
            self.service.stop_session(
                reason=SessionTerminationReason.CLEAN_SHUTDOWN,
                now_ns=now,
            )
            self._record_event(OperationalEventType.SESSION_FINALIZED, "session finalized on shutdown")
        self._running = False
        self._write_heartbeat(now, state=RuntimeHeartbeatState.PROCESS_STOPPED)
        self.store.write_metrics(self._metrics)
        self._record_event(OperationalEventType.RUNTIME_STOPPED, "runtime stopped cleanly")

    def pause(self, *, reason: str = "operator_pause") -> None:
        self._paused = True
        state = self.store.read_runtime_state()
        self.store.write_runtime_state(
            replace(state, campaign_state=ForwardObservationCampaignState.PAUSED)
        )
        self._record_event(OperationalEventType.SESSION_PAUSED, reason)

    def resume(self, *, now_ns: int | None = None) -> None:
        now = now_ns if now_ns is not None else time.time_ns()
        current_sha = read_git_head() or "unknown"
        spec = self.store.read_spec()
        frozen = self.store.read_configuration_snapshot()
        if frozen and frozen.source_sha != current_sha:
            if frozen.campaign_configuration_fingerprint != build_configuration_snapshot(spec).campaign_configuration_fingerprint:
                raise ValueError("semantic source change blocks resume")
        self._paused = False
        state = self.store.read_runtime_state()
        self.store.write_runtime_state(
            replace(state, campaign_state=ForwardObservationCampaignState.ACTIVE)
        )
        self._record_event(OperationalEventType.SESSION_RESUMED, "campaign resumed", now_ns=now)

    def start_session(self, *, now_ns: int | None = None) -> None:
        now = now_ns if now_ns is not None else time.time_ns()
        session = self.service.start_session(now_ns=now)
        self._record_event(
            OperationalEventType.SESSION_STARTED,
            f"session {session.session_id} started",
            session_id=session.session_id,
            now_ns=now,
        )

    def ingest_provider_event(self, event: ProviderEventV1) -> bool:
        """Ingest a provider event; returns True if accepted."""
        self._metrics.provider_events_received += 1
        self._last_provider_event_ns = event.received_time_ns

        if not self.provider.ingest_event(event):
            if self.provider.duplicate_events > self._metrics.duplicate_events:
                self._metrics.duplicate_events = self.provider.duplicate_events
            self._metrics.provider_events_excluded += 1
            return False

        if self._paused or not self._running:
            self._metrics.provider_events_excluded += 1
            return False

        if event.quality_state not in {"GOOD", "DEGRADED"}:
            self._metrics.provider_events_excluded += 1
            if event.quality_state == "CLOCK_DRIFT":
                self._metrics.clock_drift_exclusions += 1
            return False

        self._metrics.provider_events_accepted += 1
        self._last_accepted_observation_ns = event.received_time_ns
        return True

    def on_provider_disconnect(self) -> None:
        self.provider.disconnect()
        self._provider_degraded = True
        if self.service._active_session is not None:
            self.service._active_session.reconnect_count += 1
            self._metrics.reconnects += 1
        self._record_event(
            OperationalEventType.PROVIDER_DISCONNECTED,
            "provider disconnected",
            severity=HealthSeverity.DEGRADED,
        )

    def on_provider_reconnect(self) -> None:
        self.provider.reconnect()
        self._provider_degraded = False
        self._record_event(
            OperationalEventType.PROVIDER_RECONNECTED,
            "provider reconnected",
            severity=HealthSeverity.INFO,
        )

    def record_decision_time(self, decision_time_ns: int) -> None:
        self._decision_times.append(decision_time_ns)
        if self.service._active_session is not None and len(self._decision_times) >= 2:
            gap = maximum_qualifying_session_gap(self._decision_times)
            session = self.service._active_session.session
            self.service._active_session.session = replace(
                session,
                maximum_continuity_gap_ns=max(session.maximum_continuity_gap_ns, gap),
            )
            if gap > 0:
                self._metrics.continuity_gaps += 1

    def run_settlement_cycle(self, *, now_ns: int | None = None) -> int:
        now = now_ns if now_ns is not None else time.time_ns()
        worker = SettlementWorker(self.service.repository, store=self.store)
        batch = worker.run_settlement_batch(now_ns=now)
        self._metrics.settled_predictions += batch.settled
        self._metrics.settlement_failures += batch.transient_failures + batch.permanent_failures
        self._metrics.settlement_backlog = batch.backlog
        self._last_settlement_ns = now
        if batch.settled > 0:
            self._record_event(
                OperationalEventType.SETTLEMENT_BATCH_COMPLETED,
                f"settled {batch.settled} predictions",
                metadata={"settled": batch.settled, "backlog": batch.backlog},
            )
        return batch.settled

    def run_checkpoint_cycle(self, *, now_ns: int | None = None, force: bool = False) -> bool:
        now = now_ns if now_ns is not None else time.time_ns()
        if not force and self._last_checkpoint_ns and (now - self._last_checkpoint_ns) < CHECKPOINT_INTERVAL_NS:
            return False
        checkpoint = self.service.generate_checkpoint(
            observation_cutoff_ns=now,
            settlement_cutoff_ns=now,
        )
        self._last_checkpoint_ns = now
        self._metrics.checkpoints_created += 1
        self._record_event(
            OperationalEventType.CHECKPOINT_CREATED,
            f"checkpoint {checkpoint.checkpoint_id}",
            metadata={"disposition": checkpoint.qualification_disposition},
        )
        return True

    def tick(self, *, now_ns: int | None = None) -> None:
        """Single runtime tick: heartbeat, settlement, checkpoint."""
        now = now_ns if now_ns is not None else time.time_ns()
        self._write_heartbeat(now)
        self.run_settlement_cycle(now_ns=now)
        if self.service._active_session is not None:
            self.run_checkpoint_cycle(now_ns=now)
        self.store.write_metrics(self._metrics)

    def invalidate(self, *, reason: str, now_ns: int | None = None) -> None:
        now = now_ns if now_ns is not None else time.time_ns()
        state = self.store.read_runtime_state()
        self.store.write_runtime_state(
            replace(state, campaign_state=ForwardObservationCampaignState.INVALIDATED)
        )
        self.store.append_invalidation(reason, recorded_at_ns=now)
        self._record_event(
            OperationalEventType.CAMPAIGN_INVALIDATED,
            reason,
            severity=HealthSeverity.BLOCKING,
            now_ns=now,
        )

    def start_shakedown(self) -> ShakedownStatus:
        spec = self.store.read_spec()
        if spec.evidence_origin == CampaignEvidenceOrigin.LIVE_FORWARD:
            pass
        self.store.write_shakedown_status(ShakedownStatus.SHAKEDOWN_ACTIVE)
        self._record_event(OperationalEventType.SHAKEDOWN_STARTED, "shakedown mode started")
        return ShakedownStatus.SHAKEDOWN_ACTIVE

    def complete_shakedown(self, *, passed: bool) -> ShakedownStatus:
        status = ShakedownStatus.SHAKEDOWN_PASSED if passed else ShakedownStatus.SHAKEDOWN_FAILED
        self.store.write_shakedown_status(status)
        self._record_event(
            OperationalEventType.SHAKEDOWN_COMPLETED,
            f"shakedown {status.value}",
        )
        return status

    def assess_health(self, *, now_ns: int | None = None):
        from .health import assess_campaign_health

        now = now_ns if now_ns is not None else time.time_ns()
        state = self.store.read_runtime_state()
        spec = self.store.read_spec()
        worker = SettlementWorker(self.service.repository)
        backlog = worker.settlement_backlog(now_ns=now)
        gap = maximum_qualifying_session_gap(self._decision_times)
        checkpoint = self.service.generate_checkpoint(observation_cutoff_ns=now, settlement_cutoff_ns=now)
        return assess_campaign_health(
            campaign_state=state.campaign_state,
            provider_connected=self.provider.connected,
            provider_degraded=self._provider_degraded,
            settlement_backlog=backlog,
            qualifying_continuity_gap_ns=gap,
            clock_drift_exclusions=self._metrics.clock_drift_exclusions,
            eligible_predictions=checkpoint.progress.get("eligible_predictions", {}).get("actual", 0),
            paused=self._paused,
            invalidated=state.campaign_state == ForwardObservationCampaignState.INVALIDATED,
            now_ns=now,
        )

    def _write_heartbeat(self, now_ns: int, *, state: RuntimeHeartbeatState | None = None) -> None:
        hb_state = state or assess_heartbeat(
            RuntimeHeartbeatV1(
                state=RuntimeHeartbeatState.ACTIVE_AND_HEALTHY,
                last_heartbeat_ns=now_ns,
                last_provider_event_ns=self._last_provider_event_ns,
                last_accepted_observation_ns=self._last_accepted_observation_ns,
                process_started_at_ns=self._process_started_at_ns,
            ),
            now_ns=now_ns,
        )
        self.store.write_heartbeat(
            RuntimeHeartbeatV1(
                state=hb_state,
                last_heartbeat_ns=now_ns,
                last_provider_event_ns=self._last_provider_event_ns,
                last_accepted_observation_ns=self._last_accepted_observation_ns,
                process_started_at_ns=self._process_started_at_ns,
            )
        )

    def _record_event(
        self,
        event_type: OperationalEventType,
        message: str,
        *,
        session_id: str | None = None,
        severity: HealthSeverity = HealthSeverity.INFO,
        now_ns: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = now_ns if now_ns is not None else time.time_ns()
        spec = self.store.read_spec()
        active = self.service._active_session
        sid = session_id or (active.session.session_id if active else None)
        from .types import OperationalEventV1

        event = OperationalEventV1(
            event_id=derive_event_id(
                campaign_id=spec.campaign_id,
                event_type=event_type,
                recorded_at_ns=now,
                session_id=sid,
            ),
            event_type=event_type,
            campaign_id=spec.campaign_id,
            session_id=sid,
            recorded_at_ns=now,
            severity=severity,
            message=message,
            metadata=metadata or {},
        )
        self.store.append_operational_event(event)

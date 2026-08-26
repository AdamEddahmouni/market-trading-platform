"""Extended campaign store for EVIDENCE-01B runtime artifacts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..evidence01a.store import CampaignStore
from .config import configuration_snapshot_from_dict, configuration_snapshot_to_dict
from .events import append_event_jsonl, operational_event_from_dict
from .types import (
    CampaignConfigurationSnapshotV1,
    CampaignMetricsV1,
    OperationalEventV1,
    RuntimeHeartbeatV1,
    RuntimeHeartbeatState,
    ShakedownStatus,
)


class CampaignRuntimeStore(CampaignStore):
    """Campaign store with EVIDENCE-01B runtime persistence."""

    @property
    def events_path(self) -> Path:
        return self.root / "OPERATIONAL_EVENTS.jsonl"

    @property
    def metrics_path(self) -> Path:
        return self.root / "CAMPAIGN_METRICS.json"

    @property
    def heartbeat_path(self) -> Path:
        return self.root / "RUNTIME_HEARTBEAT.json"

    @property
    def config_snapshot_path(self) -> Path:
        return self.root / "CONFIGURATION_SNAPSHOT.json"

    @property
    def shakedown_path(self) -> Path:
        return self.root / "SHAKEDOWN_STATE.json"

    @property
    def settlement_retry_path(self) -> Path:
        return self.root / "SETTLEMENT_RETRY_STATE.json"

    def write_configuration_snapshot(self, snapshot: CampaignConfigurationSnapshotV1) -> None:
        self._atomic_write(
            self.config_snapshot_path,
            json.dumps(configuration_snapshot_to_dict(snapshot), indent=2),
        )

    def read_configuration_snapshot(self) -> CampaignConfigurationSnapshotV1 | None:
        if not self.config_snapshot_path.exists():
            return None
        return configuration_snapshot_from_dict(
            json.loads(self.config_snapshot_path.read_text(encoding="utf-8"))
        )

    def append_operational_event(self, event: OperationalEventV1) -> None:
        append_event_jsonl(self.events_path, event)

    def list_operational_events(self) -> tuple[OperationalEventV1, ...]:
        if not self.events_path.exists():
            return ()
        events: list[OperationalEventV1] = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            events.append(operational_event_from_dict(json.loads(line)))
        return tuple(events)

    def write_metrics(self, metrics: CampaignMetricsV1) -> None:
        self._atomic_write(self.metrics_path, json.dumps(metrics.to_dict(), indent=2))

    def read_metrics(self) -> CampaignMetricsV1:
        if not self.metrics_path.exists():
            return CampaignMetricsV1()
        payload = json.loads(self.metrics_path.read_text(encoding="utf-8"))
        return CampaignMetricsV1(**{k: int(payload.get(k, 0)) for k in CampaignMetricsV1.__dataclass_fields__})

    def write_heartbeat(self, heartbeat: RuntimeHeartbeatV1) -> None:
        payload = {
            "state": heartbeat.state.value,
            "last_heartbeat_ns": heartbeat.last_heartbeat_ns,
            "last_provider_event_ns": heartbeat.last_provider_event_ns,
            "last_accepted_observation_ns": heartbeat.last_accepted_observation_ns,
            "process_started_at_ns": heartbeat.process_started_at_ns,
            "metadata": dict(heartbeat.metadata),
        }
        self._atomic_write(self.heartbeat_path, json.dumps(payload, indent=2))

    def read_heartbeat(self) -> RuntimeHeartbeatV1:
        if not self.heartbeat_path.exists():
            return RuntimeHeartbeatV1(
                state=RuntimeHeartbeatState.PROCESS_STOPPED,
                last_heartbeat_ns=0,
            )
        payload = json.loads(self.heartbeat_path.read_text(encoding="utf-8"))
        return RuntimeHeartbeatV1(
            state=RuntimeHeartbeatState(str(payload.get("state", "PROCESS_STOPPED"))),
            last_heartbeat_ns=int(payload.get("last_heartbeat_ns", 0)),
            last_provider_event_ns=payload.get("last_provider_event_ns"),
            last_accepted_observation_ns=payload.get("last_accepted_observation_ns"),
            process_started_at_ns=payload.get("process_started_at_ns"),
            metadata=dict(payload.get("metadata") or {}),
        )

    def write_shakedown_status(self, status: ShakedownStatus, *, metadata: dict[str, Any] | None = None) -> None:
        self._atomic_write(
            self.shakedown_path,
            json.dumps({"status": status.value, "metadata": metadata or {}}, indent=2),
        )

    def read_shakedown_status(self) -> ShakedownStatus:
        if not self.shakedown_path.exists():
            return ShakedownStatus.SHAKEDOWN_NOT_STARTED
        payload = json.loads(self.shakedown_path.read_text(encoding="utf-8"))
        return ShakedownStatus(str(payload.get("status", "SHAKEDOWN_NOT_STARTED")))

    def append_invalidation(self, reason: str, *, recorded_at_ns: int) -> None:
        path = self.root / "INVALIDATION_EVENTS.jsonl"
        line = json.dumps({"reason": reason, "recorded_at_ns": recorded_at_ns}, sort_keys=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

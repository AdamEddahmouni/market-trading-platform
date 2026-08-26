"""Append-only campaign persistence for EVIDENCE-01A."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .types import (
    CampaignObservationRefV1,
    ForwardObservationCampaignCheckpointV1,
    ForwardObservationCampaignSessionV1,
    ForwardObservationCampaignSpecV1,
    ForwardObservationCampaignState,
)


@dataclass
class CampaignRuntimeState:
    campaign_id: str
    campaign_state: ForwardObservationCampaignState
    active_session_id: str | None = None
    session_count: int = 0
    checkpoint_count: int = 0
    last_checkpoint_id: str | None = None
    metadata: dict[str, Any] | None = None


class CampaignStoreError(ValueError):
    pass


class CampaignStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._sessions_dir = self.root / "sessions"
        self._checkpoints_dir = self.root / "checkpoints"
        self._sessions_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoints_dir.mkdir(parents=True, exist_ok=True)

    @property
    def spec_path(self) -> Path:
        return self.root / "CAMPAIGN_SPEC.json"

    @property
    def runtime_state_path(self) -> Path:
        return self.root / "CAMPAIGN_RUNTIME_STATE.json"

    @property
    def observations_path(self) -> Path:
        return self.root / "OBSERVATIONS.jsonl"

    @property
    def intelligence_path(self) -> Path:
        return self.root / "intelligence_records.jsonl"

    def write_spec(self, spec: ForwardObservationCampaignSpecV1) -> None:
        self._atomic_write(self.spec_path, json.dumps(_spec_to_dict(spec), indent=2))

    def read_spec(self) -> ForwardObservationCampaignSpecV1:
        payload = json.loads(self.spec_path.read_text(encoding="utf-8"))
        return _spec_from_dict(payload)

    def write_runtime_state(self, state: CampaignRuntimeState) -> None:
        payload = {
            "campaign_id": state.campaign_id,
            "campaign_state": state.campaign_state.value,
            "active_session_id": state.active_session_id,
            "session_count": state.session_count,
            "checkpoint_count": state.checkpoint_count,
            "last_checkpoint_id": state.last_checkpoint_id,
            "metadata": state.metadata or {},
        }
        self._atomic_write(self.runtime_state_path, json.dumps(payload, indent=2))

    def read_runtime_state(self) -> CampaignRuntimeState:
        payload = json.loads(self.runtime_state_path.read_text(encoding="utf-8"))
        return CampaignRuntimeState(
            campaign_id=str(payload["campaign_id"]),
            campaign_state=ForwardObservationCampaignState(str(payload["campaign_state"])),
            active_session_id=payload.get("active_session_id"),
            session_count=int(payload.get("session_count", 0)),
            checkpoint_count=int(payload.get("checkpoint_count", 0)),
            last_checkpoint_id=payload.get("last_checkpoint_id"),
            metadata=dict(payload.get("metadata") or {}),
        )

    def append_observation_ref(self, ref: CampaignObservationRefV1) -> None:
        line = json.dumps(_observation_ref_to_dict(ref), sort_keys=True)
        with self.observations_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def list_observation_refs(self) -> tuple[CampaignObservationRefV1, ...]:
        if not self.observations_path.exists():
            return ()
        refs: list[CampaignObservationRefV1] = []
        for line in self.observations_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            refs.append(_observation_ref_from_dict(json.loads(line)))
        return tuple(refs)

    def append_intelligence_record(self, record_type: str, payload: dict[str, Any]) -> None:
        line = json.dumps({"record_type": record_type, "payload": payload}, sort_keys=True)
        with self.intelligence_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def list_intelligence_records(self) -> tuple[dict[str, Any], ...]:
        if not self.intelligence_path.exists():
            return ()
        rows: list[dict[str, Any]] = []
        for line in self.intelligence_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rows.append(json.loads(line))
        return tuple(rows)

    def write_session(self, session: ForwardObservationCampaignSessionV1) -> None:
        path = self._sessions_dir / f"SESSION_{session.session_id}.json"
        self._atomic_write(path, json.dumps(_session_to_dict(session), indent=2))

    def read_session(self, session_id: str) -> ForwardObservationCampaignSessionV1:
        path = self._sessions_dir / f"SESSION_{session_id}.json"
        return _session_from_dict(json.loads(path.read_text(encoding="utf-8")))

    def list_sessions(self) -> tuple[ForwardObservationCampaignSessionV1, ...]:
        sessions: list[ForwardObservationCampaignSessionV1] = []
        for path in sorted(self._sessions_dir.glob("SESSION_*.json")):
            sessions.append(_session_from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return tuple(sessions)

    def append_checkpoint(self, checkpoint: ForwardObservationCampaignCheckpointV1) -> None:
        path = self._checkpoints_dir / f"CHECKPOINT_{checkpoint.checkpoint_id}.json"
        if path.exists():
            return
        self._atomic_write(path, json.dumps(_checkpoint_to_dict(checkpoint), indent=2))

    def list_checkpoints(self) -> tuple[ForwardObservationCampaignCheckpointV1, ...]:
        rows: list[ForwardObservationCampaignCheckpointV1] = []
        for path in sorted(self._checkpoints_dir.glob("CHECKPOINT_*.json")):
            rows.append(_checkpoint_from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return tuple(rows)

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        tmp.replace(path)


def _spec_to_dict(spec: ForwardObservationCampaignSpecV1) -> dict[str, Any]:
    return {
        "campaign_id": spec.campaign_id,
        "schema_version": spec.schema_version,
        "campaign_name": spec.campaign_name,
        "policy_id": spec.policy_id,
        "source_commit_sha": spec.source_commit_sha,
        "runtime_version": spec.runtime_version,
        "provider_id": spec.provider_id,
        "instrument_universe": list(spec.instrument_universe),
        "observation_mode": spec.observation_mode,
        "evidence_origin": spec.evidence_origin.value,
        "execution_mode": spec.execution_mode,
        "execution_authority": spec.execution_authority,
        "persistence_backend": spec.persistence_backend,
        "checkpoint_cadence": spec.checkpoint_cadence,
        "settlement_cadence": spec.settlement_cadence,
        "implementation_version": spec.implementation_version,
        "metadata": dict(spec.metadata),
    }


def _spec_from_dict(payload: dict[str, Any]) -> ForwardObservationCampaignSpecV1:
    from .types import CampaignEvidenceOrigin

    return ForwardObservationCampaignSpecV1(
        campaign_id=str(payload["campaign_id"]),
        schema_version=str(payload["schema_version"]),
        campaign_name=str(payload["campaign_name"]),
        policy_id=str(payload["policy_id"]),
        source_commit_sha=str(payload["source_commit_sha"]),
        runtime_version=str(payload["runtime_version"]),
        provider_id=str(payload["provider_id"]),
        instrument_universe=tuple(str(x) for x in payload["instrument_universe"]),
        observation_mode=str(payload["observation_mode"]),
        evidence_origin=CampaignEvidenceOrigin(str(payload["evidence_origin"])),
        execution_mode=str(payload["execution_mode"]),
        execution_authority=str(payload["execution_authority"]),
        persistence_backend=str(payload["persistence_backend"]),
        checkpoint_cadence=str(payload["checkpoint_cadence"]),
        settlement_cadence=str(payload["settlement_cadence"]),
        implementation_version=str(payload["implementation_version"]),
        metadata=dict(payload.get("metadata") or {}),
    )


def _session_to_dict(session: ForwardObservationCampaignSessionV1) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "schema_version": session.schema_version,
        "campaign_id": session.campaign_id,
        "source_commit_sha": session.source_commit_sha,
        "policy_id": session.policy_id,
        "started_at_ns": session.started_at_ns,
        "ended_at_ns": session.ended_at_ns,
        "termination_reason": session.termination_reason,
        "provider_id": session.provider_id,
        "provider_connected": session.provider_connected,
        "instrument_universe": list(session.instrument_universe),
        "evidence_origin": session.evidence_origin.value,
        "prediction_count": session.prediction_count,
        "eligible_prediction_count": session.eligible_prediction_count,
        "quality_exclusions": dict(session.quality_exclusions),
        "orders_submitted": session.orders_submitted,
        "reconnect_count": session.reconnect_count,
        "maximum_continuity_gap_ns": session.maximum_continuity_gap_ns,
        "runtime_errors": list(session.runtime_errors),
        "clean_shutdown": session.clean_shutdown,
        "metadata": dict(session.metadata),
    }


def _session_from_dict(payload: dict[str, Any]) -> ForwardObservationCampaignSessionV1:
    from .types import CampaignEvidenceOrigin

    return ForwardObservationCampaignSessionV1(
        session_id=str(payload["session_id"]),
        schema_version=str(payload["schema_version"]),
        campaign_id=str(payload["campaign_id"]),
        source_commit_sha=str(payload["source_commit_sha"]),
        policy_id=str(payload["policy_id"]),
        started_at_ns=int(payload["started_at_ns"]),
        ended_at_ns=payload.get("ended_at_ns"),
        termination_reason=payload.get("termination_reason"),
        provider_id=str(payload["provider_id"]),
        provider_connected=bool(payload.get("provider_connected", True)),
        instrument_universe=tuple(str(x) for x in payload["instrument_universe"]),
        evidence_origin=CampaignEvidenceOrigin(str(payload["evidence_origin"])),
        prediction_count=int(payload.get("prediction_count", 0)),
        eligible_prediction_count=int(payload.get("eligible_prediction_count", 0)),
        quality_exclusions=dict(payload.get("quality_exclusions") or {}),
        orders_submitted=int(payload.get("orders_submitted", 0)),
        reconnect_count=int(payload.get("reconnect_count", 0)),
        maximum_continuity_gap_ns=int(payload.get("maximum_continuity_gap_ns", 0)),
        runtime_errors=tuple(str(x) for x in payload.get("runtime_errors") or ()),
        clean_shutdown=bool(payload.get("clean_shutdown", False)),
        metadata=dict(payload.get("metadata") or {}),
    )


def _observation_ref_to_dict(ref: CampaignObservationRefV1) -> dict[str, Any]:
    return {
        "observation_ref_id": ref.observation_ref_id,
        "campaign_id": ref.campaign_id,
        "session_id": ref.session_id,
        "forecast_id": ref.forecast_id,
        "ledger_entry_id": ref.ledger_entry_id,
        "receipt_id": ref.receipt_id,
        "evidence_origin": ref.evidence_origin.value,
        "provider_id": ref.provider_id,
        "quality_state": ref.quality_state,
        "decision_time_ns": ref.decision_time_ns,
        "source_commit_sha": ref.source_commit_sha,
        "policy_id": ref.policy_id,
        "metadata": dict(ref.metadata),
    }


def _observation_ref_from_dict(payload: dict[str, Any]) -> CampaignObservationRefV1:
    from .types import CampaignEvidenceOrigin

    return CampaignObservationRefV1(
        observation_ref_id=str(payload["observation_ref_id"]),
        campaign_id=str(payload["campaign_id"]),
        session_id=str(payload["session_id"]),
        forecast_id=str(payload["forecast_id"]),
        ledger_entry_id=str(payload["ledger_entry_id"]),
        receipt_id=str(payload["receipt_id"]),
        evidence_origin=CampaignEvidenceOrigin(str(payload["evidence_origin"])),
        provider_id=str(payload["provider_id"]),
        quality_state=str(payload["quality_state"]),
        decision_time_ns=int(payload["decision_time_ns"]),
        source_commit_sha=str(payload["source_commit_sha"]),
        policy_id=str(payload["policy_id"]),
        metadata=dict(payload.get("metadata") or {}),
    )


def _checkpoint_to_dict(checkpoint: ForwardObservationCampaignCheckpointV1) -> dict[str, Any]:
    return {
        "checkpoint_id": checkpoint.checkpoint_id,
        "schema_version": checkpoint.schema_version,
        "campaign_id": checkpoint.campaign_id,
        "policy_id": checkpoint.policy_id,
        "assessment_id": checkpoint.assessment_id,
        "observation_cutoff_ns": checkpoint.observation_cutoff_ns,
        "settlement_cutoff_ns": checkpoint.settlement_cutoff_ns,
        "campaign_state": checkpoint.campaign_state.value,
        "qualification_disposition": checkpoint.qualification_disposition,
        "remaining_requirements": list(checkpoint.remaining_requirements),
        "progress": dict(checkpoint.progress),
        "metadata": dict(checkpoint.metadata),
    }


def _checkpoint_from_dict(payload: dict[str, Any]) -> ForwardObservationCampaignCheckpointV1:
    return ForwardObservationCampaignCheckpointV1(
        checkpoint_id=str(payload["checkpoint_id"]),
        schema_version=str(payload["schema_version"]),
        campaign_id=str(payload["campaign_id"]),
        policy_id=str(payload["policy_id"]),
        assessment_id=str(payload["assessment_id"]),
        observation_cutoff_ns=int(payload["observation_cutoff_ns"]),
        settlement_cutoff_ns=int(payload["settlement_cutoff_ns"]),
        campaign_state=ForwardObservationCampaignState(str(payload["campaign_state"])),
        qualification_disposition=str(payload["qualification_disposition"]),
        remaining_requirements=tuple(str(x) for x in payload.get("remaining_requirements") or ()),
        progress=dict(payload.get("progress") or {}),
        metadata=dict(payload.get("metadata") or {}),
    )

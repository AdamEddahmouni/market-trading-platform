"""Deterministic EVIDENCE-01A campaign identities."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .types import (
    CampaignObservationRefV1,
    ForwardObservationCampaignCheckpointV1,
    ForwardObservationCampaignReportV1,
    ForwardObservationCampaignSessionV1,
    ForwardObservationCampaignSpecV1,
    FORWARD_OBSERVATION_CAMPAIGN_IMPLEMENTATION_VERSION,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(prefix: str, payload: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest}"


def campaign_spec_identity_payload(spec: ForwardObservationCampaignSpecV1) -> dict[str, Any]:
    return {
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
        "implementation_version": spec.implementation_version,
    }


def derive_campaign_id(spec: ForwardObservationCampaignSpecV1) -> str:
    return _sha256_prefix("FOCAMP", campaign_spec_identity_payload(spec))


def derive_session_id(
    *,
    campaign_id: str,
    source_commit_sha: str,
    started_at_ns: int,
    session_index: int,
) -> str:
    payload = {
        "campaign_id": campaign_id,
        "source_commit_sha": source_commit_sha,
        "started_at_ns": started_at_ns,
        "session_index": session_index,
    }
    return _sha256_prefix("FOSESS", payload)


def derive_observation_ref_id(
    *,
    campaign_id: str,
    session_id: str,
    forecast_id: str,
    ledger_entry_id: str,
) -> str:
    payload = {
        "campaign_id": campaign_id,
        "session_id": session_id,
        "forecast_id": forecast_id,
        "ledger_entry_id": ledger_entry_id,
    }
    return _sha256_prefix("FOOBS", payload)


def derive_checkpoint_id(
    *,
    campaign_id: str,
    policy_id: str,
    observation_cutoff_ns: int,
    settlement_cutoff_ns: int,
    assessment_id: str,
) -> str:
    payload = {
        "campaign_id": campaign_id,
        "policy_id": policy_id,
        "observation_cutoff_ns": observation_cutoff_ns,
        "settlement_cutoff_ns": settlement_cutoff_ns,
        "assessment_id": assessment_id,
    }
    return _sha256_prefix("FOCHK", payload)


def derive_campaign_report_id(
    *,
    campaign_id: str,
    policy_id: str,
    final_assessment_id: str,
    observation_cutoff_ns: int,
    settlement_cutoff_ns: int,
) -> str:
    payload = {
        "campaign_id": campaign_id,
        "policy_id": policy_id,
        "final_assessment_id": final_assessment_id,
        "observation_cutoff_ns": observation_cutoff_ns,
        "settlement_cutoff_ns": settlement_cutoff_ns,
        "implementation_version": FORWARD_OBSERVATION_CAMPAIGN_IMPLEMENTATION_VERSION,
    }
    return _sha256_prefix("FOCREP", payload)


def session_identity_payload(session: ForwardObservationCampaignSessionV1) -> dict[str, Any]:
    return {
        "session_id": session.session_id,
        "campaign_id": session.campaign_id,
        "source_commit_sha": session.source_commit_sha,
        "policy_id": session.policy_id,
        "started_at_ns": session.started_at_ns,
        "ended_at_ns": session.ended_at_ns,
        "evidence_origin": session.evidence_origin.value,
    }


def checkpoint_identity_payload(checkpoint: ForwardObservationCampaignCheckpointV1) -> dict[str, Any]:
    return {
        "checkpoint_id": checkpoint.checkpoint_id,
        "campaign_id": checkpoint.campaign_id,
        "policy_id": checkpoint.policy_id,
        "assessment_id": checkpoint.assessment_id,
        "observation_cutoff_ns": checkpoint.observation_cutoff_ns,
        "settlement_cutoff_ns": checkpoint.settlement_cutoff_ns,
    }


def observation_ref_identity_payload(ref: CampaignObservationRefV1) -> dict[str, Any]:
    return {
        "observation_ref_id": ref.observation_ref_id,
        "campaign_id": ref.campaign_id,
        "session_id": ref.session_id,
        "forecast_id": ref.forecast_id,
        "ledger_entry_id": ref.ledger_entry_id,
        "receipt_id": ref.receipt_id,
        "evidence_origin": ref.evidence_origin.value,
        "decision_time_ns": ref.decision_time_ns,
    }


def report_identity_payload(report: ForwardObservationCampaignReportV1) -> dict[str, Any]:
    return {
        "report_id": report.report_id,
        "campaign_id": report.campaign_id,
        "policy_id": report.policy_id,
        "final_assessment_id": report.final_assessment_id,
        "observation_cutoff_ns": report.observation_cutoff_ns,
        "settlement_cutoff_ns": report.settlement_cutoff_ns,
    }

"""Campaign configuration freeze and drift detection for EVIDENCE-01B."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import Any

from ..evidence01.policy import BUILD26_QUALIFICATION_SPEC_ID
from ..evidence01a.types import ForwardObservationCampaignSpecV1
from .types import CampaignConfigurationSnapshotV1

SEMANTIC_CONFIG_FIELDS = (
    "policy_id",
    "provider_id",
    "instrument_universe",
    "observation_mode",
    "evidence_origin",
    "execution_mode",
    "execution_authority",
    "persistence_backend",
    "implementation_version",
)

MARKET_CALENDAR_ID = "us_equity_regular_session_v1"
CONTINUITY_POLICY_ID = "expected_observation_window_v1"
CANDIDATE_SELECTION_ID = "static_universe_v1"
PREDICTOR_ID = "direction_up_down_v1"
SETTLEMENT_POLICY_ID = "outcome_settlement_v1"
QUALITY_POLICY_ID = "good_degraded_v1"


def derive_configuration_fingerprint(snapshot: CampaignConfigurationSnapshotV1) -> str:
    payload = {
        "campaign_id": snapshot.campaign_id,
        "policy_id": snapshot.policy_id,
        "source_sha": snapshot.source_sha,
        "provider_id": snapshot.provider_id,
        "provider_config_id": snapshot.provider_config_id,
        "universe_definition": list(snapshot.universe_definition),
        "candidate_selection_id": snapshot.candidate_selection_id,
        "predictor_id": snapshot.predictor_id,
        "settlement_policy_id": snapshot.settlement_policy_id,
        "quality_policy_id": snapshot.quality_policy_id,
        "market_calendar_id": snapshot.market_calendar_id,
        "continuity_policy_id": snapshot.continuity_policy_id,
        "persistence_backend": snapshot.persistence_backend,
        "observation_mode": snapshot.observation_mode,
        "execution_authority": snapshot.execution_authority,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"CFGFP-{digest}"


def build_configuration_snapshot(
    spec: ForwardObservationCampaignSpecV1,
    *,
    provider_config_id: str = "moomoo_opend_default",
) -> CampaignConfigurationSnapshotV1:
    pending = CampaignConfigurationSnapshotV1(
        campaign_id=spec.campaign_id,
        policy_id=spec.policy_id,
        source_sha=spec.source_commit_sha,
        provider_id=spec.provider_id,
        provider_config_id=provider_config_id,
        universe_definition=spec.instrument_universe,
        candidate_selection_id=CANDIDATE_SELECTION_ID,
        predictor_id=PREDICTOR_ID,
        settlement_policy_id=SETTLEMENT_POLICY_ID,
        quality_policy_id=QUALITY_POLICY_ID,
        market_calendar_id=MARKET_CALENDAR_ID,
        continuity_policy_id=CONTINUITY_POLICY_ID,
        persistence_backend=spec.persistence_backend,
        observation_mode=spec.observation_mode,
        execution_authority=spec.execution_authority,
        campaign_configuration_fingerprint="pending",
        metadata={"build26_spec_ref": BUILD26_QUALIFICATION_SPEC_ID},
    )
    fingerprint = derive_configuration_fingerprint(pending)
    return replace(pending, campaign_configuration_fingerprint=fingerprint)


def configuration_snapshot_to_dict(snapshot: CampaignConfigurationSnapshotV1) -> dict[str, Any]:
    return {
        "campaign_id": snapshot.campaign_id,
        "policy_id": snapshot.policy_id,
        "source_sha": snapshot.source_sha,
        "provider_id": snapshot.provider_id,
        "provider_config_id": snapshot.provider_config_id,
        "universe_definition": list(snapshot.universe_definition),
        "candidate_selection_id": snapshot.candidate_selection_id,
        "predictor_id": snapshot.predictor_id,
        "settlement_policy_id": snapshot.settlement_policy_id,
        "quality_policy_id": snapshot.quality_policy_id,
        "market_calendar_id": snapshot.market_calendar_id,
        "continuity_policy_id": snapshot.continuity_policy_id,
        "persistence_backend": snapshot.persistence_backend,
        "observation_mode": snapshot.observation_mode,
        "execution_authority": snapshot.execution_authority,
        "campaign_configuration_fingerprint": snapshot.campaign_configuration_fingerprint,
        "metadata": dict(snapshot.metadata),
    }


def configuration_snapshot_from_dict(payload: dict[str, Any]) -> CampaignConfigurationSnapshotV1:
    return CampaignConfigurationSnapshotV1(
        campaign_id=str(payload["campaign_id"]),
        policy_id=str(payload["policy_id"]),
        source_sha=str(payload["source_sha"]),
        provider_id=str(payload["provider_id"]),
        provider_config_id=str(payload["provider_config_id"]),
        universe_definition=tuple(str(x) for x in payload["universe_definition"]),
        candidate_selection_id=str(payload["candidate_selection_id"]),
        predictor_id=str(payload["predictor_id"]),
        settlement_policy_id=str(payload["settlement_policy_id"]),
        quality_policy_id=str(payload["quality_policy_id"]),
        market_calendar_id=str(payload["market_calendar_id"]),
        continuity_policy_id=str(payload["continuity_policy_id"]),
        persistence_backend=str(payload["persistence_backend"]),
        observation_mode=str(payload["observation_mode"]),
        execution_authority=str(payload["execution_authority"]),
        campaign_configuration_fingerprint=str(payload["campaign_configuration_fingerprint"]),
        metadata=dict(payload.get("metadata") or {}),
    )


def is_semantic_config_compatible(
    frozen: CampaignConfigurationSnapshotV1,
    current: CampaignConfigurationSnapshotV1,
) -> tuple[bool, tuple[str, ...]]:
    blockers: list[str] = []
    if frozen.policy_id != current.policy_id:
        blockers.append("policy_id changed")
    if frozen.provider_id != current.provider_id:
        blockers.append("provider_id changed")
    if frozen.universe_definition != current.universe_definition:
        blockers.append("universe_definition changed")
    if frozen.predictor_id != current.predictor_id:
        blockers.append("predictor_id changed")
    if frozen.settlement_policy_id != current.settlement_policy_id:
        blockers.append("settlement_policy_id changed")
    if frozen.quality_policy_id != current.quality_policy_id:
        blockers.append("quality_policy_id changed")
    if frozen.execution_authority != current.execution_authority:
        blockers.append("execution_authority changed")
    if frozen.observation_mode != current.observation_mode:
        blockers.append("observation_mode changed")
    return len(blockers) == 0, tuple(blockers)


def is_source_sha_compatible(
    frozen_sha: str,
    current_sha: str,
    *,
    frozen_fingerprint: str,
    current_fingerprint: str,
) -> tuple[bool, str | None]:
    if frozen_sha == current_sha:
        return True, None
    if frozen_fingerprint == current_fingerprint:
        return True, "non_semantic_source_change"
    return False, "semantic_source_change"

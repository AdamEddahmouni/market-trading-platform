"""Campaign preflight checks for EVIDENCE-01B."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from market_platform_foundation.git_ref import read_git_head

from ..evidence01a.service import CampaignService, _assert_execution_disabled
from ..evidence01a.store import CampaignStore
from ..evidence01a.types import CampaignEvidenceOrigin, ForwardObservationCampaignState
from .config import (
    build_configuration_snapshot,
    configuration_snapshot_to_dict,
    is_semantic_config_compatible,
    is_source_sha_compatible,
)
from .types import PreflightDisposition


@dataclass(frozen=True)
class PreflightResultV1:
    disposition: PreflightDisposition
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    source_sha: str
    configuration_fingerprint: str
    metadata: dict[str, Any]


def run_preflight(
    campaign_dir: Path,
    *,
    check_provider_connectivity: bool = False,
    now_ns: int | None = None,
) -> PreflightResultV1:
    blockers: list[str] = []
    warnings: list[str] = []
    store = CampaignStore(campaign_dir)
    spec = store.read_spec()
    _assert_execution_disabled(spec)

    source_sha = read_git_head() or "unknown"
    config = build_configuration_snapshot(spec)
    fingerprint = config.campaign_configuration_fingerprint

    if spec.evidence_origin == CampaignEvidenceOrigin.LIVE_FORWARD:
        if spec.evidence_origin not in {CampaignEvidenceOrigin.LIVE_FORWARD}:
            blockers.append("evidence origin must be LIVE_FORWARD for qualification")
    elif spec.evidence_origin in {CampaignEvidenceOrigin.FIXTURE, CampaignEvidenceOrigin.REPLAY}:
        warnings.append(f"evidence origin {spec.evidence_origin.value} excluded from qualification cohort")

    frozen_path = store.root / "CONFIGURATION_SNAPSHOT.json"
    if frozen_path.exists():
        import json

        from .config import configuration_snapshot_from_dict

        frozen = configuration_snapshot_from_dict(json.loads(frozen_path.read_text(encoding="utf-8")))
        compatible, reasons = is_semantic_config_compatible(frozen, config)
        if not compatible:
            blockers.extend(reasons)
        sha_ok, sha_reason = is_source_sha_compatible(
            frozen.source_sha,
            source_sha,
            frozen_fingerprint=frozen.campaign_configuration_fingerprint,
            current_fingerprint=fingerprint,
        )
        if not sha_ok:
            blockers.append(sha_reason or "source_sha incompatible")
        elif sha_reason:
            warnings.append(sha_reason)
    else:
        frozen_path.write_text(
            __import__("json").dumps(configuration_snapshot_to_dict(config), indent=2),
            encoding="utf-8",
        )

    state = store.read_runtime_state()
    if state.campaign_state == ForwardObservationCampaignState.INVALIDATED:
        blockers.append("campaign is invalidated")

    if not spec.instrument_universe:
        blockers.append("instrument universe is empty")

    try:
        store.write_runtime_state(state)
    except OSError as exc:
        blockers.append(f"persistence not writable: {exc}")

    if check_provider_connectivity and spec.provider_id == "MOOMOO":
        try:
            from market_platform_foundation.market_data.connectivity import opend_reachable
            from market_platform_foundation.market_data.live_config import moomoo_host, moomoo_port

            if not opend_reachable(host=moomoo_host(), port=moomoo_port()):
                blockers.append("MOOMOO OpenD not reachable")
        except ImportError:
            warnings.append("provider connectivity check unavailable")

    if spec.execution_authority != "BLOCKED":
        blockers.append("execution authority must be BLOCKED")

    disposition: PreflightDisposition
    if blockers:
        disposition = PreflightDisposition.NOT_READY
    elif warnings:
        disposition = PreflightDisposition.READY_WITH_LIMITATIONS
    else:
        disposition = PreflightDisposition.READY

    return PreflightResultV1(
        disposition=disposition,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        source_sha=source_sha,
        configuration_fingerprint=fingerprint,
        metadata={"checked_at_ns": now_ns or time.time_ns()},
    )

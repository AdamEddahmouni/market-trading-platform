"""EVIDENCE-01B campaign runtime service — extends EVIDENCE-01A."""

from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path

from market_platform_foundation.git_ref import read_git_head

from ..evidence01a.service import CampaignService
from ..evidence01a.types import CampaignEvidenceOrigin, ForwardObservationCampaignState
from .config import build_configuration_snapshot
from .health import format_health_status
from .preflight import PreflightResultV1, run_preflight
from .runtime import CampaignRuntime
from .store import CampaignRuntimeStore
from .types import ShakedownStatus


class CampaignRuntimeService:
    """Thin service layer over CampaignRuntime for operator CLI."""

    def __init__(self, runtime: CampaignRuntime) -> None:
        self.runtime = runtime
        self.store = runtime.store
        self.service = runtime.service

    @classmethod
    def open(cls, campaign_dir: Path) -> CampaignRuntimeService:
        return cls(CampaignRuntime.open(campaign_dir))

    @classmethod
    def create_campaign(
        cls,
        *,
        campaign_root: Path,
        campaign_name: str,
        provider_id: str = "MOOMOO",
        evidence_origin: CampaignEvidenceOrigin = CampaignEvidenceOrigin.LIVE_FORWARD,
        source_commit_sha: str | None = None,
    ) -> CampaignRuntimeService:
        service = CampaignService.create_campaign(
            campaign_root=campaign_root,
            campaign_name=campaign_name,
            provider_id=provider_id,
            evidence_origin=evidence_origin,
            source_commit_sha=source_commit_sha,
        )
        store = CampaignRuntimeStore(service.store.root)
        config = build_configuration_snapshot(store.read_spec())
        store.write_configuration_snapshot(config)
        runtime = CampaignRuntime(service=service, store=store)
        return cls(runtime)

    def preflight(self, *, check_provider: bool = False) -> PreflightResultV1:
        return run_preflight(self.store.root, check_provider_connectivity=check_provider)

    def start(self) -> None:
        result = self.preflight()
        if result.disposition.value == "NOT_READY":
            raise ValueError(f"preflight failed: {result.blockers}")
        self.runtime.recover()
        self.runtime.start_runtime()

    def pause(self, *, reason: str = "operator_pause") -> None:
        self.runtime.pause(reason=reason)

    def resume(self) -> None:
        self.runtime.resume()

    def stop(self) -> None:
        self.runtime.stop_runtime()
        self.runtime.run_checkpoint_cycle(force=True)

    def status(self) -> str:
        now = time.time_ns()
        spec = self.store.read_spec()
        config = self.store.read_configuration_snapshot()
        health = self.runtime.assess_health(now_ns=now)
        checkpoint = self.service.generate_checkpoint(
            observation_cutoff_ns=now,
            settlement_cutoff_ns=now,
        )
        heartbeat = self.store.read_heartbeat()
        state = self.store.read_runtime_state()
        active = self.service._active_session
        return format_health_status(
            campaign_id=spec.campaign_id,
            campaign_state=state.campaign_state.value,
            health=health,
            config_fingerprint=config.campaign_configuration_fingerprint if config else "unknown",
            source_sha=read_git_head() or spec.source_commit_sha,
            policy_id=spec.policy_id,
            provider_id=spec.provider_id,
            session_id=active.session.session_id if active else state.active_session_id,
            metrics=self.store.read_metrics().to_dict(),
            progress=checkpoint.progress,
            disposition=checkpoint.qualification_disposition,
            remaining=checkpoint.remaining_requirements,
            heartbeat=heartbeat,
        )

    def health(self) -> dict:
        health = self.runtime.assess_health()
        return {
            "health_state": health.health_state.value,
            "severity": health.severity.value,
            "diagnostics": list(health.diagnostics),
            "provider_state": health.provider_state,
            "settlement_backlog": health.settlement_backlog,
            "qualifying_continuity_gap_ns": health.qualifying_continuity_gap_ns,
        }

    def shakedown_start(self) -> ShakedownStatus:
        return self.runtime.start_shakedown()

    def shakedown_status(self) -> ShakedownStatus:
        return self.store.read_shakedown_status()

    def invalidate(self, *, reason: str) -> None:
        self.runtime.invalidate(reason=reason)

    def settle(self) -> int:
        return self.runtime.run_settlement_cycle()

    def checkpoint(self) -> str:
        self.runtime.run_checkpoint_cycle(force=True)
        state = self.store.read_runtime_state()
        return state.last_checkpoint_id or "none"

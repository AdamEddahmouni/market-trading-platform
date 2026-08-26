"""EVIDENCE-01A forward observation campaign service."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from market_platform_foundation.git_ref import read_git_head

from ...contracts.forecast import ForecastV1
from ...contracts.prediction_ledger import PredictionLedgerEntryV1
from ...outcomes.service import OutcomeSettlementService, PredictionLedgerService
from ...outcomes.types import SettlementMode
from ...persistence.repository import IntelligenceRepository
from ..evidence01 import assess_forward_evidence_qualification, ForwardEvidenceDisposition
from ..evidence01.policy import BUILD26_QUALIFICATION_SPEC_ID
from ..receipt import build_forward_prediction_receipt
from ..types import EvidenceClass
from .identity import (
    derive_campaign_id,
    derive_campaign_report_id,
    derive_checkpoint_id,
    derive_observation_ref_id,
    derive_session_id,
)
from .observations import (
    build_observation_inputs,
    load_campaign_repository,
    origin_qualifies_for_real_evidence,
    persist_forecast,
    persist_ledger_entry,
    persist_outcome,
)
from .progress import build_progress_summary, default_policy, format_progress_text
from .store import CampaignRuntimeState, CampaignStore, CampaignStoreError
from .types import (
    CampaignEvidenceOrigin,
    CampaignObservationRefV1,
    ForwardObservationCampaignCheckpointV1,
    ForwardObservationCampaignReportV1,
    ForwardObservationCampaignSessionV1,
    ForwardObservationCampaignSpecV1,
    ForwardObservationCampaignState,
    FORWARD_OBSERVATION_CAMPAIGN_IMPLEMENTATION_VERSION,
    FORWARD_OBSERVATION_CAMPAIGN_SCHEMA_VERSION,
    MIN_QUALIFYING_ELIGIBLE_PER_SESSION,
    MIN_QUALIFYING_SESSION_DURATION_NS,
    SessionTerminationReason,
)

DEFAULT_INSTRUMENT_UNIVERSE: tuple[str, ...] = (
    "AAPL",
    "NVDA",
    "MSFT",
    "AMD",
    "TSLA",
    "SPY",
    "QQQ",
)


class CampaignConfigurationError(ValueError):
    pass


@dataclass
class ActiveSessionState:
    session: ForwardObservationCampaignSessionV1
    prediction_count: int = 0
    eligible_prediction_count: int = 0
    quality_exclusions: dict[str, int] | None = None
    last_decision_time_ns: int | None = None
    reconnect_count: int = 0
    runtime_errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.quality_exclusions is None:
            self.quality_exclusions = {}
        if self.runtime_errors is None:
            self.runtime_errors = []


@dataclass
class CampaignService:
    store: CampaignStore
    policy: Any
    repository: IntelligenceRepository
    _active_session: ActiveSessionState | None = None

    @classmethod
    def open(cls, campaign_dir: Path) -> CampaignService:
        store = CampaignStore(campaign_dir)
        policy = default_policy()
        repository = load_campaign_repository(store)
        return cls(store=store, policy=policy, repository=repository)

    @classmethod
    def create_campaign(
        cls,
        *,
        campaign_root: Path,
        campaign_name: str,
        provider_id: str = "MOOMOO",
        instrument_universe: tuple[str, ...] = DEFAULT_INSTRUMENT_UNIVERSE,
        evidence_origin: CampaignEvidenceOrigin = CampaignEvidenceOrigin.LIVE_FORWARD,
        source_commit_sha: str | None = None,
    ) -> CampaignService:
        if evidence_origin != CampaignEvidenceOrigin.LIVE_FORWARD:
            pass
        source_sha = source_commit_sha or read_git_head() or "unknown"
        pending = ForwardObservationCampaignSpecV1(
            campaign_id="pending",
            schema_version=FORWARD_OBSERVATION_CAMPAIGN_SCHEMA_VERSION,
            campaign_name=campaign_name,
            policy_id=default_policy().policy_id,
            source_commit_sha=source_sha,
            runtime_version=FORWARD_OBSERVATION_CAMPAIGN_IMPLEMENTATION_VERSION,
            provider_id=provider_id,
            instrument_universe=instrument_universe,
            observation_mode="OBSERVATIONAL_ONLY",
            evidence_origin=evidence_origin,
            execution_mode="NONE",
            execution_authority="BLOCKED",
            persistence_backend="campaign_jsonl",
            checkpoint_cadence="session_close_or_operator",
            settlement_cadence="operator_or_maturity",
            implementation_version=FORWARD_OBSERVATION_CAMPAIGN_IMPLEMENTATION_VERSION,
            metadata={"build26_spec_ref": BUILD26_QUALIFICATION_SPEC_ID},
        )
        campaign_id = derive_campaign_id(pending)
        spec = replace(pending, campaign_id=campaign_id)
        _assert_execution_disabled(spec)
        campaign_dir = campaign_root / campaign_id
        store = CampaignStore(campaign_dir)
        store.write_spec(spec)
        store.write_runtime_state(
            CampaignRuntimeState(
                campaign_id=campaign_id,
                campaign_state=ForwardObservationCampaignState.PLANNED,
            )
        )
        return cls(store=store, policy=default_policy(), repository=load_campaign_repository(store))

    def start_campaign(self) -> CampaignRuntimeState:
        spec = self.store.read_spec()
        _assert_execution_disabled(spec)
        state = self.store.read_runtime_state()
        if state.campaign_state not in {
            ForwardObservationCampaignState.PLANNED,
            ForwardObservationCampaignState.PAUSED,
            ForwardObservationCampaignState.EVIDENCE_INSUFFICIENT,
        }:
            raise CampaignStoreError(f"cannot start campaign from state {state.campaign_state.value}")
        state = replace(state, campaign_state=ForwardObservationCampaignState.ACTIVE)
        self.store.write_runtime_state(state)
        return state

    def start_session(self, *, now_ns: int | None = None) -> ForwardObservationCampaignSessionV1:
        spec = self.store.read_spec()
        state = self.store.read_runtime_state()
        if state.campaign_state != ForwardObservationCampaignState.ACTIVE:
            raise CampaignStoreError("campaign must be ACTIVE to start session")
        if state.active_session_id is not None:
            raise CampaignStoreError("session already active")
        started_at_ns = now_ns if now_ns is not None else time.time_ns()
        session_id = derive_session_id(
            campaign_id=spec.campaign_id,
            source_commit_sha=spec.source_commit_sha,
            started_at_ns=started_at_ns,
            session_index=state.session_count + 1,
        )
        session = ForwardObservationCampaignSessionV1(
            session_id=session_id,
            schema_version=FORWARD_OBSERVATION_CAMPAIGN_SCHEMA_VERSION,
            campaign_id=spec.campaign_id,
            source_commit_sha=spec.source_commit_sha,
            policy_id=spec.policy_id,
            started_at_ns=started_at_ns,
            ended_at_ns=None,
            termination_reason=None,
            provider_id=spec.provider_id,
            provider_connected=True,
            instrument_universe=spec.instrument_universe,
            evidence_origin=spec.evidence_origin,
            prediction_count=0,
            eligible_prediction_count=0,
            quality_exclusions={},
            orders_submitted=0,
            reconnect_count=0,
            maximum_continuity_gap_ns=0,
            runtime_errors=(),
            clean_shutdown=False,
        )
        self._active_session = ActiveSessionState(session=session)
        state = replace(
            state,
            active_session_id=session_id,
            session_count=state.session_count + 1,
        )
        self.store.write_runtime_state(state)
        return session

    def record_observation(
        self,
        *,
        forecast: ForecastV1,
        quality_state: str = "GOOD",
        provider_connected: bool = True,
        now_ns: int | None = None,
    ) -> CampaignObservationRefV1:
        spec = self.store.read_spec()
        _assert_execution_disabled(spec)
        if self._active_session is None:
            raise CampaignStoreError("no active session")
        if not provider_connected:
            self._active_session.quality_exclusions["PROVIDER_DISCONNECTED"] = (
                self._active_session.quality_exclusions.get("PROVIDER_DISCONNECTED", 0) + 1
            )
            raise CampaignStoreError("provider disconnected")
        if quality_state not in self.policy.required_quality_states:
            self._active_session.quality_exclusions["QUALITY_INELIGIBLE"] = (
                self._active_session.quality_exclusions.get("QUALITY_INELIGIBLE", 0) + 1
            )
            raise CampaignStoreError(f"quality state {quality_state} ineligible")

        existing_ids = {ref.forecast_id for ref in self.store.list_observation_refs()}
        if forecast.forecast_id in existing_ids:
            raise CampaignStoreError("duplicate prediction forecast_id")

        existing = self.repository.get_forecast(forecast.forecast_id)
        if existing is None:
            self.repository.put_forecast(forecast)
        persist_forecast(self.store, forecast)

        ledger_service = PredictionLedgerService(self.repository)
        decision_ns = forecast.decision_time_ns
        register_result = ledger_service.register_forecast(
            forecast,
            now_ns=now_ns or decision_ns,
            mode=SettlementMode.ACTUAL_LIVE,
            scenario_id=f"EVIDENCE01A:{spec.campaign_id}",
        )
        if not isinstance(register_result, PredictionLedgerEntryV1):
            raise CampaignStoreError(f"ledger registration failed: {register_result}")
        ledger_entry = register_result
        persist_ledger_entry(self.store, ledger_entry)

        evidence_class = (
            EvidenceClass.ACTUAL_FORWARD
            if origin_qualifies_for_real_evidence(spec.evidence_origin)
            else EvidenceClass.REPLAY
        )
        receipt = build_forward_prediction_receipt(
            forecast=forecast,
            ledger_entry=ledger_entry,
            qualification_run_ref=spec.campaign_id,
            recorded_at_ns=now_ns or decision_ns,
            evidence_class=evidence_class,
        )
        ref = CampaignObservationRefV1(
            observation_ref_id=derive_observation_ref_id(
                campaign_id=spec.campaign_id,
                session_id=self._active_session.session.session_id,
                forecast_id=forecast.forecast_id,
                ledger_entry_id=ledger_entry.ledger_entry_id,
            ),
            campaign_id=spec.campaign_id,
            session_id=self._active_session.session.session_id,
            forecast_id=forecast.forecast_id,
            ledger_entry_id=ledger_entry.ledger_entry_id,
            receipt_id=receipt.receipt_id,
            evidence_origin=spec.evidence_origin,
            provider_id=spec.provider_id,
            quality_state=quality_state,
            decision_time_ns=decision_ns,
            source_commit_sha=spec.source_commit_sha,
            policy_id=spec.policy_id,
            metadata={"provider_connected": provider_connected},
        )
        self.store.append_observation_ref(ref)
        self._active_session.prediction_count += 1
        self._active_session.eligible_prediction_count += 1
        if self._active_session.last_decision_time_ns is not None:
            gap = decision_ns - self._active_session.last_decision_time_ns
            current_max = self._active_session.session.maximum_continuity_gap_ns
            self._active_session.session = replace(
                self._active_session.session,
                maximum_continuity_gap_ns=max(current_max, gap),
            )
        self._active_session.last_decision_time_ns = decision_ns
        return ref

    def settle_mature(self, *, now_ns: int | None = None) -> int:
        settlement_service = OutcomeSettlementService(self.repository)
        settled = 0
        cutoff = now_ns if now_ns is not None else time.time_ns()
        for entry in self.repository.query_prediction_ledger_entries(
            decision_start_ns=0,
            decision_end_ns=cutoff,
        ):
            if entry.target_time_ns > cutoff:
                continue
            result = settlement_service.settle(entry, now_ns=cutoff)
            if result.outcome is not None:
                persist_outcome(self.store, result.outcome)
                settled += 1
        return settled

    def stop_session(
        self,
        *,
        reason: SessionTerminationReason = SessionTerminationReason.OPERATOR_STOP,
        now_ns: int | None = None,
    ) -> ForwardObservationCampaignSessionV1:
        if self._active_session is None:
            raise CampaignStoreError("no active session")
        ended_at_ns = now_ns if now_ns is not None else time.time_ns()
        session = replace(
            self._active_session.session,
            ended_at_ns=ended_at_ns,
            termination_reason=reason.value,
            prediction_count=self._active_session.prediction_count,
            eligible_prediction_count=self._active_session.eligible_prediction_count,
            quality_exclusions=dict(self._active_session.quality_exclusions or {}),
            runtime_errors=tuple(self._active_session.runtime_errors or ()),
            clean_shutdown=reason
            in {SessionTerminationReason.OPERATOR_STOP, SessionTerminationReason.CLEAN_SHUTDOWN},
            maximum_continuity_gap_ns=self._active_session.session.maximum_continuity_gap_ns,
        )
        self.store.write_session(session)
        state = self.store.read_runtime_state()
        state = replace(state, active_session_id=None)
        self.store.write_runtime_state(state)
        self._active_session = None
        return session

    def qualifying_session_count(self) -> int:
        count = 0
        for session in self.store.list_sessions():
            duration = 0
            if session.ended_at_ns is not None:
                duration = session.ended_at_ns - session.started_at_ns
            if (
                session.eligible_prediction_count >= MIN_QUALIFYING_ELIGIBLE_PER_SESSION
                and duration >= MIN_QUALIFYING_SESSION_DURATION_NS
            ):
                count += 1
        return count

    def generate_checkpoint(
        self,
        *,
        observation_cutoff_ns: int | None = None,
        settlement_cutoff_ns: int | None = None,
    ) -> ForwardObservationCampaignCheckpointV1:
        spec = self.store.read_spec()
        if spec.policy_id != self.policy.policy_id:
            raise CampaignConfigurationError("campaign policy mismatch")
        obs_cutoff = observation_cutoff_ns if observation_cutoff_ns is not None else time.time_ns()
        settle_cutoff = settlement_cutoff_ns if settlement_cutoff_ns is not None else obs_cutoff
        observations = build_observation_inputs(
            store=self.store,
            repository=self.repository,
            require_live_forward=origin_qualifies_for_real_evidence(spec.evidence_origin),
        )
        assessment = assess_forward_evidence_qualification(
            policy=self.policy,
            observations=observations,
            repository=self.repository,
            observation_cutoff_ns=obs_cutoff,
            settlement_cutoff_ns=settle_cutoff,
        )
        state = self.store.read_runtime_state()
        if assessment.qualification_disposition == ForwardEvidenceDisposition.QUALIFIED:
            campaign_state = ForwardObservationCampaignState.QUALIFIED
        elif assessment.qualification_disposition == ForwardEvidenceDisposition.INSUFFICIENT_FORWARD_EVIDENCE:
            campaign_state = ForwardObservationCampaignState.EVIDENCE_INSUFFICIENT
        else:
            campaign_state = state.campaign_state
        progress = build_progress_summary(
            policy=self.policy,
            observation_summary=assessment.observation_summary,
            campaign_state=campaign_state,
            qualifying_session_count=self.qualifying_session_count(),
        )
        checkpoint_id = derive_checkpoint_id(
            campaign_id=spec.campaign_id,
            policy_id=spec.policy_id,
            observation_cutoff_ns=obs_cutoff,
            settlement_cutoff_ns=settle_cutoff,
            assessment_id=assessment.assessment_id,
        )
        checkpoint = ForwardObservationCampaignCheckpointV1(
            checkpoint_id=checkpoint_id,
            schema_version=FORWARD_OBSERVATION_CAMPAIGN_SCHEMA_VERSION,
            campaign_id=spec.campaign_id,
            policy_id=spec.policy_id,
            assessment_id=assessment.assessment_id,
            observation_cutoff_ns=obs_cutoff,
            settlement_cutoff_ns=settle_cutoff,
            campaign_state=campaign_state,
            qualification_disposition=assessment.qualification_disposition.value,
            remaining_requirements=assessment.remaining_requirements,
            progress=progress,
            metadata={"source_commit_sha": spec.source_commit_sha},
        )
        self.store.append_checkpoint(checkpoint)
        state = replace(
            state,
            checkpoint_count=state.checkpoint_count + 1,
            last_checkpoint_id=checkpoint_id,
            campaign_state=campaign_state,
        )
        self.store.write_runtime_state(state)
        return checkpoint

    def show_progress(
        self,
        *,
        observation_cutoff_ns: int | None = None,
        settlement_cutoff_ns: int | None = None,
    ) -> str:
        checkpoint = self.generate_checkpoint(
            observation_cutoff_ns=observation_cutoff_ns,
            settlement_cutoff_ns=settlement_cutoff_ns,
        )
        return format_progress_text(
            checkpoint.progress,
            disposition=checkpoint.qualification_disposition,
            remaining=checkpoint.remaining_requirements,
        )

    def finalize_campaign(
        self,
        *,
        observation_cutoff_ns: int | None = None,
        settlement_cutoff_ns: int | None = None,
    ) -> ForwardObservationCampaignReportV1:
        checkpoint = self.generate_checkpoint(
            observation_cutoff_ns=observation_cutoff_ns,
            settlement_cutoff_ns=settlement_cutoff_ns,
        )
        limitation_status = (
            "CLOSED"
            if checkpoint.qualification_disposition == ForwardEvidenceDisposition.QUALIFIED.value
            else "STILL_OPEN"
        )
        report_id = derive_campaign_report_id(
            campaign_id=checkpoint.campaign_id,
            policy_id=checkpoint.policy_id,
            final_assessment_id=checkpoint.assessment_id,
            observation_cutoff_ns=checkpoint.observation_cutoff_ns,
            settlement_cutoff_ns=checkpoint.settlement_cutoff_ns,
        )
        report = ForwardObservationCampaignReportV1(
            report_id=report_id,
            schema_version=FORWARD_OBSERVATION_CAMPAIGN_SCHEMA_VERSION,
            campaign_id=checkpoint.campaign_id,
            policy_id=checkpoint.policy_id,
            final_assessment_id=checkpoint.assessment_id,
            campaign_state=checkpoint.campaign_state,
            qualification_disposition=checkpoint.qualification_disposition,
            limitation_status=limitation_status,
            observation_cutoff_ns=checkpoint.observation_cutoff_ns,
            settlement_cutoff_ns=checkpoint.settlement_cutoff_ns,
            progress=checkpoint.progress,
            remaining_requirements=checkpoint.remaining_requirements,
            implementation_version=FORWARD_OBSERVATION_CAMPAIGN_IMPLEMENTATION_VERSION,
        )
        state = self.store.read_runtime_state()
        final_state = (
            ForwardObservationCampaignState.FINALIZED
            if checkpoint.qualification_disposition == ForwardEvidenceDisposition.QUALIFIED.value
            else ForwardObservationCampaignState.EVIDENCE_INSUFFICIENT
        )
        self.store.write_runtime_state(replace(state, campaign_state=final_state))
        summary_path = self.store.root / "CAMPAIGN_SUMMARY.json"
        summary_path.write_text(
            _report_to_dict(report),
            encoding="utf-8",
        )
        return report

    def abort_campaign(self, *, reason: str = "operator_abort") -> CampaignRuntimeState:
        if self._active_session is not None:
            self.stop_session(reason=SessionTerminationReason.ABORT)
        state = self.store.read_runtime_state()
        state = replace(
            state,
            campaign_state=ForwardObservationCampaignState.ABORTED,
            metadata={"abort_reason": reason},
        )
        self.store.write_runtime_state(state)
        return state


def _assert_execution_disabled(spec: ForwardObservationCampaignSpecV1) -> None:
    if spec.execution_mode != "NONE" or spec.execution_authority != "BLOCKED":
        raise CampaignConfigurationError("execution must remain disabled for observation campaigns")


def _report_to_dict(report: ForwardObservationCampaignReportV1) -> str:
    import json

    return json.dumps(
        {
            "report_id": report.report_id,
            "schema_version": report.schema_version,
            "campaign_id": report.campaign_id,
            "policy_id": report.policy_id,
            "final_assessment_id": report.final_assessment_id,
            "campaign_state": report.campaign_state.value,
            "qualification_disposition": report.qualification_disposition,
            "limitation_status": report.limitation_status,
            "observation_cutoff_ns": report.observation_cutoff_ns,
            "settlement_cutoff_ns": report.settlement_cutoff_ns,
            "progress": report.progress,
            "remaining_requirements": list(report.remaining_requirements),
            "implementation_version": report.implementation_version,
            "metadata": dict(report.metadata),
        },
        indent=2,
    )

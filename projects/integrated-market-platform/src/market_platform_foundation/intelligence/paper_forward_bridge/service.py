"""Forward-test orchestration service."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Any

from market_platform_foundation.intelligence.news_strategy_evaluation.contracts import (
    StrategyEvaluationDecision,
)

from .activation import (
    ActivationManifest,
    ActivationManifestError,
    assert_manifest_session_eligible,
    cohort_arm_policy,
    is_derived_campaign_id,
    load_activation_manifest,
    manifest_universe_symbols,
    resolve_campaign_manifest_slug,
)
from .campaign_binding import CampaignBindingError, build_binding_from_activation
from .evaluation import evaluate_forward_test, refresh_evaluability
from .identity import forward_test_decision_id, forward_test_observation_id, forward_test_session_id
from .lifecycle import ForwardTestLifecycleError, assert_transition
from .paper_handoff import build_paper_preview_body, forward_test_correlation_id
from .preflight import assert_forward_test_preflight_ready, run_forward_test_preflight
from .repository import ForwardTestRepository
from .session_policy import (
    SampleFloorDisposition,
    SessionPolicyError,
    assess_sample_floor_disposition,
    assert_cohort_arm_consistency,
    assert_decision_within_calendar,
    assert_evidence_class_fail_closed,
    assert_evaluation_force_allowed,
    assert_execution_phase_gate,
    assert_no_concurrent_overlap,
    calendar_scope_from_manifest,
    evaluation_force_audit_metadata,
    sample_floor_disposition_to_dict,
)
from .temporal import (
    assert_decision_payload_immutable,
    assert_input_observable_at_decision,
    assert_observation_after_decision,
    assert_observation_source_after_decision,
    assert_run_kind_forward,
    assert_source_time_at_or_before_decision,
)
from .types import (
    EvaluationState,
    ForwardTestCohortArm,
    ForwardTestDecision,
    ForwardTestEvidenceClass,
    ForwardTestMode,
    ForwardTestObservation,
    ForwardTestRunKind,
    ForwardTestSession,
    ForwardTestSessionStatus,
    ForwardTestState,
)


class ForwardTestServiceError(ValueError):
    """Forward-test service boundary failure."""


def _require_paper_mode(mode: str) -> None:
    if mode.upper() != "PAPER":
        raise ForwardTestServiceError("FORWARD_TEST_PAPER_MODE_REQUIRED")


def _require_account_match(*, expected: str, actual: str) -> None:
    if expected != actual:
        raise ForwardTestServiceError("FORWARD_TEST_ACCOUNT_MISMATCH")


def _parse_cohort_arm(raw: str) -> ForwardTestCohortArm:
    normalized = raw.strip().upper().replace("-", "_")
    try:
        return ForwardTestCohortArm(normalized)
    except ValueError as exc:
        raise ForwardTestServiceError("FORWARD_TEST_COHORT_ARM_INVALID") from exc


def _parse_evidence_class(raw: str | None) -> ForwardTestEvidenceClass:
    if not raw:
        return ForwardTestEvidenceClass.UNCLASSIFIED
    try:
        return ForwardTestEvidenceClass(str(raw).upper())
    except ValueError as exc:
        raise ForwardTestServiceError("FORWARD_TEST_EVIDENCE_CLASS_INVALID") from exc


def _forbidden_evidence_promotion(evidence_class: ForwardTestEvidenceClass) -> None:
    if evidence_class in {
        ForwardTestEvidenceClass.PAPER_OBSERVED,
        ForwardTestEvidenceClass.ACTUAL_FORWARD,
    }:
        raise ForwardTestServiceError("FORWARD_TEST_EVIDENCE_CLASS_AUTO_PROMOTION_FORBIDDEN")


def _activation_error(exc: ActivationManifestError) -> ForwardTestServiceError:
    return ForwardTestServiceError(str(exc))


def _binding_error(exc: CampaignBindingError) -> ForwardTestServiceError:
    return ForwardTestServiceError(str(exc))


def _policy_error(exc: SessionPolicyError) -> ForwardTestServiceError:
    return ForwardTestServiceError(str(exc))


def _session_manifest_slug(session: ForwardTestSession) -> str | None:
    return resolve_campaign_manifest_slug(
        campaign_id=session.campaign_id,
        config=session.config,
    )


def _load_session_manifest(session: ForwardTestSession) -> ActivationManifest | None:
    slug = _session_manifest_slug(session)
    if not slug:
        return None
    return load_activation_manifest(slug)


def _require_empirical_campaign(session: ForwardTestSession | None) -> None:
    if session is None or not session.campaign_id:
        raise ForwardTestServiceError("FORWARD_TEST_CAMPAIGN_ID_REQUIRED")


def _campaign_provenance(session: ForwardTestSession) -> dict[str, Any]:
    if not session.manifest_fingerprint:
        return {}
    slug = _session_manifest_slug(session)
    campaign_id = session.campaign_id
    if campaign_id and is_derived_campaign_id(campaign_id):
        derived_id = campaign_id
    elif session.manifest_fingerprint:
        derived_id = f"FTCAMP-{session.manifest_fingerprint.lower()}"
    else:
        derived_id = None
    provenance: dict[str, Any] = {
        "campaign_slug": slug or session.campaign_id,
        "protocol_id": session.protocol_id,
        "manifest_fingerprint": session.manifest_fingerprint,
        "campaign_id": derived_id,
    }
    if session.cohort_arm is not None:
        provenance["cohort_arm"] = session.cohort_arm.value
    return provenance


def _require_session_campaign_slug(session: ForwardTestSession) -> str:
    slug = _session_manifest_slug(session)
    if not slug:
        raise ForwardTestServiceError("FORWARD_TEST_CAMPAIGN_SLUG_REQUIRED")
    return slug


def _campaign_required(*, api_path: bool = False) -> bool:
    raw = os.environ.get("IMP_FORWARD_TEST_CAMPAIGN_REQUIRED")
    if raw is not None:
        return raw.strip().lower() not in {"0", "false", "no", "off"}
    return True


def _resolve_campaign_slug(
    *,
    campaign_id: str | None,
    campaign_slug: str | None,
    manifest_path: str | Path | None,
) -> str | None:
    if campaign_slug:
        return str(campaign_slug).strip()
    if campaign_id:
        return str(campaign_id).strip()
    if manifest_path:
        return Path(manifest_path).parent.name
    return None


class ForwardTestService:
    def __init__(self, store: ForwardTestRepository) -> None:
        self._store = store

    def _assert_activation_eligible(
        self,
        *,
        campaign_slug: str,
        account_id: str,
        mode: str,
        cohort_arm: str | None = None,
        manifest_fingerprint: str | None = None,
        campaigns_root_override: Path | None = None,
    ) -> None:
        preflight = run_forward_test_preflight(
            campaign_slug=campaign_slug,
            mode=mode,
            run_kind=ForwardTestRunKind.FORWARD_TEST.value,
            manifest_fingerprint=manifest_fingerprint,
            cohort_arm=cohort_arm,
            campaigns_root_override=campaigns_root_override,
        )
        try:
            assert_forward_test_preflight_ready(preflight)
        except ActivationManifestError as exc:
            raise _activation_error(exc) from exc
        manifest = load_activation_manifest(
            campaign_slug,
            campaigns_root_override=campaigns_root_override,
        )
        try:
            assert_manifest_session_eligible(manifest)
        except ActivationManifestError as exc:
            raise _activation_error(exc) from exc
        paper_account = manifest.paper_account_id
        if paper_account and str(paper_account) != account_id:
            raise ForwardTestServiceError("FORWARD_TEST_ACCOUNT_MANIFEST_MISMATCH")

    def _claim_campaign_binding(
        self,
        *,
        session: ForwardTestSession,
        manifest: ActivationManifest,
        campaign_slug: str,
        campaigns_root_override: Path | None,
        activated_at_ns: int,
    ) -> None:
        try:
            binding = build_binding_from_activation(
                account_id=session.account_id,
                manifest=manifest,
                campaign_slug=campaign_slug,
                forward_test_session_id=session.session_id,
                campaigns_root_override=campaigns_root_override,
                activated_at_ns=activated_at_ns,
            )
            self._store.claim_active_binding(binding)
        except CampaignBindingError as exc:
            raise _binding_error(exc) from exc

    def _record_first_lock(
        self,
        *,
        session: ForwardTestSession,
        locked_at_ns: int,
    ) -> None:
        active = self._store.get_active_binding(account_id=session.account_id)
        if active is None:
            return
        self._store.record_first_lock_at_ns(
            account_id=session.account_id,
            campaign_id=active.campaign_id,
            first_lock_at_ns=locked_at_ns,
        )

    def create_session(
        self,
        *,
        account_id: str,
        mode: str,
        strategy_id: str,
        strategy_version: str,
        universe: tuple[str, ...],
        evaluation_horizon_ns: int,
        created_at_ns: int,
        campaign_id: str | None = None,
        campaign_slug: str | None = None,
        manifest_path: str | Path | None = None,
        cohort_arm: str | None = None,
        manifest_fingerprint: str | None = None,
        campaigns_root_override: Path | None = None,
        config: dict[str, Any] | None = None,
        api_path: bool = False,
    ) -> ForwardTestSession:
        _require_paper_mode(mode)
        normalized_universe = tuple(str(item).upper() for item in universe)
        if not normalized_universe:
            raise ForwardTestServiceError("FORWARD_TEST_UNIVERSE_REQUIRED")

        resolved_slug = _resolve_campaign_slug(
            campaign_id=campaign_id,
            campaign_slug=campaign_slug,
            manifest_path=manifest_path,
        )
        if (campaign_slug or manifest_path) and not campaign_id:
            raise ForwardTestServiceError("FORWARD_TEST_CAMPAIGN_ID_REQUIRED")
        if _campaign_required(api_path=api_path) and not campaign_id:
            raise ForwardTestServiceError("FORWARD_TEST_CAMPAIGN_ID_REQUIRED")

        campaign_binding: dict[str, Any] = {}
        if campaign_id:
            if not cohort_arm:
                raise ForwardTestServiceError("FORWARD_TEST_COHORT_ARM_REQUIRED")
            cohort = _parse_cohort_arm(cohort_arm)
            slug = resolved_slug or campaign_id
            self._assert_activation_eligible(
                campaign_slug=slug,
                account_id=account_id,
                mode=mode,
                cohort_arm=cohort.value,
                manifest_fingerprint=manifest_fingerprint,
                campaigns_root_override=campaigns_root_override,
            )
            preflight = run_forward_test_preflight(
                campaign_slug=slug,
                mode=mode,
                run_kind=ForwardTestRunKind.FORWARD_TEST.value,
                manifest_fingerprint=manifest_fingerprint,
                cohort_arm=cohort.value,
                campaigns_root_override=campaigns_root_override,
            )
            manifest = load_activation_manifest(
                slug,
                campaigns_root_override=campaigns_root_override,
            )
            expected_policy_id, expected_policy_version = cohort_arm_policy(manifest, cohort.value)
            if strategy_id != expected_policy_id or strategy_version != expected_policy_version:
                raise ForwardTestServiceError("FORWARD_TEST_STRATEGY_BINDING_MISMATCH")
            manifest_symbols = manifest_universe_symbols(manifest)
            if set(normalized_universe) - set(manifest_symbols):
                raise ForwardTestServiceError("FORWARD_TEST_UNIVERSE_MANIFEST_MISMATCH")
            manifest_horizon = int(manifest.binding.get("evaluation_horizon_ns") or 0)
            if evaluation_horizon_ns <= 0:
                evaluation_horizon_ns = manifest_horizon
            if evaluation_horizon_ns != manifest_horizon:
                raise ForwardTestServiceError("FORWARD_TEST_HORIZON_MANIFEST_MISMATCH")
            campaign_binding = {
                "campaign_id": campaign_id,
                "protocol_id": preflight.protocol_id,
                "activation_version": preflight.activation_version,
                "manifest_fingerprint": preflight.manifest_fingerprint,
                "cohort_arm": cohort,
                "campaign_slug": slug,
                "manifest": manifest,
            }
        elif evaluation_horizon_ns <= 0:
            raise ForwardTestServiceError("FORWARD_TEST_HORIZON_INVALID")

        session_config = dict(config or {})
        if campaign_binding:
            session_config["campaign_slug"] = campaign_binding["campaign_slug"]

        session = ForwardTestSession(
            session_id=forward_test_session_id(
                account_id=account_id,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                created_at_ns=created_at_ns,
                universe=normalized_universe,
            ),
            account_id=account_id,
            mode=mode.upper(),
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            universe=normalized_universe,
            evaluation_horizon_ns=evaluation_horizon_ns,
            created_at_ns=created_at_ns,
            status=ForwardTestSessionStatus.ACTIVE,
            campaign_id=campaign_binding.get("campaign_id"),
            protocol_id=campaign_binding.get("protocol_id"),
            activation_version=campaign_binding.get("activation_version"),
            manifest_fingerprint=campaign_binding.get("manifest_fingerprint"),
            cohort_arm=campaign_binding.get("cohort_arm"),
            config=session_config,
        )
        if campaign_binding:
            manifest = campaign_binding["manifest"]
            slug = campaign_binding["campaign_slug"]
            try:
                binding = build_binding_from_activation(
                    account_id=account_id,
                    manifest=manifest,
                    campaign_slug=slug,
                    forward_test_session_id=session.session_id,
                    campaigns_root_override=campaigns_root_override,
                    activated_at_ns=created_at_ns,
                )
                self._store.claim_active_binding(binding)
            except CampaignBindingError as exc:
                raise _binding_error(exc) from exc
        self._store.put_session(session)
        return session

    def _refresh_sample_floor_disposition(
        self,
        *,
        session: ForwardTestSession,
        account_id: str,
    ) -> SampleFloorDisposition | None:
        manifest = _load_session_manifest(session)
        if manifest is None:
            return None
        disposition = assess_sample_floor_disposition(
            manifest=manifest,
            decisions=self._store.list_decisions(
                account_id=account_id,
                session_id=session.session_id,
            ),
            session_ids=(session.session_id,),
        )
        updated_config = dict(session.config)
        updated_config["sample_floor_disposition"] = sample_floor_disposition_to_dict(
            disposition
        )
        if updated_config != session.config:
            self._store.put_session(replace(session, config=updated_config))
        return disposition

    def create_decision_from_strategy_evaluation(
        self,
        *,
        account_id: str,
        mode: str,
        session_id: str | None,
        strategy_decision: StrategyEvaluationDecision,
        decision_time_ns: int,
        source_time_ns: int,
        test_mode: ForwardTestMode,
        quantity: int | None = None,
        evaluation_horizon_ns: int | None = None,
        evidence_class: str | None = None,
    ) -> ForwardTestDecision:
        _require_paper_mode(mode)
        if strategy_decision.execution_authority:
            raise ForwardTestServiceError("FORWARD_TEST_STRATEGY_DECISION_EXECUTABLE")
        assert_source_time_at_or_before_decision(
            source_time_ns=source_time_ns,
            decision_time_ns=decision_time_ns,
        )
        evidence = _parse_evidence_class(evidence_class)
        _forbidden_evidence_promotion(evidence)
        assert_evidence_class_fail_closed(evidence, boundary="CREATE")
        session = self._require_bound_session(
            session_id=session_id,
            account_id=account_id,
            strategy_id=strategy_decision.policy_id,
            strategy_version=strategy_decision.policy_version,
            symbol=strategy_decision.instrument_id,
        )
        _require_empirical_campaign(session)
        if session is not None:
            manifest = _load_session_manifest(session)
            if manifest is not None:
                try:
                    scope = calendar_scope_from_manifest(manifest)
                    if scope is not None:
                        assert_decision_within_calendar(
                            decision_time_ns=decision_time_ns,
                            calendar_scope=scope,
                        )
                    assert_no_concurrent_overlap(
                        manifest=manifest,
                        session_id=session.session_id,
                        symbol=strategy_decision.instrument_id,
                        decisions=self._store.list_decisions(
                            account_id=account_id,
                            session_id=session.session_id,
                        ),
                    )
                    assert_execution_phase_gate(
                        test_mode=test_mode,
                        manifest=manifest,
                        session=session,
                        decisions=self._store.list_decisions(
                            account_id=account_id,
                            session_id=session.session_id,
                        ),
                    )
                    assert_cohort_arm_consistency(
                        session=session,
                        decision_cohort_arm=session.cohort_arm.value if session.cohort_arm else None,
                    )
                except SessionPolicyError as exc:
                    raise _policy_error(exc) from exc
        if session is not None:
            horizon = evaluation_horizon_ns or session.evaluation_horizon_ns
        else:
            horizon = evaluation_horizon_ns or 0
        if horizon <= 0:
            raise ForwardTestServiceError("FORWARD_TEST_HORIZON_INVALID")
        direction = strategy_decision.decision.value
        payload = {
            "strategy_evaluation_decision_id": strategy_decision.decision_id,
            "evaluation_run_id": strategy_decision.evaluation_run_id,
            "sample_id": strategy_decision.sample_id,
            "policy_id": strategy_decision.policy_id,
            "policy_version": strategy_decision.policy_version,
            "decision": direction,
            "feature_snapshot_id": strategy_decision.feature_snapshot_id,
            "market_snapshot_ref": strategy_decision.market_snapshot_ref,
        }
        provenance = {
            "schema_version": "intelligence/paper_forward_bridge/provenance/1.0.0",
            "strategy_id": strategy_decision.policy_id,
            "strategy_version": strategy_decision.policy_version,
            "decision_time_ns": decision_time_ns,
            "source_time_ns": source_time_ns,
            "payload_hash_ref": strategy_decision.feature_snapshot_id,
        }
        if session is not None:
            provenance.update(_campaign_provenance(session))
        decision = ForwardTestDecision(
            forward_test_id=forward_test_decision_id(
                account_id=account_id,
                session_id=session_id,
                symbol=strategy_decision.instrument_id,
                decision_time_ns=decision_time_ns,
                strategy_id=strategy_decision.policy_id,
                strategy_version=strategy_decision.policy_version,
                direction=direction,
            ),
            session_id=session_id,
            account_id=account_id,
            mode=mode.upper(),
            run_kind=ForwardTestRunKind.FORWARD_TEST,
            test_mode=test_mode,
            symbol=strategy_decision.instrument_id,
            decision_time_ns=decision_time_ns,
            source_time_ns=source_time_ns,
            state=ForwardTestState.DRAFT,
            direction=direction,
            quantity=quantity,
            confidence=float(strategy_decision.normalized_directional_units),
            strategy_id=strategy_decision.policy_id,
            strategy_version=strategy_decision.policy_version,
            research_artifact_ref=strategy_decision.decision_id,
            evaluation_horizon_ns=horizon,
            decision_payload=payload,
            provenance_snapshot=provenance,
            evidence_class=evidence,
            cohort_arm=session.cohort_arm if session is not None else None,
        )
        self._store.put_decision(decision)
        return decision

    def create_decision(
        self,
        *,
        account_id: str,
        mode: str,
        session_id: str | None,
        symbol: str,
        direction: str,
        decision_time_ns: int,
        source_time_ns: int,
        strategy_id: str,
        strategy_version: str,
        test_mode: ForwardTestMode,
        quantity: int | None = None,
        evaluation_horizon_ns: int | None = None,
        decision_payload: dict[str, Any] | None = None,
        research_artifact_ref: str | None = None,
        run_kind: ForwardTestRunKind = ForwardTestRunKind.FORWARD_TEST,
        evidence_class: str | None = None,
    ) -> ForwardTestDecision:
        _require_paper_mode(mode)
        if run_kind != ForwardTestRunKind.FORWARD_TEST:
            raise ForwardTestServiceError("FORWARD_TEST_BACKTEST_BOUNDARY_VIOLATION")
        assert_source_time_at_or_before_decision(
            source_time_ns=source_time_ns,
            decision_time_ns=decision_time_ns,
        )
        evidence = _parse_evidence_class(evidence_class)
        _forbidden_evidence_promotion(evidence)
        assert_evidence_class_fail_closed(evidence, boundary="CREATE")
        session = self._require_bound_session(
            session_id=session_id,
            account_id=account_id,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            symbol=symbol,
        )
        _require_empirical_campaign(session)
        if session is not None:
            horizon = evaluation_horizon_ns or session.evaluation_horizon_ns
        else:
            horizon = evaluation_horizon_ns or 0
        if horizon <= 0:
            raise ForwardTestServiceError("FORWARD_TEST_HORIZON_INVALID")
        if session is not None:
            manifest = _load_session_manifest(session)
            if manifest is not None:
                try:
                    scope = calendar_scope_from_manifest(manifest)
                    if scope is not None:
                        assert_decision_within_calendar(
                            decision_time_ns=decision_time_ns,
                            calendar_scope=scope,
                        )
                    assert_no_concurrent_overlap(
                        manifest=manifest,
                        session_id=session.session_id,
                        symbol=symbol,
                        decisions=self._store.list_decisions(
                            account_id=account_id,
                            session_id=session.session_id,
                        ),
                    )
                    assert_execution_phase_gate(
                        test_mode=test_mode,
                        manifest=manifest,
                        session=session,
                        decisions=self._store.list_decisions(
                            account_id=account_id,
                            session_id=session.session_id,
                        ),
                    )
                    assert_cohort_arm_consistency(
                        session=session,
                        decision_cohort_arm=session.cohort_arm.value if session.cohort_arm else None,
                    )
                except SessionPolicyError as exc:
                    raise _policy_error(exc) from exc
        payload = dict(decision_payload or {})
        provenance = {
            "schema_version": "intelligence/paper_forward_bridge/provenance/1.0.0",
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "decision_time_ns": decision_time_ns,
            "source_time_ns": source_time_ns,
        }
        if session is not None:
            provenance.update(_campaign_provenance(session))
        decision = ForwardTestDecision(
            forward_test_id=forward_test_decision_id(
                account_id=account_id,
                session_id=session_id,
                symbol=symbol,
                decision_time_ns=decision_time_ns,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                direction=direction,
            ),
            session_id=session_id,
            account_id=account_id,
            mode=mode.upper(),
            run_kind=run_kind,
            test_mode=test_mode,
            symbol=symbol.upper(),
            decision_time_ns=decision_time_ns,
            source_time_ns=source_time_ns,
            state=ForwardTestState.DRAFT,
            direction=direction,
            quantity=quantity,
            confidence=None,
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            research_artifact_ref=research_artifact_ref,
            evaluation_horizon_ns=horizon,
            decision_payload=payload,
            provenance_snapshot=provenance,
            evidence_class=evidence,
            cohort_arm=session.cohort_arm if session is not None else None,
        )
        self._store.put_decision(decision)
        return decision

    def lock_decision(
        self,
        *,
        forward_test_id: str,
        account_id: str,
        locked_at_ns: int,
        decision_payload: dict[str, Any] | None = None,
        campaign_slug: str | None = None,
    ) -> ForwardTestDecision:
        decision = self._require_decision(forward_test_id, account_id)
        _require_account_match(expected=decision.account_id, actual=account_id)
        assert_run_kind_forward(run_kind=decision.run_kind.value)
        bound_session: ForwardTestSession | None = None
        if decision.session_id is not None:
            session = self._store.get_session(decision.session_id)
            if session is None:
                raise ForwardTestServiceError("FORWARD_TEST_SESSION_NOT_FOUND")
            bound_session = session
            _require_account_match(expected=session.account_id, actual=account_id)
            _require_empirical_campaign(session)
            if session.campaign_id:
                self._assert_activation_eligible(
                    campaign_slug=_require_session_campaign_slug(session),
                    account_id=account_id,
                    mode=decision.mode,
                    cohort_arm=session.cohort_arm.value if session.cohort_arm else None,
                    manifest_fingerprint=session.manifest_fingerprint,
                )
        elif campaign_slug:
            self._assert_activation_eligible(
                campaign_slug=campaign_slug,
                account_id=account_id,
                mode=decision.mode,
            )
        else:
            raise ForwardTestServiceError("FORWARD_TEST_CAMPAIGN_ID_REQUIRED")
        if decision_payload is not None:
            assert_decision_payload_immutable(
                original=decision.decision_payload,
                proposed=decision_payload,
            )
        if bound_session is not None:
            manifest = _load_session_manifest(bound_session)
            if manifest is not None:
                try:
                    scope = calendar_scope_from_manifest(manifest)
                    if scope is not None:
                        assert_decision_within_calendar(
                            decision_time_ns=locked_at_ns,
                            calendar_scope=scope,
                        )
                    assert_evidence_class_fail_closed(decision.evidence_class, boundary="LOCK")
                    assert_no_concurrent_overlap(
                        manifest=manifest,
                        session_id=bound_session.session_id,
                        symbol=decision.symbol,
                        decisions=self._store.list_decisions(
                            account_id=account_id,
                            session_id=bound_session.session_id,
                        ),
                        exclude_forward_test_id=decision.forward_test_id,
                    )
                    assert_cohort_arm_consistency(
                        session=bound_session,
                        decision_cohort_arm=(
                            decision.cohort_arm.value if decision.cohort_arm else None
                        ),
                    )
                except SessionPolicyError as exc:
                    raise _policy_error(exc) from exc
        try:
            assert_transition(decision.state, ForwardTestState.LOCKED)
        except ForwardTestLifecycleError as exc:
            raise ForwardTestServiceError(str(exc)) from exc
        locked = replace(
            decision,
            state=ForwardTestState.LOCKED,
            locked_at_ns=locked_at_ns,
            evaluation_state=EvaluationState.PENDING,
        )
        self._store.put_decision(locked)
        if bound_session is not None and bound_session.campaign_id:
            self._record_first_lock(session=bound_session, locked_at_ns=locked_at_ns)
            self._refresh_sample_floor_disposition(
                session=bound_session,
                account_id=account_id,
            )
            refreshed = self._store.get_session(bound_session.session_id) or bound_session
            if not refreshed.config_frozen:
                self._store.put_session(replace(refreshed, config_frozen=True))
        return locked

    def submit_to_paper(
        self,
        *,
        forward_test_id: str,
        account_id: str,
        submitted_at_ns: int,
        paper_order_id: str | None = None,
        paper_intent_id: str | None = None,
        reject_reason: str | None = None,
    ) -> ForwardTestDecision:
        decision = self._require_decision(forward_test_id, account_id)
        session: ForwardTestSession | None = None
        if decision.session_id is not None:
            session = self._store.get_session(decision.session_id)
            _require_empirical_campaign(session)
        if session is not None:
            manifest = _load_session_manifest(session)
            if manifest is not None and decision.test_mode == ForwardTestMode.EXECUTION:
                try:
                    assert_execution_phase_gate(
                        test_mode=decision.test_mode,
                        manifest=manifest,
                        session=session,
                        decisions=self._store.list_decisions(
                            account_id=account_id,
                            session_id=session.session_id,
                        ),
                    )
                except SessionPolicyError as exc:
                    raise _policy_error(exc) from exc
        if decision.state != ForwardTestState.LOCKED:
            raise ForwardTestServiceError("FORWARD_TEST_NOT_LOCKED")
        if not self._store.claim_paper_submission(forward_test_id):
            raise ForwardTestServiceError("FORWARD_TEST_PAPER_ALREADY_SUBMITTED")
        if reject_reason:
            rejected = replace(
                decision,
                state=ForwardTestState.REJECTED,
                submitted_at_ns=submitted_at_ns,
                failure_reason=reject_reason,
            )
            self._store.put_decision(rejected)
            return rejected
        if decision.test_mode == ForwardTestMode.SIGNAL_ONLY:
            observing = replace(
                decision,
                state=ForwardTestState.OBSERVING,
                submitted_at_ns=submitted_at_ns,
                evaluation_state=EvaluationState.OBSERVING,
            )
            self._store.put_decision(observing)
            return observing
        target = ForwardTestState.PAPER_SUBMITTED
        try:
            assert_transition(decision.state, target)
        except ForwardTestLifecycleError as exc:
            raise ForwardTestServiceError(str(exc)) from exc
        submitted = replace(
            decision,
            state=target,
            submitted_at_ns=submitted_at_ns,
            paper_order_id=paper_order_id,
            paper_intent_id=paper_intent_id,
        )
        self._store.put_decision(submitted)
        active = replace(
            submitted,
            state=ForwardTestState.PAPER_ACTIVE,
            evaluation_state=EvaluationState.OBSERVING,
        )
        self._store.put_decision(active)
        observing = replace(
            active,
            state=ForwardTestState.OBSERVING,
            evaluation_state=EvaluationState.OBSERVING,
        )
        self._store.put_decision(observing)
        return observing

    def build_paper_order_request(
        self,
        *,
        forward_test_id: str,
        account_id: str,
        instrument_id: str | None = None,
    ) -> dict[str, Any]:
        decision = self._require_decision(forward_test_id, account_id)
        if decision.state != ForwardTestState.LOCKED:
            raise ForwardTestServiceError("FORWARD_TEST_NOT_LOCKED")
        return build_paper_preview_body(decision, instrument_id=instrument_id)

    def attach_observation(
        self,
        *,
        forward_test_id: str,
        account_id: str,
        observed_at_ns: int,
        source_time_ns: int,
        payload: dict[str, Any],
    ) -> ForwardTestDecision:
        decision = self._require_decision(forward_test_id, account_id)
        if decision.session_id is not None:
            session = self._store.get_session(decision.session_id)
            _require_empirical_campaign(session)
        assert_observation_after_decision(
            observation_time_ns=observed_at_ns,
            decision_time_ns=decision.decision_time_ns,
        )
        assert_observation_source_after_decision(
            source_time_ns=source_time_ns,
            decision_time_ns=decision.decision_time_ns,
        )
        assert_input_observable_at_decision(
            effective_time_ns=source_time_ns,
            decision_time_ns=observed_at_ns,
        )
        observation = ForwardTestObservation(
            observation_id=forward_test_observation_id(
                forward_test_id=forward_test_id,
                observed_at_ns=observed_at_ns,
                source_time_ns=source_time_ns,
            ),
            observed_at_ns=observed_at_ns,
            source_time_ns=source_time_ns,
            payload=dict(payload),
        )
        updated = replace(
            decision,
            observations=decision.observations + (observation,),
        )
        updated = refresh_evaluability(decision=updated, now_ns=observed_at_ns)
        self._store.put_decision(updated)
        return updated

    def evaluate(
        self,
        *,
        forward_test_id: str,
        account_id: str,
        now_ns: int,
        force: bool = False,
    ) -> ForwardTestDecision:
        decision = self._require_decision(forward_test_id, account_id)
        session: ForwardTestSession | None = None
        if decision.session_id is not None:
            session = self._store.get_session(decision.session_id)
            _require_empirical_campaign(session)
        try:
            assert_evaluation_force_allowed(force=force, session=session)
        except SessionPolicyError as exc:
            raise _policy_error(exc) from exc
        decision = refresh_evaluability(decision=decision, now_ns=now_ns)
        if decision.state not in {ForwardTestState.EVALUABLE, ForwardTestState.OBSERVING} and not force:
            raise ForwardTestServiceError("FORWARD_TEST_NOT_EVALUABLE")
        if decision.state == ForwardTestState.EVALUATED:
            return decision
        if not force and not self._store.claim_evaluation(forward_test_id):
            return decision
        try:
            evaluated = evaluate_forward_test(decision=decision, now_ns=now_ns)
        except ValueError:
            self._store.release_evaluation_claim(forward_test_id)
            raise
        self._store.put_decision(evaluated)
        if session is not None and session.campaign_id:
            refreshed = self._store.get_session(session.session_id) or session
            self._refresh_sample_floor_disposition(
                session=refreshed,
                account_id=account_id,
            )
        return evaluated

    def get_decision(self, *, forward_test_id: str, account_id: str) -> ForwardTestDecision:
        return self._require_decision(forward_test_id, account_id)

    def list_decisions(
        self,
        *,
        account_id: str,
        session_id: str | None = None,
    ) -> list[ForwardTestDecision]:
        return self._store.list_decisions(account_id=account_id, session_id=session_id)

    def get_session_summary(self, *, session_id: str, account_id: str) -> dict[str, Any]:
        session = self._store.get_session(session_id)
        if session is None:
            raise ForwardTestServiceError("FORWARD_TEST_SESSION_NOT_FOUND")
        _require_account_match(expected=session.account_id, actual=account_id)
        decisions = self.list_decisions(account_id=account_id, session_id=session_id)
        open_states = {
            ForwardTestState.DRAFT,
            ForwardTestState.LOCKED,
            ForwardTestState.PAPER_SUBMITTED,
            ForwardTestState.PAPER_ACTIVE,
            ForwardTestState.OBSERVING,
        }
        disposition = session.config.get("sample_floor_disposition")
        return {
            "session": session.to_dict(),
            "sample_floor_disposition": disposition,
            "decision_count": len(decisions),
            "open_decisions": sum(1 for item in decisions if item.state in open_states),
            "evaluable_decisions": sum(
                1 for item in decisions if item.state == ForwardTestState.EVALUABLE
            ),
            "completed_decisions": sum(
                1 for item in decisions if item.state == ForwardTestState.EVALUATED
            ),
        }

    def correlation_id(self, forward_test_id: str) -> str:
        return forward_test_correlation_id(forward_test_id)

    def _require_decision(self, forward_test_id: str, account_id: str) -> ForwardTestDecision:
        decision = self._store.get_decision(forward_test_id)
        if decision is None:
            raise ForwardTestServiceError("FORWARD_TEST_NOT_FOUND")
        _require_account_match(expected=decision.account_id, actual=account_id)
        return decision

    def _require_bound_session(
        self,
        *,
        session_id: str | None,
        account_id: str,
        strategy_id: str,
        strategy_version: str,
        symbol: str,
    ) -> ForwardTestSession | None:
        if session_id is None:
            return None
        session = self._store.get_session(session_id)
        if session is None:
            raise ForwardTestServiceError("FORWARD_TEST_SESSION_NOT_FOUND")
        _require_account_match(expected=session.account_id, actual=account_id)
        if session.campaign_id:
            self._assert_activation_eligible(
                campaign_slug=_require_session_campaign_slug(session),
                account_id=account_id,
                mode=session.mode,
                cohort_arm=session.cohort_arm.value if session.cohort_arm else None,
                manifest_fingerprint=session.manifest_fingerprint,
            )
        if session.strategy_id != strategy_id or session.strategy_version != strategy_version:
            raise ForwardTestServiceError("FORWARD_TEST_STRATEGY_BINDING_MISMATCH")
        normalized_symbol = str(symbol).upper()
        universe = {str(item).upper() for item in session.universe}
        if normalized_symbol not in universe:
            raise ForwardTestServiceError("FORWARD_TEST_SYMBOL_UNIVERSE_MISMATCH")
        return session

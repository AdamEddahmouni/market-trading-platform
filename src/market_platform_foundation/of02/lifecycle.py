"""Native and retrospective attribution lifecycle through OF-01 commands only."""

from __future__ import annotations

import time
from typing import Any

from market_platform_foundation.of01.canonical import CAS_LOCATOR_PROFILE, HASH_PROFILE, sha256_upper
from market_platform_foundation.of01.cas import LocalCAS
from market_platform_foundation.of01.commands import (
    AppendAttemptTransition,
    AppendRunTransition,
    AttachArtifact,
    AttachProvenanceReference,
    AttachSourceAttribution,
    CloseRun,
    RecordOutcome,
    RegisterArtifact,
    RegisterAttempt,
    RegisterRun,
)
from market_platform_foundation.of01.records import (
    AcyclicityClass,
    ActorType,
    ArtifactRecord,
    AttemptConcurrency,
    AttemptPhase,
    AttemptRecord,
    AttemptTransitionRecord,
    Completeness,
    DispositionRecord,
    EvidenceStrength,
    OutcomeRecord,
    ProvenanceQualifier,
    ProvenanceReferenceRecord,
    RedactionState,
    ReferenceKind,
    RelationType,
    RelationshipRecord,
    RunRecord,
    RunState,
    RunTransitionRecord,
    SourceAttributionRecord,
    SourceState,
    TerminalResult,
    UseRestriction,
    ValidationState,
)

from .contracts import (
    AttemptSpec,
    AttributionRequest,
    AttributionResult,
    AttributionStatus,
    CompletenessState,
)
from .gateway import LedgerWriter, submit, token_from_cas
from .identity import IdentityPlan, allocate_native
from .policy import apply_failure
from .temporal import of_reference_eligible_at


def _clock() -> int:
    return time.time_ns()


def _completeness(request: AttributionRequest) -> CompletenessState:
    if request.known_missing:
        return CompletenessState.PARTIAL
    if request.provenance_qualifier == ProvenanceQualifier.LEGACY_PARTIAL:
        return CompletenessState.PARTIAL
    return CompletenessState.COMPLETE


def _reason_for_running(attempt_index: int) -> str:
    return "ATTEMPT_RUNNING" if attempt_index == 0 else "ATTEMPT_RETRY_RUNNING"


def attribute(
    request: AttributionRequest,
    *,
    writer: LedgerWriter | None,
    identities: IdentityPlan | None = None,
    cas: LocalCAS | None = None,
    clock: Any = _clock,
    enabled: bool = True,
) -> AttributionResult:
    if not enabled:
        return AttributionResult(
            adapter_id=request.adapter_id,
            status=AttributionStatus.DISABLED,
            provenance_qualifier=request.provenance_qualifier,
            attribution_completeness=_completeness(request),
            known_missing=request.known_missing,
        )
    if writer is None:
        return apply_failure(request, Exception("OF writer is not ready"))
    try:
        return _attribute_enabled(request, writer=writer, identities=identities, cas=cas, clock=clock)
    except Exception as exc:  # noqa: BLE001 — policy maps typed and unexpected failures
        return apply_failure(request, exc)


def _attribute_enabled(
    request: AttributionRequest,
    *,
    writer: LedgerWriter,
    identities: IdentityPlan | None,
    cas: LocalCAS | None,
    clock: Any,
) -> AttributionResult:
    attempts = request.attempts
    if not attempts:
        now_default = int(clock())
        attempts = (
            AttemptSpec(
                sequence=1,
                terminal_result=TerminalResult.COMPLETED,
                reason_code="ATTEMPT_COMPLETED",
                started_at_ns=now_default,
                ended_at_ns=now_default,
            ),
        )
    plan = identities or allocate_native(
        attempt_count=len(attempts),
        capture_artifact=request.artifact is not None,
    )
    now = plan.registered_at_ns
    activate_ns = now + 1
    close_ns = now + 10
    commit_ids: list[str] = []
    existing_any = False

    def _submit(command: Any, command_id: str, tokens: dict | None = None) -> None:
        nonlocal existing_any
        receipt = submit(writer, command, command_id, tokens)
        commit_ids.append(receipt.commit_id)
        existing_any = existing_any or receipt.was_existing

    run = RunRecord(
        run_id=plan.run_id,
        operation_class=request.operation_class,
        objective=request.objective,
        consequence_profile=request.consequence_profile,
        reproducibility_class=request.reproducibility_class,
        evidence_strength=EvidenceStrength.E1_DIAGNOSTIC,
        initiator_class=request.initiator_class,
        initiator_ref=request.initiator_ref,
        trigger_type=request.trigger_type,
        trigger_ref=request.trigger_ref,
        registered_at_ns=now,
        attempt_concurrency=AttemptConcurrency.SEQUENTIAL,
        parallel_capacity=None,
        provenance_qualifier=request.provenance_qualifier,
        retention_class="RET_OPERATIONAL",
        sensitivity_class=request.sensitivity_class,
        evaluation_protocol_ref=None,
        temporal_cutoff_bundle_ref=None,
    )
    register_transition = RunTransitionRecord(
        transition_id=plan.register_transition_id,
        run_id=plan.run_id,
        predecessor_transition_id=None,
        from_state=None,
        to_state=RunState.REGISTERED,
        effective_at_ns=now,
        actor_type=ActorType.SYSTEM,
        actor_ref=request.initiator_ref,
        policy_ref=None,
        reason_code="RUN_REGISTERED",
        terminal_disposition_id=None,
    )
    _submit(RegisterRun(run=run, initial_transition=register_transition), plan.register_run_command_id)
    _submit(
        AppendRunTransition(
            transition=RunTransitionRecord(
                transition_id=plan.activate_transition_id,
                run_id=plan.run_id,
                predecessor_transition_id=plan.register_transition_id,
                from_state=RunState.REGISTERED,
                to_state=RunState.ACTIVE,
                effective_at_ns=activate_ns,
                actor_type=ActorType.SYSTEM,
                actor_ref=request.initiator_ref,
                policy_ref=None,
                reason_code="RUN_ACTIVE",
                terminal_disposition_id=None,
            ),
            expected_predecessor_transition_id=plan.register_transition_id,
        ),
        plan.activate_command_id,
    )

    if request.repository_identity and request.root_identity:
        _submit(
            AttachSourceAttribution(
                source_attribution=SourceAttributionRecord(
                    source_attribution_id=plan.source_attribution_id,
                    run_id=plan.run_id,
                    repository_identity=request.repository_identity,
                    root_identity=request.root_identity,
                    base_revision=request.base_revision,
                    source_state=SourceState.CLEAN_COMMITTED,
                    scope_manifest_artifact_id=None,
                    capsule_artifact_id=None,
                    outside_scope_proof_artifact_id=None,
                    limitations=";".join(request.known_missing) if request.known_missing else None,
                )
            ),
            plan.source_attribution_command_id,
        )

    for identity in request.domain_identities:
        limitations = None
        if request.provenance_qualifier != ProvenanceQualifier.NATIVE:
            limitations = "domain identity is the existing subsystem identity; OF IDs are not substitutes"
        _submit(
            AttachProvenanceReference(
                provenance_reference=ProvenanceReferenceRecord(
                    provenance_ref_id=plan.domain_ref_id if identity is request.domain_identities[0] else plan.domain_ref_id,
                    run_id=plan.run_id,
                    attempt_id=None,
                    reference_kind=ReferenceKind.CONFIGURATION,
                    canonical_identity=f"domain:{identity.system}:{identity.id_type}:{identity.value}",
                    canonical_version=None,
                    canonical_hash=None,
                    available_at_ns=now if request.provenance_qualifier == ProvenanceQualifier.NATIVE else now,
                    coverage_start_ns=request.event_time_ns,
                    coverage_end_ns=request.event_time_ns,
                    artifact_id=None,
                    limitations=limitations,
                )
            ),
            plan.domain_ref_command_id,
        )
        break

    _submit(
        AttachProvenanceReference(
            provenance_reference=ProvenanceReferenceRecord(
                provenance_ref_id=plan.environment_ref_id,
                run_id=plan.run_id,
                attempt_id=None,
                reference_kind=ReferenceKind.ENVIRONMENT,
                canonical_identity="environment:of02",
                canonical_version=None,
                canonical_hash=None,
                available_at_ns=now,
                coverage_start_ns=None,
                coverage_end_ns=None,
                artifact_id=None,
                limitations="attempt.environment_ref is an OF provenance identity, not a filesystem path",
            )
        ),
        plan.environment_ref_command_id,
    )

    predecessor_attempt: str | None = None
    last_attempt_id = plan.attempt_ids[0]
    for index, spec in enumerate(attempts):
        attempt_id = plan.attempt_ids[index]
        last_attempt_id = attempt_id
        started = spec.started_at_ns if spec.started_at_ns is not None else now
        ended = spec.ended_at_ns if spec.ended_at_ns is not None else now
        _submit(
            RegisterAttempt(
                attempt=AttemptRecord(
                    attempt_id=attempt_id,
                    run_id=plan.run_id,
                    attempt_sequence=spec.sequence,
                    invocation_ref=spec.invocation_ref,
                    environment_ref=plan.environment_ref_id,
                    predecessor_attempt_id=predecessor_attempt,
                    checkpoint_ref_id=None,
                    parallel_group=None,
                    expected_start_after_ns=None,
                    expected_end_before_ns=None,
                    retention_class="RET_OPERATIONAL",
                    sensitivity_class=request.sensitivity_class,
                ),
                initial_transition=AttemptTransitionRecord(
                    transition_id=plan.attempt_pending_transition_ids[index],
                    attempt_id=attempt_id,
                    predecessor_transition_id=None,
                    from_phase=None,
                    to_phase=AttemptPhase.PENDING,
                    terminal_result=None,
                    reason_family=None,
                    reason_code="ATTEMPT_PENDING",
                    started_at_ns=None,
                    ended_at_ns=None,
                    actor_type=ActorType.SYSTEM,
                    actor_ref=request.initiator_ref,
                    evidence_ref=None,
                ),
                expected_run_transition_id=plan.activate_transition_id,
            ),
            plan.attempt_register_command_ids[index],
        )
        if spec.terminal_result != TerminalResult.NOT_STARTED:
            _submit(
                AppendAttemptTransition(
                    transition=AttemptTransitionRecord(
                        transition_id=plan.attempt_running_transition_ids[index],
                        attempt_id=attempt_id,
                        predecessor_transition_id=plan.attempt_pending_transition_ids[index],
                        from_phase=AttemptPhase.PENDING,
                        to_phase=AttemptPhase.RUNNING,
                        terminal_result=None,
                        reason_family=None,
                        reason_code=_reason_for_running(index),
                        started_at_ns=started,
                        ended_at_ns=None,
                        actor_type=ActorType.SYSTEM,
                        actor_ref=request.initiator_ref,
                        evidence_ref=None,
                    ),
                    expected_predecessor_transition_id=plan.attempt_pending_transition_ids[index],
                ),
                plan.attempt_running_command_ids[index],
            )
            _submit(
                AppendAttemptTransition(
                    transition=AttemptTransitionRecord(
                        transition_id=plan.attempt_terminal_transition_ids[index],
                        attempt_id=attempt_id,
                        predecessor_transition_id=plan.attempt_running_transition_ids[index],
                        from_phase=AttemptPhase.RUNNING,
                        to_phase=AttemptPhase.TERMINAL,
                        terminal_result=spec.terminal_result,
                        reason_family=spec.reason_family,
                        reason_code=spec.reason_code,
                        started_at_ns=started,
                        ended_at_ns=ended,
                        actor_type=ActorType.SYSTEM,
                        actor_ref=request.initiator_ref,
                        evidence_ref=None,
                    ),
                    expected_predecessor_transition_id=plan.attempt_running_transition_ids[index],
                ),
                plan.attempt_terminal_command_ids[index],
            )
        else:
            _submit(
                AppendAttemptTransition(
                    transition=AttemptTransitionRecord(
                        transition_id=plan.attempt_terminal_transition_ids[index],
                        attempt_id=attempt_id,
                        predecessor_transition_id=plan.attempt_pending_transition_ids[index],
                        from_phase=AttemptPhase.PENDING,
                        to_phase=AttemptPhase.TERMINAL,
                        terminal_result=TerminalResult.NOT_STARTED,
                        reason_family=spec.reason_family,
                        reason_code=spec.reason_code,
                        started_at_ns=None,
                        ended_at_ns=ended,
                        actor_type=ActorType.SYSTEM,
                        actor_ref=request.initiator_ref,
                        evidence_ref=None,
                    ),
                    expected_predecessor_transition_id=plan.attempt_pending_transition_ids[index],
                ),
                plan.attempt_terminal_command_ids[index],
            )
        predecessor_attempt = attempt_id

    artifact_ids: tuple[str, ...] = ()
    result_ref = request.result_ref
    if request.artifact is not None:
        if cas is None:
            content_hash = sha256_upper(request.artifact.payload)
            byte_size = len(request.artifact.payload)
            tokens = None
            # In-memory writers ignore tokens; SQLite writers require CAS.
            try:
                from market_platform_foundation.of01.memory import InMemoryLedger

                memory_writer = isinstance(writer, InMemoryLedger)
            except Exception:  # pragma: no cover
                memory_writer = False
            if not memory_writer:
                raise RuntimeError("artifact capture requires CAS")
        else:
            token = token_from_cas(cas, plan.artifact_id or "", request.artifact.payload)
            content_hash = token.content_hash
            byte_size = token.byte_size
            tokens = {plan.artifact_id: token}  # type: ignore[dict-item]
        assert plan.artifact_id is not None
        last_terminal = attempts[-1].terminal_result
        _submit(
            RegisterArtifact(
                artifact=ArtifactRecord(
                    artifact_id=plan.artifact_id,
                    logical_role=request.artifact.logical_role,
                    logical_name=request.artifact.logical_name,
                    content_hash=content_hash,
                    hash_profile=HASH_PROFILE,
                    byte_size=byte_size,
                    media_type=request.artifact.media_type,
                    content_type=None,
                    producer_run_id=plan.run_id,
                    producer_attempt_id=last_attempt_id,
                    completeness=Completeness.COMPLETE,
                    producer_terminal_result=last_terminal,
                    validation_state=ValidationState.NOT_VALIDATED,
                    use_restriction=UseRestriction.UNRESTRICTED,
                    mutability_class="IMMUTABLE_EVIDENCE",
                    retention_class="RET_OPERATIONAL",
                    sensitivity_class=request.sensitivity_class,
                    cas_locator_profile=CAS_LOCATOR_PROFILE,
                    redaction_state=RedactionState.NOT_APPLICABLE,
                )
            ),
            plan.artifact_command_id or "",
            tokens,
        )
        _submit(
            AttachArtifact(
                relationship=RelationshipRecord(
                    relationship_id=plan.attach_artifact_relationship_id or plan.artifact_id,
                    source_record_type="ATTEMPT",
                    source_record_id=last_attempt_id,
                    relation_type=RelationType.PRODUCES_ARTIFACT,
                    target_record_type="ARTIFACT",
                    target_record_id=plan.artifact_id,
                    effective_at_ns=now,
                    acyclicity_class=AcyclicityClass.ACYCLIC,
                    relation_code=None,
                )
            ),
            plan.attach_artifact_command_id or "",
        )
        artifact_ids = (plan.artifact_id,)
        result_ref = f"artifact://{plan.artifact_id}"

    evaluated_at = now
    _submit(
        RecordOutcome(
            outcome=OutcomeRecord(
                outcome_id=plan.outcome_id,
                run_id=plan.run_id,
                attempt_id=last_attempt_id,
                outcome_type=request.outcome_type,
                result_ref=result_ref,
                validity=request.validity,
                evaluated_at_ns=evaluated_at,
                effective_at_ns=request.event_time_ns,
                protocol_ref=None,
                supersedes_outcome_id=None,
                limitations=request.outcome_limitations,
                retention_class="RET_OPERATIONAL",
                sensitivity_class=request.sensitivity_class,
            )
        ),
        plan.outcome_command_id,
    )
    _submit(
        CloseRun(
            disposition=DispositionRecord(
                disposition_id=plan.disposition_id,
                run_id=plan.run_id,
                outcome_id=plan.outcome_id,
                decision_at_ns=close_ns,
                authority_type=ActorType.SYSTEM,
                authority_ref=request.initiator_ref or "of02",
                policy_ref=None,
                action_category=request.disposition_action,
                domain_code=request.disposition_domain_code,
                prior_disposition_id=None,
                limitations=None,
                retention_class="RET_OPERATIONAL",
                sensitivity_class=request.sensitivity_class,
            ),
            terminal_transition=RunTransitionRecord(
                transition_id=plan.close_transition_id,
                run_id=plan.run_id,
                predecessor_transition_id=plan.activate_transition_id,
                from_state=RunState.ACTIVE,
                to_state=RunState.CLOSED,
                effective_at_ns=close_ns,
                actor_type=ActorType.SYSTEM,
                actor_ref=request.initiator_ref,
                policy_ref=None,
                reason_code="RUN_CLOSED",
                terminal_disposition_id=plan.disposition_id,
            ),
            expected_run_transition_id=plan.activate_transition_id,
        ),
        plan.close_command_id,
    )
    return AttributionResult(
        adapter_id=request.adapter_id,
        status=AttributionStatus.EXISTING if existing_any else AttributionStatus.COMMITTED,
        provenance_qualifier=request.provenance_qualifier,
        attribution_completeness=_completeness(request),
        run_id=plan.run_id,
        attempt_ids=plan.attempt_ids,
        commit_ids=tuple(commit_ids),
        artifact_ids=artifact_ids,
        outcome_id=plan.outcome_id,
        disposition_id=plan.disposition_id,
        known_missing=request.known_missing,
    )


def of_commit_eligible(*, recorded_at_ns: int, cutoff_ns: int) -> bool:
    return of_reference_eligible_at(recorded_at_ns=recorded_at_ns, cutoff_ns=cutoff_ns)

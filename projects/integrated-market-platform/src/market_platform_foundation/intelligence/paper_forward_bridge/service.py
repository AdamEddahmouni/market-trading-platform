"""Forward-test orchestration service."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from market_platform_foundation.intelligence.news_strategy_evaluation.contracts import (
    StrategyEvaluationDecision,
)

from .evaluation import evaluate_forward_test, refresh_evaluability
from .identity import forward_test_decision_id, forward_test_observation_id, forward_test_session_id
from .lifecycle import ForwardTestLifecycleError, assert_transition
from .paper_handoff import build_paper_preview_body, forward_test_correlation_id
from .store import ForwardTestStore
from .temporal import (
    assert_decision_payload_immutable,
    assert_input_observable_at_decision,
    assert_observation_after_decision,
    assert_run_kind_forward,
    assert_source_time_at_or_before_decision,
)
from .types import (
    EvaluationState,
    ForwardTestDecision,
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


class ForwardTestService:
    def __init__(self, store: ForwardTestStore) -> None:
        self._store = store

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
        config: dict[str, Any] | None = None,
    ) -> ForwardTestSession:
        _require_paper_mode(mode)
        if evaluation_horizon_ns <= 0:
            raise ForwardTestServiceError("FORWARD_TEST_HORIZON_INVALID")
        session = ForwardTestSession(
            session_id=forward_test_session_id(
                account_id=account_id,
                strategy_id=strategy_id,
                strategy_version=strategy_version,
                created_at_ns=created_at_ns,
                universe=universe,
            ),
            account_id=account_id,
            mode=mode.upper(),
            strategy_id=strategy_id,
            strategy_version=strategy_version,
            universe=universe,
            evaluation_horizon_ns=evaluation_horizon_ns,
            created_at_ns=created_at_ns,
            status=ForwardTestSessionStatus.ACTIVE,
            config=dict(config or {}),
        )
        self._store.put_session(session)
        return session

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
    ) -> ForwardTestDecision:
        _require_paper_mode(mode)
        if strategy_decision.execution_authority:
            raise ForwardTestServiceError("FORWARD_TEST_STRATEGY_DECISION_EXECUTABLE")
        assert_source_time_at_or_before_decision(
            source_time_ns=source_time_ns,
            decision_time_ns=decision_time_ns,
        )
        if session_id is not None:
            session = self._store.get_session(session_id)
            if session is None:
                raise ForwardTestServiceError("FORWARD_TEST_SESSION_NOT_FOUND")
            _require_account_match(expected=session.account_id, actual=account_id)
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
    ) -> ForwardTestDecision:
        _require_paper_mode(mode)
        assert_source_time_at_or_before_decision(
            source_time_ns=source_time_ns,
            decision_time_ns=decision_time_ns,
        )
        if session_id is not None:
            session = self._store.get_session(session_id)
            if session is None:
                raise ForwardTestServiceError("FORWARD_TEST_SESSION_NOT_FOUND")
            _require_account_match(expected=session.account_id, actual=account_id)
            horizon = evaluation_horizon_ns or session.evaluation_horizon_ns
        else:
            horizon = evaluation_horizon_ns or 0
        if horizon <= 0:
            raise ForwardTestServiceError("FORWARD_TEST_HORIZON_INVALID")
        payload = dict(decision_payload or {})
        provenance = {
            "schema_version": "intelligence/paper_forward_bridge/provenance/1.0.0",
            "strategy_id": strategy_id,
            "strategy_version": strategy_version,
            "decision_time_ns": decision_time_ns,
            "source_time_ns": source_time_ns,
        }
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
            run_kind=ForwardTestRunKind.FORWARD_TEST,
            test_mode=test_mode,
            symbol=symbol,
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
    ) -> ForwardTestDecision:
        decision = self._require_decision(forward_test_id, account_id)
        _require_account_match(expected=decision.account_id, actual=account_id)
        assert_run_kind_forward(run_kind=decision.run_kind.value)
        if decision_payload is not None:
            assert_decision_payload_immutable(
                original=decision.decision_payload,
                proposed=decision_payload,
            )
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
        assert_observation_after_decision(
            observation_time_ns=observed_at_ns,
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
        return {
            "session": session.to_dict(),
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

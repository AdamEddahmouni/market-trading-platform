"""Foundation tests for execution decision trace recorder and replay."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts.common import ContractReference
from market_platform_foundation.intelligence.execution.types import RiskDecisionKind
from market_platform_foundation.intelligence.opportunity.lifecycle import OperatorLifecycleState
from market_platform_foundation.intelligence.opportunity.types import AssessmentAction
from market_platform_foundation.intelligence.persistence.repository import RepositoryPutResult
from market_platform_foundation.rt01.execution_decision_trace import (
    EligibilityDecisionSnapshot,
    ExecutionDecisionKind,
    ExecutionDecisionTraceDraft,
    InMemoryExecutionDecisionTraceRepository,
    PreviewDecisionSnapshot,
    RuleEvaluationOutcome,
    RuleEvaluationV1,
    materialize_execution_decision_trace,
    replay_from_draft,
    round_trip_execution_decision_trace,
    verify_execution_decision_trace_replay,
)


class ExecutionDecisionTraceFoundationTests(unittest.TestCase):
    def _draft(self, *, kind: ExecutionDecisionKind) -> ExecutionDecisionTraceDraft:
        preview = None
        operator_action = None
        blocker_codes: tuple[str, ...] = ()
        if kind == ExecutionDecisionKind.PREVIEW_ALLOWED:
            preview = PreviewDecisionSnapshot(status="PREVIEW_ALLOWED", preview_id="prev-1")
        if kind == ExecutionDecisionKind.REVALIDATION_REQUIRED:
            preview = PreviewDecisionSnapshot(
                status="REVALIDATION_REQUIRED",
                reason_codes=("PREVIEW_PORTFOLIO_STALE",),
            )
            blocker_codes = ("PREVIEW_PORTFOLIO_STALE",)
        if kind == ExecutionDecisionKind.PAPER_BLOCKED:
            blocker_codes = ("PREVIEW_REQUIRED",)
        if kind == ExecutionDecisionKind.WATCH:
            operator_action = OperatorLifecycleState.WATCHED
        if kind == ExecutionDecisionKind.DISMISS:
            operator_action = OperatorLifecycleState.DISMISSED

        return ExecutionDecisionTraceDraft(
            opportunity_id="opp-lane-j-1",
            decision_time_ns=1_700_000_000_000_000_000,
            mode="PAPER",
            decision_kind=kind,
            eligibility=EligibilityDecisionSnapshot(
                assessment_action=AssessmentAction.EMIT,
                lifecycle_state=OperatorLifecycleState.ELIGIBLE,
                reason_codes=("OPPORTUNITY_EMIT",),
            ),
            risk_decision_kind=RiskDecisionKind.REJECT if kind == ExecutionDecisionKind.PAPER_BLOCKED else None,
            risk_decision_ref=(
                ContractReference(kind="risk_decision", id="risk-1")
                if kind == ExecutionDecisionKind.PAPER_BLOCKED
                else None
            ),
            provider_state={"provider_id": "fixture", "session_state": "CONNECTED"},
            market_data_freshness={"state": "FRESH", "as_of_time_ns": 1_699_999_000_000_000_000},
            preview=preview,
            operator_action=operator_action,
            rule_evaluations=(
                RuleEvaluationV1(
                    rule_id="paper.preview.required",
                    outcome=(
                        RuleEvaluationOutcome.FAIL
                        if kind == ExecutionDecisionKind.PAPER_BLOCKED
                        else RuleEvaluationOutcome.PASS
                    ),
                    reason_codes=blocker_codes or ("PREVIEW_OK",),
                ),
            ),
            blocker_codes=blocker_codes,
            execution_outcome_refs=(
                (ContractReference(kind="order", id="ord-1"),)
                if kind == ExecutionDecisionKind.BROKER_ACCEPTED
                else ()
            ),
            config_version_refs=("paper/preview-policy/1",),
            correlation_id="corr-lane-j-1",
            trace_id="trace-lane-j-1",
            immutable_inputs={
                "opportunity_id": "opp-lane-j-1",
                "mode": "PAPER",
                "preview_policy_version": "paper/preview-policy/1",
            },
        )

    def test_deterministic_identity_and_round_trip(self) -> None:
        draft = self._draft(kind=ExecutionDecisionKind.SURFACE)
        first = materialize_execution_decision_trace(draft)
        second = materialize_execution_decision_trace(draft)
        self.assertEqual(first.decision_trace_id, second.decision_trace_id)
        self.assertTrue(first.decision_trace_id.startswith("EDTR-"))
        restored = round_trip_execution_decision_trace(first)
        self.assertEqual(restored, first)

    def test_replay_verifies_rule_trail(self) -> None:
        draft = self._draft(kind=ExecutionDecisionKind.PAPER_BLOCKED)
        replay = replay_from_draft(draft)
        self.assertTrue(replay.ok)
        record = materialize_execution_decision_trace(draft)
        verification = verify_execution_decision_trace_replay(
            record,
            immutable_inputs=draft.immutable_inputs,
        )
        self.assertTrue(verification.identity_match)
        self.assertTrue(verification.rule_trail_match)

    def test_repository_append_only_and_query(self) -> None:
        repo = InMemoryExecutionDecisionTraceRepository()
        record = materialize_execution_decision_trace(self._draft(kind=ExecutionDecisionKind.WATCH))
        self.assertEqual(repo.put_execution_decision_trace(record), RepositoryPutResult.INSERTED)
        self.assertEqual(repo.put_execution_decision_trace(record), RepositoryPutResult.ALREADY_PRESENT)
        loaded = repo.get_execution_decision_trace(record.decision_trace_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.operator_action, OperatorLifecycleState.WATCHED)
        rows = repo.list_execution_decision_traces_by_opportunity("opp-lane-j-1")
        self.assertEqual(len(rows), 1)

    def test_operator_kind_binding(self) -> None:
        for kind in (
            ExecutionDecisionKind.WATCH,
            ExecutionDecisionKind.DISMISS,
            ExecutionDecisionKind.PREVIEW_ALLOWED,
        ):
            record = materialize_execution_decision_trace(self._draft(kind=kind))
            self.assertIsNotNone(record.operator_action)

    def test_negative_replay_fails_on_tampered_inputs(self) -> None:
        record = materialize_execution_decision_trace(self._draft(kind=ExecutionDecisionKind.SURFACE))
        verification = verify_execution_decision_trace_replay(
            record,
            immutable_inputs={"mode": "LIVE"},
        )
        self.assertFalse(verification.identity_match)


if __name__ == "__main__":
    unittest.main()

"""Deliberation gate and orchestrator tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import ContractKind, ContractReference, ExpertDomain
from market_platform_foundation.intelligence.council import (
    BlindCouncilOrchestrator,
    CouncilPlan,
    CouncilPolicy,
    DeliberationDecision,
    DeliberationGate,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.specialists.models import SpecialistExecutionStatus
from tests.intelligence.council_fixtures import (
    T,
    completed_outcome,
    council_participant,
    put_signals_for_refs,
    synthetic_evidence,
)


def _ref(kind: ContractKind, record_id: str) -> ContractReference:
    return ContractReference(kind=kind.value, id=record_id)


class CouncilDeliberationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryIntelligenceRepository()

    def _orchestrator_with_evidence(self, rows, participants):
        for row in rows:
            put_signals_for_refs(self.repo, row.source_signal_refs, snapshot_id=row.snapshot_id)
            self.repo.put_evidence(row)
        plan = CouncilPlan.create(
            source_snapshot_id="snap-1",
            participants=participants,
            policy=CouncilPolicy(),
            decision_time_ns=T,
        )
        orchestrator = BlindCouncilOrchestrator(plan=plan, repository=self.repo)
        orchestrator.start_blind_phase()
        for participant, evidence in zip(participants, rows, strict=False):
            orchestrator.record_participant_terminal(
                completed_outcome(
                    expert_domain=participant.expert_domain,
                    job_id=participant.job_id,
                    evidence_ids=(evidence.evidence_id,),
                )
            )
        return orchestrator

    def test_single_expert_no_deliberation(self) -> None:
        evidence = synthetic_evidence(
            evidence_id="EVID-1",
            expert_domain=ExpertDomain.MICROSTRUCTURE,
            evidence_kind="SYNTHETIC_CLAIM",
            claim="direction",
            polarity="POSITIVE",
            signal_refs=(_ref(ContractKind.SIGNAL, "SIG-1"),),
        )
        participants = (council_participant(expert_domain=ExpertDomain.MICROSTRUCTURE, job_id="job-a"),)
        orchestrator = self._orchestrator_with_evidence([evidence], participants)
        result = orchestrator.run_to_deliberation_gate()
        self.assertEqual(result.deliberation_decision, DeliberationDecision.INSUFFICIENT_EVIDENCE)

    def test_independent_conflict_triggers_deliberation(self) -> None:
        rows = [
            synthetic_evidence(
                evidence_id="EVID-A",
                expert_domain=ExpertDomain.MICROSTRUCTURE,
                evidence_kind="SYNTHETIC_CLAIM",
                claim="direction",
                polarity="POSITIVE",
                signal_refs=(_ref(ContractKind.SIGNAL, "SIG-A"),),
            ),
            synthetic_evidence(
                evidence_id="EVID-B",
                expert_domain=ExpertDomain.DERIVATIVES,
                evidence_kind="SYNTHETIC_CLAIM",
                claim="direction",
                polarity="NEGATIVE",
                signal_refs=(_ref(ContractKind.SIGNAL, "SIG-B"),),
            ),
        ]
        participants = (
            council_participant(expert_domain=ExpertDomain.MICROSTRUCTURE, job_id="job-a"),
            council_participant(expert_domain=ExpertDomain.DERIVATIVES, job_id="job-b"),
        )
        orchestrator = self._orchestrator_with_evidence(rows, participants)
        result = orchestrator.run_to_deliberation_gate()
        self.assertEqual(result.deliberation_decision, DeliberationDecision.REQUIRED)
        assert orchestrator.deliberation_request is not None
        self.assertEqual(
            set(orchestrator.deliberation_request.conflicting_evidence_refs),
            {"EVID-A", "EVID-B"},
        )

    def test_agreement_no_deliberation(self) -> None:
        rows = [
            synthetic_evidence(
                evidence_id="EVID-A",
                expert_domain=ExpertDomain.MICROSTRUCTURE,
                evidence_kind="SYNTHETIC_CLAIM",
                claim="direction",
                polarity="POSITIVE",
                signal_refs=(_ref(ContractKind.SIGNAL, "SIG-A"),),
            ),
            synthetic_evidence(
                evidence_id="EVID-B",
                expert_domain=ExpertDomain.DERIVATIVES,
                evidence_kind="SYNTHETIC_CLAIM",
                claim="direction",
                polarity="POSITIVE",
                signal_refs=(_ref(ContractKind.SIGNAL, "SIG-B"),),
            ),
        ]
        participants = (
            council_participant(expert_domain=ExpertDomain.MICROSTRUCTURE, job_id="job-a"),
            council_participant(expert_domain=ExpertDomain.DERIVATIVES, job_id="job-b"),
        )
        orchestrator = self._orchestrator_with_evidence(rows, participants)
        result = orchestrator.run_to_deliberation_gate()
        self.assertEqual(result.deliberation_decision, DeliberationDecision.NOT_REQUIRED)

    def test_round_limit_prevents_second_request(self) -> None:
        gate = DeliberationGate(CouncilPolicy(max_deliberation_rounds=1))
        self.assertEqual(gate.policy.max_deliberation_rounds, 1)

    def test_council_result_has_no_winner_fields(self) -> None:
        evidence = synthetic_evidence(
            evidence_id="EVID-1",
            expert_domain=ExpertDomain.MICROSTRUCTURE,
            evidence_kind="SYNTHETIC_CLAIM",
            claim="direction",
            polarity="POSITIVE",
            signal_refs=(_ref(ContractKind.SIGNAL, "SIG-1"),),
        )
        participants = (council_participant(expert_domain=ExpertDomain.MICROSTRUCTURE, job_id="job-a"),)
        orchestrator = self._orchestrator_with_evidence([evidence], participants)
        result = orchestrator.run_to_deliberation_gate()
        for forbidden in ("winner", "final_direction", "consensus_probability"):
            self.assertFalse(hasattr(result, forbidden))

    def test_failed_expert_no_conflict_deliberation(self) -> None:
        evidence = synthetic_evidence(
            evidence_id="EVID-1",
            expert_domain=ExpertDomain.MICROSTRUCTURE,
            evidence_kind="SYNTHETIC_CLAIM",
            claim="direction",
            polarity="POSITIVE",
            signal_refs=(_ref(ContractKind.SIGNAL, "SIG-1"),),
        )
        self.repo.put_evidence(evidence)
        put_signals_for_refs(self.repo, evidence.source_signal_refs, snapshot_id=evidence.snapshot_id)
        participants = (
            council_participant(expert_domain=ExpertDomain.MICROSTRUCTURE, job_id="job-a"),
            council_participant(expert_domain=ExpertDomain.DERIVATIVES, job_id="job-b"),
        )
        plan = CouncilPlan.create(
            source_snapshot_id="snap-1",
            participants=participants,
            policy=CouncilPolicy(),
            decision_time_ns=T,
        )
        orchestrator = BlindCouncilOrchestrator(plan=plan, repository=self.repo)
        orchestrator.start_blind_phase()
        orchestrator.record_participant_terminal(
            completed_outcome(expert_domain=ExpertDomain.MICROSTRUCTURE, job_id="job-a", evidence_ids=("EVID-1",))
        )
        from market_platform_foundation.intelligence.council.models import ParticipantOutcome

        orchestrator.record_participant_terminal(
            ParticipantOutcome(
                expert_domain=ExpertDomain.DERIVATIVES,
                job_id="job-b",
                status=SpecialistExecutionStatus.FAILED,
            )
        )
        result = orchestrator.run_to_deliberation_gate()
        self.assertNotEqual(result.deliberation_decision, DeliberationDecision.REQUIRED)


if __name__ == "__main__":
    unittest.main()

"""Blind barrier and blackboard tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import ContractKind, ExpertDomain
from market_platform_foundation.intelligence.council import (
    BlindCouncilOrchestrator,
    BlindExecutionBarrier,
    CouncilPlan,
    CouncilPolicy,
    ParticipantOutcome,
    publish_blackboard_snapshot,
)
from market_platform_foundation.intelligence.council.errors import BlackboardNotReadyError, CouncilStateError
from market_platform_foundation.intelligence.council.models import BlackboardPhase
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.specialists.models import SpecialistExecutionStatus
from tests.intelligence.council_fixtures import (
    T,
    completed_outcome,
    council_participant,
    synthetic_evidence,
)


class CouncilBarrierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryIntelligenceRepository()
        self.participants = (
            council_participant(expert_domain=ExpertDomain.MICROSTRUCTURE, job_id="job-a"),
            council_participant(expert_domain=ExpertDomain.DERIVATIVES, job_id="job-b"),
        )
        self.plan = CouncilPlan.create(
            source_snapshot_id="snap-1",
            participants=self.participants,
            policy=CouncilPolicy(),
            decision_time_ns=T,
        )
        self.orchestrator = BlindCouncilOrchestrator(plan=self.plan, repository=self.repo)

    def test_blackboard_not_ready_until_all_terminal(self) -> None:
        self.orchestrator.start_blind_phase()
        self.orchestrator.record_participant_terminal(
            completed_outcome(
                expert_domain=ExpertDomain.MICROSTRUCTURE,
                job_id="job-a",
                evidence_ids=(),
            )
        )
        with self.assertRaises(CouncilStateError):
            self.orchestrator.publish_blind_blackboard()

    def test_barrier_tracks_pending(self) -> None:
        barrier = BlindExecutionBarrier(participants=self.participants)
        self.assertEqual(barrier.pending_job_ids(), ("job-a", "job-b"))

    def test_completion_order_does_not_change_blackboard_order(self) -> None:
        evidence_a = synthetic_evidence(
            evidence_id="EVID-A",
            expert_domain=ExpertDomain.MICROSTRUCTURE,
            evidence_kind="SYNTHETIC_CLAIM",
            claim="c1",
            polarity="POSITIVE",
        )
        evidence_b = synthetic_evidence(
            evidence_id="EVID-B",
            expert_domain=ExpertDomain.DERIVATIVES,
            evidence_kind="SYNTHETIC_CLAIM",
            claim="c1",
            polarity="NEGATIVE",
        )
        self.repo.put_evidence(evidence_a)
        self.repo.put_evidence(evidence_b)
        outcomes_cab = (
            completed_outcome(expert_domain=ExpertDomain.DERIVATIVES, job_id="job-b", evidence_ids=("EVID-B",)),
            completed_outcome(expert_domain=ExpertDomain.MICROSTRUCTURE, job_id="job-a", evidence_ids=("EVID-A",)),
        )
        outcomes_abc = (
            completed_outcome(expert_domain=ExpertDomain.MICROSTRUCTURE, job_id="job-a", evidence_ids=("EVID-A",)),
            completed_outcome(expert_domain=ExpertDomain.DERIVATIVES, job_id="job-b", evidence_ids=("EVID-B",)),
        )
        bb1 = publish_blackboard_snapshot(
            council_id=self.plan.council_id,
            source_snapshot_id="snap-1",
            evidence_refs=("EVID-A", "EVID-B"),
            participant_outcomes=outcomes_cab,
            phase=BlackboardPhase.BLIND_PASS,
            revision=1,
            resolved_evidence={"EVID-A": evidence_a, "EVID-B": evidence_b},
        )
        bb2 = publish_blackboard_snapshot(
            council_id=self.plan.council_id,
            source_snapshot_id="snap-1",
            evidence_refs=("EVID-B", "EVID-A"),
            participant_outcomes=outcomes_abc,
            phase=BlackboardPhase.BLIND_PASS,
            revision=1,
            resolved_evidence={"EVID-A": evidence_a, "EVID-B": evidence_b},
        )
        self.assertEqual(bb1.blackboard_id, bb2.blackboard_id)
        self.assertEqual(bb1.evidence_refs, ("EVID-A", "EVID-B"))

    def test_blackboard_immutable_tuple(self) -> None:
        evidence = synthetic_evidence(
            evidence_id="EVID-1",
            expert_domain=ExpertDomain.MICROSTRUCTURE,
            evidence_kind="SYNTHETIC_CLAIM",
            claim="c1",
            polarity="POSITIVE",
        )
        self.repo.put_evidence(evidence)
        outcomes = (completed_outcome(expert_domain=ExpertDomain.MICROSTRUCTURE, job_id="job-a", evidence_ids=("EVID-1",)),)
        bb = publish_blackboard_snapshot(
            council_id=self.plan.council_id,
            source_snapshot_id="snap-1",
            evidence_refs=("EVID-1",),
            participant_outcomes=outcomes,
            phase=BlackboardPhase.BLIND_PASS,
            revision=1,
            resolved_evidence={"EVID-1": evidence},
        )
        refs = list(bb.evidence_refs)
        refs.append("EVID-2")
        self.assertEqual(bb.evidence_refs, ("EVID-1",))

    def test_late_evidence_not_in_published_blackboard(self) -> None:
        evidence = synthetic_evidence(
            evidence_id="EVID-1",
            expert_domain=ExpertDomain.MICROSTRUCTURE,
            evidence_kind="SYNTHETIC_CLAIM",
            claim="c1",
            polarity="POSITIVE",
        )
        self.repo.put_evidence(evidence)
        outcomes = (completed_outcome(expert_domain=ExpertDomain.MICROSTRUCTURE, job_id="job-a", evidence_ids=("EVID-1",)),)
        bb = publish_blackboard_snapshot(
            council_id=self.plan.council_id,
            source_snapshot_id="snap-1",
            evidence_refs=("EVID-1",),
            participant_outcomes=outcomes,
            phase=BlackboardPhase.BLIND_PASS,
            revision=1,
            resolved_evidence={"EVID-1": evidence},
        )
        late = synthetic_evidence(
            evidence_id="EVID-LATE",
            expert_domain=ExpertDomain.MACRO_POLICY,
            evidence_kind="SYNTHETIC_CLAIM",
            claim="late",
            polarity="POSITIVE",
        )
        self.repo.put_evidence(late)
        self.assertNotIn("EVID-LATE", bb.evidence_refs)

    def test_abstained_participant_no_evidence_on_blackboard(self) -> None:
        self.orchestrator.start_blind_phase()
        self.orchestrator.record_participant_terminal(
            ParticipantOutcome(
                expert_domain=ExpertDomain.MICROSTRUCTURE,
                job_id="job-a",
                status=SpecialistExecutionStatus.ABSTAINED,
            )
        )
        self.orchestrator.record_participant_terminal(
            completed_outcome(expert_domain=ExpertDomain.DERIVATIVES, job_id="job-b", evidence_ids=()),
        )
        bb = self.orchestrator.publish_blind_blackboard()
        self.assertEqual(bb.evidence_refs, ())


if __name__ == "__main__":
    unittest.main()

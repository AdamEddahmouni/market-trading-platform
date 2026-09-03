"""Council model and identity tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import ExpertDomain
from market_platform_foundation.intelligence.council import (
    CouncilPlan,
    CouncilPolicy,
    DEFAULT_SPECIALIST_REGISTRY,
    derive_blackboard_id,
    derive_council_id,
)
from market_platform_foundation.intelligence.council.errors import CouncilConfigurationError
from market_platform_foundation.intelligence.council.models import ParticipantOutcome
from market_platform_foundation.intelligence.specialists.models import SpecialistExecutionStatus
from tests.intelligence.council_fixtures import T, council_participant, completed_outcome


class CouncilModelTests(unittest.TestCase):
    def test_council_id_stable_for_same_plan(self) -> None:
        participants = (
            council_participant(expert_domain=ExpertDomain.MICROSTRUCTURE, job_id="job-a"),
            council_participant(expert_domain=ExpertDomain.DERIVATIVES, job_id="job-b"),
        )
        policy = CouncilPolicy()
        plan1 = CouncilPlan.create(
            source_snapshot_id="snap-1",
            participants=participants,
            policy=policy,
            decision_time_ns=T,
        )
        plan2 = CouncilPlan.create(
            source_snapshot_id="snap-1",
            participants=(participants[1], participants[0]),
            policy=policy,
            decision_time_ns=T,
        )
        self.assertEqual(plan1.council_id, plan2.council_id)

    def test_council_id_changes_when_participant_changes(self) -> None:
        policy = CouncilPolicy()
        base = CouncilPlan.create(
            source_snapshot_id="snap-1",
            participants=(council_participant(expert_domain=ExpertDomain.MICROSTRUCTURE, job_id="job-a"),),
            policy=policy,
            decision_time_ns=T,
        )
        changed = CouncilPlan.create(
            source_snapshot_id="snap-1",
            participants=(
                council_participant(expert_domain=ExpertDomain.MICROSTRUCTURE, job_id="job-a"),
                council_participant(expert_domain=ExpertDomain.DERIVATIVES, job_id="job-b"),
            ),
            policy=policy,
            decision_time_ns=T,
        )
        self.assertNotEqual(base.council_id, changed.council_id)

    def test_policy_identity_changes_with_semantics(self) -> None:
        self.assertNotEqual(
            CouncilPolicy(deliberation_enabled=True).policy_identity,
            CouncilPolicy(deliberation_enabled=False).policy_identity,
        )

    def test_frozen_participants_required(self) -> None:
        with self.assertRaises(CouncilConfigurationError):
            CouncilPlan.create(
                source_snapshot_id="snap-1",
                participants=(),
                policy=CouncilPolicy(),
                decision_time_ns=T,
            )

    def test_blackboard_id_stable(self) -> None:
        outcomes = (
            completed_outcome(
                expert_domain=ExpertDomain.MICROSTRUCTURE,
                job_id="job-a",
                evidence_ids=("EVID-1",),
            ),
        )
        bb1 = derive_blackboard_id(
            council_id="COUNCIL-1",
            evidence_ids=("EVID-1",),
            participant_outcomes=outcomes,
            phase="BLIND_PASS",
            revision=1,
        )
        bb2 = derive_blackboard_id(
            council_id="COUNCIL-1",
            evidence_ids=("EVID-1",),
            participant_outcomes=outcomes,
            phase="BLIND_PASS",
            revision=1,
        )
        self.assertEqual(bb1, bb2)

    def test_blackboard_id_changes_when_evidence_changes(self) -> None:
        outcomes = (
            completed_outcome(
                expert_domain=ExpertDomain.MICROSTRUCTURE,
                job_id="job-a",
                evidence_ids=("EVID-1",),
            ),
        )
        bb1 = derive_blackboard_id(
            council_id="COUNCIL-1",
            evidence_ids=("EVID-1",),
            participant_outcomes=outcomes,
            phase="BLIND_PASS",
            revision=1,
        )
        bb2 = derive_blackboard_id(
            council_id="COUNCIL-1",
            evidence_ids=("EVID-2",),
            participant_outcomes=outcomes,
            phase="BLIND_PASS",
            revision=1,
        )
        self.assertNotEqual(bb1, bb2)

    def test_production_registry_only_microstructure(self) -> None:
        self.assertEqual(DEFAULT_SPECIALIST_REGISTRY.domains(), (ExpertDomain.MICROSTRUCTURE,))


if __name__ == "__main__":
    unittest.main()

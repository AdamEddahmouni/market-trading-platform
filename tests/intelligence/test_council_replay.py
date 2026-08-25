"""Council replay parity tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import ContractKind, ContractReference, ExpertDomain
from market_platform_foundation.intelligence.council import BlindCouncilOrchestrator, CouncilPlan, CouncilPolicy
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.council_fixtures import T, completed_outcome, council_participant, put_signals_for_refs, synthetic_evidence


def _ref(kind: ContractKind, record_id: str) -> ContractReference:
    return ContractReference(kind=kind.value, id=record_id)


class CouncilReplayTests(unittest.TestCase):
    def _run_council(self, completion_order: tuple[str, ...]):
        repo = InMemoryIntelligenceRepository()
        rows = {
            "job-a": synthetic_evidence(
                evidence_id="EVID-A",
                expert_domain=ExpertDomain.MICROSTRUCTURE,
                evidence_kind="SYNTHETIC_CLAIM",
                claim="direction",
                polarity="POSITIVE",
                signal_refs=(_ref(ContractKind.SIGNAL, "SIG-A"),),
            ),
            "job-b": synthetic_evidence(
                evidence_id="EVID-B",
                expert_domain=ExpertDomain.DERIVATIVES,
                evidence_kind="SYNTHETIC_CLAIM",
                claim="direction",
                polarity="NEGATIVE",
                signal_refs=(_ref(ContractKind.SIGNAL, "SIG-B"),),
            ),
        }
        for row in rows.values():
            put_signals_for_refs(repo, row.source_signal_refs, snapshot_id=row.snapshot_id)
            repo.put_evidence(row)
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
        orchestrator = BlindCouncilOrchestrator(plan=plan, repository=repo)
        orchestrator.start_blind_phase()
        for job_id in completion_order:
            domain = ExpertDomain.MICROSTRUCTURE if job_id == "job-a" else ExpertDomain.DERIVATIVES
            orchestrator.record_participant_terminal(
                completed_outcome(
                    expert_domain=domain,
                    job_id=job_id,
                    evidence_ids=(rows[job_id].evidence_id,),
                )
            )
        return orchestrator.run_to_deliberation_gate()

    def test_completion_order_independent(self) -> None:
        result_ab = self._run_council(("job-a", "job-b"))
        result_ba = self._run_council(("job-b", "job-a"))
        self.assertEqual(result_ab.council_id, result_ba.council_id)
        self.assertEqual(result_ab.blind_blackboard_id, result_ba.blind_blackboard_id)
        self.assertEqual(result_ab.relation_report_id, result_ba.relation_report_id)
        self.assertEqual(result_ab.deliberation_decision, result_ba.deliberation_decision)


if __name__ == "__main__":
    unittest.main()

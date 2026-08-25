"""Provenance and relation analysis tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.contracts import ContractKind, ContractReference, EvidenceApplicability, EvidenceV1, ExpertDomain, IntelligenceScope, QualityState, QualitySummary
from market_platform_foundation.intelligence.council import (
    BlackboardPhase,
    CouncilPolicy,
    EvidenceProvenanceResolver,
    EvidenceRelationAnalyzer,
    EvidenceRelationType,
    SourceIndependence,
    publish_blackboard_snapshot,
)
from market_platform_foundation.intelligence.council.comparison import DEFAULT_COMPARISON_REGISTRY
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.council_fixtures import completed_outcome, put_signals_for_refs, synthetic_evidence
from tests.intelligence.routing_fixtures import signal, snapshot


def _ref(kind: ContractKind, record_id: str) -> ContractReference:
    return ContractReference(kind=kind.value, id=record_id)


class CouncilProvenanceRelationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryIntelligenceRepository()

    def _analyze(self, evidence_rows):
        for row in evidence_rows:
            put_signals_for_refs(self.repo, row.source_signal_refs, snapshot_id=row.snapshot_id)
            self.repo.put_evidence(row)
        outcomes = tuple(
            completed_outcome(
                expert_domain=ExpertDomain(row.metadata["expert_domain"]),
                job_id=f"job-{index}",
                evidence_ids=(row.evidence_id,),
            )
            for index, row in enumerate(evidence_rows)
        )
        bb = publish_blackboard_snapshot(
            council_id="COUNCIL-TEST",
            source_snapshot_id="snap-1",
            evidence_refs=tuple(row.evidence_id for row in evidence_rows),
            participant_outcomes=outcomes,
            phase=BlackboardPhase.BLIND_PASS,
            revision=1,
            resolved_evidence={row.evidence_id: row for row in evidence_rows},
        )
        analyzer = EvidenceRelationAnalyzer(
            comparison_registry=DEFAULT_COMPARISON_REGISTRY,
            provenance_resolver=EvidenceProvenanceResolver(self.repo),
        )
        return analyzer.analyze(
            blackboard=bb,
            evidence_by_id={row.evidence_id: row for row in evidence_rows},
            policy=CouncilPolicy(),
        )

    def test_false_consensus_same_source(self) -> None:
        shared = _ref(ContractKind.SIGNAL, "SIG-S1")
        rows = [
            synthetic_evidence(
                evidence_id=f"EVID-{index}",
                expert_domain=ExpertDomain.MICROSTRUCTURE if index == 0 else ExpertDomain.DERIVATIVES,
                evidence_kind="SYNTHETIC_CLAIM",
                claim="direction",
                polarity="POSITIVE",
                signal_refs=(shared,),
            )
            for index in range(3)
        ]
        report = self._analyze(rows)
        self.assertEqual(len(report.provenance_groups), 1)
        self.assertEqual(len(report.provenance_groups[0].evidence_ids), 3)
        relation = report.relations[0]
        self.assertEqual(relation.relation_type, EvidenceRelationType.AGREES)
        self.assertEqual(relation.source_independence, SourceIndependence.STRONGLY_CORRELATED)

    def test_partial_overlap_correlated(self) -> None:
        rows = [
            synthetic_evidence(
                evidence_id="EVID-A",
                expert_domain=ExpertDomain.MICROSTRUCTURE,
                evidence_kind="SYNTHETIC_CLAIM",
                claim="direction",
                polarity="POSITIVE",
                signal_refs=(_ref(ContractKind.SIGNAL, "SIG-A"), _ref(ContractKind.SIGNAL, "SIG-B")),
            ),
            synthetic_evidence(
                evidence_id="EVID-B",
                expert_domain=ExpertDomain.DERIVATIVES,
                evidence_kind="SYNTHETIC_CLAIM",
                claim="direction",
                polarity="NEGATIVE",
                signal_refs=(_ref(ContractKind.SIGNAL, "SIG-B"), _ref(ContractKind.SIGNAL, "SIG-C")),
            ),
        ]
        report = self._analyze(rows)
        relation = report.relations[0]
        self.assertEqual(relation.relation_type, EvidenceRelationType.CONFLICTS)
        self.assertEqual(relation.source_independence, SourceIndependence.CORRELATED)

    def test_disjoint_source_independent_conflict(self) -> None:
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
        report = self._analyze(rows)
        relation = report.relations[0]
        self.assertEqual(relation.relation_type, EvidenceRelationType.CONFLICTS)
        self.assertEqual(relation.conflict_subtype, "INDEPENDENT_CONFLICT")

    def test_orthogonal_microstructure_dimensions(self) -> None:
        snap = snapshot("snap-1")
        sig1 = signal(snap, "SIG-OF", "net_signed_share", 0.2)
        sig2 = signal(snap, "SIG-LIQ", "spread_bps", 50.0)
        self.repo.put_snapshot(snap)
        self.repo.put_signal(sig1)
        self.repo.put_signal(sig2)
        order_flow = EvidenceV1(
            evidence_id="EVID-OF",
            schema_version="1",
            snapshot_id="snap-1",
            expert_id="microstructure-specialist",
            scope=IntelligenceScope(instrument_ids=("INST-1",)),
            applicability=EvidenceApplicability.APPLICABLE,
            quality=QualitySummary(state=QualityState.GOOD),
            assessment={
                "evidence_kind": "ORDER_FLOW_TRANSITION",
                "semantic_event": "ORDER_FLOW_REVERSAL",
                "pressure_direction": "BULLISH",
            },
            source_signal_refs=(_ref(ContractKind.SIGNAL, sig1.signal_id),),
            metadata={"expert_domain": ExpertDomain.MICROSTRUCTURE.value},
        )
        liquidity = synthetic_evidence(
            evidence_id="EVID-LIQ",
            expert_domain=ExpertDomain.MICROSTRUCTURE,
            evidence_kind="LIQUIDITY_STRESS",
            claim="liquidity",
            polarity="STRESSED",
            signal_refs=(_ref(ContractKind.SIGNAL, sig2.signal_id),),
        )
        report = self._analyze([order_flow, liquidity])
        relation = report.relations[0]
        self.assertEqual(relation.relation_type, EvidenceRelationType.ORTHOGONAL)

    def test_provenance_signal_to_event_lineage(self) -> None:
        snap = snapshot("snap-prov")
        sig = signal(snap, "SIG-1", "net_signed_share", 0.1)
        self.repo.put_snapshot(snap)
        self.repo.put_signal(sig)
        evidence = synthetic_evidence(
            evidence_id="EVID-1",
            expert_domain=ExpertDomain.MICROSTRUCTURE,
            evidence_kind="SYNTHETIC_CLAIM",
            claim="c",
            polarity="POSITIVE",
            signal_refs=(_ref(ContractKind.SIGNAL, sig.signal_id),),
        )
        resolver = EvidenceProvenanceResolver(self.repo)
        signature = resolver.resolve_terminal_sources(evidence)
        self.assertEqual(signature.terminal_source_ids, (sig.signal_id,))

    def test_relation_input_order_independent(self) -> None:
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
        report1 = self._analyze(rows)
        report2 = self._analyze(list(reversed(rows)))
        self.assertEqual(report1.relations, report2.relations)


if __name__ == "__main__":
    unittest.main()

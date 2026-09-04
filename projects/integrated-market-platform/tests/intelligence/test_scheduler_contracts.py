"""BUILD 10 inference job contract tests."""

from __future__ import annotations

import dataclasses
import unittest

from market_platform_foundation.intelligence.contracts import (
    ComponentLineage,
    ContractKind,
    ContractReference,
    ExpertDomain,
    InferenceJobV1,
    RoutingPriority,
    inference_job_v1_from_dict,
    inference_job_v1_to_dict,
)
from market_platform_foundation.intelligence.scheduling import derive_inference_job_id
from tests.intelligence.scheduling_fixtures import SCHEDULER_T


def sample_job() -> InferenceJobV1:
    return InferenceJobV1(
        job_id="IJOB-test",
        schema_version="1",
        routing_decision_ref=ContractReference(kind=ContractKind.ROUTING_DECISION.value, id="ROUTE-abc"),
        detection_ref=ContractReference(kind=ContractKind.DETECTION.value, id="DET-abc"),
        source_snapshot_ref=ContractReference(kind=ContractKind.SNAPSHOT.value, id="snap-1"),
        expert_domain=ExpertDomain.MICROSTRUCTURE,
        priority=RoutingPriority.HIGH,
        decision_time_ns=SCHEDULER_T,
        submitted_at_ns=SCHEDULER_T,
        deadline_time_ns=SCHEDULER_T + 5_000_000_000,
        expires_at_ns=SCHEDULER_T + 30_000_000_000,
        required_capabilities=("QUOTES", "TRADES"),
        execution_profile_id="microstructure-cpu-v1",
        batch_key="microstructure-specialist-v1",
        residency_key="microstructure-cpu",
        adapter_key=None,
        scheduler_policy_identity="SCHPOL-test",
        scheduler_lineage=ComponentLineage(component_id="inference-scheduler", component_version="1"),
    )


class InferenceJobContractTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        record = sample_job()
        self.assertEqual(inference_job_v1_from_dict(inference_job_v1_to_dict(record)), record)

    def test_job_identity_is_stable(self) -> None:
        first = derive_inference_job_id(
            routing_decision_id="ROUTE-abc",
            scheduler_policy_identity="SCHPOL-test",
            execution_profile_id="microstructure-cpu-v1",
        )
        second = derive_inference_job_id(
            routing_decision_id="ROUTE-abc",
            scheduler_policy_identity="SCHPOL-test",
            execution_profile_id="microstructure-cpu-v1",
        )
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("IJOB-"))

    def test_profile_change_changes_identity(self) -> None:
        base = derive_inference_job_id(
            routing_decision_id="ROUTE-abc",
            scheduler_policy_identity="SCHPOL-test",
            execution_profile_id="microstructure-cpu-v1",
        )
        changed = derive_inference_job_id(
            routing_decision_id="ROUTE-abc",
            scheduler_policy_identity="SCHPOL-test",
            execution_profile_id="derivatives-gpu-v1",
        )
        self.assertNotEqual(base, changed)

    def test_deadline_invariants(self) -> None:
        with self.assertRaisesRegex(ValueError, "JOB_DEADLINE_AFTER_EXPIRATION"):
            dataclasses.replace(sample_job(), deadline_time_ns=SCHEDULER_T + 40_000_000_000)

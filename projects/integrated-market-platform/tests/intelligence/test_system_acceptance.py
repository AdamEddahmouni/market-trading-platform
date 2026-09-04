"""BUILD 25 system acceptance tests."""

from __future__ import annotations

import itertools
import unittest
from unittest import mock

from market_platform_foundation.intelligence.system_acceptance import (
    AUTHORITY_GRAPH,
    BUILD_INVENTORY,
    CONTRACT_INVENTORY,
    FORBIDDEN_AUTHORITY_PATHS,
    LINEAGE_EDGES,
    REQUIRED_INVARIANT_IDS,
    REQUIRED_SCENARIOS,
    AcceptanceDisposition,
    InvariantStatus,
    ScenarioStatus,
    build_acceptance_spec,
    contract_inventory_hash,
    invariant_failures,
    run_acceptance,
    run_golden_lifecycle,
    run_invariant_checks,
    run_scenarios,
    system_acceptance_report_v1_to_dict,
    system_acceptance_spec_v1_to_dict,
)


class ContractInventoryTests(unittest.TestCase):
    def test_contract_inventory_complete(self) -> None:
        self.assertGreaterEqual(len(CONTRACT_INVENTORY), 20)
        for name, meta in CONTRACT_INVENTORY.items():
            self.assertFalse(meta.get("ttl"), f"{name} must not have canonical TTL")
            self.assertIn("authority_build", meta)

    def test_contract_inventory_hash_stable(self) -> None:
        h1 = contract_inventory_hash()
        h2 = contract_inventory_hash()
        self.assertEqual(h1, h2)
        self.assertTrue(h1.startswith("CTRINV-"))

    def test_build_inventory_covers_24(self) -> None:
        builds = {k for k in BUILD_INVENTORY if k <= 24}
        self.assertGreaterEqual(len(builds), 20)

    def test_authority_graph_no_gaps(self) -> None:
        self.assertIn("adaptation", AUTHORITY_GRAPH)
        self.assertIn("promotion", AUTHORITY_GRAPH)

    def test_lineage_edges_use_strong_refs(self) -> None:
        for _src, _dst, ref_field in LINEAGE_EDGES:
            self.assertTrue(ref_field.endswith("_ref") or ref_field.endswith("_refs") or ref_field.endswith("_id"))


class AcceptanceSpecTests(unittest.TestCase):
    def test_spec_identity_deterministic(self) -> None:
        head = "00421583fad7825d5f97ee5541b0cb5cdb0a8584"
        s1 = build_acceptance_spec(source_build_head=head)
        s2 = build_acceptance_spec(source_build_head=head)
        self.assertEqual(s1.acceptance_spec_id, s2.acceptance_spec_id)
        self.assertTrue(s1.acceptance_spec_id.startswith("ACCSPEC-"))

    def test_spec_round_trip(self) -> None:
        spec = build_acceptance_spec(source_build_head="abc123")
        payload = system_acceptance_spec_v1_to_dict(spec)
        self.assertEqual(payload["required_build_range"], [1, 24])
        self.assertIn("A01", payload["required_adversarial_scenarios"])


class InvariantCheckerTests(unittest.TestCase):
    def test_all_required_invariants_checked(self) -> None:
        results = run_invariant_checks()
        self.assertEqual(len(results), len(REQUIRED_INVARIANT_IDS))
        failures = invariant_failures(results)
        self.assertEqual(failures, (), [f.invariant_id for f in failures])

    def test_pit_availability_invariant(self) -> None:
        results = {r.invariant_id: r for r in run_invariant_checks(("pit_availability",))}
        self.assertEqual(results["pit_availability"].status, InvariantStatus.PASS)


class GoldenLifecycleTests(unittest.TestCase):
    def test_golden_lifecycle_completes(self) -> None:
        artifacts, meta = run_golden_lifecycle()
        self.assertIsNotNone(artifacts.research_trigger_id)
        self.assertIsNotNone(artifacts.champion_assignment_id)
        self.assertTrue(meta["governance_opportunities_allowed"])

    def test_golden_lifecycle_reproducible(self) -> None:
        a1, _ = run_golden_lifecycle()
        a2, _ = run_golden_lifecycle()
        self.assertEqual(a1.scientific_id_map(), a2.scientific_id_map())


class AdversarialScenarioTests(unittest.TestCase):
    def test_all_required_scenarios_registered(self) -> None:
        results = run_scenarios()
        by_id = {r.scenario_id: r for r in results}
        for scenario_id in REQUIRED_SCENARIOS:
            self.assertIn(scenario_id, by_id)

    def test_no_scenario_failures(self) -> None:
        failures = [r for r in run_scenarios() if r.status == ScenarioStatus.FAIL]
        self.assertEqual(failures, [], [(f.scenario_id, f.observed) for f in failures])

    def test_future_event_blocked(self) -> None:
        result = next(r for r in run_scenarios(("A05",)) if r.scenario_id == "A05")
        self.assertEqual(result.status, ScenarioStatus.PASS)

    def test_monitoring_does_not_train(self) -> None:
        with mock.patch(
            "market_platform_foundation.intelligence.training.factory.TrainingFactory.generate_candidates"
        ) as generate:
            run_scenarios(("A85",))
            generate.assert_not_called()

    def test_monitoring_does_not_promote(self) -> None:
        with mock.patch(
            "market_platform_foundation.intelligence.promotion.engine.PromotionEngine.evaluate_promotion"
        ) as promote:
            run_scenarios(("A86",))
            promote.assert_not_called()


class DeterminismStressTests(unittest.TestCase):
    def test_input_order_shuffle_candidate_ids(self) -> None:
        from tests.intelligence.promotion_fixtures import validated_candidate_bundle

        ids = []
        for _ in range(3):
            _, _, candidate, _, _, _ = validated_candidate_bundle()
            ids.append(candidate.candidate_id)
        self.assertEqual(len(set(ids)), 1)

    def test_forecast_id_order_independent(self) -> None:
        from tests.intelligence.test_persistence_fixtures import sample_forecast

        refs_a = (
            sample_forecast(probability=0.6, forecast_id="fc-order").source_forecast_refs
            if hasattr(sample_forecast(probability=0.6), "source_forecast_refs")
            else ()
        )
        f1 = sample_forecast(probability=0.6)
        f2 = sample_forecast(probability=0.6)
        self.assertEqual(f1.forecast_id, f2.forecast_id)


class AuthorityBypassTests(unittest.TestCase):
    def test_forbidden_paths_catalogued(self) -> None:
        self.assertGreaterEqual(len(FORBIDDEN_AUTHORITY_PATHS), 8)

    def test_live_execution_forbidden(self) -> None:
        from market_platform_foundation.intelligence.execution.types import ExecutionPolicyV1, SizingPolicyKind
        from market_platform_foundation.intelligence.contracts.common import INTELLIGENCE_SCHEMA_VERSION

        with self.assertRaises(ValueError):
            ExecutionPolicyV1(
                execution_policy_id="live",
                schema_version=INTELLIGENCE_SCHEMA_VERSION,
                mode="LIVE",  # type: ignore[arg-type]
                sizing_policy=SizingPolicyKind.FIXED_FRACTION_NAV_WITH_CAPS,
            )


class SystemAcceptanceRunnerTests(unittest.TestCase):
    def test_acceptance_report_structure(self) -> None:
        report = run_acceptance(
            source_head="00421583fad7825d5f97ee5541b0cb5cdb0a8584",
            candidate_head="00421583fad7825d5f97ee5541b0cb5cdb0a8584",
        )
        payload = system_acceptance_report_v1_to_dict(report)
        self.assertIn("acceptance_report_id", payload)
        self.assertIn(report.overall_disposition, {
            AcceptanceDisposition.ACCEPTED,
            AcceptanceDisposition.ACCEPTED_WITH_LIMITATIONS,
        })
        self.assertEqual(report.blocking_failures, ())


if __name__ == "__main__":
    unittest.main()

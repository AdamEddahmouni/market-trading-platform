"""BUILD 26 forward shadow qualification tests."""

from __future__ import annotations

import unittest
from unittest import mock

from market_platform_foundation.intelligence.forward_qualification import (
    DEFAULT_HORIZON_NS,
    DEFAULT_INSTRUMENT_UNIVERSE,
    EvidenceClass,
    ForwardIntegrityStatus,
    IntegrityFailureCode,
    QualificationDisposition,
    REQUIRED_SCENARIOS,
    ScenarioStatus,
    build_forward_prediction_receipt,
    build_forward_qualification_run,
    build_forward_qualification_spec,
    derive_qualification_spec_id,
    detect_run_freeze_violation,
    forward_qualification_spec_v1_to_dict,
    probe_all_provider_capabilities,
    provider_capability_matrix,
    run_forward_qualification,
    run_prospective_fixture_lifecycle,
    run_scenarios,
    validate_forward_integrity,
    verify_build25_rc_integrity,
)
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from tests.intelligence.outcome_fixtures import T, synthetic_final_forecast
from market_platform_foundation.intelligence.outcomes.ledger import build_prediction_ledger_entry
from market_platform_foundation.intelligence.outcomes.types import SettlementMode


BUILD25_HEAD = "15e7a4f6fc88e5a1c90c6bc3b1b4f8c3a861d2f2"


class ForwardQualificationSpecTests(unittest.TestCase):
    def test_spec_identity_deterministic(self) -> None:
        s1 = build_forward_qualification_spec(
            release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD25_HEAD,
            qualification_start_ns=T,
        )
        s2 = build_forward_qualification_spec(
            release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD25_HEAD,
            qualification_start_ns=T,
        )
        self.assertEqual(s1.qualification_spec_id, s2.qualification_spec_id)
        self.assertTrue(s1.qualification_spec_id.startswith("FQSPEC-"))

    def test_spec_round_trip(self) -> None:
        spec = build_forward_qualification_spec(
            release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD25_HEAD,
            qualification_start_ns=T,
        )
        payload = forward_qualification_spec_v1_to_dict(spec)
        self.assertEqual(payload["target_kind"], "direction_up_down")
        self.assertEqual(payload["horizon_ns"], DEFAULT_HORIZON_NS)
        self.assertEqual(payload["execution_mode_requirement"], "NONE")
        self.assertEqual(payload["execution_authority_requirement"], "BLOCKED")

    def test_universe_change_changes_id(self) -> None:
        base = build_forward_qualification_spec(
            release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD25_HEAD,
            qualification_start_ns=T,
        )
        changed = build_forward_qualification_spec(
            release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD25_HEAD,
            qualification_start_ns=T,
            instrument_universe=("AAPL",),
        )
        self.assertNotEqual(base.qualification_spec_id, changed.qualification_spec_id)

    def test_horizon_change_changes_id(self) -> None:
        base = build_forward_qualification_spec(
            release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD25_HEAD,
            qualification_start_ns=T,
        )
        changed = build_forward_qualification_spec(
            release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD25_HEAD,
            qualification_start_ns=T,
            horizon_ns=DEFAULT_HORIZON_NS * 2,
        )
        self.assertNotEqual(base.qualification_spec_id, changed.qualification_spec_id)

    def test_live_execution_requirement_rejected_in_run(self) -> None:
        spec = build_forward_qualification_spec(
            release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD25_HEAD,
            qualification_start_ns=T,
        )
        with self.assertRaises(ValueError):
            build_forward_qualification_run(
                spec=spec,
                source_head=BUILD25_HEAD,
                run_start_ns=T,
                execution_mode="LIVE",
            )


class ForwardIntegrityTests(unittest.TestCase):
    def test_valid_forward_receipt(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = synthetic_final_forecast(repo)
        entry = build_prediction_ledger_entry(
            forecast,
            repo,
            mode=SettlementMode.ACTUAL_LIVE,
            registered_at_ns=forecast.decision_time_ns,
        )
        receipt = build_forward_prediction_receipt(
            forecast=forecast,
            ledger_entry=entry,
            qualification_run_ref="FQRUN-test",
            recorded_at_ns=forecast.decision_time_ns,
        )
        self.assertEqual(receipt.forward_integrity_status, ForwardIntegrityStatus.VALID)

    def test_replay_masquerading_rejected(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = synthetic_final_forecast(repo)
        entry = build_prediction_ledger_entry(
            forecast,
            repo,
            mode=SettlementMode.ACTUAL_LIVE,
            registered_at_ns=forecast.decision_time_ns,
        )
        status, codes = validate_forward_integrity(
            forecast=forecast,
            ledger_entry=entry,
            evidence_class=EvidenceClass.REPLAY,
        )
        self.assertEqual(status, ForwardIntegrityStatus.INVALID)
        self.assertIn(IntegrityFailureCode.REPLAY_MASQUERADING_AS_FORWARD.value, codes)

    def test_ledger_after_target_rejected(self) -> None:
        repo = InMemoryIntelligenceRepository()
        forecast = synthetic_final_forecast(repo)
        late_ns = forecast.decision_time_ns + forecast.horizon.duration_ns + 1
        entry = build_prediction_ledger_entry(
            forecast,
            repo,
            mode=SettlementMode.ACTUAL_LIVE,
            registered_at_ns=late_ns,
            reject_late_registration=False,
        )
        status, codes = validate_forward_integrity(
            forecast=forecast,
            ledger_entry=entry,
            evidence_class=EvidenceClass.ACTUAL_FORWARD,
        )
        self.assertEqual(status, ForwardIntegrityStatus.INVALID)
        self.assertIn(IntegrityFailureCode.LEDGER_AFTER_TARGET.value, codes)


class RunFreezeTests(unittest.TestCase):
    def test_champion_change_detected(self) -> None:
        violation = detect_run_freeze_violation(
            initial_champion_ref="CHAMP-1",
            current_champion_ref="CHAMP-2",
            initial_policy_ref="POL-1",
            current_policy_ref="POL-1",
            initial_feature_schema_ref="FS-1",
            current_feature_schema_ref="FS-1",
        )
        self.assertEqual(violation, IntegrityFailureCode.CHAMPION_CHANGED_MID_RUN.value)

    def test_policy_change_detected(self) -> None:
        violation = detect_run_freeze_violation(
            initial_champion_ref="CHAMP-1",
            current_champion_ref="CHAMP-1",
            initial_policy_ref="POL-1",
            current_policy_ref="POL-2",
            initial_feature_schema_ref="FS-1",
            current_feature_schema_ref="FS-1",
        )
        self.assertEqual(violation, IntegrityFailureCode.POLICY_CHANGED_MID_RUN.value)


class ProviderCapabilityTests(unittest.TestCase):
    def test_provider_matrix_present(self) -> None:
        matrix = provider_capability_matrix()
        self.assertIn("providers", matrix)
        self.assertGreaterEqual(len(matrix["providers"]), 3)

    def test_internal_fixture_eligible(self) -> None:
        entries = probe_all_provider_capabilities()
        internal = [e for e in entries if e.provider_id == "INTERNAL"]
        self.assertTrue(internal)
        self.assertTrue(internal[0].qualification_eligible)


class ScenarioTests(unittest.TestCase):
    def test_all_required_scenarios_registered(self) -> None:
        results = run_scenarios()
        by_id = {r.scenario_id: r for r in results}
        for scenario_id in REQUIRED_SCENARIOS:
            self.assertIn(scenario_id, by_id)

    def test_no_scenario_failures(self) -> None:
        failures = [r for r in run_scenarios() if r.status == ScenarioStatus.FAIL]
        self.assertEqual(failures, [], [(f.scenario_id, f.observed) for f in failures])

    def test_zero_training(self) -> None:
        with mock.patch(
            "market_platform_foundation.intelligence.training.factory.TrainingFactory.generate_candidates"
        ) as generate:
            run_scenarios(("F08",))
            generate.assert_not_called()

    def test_zero_promotion(self) -> None:
        with mock.patch(
            "market_platform_foundation.intelligence.promotion.engine.PromotionEngine.evaluate_promotion"
        ) as promote:
            run_scenarios(("F09",))
            promote.assert_not_called()


class FixtureLifecycleTests(unittest.TestCase):
    def test_prospective_fixture_lifecycle(self) -> None:
        result = run_prospective_fixture_lifecycle(
            release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD25_HEAD,
            qualification_start_ns=T,
        )
        self.assertTrue(result.pending_before_horizon)
        self.assertTrue(result.settled_after_horizon)
        self.assertEqual(result.integrity_status, ForwardIntegrityStatus.VALID)
        self.assertTrue(result.report_id.startswith("FQREP-"))


class RCIntegrityTests(unittest.TestCase):
    def test_rc_integrity_check_runs(self) -> None:
        result = verify_build25_rc_integrity()
        self.assertIn(result.status, {"PASS", "RC_INTEGRITY_MISMATCH"})
        self.assertTrue(result.actual_head)


class RunnerTests(unittest.TestCase):
    def test_run_forward_qualification(self) -> None:
        result = run_forward_qualification(
            release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD25_HEAD,
            qualification_start_ns=T,
        )
        self.assertTrue(result.fixture_lifecycle_ok)
        self.assertEqual(result.scenario_failures, ())
        self.assertIn(
            result.disposition,
            {
                QualificationDisposition.INSUFFICIENT_FORWARD_EVIDENCE,
                QualificationDisposition.QUALIFIED_WITH_LIMITATIONS,
            },
        )


class SpecDefaultsTests(unittest.TestCase):
    def test_default_universe(self) -> None:
        spec = build_forward_qualification_spec(
            release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD25_HEAD,
            qualification_start_ns=T,
        )
        self.assertEqual(spec.instrument_universe, DEFAULT_INSTRUMENT_UNIVERSE)

    def test_spec_id_excludes_results(self) -> None:
        spec = build_forward_qualification_spec(
            release_candidate_ref=BUILD25_HEAD,
            source_head=BUILD25_HEAD,
            qualification_start_ns=T,
        )
        payload = forward_qualification_spec_v1_to_dict(spec)
        self.assertNotIn("brier", payload)
        self.assertNotIn("log_loss", payload)
        self.assertEqual(spec.qualification_spec_id, derive_qualification_spec_id(spec))

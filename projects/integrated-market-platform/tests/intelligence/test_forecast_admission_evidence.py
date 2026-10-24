"""Forecast diagnostics preserve authoritative Opportunity and Action gates."""
from __future__ import annotations

import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from market_platform_foundation.intelligence.contracts.common import ContractReference, IntelligenceScope, QualitySummary
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.ui_api import paper_live_forecast as forecast
from tests.intelligence import test_action_decision as action

CUTOFF = 1791208800000000000


class ForecastAdmissionEvidenceTests(unittest.TestCase):
    def setUp(self):
        fixture = action.ActionServiceTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.service, self.body, self.store = fixture.service, fixture.body, fixture.store
        self.store.strategy_repository = InMemoryIntelligenceRepository()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def hook(self, refused=False):
        hook = object.__new__(forecast.LiveForecastHook)
        hook.root = Path(self.tmp.name)
        hook.clock = lambda: CUTOFF
        hook.build_id = "PFB-recorded"
        hook.artifacts = {}
        hook.refused = {"US:NVDA": "HOLDOUT_POLICY_NOT_SATISFIED"} if refused else {}
        hook.counters = dict(attempts=0, minted=0, existing=0, refused=0, errors=0, throttled=0)
        hook.lock = threading.Lock()
        return hook

    def build(self, hook, body=None):
        with patch.object(forecast, "live_forecast_hook", return_value=hook):
            return self.service._build(body or self.body)

    def opportunity(self):
        record = OpportunityV1("governed", "1", IntelligenceScope(("US:NVDA",)), CUTOFF - 1,
                               QualitySummary("GOOD"), side="LONG", valid_until_ns=CUTOFF + 60_000_000_000,
                               lineage_refs=(ContractReference("screener_evidence", "q"),))
        self.store.strategy_repository.put_opportunity(record)
        return record

    def test_uncovered_and_refused_artifact_are_distinct_and_candidate_bound(self):
        for refused, status, reason in [(False, "UNAVAILABLE", "INSTRUMENT_NOT_COVERED"),
                                        (True, "REJECTED", "HOLDOUT_POLICY_NOT_SATISFIED")]:
            with self.subTest(refused=refused):
                outcome = self.hook(refused).ensure_opportunity(self.store, action.candidate(), CUTOFF)
                self.assertIsInstance(outcome, dict)
                self.assertEqual(outcome["status"], status)
                self.assertEqual(outcome["reason_codes"], [reason])
                self.assertEqual(outcome["instrument_id"], "US:NVDA")
                self.assertEqual(outcome["decision_time_ns"], CUTOFF)
                self.assertEqual(outcome["evidence_ids"], ["q", "t"])

    def test_disabled_forecast_is_explicit_unavailable(self):
        with patch.object(forecast, "_HOOK", None), patch.dict("os.environ", {forecast.MODELS_ENV: ""}):
            built = self.service._build(self.body)
        evidence = built["context"].get("forecast_admission", {})
        self.assertEqual(evidence.get("status"), "UNAVAILABLE")
        self.assertIn("FORECAST_DISABLED", evidence["reason_codes"])
        self.assertEqual(evidence["candidate_run_id"], "run")
        self.assertEqual(evidence["decision_time_ns"], CUTOFF)
        self.assertIsNone(built["context"]["opportunity"])

    def test_rejection_reason_survives_action_record_with_original_identity_and_time(self):
        with patch.object(forecast, "live_forecast_hook", return_value=self.hook(True)):
            record = self.service.run(self.body)
        evidence = record["evidence_snapshot"]["context"].get("forecast_admission", {})
        self.assertEqual(evidence.get("status"), "REJECTED")
        self.assertEqual(evidence["reason_codes"], ["HOLDOUT_POLICY_NOT_SATISFIED"])
        self.assertEqual(evidence["candidate_run_id"], "run")
        self.assertEqual(evidence["outcome"]["candidate_run_id"], "run")
        self.assertEqual(evidence["decision_time_ns"], CUTOFF)
        self.assertIn("NO_GOVERNED_OPPORTUNITY", record["blocker_codes"])

    def test_unexpected_error_is_recorded_and_cannot_create_opportunity(self):
        hook = Mock()
        hook.ensure_opportunity.side_effect = RuntimeError("private-error-text")
        built = self.build(hook)
        evidence = built["context"].get("forecast_admission", {})
        self.assertEqual(evidence.get("status"), "ERROR")
        self.assertEqual(evidence["reason_codes"], ["FORECAST_ADMISSION_UNEXPECTED_ERROR"])
        self.assertEqual(evidence["error_type"], "RuntimeError")
        self.assertNotIn("private-error-text", built["encoded"])
        self.assertIsNone(built["context"]["opportunity"])

    def test_missing_hook_outcome_fails_closed_with_explicit_evidence(self):
        built = self.build(Mock(ensure_opportunity=Mock(return_value=None)))
        evidence = built["context"].get("forecast_admission", {})
        self.assertEqual(evidence.get("status"), "ERROR")
        self.assertIn("FORECAST_OUTCOME_INVALID", evidence["reason_codes"])
        self.assertIsNone(built["context"]["opportunity"])

    def test_explicit_repository_opportunity_does_not_claim_forecast_admission(self):
        self.opportunity()
        hook = Mock()
        built = self.build(hook, dict(self.body, opportunity_id="governed"))
        hook.ensure_opportunity.assert_not_called()
        evidence = built["context"].get("forecast_admission", {})
        self.assertEqual(evidence.get("status"), "NOT_REQUESTED")
        self.assertEqual(evidence["matched_opportunity_id"], "governed")
        self.assertNotIn("outcome", evidence)
        self.assertEqual(built["context"]["opportunity"]["opportunity_id"], "governed")

    def test_mint_outcome_is_preserved_without_changing_authoritative_input_identity(self):
        self.opportunity()
        hook = Mock()
        minted = dict(status="MINTED", instrument_id="US:NVDA", opportunity_id="governed",
                      build_id="PFB-real", model_id="model-real", forecast_id="forecast-real",
                      reason_codes=["OPPORTUNITY_EMITTED"], calibrated_probability=0.7)
        hook.ensure_opportunity.side_effect = [minted, dict(minted, status="EXISTING")]
        first, second = self.build(hook), self.build(hook)
        evidence = first["context"].get("forecast_admission", {})
        self.assertEqual(evidence.get("outcome"), minted)
        self.assertEqual(evidence["matched_opportunity_id"], "governed")
        self.assertEqual(first["digest"], second["digest"])
        minted["reason_codes"].append("mutated")
        self.assertEqual(evidence["outcome"]["reason_codes"], ["OPPORTUNITY_EMITTED"])

    def test_registry_disabled_missing_and_invalid_states_are_explicit(self):
        with patch.object(forecast, "_HOOK", None):
            for environment, status, reason in [({}, "UNAVAILABLE", "FORECAST_DISABLED"),
                                                ({forecast.MODELS_ENV: "relative"}, "REJECTED", "FORECAST_MODELS_DIRECTORY_INVALID"),
                                                ({forecast.MODELS_ENV: self.tmp.name}, "UNAVAILABLE", "ACTIVE_FORECAST_UNAVAILABLE")]:
                with self.subTest(environment=environment):
                    evidence = {}
                    self.assertIsNone(forecast.live_forecast_hook(environment, admission=evidence))
                    self.assertEqual(evidence["status"], status)
                    self.assertEqual(evidence["reason_codes"], [reason])
            (Path(self.tmp.name) / forecast.ACTIVE_FILE).write_text("{invalid", encoding="utf-8")
            evidence = {}
            self.assertIsNone(forecast.live_forecast_hook({forecast.MODELS_ENV: self.tmp.name}, admission=evidence))
            self.assertEqual(evidence["status"], "REJECTED")
            self.assertEqual(evidence["reason_codes"], ["FORECAST_REGISTRY_INVALID"])

    def test_mint_rejection_and_unavailability_remain_distinct_without_authority(self):
        for raw_status, status in [("NOT_MATCHED", "REJECTED"), ("SUPPRESSED", "REJECTED"),
                                   ("FORECAST_UNAVAILABLE", "UNAVAILABLE"), ("MINTED", "MINTED"),
                                   ("THROTTLED", "THROTTLED"), ("ERROR", "ERROR")]:
            with self.subTest(raw_status=raw_status):
                raw = dict(status=raw_status, instrument_id="US:NVDA", reason_codes=["EXACT_RECORDED_REASON"])
                built = self.build(Mock(ensure_opportunity=Mock(return_value=raw)))
                evidence = built["context"]["forecast_admission"]
                self.assertEqual(evidence["status"], status)
                self.assertEqual(evidence["outcome"], raw)
                self.assertEqual(evidence["reason_codes"], ["EXACT_RECORDED_REASON"])
                self.assertIsNone(built["context"]["opportunity"])
    def test_real_hook_mint_failure_preserves_safe_error_type(self):
        hook = self.hook()
        hook.artifacts = {"US:NVDA": object()}
        hook.last_attempt = {}
        hook.preregistration = {}
        hook.window_getter = lambda: object()
        candidate = action.candidate()
        candidate["instrument"].update(asset_class="EQUITY", venue_id="US_EQUITY")
        with patch("market_platform_foundation.strategy.path_a_live_forecast.mint_live_opportunity",
                   side_effect=RuntimeError("private-error-text")):
            outcome = hook.ensure_opportunity(self.store, candidate, CUTOFF)
        self.assertEqual(outcome["status"], "ERROR")
        self.assertEqual(outcome.get("error_type"), "RuntimeError")
        self.assertEqual(outcome["reason_codes"], ["FORECAST_ADMISSION_UNEXPECTED_ERROR"])
        self.assertNotIn("private-error-text", str(outcome))
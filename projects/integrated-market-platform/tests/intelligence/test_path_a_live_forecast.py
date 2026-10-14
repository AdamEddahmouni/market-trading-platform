"""Live Paper Path A: candidate → PRODUCTION forecast → StrategyMatch → governed Opportunity → Action gate."""

from __future__ import annotations

import random
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository
from market_platform_foundation.intelligence.production import live_training
from market_platform_foundation.intelligence.production.model_store import load_production_specialist_model
from market_platform_foundation.intelligence.production.training_build import _examples_from_manifest
from market_platform_foundation.strategy import path_a_live_forecast as live
from market_platform_foundation.strategy.path_a_forecast_producer import load_paper_demo_calibration
from market_platform_foundation.strategy.preregistration import build_preregistration
from tests.intelligence.test_live_feature_corpus import populated_window
from tests.intelligence.test_signal_fixtures import INSTRUMENT, ONE_SEC, T

DAY = 86_400 * ONE_SEC
# Midpoint drift per second giving a 5-minute momentum of about +/-0.0015, inside the training range.
UP, DOWN = 0.0005, -0.0005
ACCOUNT = "acct-paper-test"


def _iso(ns):
    return datetime.fromtimestamp(ns / 1e9, UTC).isoformat()


def _training_rows(count=600, seed=3):
    rng = random.Random(seed)
    start = T - DAY
    rows = []
    for index in range(count):
        momentum, nss = rng.uniform(-0.002, 0.002), rng.uniform(-0.5, 0.5)
        decision = start + index * 30 * ONE_SEC
        rows.append(dict(snapshot_id=f"snap-{index}", decision_time_ns=decision, momentum=momentum, net_signed_share=nss,
                         label=1 if momentum + rng.gauss(0, 0.0006) > 0 else 0,
                         label_available_time_ns=decision + 301 * ONE_SEC))
    return _examples_from_manifest(dict(scope=dict(instrument_ids=[INSTRUMENT]), examples=rows))


FIXTURE = SimpleNamespace()


def setUpModule():
    """One governed build shared by every test: it is read-only once built."""
    FIXTURE.tmp = tempfile.TemporaryDirectory()
    root = Path(FIXTURE.tmp.name)
    rows = _training_rows()
    built_at = max(e.label_available_time_ns for e in rows) + ONE_SEC
    record = live_training.build_instrument(INSTRUMENT, list(rows), output_dir=root / "build", decision_time_ns=built_at)
    assert record["status"] == "BUILT", record
    FIXTURE.artifacts = live.LiveForecastArtifacts(
        instrument_id=INSTRUMENT, build_id="PFB-test",
        model=load_production_specialist_model(root / "build" / INSTRUMENT / "model"),
        calibration=load_paper_demo_calibration(root / "build" / INSTRUMENT / "calibration"),
        activated_at_ns=built_at)
    FIXTURE.forecast_dir = root / "forecasts"
    FIXTURE.preregistration = build_preregistration(live.live_strategy_definition(), registered_at=_iso(built_at))


def tearDownModule():
    FIXTURE.tmp.cleanup()


class LiveForecastTests(unittest.TestCase):
    def setUp(self):
        self.artifacts, self.forecast_dir, self.preregistration = FIXTURE.artifacts, FIXTURE.forecast_dir, FIXTURE.preregistration
        self.repository = InMemoryIntelligenceRepository()
        self.candidate = dict(instrument=dict(instrument_id=INSTRUMENT, asset_class="EQUITY", venue_id="US_EQUITY"),
                              current_market_evidence=[dict(evidence_id="EV:quote-1")], reference_evidence=[], run_id="run-1")

    def mint(self, window, *, decision=T, preregistration=None, artifacts=None):
        return live.mint_live_opportunity(window=window, candidate=self.candidate, artifacts=artifacts or self.artifacts,
                                          preregistration=self.preregistration if preregistration is None else preregistration,
                                          account_id=ACCOUNT, decision_time_ns=decision, repository=self.repository,
                                          forecast_dir=self.forecast_dir)

    def test_a_rising_market_mints_one_long_opportunity_through_the_canonical_bridge(self):
        outcome = self.mint(populated_window(until_ns=T, drift=UP))
        self.assertEqual(outcome["status"], "MINTED", outcome)
        self.assertGreater(outcome["calibrated_probability"], 0.55)
        [opportunity] = self.repository.list_opportunities()
        self.assertEqual(opportunity.opportunity_id, outcome["opportunity_id"])
        self.assertEqual(opportunity.scope.instrument_ids, ("canonical:EQUITY:US_EQUITY:NVDA",))
        self.assertEqual(getattr(opportunity.side, "value", opportunity.side), "LONG")
        kinds = {ref.kind for ref in opportunity.lineage_refs}
        self.assertTrue({"forecast", "strategy_match", "champion_assignment", "opportunity_policy"} <= kinds)
        self.assertIn("EV:quote-1", {ref.id for ref in opportunity.lineage_refs})
        self.assertLessEqual(opportunity.valid_until_ns, T + live.MAX_OPPORTUNITY_LIFETIME_NS)
        self.assertEqual(opportunity.created_at_ns, T)

    def test_a_falling_market_is_not_an_entry_for_a_long_only_account(self):
        outcome = self.mint(populated_window(until_ns=T, drift=DOWN))
        self.assertEqual(outcome["status"], "NOT_MATCHED", outcome)
        self.assertIn("DIRECTION_SHORT_NOT_LONG", outcome["reason_codes"])
        self.assertEqual(list(self.repository.list_opportunities()), [])

    def test_a_strategy_registered_after_the_decision_abstains(self):
        late = build_preregistration(live.live_strategy_definition(), registered_at=_iso(T + ONE_SEC))
        outcome = self.mint(populated_window(until_ns=T, drift=UP), preregistration=late)
        self.assertEqual(outcome["status"], "NOT_MATCHED", outcome)
        self.assertEqual(list(self.repository.list_opportunities()), [])

    def test_a_tampered_preregistration_is_refused_before_any_forecast(self):
        tampered = dict(self.preregistration, registered_at=_iso(T - 2 * DAY))
        outcome = self.mint(populated_window(until_ns=T, drift=UP), preregistration=tampered)
        self.assertEqual(outcome["reason_codes"], ["STRATEGY_PREREGISTRATION_INVALID"])

    def test_a_champion_not_yet_effective_persists_nothing(self):
        later = live.LiveForecastArtifacts(instrument_id=INSTRUMENT, build_id="PFB-test", model=self.artifacts.model,
                                           calibration=self.artifacts.calibration, activated_at_ns=T + ONE_SEC)
        outcome = self.mint(populated_window(until_ns=T, drift=UP), artifacts=later)
        self.assertEqual(outcome["status"], "FORECAST_UNAVAILABLE", outcome)
        self.assertIn("CHAMPION_NOT_EFFECTIVE", outcome["reason_codes"])
        self.assertEqual(list(self.repository.list_opportunities()), [])

    def test_a_market_outside_everything_the_model_was_fitted_on_abstains(self):
        outcome = self.mint(populated_window(until_ns=T, drift=0.01))
        self.assertEqual(outcome["status"], "FORECAST_UNAVAILABLE", outcome)
        self.assertIn("ABSTAINED_OOD", outcome["reason_codes"])
        self.assertEqual(list(self.repository.list_opportunities()), [])

    def test_no_live_events_means_no_forecast(self):
        from market_platform_foundation.intelligence.production.live_feature_corpus import RollingEventWindow
        outcome = self.mint(RollingEventWindow(retain_ns=600 * ONE_SEC, clock=lambda: T))
        self.assertEqual((outcome["status"], outcome["reason_codes"]), ("FORECAST_UNAVAILABLE", ["NO_REFERENCE_QUOTE"]))

    def test_a_model_for_another_instrument_is_never_used(self):
        self.candidate["instrument"] = dict(instrument_id="AAPL", asset_class="EQUITY", venue_id="US_EQUITY")
        outcome = self.mint(populated_window(until_ns=T, drift=UP))
        self.assertEqual(outcome["reason_codes"], ["MODEL_INSTRUMENT_MISMATCH"])


class ActionGateTests(unittest.TestCase):
    """The Screener Action gate finds the Opportunity only through exact identity and shared evidence."""

    def setUp(self):
        self.repository = InMemoryIntelligenceRepository()
        candidate = dict(instrument=dict(instrument_id=INSTRUMENT, asset_class="EQUITY", venue_id="US_EQUITY"),
                         current_market_evidence=[dict(evidence_id="EV:quote-1")], reference_evidence=[], run_id="run-1")
        outcome = live.mint_live_opportunity(window=populated_window(until_ns=T, drift=UP), candidate=candidate,
                                             artifacts=FIXTURE.artifacts, preregistration=FIXTURE.preregistration, account_id=ACCOUNT,
                                             decision_time_ns=T, repository=self.repository, forecast_dir=FIXTURE.forecast_dir)
        assert outcome["status"] == "MINTED", outcome
        self.opportunity_id = outcome["opportunity_id"]
        from market_platform_foundation.ui_api.screener_action import ScreenerActionService
        self.service = ScreenerActionService(SimpleNamespace(strategy_repository=self.repository), repository=object())

    def candidate(self, evidence="EV:quote-1", iid=INSTRUMENT, venue="US_EQUITY"):
        return dict(instrument=dict(instrument_id=iid, asset_class="EQUITY", venue_id=venue),
                    current_market_evidence=[dict(evidence_id=evidence)], reference_evidence=[])

    def test_shared_evidence_and_exact_identity_find_it(self):
        found = self.service._opportunity(self.candidate(), T + ONE_SEC)
        self.assertEqual(found["opportunity_id"], self.opportunity_id)

    def test_other_evidence_another_venue_or_another_symbol_do_not(self):
        self.assertIsNone(self.service._opportunity(self.candidate(evidence="EV:other"), T + ONE_SEC))
        self.assertIsNone(self.service._opportunity(self.candidate(venue="XNYS"), T + ONE_SEC))
        self.assertIsNone(self.service._opportunity(self.candidate(iid="NVDL"), T + ONE_SEC))

    def test_it_is_not_valid_before_it_was_created_or_after_it_lapsed(self):
        self.assertIsNone(self.service._opportunity(self.candidate(), T - ONE_SEC))
        self.assertIsNone(self.service._opportunity(self.candidate(), T + live.MAX_OPPORTUNITY_LIFETIME_NS))


class LiveForecastHookTests(unittest.TestCase):
    """The server hook: only an ACTIVE, eligible, preregistered build is used, once per evidence set."""

    def setUp(self):
        import json
        import shutil
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        shutil.copytree(Path(FIXTURE.tmp.name) / "build", self.root / "PFB-test")
        (self.root / "preregistration.json").write_text(json.dumps(FIXTURE.preregistration), encoding="utf-8")
        self.write_active([INSTRUMENT])
        self.window = populated_window(until_ns=T, drift=UP)
        self.repository = InMemoryIntelligenceRepository()
        self.store = SimpleNamespace(strategy_repository=self.repository, paper_ledger=SimpleNamespace(paper_account_id=ACCOUNT))
        self.candidate = dict(instrument=dict(instrument_id=INSTRUMENT, asset_class="EQUITY", venue_id="US_EQUITY"),
                              current_market_evidence=[dict(evidence_id="EV:quote-1")], reference_evidence=[])

    def tearDown(self):
        self.tmp.cleanup()

    def write_active(self, instruments):
        import json
        (self.root / "ACTIVE.json").write_text(json.dumps(dict(
            schema_version="imp-live-forecast-active/1.0.0", build_id="PFB-test", instruments=instruments,
            activated_at=_iso(FIXTURE.artifacts.activated_at_ns))), encoding="utf-8")

    def hook(self):
        from market_platform_foundation.ui_api.paper_live_forecast import LiveForecastHook
        return LiveForecastHook(self.root, window_getter=lambda: self.window, clock=lambda: T)

    def test_an_eligible_build_mints_once_and_the_action_gate_then_finds_it(self):
        from unittest import mock
        from market_platform_foundation.ui_api import paper_live_forecast
        from market_platform_foundation.ui_api.screener_action import ScreenerActionService
        hook = self.hook()
        self.assertEqual(sorted(hook.artifacts), [INSTRUMENT])
        with mock.patch.object(paper_live_forecast, "_HOOK", hook):
            service = ScreenerActionService(self.store, repository=object())
            found = service._opportunity(self.candidate, T)
            again = service._opportunity(self.candidate, T + ONE_SEC)
        self.assertIsNotNone(found)
        self.assertEqual(found["opportunity_id"], again["opportunity_id"])
        self.assertEqual(len(list(self.repository.list_opportunities())), 1)
        self.assertEqual((hook.counters["minted"], hook.counters["existing"]), (1, 1))
        journal = list((self.root / "journal").glob("forecast-attempts-*.jsonl"))
        self.assertEqual(len(journal), 1)
        self.assertIn('"status":"MINTED"', journal[0].read_text(encoding="utf-8"))

    def test_a_refused_attempt_is_not_retried_inside_the_throttle_interval(self):
        hook = self.hook()
        self.window = populated_window(until_ns=T, drift=DOWN)
        first = hook.ensure_opportunity(self.store, self.candidate, T)
        second = hook.ensure_opportunity(self.store, self.candidate, T + ONE_SEC)
        self.assertEqual(first["status"], "NOT_MATCHED")
        self.assertEqual(second["status"], "THROTTLED")

    def test_an_ineligible_build_is_never_loaded(self):
        import json
        path = self.root / "PFB-test" / INSTRUMENT / "evaluation.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(dict(record, eligible=False)), encoding="utf-8")
        hook = self.hook()
        self.assertEqual(hook.artifacts, {})
        self.assertIsNone(hook.ensure_opportunity(self.store, self.candidate, T))

    def test_a_tampered_preregistration_disables_the_hook(self):
        import json
        from market_platform_foundation.ui_api.paper_live_forecast import LiveForecastHook
        (self.root / "preregistration.json").write_text(json.dumps(dict(FIXTURE.preregistration, principal_id="someone")), encoding="utf-8")
        with self.assertRaises(ValueError):
            LiveForecastHook(self.root)

    def test_off_unless_an_absolute_models_directory_with_an_active_build_is_configured(self):
        from unittest import mock
        from market_platform_foundation.ui_api import paper_live_forecast
        with mock.patch.object(paper_live_forecast, "_HOOK", None):
            self.assertIsNone(paper_live_forecast.live_forecast_hook({}))
            self.assertIsNone(paper_live_forecast.live_forecast_hook({"IMP_PAPER_FORECAST_MODELS_DIR": "relative/dir"}))
            self.assertEqual(paper_live_forecast.start_paper_live_forecast({})["reason"], "DISABLED")


class BoundaryTests(unittest.TestCase):
    def test_the_live_forecast_path_imports_no_order_broker_or_model_service(self):
        import ast
        tree = ast.parse(Path(live.__file__).read_text(encoding="utf-8"))
        imported = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        imported += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
        for module in imported:
            for forbidden in ("broker", "paper_projections", "paper.execution", "ui_api", "inference", "synthesis", "providers.adapters"):
                self.assertNotIn(forbidden, module, module)


if __name__ == "__main__":
    unittest.main()

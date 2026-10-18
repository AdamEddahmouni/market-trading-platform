"""Lossless corpus loading and runtime holdout policy regressions."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from market_platform_foundation.intelligence.production.errors import ProductionTrainingError
from market_platform_foundation.intelligence.production.live_feature_corpus import compute_decision, load_training_examples, SCHEMA_VERSION, LABEL_RULE
from market_platform_foundation.intelligence.production.identity import path_a_horizon
from tests.intelligence.test_live_feature_corpus import populated_window
from tests.intelligence.test_signal_fixtures import T, INSTRUMENT
from tests.intelligence import test_live_forecast_admission_integrity as integrity


class RuntimeHoldoutPolicyTests(integrity.AdmissionIntegrityTests):
    def test_eligible_flag_cannot_override_actual_holdout_rule(self):
        changes = [
            {"holdout": 10, "holdout_scores": {"samples": 10, "brier_skill": 0.5}},
            {"holdout": 100, "holdout_scores": {"samples": 100, "brier_skill": 0.0}},
            {"holdout": 100, "holdout_scores": {"samples": 100, "brier_skill": float("inf")}},
            {"holdout": 100, "holdout_scores": {"samples": 100, "brier_skill": float("nan")}},
            {"holdout_scores": {"samples": "100", "brier_skill": 0.5}},
            {"holdout_scores": None},
            {"eligibility_rule": "UNKNOWN"},
            {"eligible": "true"},
            {"instrument_id": "OTHER"},
            {"holdout": 1},
        ]
        for change in changes:
            with self.subTest(change=change):
                self.change_evaluation(lambda p: p.update(self.record, **change))
                self.assert_refused()


class LosslessCorpusLoaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"rows.jsonl"
        self.decision=compute_decision(populated_window(until_ns=T),INSTRUMENT,T)
        self.assertTrue(self.decision["accepted"])
        self.label=dict(schema_version=SCHEMA_VERSION,kind="label",instrument_id=INSTRUMENT,
                        decision_time_ns=T,status="SETTLED",label=1,
                        label_available_time_ns=T+path_a_horizon().duration_ns,
                        horizon_ns=path_a_horizon().duration_ns,label_rule=LABEL_RULE)

    def load(self, rows):
        self.path.write_text("".join(json.dumps(r)+"\n" for r in rows),encoding="utf-8")
        return load_training_examples([self.path])

    def test_valid_rows_and_identical_duplicates_remain_loadable(self):
        examples=self.load([self.decision,self.label,self.decision,self.label])
        self.assertEqual(len(examples),1)
        self.assertEqual(examples[0][1].label,1)

    def test_labels_are_not_coerced_from_boolean_float_or_string(self):
        for value in (True,1.9,"1"):
            with self.subTest(value=value),self.assertRaises(ProductionTrainingError):
                self.load([self.decision,dict(self.label,label=value)])

    def test_timestamps_are_not_coerced(self):
        for field in ("decision_time_ns","label_available_time_ns"):
            for value in (True,float(T),str(T)):
                with self.subTest(field=field,value=value),self.assertRaises(ProductionTrainingError):
                    self.load([self.decision,dict(self.label,**{field:value})])

    def test_conflicting_duplicate_label_is_refused(self):
        with self.assertRaisesRegex(ProductionTrainingError,"CONFLICTING_CORPUS_ROW"):
            self.load([self.decision,self.label,dict(self.label,label=0)])

    def test_unknown_corpus_schema_is_refused(self):
        with self.assertRaisesRegex(ProductionTrainingError,"CORPUS_SCHEMA"):
            self.load([dict(self.decision,schema_version="UNKNOWN"),self.label])

    def test_snapshot_and_row_decision_times_must_agree(self):
        snapshot=dict(self.decision["snapshot"],decision_time_ns=T-1)
        with self.assertRaisesRegex(ProductionTrainingError,"CORPUS_SNAPSHOT"):
            self.load([dict(self.decision,snapshot=snapshot),self.label])

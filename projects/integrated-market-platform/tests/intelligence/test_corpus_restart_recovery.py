"""Restart recovery preserves recorded clocks and never invents terminal evidence."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from market_platform_foundation.intelligence.production import live_feature_corpus as corpus
from tests.intelligence.test_live_feature_corpus import populated_window
from tests.intelligence.test_signal_fixtures import INSTRUMENT, ONE_SEC, T, quote_event


class CorpusRestartRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.now = T
        self.horizon = corpus.path_a_horizon().duration_ns
        self.original = self.recorder(populated_window(until_ns=T))
        self.original.tick()
        self.reference = dict(self.original.pending[0]["reference"])
        self.decision_ns = self.original.pending[0]["decision_time_ns"]

    def recorder(self, window=None):
        window = window or corpus.RollingEventWindow(retain_ns=1000 * ONE_SEC, clock=lambda: self.now)
        return corpus.LiveFeatureCorpusRecorder(
            window=window, directory=self.directory, instruments=lambda: [INSTRUMENT],
            session_open=lambda _at: True, clock=lambda: self.now)

    def rows(self):
        return [json.loads(line) for p in self.directory.glob("feature-corpus-*.jsonl")
                for line in p.read_text(encoding="utf-8").splitlines()]

    def labels(self):
        return [r for r in self.rows() if r["kind"] == "label" and r["decision_time_ns"] == self.decision_ns]

    def test_restart_before_horizon_restores_reference_and_settles_from_future_quote(self):
        self.now = T + ONE_SEC
        restarted = self.recorder()
        restarted.tick()
        self.assertEqual(len(restarted.pending), 1)
        self.assertEqual(restarted.pending[0]["reference"], self.reference)
        self.assertEqual(sum(r["kind"] == "decision" and r["decision_time_ns"] == self.decision_ns for r in self.rows()), 1)
        due = self.decision_ns + self.horizon
        self.now = due + ONE_SEC
        restarted.window.dispatch(quote_event("after-restart", event_time_ns=due,
                                             bid=self.reference["midpoint"] + 1,
                                             ask=self.reference["midpoint"] + 2))
        restarted.tick()
        label = self.labels()[0]
        self.assertEqual(label["status"], "SETTLED")
        self.assertEqual(label["terminal_event_id"], "after-restart")
        self.assertEqual(label["label_available_time_ns"], due)

    def test_restart_after_horizon_records_missing_terminal_evidence_without_a_label(self):
        self.now = self.decision_ns + self.horizon + ONE_SEC
        self.recorder().tick()
        self.assertEqual(len(self.labels()), 1)
        [label] = self.labels()
        self.assertEqual(label["status"], "UNLABELABLE")
        self.assertIsNone(label["label"])
        self.assertEqual(label["reason"], "RECORDER_RESTART_TERMINAL_EVIDENCE_UNAVAILABLE")
        self.assertEqual(label["recovered_at_ns"], self.now)
        self.assertEqual(corpus.load_training_examples(self.directory.glob("feature-corpus-*.jsonl")), [])

    def test_repeated_restart_preserves_existing_label_and_does_not_duplicate_it(self):
        self.now = self.decision_ns + self.horizon + ONE_SEC
        self.recorder().tick()
        self.assertEqual(len(self.labels()), 1)
        [before] = self.labels()
        self.now += ONE_SEC
        self.recorder().tick()
        self.assertEqual(self.labels(), [before])

    def test_recovery_index_has_a_hard_memory_bound_and_writes_nothing_on_overflow(self):
        later = corpus.compute_decision(populated_window(until_ns=T + 30 * ONE_SEC), INSTRUMENT, T + 30 * ONE_SEC)
        self.original._write(later)
        before = self.rows()
        self.now = T + 31 * ONE_SEC
        with mock.patch.object(corpus, "MAX_RECOVERY_DECISIONS", 1, create=True):
            with self.assertRaisesRegex(ValueError, "CORPUS_RECOVERY_CAP_EXCEEDED"):
                self.recorder().tick()
        self.assertEqual(self.rows(), before)

    def test_failed_later_file_retry_publishes_one_pending_identity_and_one_outcome(self):
        later = self.directory / "feature-corpus-9999-12-31.jsonl"
        later.write_text("{invalid", encoding="utf-8")
        self.now = T + ONE_SEC
        restarted = self.recorder()
        original_status = dict(restarted.status)
        for _attempt in range(2):
            with self.assertRaises(ValueError):
                restarted.tick()
            self.assertEqual(restarted.pending, [])
            self.assertEqual(restarted.status, original_status)
        later.write_text("", encoding="utf-8")
        restarted.tick()
        self.assertEqual(len(restarted.pending), 1)
        self.assertEqual(restarted.status["recovered_pending"], 1)
        due = self.decision_ns + self.horizon
        self.now = due + ONE_SEC
        restarted.window.dispatch(quote_event("retry-terminal", event_time_ns=due,
                                             bid=self.reference["midpoint"] + 1,
                                             ask=self.reference["midpoint"] + 2))
        restarted.tick()
        self.assertEqual(len(self.labels()), 1)
        self.assertEqual(self.labels()[0]["status"], "SETTLED")

    def test_appended_past_outcome_survives_io_failure_without_duplicate_on_retry(self):
        self.now = self.decision_ns + self.horizon + ONE_SEC
        restarted = self.recorder()
        original_write = restarted._write

        def appended_then_failed(row):
            original_write(row)
            raise OSError("simulated close failure after append")

        with mock.patch.object(restarted, "_write", side_effect=appended_then_failed):
            with self.assertRaises(OSError):
                restarted.tick()
        [before] = self.labels()
        restarted.tick()
        self.assertEqual(self.labels(), [before])
        self.assertEqual(restarted.pending, [])

    def test_failed_scan_repaired_after_expiry_never_writes_conflicting_outcomes(self):
        later = self.directory / "feature-corpus-9999-12-31.jsonl"
        later.write_text("{invalid", encoding="utf-8")
        self.now = T + ONE_SEC
        restarted = self.recorder()
        with self.assertRaises(ValueError):
            restarted.tick()
        self.now = self.decision_ns + self.horizon + corpus.DEFAULT_TERMINAL_TOLERANCE_NS + ONE_SEC
        later.write_text("", encoding="utf-8")
        restarted.tick()
        self.assertEqual(len(self.labels()), 1)
        self.assertEqual(self.labels()[0]["reason"], "RECORDER_RESTART_TERMINAL_EVIDENCE_UNAVAILABLE")
        self.assertEqual(corpus.load_training_examples(self.directory.glob("feature-corpus-*.jsonl")), [])
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from market_platform_foundation.shadow.acceptance import (
    Disposition,
    evaluate_acceptance,
    summarize_p6_disposition,
)


class AcceptanceEvaluatorTests(unittest.TestCase):
    def _base_kwargs(self, **overrides):
        kwargs = dict(
            protocol_present=True,
            protocol_preregistered_before_decisions=True,
            forward_observation_count=0,
            forward_source_configured=False,
            causality_violations=0,
            immutability_tests_pass=True,
            decisions_with_provenance=0,
            total_decisions=0,
            execution_gates_safe=True,
            recorder_error_count=0,
            evaluation_separation_proven=True,
            matrix_written=True,
            validation_green=True,
            manifest_immutable=True,
            es_excluded_not_fabricated=True,
            run_id_present=True,
            infrastructure_only_observations=False,
        )
        kwargs.update(overrides)
        return kwargs

    def test_blocked_forward_when_source_unconfigured(self):
        rows = evaluate_acceptance(**self._base_kwargs())
        forward = next(r for r in rows if r.criterion.criterion_id == "P6-AC-002")
        self.assertEqual(forward.disposition, Disposition.BLOCKED)
        self.assertEqual(summarize_p6_disposition(rows), "IN_PROGRESS_EVIDENCE_COLLECTION")

    def test_fail_forward_when_configured_but_no_observations(self):
        rows = evaluate_acceptance(**self._base_kwargs(forward_source_configured=True))
        forward = next(r for r in rows if r.criterion.criterion_id == "P6-AC-002")
        self.assertEqual(forward.disposition, Disposition.FAIL)

    def test_blocked_when_fixture_observations_only(self):
        rows = evaluate_acceptance(
            **self._base_kwargs(
                forward_source_configured=True,
                forward_observation_count=3,
                infrastructure_only_observations=True,
            )
        )
        forward = next(r for r in rows if r.criterion.criterion_id == "P6-AC-002")
        self.assertEqual(forward.disposition, Disposition.BLOCKED)

    def test_causality_violation_fails_acceptance(self):
        rows = evaluate_acceptance(**self._base_kwargs(causality_violations=1))
        causality = next(r for r in rows if r.criterion.criterion_id == "P6-AC-003")
        self.assertEqual(causality.disposition, Disposition.FAIL)
        self.assertEqual(summarize_p6_disposition(rows), "FAILED_ACCEPTANCE")

    def test_all_criteria_pass_without_stopping_rule_stays_in_progress(self):
        rows = evaluate_acceptance(**self._base_kwargs(forward_source_configured=True, forward_observation_count=2))
        self.assertTrue(all(r.disposition == Disposition.PASS for r in rows))
        self.assertEqual(summarize_p6_disposition(rows, stopping_rule_met=False), "IN_PROGRESS_EVIDENCE_COLLECTION")
        self.assertEqual(summarize_p6_disposition(rows, stopping_rule_met=True), "CLOSED")

    def test_provenance_passes_when_all_decisions_have_inline_fields(self):
        rows = evaluate_acceptance(
            **self._base_kwargs(
                forward_source_configured=True,
                forward_observation_count=2,
                total_decisions=2,
                decisions_with_provenance=2,
            )
        )
        provenance = next(r for r in rows if r.criterion.criterion_id == "P6-AC-005")
        self.assertEqual(provenance.disposition, Disposition.PASS)


if __name__ == "__main__":
    unittest.main()

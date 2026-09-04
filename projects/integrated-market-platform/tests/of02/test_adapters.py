from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from market_platform_foundation.of01.errors import OF01Error, OF01ErrorCode
from market_platform_foundation.of01.ids import new_uuid
from market_platform_foundation.of01.memory import InMemoryLedger
from market_platform_foundation.of01.records import (
    ActionCategory,
    ConsequenceProfile,
    FailureReasonFamily,
    OutcomeValidity,
    ProvenanceQualifier,
    TerminalResult,
)
from market_platform_foundation.of02.adapters.catalog import (
    attribute_benchmark,
    attribute_drift,
    attribute_evaluation,
    attribute_operational_drill,
    attribute_promotion,
    attribute_provider_smoke,
    attribute_research,
    attribute_training,
)
from market_platform_foundation.of02.adapters.validation import attribute_validation
from market_platform_foundation.of02.agent_policy import (
    prohibit_backdating,
    prohibit_direct_sql,
    prohibit_future_information,
    prohibit_historical_fabrication,
    prohibit_history_rewrite,
    prohibit_live_smoke_fabrication,
    prohibit_retry_id_regeneration,
)
from market_platform_foundation.of02.cli import main as of02_main
from market_platform_foundation.of02.contracts import AttemptSpec
from market_platform_foundation.of02.errors import OF02Error, OF02ErrorCode
from market_platform_foundation.of02.identity import allocate_native
from market_platform_foundation.of02.lifecycle import attribute, of_commit_eligible
from market_platform_foundation.of02.operations import execute
from market_platform_foundation.of02.retrospective import index_sources
from market_platform_foundation.of02.temporal import of_reference_eligible_at, reject_future_information
from tests.of01.support import DisposableAuthority


def _pass_result(**overrides):
    payload = {
        "schema_version": "1.0",
        "mode": "changed",
        "started_at": "2026-08-28T00:00:00+00:00",
        "status": "passed",
        "selected_suites": ["validation"],
        "full_suite_required": False,
        "tests_run": 10,
        "passes": 10,
        "skips": 0,
        "failures": 0,
        "errors": 0,
    }
    payload.update(overrides)
    return payload


class ValidationAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = InMemoryLedger(new_uuid())

    def test_clean_pass(self) -> None:
        result = attribute_validation(_pass_result(), writer=self.ledger, enabled=True, git_revision="abc")
        self.assertEqual(result.status.value, "COMMITTED")
        run = self.ledger.get_record("RUN", result.run_id)
        self.assertEqual(run.provenance_qualifier, ProvenanceQualifier.NATIVE)
        outcome = self.ledger.get_record("OUTCOME", result.outcome_id)
        self.assertEqual(outcome.validity, OutcomeValidity.VALID)
        disposition = self.ledger.get_record("DISPOSITION", result.disposition_id)
        self.assertEqual(disposition.action_category, ActionCategory.ACCEPT)
        self.assertEqual(disposition.domain_code, "PASS")
        attempt = self.ledger.get_record("ATTEMPT", result.attempt_ids[0])
        transition = None
        for bundle in self.ledger.stream_commits(0):
            for record in bundle.records:
                if getattr(record, "record_type", None) == "ATTEMPT_TRANSITION" and record.attempt_id == attempt.attempt_id:
                    if record.to_phase.value == "TERMINAL":
                        transition = record
        self.assertEqual(transition.terminal_result, TerminalResult.COMPLETED)

    def test_valid_test_failure_is_not_technical_failure(self) -> None:
        result = attribute_validation(
            _pass_result(status="failed", failures=2, passes=8),
            writer=self.ledger,
            enabled=True,
        )
        attempt_id = result.attempt_ids[0]
        terminal = None
        for bundle in self.ledger.stream_commits(0):
            for record in bundle.records:
                if getattr(record, "terminal_result", None) is not None:
                    terminal = record.terminal_result
        self.assertEqual(terminal, TerminalResult.COMPLETED)
        disposition = self.ledger.get_record("DISPOSITION", result.disposition_id)
        self.assertEqual(disposition.action_category, ActionCategory.REJECT)
        self.assertEqual(disposition.domain_code, "TESTS_FAILED")
        self.assertEqual(self.ledger.get_record("OUTCOME", result.outcome_id).validity, OutcomeValidity.VALID)

    def test_environment_error(self) -> None:
        result = attribute_validation(
            _pass_result(status="error", errors=1, tests_run=0, passes=0),
            writer=self.ledger,
            enabled=True,
        )
        disposition = self.ledger.get_record("DISPOSITION", result.disposition_id)
        self.assertEqual(disposition.domain_code, "ENVIRONMENT_ERROR")
        self.assertEqual(self.ledger.get_record("OUTCOME", result.outcome_id).validity, OutcomeValidity.INDETERMINATE)

    def test_retry_then_pass(self) -> None:
        attempts = (
            AttemptSpec(
                sequence=1,
                terminal_result=TerminalResult.FAILED,
                reason_code="ENVIRONMENT_FAILURE",
                reason_family=FailureReasonFamily.ENVIRONMENT_FAILURE,
            ),
            AttemptSpec(
                sequence=2,
                terminal_result=TerminalResult.COMPLETED,
                reason_code="ATTEMPT_COMPLETED",
            ),
        )
        result = attribute_validation(
            _pass_result(),
            writer=self.ledger,
            enabled=True,
            attempts=attempts,
            retry_then_pass=True,
        )
        self.assertEqual(len(result.attempt_ids), 2)
        first = self.ledger.get_record("ATTEMPT", result.attempt_ids[0])
        second = self.ledger.get_record("ATTEMPT", result.attempt_ids[1])
        self.assertEqual(first.attempt_sequence, 1)
        self.assertEqual(second.attempt_sequence, 2)
        self.assertEqual(second.predecessor_attempt_id, first.attempt_id)
        self.assertEqual(self.ledger.get_record("DISPOSITION", result.disposition_id).domain_code, "PASS_WITH_RETRY")

    def test_full_suite_required_and_skips(self) -> None:
        result = attribute_validation(
            _pass_result(full_suite_required=True, skips=3, passes=7),
            writer=self.ledger,
            enabled=True,
        )
        self.assertEqual(self.ledger.get_record("DISPOSITION", result.disposition_id).domain_code, "PASS_WITH_SKIPS")

    def test_cancel_interruption(self) -> None:
        result = attribute_validation(
            _pass_result(status="failed", interrupted=True),
            writer=self.ledger,
            enabled=True,
        )
        self.assertEqual(self.ledger.get_record("DISPOSITION", result.disposition_id).action_category, ActionCategory.CANCEL)

    def test_lost_response_resolves_existing_receipt(self) -> None:
        identities = allocate_native(attempt_count=1, capture_artifact=True)
        first = attribute_validation(_pass_result(), writer=self.ledger, enabled=True, identities=identities)
        resolved = self.ledger.resolve_command(identities.register_run_command_id)
        self.assertIsNotNone(resolved)
        retry = attribute_validation(_pass_result(), writer=self.ledger, enabled=True, identities=identities)
        self.assertEqual(retry.run_id, first.run_id)
        self.assertEqual(retry.status.value, "EXISTING")

    def test_same_command_retry_is_idempotent(self) -> None:
        identities = allocate_native(attempt_count=1, capture_artifact=True)
        first = attribute_validation(_pass_result(), writer=self.ledger, enabled=True, identities=identities)
        second = attribute_validation(_pass_result(), writer=self.ledger, enabled=True, identities=identities)
        self.assertEqual(first.run_id, second.run_id)
        self.assertEqual(second.status.value, "EXISTING")
        runs = [b for b in self.ledger.stream_commits(0) if b.command_type == "RegisterRun"]
        self.assertEqual(len(runs), 1)

    def test_materially_changed_request_new_run(self) -> None:
        first = attribute_validation(_pass_result(mode="changed"), writer=self.ledger, enabled=True)
        second = attribute_validation(_pass_result(mode="full"), writer=self.ledger, enabled=True)
        self.assertNotEqual(first.run_id, second.run_id)

    def test_command_conflict(self) -> None:
        identities = allocate_native(attempt_count=1, capture_artifact=True)
        attribute_validation(_pass_result(mode="changed"), writer=self.ledger, enabled=True, identities=identities)
        conflicted = attribute_validation(
            _pass_result(mode="full"),
            writer=self.ledger,
            enabled=True,
            identities=identities,
        )
        self.assertEqual(conflicted.status.value, "CONFLICTED")

    def test_disabled_does_not_write(self) -> None:
        result = attribute_validation(_pass_result(), writer=self.ledger, enabled=False)
        self.assertEqual(result.status.value, "DISABLED")
        self.assertEqual(list(self.ledger.stream_commits(0)), [])

    def test_c3_writer_unavailable_withholds(self) -> None:
        result = attribute_validation(
            _pass_result(),
            writer=None,
            enabled=True,
            consequence=ConsequenceProfile.C3_EVIDENCE_CRITICAL,
        )
        self.assertTrue(result.withheld_acceptance)
        self.assertEqual(result.status.value, "WITHHELD")

    def test_c1_writer_unavailable_is_best_effort(self) -> None:
        result = attribute_validation(_pass_result(), writer=None, enabled=True)
        self.assertEqual(result.status.value, "BEST_EFFORT_FAILED")
        self.assertFalse(result.withheld_acceptance)

    def test_cas_artifact_on_sqlite(self) -> None:
        authority = DisposableAuthority()
        self.addCleanup(authority.close)
        writer = authority.open_writer()
        result = attribute_validation(
            _pass_result(),
            writer=writer,
            cas=authority.cas,
            enabled=True,
        )
        self.assertEqual(
            result.status.value,
            "COMMITTED",
            msg=f"{result.error_code}: {result.error_message}",
        )
        self.assertEqual(len(result.artifact_ids), 1)


class CatalogAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = InMemoryLedger(new_uuid())

    def test_benchmark_is_informational(self) -> None:
        result = attribute_benchmark(
            {"name": "overhead", "schema_version": "1.0", "sample_count": 3, "comparability": "SAME_HOST"},
            writer=self.ledger,
            enabled=True,
        )
        self.assertEqual(self.ledger.get_record("DISPOSITION", result.disposition_id).domain_code, "INFORMATIONAL")

    def test_provider_smoke_fixture_not_live(self) -> None:
        result = attribute_provider_smoke(
            {"provider": "moomoo", "status": "NOT_EXECUTED"},
            writer=self.ledger,
            enabled=True,
            real_provider_executed=False,
        )
        self.assertEqual(self.ledger.get_record("DISPOSITION", result.disposition_id).domain_code, "NOT_EXECUTED")

    def test_research_training_evaluation_promotion_drift_drill(self) -> None:
        research = attribute_research({"experiment_id": "EXP-1", "objective": "scan"}, writer=self.ledger, enabled=True)
        training = attribute_training({"training_run_id": "TRN-1", "dataset_id": "DS-1", "candidate_id": "CAND-1"}, writer=self.ledger, enabled=True)
        evaluation = attribute_evaluation(
            {"evaluation_id": "EV-1", "underperformed_baseline": True, "analytical_result": "below_baseline"},
            writer=self.ledger,
            enabled=True,
        )
        promotion = attribute_promotion({"decision_id": "DEC-1", "decision": "REJECT", "candidate_id": "CAND-1"}, writer=self.ledger, enabled=True)
        drift = attribute_drift({"assessment_id": "AD-1", "trigger": "psi"}, writer=self.ledger, enabled=True)
        drill = attribute_operational_drill({"drill_id": "DR-1", "drill_type": "backup", "status": "passed"}, writer=self.ledger, enabled=True)
        eval_disp = self.ledger.get_record("DISPOSITION", evaluation.disposition_id)
        self.assertEqual(eval_disp.action_category, ActionCategory.REJECT)
        self.assertEqual(eval_disp.domain_code, "UNDERPERFORMED_BASELINE")
        terminal = None
        for bundle in self.ledger.stream_commits(0):
            for record in bundle.records:
                if getattr(record, "attempt_id", None) == evaluation.attempt_ids[0] and getattr(record, "terminal_result", None):
                    terminal = record.terminal_result
        self.assertEqual(terminal, TerminalResult.COMPLETED)
        self.assertEqual(self.ledger.get_record("OUTCOME", evaluation.outcome_id).validity, OutcomeValidity.VALID)
        self.assertIsNotNone(research.run_id)
        self.assertIsNotNone(training.run_id)
        self.assertEqual(self.ledger.get_record("DISPOSITION", promotion.disposition_id).domain_code, "EXISTING_AUTHORITY_DECISION")
        self.assertEqual(self.ledger.get_record("DISPOSITION", drift.disposition_id).domain_code, "RESEARCH_TRIGGER_ONLY")
        self.assertEqual(self.ledger.get_record("DISPOSITION", drill.disposition_id).domain_code, "VERIFIED")


class RetrospectiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ledger = InMemoryLedger(new_uuid())
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.root = Path(self.tmpdir.name)

    def _write(self, name: str, payload: dict) -> Path:
        path = self.root / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_dry_run_does_not_write(self) -> None:
        path = self._write("a.json", {"schema_version": "1.0", "status": "passed", "started_at": 10})
        batch = index_sources([path], writer=self.ledger, dry_run=True)
        self.assertEqual(batch.discovered, 1)
        self.assertEqual(batch.indexed, 0)
        self.assertEqual(list(self.ledger.stream_commits(0)), [])

    def test_idempotent_index(self) -> None:
        path = self._write("a.json", {"schema_version": "1.0", "status": "passed", "started_at": 10})
        first = index_sources([path], writer=self.ledger, dry_run=False)
        second = index_sources([path], writer=self.ledger, dry_run=False)
        self.assertEqual(first.indexed, 1)
        self.assertEqual(second.already_indexed, 1)
        self.assertEqual(len([b for b in self.ledger.stream_commits(0) if b.command_type == "RegisterRun"]), 1)

    def test_resume_interrupted_batch(self) -> None:
        paths = [
            self._write("a.json", {"schema_version": "1.0", "status": "passed", "started_at": 10}),
            self._write("b.json", {"schema_version": "1.0", "status": "passed", "started_at": 11}),
        ]
        index_sources(paths[:1], writer=self.ledger, dry_run=False)
        resumed = index_sources(paths, writer=self.ledger, dry_run=False)
        self.assertEqual(resumed.already_indexed, 1)
        self.assertEqual(resumed.indexed, 1)

    def test_missing_source(self) -> None:
        batch = index_sources([self.root / "missing.json"], writer=self.ledger, dry_run=False)
        self.assertEqual(batch.skipped, 1)

    def test_legacy_partial(self) -> None:
        path = self._write("partial.json", {"note": "old scrap"})
        batch = index_sources([path], writer=self.ledger, dry_run=False)
        self.assertEqual(batch.legacy_partial, 1)
        result = batch.results[0]
        self.assertEqual(result.provenance_qualifier, ProvenanceQualifier.LEGACY_PARTIAL)

    def test_source_change_creates_new_identity(self) -> None:
        path = self._write("a.json", {"schema_version": "1.0", "status": "passed", "started_at": 10})
        first = index_sources([path], writer=self.ledger, dry_run=False)
        path.write_text(json.dumps({"schema_version": "1.0", "status": "passed", "started_at": 10, "extra": 1}), encoding="utf-8")
        second = index_sources([path], writer=self.ledger, dry_run=False)
        self.assertEqual(first.results[0].run_id != second.results[0].run_id, True)
        self.assertEqual(len([b for b in self.ledger.stream_commits(0) if b.command_type == "RegisterRun"]), 2)

    def test_recorded_at_not_event_time(self) -> None:
        path = self._write("a.json", {"schema_version": "1.0", "status": "passed", "started_at": 50})
        batch = index_sources([path], writer=self.ledger, dry_run=False)
        outcome = self.ledger.get_record("OUTCOME", batch.results[0].outcome_id)
        last = list(self.ledger.stream_commits(0))[-1]
        self.assertEqual(outcome.effective_at_ns, 50)
        self.assertNotEqual(last.recorded_at_ns, 50)
        self.assertFalse(of_reference_eligible_at(recorded_at_ns=last.recorded_at_ns, cutoff_ns=0))
        self.assertFalse(of_commit_eligible(recorded_at_ns=last.recorded_at_ns, cutoff_ns=last.recorded_at_ns - 1))


class TemporalAndAgentTests(unittest.TestCase):
    def test_future_information_rejected(self) -> None:
        with self.assertRaises(OF02Error) as ctx:
            reject_future_information(decision_time_ns=10, of_recorded_at_ns=20)
        self.assertEqual(ctx.exception.code, OF02ErrorCode.FUTURE_INFORMATION)

    def test_agent_prohibitions(self) -> None:
        for fn, code in (
            (prohibit_historical_fabrication, OF02ErrorCode.FABRICATION_PROHIBITED),
            (prohibit_backdating, OF02ErrorCode.BACKDATE_PROHIBITED),
            (prohibit_direct_sql, OF02ErrorCode.DIRECT_SQL_PROHIBITED),
            (prohibit_retry_id_regeneration, OF02ErrorCode.RETRY_IDENTITY_REGENERATION),
            (prohibit_future_information, OF02ErrorCode.FUTURE_INFORMATION),
            (prohibit_history_rewrite, OF02ErrorCode.FABRICATION_PROHIBITED),
            (prohibit_live_smoke_fabrication, OF02ErrorCode.LIVE_SMOKE_FABRICATED),
        ):
            with self.subTest(fn=fn.__name__):
                with self.assertRaises(OF02Error) as ctx:
                    fn()
                self.assertEqual(ctx.exception.code, code)

    def test_status_capability(self) -> None:
        result = execute("OF02.OP.STATUS")
        self.assertEqual(result.outcome_code, "OK")
        self.assertEqual(of02_main(["status"]), 0)


class RegressionAndFaultTests(unittest.TestCase):
    def test_domain_output_independent_of_adapter(self) -> None:
        domain = _pass_result()
        disabled = attribute_validation(domain, writer=InMemoryLedger(new_uuid()), enabled=False)
        enabled = attribute_validation(domain, writer=InMemoryLedger(new_uuid()), enabled=True)
        self.assertEqual(domain["status"], "passed")
        self.assertEqual(disabled.status.value, "DISABLED")
        self.assertEqual(enabled.status.value, "COMMITTED")

    def test_c4_fail_closed(self) -> None:
        from market_platform_foundation.of02.contracts import AttributionRequest
        from market_platform_foundation.of02.lifecycle import attribute as lifecycle_attribute
        from market_platform_foundation.of02.policy import apply_failure

        request = AttributionRequest(
            adapter_id="validation",
            operation_class="VALIDATION",
            objective="x",
            consequence_profile=ConsequenceProfile.C4_AUTHORITY_CRITICAL,
            provenance_qualifier=ProvenanceQualifier.NATIVE,
        )
        with self.assertRaises(OF02Error) as ctx:
            apply_failure(request, RuntimeError("commit failed"))
        self.assertEqual(ctx.exception.code, OF02ErrorCode.AUTHORITY_FAIL_CLOSED)

    def test_attribution_overhead_is_measured(self) -> None:
        ledger = InMemoryLedger(new_uuid())
        started = time.perf_counter()
        attribute_validation(_pass_result(), writer=ledger, enabled=True)
        elapsed = time.perf_counter() - started
        self.assertGreater(elapsed, 0.0)
        self.assertLess(elapsed, 30.0)


if __name__ == "__main__":
    unittest.main()

"""Batch 07 operation-specific readiness coverage.

Verifies conservative admissibility, timestamp-uncertainty edges, determinism, isolation
from Phase 3A/3B evaluation, and that no outcome/OHLCV path is reachable. Unit tests use
synthetic fixtures; the committed golden report is compared byte-for-byte.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from squeeze_core.acquisition.operation_readiness import (
    ENABLED_RULE_IDS,
    FROZEN_COHORT,
    OhlcvAccessError,
    PHASE2_OPERATION_DEPENDENCIES,
    AdmissibilityStatus,
    CaseOperationReadiness,
    OperationReadinessReport,
    Phase3ARequestReadiness,
    assess_operation,
    assess_request_readiness,
    boundary_id_for,
    build_envelope,
    build_report,
    context_from_resolved,
    definitely_completed_before,
    render_markdown,
    serialize_report,
    straddles_boundary,
)
from squeeze_core.acquisition.operation_readiness import evidence_inputs, models
from squeeze_core.acquisition.operation_readiness.admissibility import AdmissibilityContext
from squeeze_core.acquisition.operation_readiness.evidence_inputs import (
    load_detection_context_evidence,
)
from squeeze_core.acquisition.ibkr_semantics.evidence import OFFICIAL_TRADES_EVIDENCE
from squeeze_core.acquisition.ibkr_semantics.resolver import resolve_ibkr_semantics

REPO_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_ROOT = REPO_ROOT / "tests" / "fixtures" / "acquisition" / "batch07" / "synthetic-batch05"
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "acquisition" / "batch07"
PKG_DIR = REPO_ROOT / "src" / "squeeze_core" / "acquisition" / "operation_readiness"

BOUNDARY = datetime(2026, 7, 18, 13, 37, 55, 17661, tzinfo=UTC)


@pytest.fixture(scope="module")
def report() -> OperationReadinessReport:
    return build_report(SYNTHETIC_ROOT)


def _dep(operation: str):
    return next(d for d in PHASE2_OPERATION_DEPENDENCIES if d.operation == operation)


def _resolved():
    return resolve_ibkr_semantics(OFFICIAL_TRADES_EVIDENCE)


def _ctx(**overrides) -> AdmissibilityContext:
    base = context_from_resolved(
        _resolved(),
        market_bars_present=True,
        final_bar_definitely_completed=True,
        final_bar_straddles_boundary=False,
    )
    if overrides:
        return AdmissibilityContext(**{**base.__dict__, **overrides})
    return base


# --- Global preflight isolation --------------------------------------------------------

def test_global_preflight_verdict_unchanged(report):
    assert report.global_preflight_verdict == "PREFLIGHT_REJECTED"
    assert report.global_preflight_unchanged is True


def test_operation_readiness_does_not_import_evaluation_runtime():
    # No module in the package imports the Phase 3A/3B evaluation or research runtime.
    for path in PKG_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "squeeze_core.evaluation" not in text, path.name
        assert "from ..evaluation" not in text and "import evaluation" not in text, path.name
        assert "squeeze_core.research" not in text, path.name


# --- Price / volume independence -------------------------------------------------------

def test_price_only_ratio_has_no_volume_dependency():
    sem = _dep("PERCENTAGE_RETURN").semantic_dependency
    assert sem.price_adjustment_ratio is True
    assert sem.volume_unit is False
    assert sem.volume_corporate_action is False
    assert sem.volume_filter_stationarity is False


def test_price_ratio_admissible_with_constraints_under_split_adjusted():
    result = assess_operation(_dep("PERCENTAGE_RETURN"), _ctx())
    assert result.status is AdmissibilityStatus.ADMISSIBLE_WITH_CONSTRAINTS
    assert models.ReasonCode.PRICE_RATIO_SPLIT_INVARIANT in result.reason_codes
    assert result.constraints  # explicit stated constraints


def test_absolute_price_level_blocks_on_corporate_action():
    result = assess_operation(_dep("ABSOLUTE_RETURN"), _ctx())
    assert result.status is AdmissibilityStatus.BLOCKED_MISSING_SEMANTICS
    assert (
        models.ReasonCode.PRICE_ABSOLUTE_LEVEL_CORPORATE_ACTION_UNCONFIRMED
        in result.reason_codes
    )


def test_volume_operation_blocks_on_unresolved_semantics():
    result = assess_operation(_dep("RELATIVE_VOLUME"), _ctx())
    assert result.status is AdmissibilityStatus.BLOCKED_MISSING_SEMANTICS
    assert models.ReasonCode.VOLUME_UNIT_UNRESOLVED in result.reason_codes
    assert models.ReasonCode.VOLUME_CORPORATE_ACTION_UNKNOWN in result.reason_codes
    assert models.ReasonCode.VOLUME_FILTER_STATIONARITY_UNPROVEN in result.reason_codes


def test_volume_stays_blocked_even_if_unit_were_resolved_but_others_unknown():
    # Resolving only the unit is not enough: corp-action + filter stationarity still block.
    result = assess_operation(_dep("RELATIVE_VOLUME"), _ctx(volume_unit_resolved=True))
    assert result.status is AdmissibilityStatus.BLOCKED_MISSING_SEMANTICS
    assert models.ReasonCode.VOLUME_UNIT_UNRESOLVED not in result.reason_codes
    assert models.ReasonCode.VOLUME_CORPORATE_ACTION_UNKNOWN in result.reason_codes


def test_provider_filtering_drives_volume_stationarity_block():
    # With filtering off, the filter-stationarity reason disappears (still blocked on unit).
    result = assess_operation(_dep("RELATIVE_VOLUME"), _ctx(provider_filtered=False))
    assert models.ReasonCode.VOLUME_FILTER_STATIONARITY_UNPROVEN not in result.reason_codes
    assert result.status is AdmissibilityStatus.BLOCKED_MISSING_SEMANTICS


def test_no_volume_magnitude_or_lot_inference_available():
    # The context exposes only documented facts; there is no magnitude/lot field to infer.
    ctx = _ctx()
    assert not hasattr(ctx, "observed_volume")
    assert not hasattr(ctx, "volume_magnitude")
    assert not hasattr(ctx, "shares_vs_lots")


# --- Timestamp uncertainty -------------------------------------------------------------

@pytest.mark.parametrize(
    "offset_seconds,expect_completed,expect_straddle",
    [
        (-61, True, False),   # t+60 = B-1 <= B
        (-60, True, False),   # t+60 = B exactly
        (-59, False, True),   # t+60 = B+1 > B, and t-60 < B -> straddle
        (0, False, True),     # t = B -> straddle
    ],
)
def test_timestamp_edge_cases(offset_seconds, expect_completed, expect_straddle):
    t = BOUNDARY + timedelta(seconds=offset_seconds)
    assert definitely_completed_before(t, 60, BOUNDARY) is expect_completed
    assert straddles_boundary(t, 60, BOUNDARY) is expect_straddle


def test_envelope_does_not_mutate_timestamp():
    t = datetime(2026, 7, 17, 23, 59, 0, tzinfo=UTC)
    env = build_envelope(t, 60, BOUNDARY)
    assert env.event_timestamp == t
    assert env.earliest_possible_completion == t
    assert env.latest_possible_completion == t + timedelta(seconds=60)
    assert env.definitely_completed_before_boundary is True
    assert env.straddles_boundary is False


def test_straddling_bar_blocks_alignment():
    ctx = _ctx(final_bar_definitely_completed=False, final_bar_straddles_boundary=True)
    completed = next(d for d, _ in _rule_deps() if d.operation == "COMPLETED_BAR_AVAILABLE")
    result = assess_operation(completed, ctx)
    assert result.status is AdmissibilityStatus.BLOCKED_ALIGNMENT


def _rule_deps():
    from squeeze_core.acquisition.operation_readiness.dependencies import (
        PHASE3A_RULE_DEPENDENCIES,
    )

    return PHASE3A_RULE_DEPENDENCIES


# --- Session dependency ---------------------------------------------------------------

def test_session_completeness_blocks_when_unevidenced():
    from squeeze_core.acquisition.operation_readiness.models import (
        OperationDependency,
        OperationKind,
        SemanticDependency,
    )

    dep = OperationDependency(
        operation="SYNTHETIC_SESSION_COMPLETE_OP",
        kind=OperationKind.PRICE_ONLY_RATIO,
        required_domains=("MARKET_BARS",),
        touches_detection_context_bars=True,
        semantic_dependency=SemanticDependency(
            price_adjustment_ratio=True, session_completeness=True
        ),
    )
    blocked = assess_operation(dep, _ctx(session_completeness_evidenced=False))
    assert blocked.status is AdmissibilityStatus.BLOCKED_MISSING_EVIDENCE
    ok = assess_operation(dep, _ctx(session_completeness_evidenced=True))
    assert ok.status is AdmissibilityStatus.ADMISSIBLE_WITH_CONSTRAINTS


# --- OHLCV / outcome isolation ---------------------------------------------------------

def test_guard_refuses_raw_csv(tmp_path):
    from squeeze_core.acquisition.operation_readiness.evidence_inputs import (
        _guard_manifest_path,
    )

    with pytest.raises(OhlcvAccessError):
        _guard_manifest_path(Path("intake/local-bars/ibkr-batch-05/raw/XNCR-detection-context.csv"))
    with pytest.raises(OhlcvAccessError):
        _guard_manifest_path(Path("something/XNCR-frozen-forward-24h.jsonl"))
    with pytest.raises(OhlcvAccessError):
        _guard_manifest_path(Path("requests/not-a-manifest.json"))


def test_forward_artifacts_referenced_by_identity_only():
    forward = evidence_inputs.forward_artifact_identity(SYNTHETIC_ROOT)
    assert set(forward) == {sym for sym, _ in FROZEN_COHORT}
    for sha, length in forward.values():
        assert len(sha) == 64 and length > 0


def test_case_record_has_no_outcome_fields():
    forbidden = {"outcome", "score", "rank", "ranking", "recommendation", "pnl", "return",
                 "forward_return", "substantial_move", "label"}
    assert forbidden.isdisjoint(set(CaseOperationReadiness.model_fields))


# --- 25-rule matrix and Phase 3A readiness --------------------------------------------

def test_rule_matrix_covers_exactly_the_policy_25_rules(report):
    policy_path = (
        REPO_ROOT / "src" / "squeeze_core" / "evaluation" / "policies"
        / "phase_3a_transparent_candidate_policy_v1.json"
    )
    enabled = set(json.loads(policy_path.read_text(encoding="utf-8"))["enabled_rule_ids"])
    assert len(enabled) == 25
    matrix_ids = {r.rule_id for r in report.phase3a_rule_dependency_matrix}
    assert matrix_ids == enabled
    assert set(ENABLED_RULE_IDS) == enabled


def test_rule_matrix_emits_no_pass_or_fail(report):
    allowed = set(AdmissibilityStatus)
    for rule in report.phase3a_rule_dependency_matrix:
        assert rule.admissibility_status in allowed
        assert rule.admissibility_status.value not in {"PASS", "FAIL"}


def test_request_readiness_ready_without_executing(report):
    assert all(
        c.phase3a_request_readiness is Phase3ARequestReadiness.PHASE3A_REQUEST_READY
        for c in report.cases
    )
    # missing identity would block; this proves it is a pure determination, not execution
    assert (
        assess_request_readiness(
            has_frozen_symbol=False,
            has_frozen_boundary_as_of=True,
            has_policy_version=True,
            has_enabled_rule_ids=True,
        )
        is Phase3ARequestReadiness.PHASE3A_REQUEST_BLOCKED
    )


def test_market_bar_availability_rules_admissible(report):
    by_id = {r.rule_id: r for r in report.phase3a_rule_dependency_matrix}
    assert by_id["MARKET_DATA_AVAILABLE"].admissibility_status is AdmissibilityStatus.ADMISSIBLE
    assert by_id["COMPLETED_BAR_AVAILABLE"].admissibility_status is AdmissibilityStatus.ADMISSIBLE
    assert (
        by_id["PERCENTAGE_CHANGE_MINIMUM"].admissibility_status
        is AdmissibilityStatus.ADMISSIBLE_WITH_CONSTRAINTS
    )
    assert by_id["PRICE_RANGE"].admissibility_status is AdmissibilityStatus.BLOCKED_MISSING_SEMANTICS
    assert (
        by_id["RELATIVE_VOLUME_MINIMUM"].admissibility_status
        is AdmissibilityStatus.BLOCKED_MISSING_SEMANTICS
    )


# --- Association / determinism ---------------------------------------------------------

def test_fifteen_cases_in_source_order(report):
    assert len(report.cases) == 15
    assert [c.symbol for c in report.cases] == [sym for sym, _ in FROZEN_COHORT]
    assert [c.case_id for c in report.cases] == [cid for _, cid in FROZEN_COHORT]


def test_association_deterministic_and_boundary_id_stable():
    r1 = build_report(SYNTHETIC_ROOT)
    r2 = build_report(SYNTHETIC_ROOT)
    assert [c.association_id for c in r1.cases] == [c.association_id for c in r2.cases]
    assert [c.deterministic_id for c in r1.cases] == [c.deterministic_id for c in r2.cases]
    for sym, cid in FROZEN_COHORT:
        assert boundary_id_for(cid, sym) == boundary_id_for(cid, sym)


def test_schema_version_is_1_0_0(report):
    assert models.SCHEMA_VERSION == "1.0.0"
    assert report.schema_version == "1.0.0"
    for case in report.cases:
        assert case.schema_version == "1.0.0"


def test_generator_byte_identical_and_matches_committed_golden():
    produced = serialize_report(build_report(SYNTHETIC_ROOT))
    again = serialize_report(build_report(SYNTHETIC_ROOT))
    assert produced == again
    committed = (FIXTURE_DIR / "operation-readiness-report.json").read_bytes()
    assert produced == committed
    md = render_markdown(build_report(SYNTHETIC_ROOT))
    committed_md = (FIXTURE_DIR / "operation-readiness-report.md").read_text(encoding="utf-8")
    assert md == committed_md


def test_observed_coverage_from_provenance_only():
    evidence = load_detection_context_evidence(SYNTHETIC_ROOT)
    assert set(evidence) == {sym for sym, _ in FROZEN_COHORT}
    xncr = evidence["XNCR"]
    assert xncr.coverage.observed_coverage_end == datetime(2026, 7, 17, 23, 59, tzinfo=UTC)
    assert xncr.coverage.max_possible_final_bar_completion == datetime(2026, 7, 18, 0, 0, tzinfo=UTC)
    # gap from definitely-completed evidence to the Saturday boundary (weekend fact)
    assert xncr.coverage.gap_seconds_from_definitely_completed_to_boundary == 49075


def test_no_ranking_or_recommendation_in_report_fields():
    forbidden = {"ranking", "recommendation", "score", "rank"}
    assert forbidden.isdisjoint(set(OperationReadinessReport.model_fields))

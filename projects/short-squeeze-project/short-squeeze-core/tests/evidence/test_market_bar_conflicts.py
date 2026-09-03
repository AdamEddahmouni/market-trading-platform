from datetime import datetime

from squeeze_core.adapters.market_bars import normalize_market_bar_record
from squeeze_core.evidence import (
    ConflictClassification,
    CoverageDomain,
    CoverageState,
    PointInTimeEvidencePolicy,
    build_point_in_time_evidence,
)

from tests.adapters.market_bars.test_models_and_parsing import record_values
from tests.adapters.market_bars.test_normalizer import context


def _observation(provider, provider_id, **updates):
    raw = record_values(
        provider=provider,
        provider_record_id=provider_id,
        source_record_id=provider_id,
        **updates,
    )
    return normalize_market_bar_record(raw, context()).observations[0]


def _bundle(*observations):
    return build_point_in_time_evidence(
        "TESTA",
        observations,
        PointInTimeEvidencePolicy(
            as_of=datetime.fromisoformat("2026-01-15T14:32:00+00:00"),
            allow_stale=True,
            include_market_bars_domain=True,
        ),
    )


def test_same_boundary_different_provider_values_are_preserved_without_winner():
    left = _observation("SCHWAB_SHAPED", "schwab-bar")
    right = _observation("IBKR_SHAPED", "ibkr-bar", close="10.26")
    bundle = _bundle(left, right)
    conflicts = [item for item in bundle.conflicts if item.semantic_field == "bar_close"]
    assert len(conflicts) == 1
    assert conflicts[0].classification is ConflictClassification.VALUE_CONFLICT
    assert set(conflicts[0].values) == {left.payload.close, right.payload.close}
    assert conflicts[0].status == "UNRESOLVED"
    coverage = next(item for item in bundle.source_coverage if item.domain is CoverageDomain.MARKET_BARS)
    assert coverage.state is CoverageState.CONFLICTED


def test_equal_same_boundary_cross_provider_values_are_not_conflicts():
    bundle = _bundle(
        _observation("SCHWAB_SHAPED", "schwab-bar"),
        _observation("IBKR_SHAPED", "ibkr-bar"),
    )
    assert not [item for item in bundle.conflicts if item.semantic_field.startswith("bar_")]


def test_different_boundaries_are_temporal_not_direct_value_conflicts():
    later = _observation(
        "IBKR_SHAPED",
        "ibkr-later",
        bar_start="2026-01-15T09:31:00-05:00",
        bar_end="2026-01-15T09:32:00-05:00",
        publication_timestamp="2026-01-15T09:32:01-05:00",
    )
    bundle = _bundle(_observation("SCHWAB_SHAPED", "schwab-bar"), later)
    assert all(
        item.classification is ConflictClassification.TEMPORAL_DIFFERENCE
        for item in bundle.conflicts
        if item.semantic_field.startswith("bar_")
    )


def test_explicit_partial_completion_progression_is_not_a_value_conflict():
    partial = _observation("SCHWAB_SHAPED", "partial", status="PARTIAL", close="10.15")
    completed = _observation(
        "SCHWAB_SHAPED",
        "complete",
        supersedes_provider_record_id="partial",
    )
    bundle = _bundle(partial, completed)
    assert not [item for item in bundle.conflicts if item.semantic_field.startswith("bar_")]


def test_conflict_ids_are_stable_under_input_reordering():
    left = _observation("SCHWAB_SHAPED", "schwab-bar")
    right = _observation("IBKR_SHAPED", "ibkr-bar", close="10.26")
    first = _bundle(left, right)
    second = _bundle(right, left)
    assert first.conflicts == second.conflicts

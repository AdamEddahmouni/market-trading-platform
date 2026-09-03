from squeeze_core.evidence import CoverageDomain
from squeeze_core.readiness import build_conflict_summary
from squeeze_core.readiness.diagnostics import ReadinessDiagnosticCode

from .conftest import build_bundle, make_bar, make_borrow, make_short_interest


def test_no_conflicts():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    summary = build_conflict_summary(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    assert summary.conflict_count == 0
    assert any(
        d.code is ReadinessDiagnosticCode.CONFLICT_SUMMARY_NO_CONFLICTS for d in summary.diagnostics
    )


def test_one_conflict():
    # Same-provider records for the same settlement period with disagreeing values
    # produce one EvidenceConflict per compared payload field (Phase 1's
    # DUPLICATE_CONFLICT classification), not necessarily exactly one overall -- this
    # test only asserts that at least one unresolved conflict is present and
    # attributed to the domain, not a specific count.
    a = make_short_interest(source_record_id="si-a", settlement_date="2026-01-15", short_shares="1000000")
    b = make_short_interest(source_record_id="si-b", settlement_date="2026-01-15", short_shares="2000000")
    bundle = build_bundle("TESTD", [a, b], "2026-03-01T12:00:00Z")
    summary = build_conflict_summary(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    assert summary.conflict_count >= 1
    assert summary.conflicts_by_domain[0].domain is CoverageDomain.PUBLISHED_SHORT_INTEREST
    assert any(
        d.code is ReadinessDiagnosticCode.CONFLICT_SUMMARY_UNRESOLVED_CONFLICT
        for d in summary.diagnostics
    )


def test_multiple_conflicts_in_one_domain():
    a = make_short_interest(source_record_id="si-a", settlement_date="2026-01-15", short_shares="1000000")
    b = make_short_interest(source_record_id="si-b", settlement_date="2026-01-15", short_shares="2000000")
    c = make_short_interest(source_record_id="si-c", settlement_date="2026-01-15", short_shares="3000000")
    bundle = build_bundle("TESTD", [a, b, c], "2026-03-01T12:00:00Z")
    summary = build_conflict_summary(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    assert summary.conflict_count >= 2
    assert summary.conflicts_by_domain[0].domain is CoverageDomain.PUBLISHED_SHORT_INTEREST


def test_conflicts_across_multiple_domains_are_grouped_per_domain():
    si_a = make_short_interest(source_record_id="si-a", settlement_date="2026-01-15", short_shares="1000000")
    si_b = make_short_interest(source_record_id="si-b", settlement_date="2026-01-15", short_shares="2000000")
    bundle = build_bundle("TESTD", [si_a, si_b], "2026-03-01T12:00:00Z")
    summary = build_conflict_summary(
        bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.MARKET_BARS)
    )
    domains_with_conflicts = {entry.domain for entry in summary.conflicts_by_domain}
    assert domains_with_conflicts == {CoverageDomain.PUBLISHED_SHORT_INTEREST}


def test_revision_not_counted_as_conflict():
    original = make_short_interest(
        source_record_id="si-rev-orig", settlement_date="2026-01-15", short_shares="900000"
    )
    revision = make_short_interest(
        source_record_id="si-rev-new",
        settlement_date="2026-01-15",
        publication_date="2026-02-05",
        short_shares="950000",
        revision_status="REVISED",
        revision_number=1,
        supersedes_source_record_id="si-rev-orig",
    )
    bundle = build_bundle("TESTD", [original, revision], "2026-03-01T12:00:00Z")
    summary = build_conflict_summary(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    assert summary.conflict_count == 0


def test_cancellation_not_counted_as_conflict():
    original = make_short_interest(
        source_record_id="si-cancel-orig", settlement_date="2026-01-15", short_shares="900000"
    )
    cancellation = make_short_interest(
        source_record_id="si-cancel-new",
        settlement_date="2026-01-15",
        publication_date="2026-02-05",
        short_shares="900000",
        revision_status="CANCELLED",
        revision_number=1,
        supersedes_source_record_id="si-cancel-orig",
    )
    bundle = build_bundle("TESTD", [original, cancellation], "2026-03-01T12:00:00Z")
    summary = build_conflict_summary(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    assert summary.conflict_count == 0


def test_temporal_difference_not_counted_as_conflict():
    early = make_short_interest(
        source_record_id="si-early", settlement_date="2025-12-15", short_shares="900000"
    )
    late = make_short_interest(
        source_record_id="si-late", settlement_date="2026-01-31", short_shares="950000"
    )
    bundle = build_bundle("TESTD", [early, late], "2026-03-01T12:00:00Z")
    summary = build_conflict_summary(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    assert summary.conflict_count == 0


def test_stable_conflict_ids_across_two_builds():
    a = make_short_interest(source_record_id="si-a", settlement_date="2026-01-15", short_shares="1000000")
    b = make_short_interest(source_record_id="si-b", settlement_date="2026-01-15", short_shares="2000000")
    bundle_1 = build_bundle("TESTD", [a, b], "2026-03-01T12:00:00Z")
    bundle_2 = build_bundle("TESTD", [a, b], "2026-03-01T12:00:00Z")
    summary_1 = build_conflict_summary(bundle_1, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    summary_2 = build_conflict_summary(bundle_2, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    assert summary_1.conflict_ids == summary_2.conflict_ids
    assert summary_1.deterministic_id == summary_2.deterministic_id


def test_conflict_ids_are_sorted():
    a = make_short_interest(source_record_id="si-a", settlement_date="2026-01-15", short_shares="1000000")
    b = make_short_interest(source_record_id="si-b", settlement_date="2026-01-15", short_shares="2000000")
    c = make_short_interest(source_record_id="si-c", settlement_date="2026-01-15", short_shares="3000000")
    bundle = build_bundle("TESTD", [a, b, c], "2026-03-01T12:00:00Z")
    summary = build_conflict_summary(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    assert summary.conflict_ids == tuple(sorted(summary.conflict_ids))


def test_affected_observation_ids_sorted():
    a = make_short_interest(source_record_id="si-a", settlement_date="2026-01-15", short_shares="1000000")
    b = make_short_interest(source_record_id="si-b", settlement_date="2026-01-15", short_shares="2000000")
    bundle = build_bundle("TESTD", [a, b], "2026-03-01T12:00:00Z")
    summary = build_conflict_summary(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    assert summary.affected_observation_ids == tuple(sorted(summary.affected_observation_ids))


def test_no_provider_winner_or_resolution_field():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    summary = build_conflict_summary(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    field_names = set(type(summary).model_fields)
    for forbidden in ("winner", "resolved_value", "average"):
        assert forbidden not in field_names

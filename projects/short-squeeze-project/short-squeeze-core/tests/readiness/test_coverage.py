from squeeze_core.evidence import CoverageDomain
from squeeze_core.readiness import DomainCoverageState, build_domain_coverage_snapshot
from squeeze_core.readiness.coverage import classify_domain_coverage

from .conftest import build_bundle, make_bar, make_borrow, make_sec_filing, make_short_interest


def test_all_requested_domains_present():
    si = make_short_interest()
    fee, availability = make_borrow()
    bar = make_bar()
    bundle = build_bundle("TESTD", [si, fee, availability, bar], "2026-03-01T12:00:00Z")
    domains = (
        CoverageDomain.PUBLISHED_SHORT_INTEREST,
        CoverageDomain.BORROW_FEE,
        CoverageDomain.BORROW_AVAILABILITY,
        CoverageDomain.MARKET_BARS,
    )
    snapshot = build_domain_coverage_snapshot(bundle, domains)
    assert set(snapshot.present_domains) == set(domains)
    assert not snapshot.missing_domains


def test_one_missing_domain():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    snapshot = build_domain_coverage_snapshot(
        bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.BORROW_FEE)
    )
    assert snapshot.missing_domains == (CoverageDomain.BORROW_FEE,)
    assert snapshot.present_domains == (CoverageDomain.PUBLISHED_SHORT_INTEREST,)


def test_multiple_missing_domains():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    snapshot = build_domain_coverage_snapshot(
        bundle,
        (
            CoverageDomain.PUBLISHED_SHORT_INTEREST,
            CoverageDomain.BORROW_FEE,
            CoverageDomain.BORROW_AVAILABILITY,
        ),
    )
    assert set(snapshot.missing_domains) == {
        CoverageDomain.BORROW_FEE,
        CoverageDomain.BORROW_AVAILABILITY,
    }


def test_domain_with_only_future_evidence_is_unavailable_not_missing():
    si = make_short_interest(publication_date="2026-04-01", settlement_date="2026-03-25")
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    state, _ = classify_domain_coverage(bundle, CoverageDomain.PUBLISHED_SHORT_INTEREST)
    assert state is DomainCoverageState.UNAVAILABLE


def test_domain_with_receipt_after_as_of_is_unavailable():
    si = make_short_interest(ingested_at="2026-04-01T00:00:00Z")
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    state, _ = classify_domain_coverage(bundle, CoverageDomain.PUBLISHED_SHORT_INTEREST)
    assert state is DomainCoverageState.UNAVAILABLE


def test_domain_with_eligible_active_record_is_present():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    state, _ = classify_domain_coverage(bundle, CoverageDomain.PUBLISHED_SHORT_INTEREST)
    assert state is DomainCoverageState.PRESENT


def test_domain_with_only_cancelled_record_is_cancelled():
    cancelled = make_short_interest(
        source_record_id="si-cancel",
        settlement_date="2026-01-15",
        publication_date="2026-02-05",
        short_shares="900000",
        revision_status="CANCELLED",
        revision_number=1,
        supersedes_source_record_id="si-original-not-in-bundle",
    )
    bundle = build_bundle("TESTD", [cancelled], "2026-03-01T12:00:00Z")
    state, _ = classify_domain_coverage(bundle, CoverageDomain.PUBLISHED_SHORT_INTEREST)
    assert state is DomainCoverageState.CANCELLED


def test_active_record_plus_older_cancellation_of_different_period_is_present():
    active = make_short_interest(
        source_record_id="si-active", settlement_date="2026-01-31", publication_date="2026-02-10"
    )
    older_original = make_short_interest(
        source_record_id="si-old-original",
        settlement_date="2025-12-15",
        publication_date="2025-12-20",
        short_shares="700000",
    )
    older_cancelled = make_short_interest(
        source_record_id="si-old-cancel",
        settlement_date="2025-12-15",
        publication_date="2025-12-25",
        revision_status="CANCELLED",
        revision_number=1,
        supersedes_source_record_id="si-old-original",
    )
    bundle = build_bundle(
        "TESTD", [active, older_original, older_cancelled], "2026-03-01T12:00:00Z"
    )
    state, _ = classify_domain_coverage(bundle, CoverageDomain.PUBLISHED_SHORT_INTEREST)
    assert state is DomainCoverageState.PRESENT


def test_domain_with_unresolved_conflict_is_conflicted():
    conflict_a = make_short_interest(
        source_record_id="si-conf-a", settlement_date="2026-01-15", short_shares="1000000"
    )
    conflict_b = make_short_interest(
        source_record_id="si-conf-b", settlement_date="2026-01-15", short_shares="2000000"
    )
    bundle = build_bundle("TESTD", [conflict_a, conflict_b], "2026-03-01T12:00:00Z")
    state, _ = classify_domain_coverage(bundle, CoverageDomain.PUBLISHED_SHORT_INTEREST)
    assert state is DomainCoverageState.CONFLICTED


def test_revision_chain_is_present_not_conflicted():
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
    state, _ = classify_domain_coverage(bundle, CoverageDomain.PUBLISHED_SHORT_INTEREST)
    assert state is DomainCoverageState.PRESENT


def test_partial_bar_domain_is_partial():
    partial_bar = make_bar(status="PARTIAL", source_record_id="bar-partial")
    bundle = build_bundle("TESTD", [partial_bar], "2026-03-01T12:00:00Z")
    state, _ = classify_domain_coverage(bundle, CoverageDomain.MARKET_BARS)
    assert state is DomainCoverageState.PARTIAL


def test_completed_bar_domain_is_present():
    bar = make_bar()
    bundle = build_bundle("TESTD", [bar], "2026-03-01T12:00:00Z")
    state, _ = classify_domain_coverage(bundle, CoverageDomain.MARKET_BARS)
    assert state is DomainCoverageState.PRESENT


def test_domain_never_evaluated_by_bundle_policy_is_unknown():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    state, _ = classify_domain_coverage(bundle, CoverageDomain.NEWS)
    assert state is DomainCoverageState.UNKNOWN


def test_zero_valued_short_interest_is_present_not_missing():
    si = make_short_interest(short_shares="0")
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    state, _ = classify_domain_coverage(bundle, CoverageDomain.PUBLISHED_SHORT_INTEREST)
    assert state is DomainCoverageState.PRESENT


def test_sec_filing_reporting_period_domain_present():
    sec = make_sec_filing()
    bundle = build_bundle("TESTD", [sec], "2026-03-01T12:00:00Z", include_sec_filings_domain=True)
    state, _ = classify_domain_coverage(bundle, CoverageDomain.SEC_FILINGS)
    assert state is DomainCoverageState.PRESENT


def test_coverage_snapshot_order_invariant_to_requested_domain_order():
    si = make_short_interest()
    bar = make_bar()
    bundle = build_bundle("TESTD", [si, bar], "2026-03-01T12:00:00Z")
    a = build_domain_coverage_snapshot(
        bundle, (CoverageDomain.MARKET_BARS, CoverageDomain.PUBLISHED_SHORT_INTEREST)
    )
    b = build_domain_coverage_snapshot(
        bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.MARKET_BARS)
    )
    assert a.deterministic_id == b.deterministic_id
    assert a.coverage_by_domain == b.coverage_by_domain


def test_coverage_snapshot_order_invariant_to_observation_order():
    si = make_short_interest()
    bar = make_bar()
    bundle_a = build_bundle("TESTD", [si, bar], "2026-03-01T12:00:00Z")
    bundle_b = build_bundle("TESTD", [bar, si], "2026-03-01T12:00:00Z")
    domains = (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.MARKET_BARS)
    a = build_domain_coverage_snapshot(bundle_a, domains)
    b = build_domain_coverage_snapshot(bundle_b, domains)
    assert a.deterministic_id == b.deterministic_id


def test_deterministic_id_stable_across_rebuilds():
    si = make_short_interest()
    bundle_a = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    bundle_b = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    domains = (CoverageDomain.PUBLISHED_SHORT_INTEREST,)
    a = build_domain_coverage_snapshot(bundle_a, domains)
    b = build_domain_coverage_snapshot(bundle_b, domains)
    assert a.deterministic_id == b.deterministic_id


def test_no_score_or_candidate_label_field_on_snapshot():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    snapshot = build_domain_coverage_snapshot(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    field_names = set(type(snapshot).model_fields)
    for forbidden in ("score", "rank", "recommendation", "grade", "label"):
        assert forbidden not in field_names

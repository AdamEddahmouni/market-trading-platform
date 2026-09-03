from squeeze_core.evidence import CoverageDomain
from squeeze_core.readiness import build_domain_coverage_snapshot, build_missingness_summary
from squeeze_core.readiness.models import MissingnessCategory
from squeeze_core.readiness.policies import lookup_policy

from .conftest import build_bundle, make_bar, make_short_interest


def test_missing_domain_counted():
    si = make_short_interest()
    bundle = build_bundle(
        "TESTD", [si], "2026-03-01T12:00:00Z", include_market_bars_domain=True
    )
    policy = lookup_policy("DAYS_TO_COVER")
    snapshot = build_domain_coverage_snapshot(bundle, policy.required_domains)
    summary = build_missingness_summary(bundle, snapshot, policy=policy)
    assert summary.missing_domain_count == 1
    entry = next(e for e in summary.missing_by_domain if e.domain is CoverageDomain.MARKET_BARS)
    assert MissingnessCategory.MISSING_DOMAIN in entry.categories


def test_missing_required_metric_counted():
    si = make_short_interest()
    bar = make_bar()
    bundle = build_bundle("TESTD", [si, bar], "2026-03-01T12:00:00Z")
    policy = lookup_policy("RELATIVE_VOLUME")
    snapshot = build_domain_coverage_snapshot(bundle, policy.required_domains)
    summary = build_missingness_summary(bundle, snapshot, policy=policy, metric_results=())
    assert "MEAN_VOLUME_BASELINE" in summary.missing_required_inputs


def test_unknown_availability_counted_distinctly_from_missing():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    snapshot = build_domain_coverage_snapshot(
        bundle, (CoverageDomain.NEWS, CoverageDomain.BORROW_FEE)
    )
    summary = build_missingness_summary(bundle, snapshot)
    news_entry = next(e for e in summary.missing_by_domain if e.domain is CoverageDomain.NEWS)
    borrow_entry = next(e for e in summary.missing_by_domain if e.domain is CoverageDomain.BORROW_FEE)
    assert MissingnessCategory.UNKNOWN_AVAILABILITY in news_entry.categories
    assert MissingnessCategory.MISSING_DOMAIN in borrow_entry.categories
    assert news_entry.categories != borrow_entry.categories
    assert CoverageDomain.NEWS in summary.unknown_by_domain


def test_zero_value_short_interest_not_counted_as_missing():
    si = make_short_interest(short_shares="0")
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    snapshot = build_domain_coverage_snapshot(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    summary = build_missingness_summary(bundle, snapshot)
    assert summary.missing_domain_count == 0


def test_conflict_not_counted_as_missing():
    a = make_short_interest(source_record_id="si-a", settlement_date="2026-01-15", short_shares="1000000")
    b = make_short_interest(source_record_id="si-b", settlement_date="2026-01-15", short_shares="2000000")
    bundle = build_bundle("TESTD", [a, b], "2026-03-01T12:00:00Z")
    snapshot = build_domain_coverage_snapshot(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    summary = build_missingness_summary(bundle, snapshot)
    assert summary.missing_domain_count == 0


def test_cancelled_input_classified_separately_from_missing():
    cancelled = make_short_interest(
        source_record_id="si-cancel",
        settlement_date="2026-01-15",
        publication_date="2026-02-05",
        revision_status="CANCELLED",
        revision_number=1,
        supersedes_source_record_id="si-original-not-present",
    )
    bundle = build_bundle("TESTD", [cancelled], "2026-03-01T12:00:00Z")
    snapshot = build_domain_coverage_snapshot(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    summary = build_missingness_summary(bundle, snapshot)
    assert summary.missing_domain_count == 0
    assert not summary.missing_by_domain


def test_deterministic_counts_across_two_builds():
    si = make_short_interest()
    bundle_a = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    bundle_b = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    policy = lookup_policy("DAYS_TO_COVER")
    snapshot_a = build_domain_coverage_snapshot(bundle_a, policy.required_domains)
    snapshot_b = build_domain_coverage_snapshot(bundle_b, policy.required_domains)
    summary_a = build_missingness_summary(bundle_a, snapshot_a, policy=policy)
    summary_b = build_missingness_summary(bundle_b, snapshot_b, policy=policy)
    assert summary_a.deterministic_id == summary_b.deterministic_id


def test_no_default_value_substitution_field():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    snapshot = build_domain_coverage_snapshot(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    summary = build_missingness_summary(bundle, snapshot)
    field_names = set(type(summary).model_fields)
    for forbidden in ("default_value", "substituted_value", "fallback"):
        assert forbidden not in field_names

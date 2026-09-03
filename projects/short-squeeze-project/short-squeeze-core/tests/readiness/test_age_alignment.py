from decimal import Decimal

from squeeze_core.evidence import CoverageDomain
from squeeze_core.readiness import build_evidence_age_alignment
from squeeze_core.readiness.diagnostics import ReadinessDiagnosticCode

from .conftest import build_bundle, make_bar, make_borrow, make_short_interest


def test_two_domains_identical_availability_age():
    # Published-short-interest's effective_timestamp is its RECEIPT time (Phase 1
    # treats publication-date-only records as effective once received, given
    # uncertain exact publication timing), while borrow fee's effective_timestamp is
    # its own provider-stamped time directly -- aligning provider_timestamp with the
    # short-interest receipt time makes both domains' representative ages equal.
    si = make_short_interest(ingested_at="2026-02-01T00:00:00Z")
    fee, _ = make_borrow(ingested_at="2026-02-01T00:00:00Z", provider_timestamp="2026-02-01T00:00:00Z")
    bundle = build_bundle("TESTD", [si, fee], "2026-02-01T00:00:00Z")
    alignment = build_evidence_age_alignment(
        bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.BORROW_FEE)
    )
    entries = {e.domain: e.age_seconds for e in alignment.domain_ages}
    assert entries[CoverageDomain.PUBLISHED_SHORT_INTEREST] == entries[CoverageDomain.BORROW_FEE]
    assert alignment.age_spread_seconds == 0


def test_two_domains_different_ages():
    si = make_short_interest()
    bar = make_bar()
    bundle = build_bundle("TESTD", [si, bar], "2026-03-01T12:00:00Z")
    alignment = build_evidence_age_alignment(
        bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.MARKET_BARS)
    )
    assert alignment.age_spread_seconds is not None
    assert alignment.age_spread_seconds == alignment.oldest_age_seconds - alignment.youngest_age_seconds
    assert alignment.age_spread_seconds > 0


def test_three_domain_minimum_maximum_spread():
    si = make_short_interest()
    fee, availability = make_borrow()
    bundle = build_bundle("TESTD", [si, fee, availability], "2026-03-01T12:00:00Z")
    alignment = build_evidence_age_alignment(
        bundle,
        (
            CoverageDomain.PUBLISHED_SHORT_INTEREST,
            CoverageDomain.BORROW_FEE,
            CoverageDomain.BORROW_AVAILABILITY,
        ),
    )
    ages = [e.age_seconds for e in alignment.domain_ages]
    assert alignment.youngest_age_seconds == min(ages)
    assert alignment.oldest_age_seconds == max(ages)
    assert alignment.domain_count == 3


def test_single_comparable_domain():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    alignment = build_evidence_age_alignment(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    assert alignment.age_spread_seconds == 0
    assert any(
        d.code is ReadinessDiagnosticCode.AGE_ALIGNMENT_SINGLE_DOMAIN_ONLY
        for d in alignment.diagnostics
    )


def test_no_comparable_domains():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    alignment = build_evidence_age_alignment(bundle, (CoverageDomain.BORROW_FEE,))
    assert alignment.youngest_age_seconds is None
    assert alignment.oldest_age_seconds is None
    assert alignment.age_spread_seconds is None
    assert alignment.missing_age_domains == (CoverageDomain.BORROW_FEE,)
    assert any(
        d.code is ReadinessDiagnosticCode.AGE_ALIGNMENT_NO_COMPARABLE_DOMAINS
        for d in alignment.diagnostics
    )


def test_unknown_domain_excluded_from_comparable_ages():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    alignment = build_evidence_age_alignment(bundle, (CoverageDomain.NEWS,))
    assert alignment.domain_count == 0
    assert alignment.missing_age_domains == (CoverageDomain.NEWS,)


def test_exact_integer_second_arithmetic():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    alignment = build_evidence_age_alignment(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    age = alignment.domain_ages[0].age_seconds
    assert isinstance(age, int)


def test_deterministic_mean_age():
    si = make_short_interest()
    fee, _ = make_borrow()
    bundle = build_bundle("TESTD", [si, fee], "2026-03-01T12:00:00Z")
    alignment = build_evidence_age_alignment(
        bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.BORROW_FEE)
    )
    ages = [e.age_seconds for e in alignment.domain_ages]
    expected_mean = (Decimal(ages[0]) + Decimal(ages[1])) / Decimal(2)
    assert alignment.mean_age_seconds == expected_mean


def test_age_alignment_order_invariant():
    si = make_short_interest()
    fee, _ = make_borrow()
    bundle = build_bundle("TESTD", [si, fee], "2026-03-01T12:00:00Z")
    a = build_evidence_age_alignment(
        bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.BORROW_FEE)
    )
    b = build_evidence_age_alignment(
        bundle, (CoverageDomain.BORROW_FEE, CoverageDomain.PUBLISHED_SHORT_INTEREST)
    )
    assert a.deterministic_id == b.deterministic_id


def test_availability_age_and_reporting_period_age_remain_distinct():
    # Old short-interest reporting period (2026-01-15) with a recent receipt --
    # availability age (time since received/effective) is small, but the
    # reporting-period age is large. The two must never be collapsed into one number.
    from squeeze_core.readiness import build_reporting_period_alignment

    si = make_short_interest(ingested_at="2026-02-28T00:00:00Z")
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    age = build_evidence_age_alignment(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    reporting = build_reporting_period_alignment(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    availability_age = age.domain_ages[0].age_seconds
    reporting_age = reporting.reporting_period_by_domain[0].reporting_period_age_seconds
    assert availability_age != reporting_age
    assert reporting_age > availability_age


def test_no_staleness_or_threshold_field_on_age_alignment():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    alignment = build_evidence_age_alignment(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    field_names = set(type(alignment).model_fields)
    for forbidden in ("stale", "fresh", "threshold", "acceptable"):
        assert forbidden not in field_names

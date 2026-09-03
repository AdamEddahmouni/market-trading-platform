from squeeze_core.evidence import CoverageDomain
from squeeze_core.readiness import build_reporting_period_alignment
from squeeze_core.readiness.diagnostics import ReadinessDiagnosticCode

from .conftest import build_bundle, make_bar, make_sec_filing, make_short_interest


def test_same_reporting_period_end_across_two_applicable_domains():
    si = make_short_interest(settlement_date="2026-01-15")
    sec = make_sec_filing(period_of_report="2026-01-15")
    bundle = build_bundle(
        "TESTD", [si, sec], "2026-03-01T12:00:00Z", include_sec_filings_domain=True
    )
    alignment = build_reporting_period_alignment(
        bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.SEC_FILINGS)
    )
    assert alignment.earliest_reporting_period_end == alignment.latest_reporting_period_end
    assert alignment.reporting_period_spread_seconds == 0


def test_different_reporting_period_ends():
    si = make_short_interest(settlement_date="2026-01-15")
    sec = make_sec_filing(
        period_of_report="2025-12-31", filed_at="2026-01-20", accepted_at="2026-01-20T14:30:00Z"
    )
    bundle = build_bundle(
        "TESTD", [si, sec], "2026-03-01T12:00:00Z", include_sec_filings_domain=True
    )
    alignment = build_reporting_period_alignment(
        bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.SEC_FILINGS)
    )
    assert alignment.earliest_reporting_period_end != alignment.latest_reporting_period_end
    assert alignment.reporting_period_spread_seconds == 15 * 86400


def test_domain_without_reporting_period_semantics_is_recorded_as_missing():
    bar = make_bar()
    bundle = build_bundle("TESTD", [bar], "2026-03-01T12:00:00Z")
    alignment = build_reporting_period_alignment(bundle, (CoverageDomain.MARKET_BARS,))
    assert alignment.missing_reporting_period_domains == (CoverageDomain.MARKET_BARS,)
    assert any(
        d.code is ReadinessDiagnosticCode.AGE_ALIGNMENT_REPORTING_PERIOD_NOT_APPLICABLE
        for d in alignment.diagnostics
    )


def test_missing_reporting_period_field_recorded_as_missing():
    bundle = build_bundle("TESTD", [], "2026-03-01T12:00:00Z")
    alignment = build_reporting_period_alignment(
        bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,)
    )
    assert alignment.missing_reporting_period_domains == (CoverageDomain.PUBLISHED_SHORT_INTEREST,)


def test_short_interest_reporting_period_preserved_exactly():
    si = make_short_interest(settlement_date="2026-01-15")
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    alignment = build_reporting_period_alignment(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    entry = alignment.reporting_period_by_domain[0]
    assert str(entry.reporting_period_end) == "2026-01-15"


def test_sec_filing_reporting_period_preserved_exactly():
    sec = make_sec_filing(period_of_report="2026-01-15")
    bundle = build_bundle("TESTD", [sec], "2026-03-01T12:00:00Z", include_sec_filings_domain=True)
    alignment = build_reporting_period_alignment(bundle, (CoverageDomain.SEC_FILINGS,))
    entry = alignment.reporting_period_by_domain[0]
    assert str(entry.reporting_period_end) == "2026-01-15"


def test_publication_time_not_substituted_for_period_end():
    si = make_short_interest(settlement_date="2026-01-15", publication_date="2026-01-25")
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    alignment = build_reporting_period_alignment(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    entry = alignment.reporting_period_by_domain[0]
    assert str(entry.reporting_period_end) == "2026-01-15"
    assert str(entry.reporting_period_end) != "2026-01-25"


def test_receipt_time_not_substituted_for_period_end():
    si = make_short_interest(settlement_date="2026-01-15", ingested_at="2026-02-20T00:00:00Z")
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    alignment = build_reporting_period_alignment(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    entry = alignment.reporting_period_by_domain[0]
    assert str(entry.reporting_period_end) == "2026-01-15"


def test_earliest_and_latest_period_selection():
    si = make_short_interest(settlement_date="2026-01-15")
    sec = make_sec_filing(
        period_of_report="2026-02-10", filed_at="2026-02-20", accepted_at="2026-02-20T14:30:00Z"
    )
    bundle = build_bundle(
        "TESTD", [si, sec], "2026-03-01T12:00:00Z", include_sec_filings_domain=True
    )
    alignment = build_reporting_period_alignment(
        bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.SEC_FILINGS)
    )
    assert str(alignment.earliest_reporting_period_end) == "2026-01-15"
    assert str(alignment.latest_reporting_period_end) == "2026-02-10"


def test_reporting_alignment_order_invariant():
    si = make_short_interest(settlement_date="2026-01-15")
    sec = make_sec_filing(
        period_of_report="2026-02-10", filed_at="2026-02-20", accepted_at="2026-02-20T14:30:00Z"
    )
    bundle = build_bundle(
        "TESTD", [si, sec], "2026-03-01T12:00:00Z", include_sec_filings_domain=True
    )
    a = build_reporting_period_alignment(
        bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST, CoverageDomain.SEC_FILINGS)
    )
    b = build_reporting_period_alignment(
        bundle, (CoverageDomain.SEC_FILINGS, CoverageDomain.PUBLISHED_SHORT_INTEREST)
    )
    assert a.deterministic_id == b.deterministic_id


def test_no_alignment_score_field():
    si = make_short_interest()
    bundle = build_bundle("TESTD", [si], "2026-03-01T12:00:00Z")
    alignment = build_reporting_period_alignment(bundle, (CoverageDomain.PUBLISHED_SHORT_INTEREST,))
    field_names = set(type(alignment).model_fields)
    for forbidden in ("score", "grade", "stale", "fresh"):
        assert forbidden not in field_names

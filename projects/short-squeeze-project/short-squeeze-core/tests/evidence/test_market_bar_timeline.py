from datetime import datetime

from squeeze_core.adapters.market_bars import normalize_market_bar_record
from squeeze_core.evidence import (
    CoverageDomain,
    CoverageState,
    EvidenceDiagnosticCode,
    PointInTimeEvidencePolicy,
    build_point_in_time_evidence,
)
from squeeze_core.serialization import canonical_json_bytes

from tests.adapters.market_bars.test_models_and_parsing import record_values
from tests.adapters.market_bars.test_normalizer import context


def _bar(status, provider_id, publication, receipt, **updates):
    raw = record_values(
        status=status,
        provider_record_id=provider_id,
        source_record_id=provider_id,
        publication_timestamp=publication,
        **updates,
    )
    return normalize_market_bar_record(raw, context(receipt)).observations[0]


def lifecycle():
    partial = _bar(
        "PARTIAL",
        "bar-partial",
        "2026-01-15T09:30:30-05:00",
        "2026-01-15T14:30:31Z",
        close="10.15",
        volume="400",
    )
    complete = _bar(
        "COMPLETED",
        "bar-complete",
        "2026-01-15T09:31:01-05:00",
        "2026-01-15T14:31:02Z",
        supersedes_provider_record_id="bar-partial",
    )
    corrected = _bar(
        "CORRECTED",
        "bar-corrected",
        "2026-01-15T09:35:00-05:00",
        "2026-01-15T14:35:01Z",
        close="10.26",
        supersedes_provider_record_id="bar-complete",
        revision_number=1,
    )
    return partial, complete, corrected


def _bundle(as_of, observations=None):
    return build_point_in_time_evidence(
        "TESTA",
        lifecycle() if observations is None else observations,
        PointInTimeEvidencePolicy(
            as_of=datetime.fromisoformat(as_of.replace("Z", "+00:00")),
            allow_stale=True,
            include_market_bars_domain=True,
        ),
    )


def _bar_coverage(bundle):
    return next(item for item in bundle.source_coverage if item.domain is CoverageDomain.MARKET_BARS)


def test_before_partial_publication_no_bar_is_eligible():
    bundle = _bundle("2026-01-15T14:30:29Z")
    assert not [item for item in bundle.observations if item.event_type.value == "BAR"]
    assert _bar_coverage(bundle).state is CoverageState.MISSING
    assert EvidenceDiagnosticCode.EVIDENCE_BAR_NOT_YET_PUBLISHED in {item.code for item in bundle.diagnostics}


def test_after_partial_receipt_partial_bar_is_explicitly_eligible():
    bundle = _bundle("2026-01-15T14:30:31Z")
    bars = [item for item in bundle.observations if item.event_type.value == "BAR"]
    assert [item.source_record_id for item in bars] == ["bar-partial"]
    assert bars[0].provenance.provider_metadata["status"] == "PARTIAL"
    assert _bar_coverage(bundle).state is CoverageState.PARTIAL
    assert EvidenceDiagnosticCode.EVIDENCE_BAR_PARTIAL in {item.code for item in bundle.diagnostics}


def test_after_interval_end_before_completed_receipt_only_partial_is_known():
    bundle = _bundle("2026-01-15T14:31:01.500000Z")
    bars = [item for item in bundle.observations if item.event_type.value == "BAR"]
    assert [item.source_record_id for item in bars] == ["bar-partial"]
    assert EvidenceDiagnosticCode.EVIDENCE_BAR_NOT_YET_RECEIVED in {item.code for item in bundle.diagnostics}


def test_after_completed_receipt_both_records_are_preserved():
    bundle = _bundle("2026-01-15T14:31:02Z")
    bars = [item for item in bundle.observations if item.event_type.value == "BAR"]
    assert [item.source_record_id for item in bars] == ["bar-partial", "bar-complete"]
    assert _bar_coverage(bundle).state is CoverageState.PRESENT
    assert EvidenceDiagnosticCode.EVIDENCE_BAR_COMPLETED in {item.code for item in bundle.diagnostics}
    assert len(bundle.revision_relationships) == 1


def test_before_correction_receipt_prior_completed_value_remains_known():
    bundle = _bundle("2026-01-15T14:35:00.500000Z")
    bars = [item for item in bundle.observations if item.event_type.value == "BAR"]
    assert bars[-1].source_record_id == "bar-complete"
    assert EvidenceDiagnosticCode.EVIDENCE_BAR_CORRECTION_NOT_YET_AVAILABLE in {item.code for item in bundle.diagnostics}


def test_after_correction_receipt_correction_is_added_without_mutation():
    bundle = _bundle("2026-01-15T14:35:01Z")
    bars = [item for item in bundle.observations if item.event_type.value == "BAR"]
    assert [item.source_record_id for item in bars] == ["bar-partial", "bar-complete", "bar-corrected"]
    assert bars[0].payload.close != bars[-1].payload.close
    assert len(bundle.revision_relationships) == 2
    assert EvidenceDiagnosticCode.EVIDENCE_BAR_CORRECTION_AVAILABLE in {item.code for item in bundle.diagnostics}


def test_later_records_do_not_change_historical_bundle_bytes():
    all_records = lifecycle()
    earlier_before = _bundle("2026-01-15T14:30:31Z", all_records)
    earlier_after = _bundle("2026-01-15T14:30:31Z", all_records)
    assert canonical_json_bytes(earlier_before) == canonical_json_bytes(earlier_after)


def test_bar_ages_keep_interval_publication_capture_and_availability_separate():
    captured = _bar(
        "COMPLETED",
        "captured",
        "2026-01-15T09:31:01-05:00",
        "2026-01-15T14:31:02Z",
        capture_timestamp="2026-01-15T09:31:01.500000-05:00",
    )
    bundle = _bundle("2026-01-15T14:32:00Z", (captured,))
    age = bundle.observation_ages[0]
    assert age.interval_age_ms == 60_000
    assert age.publication_age_ms == 59_000
    assert age.capture_age_ms == 58_500
    assert age.availability_age_ms == 58_000


def test_market_bar_coverage_is_independent_when_required_but_absent():
    bundle = _bundle("2026-01-15T14:32:00Z", ())
    assert _bar_coverage(bundle).state is CoverageState.MISSING
    assert EvidenceDiagnosticCode.EVIDENCE_MISSING_MARKET_BARS in {item.code for item in bundle.diagnostics}

"""Unit tests for the offline local historical bar-intake workflow (batch 03)."""

import hashlib
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from squeeze_core.acquisition.local_bar_intake import (
    CaseAssociationMapping,
    ColumnMappingProfile,
    IntakeManifest,
    build_intake_summary,
    normalize_from_bytes,
    validate_artifact_bytes,
    validate_case_association,
)
from squeeze_core.acquisition.local_bar_intake.normalization import _PARSE_ERROR_CODES
from squeeze_core.acquisition.local_bar_intake.semantics import (
    ArtifactFormat,
    BarInterval,
    BarSession,
    CorporateActionHandling,
    DataTimeBasis,
    DuplicatePolicy,
    IntakeReasonCode,
    IntakeValidationStatus,
    IntendedUse,
    PriceAdjustmentSemantics,
    SessionCoveragePolicy,
    SortExpectation,
    ThousandsSeparatorPolicy,
    TimestampSemantics,
    ValueAuthenticity,
    VolumeAdjustmentSemantics,
)


HEADER = "ts,symbol,venue,o,h,l,c,v,n,vw,ccy"
VALID_ROWS = (
    "2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10.00,10.50,9.90,10.20,1000,12,10.15,USD",
    "2026-07-18T13:35:00,ZZAA,DEMO_VENUE,10.20,10.62,10.10,10.55,2000,20,10.41,USD",
)


def _csv(*rows: str) -> bytes:
    return ("\n".join((HEADER, *rows)) + "\n").encode("utf-8")


def _profile(**over) -> ColumnMappingProfile:
    base = dict(
        profile_id="p1", delimiter=",", encoding="utf-8", has_header=True,
        timestamp_column="ts", symbol_column="symbol", venue_column="venue",
        open_column="o", high_column="h", low_column="l", close_column="c",
        volume_column="v", trade_count_column="n", vwap_column="vw", currency_column="ccy",
        decimal_separator=".", thousands_separator_policy=ThousandsSeparatorPolicy.DISALLOW,
        null_tokens=("",), sort_expectation=SortExpectation.STABLE_SORT_BY_EVENT_START,
        duplicate_policy=DuplicatePolicy.COLLAPSE_IDENTICAL_REJECT_CONFLICTING,
    )
    base.update(over)
    return ColumnMappingProfile(**base)


def _manifest(content: bytes, **over) -> IntakeManifest:
    base = dict(
        bundle_id="b1", provider_name="DEMO_PROVIDER",
        provider_product_or_export_name="Synthetic CSV",
        user_entitlement_assertion="synthetic fixture", license_or_terms_reference=None,
        retrieval_time=datetime(2026, 7, 20, 9, tzinfo=UTC),
        export_time=datetime(2026, 7, 20, 8, tzinfo=UTC),
        artifact_relative_path="raw/bars.csv",
        artifact_sha256=hashlib.sha256(content).hexdigest(),
        artifact_byte_length=len(content), artifact_media_type="text/csv",
        artifact_format=ArtifactFormat.CSV, provider_symbol="ZZAA", canonical_symbol="ZZAA",
        market_or_venue="DEMO_VENUE", bar_interval=BarInterval.FIVE_MINUTES,
        event_timezone="UTC", timestamp_semantics=TimestampSemantics.START,
        session_coverage=BarSession.REGULAR,
        session_coverage_policy=SessionCoveragePolicy.REQUIRE_CONTINUOUS,
        price_adjustment_semantics=PriceAdjustmentSemantics.RAW_UNADJUSTED,
        volume_adjustment_semantics=VolumeAdjustmentSemantics.RAW_UNADJUSTED,
        corporate_action_handling=CorporateActionHandling.RAW_NO_ADJUSTMENT,
        data_time_basis=DataTimeBasis.HISTORICAL,
        value_authenticity=ValueAuthenticity.SYNTHETIC_FIXTURE,
        intended_use=IntendedUse.INFRASTRUCTURE_FIXTURE,
        expected_start_time=datetime(2026, 7, 18, 13, 30, tzinfo=UTC),
        expected_end_time=datetime(2026, 7, 18, 14, 0, tzinfo=UTC),
        column_mapping_profile_id="p1", notes=None,
    )
    base.update(over)
    return IntakeManifest(**base)


def _codes(outcome) -> set[str]:
    return {code.value for code in outcome.diagnostics.bundle_reason_codes}


# --- Acceptance and determinism -------------------------------------------------

def test_valid_csv_bundle_accepted_and_bars_normalized():
    content = _csv(*VALID_ROWS)
    outcome = normalize_from_bytes(_manifest(content), _profile(), content)
    assert outcome.diagnostics.status is IntakeValidationStatus.ACCEPTED
    assert outcome.bar_set is not None and len(outcome.bar_set.bars) == 2
    first = outcome.bar_set.bars[0]
    assert first.open == Decimal("10.00") and first.high == Decimal("10.50")
    assert first.event_start_time == datetime(2026, 7, 18, 13, 30, tzinfo=UTC)
    assert first.event_end_time == datetime(2026, 7, 18, 13, 35, tzinfo=UTC)


def test_repeated_normalization_is_byte_identical():
    content = _csv(*VALID_ROWS)
    manifest, profile = _manifest(content), _profile()
    from squeeze_core.serialization import canonical_json_bytes
    a = canonical_json_bytes(normalize_from_bytes(manifest, profile, content).bar_set)
    b = canonical_json_bytes(normalize_from_bytes(manifest, profile, content).bar_set)
    assert a == b


# --- Artifact integrity ---------------------------------------------------------

def test_sha256_tampering_rejected():
    content = _csv(*VALID_ROWS)
    report = validate_artifact_bytes(_manifest(content, artifact_sha256="0" * 64), content)
    assert report.status is IntakeValidationStatus.REJECTED
    assert IntakeReasonCode.ARTIFACT_SHA256_MISMATCH in report.reason_codes


def test_byte_length_tampering_rejected():
    content = _csv(*VALID_ROWS)
    report = validate_artifact_bytes(
        _manifest(content, artifact_byte_length=len(content) + 1), content
    )
    assert report.status is IntakeValidationStatus.REJECTED
    assert IntakeReasonCode.ARTIFACT_BYTE_LENGTH_MISMATCH in report.reason_codes


def test_missing_artifact_rejected():
    content = _csv(*VALID_ROWS)
    report = validate_artifact_bytes(_manifest(content), None)
    assert report.status is IntakeValidationStatus.REJECTED
    assert IntakeReasonCode.ARTIFACT_MISSING in report.reason_codes


def test_non_csv_format_rejected():
    content = _csv(*VALID_ROWS)
    report = validate_artifact_bytes(
        _manifest(content, artifact_media_type="application/json",
                  artifact_format=ArtifactFormat.JSON), content
    )
    assert IntakeReasonCode.UNSUPPORTED_FORMAT in report.reason_codes


# --- Manifest / declaration -----------------------------------------------------

def test_malformed_manifest_missing_field_raises():
    with pytest.raises(ValidationError):
        IntakeManifest.model_validate({"bundle_id": "b1"})


def test_absolute_artifact_path_is_rejected_at_construction():
    content = _csv(*VALID_ROWS)
    with pytest.raises(ValidationError):
        _manifest(content, artifact_relative_path="C:/secrets/bars.csv")
    with pytest.raises(ValidationError):
        _manifest(content, artifact_relative_path="/etc/passwd")


def test_absolute_path_excluded_from_identity():
    # The identity canonicalizer drops any 'absolute_path' key entirely.
    from squeeze_core.acquisition.identifiers import deterministic_acquisition_id
    a = deterministic_acquisition_id({"x": 1, "absolute_path": "C:/a"})
    b = deterministic_acquisition_id({"x": 1, "absolute_path": "/tmp/b"})
    assert a == b


def test_missing_interval_rejected_at_construction():
    content = _csv(*VALID_ROWS)
    base = _manifest(content).model_dump(mode="python")
    base.pop("bar_interval")
    base["deterministic_id"] = None
    with pytest.raises(ValidationError):
        IntakeManifest.model_validate(base)


def test_session_based_interval_unsupported_this_batch():
    content = _csv(*VALID_ROWS)
    outcome = normalize_from_bytes(
        _manifest(content, bar_interval=BarInterval.ONE_DAY), _profile(), content
    )
    assert outcome.diagnostics.status is IntakeValidationStatus.REJECTED
    assert IntakeReasonCode.UNSUPPORTED_INTERVAL.value in _codes(outcome)


def test_unknown_timezone_rejected():
    content = _csv(*VALID_ROWS)
    outcome = normalize_from_bytes(
        _manifest(content, event_timezone="Nowhere/Unknown"), _profile(), content
    )
    assert outcome.diagnostics.status is IntakeValidationStatus.REJECTED
    assert IntakeReasonCode.UNKNOWN_TIMEZONE.value in _codes(outcome)


def test_missing_timestamp_semantics_rejected():
    content = _csv(*VALID_ROWS)
    outcome = normalize_from_bytes(
        _manifest(content, timestamp_semantics=TimestampSemantics.UNKNOWN), _profile(), content
    )
    assert IntakeReasonCode.MISSING_TIMESTAMP_SEMANTICS.value in _codes(outcome)


def test_missing_adjustment_semantics_rejected():
    content = _csv(*VALID_ROWS)
    outcome = normalize_from_bytes(
        _manifest(content, price_adjustment_semantics=PriceAdjustmentSemantics.UNKNOWN,
                  corporate_action_handling=CorporateActionHandling.UNKNOWN),
        _profile(), content,
    )
    assert IntakeReasonCode.MISSING_ADJUSTMENT_SEMANTICS.value in _codes(outcome)


def test_contradictory_adjustment_semantics_rejected():
    content = _csv(*VALID_ROWS)
    outcome = normalize_from_bytes(
        _manifest(content, price_adjustment_semantics=PriceAdjustmentSemantics.SPLIT_ADJUSTED),
        _profile(), content,
    )
    assert IntakeReasonCode.CONTRADICTORY_ADJUSTMENT_SEMANTICS.value in _codes(outcome)


def test_ambiguous_timezone_reason_mapping():
    # The parser's ambiguous-local-time error maps to AMBIGUOUS_TIMEZONE.
    assert _PARSE_ERROR_CODES["BAR_AMBIGUOUS_LOCAL_TIME"] is IntakeReasonCode.AMBIGUOUS_TIMEZONE

    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        ZoneInfo("America/New_York")
    except (ZoneInfoNotFoundError, KeyError):
        return  # IANA DB unavailable; the mapping assertion above still guards the path
    ambiguous = _csv("2025-11-02T01:30:00,ZZAA,DEMO_VENUE,10,11,9,10,1,1,10,USD")
    outcome = normalize_from_bytes(
        _manifest(ambiguous, event_timezone="America/New_York",
                  expected_start_time=datetime(2025, 11, 2, 0, tzinfo=UTC),
                  expected_end_time=datetime(2025, 11, 2, 23, tzinfo=UTC)),
        _profile(), ambiguous,
    )
    assert IntakeReasonCode.AMBIGUOUS_TIMEZONE.value in _codes(outcome)


# --- Value / row integrity ------------------------------------------------------

def test_invalid_ohlc_rejected():
    content = _csv("2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10,9,11,10,1,1,10,USD")
    outcome = normalize_from_bytes(_manifest(content), _profile(), content)
    assert IntakeReasonCode.INVALID_OHLC_RELATIONSHIP.value in _codes(outcome)
    assert outcome.bar_set is None


def test_negative_volume_rejected():
    content = _csv("2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10,11,9,10,-1,1,10,USD")
    outcome = normalize_from_bytes(_manifest(content), _profile(), content)
    assert IntakeReasonCode.NEGATIVE_VOLUME.value in _codes(outcome)


def test_negative_trade_count_rejected():
    content = _csv("2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10,11,9,10,1,-3,10,USD")
    outcome = normalize_from_bytes(_manifest(content), _profile(), content)
    assert IntakeReasonCode.NEGATIVE_TRADE_COUNT.value in _codes(outcome)


def test_malformed_decimal_rejected():
    content = _csv("2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10,1x,9,10,1,1,10,USD")
    outcome = normalize_from_bytes(_manifest(content), _profile(), content)
    assert IntakeReasonCode.MALFORMED_DECIMAL.value in _codes(outcome)


def test_nan_or_infinity_rejected():
    content = _csv("2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10,inf,9,10,1,1,10,USD")
    outcome = normalize_from_bytes(_manifest(content), _profile(), content)
    assert IntakeReasonCode.NAN_OR_INFINITY.value in _codes(outcome)


def test_missing_ohlc_never_inferred():
    content = _csv("2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10,,9,10,1,1,10,USD")
    outcome = normalize_from_bytes(_manifest(content), _profile(), content)
    assert IntakeReasonCode.MISSING_OHLC_VALUE.value in _codes(outcome)


def test_event_time_outside_coverage_rejected():
    content = _csv("2026-07-18T15:30:00,ZZAA,DEMO_VENUE,10,11,9,10,1,1,10,USD")
    outcome = normalize_from_bytes(_manifest(content), _profile(), content)
    assert IntakeReasonCode.EVENT_TIME_OUTSIDE_COVERAGE.value in _codes(outcome)


def test_symbol_mismatch_rejected():
    content = _csv("2026-07-18T13:30:00,WRONG,DEMO_VENUE,10,11,9,10,1,1,10,USD")
    outcome = normalize_from_bytes(_manifest(content), _profile(), content)
    assert IntakeReasonCode.SYMBOL_MISMATCH.value in _codes(outcome)


def test_venue_mismatch_rejected():
    content = _csv("2026-07-18T13:30:00,ZZAA,OTHER_VENUE,10,11,9,10,1,1,10,USD")
    outcome = normalize_from_bytes(_manifest(content), _profile(), content)
    assert IntakeReasonCode.MARKET_VENUE_MISMATCH.value in _codes(outcome)


# --- Cross-row integrity --------------------------------------------------------

def test_identical_duplicate_rows_collapsed_and_quarantined():
    row = "2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10,11,9,10,1,1,10,USD"
    content = _csv(row, row)
    outcome = normalize_from_bytes(_manifest(content), _profile(), content)
    assert outcome.diagnostics.status is IntakeValidationStatus.QUARANTINED
    assert outcome.bar_set is not None and len(outcome.bar_set.bars) == 1
    assert outcome.diagnostics.quarantined_count == 1


def test_conflicting_duplicate_rows_rejected():
    content = _csv(
        "2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10,11,9,10,1,1,10,USD",
        "2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10,11,9,10,999,1,10,USD",
    )
    outcome = normalize_from_bytes(_manifest(content), _profile(), content)
    assert outcome.diagnostics.status is IntakeValidationStatus.REJECTED
    assert IntakeReasonCode.CONFLICTING_DUPLICATE_BAR.value in _codes(outcome)


def test_overlapping_bars_rejected():
    content = _csv(
        "2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10,11,9,10,1,1,10,USD",
        "2026-07-18T13:32:00,ZZAA,DEMO_VENUE,10,11,9,10,1,1,10,USD",
    )
    outcome = normalize_from_bytes(_manifest(content), _profile(), content)
    assert IntakeReasonCode.OVERLAPPING_BARS.value in _codes(outcome)


def test_coverage_gap_rejected_when_continuity_required():
    content = _csv(
        "2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10,11,9,10,1,1,10,USD",
        "2026-07-18T13:45:00,ZZAA,DEMO_VENUE,10,11,9,10,1,1,10,USD",
    )
    outcome = normalize_from_bytes(_manifest(content), _profile(), content)
    assert IntakeReasonCode.COVERAGE_GAP.value in _codes(outcome)


def test_gap_allowed_when_policy_allows():
    content = _csv(
        "2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10,11,9,10,1,1,10,USD",
        "2026-07-18T13:45:00,ZZAA,DEMO_VENUE,10,11,9,10,1,1,10,USD",
    )
    outcome = normalize_from_bytes(
        _manifest(content, session_coverage_policy=SessionCoveragePolicy.ALLOW_GAPS),
        _profile(), content,
    )
    assert outcome.diagnostics.status is IntakeValidationStatus.ACCEPTED


def test_non_monotonic_rejected_when_presorted_required():
    content = _csv(
        "2026-07-18T13:35:00,ZZAA,DEMO_VENUE,10,11,9,10,1,1,10,USD",
        "2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10,11,9,10,1,1,10,USD",
    )
    outcome = normalize_from_bytes(
        _manifest(content, session_coverage_policy=SessionCoveragePolicy.ALLOW_GAPS),
        _profile(sort_expectation=SortExpectation.REQUIRE_PRESORTED), content,
    )
    assert IntakeReasonCode.NON_MONOTONIC_ORDER.value in _codes(outcome)


def test_source_row_provenance_preserved_after_stable_sort():
    # Rows supplied out of time order; STABLE_SORT reorders bars but preserves the
    # physical source_row_number of each row.
    content = _csv(
        "2026-07-18T13:35:00,ZZAA,DEMO_VENUE,10,11,9,10,1,1,10,USD",  # physical line 2
        "2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10,11,9,10,1,1,10,USD",  # physical line 3
    )
    outcome = normalize_from_bytes(
        _manifest(content, session_coverage_policy=SessionCoveragePolicy.ALLOW_GAPS),
        _profile(), content,
    )
    bars = outcome.bar_set.bars
    assert bars[0].event_start_time < bars[1].event_start_time
    assert bars[0].source_row_number == 3  # the 13:30 bar came from physical line 3
    assert bars[1].source_row_number == 2


# --- Provenance / safety --------------------------------------------------------

def test_current_value_as_historical_rejected():
    content = _csv(*VALID_ROWS)
    outcome = normalize_from_bytes(
        _manifest(content, data_time_basis=DataTimeBasis.CURRENT), _profile(), content
    )
    assert IntakeReasonCode.CURRENT_VALUE_AS_HISTORICAL.value in _codes(outcome)


def test_synthetic_value_as_historical_rejected():
    content = _csv(*VALID_ROWS)
    outcome = normalize_from_bytes(
        _manifest(content, intended_use=IntendedUse.HISTORICAL_EVIDENCE), _profile(), content
    )
    assert IntakeReasonCode.SYNTHETIC_VALUE_AS_HISTORICAL.value in _codes(outcome)


def test_price_adjustment_and_session_semantics_preserved_on_bars():
    content = _csv(*VALID_ROWS)
    outcome = normalize_from_bytes(
        _manifest(content, price_adjustment_semantics=PriceAdjustmentSemantics.RAW_UNADJUSTED),
        _profile(), content,
    )
    bar = outcome.bar_set.bars[0]
    assert bar.price_adjustment_semantics is PriceAdjustmentSemantics.RAW_UNADJUSTED
    assert bar.volume_adjustment_semantics is VolumeAdjustmentSemantics.RAW_UNADJUSTED
    assert bar.session is BarSession.REGULAR
    assert bar.value_authenticity is ValueAuthenticity.SYNTHETIC_FIXTURE


def test_event_time_distinct_from_retrieval_and_export_time():
    content = _csv(*VALID_ROWS)
    manifest = _manifest(content)
    outcome = normalize_from_bytes(manifest, _profile(), content)
    summary = build_intake_summary(
        manifest, validate_artifact_bytes(manifest, content), outcome.diagnostics,
        outcome.bar_set,
    )
    assert summary.retrieval_time == datetime(2026, 7, 20, 9, tzinfo=UTC)
    assert summary.export_time == datetime(2026, 7, 20, 8, tzinfo=UTC)
    assert summary.event_start_min == datetime(2026, 7, 18, 13, 30, tzinfo=UTC)
    assert summary.event_start_min != summary.retrieval_time != summary.export_time


# --- Case association (non-executing) ------------------------------------------

def _mapping(**over) -> CaseAssociationMapping:
    base = dict(
        case_id="CASE_1", canonical_symbol="ZZAA", frozen_detection_boundary_id="BND_1",
        requested_window_start=datetime(2026, 7, 18, 13, 30, tzinfo=UTC),
        requested_window_end=datetime(2026, 7, 19, 13, 30, tzinfo=UTC),
        required_interval=BarInterval.FIVE_MINUTES, required_session_coverage=BarSession.REGULAR,
        bundle_id="b1",
    )
    base.update(over)
    return CaseAssociationMapping(**base)


def test_case_mapping_requires_known_case_and_boundary_ids():
    result = validate_case_association(
        _mapping(), known_case_ids=frozenset(), known_boundary_ids=frozenset()
    )
    assert result.valid is False
    assert IntakeReasonCode.UNKNOWN_CASE_ID in result.reason_codes
    assert IntakeReasonCode.UNKNOWN_BOUNDARY_ID in result.reason_codes


def test_case_mapping_valid_against_known_references():
    content = _csv(*VALID_ROWS)
    result = validate_case_association(
        _mapping(), known_case_ids=frozenset({"CASE_1"}),
        known_boundary_ids=frozenset({"BND_1"}), manifest=_manifest(content),
    )
    assert result.valid is True


def test_case_mapping_never_computes_outcome_or_creates_phase_records():
    result = validate_case_association(
        _mapping(), known_case_ids=frozenset({"CASE_1"}),
        known_boundary_ids=frozenset({"BND_1"}),
    )
    assert result.outcome_computed is False
    assert result.phase_3a_or_3b_record_created is False


def test_case_mapping_detects_incompatible_symbol_and_interval():
    content = _csv(*VALID_ROWS)
    result = validate_case_association(
        _mapping(canonical_symbol="OTHER", required_interval=BarInterval.ONE_MINUTE),
        known_case_ids=frozenset({"CASE_1"}), known_boundary_ids=frozenset({"BND_1"}),
        manifest=_manifest(content),
    )
    assert result.valid is False
    assert IntakeReasonCode.CASE_SYMBOL_INCOMPATIBLE in result.reason_codes
    assert IntakeReasonCode.CASE_INTERVAL_INCOMPATIBLE in result.reason_codes

"""Deterministic, offline canonical fixtures for local-bar-intake batch 03.

Builds a single, unmistakably synthetic intake bundle (dummy provider and dummy
symbols) and renders every canonical batch-03 output document: the intake
contract, manifest, mapping profile, raw-artifact descriptor, artifact
validation, normalized bars (JSONL + CSV), normalization diagnostics, intake
summary, a non-executing case-association example and its validation, a set of
rejected-intake examples, and determinism anchors.

Everything is derived from in-memory synthetic bytes with fixed instants -- never
wall-clock, never network, never disk-order dependent -- so repeated builds are
byte-identical. No real market data, no acquisition, no outcome work, no Phase
3A/3B records, and no Phase 3E.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from squeeze_core.serialization import canonical_json_bytes

from .local_bar_intake.case_association import validate_case_association
from .local_bar_intake.contract import build_intake_contract
from .local_bar_intake.artifact_validation import describe_raw_artifact, validate_artifact_bytes
from .local_bar_intake.models import (
    CaseAssociationMapping,
    ColumnMappingProfile,
    IntakeManifest,
)
from .local_bar_intake.normalization import normalize_from_bytes
from .local_bar_intake.semantics import (
    ArtifactFormat,
    BarInterval,
    BarSession,
    CorporateActionHandling,
    DataTimeBasis,
    DuplicatePolicy,
    IntendedUse,
    PriceAdjustmentSemantics,
    SessionCoveragePolicy,
    SortExpectation,
    ThousandsSeparatorPolicy,
    TimestampSemantics,
    ValueAuthenticity,
    VolumeAdjustmentSemantics,
)
from .local_bar_intake.summary import (
    build_intake_summary,
    serialize_bars_csv,
    serialize_bars_jsonl,
)


BUNDLE_ID = "demo-zzaa-5m-2026-07-18"
PROFILE_ID = "demo-generic-ohlcv-csv.v1"
CASE_ID = "DEMO_CASE_ZZAA_5M"
BOUNDARY_ID = "DEMO_BOUNDARY_ZZAA_5M"

# Fixed instants (never wall-clock). Retrieval/export are distinct from event time.
_RETRIEVAL_TIME = datetime(2026, 7, 20, 9, 0, 0, tzinfo=UTC)
_EXPORT_TIME = datetime(2026, 7, 20, 8, 55, 0, tzinfo=UTC)
_COVERAGE_START = datetime(2026, 7, 18, 13, 30, 0, tzinfo=UTC)
_COVERAGE_END = datetime(2026, 7, 18, 14, 0, 0, tzinfo=UTC)

# Unmistakably synthetic raw artifact: dummy symbol ZZAA, six contiguous 5-minute
# UTC bars. LF line endings; no thousands separators; explicit header.
_RAW_CSV = (
    "timestamp,symbol,venue,open,high,low,close,volume,trades,vwap,currency\n"
    "2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10.00,10.50,9.90,10.20,1000,12,10.15,USD\n"
    "2026-07-18T13:35:00,ZZAA,DEMO_VENUE,10.20,10.62,10.10,10.55,2000,20,10.41,USD\n"
    "2026-07-18T13:40:00,ZZAA,DEMO_VENUE,10.55,10.70,10.40,10.45,1500,18,10.52,USD\n"
    "2026-07-18T13:45:00,ZZAA,DEMO_VENUE,10.45,10.80,10.30,10.75,1750,17,10.58,USD\n"
    "2026-07-18T13:50:00,ZZAA,DEMO_VENUE,10.75,10.95,10.60,10.62,1200,15,10.77,USD\n"
    "2026-07-18T13:55:00,ZZAA,DEMO_VENUE,10.62,10.68,10.11,10.20,1900,22,10.40,USD\n"
).encode("utf-8")


def build_column_mapping_profile() -> ColumnMappingProfile:
    return ColumnMappingProfile(
        profile_id=PROFILE_ID,
        delimiter=",",
        encoding="utf-8",
        has_header=True,
        timestamp_column="timestamp",
        symbol_column="symbol",
        venue_column="venue",
        open_column="open",
        high_column="high",
        low_column="low",
        close_column="close",
        volume_column="volume",
        trade_count_column="trades",
        vwap_column="vwap",
        currency_column="currency",
        decimal_separator=".",
        thousands_separator_policy=ThousandsSeparatorPolicy.DISALLOW,
        null_tokens=("", "NA", "null"),
        sort_expectation=SortExpectation.STABLE_SORT_BY_EVENT_START,
        duplicate_policy=DuplicatePolicy.COLLAPSE_IDENTICAL_REJECT_CONFLICTING,
    )


def build_valid_manifest() -> IntakeManifest:
    return IntakeManifest(
        bundle_id=BUNDLE_ID,
        provider_name="DEMO_HISTDATA_EXPORT",
        provider_product_or_export_name="Synthetic Intraday CSV (fixture)",
        user_entitlement_assertion=(
            "SYNTHETIC FIXTURE -- contains no real vendor data; entitlement not applicable."
        ),
        license_or_terms_reference="synthetic-fixture-no-license",
        retrieval_time=_RETRIEVAL_TIME,
        export_time=_EXPORT_TIME,
        artifact_relative_path="raw/valid-bars.csv",
        artifact_sha256=hashlib.sha256(_RAW_CSV).hexdigest(),
        artifact_byte_length=len(_RAW_CSV),
        artifact_media_type="text/csv",
        artifact_format=ArtifactFormat.CSV,
        provider_symbol="ZZAA",
        canonical_symbol="ZZAA",
        market_or_venue="DEMO_VENUE",
        bar_interval=BarInterval.FIVE_MINUTES,
        event_timezone="UTC",
        timestamp_semantics=TimestampSemantics.START,
        session_coverage=BarSession.REGULAR,
        session_coverage_policy=SessionCoveragePolicy.REQUIRE_CONTINUOUS,
        price_adjustment_semantics=PriceAdjustmentSemantics.RAW_UNADJUSTED,
        volume_adjustment_semantics=VolumeAdjustmentSemantics.RAW_UNADJUSTED,
        corporate_action_handling=CorporateActionHandling.RAW_NO_ADJUSTMENT,
        data_time_basis=DataTimeBasis.HISTORICAL,
        value_authenticity=ValueAuthenticity.SYNTHETIC_FIXTURE,
        intended_use=IntendedUse.INFRASTRUCTURE_FIXTURE,
        expected_start_time=_COVERAGE_START,
        expected_end_time=_COVERAGE_END,
        column_mapping_profile_id=PROFILE_ID,
        notes="Synthetic fixture bundle for batch 03 infrastructure verification.",
    )


def build_case_association_mapping() -> CaseAssociationMapping:
    return CaseAssociationMapping(
        case_id=CASE_ID,
        canonical_symbol="ZZAA",
        frozen_detection_boundary_id=BOUNDARY_ID,
        requested_window_start=_COVERAGE_START,
        requested_window_end=datetime(2026, 7, 19, 13, 30, 0, tzinfo=UTC),
        required_interval=BarInterval.FIVE_MINUTES,
        required_session_coverage=BarSession.REGULAR,
        bundle_id=BUNDLE_ID,
    )


# Rejected-intake scenarios. Each mutates the valid bundle in exactly one way and
# is normalized deterministically to record the resulting status and reason codes.
def _rejected_scenarios() -> list[dict]:
    manifest = build_valid_manifest()
    profile = build_column_mapping_profile()
    scenarios: list[dict] = []

    def record(name: str, description: str, *, manifest_override=None, content=None):
        used_content = _RAW_CSV if content is None else content
        updates = dict(manifest_override or {})
        # When a scenario supplies replacement bytes (and is not itself an artifact
        # tamper case), realign the declared hash/length so the intended row- or
        # manifest-level reason surfaces instead of an artifact mismatch.
        if (
            content is not None
            and "artifact_sha256" not in updates
            and "artifact_byte_length" not in updates
        ):
            updates["artifact_sha256"] = hashlib.sha256(used_content).hexdigest()
            updates["artifact_byte_length"] = len(used_content)
        used_manifest = (
            manifest if not updates
            else manifest.model_copy(update={**updates, "deterministic_id": None})
        )
        outcome = normalize_from_bytes(used_manifest, profile, used_content)
        scenarios.append({
            "scenario": name,
            "description": description,
            "normalization_status": outcome.diagnostics.status.value,
            "bundle_reason_codes": tuple(
                code.value for code in outcome.diagnostics.bundle_reason_codes
            ),
        })

    header = _RAW_CSV.split(b"\n", 1)[0].decode("ascii")

    def one_row(row: str) -> bytes:
        return (header + "\n" + row + "\n").encode("utf-8")

    record(
        "artifact_sha256_mismatch",
        "Manifest SHA-256 does not match the raw bytes (tamper).",
        manifest_override={"artifact_sha256": "0" * 64},
    )
    record(
        "artifact_byte_length_mismatch",
        "Manifest byte length does not match the raw bytes (tamper).",
        manifest_override={"artifact_byte_length": len(_RAW_CSV) + 1},
    )
    record(
        "invalid_ohlc_relationship",
        "A bar high is below open/close (impossible OHLC).",
        content=one_row("2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10.00,9.00,9.90,10.20,100,1,10.0,USD"),
    )
    record(
        "negative_volume",
        "A bar carries negative volume.",
        content=one_row("2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10.00,10.50,9.90,10.20,-5,1,10.0,USD"),
    )
    record(
        "malformed_decimal",
        "A price is not a valid decimal.",
        content=one_row("2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10.00,1x.0,9.90,10.20,100,1,10.0,USD"),
    )
    record(
        "non_finite_value",
        "A price is NaN.",
        content=one_row("2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10.00,nan,9.90,10.20,100,1,10.0,USD"),
    )
    record(
        "missing_ohlc_value",
        "A required OHLC value is missing and is never inferred.",
        content=one_row("2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10.00,,9.90,10.20,100,1,10.0,USD"),
    )
    record(
        "event_time_outside_coverage",
        "A bar falls outside the manifest's declared coverage window.",
        content=one_row("2026-07-18T15:30:00,ZZAA,DEMO_VENUE,10.00,10.50,9.90,10.20,100,1,10.0,USD"),
    )
    record(
        "symbol_mismatch",
        "A row symbol disagrees with the manifest's declared symbol.",
        content=one_row("2026-07-18T13:30:00,WRONG,DEMO_VENUE,10.00,10.50,9.90,10.20,100,1,10.0,USD"),
    )
    record(
        "conflicting_duplicate_bar",
        "Two rows share a timestamp but disagree on values.",
        content=one_row(
            "2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10.00,10.50,9.90,10.20,100,1,10.0,USD"
        )[:-1] + b"\n2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10.00,10.50,9.90,10.20,999,1,10.0,USD\n",
    )
    record(
        "overlapping_bars",
        "A later bar starts before the previous bar's end.",
        content=(
            header + "\n"
            + "2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10.00,10.50,9.90,10.20,100,1,10.0,USD\n"
            + "2026-07-18T13:32:00,ZZAA,DEMO_VENUE,10.20,10.50,9.90,10.20,100,1,10.0,USD\n"
        ).encode("utf-8"),
    )
    record(
        "coverage_gap",
        "Continuity is required but consecutive bars leave a gap.",
        content=(
            header + "\n"
            + "2026-07-18T13:30:00,ZZAA,DEMO_VENUE,10.00,10.50,9.90,10.20,100,1,10.0,USD\n"
            + "2026-07-18T13:45:00,ZZAA,DEMO_VENUE,10.20,10.50,9.90,10.20,100,1,10.0,USD\n"
        ).encode("utf-8"),
    )
    record(
        "current_value_as_historical",
        "The export is declared CURRENT and cannot be ingested as historical.",
        manifest_override={"data_time_basis": DataTimeBasis.CURRENT},
    )
    record(
        "synthetic_value_as_historical",
        "A synthetic fixture is declared as HISTORICAL_EVIDENCE.",
        manifest_override={"intended_use": IntendedUse.HISTORICAL_EVIDENCE},
    )
    record(
        "missing_timestamp_semantics",
        "The manifest leaves timestamp semantics UNKNOWN.",
        manifest_override={"timestamp_semantics": TimestampSemantics.UNKNOWN},
    )
    record(
        "contradictory_adjustment_semantics",
        "Adjusted prices are declared with RAW corporate-action handling.",
        manifest_override={
            "price_adjustment_semantics": PriceAdjustmentSemantics.SPLIT_ADJUSTED
        },
    )
    record(
        "unknown_timezone",
        "The declared event timezone cannot be resolved.",
        manifest_override={"event_timezone": "Nowhere/Unknown"},
    )
    return scenarios


def _json(value) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _anchor(name: str, value: str) -> str:
    return hashlib.sha256(f"{name}\0{value}".encode("utf-8")).hexdigest()


def build_batch03_documents() -> dict[str, bytes]:
    profile = build_column_mapping_profile()
    manifest = build_valid_manifest()
    raw_descriptor = describe_raw_artifact(manifest)
    artifact_report = validate_artifact_bytes(manifest, _RAW_CSV)
    outcome = normalize_from_bytes(manifest, profile, _RAW_CSV)
    assert outcome.bar_set is not None
    summary = build_intake_summary(manifest, artifact_report, outcome.diagnostics, outcome.bar_set)

    mapping = build_case_association_mapping()
    mapping_validation = validate_case_association(
        mapping,
        known_case_ids=frozenset({CASE_ID}),
        known_boundary_ids=frozenset({BOUNDARY_ID}),
        manifest=manifest,
    )

    rejected = {
        "schema_version": "1.0.0",
        "document": "phase_3d_batch_03_rejected_intake_examples",
        "note": (
            "Deterministic rejection/quarantine examples. Ambiguous or unsafe input is "
            "never repaired; each scenario records its status and reason codes."
        ),
        "examples": tuple(_rejected_scenarios()),
    }

    bars_jsonl = serialize_bars_jsonl(outcome.bar_set)
    bars_csv = serialize_bars_csv(outcome.bar_set)

    documents: dict[str, bytes] = {
        "intake-contract.json": _json(build_intake_contract()),
        "valid-raw-bars.csv": _RAW_CSV,
        "valid-intake-manifest.json": _json(manifest),
        "column-mapping-profile.json": _json(profile),
        "raw-artifact-manifest.json": _json(raw_descriptor),
        "artifact-validation.json": _json(artifact_report),
        "normalized-bars.jsonl": bars_jsonl,
        "normalized-bars.csv": bars_csv,
        "normalization-diagnostics.json": _json(outcome.diagnostics),
        "intake-summary.json": _json(summary),
        "case-association-example.json": _json(mapping),
        "case-association-validation.json": _json(mapping_validation),
        "rejected-intake-examples.json": _json(rejected),
    }

    raw_anchors = {
        "intake_contract": hashlib.sha256(documents["intake-contract.json"]).hexdigest(),
        "raw_artifact_sha256": manifest.artifact_sha256,
        "intake_manifest": str(manifest.deterministic_id),
        "column_mapping_profile": str(profile.deterministic_id),
        "raw_artifact_descriptor": str(raw_descriptor.deterministic_id),
        "artifact_validation": str(artifact_report.deterministic_id),
        "normalized_bar_set": str(outcome.bar_set.deterministic_id),
        "normalization_diagnostics": str(outcome.diagnostics.deterministic_id),
        "intake_summary": str(summary.deterministic_id),
        "case_association_mapping": str(mapping.deterministic_id),
        "case_association_validation": str(mapping_validation.deterministic_id),
        "normalized_bars_jsonl": hashlib.sha256(bars_jsonl).hexdigest(),
        "normalized_bars_csv": hashlib.sha256(bars_csv).hexdigest(),
        "rejected_intake_examples": hashlib.sha256(
            documents["rejected-intake-examples.json"]
        ).hexdigest(),
    }
    for bar in outcome.bar_set.bars:
        raw_anchors[f"bar::{bar.source_record_id}"] = str(bar.deterministic_id)

    anchors = {name: _anchor(name, value) for name, value in raw_anchors.items()}
    documents["determinism-anchors.json"] = _json({
        "schema_version": "1.0.0",
        "anchors": anchors,
    })
    documents["batch-03-fixture-metadata.json"] = _json({
        "schema_version": "1.0.0",
        "file_sha256": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in sorted(documents.items())
        },
        "fixture_classifications": ("SYNTHETIC_EDGE_CASE", "SYNTHETIC_FIXTURE"),
        "sensitive_content_included": False,
        "real_market_data_committed": False,
        "outcome_work_performed": False,
    })
    return dict(sorted(documents.items()))


__all__ = [
    "build_batch03_documents",
    "build_valid_manifest",
    "build_column_mapping_profile",
    "build_case_association_mapping",
]

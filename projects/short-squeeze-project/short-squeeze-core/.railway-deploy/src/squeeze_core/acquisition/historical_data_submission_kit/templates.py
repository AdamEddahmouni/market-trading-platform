"""Blank, fill-in templates for the three operator-supplied Batch 03 documents.

Each template is a syntactically valid JSON object that contains every field of the
corresponding Batch 03 model. Operator-supplied values use ``<REPLACE: ...>``
tokens; enum choices list the exact supported options; fields with safe defaults
carry those defaults. Templates are fill-in documents -- they are not required to
pass model validation until the operator replaces the placeholders and removes the
leading-underscore guidance blocks. No secrets, no real case IDs, safe to commit.
"""

from __future__ import annotations

from ..local_bar_intake.models import INTAKE_CONTRACT_VERSION, SCHEMA_VERSION
from ..local_bar_intake.semantics import (
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

# Field names that are template annotations only. The operator removes them before
# validation; they are chosen never to collide with a real model field name.
GUIDANCE_KEY = "_field_guidance"
WARNING_KEY = "_warning"


def _one_of(enum) -> str:
    return "<REPLACE: one of " + ", ".join(member.value for member in enum) + ">"


def build_intake_manifest_template() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "intake_contract_version": INTAKE_CONTRACT_VERSION,
        "bundle_id": "<REPLACE: unique bundle id, e.g. myprovider-abcd-5m-2026-01-15>",
        "provider_name": "<REPLACE: provider or data-source name>",
        "provider_product_or_export_name": "<REPLACE: product or export name>",
        "user_entitlement_assertion": (
            "<REPLACE: state that you are entitled to use this export under its terms>"
        ),
        "license_or_terms_reference": "<REPLACE-OR-NULL: license/terms reference, or null>",
        "retrieval_time": "<REPLACE: ISO-8601 UTC instant you retrieved it, e.g. 2026-01-16T10:00:00Z>",
        "export_time": "<REPLACE: ISO-8601 UTC instant the provider produced it, e.g. 2026-01-16T09:45:00Z>",
        "artifact_relative_path": "raw/<REPLACE: your-export.csv>",
        "artifact_sha256": "<REPLACE: 64-hex lowercase SHA-256 of the exact raw file>",
        "artifact_byte_length": "<REPLACE: integer byte length of the exact raw file>",
        "artifact_media_type": "text/csv",
        "artifact_format": ArtifactFormat.CSV.value,
        "provider_symbol": "<REPLACE: symbol exactly as the provider labels it>",
        "canonical_symbol": "<REPLACE: your canonical symbol for this instrument>",
        "market_or_venue": "<REPLACE: market or venue identifier>",
        "bar_interval": _one_of(BarInterval),
        "event_timezone": "<REPLACE: UTC, an explicit offset like -05:00, or an IANA zone>",
        "timestamp_semantics": _one_of(TimestampSemantics),
        "session_coverage": _one_of(BarSession),
        "session_coverage_policy": SessionCoveragePolicy.ALLOW_GAPS.value,
        "price_adjustment_semantics": _one_of(PriceAdjustmentSemantics),
        "volume_adjustment_semantics": _one_of(VolumeAdjustmentSemantics),
        "corporate_action_handling": _one_of(CorporateActionHandling),
        "data_time_basis": _one_of(DataTimeBasis),
        "value_authenticity": _one_of(ValueAuthenticity),
        "intended_use": _one_of(IntendedUse),
        "expected_start_time": "<REPLACE: ISO-8601 UTC start of declared coverage>",
        "expected_end_time": "<REPLACE: ISO-8601 UTC end of declared coverage>",
        "column_mapping_profile_id": "<REPLACE: profile_id of your column-mapping profile>",
        "notes": "<REPLACE-OR-NULL: free-text notes, or null>",
        GUIDANCE_KEY: {
            "purpose": (
                "Declares provenance and semantics for one raw export. Replace every "
                "<REPLACE: ...> value, then delete this _field_guidance block before "
                "running preflight."
            ),
            "must_replace": [
                "bundle_id", "provider_name", "provider_product_or_export_name",
                "user_entitlement_assertion", "retrieval_time", "export_time",
                "artifact_relative_path", "artifact_sha256", "artifact_byte_length",
                "provider_symbol", "canonical_symbol", "market_or_venue", "bar_interval",
                "event_timezone", "timestamp_semantics", "session_coverage",
                "price_adjustment_semantics", "volume_adjustment_semantics",
                "corporate_action_handling", "data_time_basis", "value_authenticity",
                "intended_use", "expected_start_time", "expected_end_time",
                "column_mapping_profile_id",
            ],
            "may_default": [
                "artifact_media_type", "artifact_format", "session_coverage_policy",
            ],
            "nullable": ["license_or_terms_reference", "notes"],
            "notes": (
                "artifact_sha256 and artifact_byte_length must describe the exact raw "
                "bytes placed under raw/. retrieval_time and export_time are distinct "
                "from the bars' event times. Only CSV is normalized this batch."
            ),
        },
    }


def build_column_mapping_profile_template() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "profile_id": "<REPLACE: unique profile id, e.g. myprovider-ohlcv-csv.v1>",
        "delimiter": ",",
        "encoding": "utf-8",
        "has_header": True,
        "timestamp_column": "<REPLACE-OR-NULL: single timestamp column name, or null>",
        "date_column": "<REPLACE-OR-NULL: date column name if using separate date+time, or null>",
        "time_column": "<REPLACE-OR-NULL: time column name if using separate date+time, or null>",
        "timestamp_format": "<REPLACE-OR-NULL: explicit format if required, or null>",
        "symbol_column": "<REPLACE-OR-NULL: symbol column name, or null>",
        "venue_column": "<REPLACE-OR-NULL: venue column name, or null>",
        "open_column": "<REPLACE: open column name>",
        "high_column": "<REPLACE: high column name>",
        "low_column": "<REPLACE: low column name>",
        "close_column": "<REPLACE: close column name>",
        "volume_column": "<REPLACE-OR-NULL: volume column name, or null>",
        "trade_count_column": "<REPLACE-OR-NULL: trade-count column name, or null>",
        "vwap_column": "<REPLACE-OR-NULL: vwap column name, or null>",
        "currency_column": "<REPLACE-OR-NULL: currency column name, or null>",
        "decimal_separator": ".",
        "thousands_separator_policy": ThousandsSeparatorPolicy.DISALLOW.value,
        "null_tokens": [],
        "sort_expectation": SortExpectation.STABLE_SORT_BY_EVENT_START.value,
        "duplicate_policy": DuplicatePolicy.COLLAPSE_IDENTICAL_REJECT_CONFLICTING.value,
        GUIDANCE_KEY: {
            "purpose": (
                "Maps your CSV's columns to canonical bar fields. Declare exactly one "
                "of timestamp_column OR (date_column + time_column). Replace the "
                "<REPLACE: ...> values, set unused optional columns to null, then delete "
                "this _field_guidance block before running preflight."
            ),
            "must_replace": ["profile_id", "open_column", "high_column", "low_column", "close_column"],
            "one_of_required": ["timestamp_column", "date_column + time_column"],
            "may_default": [
                "delimiter", "encoding", "has_header", "decimal_separator",
                "thousands_separator_policy", "null_tokens", "sort_expectation",
                "duplicate_policy",
            ],
            "nullable": [
                "timestamp_column", "date_column", "time_column", "timestamp_format",
                "symbol_column", "venue_column", "volume_column", "trade_count_column",
                "vwap_column", "currency_column",
            ],
            "notes": (
                "The event timezone is declared in the manifest (event_timezone), not "
                "here. decimal_separator must differ from delimiter. thousands_separator"
                "_policy is one of DISALLOW, COMMA, SPACE, UNDERSCORE."
            ),
        },
    }


def build_case_association_template() -> dict:
    return {
        WARNING_KEY: "NOT FOR USE IN BATCH 04 -- FUTURE AUTHORIZED WORK ONLY.",
        "schema_version": SCHEMA_VERSION,
        "case_id": "<PLACEHOLDER: future case id -- do NOT use a real case id in Batch 04>",
        "canonical_symbol": "<PLACEHOLDER: canonical symbol>",
        "frozen_detection_boundary_id": "<PLACEHOLDER: frozen detection boundary id>",
        "requested_window_start": "<PLACEHOLDER: ISO-8601 UTC window start>",
        "requested_window_end": "<PLACEHOLDER: ISO-8601 UTC window end>",
        "required_interval": _one_of(BarInterval),
        "required_session_coverage": _one_of(BarSession),
        "bundle_id": "<PLACEHOLDER: bundle_id of a validated bundle>",
        GUIDANCE_KEY: {
            "status": "NOT FOR USE IN BATCH 04 -- FUTURE AUTHORIZED WORK ONLY",
            "purpose": (
                "Declarative, non-executing link from a validated bundle to a future "
                "case. Batch 04 never performs case association; this template exists so "
                "the shape is documented for later authorized work only."
            ),
            "must_not": [
                "Do not populate with any real research case id.",
                "Do not populate with any real detection boundary id.",
                "Use obvious placeholder values only; do not attempt association during Batch 04.",
            ],
        },
    }


__all__ = [
    "GUIDANCE_KEY",
    "WARNING_KEY",
    "build_intake_manifest_template",
    "build_column_mapping_profile_template",
    "build_case_association_template",
]

"""Reason-code troubleshooting metadata and a deterministic invalid-scenario index.

The troubleshooting index maps every Batch 03 ``IntakeReasonCode`` to operator
guidance. It never advises bypassing a source restriction or editing raw data to
force acceptance; it separates a safe manifest/mapping correction from changing the
raw artifact. The invalid-scenario index reuses the Batch 03 normalization
machinery on the kit's synthetic bundle to record, for each scenario, the resulting
preflight status and reason codes plus a remediation. Unsafe input is never
auto-repaired.
"""

from __future__ import annotations

import hashlib

from ..local_bar_intake.models import SCHEMA_VERSION
from ..local_bar_intake.semantics import (
    ArtifactFormat,
    BarInterval,
    DataTimeBasis,
    DuplicatePolicy,
    IntakeReasonCode,
    IntendedUse,
    PriceAdjustmentSemantics,
    SortExpectation,
    TimestampSemantics,
)
from .preflight import run_preflight_from_bytes
from .synthetic import build_column_mapping_profile, build_valid_manifest, RAW_CSV

# Distinct from ``None`` so a scenario can pass ``content=None`` to mean "the raw
# file is absent" without colliding with "no content override supplied".
_UNSET = object()


# meaning / why_blocked / inspect / may_change / must_not_guess / new_export_required
_C = IntakeReasonCode
_TROUBLESHOOTING: dict[str, dict[str, str]] = {
    _C.ARTIFACT_MISSING.value: {
        "meaning": "No file was found at the manifest's artifact_relative_path under the bundle root.",
        "why_blocked": "Blocks the bundle: nothing can be validated or normalized.",
        "inspect": "The bundle root, the raw/ folder, and artifact_relative_path spelling.",
        "may_change": "Fix artifact_relative_path, or place the exact raw file where it points.",
        "must_not_guess": "Do not substitute a different file to make the path resolve.",
        "new_export_required": "NO",
    },
    _C.ARTIFACT_EMPTY.value: {
        "meaning": "The raw file exists but has zero bytes.",
        "why_blocked": "Blocks the bundle: an empty export carries no bars.",
        "inspect": "Whether the export completed and was copied fully.",
        "may_change": "Replace with the complete raw export and update sha256/byte_length.",
        "must_not_guess": "Do not fabricate rows to fill an empty file.",
        "new_export_required": "SOMETIMES",
    },
    _C.ARTIFACT_BYTE_LENGTH_MISMATCH.value: {
        "meaning": "The raw file's byte length differs from artifact_byte_length in the manifest.",
        "why_blocked": "Blocks the bundle: the manifest no longer describes the exact bytes.",
        "inspect": "The real byte length (historical-bar-hash) versus the declared value.",
        "may_change": "Recompute and set artifact_byte_length for the exact file placed under raw/.",
        "must_not_guess": "Do not resave or reformat the raw file to reach the declared length.",
        "new_export_required": "NO",
    },
    _C.ARTIFACT_SHA256_MISMATCH.value: {
        "meaning": "The raw file's SHA-256 differs from artifact_sha256 in the manifest.",
        "why_blocked": "Blocks the bundle: the bytes were altered or the wrong file is present.",
        "inspect": "The real SHA-256 (historical-bar-hash); whether line endings changed on copy.",
        "may_change": "Recompute and set artifact_sha256 for the exact file placed under raw/.",
        "must_not_guess": "Do not edit raw bytes to reach the declared hash.",
        "new_export_required": "SOMETIMES",
    },
    _C.UNSUPPORTED_ENCODING.value: {
        "meaning": "The declared profile.encoding is not one this batch can decode.",
        "why_blocked": "Blocks the bundle: the text cannot be decoded deterministically.",
        "inspect": "The real file encoding; supported values are utf-8, utf-8-sig, ascii, latin-1.",
        "may_change": "Set profile.encoding to the export's actual supported encoding.",
        "must_not_guess": "Do not guess an encoding that silently corrupts characters.",
        "new_export_required": "SOMETIMES",
    },
    _C.UNSUPPORTED_FORMAT.value: {
        "meaning": "artifact_format is a declared format this batch does not normalize (only CSV).",
        "why_blocked": "Blocks the bundle: only CSV is normalized this batch.",
        "inspect": "The export's real format; whether a delimited CSV export is available.",
        "may_change": "Provide a CSV export and set artifact_format to CSV.",
        "must_not_guess": "Do not relabel a non-CSV file as CSV.",
        "new_export_required": "SOMETIMES",
    },
    _C.MALFORMED_MANIFEST.value: {
        "meaning": "The manifest JSON is not a valid IntakeManifest (missing/invalid fields).",
        "why_blocked": "Blocks at load: preflight cannot build the manifest object.",
        "inspect": "The manifest against the intake-manifest template and field guidance.",
        "may_change": "Fix the manifest JSON: add required fields, correct types, remove guidance keys.",
        "must_not_guess": "Do not invent provenance values to satisfy the schema.",
        "new_export_required": "NO",
    },
    _C.MANIFEST_SCHEMA_MISMATCH.value: {
        "meaning": "The manifest declares a schema/contract version this batch does not accept.",
        "why_blocked": "Blocks the bundle: the declared contract does not match this workflow.",
        "inspect": "schema_version and intake_contract_version against the template defaults.",
        "may_change": "Set the versions to the values in the current template.",
        "must_not_guess": "Do not force an unsupported version through.",
        "new_export_required": "NO",
    },
    _C.UNKNOWN_TIMEZONE.value: {
        "meaning": "event_timezone could not be resolved (unknown name, or IANA data unavailable).",
        "why_blocked": "Blocks the bundle: timestamps cannot be anchored to an instant.",
        "inspect": "event_timezone; prefer UTC or an explicit offset like -05:00 when IANA data is absent.",
        "may_change": "Set event_timezone to UTC, an explicit offset, or a resolvable IANA zone.",
        "must_not_guess": "Do not infer the timezone from the symbol or venue.",
        "new_export_required": "NO",
    },
    _C.AMBIGUOUS_TIMEZONE.value: {
        "meaning": "A local timestamp is ambiguous (a daylight-saving fall-back repeats the hour).",
        "why_blocked": "Blocks the row: the instant is not unique, so it is never guessed.",
        "inspect": "Whether the export provides UTC or an explicit offset instead of local time.",
        "may_change": "Re-declare event_timezone as UTC or an explicit offset if the export supports it.",
        "must_not_guess": "Do not pick one side of the repeated hour.",
        "new_export_required": "SOMETIMES",
    },
    _C.NONEXISTENT_LOCAL_TIME.value: {
        "meaning": "A local timestamp falls in a daylight-saving spring-forward gap that never occurred.",
        "why_blocked": "Blocks the row: the instant does not exist, so it is never invented.",
        "inspect": "Whether the export mislabels timezone, or provides UTC/explicit offset.",
        "may_change": "Re-declare event_timezone as UTC or an explicit offset if the export supports it.",
        "must_not_guess": "Do not shift the time into the adjacent valid hour.",
        "new_export_required": "SOMETIMES",
    },
    _C.MISSING_TIMESTAMP_SEMANTICS.value: {
        "meaning": "timestamp_semantics is not START or END, so bar boundaries are undefined.",
        "why_blocked": "Blocks the bundle: whether a timestamp labels the bar start or end is unknown.",
        "inspect": "The provider's documentation for whether timestamps mark bar open or close.",
        "may_change": "Set timestamp_semantics to START or END per the provider's definition.",
        "must_not_guess": "Do not assume START without confirming the provider's convention.",
        "new_export_required": "NO",
    },
    _C.MISSING_INTERVAL.value: {
        "meaning": "No bar_interval is declared, so bar duration is undefined.",
        "why_blocked": "Blocks at load: the manifest requires an explicit interval.",
        "inspect": "The export's actual bar interval.",
        "may_change": "Declare bar_interval to match the export.",
        "must_not_guess": "Do not infer interval from row spacing.",
        "new_export_required": "NO",
    },
    _C.UNSUPPORTED_INTERVAL.value: {
        "meaning": "bar_interval is a session-based or otherwise unsupported interval this batch cannot bound.",
        "why_blocked": "Blocks the bundle: daily/irregular bars are not silently converted.",
        "inspect": "Whether a supported fixed interval (1/5/15/30 minute or 1 hour) export exists.",
        "may_change": "Provide an export at a supported fixed interval and declare it.",
        "must_not_guess": "Do not resample or convert bars to a supported interval by hand.",
        "new_export_required": "SOMETIMES",
    },
    _C.MISSING_ADJUSTMENT_SEMANTICS.value: {
        "meaning": "A price/volume/corporate-action semantic is UNKNOWN, so adjustment meaning is undefined.",
        "why_blocked": "Blocks the bundle: adjustment cannot be inferred from the numbers.",
        "inspect": "The provider's documentation for how prices and volume are adjusted.",
        "may_change": "Set price/volume adjustment and corporate_action_handling to declared values.",
        "must_not_guess": "Do not guess raw vs adjusted from the price magnitudes.",
        "new_export_required": "NO",
    },
    _C.UNSUPPORTED_ADJUSTMENT_SEMANTICS.value: {
        "meaning": "A declared adjustment semantic is outside the supported set.",
        "why_blocked": "Blocks the bundle: the declared adjustment cannot be represented.",
        "inspect": "The supported price/volume adjustment options in the adjustment guide.",
        "may_change": "Re-declare using a supported adjustment value if it matches the export.",
        "must_not_guess": "Do not map an unsupported adjustment onto a supported one.",
        "new_export_required": "SOMETIMES",
    },
    _C.CONTRADICTORY_ADJUSTMENT_SEMANTICS.value: {
        "meaning": "Price adjustment and corporate-action handling disagree (e.g. adjusted price, raw handling).",
        "why_blocked": "Blocks the bundle: the declared semantics are internally inconsistent.",
        "inspect": "price_adjustment_semantics against corporate_action_handling.",
        "may_change": "Correct whichever field is mis-declared to match the export.",
        "must_not_guess": "Do not pick one field arbitrarily to resolve the conflict.",
        "new_export_required": "NO",
    },
    _C.DATA_TIME_BASIS_UNKNOWN.value: {
        "meaning": "data_time_basis is UNKNOWN, so it is unclear whether values are historical or current.",
        "why_blocked": "Blocks the bundle: current values must not be ingested as historical.",
        "inspect": "Whether the export is a historical snapshot or a live/current view.",
        "may_change": "Set data_time_basis to HISTORICAL only when the export truly is historical.",
        "must_not_guess": "Do not declare HISTORICAL to get past the check.",
        "new_export_required": "SOMETIMES",
    },
    _C.INVALID_TIMESTAMP.value: {
        "meaning": "A row timestamp is missing or unparseable.",
        "why_blocked": "Blocks the row: the bar cannot be placed in time.",
        "inspect": "The timestamp column mapping and timestamp_format against the raw rows.",
        "may_change": "Correct timestamp_column/date_column/time_column/timestamp_format in the profile.",
        "must_not_guess": "Do not fill in a plausible timestamp for a broken row.",
        "new_export_required": "SOMETIMES",
    },
    _C.EVENT_TIME_OUTSIDE_COVERAGE.value: {
        "meaning": "A bar falls outside the manifest's declared expected_start_time/expected_end_time.",
        "why_blocked": "Blocks the row: the bundle claims a coverage window the data exceeds.",
        "inspect": "The declared coverage window against the actual first/last bar times.",
        "may_change": "Widen expected_start_time/expected_end_time to the true coverage if intended.",
        "must_not_guess": "Do not drop or move the out-of-window bar.",
        "new_export_required": "NO",
    },
    _C.MIXED_INTERVALS_UNDECLARED.value: {
        "meaning": "Rows imply more than one bar interval but a single interval was declared.",
        "why_blocked": "Blocks the bundle: mixed intervals are not silently reconciled.",
        "inspect": "Row spacing against the declared bar_interval.",
        "may_change": "Split the export into single-interval bundles, each declared correctly.",
        "must_not_guess": "Do not resample mixed bars into one interval.",
        "new_export_required": "SOMETIMES",
    },
    _C.SYMBOL_MISMATCH.value: {
        "meaning": "A row's symbol disagrees with the manifest provider_symbol.",
        "why_blocked": "Blocks the row: the bundle would mix instruments.",
        "inspect": "The symbol column values against provider_symbol.",
        "may_change": "Correct provider_symbol, or the symbol_column mapping, to match the export.",
        "must_not_guess": "Do not overwrite the row symbol to match.",
        "new_export_required": "NO",
    },
    _C.MARKET_VENUE_MISMATCH.value: {
        "meaning": "A row's venue disagrees with the manifest market_or_venue.",
        "why_blocked": "Blocks the row: the bundle would mix venues.",
        "inspect": "The venue column values against market_or_venue.",
        "may_change": "Correct market_or_venue, or the venue_column mapping, to match the export.",
        "must_not_guess": "Do not overwrite the row venue to match.",
        "new_export_required": "NO",
    },
    _C.MISSING_OHLC_VALUE.value: {
        "meaning": "A required open/high/low/close value is missing for a row.",
        "why_blocked": "Blocks the row: OHLC is never inferred.",
        "inspect": "The OHLC column mappings and null_tokens against the raw rows.",
        "may_change": "Fix the OHLC column mapping if a real value was misread as null.",
        "must_not_guess": "Do not fill a missing price from a neighboring bar.",
        "new_export_required": "SOMETIMES",
    },
    _C.MALFORMED_DECIMAL.value: {
        "meaning": "A numeric field is not a valid decimal under the profile's separators.",
        "why_blocked": "Blocks the row: the value cannot be parsed deterministically.",
        "inspect": "decimal_separator and thousands_separator_policy against the raw numbers.",
        "may_change": "Correct decimal_separator/thousands_separator_policy to match the export.",
        "must_not_guess": "Do not rewrite the raw number to a clean form.",
        "new_export_required": "SOMETIMES",
    },
    _C.NAN_OR_INFINITY.value: {
        "meaning": "A numeric field is NaN or infinity.",
        "why_blocked": "Blocks the row: non-finite values are never accepted.",
        "inspect": "Whether the export emitted NaN/inf placeholders for missing data.",
        "may_change": "If NaN means null, map it via null_tokens; otherwise the row stays blocked.",
        "must_not_guess": "Do not replace NaN/inf with a fabricated number.",
        "new_export_required": "SOMETIMES",
    },
    _C.NEGATIVE_VOLUME.value: {
        "meaning": "A row carries negative volume.",
        "why_blocked": "Blocks the row: volume cannot be negative.",
        "inspect": "The volume column mapping and the raw values.",
        "may_change": "Fix the volume_column mapping if a non-volume column was mapped.",
        "must_not_guess": "Do not take the absolute value of negative volume.",
        "new_export_required": "SOMETIMES",
    },
    _C.NEGATIVE_TRADE_COUNT.value: {
        "meaning": "A row carries a negative trade count.",
        "why_blocked": "Blocks the row: trade count cannot be negative.",
        "inspect": "The trade_count column mapping and the raw values.",
        "may_change": "Fix the trade_count_column mapping if a wrong column was mapped.",
        "must_not_guess": "Do not take the absolute value of a negative trade count.",
        "new_export_required": "SOMETIMES",
    },
    _C.INVALID_OHLC_RELATIONSHIP.value: {
        "meaning": "A bar violates high >= max(open,close,low) or low <= min(open,close,high).",
        "why_blocked": "Blocks the row: the OHLC values are internally impossible.",
        "inspect": "The OHLC column mapping; a swapped high/low is a common cause.",
        "may_change": "Fix the OHLC column mapping if columns were transposed.",
        "must_not_guess": "Do not reorder or clamp OHLC values to make them valid.",
        "new_export_required": "SOMETIMES",
    },
    _C.INVALID_BOUNDARY_DURATION.value: {
        "meaning": "A bar's computed end is not strictly after its start.",
        "why_blocked": "Blocks the row: the bar has no positive duration.",
        "inspect": "timestamp_semantics and bar_interval against the row timestamp.",
        "may_change": "Correct timestamp_semantics or bar_interval if mis-declared.",
        "must_not_guess": "Do not extend the bar to a positive duration by hand.",
        "new_export_required": "NO",
    },
    _C.MALFORMED_ROW.value: {
        "meaning": "A row cannot be split into the expected fields.",
        "why_blocked": "Blocks the row: the record is structurally broken.",
        "inspect": "delimiter and has_header against the raw line.",
        "may_change": "Correct delimiter/has_header if the profile mis-describes the CSV.",
        "must_not_guess": "Do not hand-edit the broken raw line.",
        "new_export_required": "SOMETIMES",
    },
    _C.DUPLICATE_TIMESTAMP.value: {
        "meaning": "Two or more rows share the same bar start time.",
        "why_blocked": "Identical duplicates quarantine (collapse); under REJECT_ALL_DUPLICATES they reject.",
        "inspect": "Whether the duplicates are truly identical and the duplicate_policy setting.",
        "may_change": "Choose the duplicate_policy that matches your intent for identical rows.",
        "must_not_guess": "Do not delete rows to remove duplicates silently.",
        "new_export_required": "NO",
    },
    _C.CONFLICTING_DUPLICATE_BAR.value: {
        "meaning": "Two rows share a start time but disagree on values.",
        "why_blocked": "Blocks the bundle: which conflicting bar is correct is never guessed.",
        "inspect": "The conflicting rows and why the export produced both.",
        "may_change": "Obtain a clean export without conflicting duplicates.",
        "must_not_guess": "Do not pick one conflicting row over the other.",
        "new_export_required": "YES",
    },
    _C.OVERLAPPING_BARS.value: {
        "meaning": "A later bar starts before the previous bar's end.",
        "why_blocked": "Blocks the bundle: overlapping bars are inconsistent.",
        "inspect": "bar_interval and timestamp_semantics against the row spacing.",
        "may_change": "Correct bar_interval/timestamp_semantics if mis-declared.",
        "must_not_guess": "Do not trim bars to remove the overlap.",
        "new_export_required": "SOMETIMES",
    },
    _C.NON_MONOTONIC_ORDER.value: {
        "meaning": "Rows are not sorted by time but the profile requires presorted input.",
        "why_blocked": "Blocks the bundle when sort_expectation is REQUIRE_PRESORTED.",
        "inspect": "The raw row order and the sort_expectation setting.",
        "may_change": "Set sort_expectation to STABLE_SORT_BY_EVENT_START if unordered input is acceptable.",
        "must_not_guess": "Do not reorder the raw rows in place to fake presorting.",
        "new_export_required": "NO",
    },
    _C.COVERAGE_GAP.value: {
        "meaning": "Consecutive bars leave a gap but continuity was required.",
        "why_blocked": "Blocks the bundle when session_coverage_policy is REQUIRE_CONTINUOUS.",
        "inspect": "Whether gaps are expected (halts, closed session) for this data.",
        "may_change": "Set session_coverage_policy to ALLOW_GAPS if gaps are legitimate.",
        "must_not_guess": "Do not synthesize filler bars to close the gap.",
        "new_export_required": "NO",
    },
    _C.CURRENT_VALUE_AS_HISTORICAL.value: {
        "meaning": "data_time_basis is CURRENT, so the values are a live view, not historical.",
        "why_blocked": "Blocks the bundle: current values cannot substitute for historical ones.",
        "inspect": "Whether the export is a live snapshot or a true historical extract.",
        "may_change": "Provide a genuinely historical export and declare HISTORICAL.",
        "must_not_guess": "Do not relabel a current view as historical.",
        "new_export_required": "YES",
    },
    _C.SYNTHETIC_VALUE_AS_HISTORICAL.value: {
        "meaning": "A SYNTHETIC_FIXTURE bundle is declared as HISTORICAL_EVIDENCE.",
        "why_blocked": "Blocks the bundle: synthetic values cannot represent historical evidence.",
        "inspect": "value_authenticity against intended_use.",
        "may_change": "Set intended_use to INFRASTRUCTURE_FIXTURE for synthetic data.",
        "must_not_guess": "Do not relabel synthetic data as vendor-supplied historical evidence.",
        "new_export_required": "YES",
    },
    _C.ABSOLUTE_PATH_IN_IDENTITY.value: {
        "meaning": "artifact_relative_path is absolute or escapes the intake root.",
        "why_blocked": "Blocks at load: absolute/machine paths never enter deterministic identity.",
        "inspect": "artifact_relative_path; it must be a relative path under the bundle root.",
        "may_change": "Use a relative path such as raw/your-export.csv.",
        "must_not_guess": "Do not embed a machine-specific absolute path.",
        "new_export_required": "NO",
    },
    _C.CREDENTIAL_LIKE_VALUE_PRESENT.value: {
        "meaning": "A field contains credential-like material (a login pass-phrase, API key, or token).",
        "why_blocked": "Blocks the bundle: credentials must never enter intake artifacts.",
        "inspect": "Every manifest/profile value for accidentally pasted credential material.",
        "may_change": "Remove the credential-like value; declare only provenance and semantics.",
        "must_not_guess": "Do not obfuscate credential material to pass the check.",
        "new_export_required": "NO",
    },
    _C.CASE_ASSOCIATION_WITHOUT_DECLARATION.value: {
        "meaning": "An association was attempted without a declared, validated mapping.",
        "why_blocked": "Blocks: Batch 04 performs no case association at all.",
        "inspect": "Nothing to change in Batch 04; association is future authorized work only.",
        "may_change": "Nothing in this batch; do not attempt association here.",
        "must_not_guess": "Do not link a bundle to any real case during Batch 04.",
        "new_export_required": "NO",
    },
    _C.UNKNOWN_CASE_ID.value: {
        "meaning": "A case-association mapping references a case id not in the known set.",
        "why_blocked": "Future-work guard: association validates references only, and only later.",
        "inspect": "Not applicable in Batch 04; the case-association template is placeholder-only.",
        "may_change": "Nothing in this batch.",
        "must_not_guess": "Do not substitute a real case id into the template during Batch 04.",
        "new_export_required": "NO",
    },
    _C.UNKNOWN_BOUNDARY_ID.value: {
        "meaning": "A case-association mapping references a boundary id not in the known set.",
        "why_blocked": "Future-work guard: association validates references only, and only later.",
        "inspect": "Not applicable in Batch 04.",
        "may_change": "Nothing in this batch.",
        "must_not_guess": "Do not substitute a real boundary id during Batch 04.",
        "new_export_required": "NO",
    },
    _C.CASE_SYMBOL_INCOMPATIBLE.value: {
        "meaning": "A mapping's symbol is incompatible with the bundle's manifest symbol.",
        "why_blocked": "Future-work guard: symbol compatibility is checked only in later authorized work.",
        "inspect": "Not applicable in Batch 04.",
        "may_change": "Nothing in this batch.",
        "must_not_guess": "Do not force a symbol match during Batch 04.",
        "new_export_required": "NO",
    },
    _C.CASE_COVERAGE_INCOMPATIBLE.value: {
        "meaning": "A mapping's required session coverage is incompatible with the bundle's coverage.",
        "why_blocked": "Future-work guard: coverage compatibility is checked only in later authorized work.",
        "inspect": "Not applicable in Batch 04.",
        "may_change": "Nothing in this batch.",
        "must_not_guess": "Do not force a coverage match during Batch 04.",
        "new_export_required": "NO",
    },
    _C.CASE_INTERVAL_INCOMPATIBLE.value: {
        "meaning": "A mapping's required interval is incompatible with the bundle's interval.",
        "why_blocked": "Future-work guard: interval compatibility is checked only in later authorized work.",
        "inspect": "Not applicable in Batch 04.",
        "may_change": "Nothing in this batch.",
        "must_not_guess": "Do not force an interval match during Batch 04.",
        "new_export_required": "NO",
    },
}


def build_troubleshooting_index() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "document": "phase_3d_batch_04_troubleshooting_index",
        "note": (
            "Operator guidance per reason code. Guidance never advises bypassing a "
            "source restriction or editing raw data to force acceptance. A manifest or "
            "mapping-profile correction is always distinct from changing the raw "
            "artifact, whose bytes are never rewritten by this workflow."
        ),
        "reason_codes": {code: dict(sorted(entry.items())) for code, entry in _TROUBLESHOOTING.items()},
    }


def _one_row(row: str) -> bytes:
    header = RAW_CSV.split(b"\n", 1)[0].decode("ascii")
    return (header + "\n" + row + "\n").encode("utf-8")


def _two_rows(row_a: str, row_b: str) -> bytes:
    header = RAW_CSV.split(b"\n", 1)[0].decode("ascii")
    return (header + "\n" + row_a + "\n" + row_b + "\n").encode("utf-8")


def build_invalid_scenario_index() -> dict:
    """Deterministic index of invalid scenarios and their preflight outcomes.

    Executed scenarios run the kit's synthetic bundle through the real preflight
    workflow; documented scenarios describe environment-limited or load-time
    barriers (ambiguous/nonexistent local time, load-time guards) without executing.
    """
    manifest = build_valid_manifest()
    profile = build_column_mapping_profile()
    executed: list[dict] = []

    def run(name, description, remediation, *, manifest_override=None, profile_override=None, content=_UNSET):
        used_content = RAW_CSV if content is _UNSET else content
        updates = dict(manifest_override or {})
        if (
            content is not _UNSET
            and content is not None
            and "artifact_sha256" not in updates
            and "artifact_byte_length" not in updates
        ):
            updates["artifact_sha256"] = hashlib.sha256(used_content).hexdigest()
            updates["artifact_byte_length"] = len(used_content)
        used_manifest = (
            manifest if not updates
            else manifest.model_copy(update={**updates, "deterministic_id": None})
        )
        used_profile = (
            profile if not profile_override
            else profile.model_copy(update={**profile_override, "deterministic_id": None})
        )
        report = run_preflight_from_bytes(used_manifest, used_profile, used_content)
        executed.append({
            "scenario": name,
            "description": description,
            "evaluation": "EXECUTED",
            "preflight_status": report.status.value,
            "reason_codes": tuple(code.value for code in report.reason_codes),
            "remediation": remediation,
        })

    run("missing_raw_artifact", "No file at the declared path.",
        "Place the exact raw file, or fix artifact_relative_path.", content=None)
    run("incorrect_byte_length", "Declared byte length does not match the bytes.",
        "Recompute artifact_byte_length for the exact file.",
        manifest_override={"artifact_byte_length": len(RAW_CSV) + 1})
    run("incorrect_sha256", "Declared SHA-256 does not match the bytes.",
        "Recompute artifact_sha256 for the exact file.",
        manifest_override={"artifact_sha256": "0" * 64})
    run("unsupported_encoding", "Profile declares an unsupported encoding.",
        "Set encoding to a supported value (utf-8, utf-8-sig, ascii, latin-1).",
        profile_override={"encoding": "utf-16"})
    run("unsupported_format", "Manifest declares a non-CSV format.",
        "Provide a CSV export and set artifact_format to CSV.",
        manifest_override={"artifact_format": ArtifactFormat.JSON})
    run("unknown_timezone", "event_timezone cannot be resolved.",
        "Use UTC or an explicit offset like -05:00.",
        manifest_override={"event_timezone": "Nowhere/Unknown"})
    run("unsupported_interval", "A session-based (daily) interval is declared.",
        "Provide a supported fixed-interval export and declare it.",
        manifest_override={"bar_interval": BarInterval("1_DAY")})
    run("missing_timestamp_semantics", "timestamp_semantics is UNKNOWN.",
        "Set timestamp_semantics to START or END per the provider convention.",
        manifest_override={"timestamp_semantics": TimestampSemantics.UNKNOWN})
    run("missing_adjustment_semantics", "price_adjustment_semantics is UNKNOWN.",
        "Declare the price/volume/corporate-action semantics from provider docs.",
        manifest_override={"price_adjustment_semantics": PriceAdjustmentSemantics.UNKNOWN})
    run("contradictory_adjustment_semantics", "Adjusted price with raw corporate-action handling.",
        "Make price adjustment and corporate_action_handling consistent.",
        manifest_override={"price_adjustment_semantics": PriceAdjustmentSemantics.SPLIT_ADJUSTED})
    run("current_value_as_historical", "data_time_basis is CURRENT.",
        "Provide a historical export and declare HISTORICAL.",
        manifest_override={"data_time_basis": DataTimeBasis.CURRENT})
    run("synthetic_value_as_historical", "Synthetic fixture declared as historical evidence.",
        "Set intended_use to INFRASTRUCTURE_FIXTURE for synthetic data.",
        manifest_override={"intended_use": IntendedUse.HISTORICAL_EVIDENCE})
    run("symbol_mismatch", "A row symbol disagrees with the manifest.",
        "Correct provider_symbol or the symbol_column mapping.",
        content=_one_row("2026-07-15T14:30:00,WRONG,DEMO_VENUE_X,20.00,20.40,19.90,20.25,3000,30,20.12,USD"))
    run("venue_mismatch", "A row venue disagrees with the manifest.",
        "Correct market_or_venue or the venue_column mapping.",
        content=_one_row("2026-07-15T14:30:00,ZZQ1,WRONG_VENUE,20.00,20.40,19.90,20.25,3000,30,20.12,USD"))
    run("malformed_decimal", "A price is not a valid decimal.",
        "Correct decimal_separator/thousands_separator_policy.",
        content=_one_row("2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,2x.40,19.90,20.25,3000,30,20.12,USD"))
    run("nan_or_infinity", "A price is NaN.",
        "If NaN means null, map via null_tokens; otherwise obtain clean data.",
        content=_one_row("2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,nan,19.90,20.25,3000,30,20.12,USD"))
    run("missing_ohlc_value", "A required OHLC value is missing.",
        "Fix the OHLC mapping if a real value was misread as null.",
        content=_one_row("2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,,19.90,20.25,3000,30,20.12,USD"))
    run("negative_volume", "A bar carries negative volume.",
        "Fix the volume_column mapping if a wrong column was mapped.",
        content=_one_row("2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,20.40,19.90,20.25,-5,30,20.12,USD"))
    run("negative_trade_count", "A bar carries a negative trade count.",
        "Fix the trade_count_column mapping if a wrong column was mapped.",
        content=_one_row("2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,20.40,19.90,20.25,3000,-3,20.12,USD"))
    run("invalid_ohlc_relationship", "A bar high is below open/close (impossible OHLC).",
        "Fix the OHLC mapping if high/low were transposed.",
        content=_one_row("2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,19.00,19.90,20.25,3000,30,20.12,USD"))
    run("event_time_outside_coverage", "A bar falls outside declared coverage.",
        "Widen expected_start_time/expected_end_time to the true coverage.",
        content=_one_row("2026-07-15T16:30:00,ZZQ1,DEMO_VENUE_X,20.00,20.40,19.90,20.25,3000,30,20.12,USD"))
    run("identical_duplicate_collapse_policy",
        "Two identical rows under COLLAPSE_IDENTICAL_REJECT_CONFLICTING.",
        "Identical duplicates are collapsed (quarantine); choose the intended duplicate_policy.",
        content=_two_rows(
            "2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,20.40,19.90,20.25,3000,30,20.12,USD",
            "2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,20.40,19.90,20.25,3000,30,20.12,USD"))
    run("identical_duplicate_reject_policy",
        "Two identical rows under REJECT_ALL_DUPLICATES.",
        "Under REJECT_ALL_DUPLICATES all duplicates reject; choose the intended policy.",
        profile_override={"duplicate_policy": DuplicatePolicy.REJECT_ALL_DUPLICATES},
        content=_two_rows(
            "2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,20.40,19.90,20.25,3000,30,20.12,USD",
            "2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,20.40,19.90,20.25,3000,30,20.12,USD"))
    run("conflicting_duplicate_bar", "Two rows share a timestamp but disagree on values.",
        "Obtain a clean export without conflicting duplicates.",
        content=_two_rows(
            "2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,20.40,19.90,20.25,3000,30,20.12,USD",
            "2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,20.40,19.90,20.25,9999,30,20.12,USD"))
    run("overlapping_bars", "A later bar starts before the previous bar's end.",
        "Correct bar_interval/timestamp_semantics if mis-declared.",
        content=_two_rows(
            "2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,20.40,19.90,20.25,3000,30,20.12,USD",
            "2026-07-15T14:32:00,ZZQ1,DEMO_VENUE_X,20.25,20.55,20.15,20.50,3200,33,20.36,USD"))
    run("non_monotonic_order", "Unsorted rows under REQUIRE_PRESORTED.",
        "Set sort_expectation to STABLE_SORT_BY_EVENT_START if unordered input is acceptable.",
        profile_override={"sort_expectation": SortExpectation.REQUIRE_PRESORTED},
        content=_two_rows(
            "2026-07-15T14:35:00,ZZQ1,DEMO_VENUE_X,20.25,20.55,20.15,20.50,3200,33,20.36,USD",
            "2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,20.40,19.90,20.25,3000,30,20.12,USD"))
    run("coverage_gap", "Continuity required but consecutive bars leave a gap.",
        "Set session_coverage_policy to ALLOW_GAPS if gaps are legitimate.",
        content=_two_rows(
            "2026-07-15T14:30:00,ZZQ1,DEMO_VENUE_X,20.00,20.40,19.90,20.25,3000,30,20.12,USD",
            "2026-07-15T14:45:00,ZZQ1,DEMO_VENUE_X,20.40,20.90,20.30,20.85,3500,35,20.61,USD"))

    documented = [
        {
            "scenario": "malformed_manifest",
            "description": "The manifest JSON is not a valid IntakeManifest.",
            "evaluation": "DOCUMENTED_ONLY",
            "reason": "Fails at manifest load before normalization runs.",
            "expected_reason_code": IntakeReasonCode.MALFORMED_MANIFEST.value,
            "remediation": "Fix the manifest against the template; remove guidance keys.",
        },
        {
            "scenario": "missing_interval",
            "description": "The manifest omits bar_interval.",
            "evaluation": "DOCUMENTED_ONLY",
            "reason": "Fails at manifest load; bar_interval is required.",
            "expected_reason_code": IntakeReasonCode.MISSING_INTERVAL.value,
            "remediation": "Declare bar_interval to match the export.",
        },
        {
            "scenario": "ambiguous_timezone",
            "description": "A local timestamp is ambiguous at a daylight-saving fall-back.",
            "evaluation": "DOCUMENTED_ONLY",
            "reason": "Requires an IANA daylight-saving zone; IANA tz data is environment-limited.",
            "expected_reason_code": IntakeReasonCode.AMBIGUOUS_TIMEZONE.value,
            "remediation": "Re-declare event_timezone as UTC or an explicit offset if the export supports it.",
        },
        {
            "scenario": "nonexistent_local_time",
            "description": "A local timestamp falls in a daylight-saving spring-forward gap.",
            "evaluation": "DOCUMENTED_ONLY",
            "reason": "Requires an IANA daylight-saving zone; IANA tz data is environment-limited.",
            "expected_reason_code": IntakeReasonCode.NONEXISTENT_LOCAL_TIME.value,
            "remediation": "Re-declare event_timezone as UTC or an explicit offset if the export supports it.",
        },
        {
            "scenario": "absolute_path_in_identity",
            "description": "artifact_relative_path is absolute or escapes the intake root.",
            "evaluation": "DOCUMENTED_ONLY",
            "reason": "The model rejects absolute paths at load; no absolute path enters identity.",
            "expected_reason_code": IntakeReasonCode.ABSOLUTE_PATH_IN_IDENTITY.value,
            "remediation": "Use a relative path such as raw/your-export.csv.",
        },
        {
            "scenario": "attempted_case_association_in_batch_04",
            "description": "An attempt to associate a bundle with a real case during Batch 04.",
            "evaluation": "DOCUMENTED_ONLY",
            "reason": "Batch 04 preflight performs no case association; there is no such code path.",
            "expected_reason_code": IntakeReasonCode.CASE_ASSOCIATION_WITHOUT_DECLARATION.value,
            "remediation": "Do not attempt association in Batch 04; it is future authorized work only.",
        },
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "document": "phase_3d_batch_04_invalid_scenario_index",
        "note": (
            "Deterministic invalid scenarios. Executed scenarios run the synthetic "
            "bundle through the real preflight workflow; documented scenarios describe "
            "load-time or environment-limited barriers. No unsafe input is auto-repaired."
        ),
        "executed_scenarios": tuple(executed),
        "documented_scenarios": tuple(documented),
    }


__all__ = [
    "build_troubleshooting_index",
    "build_invalid_scenario_index",
]

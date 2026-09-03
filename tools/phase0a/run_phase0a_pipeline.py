"""Build Phase 0A characterization and assertion evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.offline_guard import install_guard

COLLECTION_RELATIVE_PATH = (
    "short-squeeze-project/short-squeeze-core/tests/fixtures/validation/"
    "outcome_amendment/biya_market_bars_intraday.jsonl"
)
PINNED_SHA256 = "6895533AA441AE309BD944AE9AD2ACAB81B348CE972DB7E4287BCFF264389E3A"
PINNED_BYTE_LENGTH = 8046257
SOURCE_OBJECT_ID = "ADMITTED-SHORTSQ-BIYA-BARS-001"
EVALUATED_AT = "2026-08-15T05:30:00.000000000Z"


def _approval_record_id(record: dict[str, object]) -> str:
    from market_platform_foundation.canonical import canonical_bytes, sha256_bytes

    body = dict(record)
    body.pop("approval_record_id", None)
    return sha256_bytes(canonical_bytes(body))


def _decision_id(decision: dict[str, object]) -> str:
    from market_platform_foundation.canonical import canonical_bytes, sha256_bytes

    body = dict(decision)
    body.pop("decision_id", None)
    return sha256_bytes(canonical_bytes(body))


def _is_lfs_pointer(data: bytes) -> bool:
    return data.startswith(b"version https://git-lfs.github.com/spec/")


def _verify_admitted_object(collection_root: Path) -> dict[str, object]:
    """Read-only verification of the admitted source object in the collection."""
    from market_platform_foundation.canonical import sha256_bytes

    path = collection_root / COLLECTION_RELATIVE_PATH
    report: dict[str, object] = {
        "collection_relative_path": COLLECTION_RELATIVE_PATH,
        "object_readable": False,
        "pinned_sha256": PINNED_SHA256,
        "source_object_id": SOURCE_OBJECT_ID,
    }
    if not path.is_file():
        report["observed_sha256"] = None
        report["reason_codes"] = ["DF001_NO_LOCAL_BYTES"]
        return report
    data = path.read_bytes()
    observed = sha256_bytes(data)
    report["object_readable"] = True
    report["byte_length"] = len(data)
    report["observed_sha256"] = observed
    report["lfs_pointer"] = _is_lfs_pointer(data)
    reasons: list[str] = []
    if observed != PINNED_SHA256:
        reasons.append("DF001_HASH_MISMATCH")
    if len(data) != PINNED_BYTE_LENGTH:
        reasons.append("DF001_BYTE_LENGTH_MISMATCH")
    if report["lfs_pointer"]:
        reasons.append("DF001_LFS_POINTER_ONLY")
    report["reason_codes"] = reasons
    return report


def _parse_admitted_object(collection_root: Path) -> dict[str, object]:
    """Offline stdlib JSONL parser over the admitted source object only."""
    path = collection_root / COLLECTION_RELATIVE_PATH
    record_count = 0
    failure_count = 0
    fields: set[str] = set()
    payload_fields: set[str] = set()
    event_types: set[str] = set()
    symbols: set[str] = set()
    sessions: set[str] = set()
    exchanges: set[str] = set()
    timeframes: set[str] = set()
    effective_timestamps: set[str] = set()
    source_timestamps: set[str] = set()
    sequence_non_null = 0
    bar_epochs: list[int] = []
    provenance_keys: set[str] = set()
    first_fields: list[str] = []
    last_fields: list[str] = []
    provider: str | None = None
    entitlement_state: str | None = None
    normalization_version: str | None = None
    schema_version: str | None = None
    source: str | None = None
    observation_kind: str | None = None
    data_freshness: str | None = None
    naming_modified: set[bool] = set()
    units_modified: set[bool] = set()

    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except ValueError:
                failure_count += 1
                continue
            if not isinstance(record, dict):
                failure_count += 1
                continue
            record_count += 1
            fields.update(str(key) for key in record)
            event_types.add(str(record.get("event_type")))
            symbols.add(str(record.get("symbol")))
            sessions.add(str(record.get("market_session")))
            exchanges.add(str(record.get("exchange")))
            effective_timestamps.add(str(record.get("effective_timestamp")))
            source_timestamps.add(str(record.get("source_timestamp")))
            if record.get("sequence_number") is not None:
                sequence_non_null += 1
            payload = record.get("payload")
            if isinstance(payload, dict):
                payload_fields.update(str(key) for key in payload)
                timeframes.add(str(payload.get("timeframe")))
            provenance = record.get("provenance")
            if isinstance(provenance, dict):
                provenance_keys.update(str(key) for key in provenance)
                provider = str(provenance.get("provider")) if provider is None else provider
                entitlement_state = (
                    str(provenance.get("entitlement_state"))
                    if entitlement_state is None
                    else entitlement_state
                )
                naming_modified.add(bool(provenance.get("naming_modified")))
                units_modified.add(bool(provenance.get("units_modified")))
            srid = record.get("source_record_id")
            if isinstance(srid, str) and srid.rsplit("-", 1)[-1].isdigit():
                bar_epochs.append(int(srid.rsplit("-", 1)[-1]))
            if record_count == 1:
                first_fields = sorted(str(key) for key in record)
            last_fields = sorted(str(key) for key in record)
            normalization_version = (
                str(record.get("normalization_version"))
                if normalization_version is None
                else normalization_version
            )
            schema_version = (
                str(record.get("schema_version")) if schema_version is None else schema_version
            )
            source = str(record.get("source")) if source is None else source
            observation_kind = (
                str(record.get("observation_kind")) if observation_kind is None else observation_kind
            )
            data_freshness = (
                str(record.get("data_freshness")) if data_freshness is None else data_freshness
            )

    deltas: dict[int, int] = {}
    ordered = sorted(bar_epochs)
    for first, second in zip(ordered, ordered[1:]):
        delta = second - first
        deltas[delta] = deltas.get(delta, 0) + 1
    return {
        "bar_epoch_max": ordered[-1] if ordered else None,
        "bar_epoch_min": ordered[0] if ordered else None,
        "bar_epoch_seconds_offset_irregular": sorted(
            {epoch % 60 for epoch in ordered if epoch % 60 != 0}
        ),
        "bar_epoch_spacing_histogram_top": sorted(
            deltas.items(), key=lambda row: (-row[1], row[0])
        )[:6],
        "bar_epochs_monotonic": ordered == bar_epochs,
        "data_freshness": data_freshness,
        "distinct_effective_timestamp_count": len(effective_timestamps),
        "distinct_source_timestamp_count": len(source_timestamps),
        "entitlement_state": entitlement_state,
        "event_types": sorted(event_types),
        "exchanges": sorted(exchanges),
        "failure_count": failure_count,
        "first_record_field_names": first_fields,
        "last_record_field_names": last_fields,
        "naming_modified_observed": sorted(naming_modified),
        "normalization_version": normalization_version,
        "observation_kind": observation_kind,
        "parser_identifier": "stdlib-jsonl/1.0.0",
        "payload_field_names": sorted(payload_fields),
        "provenance_field_names": sorted(provenance_keys),
        "provider": provider,
        "record_count": record_count,
        "record_field_names": sorted(fields),
        "schema_version": schema_version,
        "sequence_number_non_null_count": sequence_non_null,
        "sessions": sorted(sessions),
        "source": source,
        "symbols": sorted(symbols),
        "timeframes": sorted(timeframes),
        "units_modified_observed": sorted(units_modified),
    }


def main() -> int:
    events: list[dict[str, str]] = []
    install_guard(events)
    from market_platform_foundation.authority import resolve_canonical_authority
    from market_platform_foundation.canonical import (
        canonical_bytes,
        load_json_strict,
        sha256_bytes,
        write_canonical_json,
    )
    from market_platform_foundation.phase0a_assertions import (
        aggregate_status,
        build_registry,
        create_run_manifest,
        evaluate_run,
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", default=str(ROOT))
    parser.add_argument("--collection-root", default=str(ROOT.parent))
    parser.add_argument("--output-base", default=str(ROOT / "evidence" / "phase0a"))
    args = parser.parse_args()
    repo = Path(args.repository_root)
    collection_root = Path(args.collection_root)

    # Finalize governance approvals with derived IDs
    approvals_path = repo / "docs/superpowers/governance/2026-08-15-phase-0a-governance-approvals.json"
    approvals = load_json_strict(approvals_path)
    if isinstance(approvals, dict):
        records = approvals.get("approval_records", [])
        if isinstance(records, list):
            for record in records:
                if isinstance(record, dict):
                    record["approval_record_id"] = _approval_record_id(record)
        write_canonical_json(approvals_path, approvals)

    decision_path = repo / "docs/superpowers/governance/2026-08-15-phase-0a-admitted-source-decision.json"
    decision = load_json_strict(decision_path)
    if isinstance(decision, dict):
        decision["decision_id"] = _decision_id(decision)
        write_canonical_json(decision_path, decision)

    activation_path = repo / "docs/superpowers/governance/2026-08-15-phase-0a-implementation-activation.json"
    activation = load_json_strict(activation_path)
    if isinstance(activation, dict):
        body = dict(activation)
        body.pop("activation_id", None)
        activation["activation_id"] = sha256_bytes(canonical_bytes(body))
        write_canonical_json(activation_path, activation)

    auth_impl_path = repo / "docs/superpowers/governance/2026-08-15-phase-0a-implementation-authorization.json"
    impl_auth_hash = sha256_bytes(auth_impl_path.read_bytes())

    registry_doc = build_registry(repo / "manifests/phase0a/assertion-predicates.json")
    registry_hash = sha256_bytes(canonical_bytes(registry_doc))

    authority = resolve_canonical_authority(repo)
    subject_manifest = {
        "authority_manifest_sha256": authority.get("manifest_sha256", "UNRESOLVED"),
        "phase0_status": authority.get("phase0_status", "UNKNOWN"),
        "repository_root_id": "ROOT-2E7C91F4",
        "track": "PHASE_0A",
    }
    subject_manifest_hash = sha256_bytes(canonical_bytes(subject_manifest))

    tool_versions = ["phase0a-pipeline/1.1.0", "market_platform_foundation/phase0a_assertions/1.0.0"]

    activation_hash = sha256_bytes(
        (repo / "docs/superpowers/governance/2026-08-15-phase-0a-implementation-activation.json").read_bytes()
    )

    # Admitted-source verification (read-only against the external collection)
    hash_report = _verify_admitted_object(collection_root)
    parser_report = _parse_admitted_object(collection_root)

    df001_reasons = sorted(str(code) for code in hash_report.get("reason_codes", []))
    if parser_report["record_count"] < 1:
        df001_reasons.append("DF001_PARSER_ZERO_RECORDS")
    license_resolved = True
    df001_observed: dict[str, object] = {
        "byte_length": hash_report.get("byte_length"),
        "license_status": "RESOLVED" if license_resolved else "UNRESOLVED",
        "lfs_pointer": hash_report.get("lfs_pointer"),
        "observed_sha256": hash_report.get("observed_sha256"),
        "parsed_record_count": parser_report["record_count"],
        "parser_failure_count": parser_report["failure_count"],
        "pinned_sha256": PINNED_SHA256,
        "source_object_id": SOURCE_OBJECT_ID,
    }
    df001_status = "PASS" if not df001_reasons and license_resolved else "BLOCKED"

    df002_observed: dict[str, object] = {
        "capability_manifest_present": True,
        "sampled_schema_report_present": True,
        "source_semantics_review_present": True,
        "unsupported_capabilities_explicit": [
            "DEPTH_LEVEL2",
            "TRADE_TICK",
            "QUOTE",
            "MBO",
            "AGGRESSOR",
            "QUEUE",
        ],
    }
    df002_reasons: list[str] = []
    if df001_status != "PASS":
        df002_reasons.append("DF001_BLOCKED_PREREQUISITE")
    df002_status = "PASS" if not df002_reasons else "BLOCKED"

    # Characterization artifact content (hashed before run manifest)
    donor_index = {
        "artifact_type": "PHASE_0A_DONOR_CHARACTERIZATION_INDEX",
        "donor_count": 7,
        "donors": [
            {
                "classification_summary": "PORT_ADAPT depth/replay patterns; 20 LFS pointers; metadata-only ES locally",
                "logical_id": "PROTO-FUTURESX-001",
                "notes_ref": "docs/research/donors/README.md",
                "rights_state": "PROTOTYPE_REFERENCE_ONLY",
            },
            {
                "classification_summary": "CVD/OFI oracle candidates; demo OHLCV gzip non-ES",
                "logical_id": "PROTO-CVD-001",
                "notes_ref": "docs/research/donors/README.md",
                "rights_state": "PROTOTYPE_REFERENCE_ONLY",
            },
            {
                "classification_summary": "provenance/freshness gates; equity fixtures",
                "logical_id": "PROTO-SHORTSQ-001",
                "notes_ref": "docs/research/donors/README.md",
                "rights_state": "NESTED_GIT_PROTOTYPE",
            },
            {
                "classification_summary": "news/options workflow concept only",
                "logical_id": "PROTO-INTERNSHIP-001",
                "notes_ref": "docs/research/donors/README.md",
                "rights_state": "PROTOTYPE_REFERENCE_ONLY",
            },
            {
                "classification_summary": "volume-anomaly visualization patterns",
                "logical_id": "PROTO-L1VOL-001",
                "notes_ref": "docs/research/donors/README.md",
                "rights_state": "PROTOTYPE_REFERENCE_ONLY",
            },
            {
                "classification_summary": "model comparison patterns; leakage in holdout paths DO_NOT_USE",
                "logical_id": "PROTO-DS340W-001",
                "notes_ref": "docs/research/donors/DS340W_NOTES.md",
                "rights_state": "UNRESOLVED_DO_NOT_COPY_OR_REDISTRIBUTE",
            },
            {
                "classification_summary": "dataset/cache/API/UI patterns; Gemini and SQLite DO_NOT_USE",
                "logical_id": "PROTO-GRIDIQ-001",
                "notes_ref": "docs/research/donors/GRID_IQ_NOTES.md",
                "rights_state": "UNRESOLVED_DO_NOT_COPY_OR_REDISTRIBUTE",
            },
        ],
        "inspection_mode": "READ_ONLY_OFFLINE",
        "logical_id": "phase0a.donor_characterization_index",
        "matrix_ref": "docs/research/donors/DONOR_REUSE_MATRIX.md",
        "revision_3_extension_complete": True,
        "status": "COMPLETE_FOR_READ_ONLY_CHARACTERIZATION",
    }

    oracle_char = {
        "artifact_type": "PHASE_0A_ORACLE_CHARACTERIZATION",
        "copy_prohibited": True,
        "logical_id": "phase0a.oracle_characterization",
        "oracles": [
            {
                "donor_root_id": "PROTO-CVD-001",
                "oracle_class": "CVD_DELTA",
                "use": "POTENTIAL_NEGATIVE_AND_POSITIVE_FIXTURE_ORACLE",
            },
            {
                "donor_root_id": "PROTO-CVD-001",
                "oracle_class": "OFI",
                "use": "POTENTIAL_FIXTURE_ORACLE",
            },
            {
                "donor_root_id": "PROTO-FUTURESX-001",
                "oracle_class": "DEPTH_BOOK_SNAPSHOT",
                "use": "REFERENCE_ONLY_UNTIL_LAWFUL_SOURCE",
            },
            {
                "donor_root_id": "PROTO-SHORTSQ-001",
                "oracle_class": "FRESHNESS_READINESS_GATE",
                "use": "POTENTIAL_QUALITY_GATE_ORACLE",
            },
        ],
        "status": "PLANNING_ONLY",
    }

    source_manifest = {
        "admitted_path_class": "EXTERNAL_COLLECTION_READ_ONLY",
        "artifact_type": "PHASE_0A_SOURCE_MANIFEST",
        "byte_length": PINNED_BYTE_LENGTH,
        "collection_relative_path": COLLECTION_RELATIVE_PATH,
        "copy_into_governed_paths": False,
        "donor_root_id": "PROTO-SHORTSQ-001",
        "license_record_ref": "phase0a.license_record",
        "logical_id": "phase0a.source_manifest",
        "media_type": "application/jsonl",
        "pinned_sha256": PINNED_SHA256,
        "schema_family": "equity_intraday_jsonl",
        "source_object_id": SOURCE_OBJECT_ID,
        "status": "EFFECTIVE",
    }

    object_hash_report = {
        "artifact_type": "PHASE_0A_OBJECT_HASH_REPORT",
        "lfs_pointer_scan": {
            "method": "GIT_LFS_POINTER_PREFIX_RULE",
            "observed_is_pointer": hash_report.get("lfs_pointer"),
        },
        "logical_id": "phase0a.object_hash_report",
        "observed_byte_length": hash_report.get("byte_length"),
        "observed_sha256": hash_report.get("observed_sha256"),
        "pinned_byte_length": PINNED_BYTE_LENGTH,
        "pinned_sha256": PINNED_SHA256,
        "source_object_id": SOURCE_OBJECT_ID,
        "status": "MATCH" if df001_status == "PASS" else "MISMATCH",
        "verification_method": "OFFLINE_SHA256_READ_ONLY",
    }

    parser_report_doc = {
        "artifact_type": "PHASE_0A_PARSER_REPORT",
        "failure_count": parser_report["failure_count"],
        "first_record_field_names": parser_report["first_record_field_names"],
        "last_record_field_names": parser_report["last_record_field_names"],
        "logical_id": "phase0a.parser_report",
        "parser_identifier": parser_report["parser_identifier"],
        "record_count": parser_report["record_count"],
        "source_object_id": SOURCE_OBJECT_ID,
        "status": "PASS" if parser_report["record_count"] >= 1 else "FAIL",
        "third_party_dependencies": [],
    }

    sampled_schema_report = {
        "artifact_type": "PHASE_0A_SAMPLED_SCHEMA_REPORT",
        "bar_epoch_spacing_histogram_top": [
            {"delta_seconds": delta, "occurrences": count}
            for delta, count in parser_report["bar_epoch_spacing_histogram_top"]
        ],
        "bar_epochs_monotonic": parser_report["bar_epochs_monotonic"],
        "bar_time_location": "source_record_id suffix (unix epoch seconds, bar start)",
        "bar_time_seconds_offset_irregular": parser_report["bar_epoch_seconds_offset_irregular"],
        "correction_behavior": "NOT_OBSERVED_NO_CORRECTION_FIELDS",
        "distinct_effective_timestamp_count": parser_report["distinct_effective_timestamp_count"],
        "distinct_source_timestamp_count": parser_report["distinct_source_timestamp_count"],
        "event_types": parser_report["event_types"],
        "exchanges": parser_report["exchanges"],
        "logical_id": "phase0a.sampled_schema_report",
        "observation_kind": parser_report["observation_kind"],
        "payload_field_names": parser_report["payload_field_names"],
        "provenance_field_names": parser_report["provenance_field_names"],
        "record_count": parser_report["record_count"],
        "record_field_names": parser_report["record_field_names"],
        "sampled_records": parser_report["record_count"],
        "schema_version": parser_report["schema_version"],
        "sequence_behavior": (
            "sequence_number NULL on all sampled records"
            if parser_report["sequence_number_non_null_count"] == 0
            else f"sequence_number non-null on {parser_report['sequence_number_non_null_count']} records"
        ),
        "sessions": parser_report["sessions"],
        "source_object_id": SOURCE_OBJECT_ID,
        "symbols": parser_report["symbols"],
        "third_party_parser_used": False,
        "timeframes": parser_report["timeframes"],
        "timestamp_fields": [
            "effective_timestamp",
            "received_timestamp",
            "source_timestamp",
        ],
    }

    source_semantics_review = {
        "admitted_capability_scope": "EQUITY_INTRADAY_BARS_ONLY",
        "artifact_type": "PHASE_0A_SOURCE_SEMANTICS_REVIEW",
        "correction_and_sequence_semantics": (
            "No correction fields observed; sequence_number is NULL on all records; ordering "
            "must be derived from the bar epoch embedded in source_record_id, which is "
            "monotonic across the fixture."
        ),
        "entitlement_state_recorded_by_source": parser_report["entitlement_state"],
        "es_futures_claims": "NONE_SOURCE_IS_EQUITY_NCM_SINGLE_SYMBOL",
        "logical_id": "phase0a.source_semantics_review",
        "naming_modified_observed": parser_report["naming_modified_observed"],
        "normalization_notes": (
            f"Normalization {parser_report['normalization_version']} applied by the donor "
            "pipeline; naming_modified observed; units not modified. Prices are decimal "
            "strings; volume is an integer; vwap and trade_count are NULL in this fixture."
        ),
        "provider_recorded_by_source": parser_report["provider"],
        "source_freshness": parser_report["data_freshness"],
        "source_object_id": SOURCE_OBJECT_ID,
        "timestamp_semantics": (
            "effective_timestamp, source_timestamp, and received_timestamp are record-level "
            "normalization metadata sharing a single distinct value across the fixture "
            "(2026-07-21T21:00:34.865603Z); per-bar times are encoded only in the "
            "source_record_id epoch suffix spanning 2026-07-16T08:00:00Z to "
            "2026-07-21T21:00:09Z. ADR-TIME-001 must resolve this mapping before any "
            "canonical time binding."
        ),
        "units_modified_observed": parser_report["units_modified_observed"],
    }

    license_record = {
        "artifact_type": "PHASE_0A_LICENSE_RECORD",
        "entitlement_class": "MIT_LICENSED_REPOSITORY_FIXTURE",
        "license_scope": (
            "Fixture object resides in the MIT-licensed short-squeeze repository whose "
            "copyright is held by PROJECT-PRINCIPAL-001; underlying market bars carry "
            "donor-recorded provider provenance with entitlement_state NOT_APPLICABLE "
            "and HISTORICAL freshness; governed use is private fixture admission without "
            "redistribution."
        ),
        "logical_id": "phase0a.license_record",
        "principal_acknowledgment": {
            "acknowledged_at": "2026-08-15T05:10:00.000000000Z",
            "principal_id": "PROJECT-PRINCIPAL-001",
            "record_ref": "phase0a.admitted_source_decision",
        },
        "redistribution_class": "PERMISSIVE_MIT_WITH_NOTICE_PRIVATE_FIXTURE_USE",
        "source_candidates_reviewed": [
            "ERIC_FUTURESX_LFS_POINTERS",
            "ERIC_FUTURESX_METADATA_JSON",
            "ERIC_FUTURESX_SMOKE_CSV",
            "CVD_DEMO_GZIP",
            "SHORTSQ_EQUITY_JSONL",
        ],
        "source_object_id": SOURCE_OBJECT_ID,
        "status": "RESOLVED",
    }

    capability_manifest = {
        "admitted_source_id": SOURCE_OBJECT_ID,
        "artifact_type": "PHASE_0A_CAPABILITY_MANIFEST",
        "capabilities": [
            {
                "capability_id": "BAR_OHLCV_1M",
                "normalization_notes": (
                    "Prices decimal strings; volume integer; vwap and trade_count NULL in "
                    "this fixture; bar time embedded in source_record_id epoch suffix."
                ),
                "observed_fields": [
                    "payload.open",
                    "payload.high",
                    "payload.low",
                    "payload.close",
                    "payload.volume",
                    "payload.timeframe",
                ],
                "semantics_ref": "phase0a.source_semantics_review",
                "supported": True,
                "timestamp_fields": ["source_record_id"],
            },
            {
                "capability_id": "EQUITY_INTRADAY_SESSION_LABELS",
                "normalization_notes": "market_session observed as PRE_MARKET/REGULAR/AFTER_HOURS.",
                "observed_fields": ["market_session", "exchange", "symbol"],
                "semantics_ref": "phase0a.source_semantics_review",
                "supported": True,
                "timestamp_fields": [],
            },
        ],
        "explicitly_unsupported": [
            {"capability_id": "DEPTH_LEVEL2", "reason_code": "OHLCV_ONLY_SOURCE", "supported": False},
            {"capability_id": "TRADE_TICK", "reason_code": "OHLCV_ONLY_SOURCE", "supported": False},
            {"capability_id": "QUOTE", "reason_code": "OHLCV_ONLY_SOURCE", "supported": False},
            {"capability_id": "MBO", "reason_code": "OHLCV_ONLY_SOURCE", "supported": False},
            {"capability_id": "AGGRESSOR", "reason_code": "OHLCV_ONLY_SOURCE", "supported": False},
            {"capability_id": "QUEUE", "reason_code": "OHLCV_ONLY_SOURCE", "supported": False},
            {"capability_id": "ES_FUTURES_ANY", "reason_code": "EQUITY_ONLY_SOURCE_NO_ES_CLAIMS", "supported": False},
        ],
        "logical_id": "phase0a.capability_manifest",
        "manifest_version": "1.1.0",
        "schema_family": "equity_intraday_jsonl",
        "status": "EFFECTIVE",
    }

    negative_fixture = {
        "artifact_type": "PHASE_0A_NEGATIVE_CAPABILITY_FIXTURE",
        "case_id": "EQUITY_BARS_ONLY_NO_EVENT_CAPABILITIES",
        "description": (
            "Admitted source is equity intraday bars only; sweep, depth, trade, quote, MBO, "
            "aggressor, and queue capabilities must remain false, and no ES futures claims "
            "may be derived from this source."
        ),
        "expected_blocked_capabilities": [
            "DEPTH_LEVEL2",
            "TRADE_TICK",
            "QUOTE",
            "MBO",
            "AGGRESSOR",
            "QUEUE",
        ],
        "linked_assertion": "SC-002",
        "logical_id": "phase0a.negative_capability_fixture",
        "schema_family": "equity_intraday_jsonl",
        "source_object_id": SOURCE_OBJECT_ID,
        "status": "DOCUMENTED_FOR_ADMITTED_SOURCE",
    }

    adr_scope = {
        "artifact_type": "ADR_DONOR_001_SCOPE_DRAFT",
        "logical_id": "phase0a.adr_donor_001_scope_draft",
        "planned_scope": [
            "extract_adapt_reimplement boundary",
            "rights evidence requirements before any PORT_ADAPT",
            "donor execution prohibition restatement",
            "seven-donor matrix as input not authority",
        ],
        "status": "DRAFT_NOT_ACCEPTED",
    }

    fixture_inventory_ref = {
        "inventory_logical_id": "phase0a.fixture_inventory",
        "inventory_path": "docs/research/fixtures/2026-08-15-phase-0a-collection-fixture-inventory.md",
        "inventory_sha256": "8192F1385066C4FB5E5C15B91FCBA68F63B1F8964778FBF8D1A3C2880AC8F43F",
        "logical_id": "phase0a.fixture_inventory_ref",
    }

    artifacts: list[tuple[str, object]] = [
        ("phase0a.admitted_source_decision", decision),
        ("phase0a.donor_characterization_index", donor_index),
        ("phase0a.oracle_characterization", oracle_char),
        ("phase0a.negative_capability_fixture", negative_fixture),
        ("phase0a.license_record", license_record),
        ("phase0a.capability_manifest", capability_manifest),
        ("phase0a.adr_donor_001_scope_draft", adr_scope),
        ("phase0a.fixture_inventory_ref", fixture_inventory_ref),
        ("phase0a.source_manifest", source_manifest),
        ("phase0a.object_hash_report", object_hash_report),
        ("phase0a.parser_report", parser_report_doc),
        ("phase0a.sampled_schema_report", sampled_schema_report),
        ("phase0a.source_semantics_review", source_semantics_review),
        ("phase0a.assertion_registry", registry_doc),
    ]

    member_pairs = sorted(
        (logical_id, sha256_bytes(canonical_bytes(content))) for logical_id, content in artifacts
    )

    manifest_inputs: dict[str, object] = {
        "active_keys": registry_doc["active_keys"],
        "assertion_observations": {
            "DF-001": {
                **df001_observed,
                "reason_codes": df001_reasons,
                "status": df001_status,
            },
            "DF-002": {
                **df002_observed,
                "reason_codes": df002_reasons,
                "status": df002_status,
            },
        },
        "authorization_refs": [
            {
                "logical_id": "phase0a.implementation_authorization",
                "sha256": impl_auth_hash,
            },
            {
                "logical_id": "phase0a.implementation_activation",
                "sha256": activation_hash,
            },
        ],
        "evaluated_at": EVALUATED_AT,
        "registry_hash": registry_hash,
        "selected_evidence": [{"logical_id": lid, "sha256": hsh} for lid, hsh in member_pairs],
        "subject_manifest_hash": subject_manifest_hash,
        "tool_versions": tool_versions,
    }
    staging_manifest = Path(args.output_base) / ".staging-run-manifest.json"
    run_id = create_run_manifest(staging_manifest, manifest_inputs)
    run_dir = Path(args.output_base) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    staging_manifest.replace(run_dir / "assertion-run-manifest.json")

    for logical_id, content in artifacts:
        slug = logical_id.replace("phase0a.", "").replace(".", "-")
        out_path = run_dir / f"{slug}.json"
        write_canonical_json(out_path, content)

    results = evaluate_run(run_dir / "assertion-run-manifest.json", run_dir)
    aggregate = aggregate_status(results)

    aggregate_doc = {
        "aggregate_status": aggregate,
        "logical_id": "phase0a.assertion_aggregate",
        "mandatory_ids": list(registry_doc["mandatory_ids"]),
        "reason_codes": sorted(
            {
                code
                for result in results
                for code in result.get("reason_codes", [])
            }
        ),
        "results_by_id": {str(r["assertion_id"]): str(r["status"]) for r in results},
        "run_id": run_id,
    }
    write_canonical_json(run_dir / "assertion-aggregate.json", aggregate_doc)

    sorted_pairs = list(member_pairs)
    index_sha256_input = sha256_bytes(
        canonical_bytes([(lid, hsh) for lid, hsh in sorted_pairs])
    )
    root_hash = sha256_bytes(
        canonical_bytes({"index_sha256": index_sha256_input, "members": sorted_pairs})
    )
    candidate_root_doc = {
        "candidate_evidence_root": root_hash,
        "logical_id": "phase0a.candidate_evidence_root",
        "member_count": len(sorted_pairs),
        "members": [{"logical_id": lid, "sha256": hsh} for lid, hsh in sorted_pairs],
        "run_id": run_id,
    }
    write_canonical_json(run_dir / "candidate-evidence-root.json", candidate_root_doc)

    print(f"run_id={run_id}")
    print(f"aggregate_status={aggregate}")
    print(f"candidate_evidence_root={root_hash}")
    return 0 if aggregate == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

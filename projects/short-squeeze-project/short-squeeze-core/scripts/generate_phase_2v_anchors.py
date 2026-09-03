"""Regenerate the Phase 2V deterministic anchor manifest.

Run twice and diff: the manifest and every fixture this writes must be byte-identical
across runs. Nothing here reads the wall clock, the network, or any absolute path.

A note on the BIYA replays: they are built from an *empty* observation set. That is not
a shortcut -- it is the finding. No BIYA observation of any domain exists in the
workspace, so an honest as-of replay at either window edge sees nothing. Feeding
synthetic bars in to make the replay look substantial would misrepresent the case.
"""

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _write_text_lf(path: Path, text: str) -> None:
    """Write with explicit LF endings.

    Path.write_text translates "\\n" to os.linesep, so on Windows it emits CRLF while
    .gitattributes (`* text=auto eol=lf`) stores LF. Two anchors below hash file bytes,
    so that mismatch would make them fail on any fresh checkout. Writing LF explicitly
    keeps the working tree byte-identical to the committed form on every platform.
    """

    path.write_bytes(text.encode("utf-8"))

from squeeze_core.serialization import canonical_hash, canonical_json_bytes  # noqa: E402
from squeeze_core.validation import (  # noqa: E402
    ORIGINAL_RULES,
    ArtifactReliabilityClass,
    CandidateOutcomeObservation,
    DetectionTimeEvidence,
    FieldComparisonEntry,
    OriginalCandidateSnapshot,
    OriginalValueState,
    OutcomeWindow,
    PublicValidationCase,
    RebuiltAsOfSnapshot,
    RuleValidationEntry,
    RuleValidationState,
    ValidationArtifact,
    ValidationCase,
    ValidationCaseConclusion,
    acquisition_manifest,
    build_case_registry,
    build_detection_time_evidence,
    build_field_comparison,
    build_original_snapshot,
    build_public_validation_case,
    build_rebuilt_as_of_snapshot,
    build_rule_validation,
    build_validation_case,
    case_conclusion_hash,
    detection_time_hash,
    field_comparison_hash,
    observed_universe_entries,
    original_snapshot_hash,
    outcome_observation_hash,
    public_case_hash,
    replay_hash,
    rule_validation_hash,
    serialize_case_conclusion,
    serialize_detection_time,
    serialize_field_comparison,
    serialize_original_snapshot,
    serialize_outcome_observation,
    serialize_public_case,
    serialize_replay,
    serialize_rule_validation,
    serialize_validation_case,
    unknown_field,
    unobserved_outcome,
    validation_case_hash,
)
from squeeze_core.validation.case_spec import build_case_from_spec, load_case_spec  # noqa: E402
from squeeze_core.validation.models import OriginalFieldValue  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "validation"
OUT_PATH = FIXTURES / "expected_phase_2v_validation_metadata.json"
CASE_SPEC = FIXTURES / "biya_validation_case.json"
CASE_MANIFEST = FIXTURES / "phase_2v_comparison_case_manifest.json"
FIXTURE_METADATA = FIXTURES / "phase_2v_fixture_metadata.json"
DEMO_DATA = ROOT / "apps" / "biya-validation-demo" / "data" / "biya-case.json"

WINDOW_START = datetime(2026, 7, 17, 14, 23, 58, tzinfo=UTC)
WINDOW_END = datetime(2026, 7, 17, 16, 54, 58, tzinfo=UTC)
MEETING_START = datetime(2026, 7, 17, 16, 46, 15, tzinfo=UTC)

_HASH_FUNCS = {
    DetectionTimeEvidence.__name__: detection_time_hash,
    OriginalCandidateSnapshot.__name__: original_snapshot_hash,
    RebuiltAsOfSnapshot.__name__: replay_hash,
    FieldComparisonEntry.__name__: field_comparison_hash,
    RuleValidationEntry.__name__: rule_validation_hash,
    CandidateOutcomeObservation.__name__: outcome_observation_hash,
    ValidationCaseConclusion.__name__: case_conclusion_hash,
    ValidationCase.__name__: validation_case_hash,
    PublicValidationCase.__name__: public_case_hash,
}

_SERIALIZE_FUNCS = {
    DetectionTimeEvidence.__name__: serialize_detection_time,
    OriginalCandidateSnapshot.__name__: serialize_original_snapshot,
    RebuiltAsOfSnapshot.__name__: serialize_replay,
    FieldComparisonEntry.__name__: serialize_field_comparison,
    RuleValidationEntry.__name__: serialize_rule_validation,
    CandidateOutcomeObservation.__name__: serialize_outcome_observation,
    ValidationCaseConclusion.__name__: serialize_case_conclusion,
    ValidationCase.__name__: serialize_validation_case,
    PublicValidationCase.__name__: serialize_public_case,
}


def _stored_record_artifact() -> ValidationArtifact:
    return ValidationArtifact(
        artifact_id="ART-SYNTH-STORED",
        artifact_type="STORED_CANDIDATE_RECORD",
        repository_or_source="phase-2v-synthetic",
        relative_path="synthetic/stored-candidate.json",
        embedded_event_time_if_known=MEETING_START,
        timezone_if_known="UTC",
        reliability_class=ArtifactReliabilityClass.DIRECT_PLATFORM_RECORD,
    )


def _biya_artifacts() -> tuple[ValidationArtifact, ...]:
    spec = load_case_spec(CASE_SPEC)
    case = build_case_from_spec(spec)
    return case.artifacts


def build_anchor_results() -> dict[str, object]:
    results: dict[str, object] = {}

    # --- detection time, one anchor per resolvable state ---------------------------
    results["detection_time_exact_case"] = build_detection_time_evidence(
        "SYNTH", (_stored_record_artifact(),), timezone_label="UTC"
    )
    biya_artifacts = _biya_artifacts()
    biya_detection = build_detection_time_evidence(
        "BIYA",
        biya_artifacts,
        timezone_label="America/New_York",
        confidence_basis=(
            "Screener run start bounds below and the application log's last write bounds "
            "above. No artifact records a platform event time, so no exact timestamp is claimed."
        ),
    )
    results["detection_time_bounded_case"] = biya_detection
    results["detection_time_unknown_case"] = build_detection_time_evidence(
        "SYNTH",
        (
            ValidationArtifact(
                artifact_id="ART-SYNTH-NOTIME",
                artifact_type="NOTE",
                repository_or_source="phase-2v-synthetic",
                relative_path="synthetic/undated-note.txt",
            ),
        ),
    )

    # --- original snapshot: every BIYA field is unknown, and stays unknown ----------
    biya_fields = tuple(
        unknown_field(field_id, display_label=label)
        for field_id, label in (
            ("price", "Price"),
            ("change_percent", "Change %"),
            ("rel_volume", "Rel Volume"),
            ("float_shares", "Float"),
            ("short_interest_percent", "Short Interest (%)"),
            ("shares_short", "Shares Short"),
            ("days_to_cover", "Days to Cover"),
            ("borrow_fee_rate", "Borrow Fee"),
            ("news_headline", "Headline"),
            ("news_published_at", "News Time"),
            ("squeeze_score", "Squeeze Score"),
            ("tier_label", "Setup"),
        )
    )
    results["biya_original_candidate_snapshot"] = build_original_snapshot(
        "BIYA",
        biya_fields,
        detection_time_evidence_id=biya_detection.deterministic_id,
        source_artifact_ids=("ART-001",),
    )

    # --- replays at both window edges, over the empty evidence set that really exists
    results["biya_earliest_as_of_replay"] = build_rebuilt_as_of_snapshot(
        "earliest", "BIYA", (), WINDOW_START, operation="DAYS_TO_COVER"
    )
    results["biya_latest_as_of_replay"] = build_rebuilt_as_of_snapshot(
        "latest", "BIYA", (), WINDOW_END, operation="DAYS_TO_COVER"
    )

    # --- field comparisons ----------------------------------------------------------
    results["biya_field_comparison"] = build_field_comparison(
        "short_interest_percent",
        OriginalFieldValue(
            field_id="short_interest_percent",
            display_label="Short Interest (%)",
            internal_field_name="ShortFloat",
            state=OriginalValueState.UNKNOWN,
        ),
        rebuilt_available=False,
        available_at_detection=None,
    )
    results["biya_days_to_cover_comparison"] = build_field_comparison(
        "days_to_cover",
        OriginalFieldValue(
            field_id="days_to_cover",
            display_label="Days to Cover",
            internal_field_name="DaysToCover",
            state=OriginalValueState.UNKNOWN,
        ),
        rebuilt_available=False,
        available_at_detection=None,
        issues=(
            "original numerator (shares_short) unrecorded; twice-monthly FINRA basis",
            "original denominator was a trailing mean of completed daily bars from a 1-hour cache",
        ),
    )
    results["biya_news_timing_comparison"] = build_field_comparison(
        "news_published_at",
        OriginalFieldValue(
            field_id="news_published_at",
            display_label="News Time",
            internal_field_name="timestamp",
            state=OriginalValueState.UNKNOWN,
        ),
        rebuilt_available=False,
        available_at_detection=None,
        issues=(
            "original platform substituted the literal string 'Unknown time' for a missing "
            "publication time, making absence type-indistinguishable from a real value",
        ),
    )

    # --- rule classifications --------------------------------------------------------
    rule_states = {
        "RULE-001-PRIME-SUBPRIME": RuleValidationState.MOMENTUM_DISCOVERY_ONLY,
        "RULE-002-SHORT-INTEREST-COLUMN": RuleValidationState.MISLABELED,
        "RULE-003-DAYS-TO-COVER": RuleValidationState.SUPPORTED_WITH_CORRECTION,
        "RULE-004-NEWS-TIMESTAMP": RuleValidationState.MISSING_DEFAULT_SUBSTITUTION,
        "RULE-005-MARKET-DATA-FRESHNESS": RuleValidationState.UNAVAILABLE_AT_DETECTION,
        "RULE-006-CROSS-PROVIDER-CORROBORATION": RuleValidationState.REDUNDANT,
        "RULE-007-COMPOSITE-SQUEEZE-SCORE": RuleValidationState.SUPPORTED_WITH_CORRECTION,
    }
    validations = tuple(
        build_rule_validation(rule.rule_id, rule_states[rule.rule_id], rule.display_name)
        for rule in ORIGINAL_RULES
    )
    results["biya_rule_validation_collection"] = validations[0]

    # --- outcome and case -------------------------------------------------------------
    biya_outcome = unobserved_outcome(
        "BIYA", detection_time_evidence_id=biya_detection.deterministic_id
    )
    results["biya_outcome_observation"] = biya_outcome

    spec = load_case_spec(CASE_SPEC)
    biya_case = build_case_from_spec(spec)
    results["biya_complete_validation_case"] = biya_case
    assert biya_case.conclusion is not None
    results["biya_methodology_conclusion"] = biya_case.conclusion
    results["public_biya_case_export"] = build_public_validation_case(biya_case)

    return results


def main() -> None:
    results = build_anchor_results()
    anchors: dict[str, str] = {}
    for name, result in results.items():
        anchors[name] = _HASH_FUNCS[type(result).__name__](result)

    ordered_names = sorted(results)
    collection = [results[name] for name in ordered_names]
    anchors["mixed_phase_2v_output"] = canonical_hash(list(collection))
    anchors["serialized_phase_2v_collection"] = hashlib.sha256(
        b"[" + b",".join(_SERIALIZE_FUNCS[type(item).__name__](item) for item in collection) + b"]"
    ).hexdigest()

    # --- comparison-case registry -------------------------------------------------
    registry = build_case_registry(observed_universe_entries())
    manifest_document = {
        "schema_version": "1.0.0",
        "description": (
            "Symbols observed in the platform's own screening universe alongside BIYA on "
            "2026-07-17. None is cased: the application log records no field value, label, or "
            "score for any of them, and no market data exists locally. Fixture provenance: "
            "SANITIZED_LOCAL_ARTIFACT. Completion is never inferred from a ticker appearing in "
            "a log."
        ),
        "cases": [json.loads(canonical_json_bytes(entry)) for entry in registry],
        "acquisition_manifest": [dict(row) for row in acquisition_manifest(registry)],
    }
    _write_text_lf(CASE_MANIFEST, json.dumps(manifest_document, indent=2) + "\n")
    anchors["comparison_case_manifest"] = hashlib.sha256(
        CASE_MANIFEST.read_bytes()
    ).hexdigest()

    # --- CLI output ----------------------------------------------------------------
    cli = subprocess.run(
        [
            sys.executable, "-m", "squeeze_core", "build-candidate-validation",
            "--case-spec", str(CASE_SPEC),
        ],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    anchors["phase_2v_cli_output"] = hashlib.sha256(cli.stdout.encode("utf-8")).hexdigest()

    # --- public demo payload --------------------------------------------------------
    biya_case = results["biya_complete_validation_case"]
    public = build_public_validation_case(biya_case)  # type: ignore[arg-type]
    DEMO_DATA.parent.mkdir(parents=True, exist_ok=True)
    DEMO_DATA.write_bytes(serialize_public_case(public) + b"\n")
    anchors["phase_2v_demo_data_output"] = hashlib.sha256(DEMO_DATA.read_bytes()).hexdigest()

    # --- artifact inventory ----------------------------------------------------------
    anchors["biya_artifact_inventory"] = canonical_hash(
        list(biya_case.artifacts)  # type: ignore[union-attr]
    )

    fixture_metadata = {
        "schema_version": "1.0.0",
        "description": (
            "Provenance classification for every Phase 2V fixture. SANITIZED_LOCAL_ARTIFACT "
            "entries trace to an artifact id recorded in docs/phase-2v-biya-artifact-inventory.md; "
            "SYNTHETIC_EDGE_CASE entries are constructed to exercise a branch and are never "
            "presented as recorded evidence."
        ),
        "fixtures": {
            "biya_validation_case.json": {
                "provenance": "SANITIZED_LOCAL_ARTIFACT",
                "notes": (
                    "Real local evidence. Absolute paths reduced to workspace-relative form; the "
                    "Finviz credential present in ART-001 is excluded entirely. Every original "
                    "field value is UNKNOWN because no surviving artifact records one."
                ),
            },
            "phase_2v_comparison_case_manifest.json": {
                "provenance": "SANITIZED_LOCAL_ARTIFACT",
                "notes": "Symbols really observed in the screening universe; none is cased.",
            },
            "expected_phase_2v_validation_metadata.json": {
                "provenance": "SANITIZED_LOCAL_ARTIFACT",
                "notes": "Anchor hashes regenerated by scripts/generate_phase_2v_anchors.py.",
            },
        },
        "synthetic_anchor_inputs": {
            "detection_time_exact_case": "SYNTHETIC_EDGE_CASE",
            "detection_time_unknown_case": "SYNTHETIC_EDGE_CASE",
        },
    }
    _write_text_lf(FIXTURE_METADATA, json.dumps(fixture_metadata, indent=2) + "\n")

    metadata = {
        "schema_version": "1.0.0",
        "description": (
            "Phase 2V anchor hashes. Each validation result is hashed with its dedicated "
            "*_hash() helper in squeeze_core.validation.serialization; mixed_phase_2v_output is "
            "canonical_hash() of the sorted-by-name result list; serialized_phase_2v_collection "
            "is sha256 of the concatenated per-result canonical JSON bytes; phase_2v_cli_output "
            "is sha256 of build-candidate-validation stdout for biya_validation_case.json; "
            "phase_2v_demo_data_output is sha256 of the deterministic public export. This is a "
            "Phase 2V-only manifest, separate from the Phase 1/2A/2B/2C/2D manifests; none of "
            "those files is written by this script."
        ),
        "anchor_result_order": ordered_names,
        "anchors": dict(sorted(anchors.items())),
    }
    _write_text_lf(OUT_PATH, json.dumps(metadata, indent=2, sort_keys=False) + "\n")
    print(f"wrote {OUT_PATH}")
    print(f"wrote {CASE_MANIFEST}")
    print(f"wrote {FIXTURE_METADATA}")
    print(f"wrote {DEMO_DATA}")


if __name__ == "__main__":
    main()

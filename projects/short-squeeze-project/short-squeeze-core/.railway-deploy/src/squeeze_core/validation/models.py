import re
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from squeeze_core.contracts import Quality
from squeeze_core.contracts.validation import require_aware_utc

from .diagnostics import ValidationDiagnostic

# A drive-rooted ("C:\..."), UNC ("\\host\share"), or POSIX-absolute ("/home/...") path.
# Absolute local paths must never reach canonical serialization -- they leak the
# operator's filesystem layout into hashes and into any downstream export
# (docs/phase-2v-design.md Section 6).
_ABSOLUTE_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|\\\\|/)")


def _sorted_str_tuple(value: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(value))


def _reject_absolute_path(value: str) -> str:
    if _ABSOLUTE_PATH.match(value):
        raise ValueError(
            "relative_path must be workspace-relative; absolute local paths are "
            "excluded from canonical serialization"
        )
    return value


class ArtifactReliabilityClass(StrEnum):
    """How much weight an artifact's own claims can carry.

    FILESYSTEM_METADATA_ONLY exists specifically so a file mtime can be recorded as
    evidence without ever being promoted to a platform event time
    (docs/phase-2v-design.md Section 5)."""

    DIRECT_PLATFORM_RECORD = "DIRECT_PLATFORM_RECORD"
    DERIVED_FROM_PLATFORM_RECORD = "DERIVED_FROM_PLATFORM_RECORD"
    EXTERNAL_CORROBORATION = "EXTERNAL_CORROBORATION"
    FILESYSTEM_METADATA_ONLY = "FILESYSTEM_METADATA_ONLY"
    USER_RECOLLECTION = "USER_RECOLLECTION"
    UNKNOWN = "UNKNOWN"


class ArtifactAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    NOT_FOUND = "NOT_FOUND"
    UNREADABLE = "UNREADABLE"


class DetectionTimeState(StrEnum):
    """Exactly three members. There is deliberately no APPROXIMATE or ESTIMATED state:
    an approximate time is a bounded window, and manufacturing a point estimate to make
    replay easier is the specific failure this vocabulary prevents."""

    EXACT_TIMESTAMP = "EXACT_TIMESTAMP"
    BOUNDED_TIME_WINDOW = "BOUNDED_TIME_WINDOW"
    UNKNOWN = "UNKNOWN"


class OriginalValueState(StrEnum):
    """Distinguishes 'the original system recorded a zero' from 'we do not know what
    the original system recorded'. UNKNOWN is the default everywhere."""

    RECOVERED = "RECOVERED"
    MISSING_IN_ARTIFACT = "MISSING_IN_ARTIFACT"
    DEFAULT_SUBSTITUTED = "DEFAULT_SUBSTITUTED"
    DERIVED = "DERIVED"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


class ComparisonState(StrEnum):
    MATCH = "MATCH"
    MATCH_WITH_NORMALIZATION = "MATCH_WITH_NORMALIZATION"
    DIFFERENT_VALUE = "DIFFERENT_VALUE"
    DIFFERENT_SEMANTICS = "DIFFERENT_SEMANTICS"
    ORIGINAL_MISSING = "ORIGINAL_MISSING"
    REBUILT_UNAVAILABLE = "REBUILT_UNAVAILABLE"
    ORIGINAL_DEFAULT_SUBSTITUTION = "ORIGINAL_DEFAULT_SUBSTITUTION"
    ORIGINAL_MISLABELED = "ORIGINAL_MISLABELED"
    INCOMPARABLE = "INCOMPARABLE"
    UNKNOWN = "UNKNOWN"


class RuleValidationState(StrEnum):
    """Methodology judgements about a rule -- never candidate-quality or trading
    labels. STALE is descriptive only: Phase 2V applies no staleness threshold because
    no versioned policy defines one (ADR 0035, ADR 0039)."""

    SUPPORTED = "SUPPORTED"
    SUPPORTED_WITH_CORRECTION = "SUPPORTED_WITH_CORRECTION"
    MOMENTUM_DISCOVERY_ONLY = "MOMENTUM_DISCOVERY_ONLY"
    MISLABELED = "MISLABELED"
    STALE = "STALE"
    UNAVAILABLE_AT_DETECTION = "UNAVAILABLE_AT_DETECTION"
    MISSING_DEFAULT_SUBSTITUTION = "MISSING_DEFAULT_SUBSTITUTION"
    REDUNDANT = "REDUNDANT"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class OutcomeWindow(StrEnum):
    MINUTES_15 = "15_MINUTES"
    MINUTES_30 = "30_MINUTES"
    HOUR_1 = "1_HOUR"
    SESSION_CLOSE = "SESSION_CLOSE"
    NEXT_SESSION_OPEN = "NEXT_SESSION_OPEN"
    NEXT_SESSION_CLOSE = "NEXT_SESSION_CLOSE"
    HOURS_24 = "24_HOURS"


class MethodologyConclusion(StrEnum):
    VALIDATED_AS_RECORDED = "VALIDATED_AS_RECORDED"
    PARTIALLY_VALIDATED = "PARTIALLY_VALIDATED"
    OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED = "OUTCOME_CONFIRMED_METHODOLOGY_UNVERIFIED"
    NOT_POINT_IN_TIME_VALID = "NOT_POINT_IN_TIME_VALID"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class CaseStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    ARTIFACT_DISCOVERY_ONLY = "ARTIFACT_DISCOVERY_ONLY"
    BLOCKED_MISSING_DETECTION_TIME = "BLOCKED_MISSING_DETECTION_TIME"
    BLOCKED_MISSING_ORIGINAL_OUTPUT = "BLOCKED_MISSING_ORIGINAL_OUTPUT"
    BLOCKED_MISSING_MARKET_DATA = "BLOCKED_MISSING_MARKET_DATA"


class FixtureProvenanceClass(StrEnum):
    LOCAL_RECORDED_ARTIFACT = "LOCAL_RECORDED_ARTIFACT"
    SANITIZED_LOCAL_ARTIFACT = "SANITIZED_LOCAL_ARTIFACT"
    SANITIZED_REPRESENTATIVE_SAMPLE = "SANITIZED_REPRESENTATIVE_SAMPLE"
    SYNTHETIC_EDGE_CASE = "SYNTHETIC_EDGE_CASE"


class ValidationArtifact(BaseModel):
    """One immutable provenance entry. Two artifacts sharing a content_hash at
    different paths remain two entries -- the duplication is a finding, not something
    to collapse."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str
    artifact_type: str
    repository_or_source: str
    relative_path: str
    content_hash: str | None = None
    availability: ArtifactAvailability = ArtifactAvailability.AVAILABLE
    created_time_if_known: datetime | None = None
    modified_time_if_known: datetime | None = None
    embedded_event_time_if_known: datetime | None = None
    timezone_if_known: str | None = None
    reliability_class: ArtifactReliabilityClass = ArtifactReliabilityClass.UNKNOWN
    limitations: tuple[str, ...] = ()
    sensitive: bool = False
    included_in_public_demo: bool = False
    # Whether this artifact's times constrain *this candidate's* detection event. An
    # artifact can be genuine evidence about the case while bounding nothing about when
    # the candidate was surfaced -- an email that never mentions the symbol, or a design
    # note written hours later. Such an artifact's mtime must not silently widen the
    # detection window, so bounding is opt-in per artifact rather than assumed from mere
    # presence in the case.
    bounds_detection_event: bool = True

    @field_validator("relative_path")
    @classmethod
    def reject_absolute(cls, value: str) -> str:
        return _reject_absolute_path(value)

    @field_validator("limitations")
    @classmethod
    def sort_limitations(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @field_validator(
        "created_time_if_known", "modified_time_if_known", "embedded_event_time_if_known"
    )
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)

    @model_validator(mode="after")
    def sensitive_artifacts_stay_private(self) -> "ValidationArtifact":
        if self.sensitive and self.included_in_public_demo:
            raise ValueError(
                "a sensitive artifact cannot be included in the public demo; export a "
                "sanitized derivative as its own artifact instead"
            )
        return self


class DetectionTimeEvidence(BaseModel):
    """Resolved detection time for one symbol, plus the reasoning that produced it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    state: DetectionTimeState
    exact_timestamp: datetime | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    timezone: str | None = None
    source_artifact_ids: tuple[str, ...] = ()
    source_artifact_types: tuple[str, ...] = ()
    evidence_notes: tuple[str, ...] = ()
    confidence_basis: str | None = None
    quality: Quality
    diagnostics: tuple[ValidationDiagnostic, ...] = ()
    deterministic_id: str

    @field_validator("source_artifact_ids", "source_artifact_types", "evidence_notes")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @field_validator("exact_timestamp", "window_start", "window_end")
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)

    @model_validator(mode="after")
    def state_matches_fields(self) -> "DetectionTimeEvidence":
        if self.state is DetectionTimeState.EXACT_TIMESTAMP:
            if self.exact_timestamp is None:
                raise ValueError("EXACT_TIMESTAMP requires exact_timestamp")
            if self.window_start is not None or self.window_end is not None:
                raise ValueError("EXACT_TIMESTAMP cannot also carry a window")
        elif self.state is DetectionTimeState.BOUNDED_TIME_WINDOW:
            if self.window_start is None and self.window_end is None:
                raise ValueError("BOUNDED_TIME_WINDOW requires at least one bound")
            if self.exact_timestamp is not None:
                raise ValueError("BOUNDED_TIME_WINDOW cannot also carry an exact timestamp")
            if (
                self.window_start is not None
                and self.window_end is not None
                and self.window_start > self.window_end
            ):
                raise ValueError("window_start must not follow window_end")
        elif self.exact_timestamp is not None or self.window_start or self.window_end:
            raise ValueError("UNKNOWN detection time cannot carry any timestamp")
        return self


class OriginalRuleDefinition(BaseModel):
    """Descriptive evidence about a rule as actually implemented. Never silently
    corrected -- where implementation and documentation disagree, both are recorded."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    display_name: str
    implemented_formula: str
    intended_meaning: str | None = None
    actual_input_fields: tuple[str, ...] = ()
    providers: tuple[str, ...] = ()
    thresholds: tuple[str, ...] = ()
    missing_value_behavior: str | None = None
    timestamp_behavior: str | None = None
    unit_behavior: str | None = None
    original_output_field: str | None = None
    known_mislabeling: str | None = None
    source_file: str | None = None
    source_lines_or_symbol: str | None = None
    source_commit: str | None = None
    documented_but_not_implemented: bool = False
    implemented_but_not_documented: bool = False

    @field_validator("actual_input_fields", "providers", "thresholds")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @field_validator("source_file")
    @classmethod
    def reject_absolute(cls, value: str | None) -> str | None:
        return None if value is None else _reject_absolute_path(value)


class OriginalFieldValue(BaseModel):
    """One displayed field's original value. `value` is None whenever `state` is not
    RECOVERED/DEFAULT_SUBSTITUTED/DERIVED -- an unknown is never rendered as 0 or ""."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field_id: str
    display_label: str | None = None
    internal_field_name: str | None = None
    state: OriginalValueState = OriginalValueState.UNKNOWN
    value: str | Decimal | bool | None = None
    unit: str | None = None
    provider: str | None = None
    source_timestamp: datetime | None = None
    substituted_default: str | None = None
    ambiguity_note: str | None = None
    source_artifact_ids: tuple[str, ...] = ()

    @field_validator("source_artifact_ids")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @field_validator("source_timestamp")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)

    @model_validator(mode="after")
    def unknown_carries_no_value(self) -> "OriginalFieldValue":
        # AMBIGUOUS belongs here: the value *was* recovered, it is its meaning or unit
        # that is unclear. Only genuinely absent states must stay null.
        valued = {
            OriginalValueState.RECOVERED,
            OriginalValueState.DEFAULT_SUBSTITUTED,
            OriginalValueState.DERIVED,
            OriginalValueState.AMBIGUOUS,
        }
        if self.state not in valued and self.value is not None:
            raise ValueError(
                f"state {self.state.value} cannot carry a value; an unrecovered "
                "original field must stay null rather than be filled in"
            )
        if self.state is OriginalValueState.DEFAULT_SUBSTITUTED and self.substituted_default is None:
            raise ValueError("DEFAULT_SUBSTITUTED requires substituted_default")
        return self


class OriginalRuleResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    state: OriginalValueState = OriginalValueState.UNKNOWN
    outcome: str | None = None
    contributing_field_ids: tuple[str, ...] = ()

    @field_validator("contributing_field_ids")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @model_validator(mode="after")
    def unknown_carries_no_outcome(self) -> "OriginalRuleResult":
        if self.state is OriginalValueState.UNKNOWN and self.outcome is not None:
            raise ValueError("an UNKNOWN rule result cannot carry an outcome")
        return self


class OriginalCandidateSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    detection_time_evidence_id: str | None = None
    original_field_values: tuple[OriginalFieldValue, ...] = ()
    original_rule_results: tuple[OriginalRuleResult, ...] = ()
    original_score_if_any: str | None = None
    original_label_if_any: str | None = None
    source_artifact_ids: tuple[str, ...] = ()
    missing_fields: tuple[str, ...] = ()
    default_substitutions: tuple[str, ...] = ()
    unknown_fields: tuple[str, ...] = ()
    quality: Quality
    diagnostics: tuple[ValidationDiagnostic, ...] = ()
    deterministic_id: str

    @field_validator("source_artifact_ids", "missing_fields", "default_substitutions", "unknown_fields")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @field_validator("original_field_values")
    @classmethod
    def sort_values(cls, value: tuple[OriginalFieldValue, ...]) -> tuple[OriginalFieldValue, ...]:
        return tuple(sorted(value, key=lambda item: item.field_id))

    @field_validator("original_rule_results")
    @classmethod
    def sort_results(cls, value: tuple[OriginalRuleResult, ...]) -> tuple[OriginalRuleResult, ...]:
        return tuple(sorted(value, key=lambda item: item.rule_id))


class RebuiltAsOfSnapshot(BaseModel):
    """One strict as-of replay. Every diagnostic field here is produced by Phase 1
    evidence and Phase 2D readiness -- this model stores their ids and states, it does
    not recompute them (docs/phase-2v-design.md Section 3)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str
    symbol: str
    as_of: datetime
    eligible_observation_ids: tuple[str, ...] = ()
    eligible_metric_ids: tuple[str, ...] = ()
    coverage_snapshot_id: str | None = None
    age_alignment_id: str | None = None
    reporting_alignment_id: str | None = None
    conflict_summary_id: str | None = None
    missingness_summary_id: str | None = None
    sufficiency_result_id: str | None = None
    operation: str | None = None
    structural_state: str | None = None
    present_domains: tuple[str, ...] = ()
    missing_domains: tuple[str, ...] = ()
    conflicted_domains: tuple[str, ...] = ()
    metric_results: tuple[str, ...] = ()
    quality: Quality
    diagnostics: tuple[ValidationDiagnostic, ...] = ()
    deterministic_id: str

    @field_validator(
        "eligible_observation_ids",
        "eligible_metric_ids",
        "present_domains",
        "missing_domains",
        "conflicted_domains",
        "metric_results",
    )
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return require_aware_utc(value)


class FieldComparisonEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    field_id: str
    display_name: str | None = None
    original_value: str | Decimal | bool | None = None
    original_unit: str | None = None
    original_provider: str | None = None
    rebuilt_value: str | Decimal | bool | None = None
    rebuilt_unit: str | None = None
    rebuilt_provider: str | None = None
    available_at_detection: bool | None = None
    original_source_time: datetime | None = None
    rebuilt_source_time: datetime | None = None
    reporting_period: date | None = None
    availability_age_seconds: int | None = Field(default=None, ge=0)
    reporting_period_age_seconds: int | None = Field(default=None, ge=0)
    publication_lag_seconds: int | None = Field(default=None, ge=0)
    comparison_state: ComparisonState = ComparisonState.UNKNOWN
    issues: tuple[str, ...] = ()
    supporting_artifact_ids: tuple[str, ...] = ()
    supporting_observation_ids: tuple[str, ...] = ()
    supporting_metric_ids: tuple[str, ...] = ()
    deterministic_id: str

    @field_validator(
        "issues", "supporting_artifact_ids", "supporting_observation_ids", "supporting_metric_ids"
    )
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @field_validator("original_source_time", "rebuilt_source_time")
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)


class RuleValidationEntry(BaseModel):
    """A methodology classification for one original rule.

    This model deliberately has no score, rank, confidence, recommendation, tier, or
    trading-label field. tests/validation/test_rule_validation.py asserts the absence
    by scanning canonical JSON keys, so a future field cannot quietly reintroduce
    one."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rule_id: str
    state: RuleValidationState = RuleValidationState.UNKNOWN
    rationale: str
    corrections_required: tuple[str, ...] = ()
    supporting_artifact_ids: tuple[str, ...] = ()
    supporting_field_ids: tuple[str, ...] = ()
    diagnostics: tuple[ValidationDiagnostic, ...] = ()
    deterministic_id: str

    @field_validator("corrections_required", "supporting_artifact_ids", "supporting_field_ids")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)


class OutcomeWindowObservation(BaseModel):
    """One evaluation window. `observed` False means the bars were absent -- the window
    is reported as uncomputable rather than dropped or zero-filled."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    window: OutcomeWindow
    observed: bool = False
    window_end_time: datetime | None = None
    high_price: Decimal | None = None
    low_price: Decimal | None = None
    close_price: Decimal | None = None
    volume: int | None = Field(default=None, ge=0)
    return_percent: Decimal | None = None
    limitations: tuple[str, ...] = ()

    @field_validator("limitations")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @field_validator("window_end_time")
    @classmethod
    def normalize_time(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)

    @model_validator(mode="after")
    def unobserved_carries_no_values(self) -> "OutcomeWindowObservation":
        if not self.observed and any(
            item is not None
            for item in (self.high_price, self.low_price, self.close_price, self.volume, self.return_percent)
        ):
            raise ValueError("an unobserved window cannot carry price or volume values")
        return self


class CandidateOutcomeObservation(BaseModel):
    """Retrospective price/volume observation. Explicitly not a trade and not a
    backtest.

    There is no field for fill price, entry, exit, position size, P&L, return on
    capital, stop, target, or a squeeze verdict, so none can be populated. Observed
    movement and causal interpretation are kept in separate fields, and
    `causal_interpretation` is never auto-populated from price movement
    (docs/phase-2v-design.md Section 11)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    detection_time_evidence_id: str | None = None
    reference_price: Decimal | None = None
    reference_price_time: datetime | None = None
    subsequent_windows: tuple[OutcomeWindowObservation, ...] = ()
    maximum_observed_price: Decimal | None = None
    maximum_observed_return_percent: Decimal | None = None
    time_to_maximum_seconds: int | None = Field(default=None, ge=0)
    minimum_observed_price: Decimal | None = None
    maximum_adverse_move_percent: Decimal | None = None
    halt_events: tuple[str, ...] = ()
    volume_observations: tuple[str, ...] = ()
    window_end: datetime | None = None
    data_sources: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    causal_interpretation: str | None = None
    quality: Quality
    diagnostics: tuple[ValidationDiagnostic, ...] = ()
    deterministic_id: str

    @field_validator("halt_events", "volume_observations", "data_sources", "limitations")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @field_validator("subsequent_windows")
    @classmethod
    def sort_windows(
        cls, value: tuple[OutcomeWindowObservation, ...]
    ) -> tuple[OutcomeWindowObservation, ...]:
        return tuple(sorted(value, key=lambda item: item.window.value))

    @field_validator("reference_price_time", "window_end")
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)


class ValidationCaseConclusion(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    symbol: str
    conclusion: MethodologyConclusion
    rationale: str
    supporting_findings: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    quality: Quality
    diagnostics: tuple[ValidationDiagnostic, ...] = ()
    deterministic_id: str

    @field_validator("supporting_findings", "limitations")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)


class ValidationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    symbol: str
    case_status: CaseStatus
    artifacts: tuple[ValidationArtifact, ...] = ()
    detection_time_evidence: DetectionTimeEvidence | None = None
    original_rules: tuple[OriginalRuleDefinition, ...] = ()
    original_snapshot: OriginalCandidateSnapshot | None = None
    replays: tuple[RebuiltAsOfSnapshot, ...] = ()
    field_comparisons: tuple[FieldComparisonEntry, ...] = ()
    rule_validations: tuple[RuleValidationEntry, ...] = ()
    outcome_observation: CandidateOutcomeObservation | None = None
    conclusion: ValidationCaseConclusion | None = None
    limitations: tuple[str, ...] = ()
    quality: Quality
    diagnostics: tuple[ValidationDiagnostic, ...] = ()
    deterministic_id: str

    @field_validator("limitations")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @field_validator("artifacts")
    @classmethod
    def sort_artifacts(cls, value: tuple[ValidationArtifact, ...]) -> tuple[ValidationArtifact, ...]:
        return tuple(sorted(value, key=lambda item: item.artifact_id))

    @field_validator("original_rules")
    @classmethod
    def sort_rules(
        cls, value: tuple[OriginalRuleDefinition, ...]
    ) -> tuple[OriginalRuleDefinition, ...]:
        return tuple(sorted(value, key=lambda item: item.rule_id))

    @field_validator("replays")
    @classmethod
    def sort_replays(cls, value: tuple[RebuiltAsOfSnapshot, ...]) -> tuple[RebuiltAsOfSnapshot, ...]:
        return tuple(sorted(value, key=lambda item: (item.as_of, item.label)))

    @field_validator("field_comparisons")
    @classmethod
    def sort_comparisons(
        cls, value: tuple[FieldComparisonEntry, ...]
    ) -> tuple[FieldComparisonEntry, ...]:
        return tuple(sorted(value, key=lambda item: item.field_id))

    @field_validator("rule_validations")
    @classmethod
    def sort_validations(
        cls, value: tuple[RuleValidationEntry, ...]
    ) -> tuple[RuleValidationEntry, ...]:
        return tuple(sorted(value, key=lambda item: item.rule_id))


class ComparisonCaseEntry(BaseModel):
    """Registry entry for a candidate that may become a case. `case_status` never
    reports COMPLETE on the strength of artifact discovery alone."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    symbol: str
    case_status: CaseStatus
    detection_time_state: DetectionTimeState = DetectionTimeState.UNKNOWN
    artifact_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    acquisition_needs: tuple[str, ...] = ()

    @field_validator("artifact_ids", "limitations", "acquisition_needs")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)


class PublicValidationCase(BaseModel):
    """Whitelist projection for the static demo. Built field by field from a
    ValidationCase rather than copied and stripped, so a newly added internal field is
    absent from the export by default instead of leaking until someone remembers to
    redact it (docs/phase-2v-design.md Section 14)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str
    symbol: str
    case_status: CaseStatus
    schema_version: str = "1.0.0"
    detection_time_state: DetectionTimeState
    detection_window_start: datetime | None = None
    detection_window_end: datetime | None = None
    detection_timezone: str | None = None
    detection_confidence_basis: str | None = None
    artifact_summaries: tuple[str, ...] = ()
    rules: tuple[dict[str, str], ...] = ()
    field_comparisons: tuple[dict[str, str], ...] = ()
    replay_labels: tuple[str, ...] = ()
    outcome_available: bool = False
    outcome_limitations: tuple[str, ...] = ()
    conclusion: MethodologyConclusion
    conclusion_rationale: str
    limitations: tuple[str, ...] = ()
    deterministic_id: str

    @field_validator("artifact_summaries", "replay_labels", "outcome_limitations", "limitations")
    @classmethod
    def sort_strings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _sorted_str_tuple(value)

    @field_validator("detection_window_start", "detection_window_end")
    @classmethod
    def normalize_times(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware_utc(value)


__all__ = [
    "ArtifactAvailability",
    "ArtifactReliabilityClass",
    "CandidateOutcomeObservation",
    "CaseStatus",
    "ComparisonCaseEntry",
    "ComparisonState",
    "DetectionTimeEvidence",
    "DetectionTimeState",
    "FieldComparisonEntry",
    "FixtureProvenanceClass",
    "MethodologyConclusion",
    "OriginalCandidateSnapshot",
    "OriginalFieldValue",
    "OriginalRuleDefinition",
    "OriginalRuleResult",
    "OriginalValueState",
    "OutcomeWindow",
    "OutcomeWindowObservation",
    "PublicValidationCase",
    "RebuiltAsOfSnapshot",
    "RuleValidationEntry",
    "RuleValidationState",
    "ValidationArtifact",
    "ValidationCase",
    "ValidationCaseConclusion",
]

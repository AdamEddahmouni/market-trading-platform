"""Temporal integrity and point-in-time rules (BUILD 02)."""

from .models import (
    DuplicateClassification,
    TemporalEligibility,
    TemporalIntegrityError,
    TemporalIntegrityReport,
    TemporalViolation,
    TemporalViolationCode,
    TemporalViolationSeverity,
)
from .policy import DEFAULT_TEMPORAL_POLICY, TemporalIntegrityPolicy
from .resolver import MappingTemporalResolver, TemporalReferenceResolver, mapping_resolver
from .selection import eligible_as_of, select_events_as_of, usable_as_of
from .snapshot import require_snapshot_temporally_valid, validate_snapshot_temporal_integrity
from .stream import TemporalStreamObservation, TemporalStreamState
from .validation import (
    classify_duplicate_events,
    event_sort_key,
    inspect_event_temporal_integrity,
    inspect_signal_temporal_integrity,
    inspect_temporal_integrity,
    is_temporally_eligible,
    require_temporally_usable,
    temporal_eligibility,
)

__all__ = [
    "DEFAULT_TEMPORAL_POLICY",
    "DuplicateClassification",
    "MappingTemporalResolver",
    "TemporalEligibility",
    "TemporalIntegrityError",
    "TemporalIntegrityPolicy",
    "TemporalIntegrityReport",
    "TemporalReferenceResolver",
    "TemporalStreamObservation",
    "TemporalStreamState",
    "TemporalViolation",
    "TemporalViolationCode",
    "TemporalViolationSeverity",
    "classify_duplicate_events",
    "eligible_as_of",
    "event_sort_key",
    "inspect_event_temporal_integrity",
    "inspect_signal_temporal_integrity",
    "inspect_temporal_integrity",
    "is_temporally_eligible",
    "mapping_resolver",
    "require_snapshot_temporally_valid",
    "require_temporally_usable",
    "select_events_as_of",
    "temporal_eligibility",
    "usable_as_of",
    "validate_snapshot_temporal_integrity",
]

"""Resolving when a candidate was detected, from artifact evidence alone.

The single rule this module exists to enforce: an exact detection timestamp requires an
artifact that *directly records the candidate event time*. Filesystem metadata,
screenshots, emails, and meeting recordings bound a window -- they never produce
EXACT_TIMESTAMP, however convenient that would make replay.
"""

from collections.abc import Sequence
from datetime import datetime

from squeeze_core.adapters.diagnostics import DiagnosticSeverity
from squeeze_core.contracts import Quality
from squeeze_core.contracts.enums import QualityState

from .diagnostics import ValidationDiagnostic, ValidationDiagnosticCode, sort_diagnostics
from .identifiers import detection_time_identity, deterministic_validation_id
from .models import (
    ArtifactAvailability,
    ArtifactReliabilityClass,
    DetectionTimeEvidence,
    DetectionTimeState,
    ValidationArtifact,
)

# Only a direct platform record can carry an exact event time, and only through its
# *embedded* event time -- a time the platform itself wrote into the artifact. A
# filesystem mtime on a direct platform record still bounds rather than fixes.
_EXACT_ELIGIBLE = frozenset({ArtifactReliabilityClass.DIRECT_PLATFORM_RECORD})


def _bounds_from_artifact(
    artifact: ValidationArtifact,
) -> tuple[datetime | None, datetime | None]:
    """Lower and upper bounds an artifact places on a detection event.

    A created time bounds below (the event cannot precede the run that wrote the file);
    a modified time bounds above (the event happened by the time writing stopped). An
    embedded event time bounds both."""

    if artifact.embedded_event_time_if_known is not None:
        return artifact.embedded_event_time_if_known, artifact.embedded_event_time_if_known
    return artifact.created_time_if_known, artifact.modified_time_if_known


def build_detection_time_evidence(
    symbol: str,
    artifacts: Sequence[ValidationArtifact],
    *,
    timezone_label: str | None = None,
    confidence_basis: str | None = None,
    evidence_notes: Sequence[str] = (),
    allow_exact: bool = True,
) -> DetectionTimeEvidence:
    """Resolve detection time for `symbol` from `artifacts`.

    Returns EXACT_TIMESTAMP only when a direct platform record carries an embedded
    event time and every other exact-eligible record agrees. Disagreement widens to a
    bounded window rather than silently choosing one -- a conflict is evidence about
    uncertainty, not a tie to be broken.
    """

    usable = [
        artifact
        for artifact in artifacts
        if artifact.availability is ArtifactAvailability.AVAILABLE
        and artifact.bounds_detection_event
    ]

    diagnostics: list[ValidationDiagnostic] = []
    lower_bounds: list[tuple[datetime, str]] = []
    upper_bounds: list[tuple[datetime, str]] = []
    exact_candidates: list[tuple[datetime, str]] = []
    contributing: list[ValidationArtifact] = []

    for artifact in usable:
        lower, upper = _bounds_from_artifact(artifact)
        if lower is None and upper is None:
            continue
        contributing.append(artifact)
        if lower is not None:
            lower_bounds.append((lower, artifact.artifact_id))
        if upper is not None:
            upper_bounds.append((upper, artifact.artifact_id))

        if (
            artifact.embedded_event_time_if_known is not None
            and artifact.reliability_class in _EXACT_ELIGIBLE
        ):
            exact_candidates.append((artifact.embedded_event_time_if_known, artifact.artifact_id))
        elif artifact.reliability_class is ArtifactReliabilityClass.FILESYSTEM_METADATA_ONLY:
            diagnostics.append(
                ValidationDiagnostic(
                    code=ValidationDiagnosticCode.VALIDATION_DETECTION_TIME_FILESYSTEM_ONLY,
                    severity=DiagnosticSeverity.INFO,
                    message=(
                        "filesystem metadata bounds the detection window but cannot fix an "
                        "exact detection time"
                    ),
                    artifact_id=artifact.artifact_id,
                )
            )

    distinct_exact = sorted({moment for moment, _ in exact_candidates})

    if allow_exact and len(distinct_exact) == 1:
        state = DetectionTimeState.EXACT_TIMESTAMP
        exact = distinct_exact[0]
        window_start = window_end = None
    else:
        if len(distinct_exact) > 1:
            diagnostics.append(
                ValidationDiagnostic(
                    code=ValidationDiagnosticCode.VALIDATION_DETECTION_TIME_CONFLICTED,
                    severity=DiagnosticSeverity.WARNING,
                    message=(
                        "direct platform records disagree on the event time; widening to the "
                        "interval they jointly permit rather than selecting one"
                    ),
                )
            )
            # A conflict must not narrow the window: fold the disagreeing exact times
            # into the bounds so the result spans every claim.
            lower_bounds.extend((moment, artifact_id) for moment, artifact_id in exact_candidates)
            upper_bounds.extend((moment, artifact_id) for moment, artifact_id in exact_candidates)

        exact = None
        window_start = min((moment for moment, _ in lower_bounds), default=None)
        window_end = max((moment for moment, _ in upper_bounds), default=None)
        state = (
            DetectionTimeState.BOUNDED_TIME_WINDOW
            if window_start is not None or window_end is not None
            else DetectionTimeState.UNKNOWN
        )

    if state is DetectionTimeState.BOUNDED_TIME_WINDOW:
        diagnostics.append(
            ValidationDiagnostic(
                code=ValidationDiagnosticCode.VALIDATION_DETECTION_WINDOW_ONLY,
                severity=DiagnosticSeverity.INFO,
                message=(
                    "detection time is bounded, not exact; replay is run at each window edge"
                ),
            )
        )
        # Following the Phase 2D convention: quality describes whether the *computation*
        # succeeded, not how precise its answer is. A bounded window is a successfully
        # determined result; its imprecision is carried by `state`, not by quality.
        quality = Quality(state=QualityState.KNOWN_VALUE)
    elif state is DetectionTimeState.UNKNOWN:
        diagnostics.append(
            ValidationDiagnostic(
                code=ValidationDiagnosticCode.VALIDATION_DETECTION_TIME_UNKNOWN,
                severity=DiagnosticSeverity.WARNING,
                message="no artifact establishes a defensible detection time or bound",
            )
        )
        quality = Quality(
            state=QualityState.MISSING,
            reasons=("no artifact bounds the detection time",),
        )
    else:
        quality = Quality(state=QualityState.KNOWN_VALUE)

    draft = DetectionTimeEvidence(
        symbol=symbol.strip().upper(),
        state=state,
        exact_timestamp=exact,
        window_start=window_start,
        window_end=window_end,
        timezone=timezone_label,
        source_artifact_ids=tuple(item.artifact_id for item in contributing),
        source_artifact_types=tuple({item.artifact_type for item in contributing}),
        evidence_notes=tuple(evidence_notes),
        confidence_basis=confidence_basis,
        quality=quality,
        diagnostics=sort_diagnostics(diagnostics),
        deterministic_id="",
    )
    return draft.model_copy(
        update={"deterministic_id": deterministic_validation_id(detection_time_identity(draft))}
    )


def replay_boundaries(evidence: DetectionTimeEvidence) -> tuple[tuple[str, datetime], ...]:
    """The as-of instants a case must replay at.

    An exact time yields one replay. A bounded window yields both edges -- selecting
    whichever looks more favourable is exactly the failure this returns two values to
    prevent. An unknown detection time yields none.
    """

    if evidence.state is DetectionTimeState.EXACT_TIMESTAMP and evidence.exact_timestamp:
        return (("exact", evidence.exact_timestamp),)
    if evidence.state is DetectionTimeState.BOUNDED_TIME_WINDOW:
        edges: list[tuple[str, datetime]] = []
        if evidence.window_start is not None:
            edges.append(("earliest", evidence.window_start))
        if evidence.window_end is not None:
            edges.append(("latest", evidence.window_end))
        return tuple(edges)
    return ()


__all__ = ["build_detection_time_evidence", "replay_boundaries"]

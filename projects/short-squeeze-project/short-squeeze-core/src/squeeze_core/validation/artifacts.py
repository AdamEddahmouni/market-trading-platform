"""Artifact discovery and provenance, kept separate from interpretation.

Nothing in this module decides what an artifact *means*. It records what exists, what
it hashes to, when the filesystem says it changed, and how much weight its own claims
can carry. Interpretation lives in detection_time.py and original_snapshot.py.
"""

import hashlib
from collections.abc import Iterable, Sequence

from squeeze_core.adapters.diagnostics import DiagnosticSeverity

from .diagnostics import ValidationDiagnostic, ValidationDiagnosticCode, sort_diagnostics
from .models import ArtifactAvailability, ArtifactReliabilityClass, ValidationArtifact


def content_hash(payload: bytes) -> str:
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def sort_artifacts(items: Iterable[ValidationArtifact]) -> tuple[ValidationArtifact, ...]:
    return tuple(sorted(items, key=lambda item: item.artifact_id))


def duplicate_content_groups(
    artifacts: Sequence[ValidationArtifact],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Artifact ids grouped by shared content hash, for hashes claimed by more than one
    artifact. The same bytes at two paths stay two provenance entries -- this reports
    the duplication rather than collapsing it."""

    by_hash: dict[str, list[str]] = {}
    for artifact in artifacts:
        if artifact.content_hash is None:
            continue
        by_hash.setdefault(artifact.content_hash, []).append(artifact.artifact_id)
    return tuple(
        (digest, tuple(sorted(ids)))
        for digest, ids in sorted(by_hash.items())
        if len(ids) > 1
    )


def artifact_diagnostics(
    artifacts: Sequence[ValidationArtifact],
) -> tuple[ValidationDiagnostic, ...]:
    """Structural facts about a set of artifacts. Emits only codes this function can
    actually produce, matching the Phase 2D diagnostics convention."""

    found: list[ValidationDiagnostic] = []

    for artifact in artifacts:
        if artifact.availability is ArtifactAvailability.NOT_FOUND:
            found.append(
                ValidationDiagnostic(
                    code=ValidationDiagnosticCode.VALIDATION_ARTIFACT_NOT_FOUND,
                    severity=DiagnosticSeverity.ERROR,
                    message=f"artifact not found at its recorded path: {artifact.relative_path}",
                    artifact_id=artifact.artifact_id,
                )
            )
            continue
        if artifact.availability is ArtifactAvailability.UNREADABLE:
            found.append(
                ValidationDiagnostic(
                    code=ValidationDiagnosticCode.VALIDATION_ARTIFACT_UNREADABLE,
                    severity=DiagnosticSeverity.ERROR,
                    message=f"artifact could not be read: {artifact.relative_path}",
                    artifact_id=artifact.artifact_id,
                )
            )
            continue

        has_time = (
            artifact.embedded_event_time_if_known is not None
            or artifact.created_time_if_known is not None
            or artifact.modified_time_if_known is not None
        )
        if not has_time:
            found.append(
                ValidationDiagnostic(
                    code=ValidationDiagnosticCode.VALIDATION_ARTIFACT_TIME_UNKNOWN,
                    severity=DiagnosticSeverity.WARNING,
                    message="artifact carries no known created, modified, or embedded event time",
                    artifact_id=artifact.artifact_id,
                )
            )

    for digest, ids in duplicate_content_groups(artifacts):
        for artifact_id in ids:
            found.append(
                ValidationDiagnostic(
                    code=ValidationDiagnosticCode.VALIDATION_ARTIFACT_DUPLICATE_CONTENT,
                    severity=DiagnosticSeverity.INFO,
                    message=(
                        f"identical content ({digest}) also recorded as: "
                        f"{', '.join(other for other in ids if other != artifact_id)}"
                    ),
                    artifact_id=artifact_id,
                )
            )

    return sort_diagnostics(found)


def public_artifacts(
    artifacts: Sequence[ValidationArtifact],
) -> tuple[ValidationArtifact, ...]:
    """Artifacts eligible for public export.

    Both conditions are required: the artifact must be explicitly marked for the demo
    *and* not sensitive. ValidationArtifact already rejects that combination at
    construction, so this is defence in depth rather than the only guard."""

    return sort_artifacts(
        artifact
        for artifact in artifacts
        if artifact.included_in_public_demo and not artifact.sensitive
    )


def public_artifact_summary(artifact: ValidationArtifact) -> str:
    """A sanitized one-line description. Deliberately omits relative_path: even a
    workspace-relative path describes the operator's layout and is unnecessary for a
    reader judging evidence weight."""

    reliability = artifact.reliability_class.value.replace("_", " ").lower()
    return f"{artifact.artifact_id}: {artifact.artifact_type} ({reliability})"


def is_direct_platform_record(artifact: ValidationArtifact) -> bool:
    return artifact.reliability_class is ArtifactReliabilityClass.DIRECT_PLATFORM_RECORD


__all__ = [
    "artifact_diagnostics",
    "content_hash",
    "duplicate_content_groups",
    "is_direct_platform_record",
    "public_artifact_summary",
    "public_artifacts",
    "sort_artifacts",
]

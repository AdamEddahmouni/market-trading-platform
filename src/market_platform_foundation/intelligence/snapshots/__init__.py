"""Immutable snapshot engine (BUILD 05)."""

from .builder import (
    ExclusionReason,
    SnapshotBuildResult,
    SnapshotBuilder,
    SnapshotExclusion,
    build_snapshot,
    compose_snapshot,
    inspect_snapshot_build,
    verify_snapshot_reproducibility,
)
from .canonical import (
    FINGERPRINT_VERSION,
    SNAPSHOT_ID_PREFIX,
    content_fingerprint,
    fingerprint_from_snapshot_parts,
    semantic_payload,
    snapshot_id_from_fingerprint,
    verify_snapshot_fingerprint,
)
from .errors import (
    SnapshotBuildError,
    SnapshotError,
    SnapshotIntegrityError,
    SnapshotQualityError,
    SnapshotReferenceError,
    SnapshotTemporalError,
)
from .policy import (
    BUILDER_COMPONENT_ID,
    BUILDER_COMPONENT_VERSION,
    SnapshotBuildRequest,
    SnapshotCompositionPolicy,
)
from .resolver import (
    RepositoryTemporalResolver,
    SnapshotResolvedState,
    resolve_snapshot,
    verify_snapshot_integrity,
)

__all__ = [
    "BUILDER_COMPONENT_ID",
    "BUILDER_COMPONENT_VERSION",
    "ExclusionReason",
    "FINGERPRINT_VERSION",
    "SNAPSHOT_ID_PREFIX",
    "RepositoryTemporalResolver",
    "SnapshotBuildError",
    "SnapshotBuildRequest",
    "SnapshotBuildResult",
    "SnapshotBuilder",
    "SnapshotCompositionPolicy",
    "SnapshotError",
    "SnapshotExclusion",
    "SnapshotIntegrityError",
    "SnapshotQualityError",
    "SnapshotReferenceError",
    "SnapshotResolvedState",
    "SnapshotTemporalError",
    "build_snapshot",
    "compose_snapshot",
    "content_fingerprint",
    "fingerprint_from_snapshot_parts",
    "inspect_snapshot_build",
    "resolve_snapshot",
    "semantic_payload",
    "snapshot_id_from_fingerprint",
    "verify_snapshot_fingerprint",
    "verify_snapshot_integrity",
    "verify_snapshot_reproducibility",
]

"""Optional capture-context sidecars for receipt artifacts (software-only metadata)."""

from .sidecar import (
    CAPTURE_CONTEXT_ARTIFACT_KIND,
    CAPTURE_CONTEXT_SCHEMA_VERSION,
    CaptureContextError,
    create_capture_context_sidecar,
    default_sidecar_path_for_artifact,
    infer_artifact_evidence_class,
    verify_capture_context_sidecar,
)

__all__ = [
    "CAPTURE_CONTEXT_ARTIFACT_KIND",
    "CAPTURE_CONTEXT_SCHEMA_VERSION",
    "CaptureContextError",
    "create_capture_context_sidecar",
    "default_sidecar_path_for_artifact",
    "infer_artifact_evidence_class",
    "verify_capture_context_sidecar",
]

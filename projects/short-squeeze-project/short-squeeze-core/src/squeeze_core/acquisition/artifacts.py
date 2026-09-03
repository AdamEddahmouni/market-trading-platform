import hashlib
from pathlib import Path

from .models import ArtifactManifest, ArtifactVerificationResult


SUPPORTED_MEDIA_TYPES = {
    "application/json", "application/pdf", "text/csv", "text/html", "text/plain",
    "image/jpeg", "image/png",
}


def verify_artifact_manifest(root: Path, manifest: ArtifactManifest) -> ArtifactVerificationResult:
    verified: list[str] = []
    diagnostics: list[str] = []
    seen_hashes: set[str] = set()
    for artifact in manifest.artifacts:
        if artifact.media_type not in SUPPORTED_MEDIA_TYPES:
            diagnostics.append("UNSUPPORTED_MEDIA_TYPE")
            continue
        path = root.joinpath(*artifact.relative_path.split("/"))
        if not path.is_file():
            diagnostics.append("SOURCE_ARTIFACT_MISSING")
            continue
        content = path.read_bytes()
        if len(content) != artifact.byte_length or hashlib.sha256(content).hexdigest() != artifact.sha256:
            diagnostics.append("SOURCE_ARTIFACT_HASH_MISMATCH")
            continue
        if artifact.sha256 in seen_hashes:
            diagnostics.append("DUPLICATE_ARTIFACT")
            continue
        seen_hashes.add(artifact.sha256)
        verified.append(artifact.artifact_id)
    return ArtifactVerificationResult(
        manifest_id=manifest.manifest_id,
        valid=not diagnostics,
        verified_artifact_ids=tuple(verified),
        diagnostic_codes=tuple(diagnostics),
    )


__all__ = ["SUPPORTED_MEDIA_TYPES", "verify_artifact_manifest"]

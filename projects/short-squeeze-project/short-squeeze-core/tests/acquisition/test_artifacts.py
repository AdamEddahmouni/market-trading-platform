import hashlib
from datetime import UTC, datetime

import pytest

from squeeze_core.acquisition.artifacts import verify_artifact_manifest
from squeeze_core.acquisition.models import (
    ArtifactClassification,
    ArtifactManifest,
    ArtifactRecord,
    DiscoverySourceClass,
)


def _record(content: bytes, **changes):
    values = {
        "artifact_id": "artifact-1",
        "file_name": "source.json",
        "relative_path": "raw/source.json",
        "media_type": "application/json",
        "byte_length": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "source_class": DiscoverySourceClass.ARCHIVED_PROVIDER_RESPONSE,
        "provider_provenance_id": "prov-1",
        "fixture_classification": ArtifactClassification.LOCAL_HISTORICAL_ARTIFACT,
        "capture_method": "LOCAL_EXPORT",
        "observed_at": datetime(2024, 5, 14, tzinfo=UTC),
        "effective_at": datetime(2024, 5, 14, tzinfo=UTC),
        "published_at": datetime(2024, 5, 14, tzinfo=UTC),
        "content_status": "CAPTURED",
        "sensitive_content_status": "NONE",
    }
    values.update(changes)
    return ArtifactRecord(**values)


def test_manifest_verifies_hash_length_and_preserves_source_bytes(tmp_path):
    root = tmp_path / "intake"
    path = root / "raw" / "source.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"{}")
    before = path.read_bytes()
    manifest = ArtifactManifest(manifest_id="manifest-1", artifacts=(_record(before),))
    result = verify_artifact_manifest(root, manifest)
    assert result.valid
    assert result.verified_artifact_ids == ("artifact-1",)
    assert path.read_bytes() == before


def test_manifest_reports_missing_hash_mismatch_and_unsupported_media(tmp_path):
    root = tmp_path / "intake"
    path = root / "raw" / "source.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"changed")
    records = (
        _record(b"{}"),
        _record(b"x", artifact_id="missing", relative_path="raw/missing.json"),
        _record(b"changed", artifact_id="media", relative_path="raw/source.json",
                media_type="application/x-executable"),
    )
    result = verify_artifact_manifest(root, ArtifactManifest(manifest_id="m", artifacts=records))
    assert not result.valid
    assert set(result.diagnostic_codes) == {
        "SOURCE_ARTIFACT_HASH_MISMATCH",
        "SOURCE_ARTIFACT_MISSING",
        "UNSUPPORTED_MEDIA_TYPE",
    }


def test_manifest_rejects_duplicate_artifact_ids():
    record = _record(b"{}")
    with pytest.raises(ValueError, match="duplicate artifact ID"):
        ArtifactManifest(manifest_id="m", artifacts=(record, record))


def test_manifest_reports_duplicate_content_under_different_artifact_ids(tmp_path):
    root = tmp_path / "intake"
    first_path = root / "raw" / "first.json"
    second_path = root / "raw" / "second.json"
    first_path.parent.mkdir(parents=True)
    first_path.write_bytes(b"{}")
    second_path.write_bytes(b"{}")
    manifest = ArtifactManifest(manifest_id="m", artifacts=(
        _record(b"{}", artifact_id="first", relative_path="raw/first.json"),
        _record(b"{}", artifact_id="second", relative_path="raw/second.json"),
    ))
    result = verify_artifact_manifest(root, manifest)
    assert not result.valid
    assert result.diagnostic_codes == ("DUPLICATE_ARTIFACT",)

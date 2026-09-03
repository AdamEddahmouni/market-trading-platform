from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from squeeze_core.serialization import canonical_json_bytes
from squeeze_core.validation import (
    ArtifactAvailability,
    ArtifactReliabilityClass,
    ValidationArtifact,
    ValidationDiagnosticCode,
    artifact_diagnostics,
    content_hash,
    duplicate_content_groups,
    is_direct_platform_record,
    public_artifact_summary,
    public_artifacts,
    sort_artifacts,
)

from .conftest import artifact, biya_log_artifact, unavailable_artifact


def _codes(items) -> set[str]:
    return {item.code.value for item in items}


def test_direct_platform_record_is_recognized():
    assert is_direct_platform_record(biya_log_artifact())


def test_derived_platform_record_is_not_a_direct_record():
    derived = artifact(
        "ART-D", reliability_class=ArtifactReliabilityClass.DERIVED_FROM_PLATFORM_RECORD
    )
    assert not is_direct_platform_record(derived)


def test_filesystem_metadata_only_class_is_representable():
    item = artifact("ART-F", reliability_class=ArtifactReliabilityClass.FILESYSTEM_METADATA_ONLY)
    assert item.reliability_class is ArtifactReliabilityClass.FILESYSTEM_METADATA_ONLY


def test_user_recollection_class_is_representable():
    item = artifact("ART-U", reliability_class=ArtifactReliabilityClass.USER_RECOLLECTION)
    assert item.reliability_class is ArtifactReliabilityClass.USER_RECOLLECTION


def test_unknown_provenance_is_the_default():
    item = ValidationArtifact(
        artifact_id="ART-X",
        artifact_type="NOTE",
        repository_or_source="test",
        relative_path="note.txt",
    )
    assert item.reliability_class is ArtifactReliabilityClass.UNKNOWN


def test_content_hash_is_stable_across_reads():
    payload = b"the same bytes"
    assert content_hash(payload) == content_hash(payload)
    assert content_hash(payload).startswith("sha256:")


def test_artifact_identity_is_stable_under_reserialization():
    item = biya_log_artifact()
    assert canonical_json_bytes(item) == canonical_json_bytes(item.model_copy())


@pytest.mark.parametrize(
    "bad_path",
    ["C:\\Users\\someone\\repo\\app.log", "/home/someone/repo/app.log", "\\\\host\\share\\a.log"],
)
def test_absolute_local_paths_are_rejected(bad_path):
    with pytest.raises(ValidationError, match="workspace-relative"):
        artifact("ART-ABS", relative_path=bad_path)


def test_sensitive_artifact_cannot_be_marked_public():
    with pytest.raises(ValidationError, match="sensitive artifact cannot be included"):
        artifact("ART-S", sensitive=True, included_in_public_demo=True)


def test_sensitive_artifact_is_absent_from_public_export():
    items = (
        biya_log_artifact(),  # sensitive
        artifact("ART-P", sensitive=False, included_in_public_demo=True),
    )
    exported = public_artifacts(items)
    assert [item.artifact_id for item in exported] == ["ART-P"]


def test_duplicate_content_is_detected():
    digest = "sha256:" + "a" * 64
    items = (
        artifact("ART-1", content_hash=digest),
        artifact("ART-2", content_hash=digest, relative_path="copy/app.log"),
        artifact("ART-3", content_hash="sha256:" + "b" * 64),
    )
    assert duplicate_content_groups(items) == ((digest, ("ART-1", "ART-2")),)


def test_same_content_at_two_paths_stays_two_entries():
    digest = "sha256:" + "c" * 64
    items = (
        artifact("ART-1", content_hash=digest, relative_path="a/app.log"),
        artifact("ART-2", content_hash=digest, relative_path="b/app.log"),
    )
    assert len(items) == 2
    assert {item.relative_path for item in items} == {"a/app.log", "b/app.log"}
    assert ValidationDiagnosticCode.VALIDATION_ARTIFACT_DUPLICATE_CONTENT.value in _codes(
        artifact_diagnostics(items)
    )


def test_unreadable_artifact_emits_a_diagnostic():
    items = (unavailable_artifact("ART-BAD", ArtifactAvailability.UNREADABLE),)
    assert ValidationDiagnosticCode.VALIDATION_ARTIFACT_UNREADABLE.value in _codes(
        artifact_diagnostics(items)
    )


def test_missing_artifact_emits_a_diagnostic():
    items = (unavailable_artifact("ART-GONE", ArtifactAvailability.NOT_FOUND),)
    assert ValidationDiagnosticCode.VALIDATION_ARTIFACT_NOT_FOUND.value in _codes(
        artifact_diagnostics(items)
    )


def test_artifact_without_any_known_time_is_flagged():
    items = (artifact("ART-NOTIME"),)
    assert ValidationDiagnosticCode.VALIDATION_ARTIFACT_TIME_UNKNOWN.value in _codes(
        artifact_diagnostics(items)
    )


def test_ordering_is_deterministic_under_input_permutation():
    items = [artifact(f"ART-{index}") for index in range(5)]
    forward = sort_artifacts(items)
    reverse = sort_artifacts(list(reversed(items)))
    assert forward == reverse
    assert [item.artifact_id for item in forward] == sorted(item.artifact_id for item in items)


def test_diagnostic_ordering_is_deterministic():
    items = [
        unavailable_artifact("ART-B", ArtifactAvailability.NOT_FOUND),
        unavailable_artifact("ART-A", ArtifactAvailability.UNREADABLE),
    ]
    assert artifact_diagnostics(items) == artifact_diagnostics(list(reversed(items)))


def test_public_summary_omits_the_path():
    item = artifact("ART-P", relative_path="deep/nested/secret-layout.log", sensitive=False)
    summary = public_artifact_summary(item)
    assert "secret-layout" not in summary
    assert "ART-P" in summary


def test_naive_timestamps_are_rejected():
    with pytest.raises(ValidationError):
        artifact("ART-NAIVE", created_time_if_known=datetime(2026, 7, 17, 10, 0, 0))


def test_timestamps_are_normalized_to_utc():
    item = artifact("ART-TZ", created_time_if_known=datetime(2026, 7, 17, 14, 23, 58, tzinfo=UTC))
    assert item.created_time_if_known is not None
    assert item.created_time_if_known.tzinfo is UTC

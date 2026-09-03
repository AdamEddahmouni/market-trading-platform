from datetime import UTC, datetime

from squeeze_core.contracts.enums import QualityState
from squeeze_core.validation import (
    ArtifactReliabilityClass,
    DetectionTimeState,
    ValidationDiagnosticCode,
    build_detection_time_evidence,
    replay_boundaries,
    serialize_detection_time,
)

from .conftest import (
    BIYA_MEETING_START,
    BIYA_WINDOW_END,
    BIYA_WINDOW_START,
    artifact,
    biya_log_artifact,
    biya_meeting_artifact,
)

EVENT_TIME = datetime(2026, 7, 17, 15, 30, 0, tzinfo=UTC)


def _codes(evidence) -> set[str]:
    return {item.code.value for item in evidence.diagnostics}


def test_exact_timestamp_from_a_direct_platform_record():
    stored = biya_log_artifact(
        artifact_id="ART-STORED", embedded_event_time_if_known=EVENT_TIME
    )
    evidence = build_detection_time_evidence("BIYA", (stored,))
    assert evidence.state is DetectionTimeState.EXACT_TIMESTAMP
    assert evidence.exact_timestamp == EVENT_TIME
    assert evidence.window_start is None and evidence.window_end is None


def test_bounded_window_from_two_artifacts():
    evidence = build_detection_time_evidence(
        "BIYA", (biya_log_artifact(), biya_meeting_artifact())
    )
    assert evidence.state is DetectionTimeState.BOUNDED_TIME_WINDOW
    assert evidence.window_start == BIYA_WINDOW_START
    assert evidence.window_end == BIYA_WINDOW_END


def test_one_sided_lower_bound():
    lower_only = artifact(
        "ART-LOW",
        reliability_class=ArtifactReliabilityClass.FILESYSTEM_METADATA_ONLY,
        created_time_if_known=BIYA_WINDOW_START,
    )
    evidence = build_detection_time_evidence("BIYA", (lower_only,))
    assert evidence.state is DetectionTimeState.BOUNDED_TIME_WINDOW
    assert evidence.window_start == BIYA_WINDOW_START
    assert evidence.window_end is None


def test_one_sided_upper_bound():
    upper_only = artifact(
        "ART-UP",
        reliability_class=ArtifactReliabilityClass.FILESYSTEM_METADATA_ONLY,
        modified_time_if_known=BIYA_WINDOW_END,
    )
    evidence = build_detection_time_evidence("BIYA", (upper_only,))
    assert evidence.state is DetectionTimeState.BOUNDED_TIME_WINDOW
    assert evidence.window_start is None
    assert evidence.window_end == BIYA_WINDOW_END


def test_unknown_when_no_artifact_carries_a_time():
    evidence = build_detection_time_evidence("BIYA", (artifact("ART-NONE"),))
    assert evidence.state is DetectionTimeState.UNKNOWN
    assert evidence.quality.state is QualityState.MISSING
    assert ValidationDiagnosticCode.VALIDATION_DETECTION_TIME_UNKNOWN.value in _codes(evidence)


def test_unknown_when_there_are_no_artifacts_at_all():
    evidence = build_detection_time_evidence("BIYA", ())
    assert evidence.state is DetectionTimeState.UNKNOWN


def test_conflicting_exact_evidence_widens_rather_than_picking_one():
    early = biya_log_artifact(
        artifact_id="ART-E", embedded_event_time_if_known=datetime(2026, 7, 17, 15, 0, tzinfo=UTC)
    )
    late = biya_log_artifact(
        artifact_id="ART-L",
        relative_path="app/logs/other.log",
        embedded_event_time_if_known=datetime(2026, 7, 17, 16, 0, tzinfo=UTC),
    )
    evidence = build_detection_time_evidence("BIYA", (early, late))

    assert evidence.state is DetectionTimeState.BOUNDED_TIME_WINDOW
    assert evidence.exact_timestamp is None
    # The window must span both claims, never collapse onto one of them.
    assert evidence.window_start == datetime(2026, 7, 17, 15, 0, tzinfo=UTC)
    assert evidence.window_end == datetime(2026, 7, 17, 16, 0, tzinfo=UTC)
    assert ValidationDiagnosticCode.VALIDATION_DETECTION_TIME_CONFLICTED.value in _codes(evidence)


def test_timestamps_are_normalized_to_utc():
    from datetime import timedelta, timezone

    eastern = timezone(timedelta(hours=-4))
    local = artifact(
        "ART-TZ",
        embedded_event_time_if_known=datetime(2026, 7, 17, 12, 46, 15, tzinfo=eastern),
    )
    evidence = build_detection_time_evidence("BIYA", (local,))
    assert evidence.exact_timestamp == BIYA_MEETING_START
    assert evidence.exact_timestamp.tzinfo is UTC


def test_filesystem_metadata_alone_never_yields_an_exact_timestamp():
    fs_only = artifact(
        "ART-FS",
        reliability_class=ArtifactReliabilityClass.FILESYSTEM_METADATA_ONLY,
        created_time_if_known=EVENT_TIME,
        modified_time_if_known=EVENT_TIME,
    )
    evidence = build_detection_time_evidence("BIYA", (fs_only,))
    assert evidence.state is DetectionTimeState.BOUNDED_TIME_WINDOW
    assert evidence.exact_timestamp is None
    assert ValidationDiagnosticCode.VALIDATION_DETECTION_TIME_FILESYSTEM_ONLY.value in _codes(
        evidence
    )


def test_screenshot_time_is_bounded_evidence_only():
    screenshot = artifact(
        "ART-SHOT",
        artifact_type="SCREENSHOT",
        relative_path="shots/app.png",
        reliability_class=ArtifactReliabilityClass.FILESYSTEM_METADATA_ONLY,
        created_time_if_known=BIYA_WINDOW_START,
        modified_time_if_known=BIYA_WINDOW_END,
    )
    evidence = build_detection_time_evidence("BIYA", (screenshot,))
    assert evidence.state is DetectionTimeState.BOUNDED_TIME_WINDOW


def test_email_is_corroboration_and_never_an_exact_detection_time():
    email = artifact(
        "ART-MAIL",
        artifact_type="EMAIL_LOG",
        relative_path="email-log.txt",
        reliability_class=ArtifactReliabilityClass.EXTERNAL_CORROBORATION,
        embedded_event_time_if_known=EVENT_TIME,
    )
    evidence = build_detection_time_evidence("BIYA", (email,))
    # An embedded time on an EXTERNAL_CORROBORATION artifact still only bounds.
    assert evidence.state is DetectionTimeState.BOUNDED_TIME_WINDOW
    assert evidence.exact_timestamp is None


def test_artifact_that_does_not_bound_the_event_is_excluded():
    """An email that never mentions the symbol must not widen the window with its mtime."""

    unrelated = artifact(
        "ART-UNRELATED",
        artifact_type="EMAIL_LOG",
        relative_path="email-log.txt",
        reliability_class=ArtifactReliabilityClass.EXTERNAL_CORROBORATION,
        modified_time_if_known=datetime(2026, 7, 18, 15, 41, 40, tzinfo=UTC),
        bounds_detection_event=False,
    )
    evidence = build_detection_time_evidence(
        "BIYA", (biya_log_artifact(), biya_meeting_artifact(), unrelated)
    )
    assert evidence.window_end == BIYA_WINDOW_END
    assert "ART-UNRELATED" not in evidence.source_artifact_ids


def test_identity_is_deterministic_and_input_order_invariant():
    forward = build_detection_time_evidence("BIYA", (biya_log_artifact(), biya_meeting_artifact()))
    reverse = build_detection_time_evidence("BIYA", (biya_meeting_artifact(), biya_log_artifact()))
    assert forward.deterministic_id == reverse.deterministic_id


def test_different_windows_produce_different_identities():
    narrow = build_detection_time_evidence("BIYA", (biya_meeting_artifact(),))
    wide = build_detection_time_evidence("BIYA", (biya_log_artifact(), biya_meeting_artifact()))
    assert narrow.deterministic_id != wide.deterministic_id


def test_serialization_is_byte_stable():
    evidence = build_detection_time_evidence("BIYA", (biya_log_artifact(), biya_meeting_artifact()))
    assert serialize_detection_time(evidence) == serialize_detection_time(evidence)


def test_biya_resolves_to_the_surfacing_window_not_the_meeting_window():
    evidence = build_detection_time_evidence(
        "BIYA",
        (biya_log_artifact(), biya_meeting_artifact()),
        timezone_label="America/New_York",
    )
    assert evidence.state is DetectionTimeState.BOUNDED_TIME_WINDOW
    assert evidence.window_start == BIYA_WINDOW_START
    assert evidence.window_end == BIYA_WINDOW_END
    # The 8m43s meeting interval bounds discussion, not detection; it must not be
    # substituted for the wider surfacing window.
    assert evidence.window_start != BIYA_MEETING_START
    assert ValidationDiagnosticCode.VALIDATION_DETECTION_WINDOW_ONLY.value in _codes(evidence)


def test_bounded_window_produces_two_replay_boundaries():
    evidence = build_detection_time_evidence("BIYA", (biya_log_artifact(), biya_meeting_artifact()))
    boundaries = replay_boundaries(evidence)
    assert [label for label, _ in boundaries] == ["earliest", "latest"]
    assert [moment for _, moment in boundaries] == [BIYA_WINDOW_START, BIYA_WINDOW_END]


def test_exact_timestamp_produces_one_replay_boundary():
    stored = biya_log_artifact(artifact_id="ART-S", embedded_event_time_if_known=EVENT_TIME)
    boundaries = replay_boundaries(build_detection_time_evidence("BIYA", (stored,)))
    assert boundaries == (("exact", EVENT_TIME),)


def test_unknown_detection_time_produces_no_replay_boundary():
    evidence = build_detection_time_evidence("BIYA", (artifact("ART-NONE"),))
    assert replay_boundaries(evidence) == ()

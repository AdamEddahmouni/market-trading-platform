from squeeze_core.__main__ import main
from datetime import UTC, datetime, timedelta

from squeeze_core.acquisition.models import (
    ArtifactManifest, LeakageAuditRequest, SourceManifest,
)
from squeeze_core.acquisition.runner import curate_historical_cases
from squeeze_core.acquisition.serialization import serialize_acquisition_model
from tests.acquisition.helpers import sample_plan


def test_validate_plan_and_curate_commands_are_deterministic(tmp_path, capsys):
    plan_path = tmp_path / "plan.json"
    source_path = tmp_path / "source.json"
    artifact_path = tmp_path / "artifacts.json"
    output_a = tmp_path / "a.json"
    output_b = tmp_path / "b.json"
    plan_path.write_bytes(serialize_acquisition_model(sample_plan()))
    source_path.write_bytes(serialize_acquisition_model(
        SourceManifest(manifest_id="source-1", discovery_records=(), provider_provenance=())
    ))
    artifact_path.write_bytes(serialize_acquisition_model(
        ArtifactManifest(manifest_id="artifacts-1", artifacts=())
    ))
    assert main(["validate-acquisition-plan", "--plan", str(plan_path)]) == 0
    capsys.readouterr()
    common = [
        "curate-historical-cases", "--plan", str(plan_path),
        "--source-manifest", str(source_path), "--artifact-manifest", str(artifact_path),
    ]
    assert main([*common, "--output", str(output_a)]) == 0
    capsys.readouterr()
    assert main([*common, "--output", str(output_b)]) == 0
    capsys.readouterr()
    assert output_a.read_bytes() == output_b.read_bytes()


def test_draft_plan_cannot_curate_and_failure_is_structured(tmp_path, capsys):
    plan = sample_plan(plan_status="DRAFT")
    plan_path = tmp_path / "plan.json"
    source_path = tmp_path / "source.json"
    artifact_path = tmp_path / "artifacts.json"
    plan_path.write_bytes(serialize_acquisition_model(plan))
    source_path.write_bytes(serialize_acquisition_model(
        SourceManifest(manifest_id="source-1", discovery_records=(), provider_provenance=())
    ))
    artifact_path.write_bytes(serialize_acquisition_model(
        ArtifactManifest(manifest_id="artifacts-1", artifacts=())
    ))
    result = main([
        "curate-historical-cases", "--plan", str(plan_path),
        "--source-manifest", str(source_path), "--artifact-manifest", str(artifact_path),
        "--output", str(tmp_path / "output.json"),
    ])
    error = capsys.readouterr().err
    assert result == 1
    assert '"valid":false' in error
    assert "ACQUISITION_PLAN_NOT_PREREGISTERED" in error


def test_render_report_command_requires_explicit_batch(tmp_path, capsys):
    result = main([
        "render-acquisition-report", "--batch", str(tmp_path / "missing.json"),
        "--format", "markdown", "--output", str(tmp_path / "report.md"),
    ])
    assert result == 1
    assert '"valid":false' in capsys.readouterr().err


def test_failed_leakage_audit_writes_result_and_returns_nonzero(tmp_path, capsys):
    start = datetime(2024, 5, 14, 12, 0, tzinfo=UTC)
    batch = curate_historical_cases(
        sample_plan(), SourceManifest(manifest_id="source", discovery_records=(),
                                      provider_provenance=()),
        ArtifactManifest(manifest_id="artifacts", artifacts=()),
    )
    request = LeakageAuditRequest(
        case_attempt_id="attempt-1", discovery_input_fields=("outcome_label",),
        eligibility_input_fields=(), boundary_input_fields=(), evaluation_input_fields=(),
        plan_frozen_at=start, boundary_frozen_at=start + timedelta(minutes=1),
        evaluation_request_frozen_at=start + timedelta(minutes=2),
        evaluation_result_frozen_at=start + timedelta(minutes=3),
        outcome_captured_at=start + timedelta(minutes=4),
        discovery_manifest_id="discovery", outcome_manifest_id="outcome",
        plan_changed_after_outcome_access=False,
        outcome_aware_selection_indicator=False,
        maximum_return_selection_indicator=False,
        post_event_article_used_as_discovery_source=False,
    )
    batch = batch.model_copy(update={"leakage_audit_requests": (request,)})
    batch_path = tmp_path / "batch.json"
    output = tmp_path / "audit.json"
    batch_path.write_bytes(serialize_acquisition_model(batch))
    result = main([
        "audit-outcome-leakage", "--batch", str(batch_path), "--output", str(output)
    ])
    capsys.readouterr()
    assert result == 1
    assert b'"publication_blocked":true' in output.read_bytes()

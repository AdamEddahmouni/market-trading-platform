import hashlib
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from squeeze_core.research.models import CandidateCaseRegistry
from squeeze_core.research.serialization import deserialize_research_dataset
from squeeze_core.serialization import canonical_json_bytes

from .boundary_freeze import freeze_detection_boundary
from .eligibility import decide_eligibility
from .identity_resolution import resolve_identity
from .leakage_guards import audit_outcome_leakage
from .migration import migrate_phase3b_registry
from .models import (
    AcquisitionPlanStatus, ArtifactClassification, ArtifactManifest, ArtifactRecord,
    BoundaryEvidence, BoundaryRule, CuratedCaseBundle, CurationStatus, DiscoveryRecord,
    DiscoverySourceClass, EligibilityContext, HistoricalOrCurrent, IdentityClaim,
    LeakageAuditCollection, LeakageAuditRequest, ProviderProvenance, SourceManifest,
)
from .plans import build_pilot_acquisition_plan
from .policies import load_policy
from .publication import build_phase3b_dataset_candidate, build_phase3b_registry_candidate
from .reports import render_acquisition_report
from .runner import curate_historical_cases


def _json(value) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _anchor(name: str, value: str) -> str:
    return hashlib.sha256(f"{name}\0{value}".encode("utf-8")).hexdigest()


def _pilot_inputs():
    observed = datetime(2024, 5, 14, 12, 0, tzinfo=UTC)
    sanitized_content = b'{"source":"phase-3d-pilot","symbol":"PILT"}\n'
    provenance = ProviderProvenance(
        provider_provenance_id="phase-3d-pilot-provider",
        provider_name="Public Pilot Feed", provider_product="Historical Export",
        provider_dataset="US Equity Events", provider_scope="US_EQUITY",
        access_method="SANITIZED_LOCAL_EXPORT", artifact_timestamp=observed + timedelta(minutes=5),
        event_at=observed, observed_at=observed + timedelta(minutes=1),
        effective_at=observed, published_at=observed + timedelta(minutes=2),
        received_at=observed + timedelta(minutes=3), timezone="UTC", latency_status="KNOWN",
        historical_or_current=HistoricalOrCurrent.HISTORICAL, revision_status="ORIGINAL",
        terms_or_license_reference="public pilot fixture", source_artifact_id="pilot-discovery",
    )
    discovery = DiscoveryRecord(
        discovery_record_id="PILT_20240514_DISCOVERY", symbol_as_observed="PILT",
        observed_at=observed, source_class=DiscoverySourceClass.PUBLIC_MARKET_EVENT_FEED,
        source_name="phase-3d-pilot-feed", source_artifact_id="pilot-discovery",
        provider="Public Pilot Feed", provider_scope="US_EQUITY",
        query_or_filter_definition="fixed-filter-v1", original_order=1,
        platform_surfaced_status="UNKNOWN", discovery_reason="source-defined pilot event",
        fixture_classification=ArtifactClassification.SANITIZED_HISTORICAL_FIXTURE,
    )
    artifact = ArtifactRecord(
        artifact_id="pilot-discovery", file_name="sanitized_discovery.json",
        relative_path="raw/sanitized_discovery.json", media_type="application/json",
        byte_length=len(sanitized_content), sha256=hashlib.sha256(sanitized_content).hexdigest(),
        source_class=DiscoverySourceClass.PUBLIC_MARKET_EVENT_FEED,
        provider_provenance_id=provenance.provider_provenance_id,
        fixture_classification=ArtifactClassification.SANITIZED_HISTORICAL_FIXTURE,
        capture_method="SANITIZED_LOCAL_EXPORT", observed_at=observed,
        effective_at=observed, published_at=observed + timedelta(minutes=2),
        content_status="CAPTURED", sensitive_content_status="SANITIZED",
    )
    return (
        SourceManifest(manifest_id="phase-3d-pilot-source", discovery_records=(discovery,),
                       provider_provenance=(provenance,)),
        ArtifactManifest(manifest_id="phase-3d-pilot-artifacts", artifacts=(artifact,)),
    )


def _audit_request(*, failed: bool) -> LeakageAuditRequest:
    start = datetime(2024, 5, 14, 12, 0, tzinfo=UTC)
    return LeakageAuditRequest(
        case_attempt_id="PILT_20240514_DISCOVERY",
        discovery_input_fields=("outcome_label",) if failed else ("symbol", "observed_at"),
        eligibility_input_fields=("identity", "artifacts"),
        boundary_input_fields=("discovery_timestamp",),
        evaluation_input_fields=("market_bars",), plan_frozen_at=start,
        boundary_frozen_at=start + timedelta(minutes=1),
        evaluation_request_frozen_at=start + timedelta(minutes=2),
        evaluation_result_frozen_at=start + timedelta(minutes=3),
        outcome_captured_at=start + timedelta(minutes=4),
        discovery_manifest_id="phase-3d-pilot-source",
        outcome_manifest_id="phase-3d-pilot-outcome",
        plan_changed_after_outcome_access=False,
        outcome_aware_selection_indicator=False,
        maximum_return_selection_indicator=False,
        post_event_article_used_as_discovery_source=False,
    )


def build_phase3d_fixture_documents(research_fixture_dir: Path) -> dict[str, bytes]:
    plan = build_pilot_acquisition_plan()
    source_manifest, artifact_manifest = _pilot_inputs()
    batch = curate_historical_cases(plan, source_manifest, artifact_manifest)
    pass_audit = audit_outcome_leakage(_audit_request(failed=False))
    fail_audit = audit_outcome_leakage(_audit_request(failed=True))
    audit_collection = LeakageAuditCollection(
        batch_id=batch.batch_id, audits=(pass_audit, fail_audit)
    )

    registry = CandidateCaseRegistry.model_validate_json(
        (research_fixture_dir / "phase_3b_case_registry.json").read_text(encoding="utf-8")
    )
    dataset = deserialize_research_dataset(
        (research_fixture_dir / "phase_3b_research_dataset.json").read_bytes()
    )
    migrated = migrate_phase3b_registry(
        registry, acquisition_plan_id="phase-3d-existing-evidence-migration"
    )
    migrated_by_id = {item.case_attempt_id: item for item in migrated}
    registry_by_id = {item.case_id: item for item in registry.entries}
    rows_by_id = {item.case_id: item for item in dataset.rows}
    biya = tuple(item for item in migrated if item.symbol == "BIYA")
    incomplete = tuple(item for item in migrated if item.symbol != "BIYA")
    registry_candidates = tuple(
        build_phase3b_registry_candidate(item, registry_by_id[item.case_attempt_id])
        for item in migrated
    )
    dataset_candidates = tuple(
        build_phase3b_dataset_candidate(
            migrated_by_id[case_id], rows_by_id[case_id]
        )
        for case_id in ("BIYA_EARLIEST_BOUNDARY", "BIYA_LATEST_BOUNDARY")
    )

    resolved = resolve_identity((IdentityClaim(
        source_artifact_id="identity-a", symbol="PILT", issuer_name="Pilot Issuer",
        exchange="NASDAQ", security_type="COMMON_STOCK", provider_identifier="pilot:1",
        effective_from=date(2024, 1, 1),
    ),))
    conflicted = resolve_identity((
        IdentityClaim(source_artifact_id="identity-a", symbol="PILT", issuer_name="Pilot Issuer",
                      exchange="NASDAQ", security_type="COMMON_STOCK",
                      provider_identifier="pilot:1"),
        IdentityClaim(source_artifact_id="identity-b", symbol="PILT", issuer_name="Pilot Issuer",
                      exchange="NYSE", security_type="COMMON_STOCK",
                      provider_identifier="pilot:1"),
    ))
    eligibility_context = EligibilityContext(
        acquisition_plan_status=AcquisitionPlanStatus.PREREGISTERED,
        within_date_range=True, within_population=True,
        discovery_provenance_available=True, artifact_validation_passed=True,
        identity_resolution=resolved, deterministic_boundary_available=True,
        objective_market_evidence_available=True, phase_3a_request_constructible=True,
        missing_domains=("SHORT_PRESSURE",), synthetic=False,
    )
    valid_eligibility = decide_eligibility(eligibility_context)
    excluded_eligibility = decide_eligibility(EligibilityContext(
        **{**eligibility_context.model_dump(mode="python"), "within_population": False}
    ))
    boundary_evidence = (BoundaryEvidence(
        timestamp=datetime(2024, 5, 14, 12, 0, tzinfo=UTC),
        source_artifact_id="pilot-discovery",
    ),)
    valid_boundary = freeze_detection_boundary(
        case_attempt_id="PILT_20240514_DISCOVERY", symbol="PILT", evidence=boundary_evidence,
        rule=BoundaryRule.FIRST_OBJECTIVE_DISCOVERY_TIMESTAMP,
    )
    rejected_boundary = freeze_detection_boundary(
        case_attempt_id="PILT_20240514_DISCOVERY", symbol="PILT", evidence=boundary_evidence,
        rule=BoundaryRule.MAXIMUM_LATER_RETURN,
    )

    batch_summary = {
        "schema_version": "1.0.0", "batch_id": batch.batch_id,
        "attempted_case_count": len(batch.ledger.attempts),
        "included_case_count": 0, "excluded_case_count": 0,
        "discovered_case_count": 1, "partial_case_count": 0, "blocked_case_count": 0,
        "complete_case_count": 0, "unique_identity_count": 1,
        "repeated_boundary_count": 0,
        "registry_ready_count": len(registry_candidates),
        "dataset_ready_count": len(dataset_candidates),
        "interpretation": "No new complete historical case is claimed by this pilot fixture.",
    }
    report = render_acquisition_report(batch)
    documents: dict[str, bytes] = {
        "phase_3d_acquisition_plan.json": _json(plan),
        "phase_3d_discovery_policy.json": _json(dict(load_policy("candidate_discovery"))),
        "phase_3d_inclusion_policy.json": _json(dict(load_policy("historical_inclusion"))),
        "phase_3d_exclusion_policy.json": _json(dict(load_policy("historical_exclusion"))),
        "phase_3d_identity_resolution_policy.json": _json(dict(load_policy("identity_resolution"))),
        "phase_3d_boundary_policy.json": _json(dict(load_policy("detection_boundary"))),
        "phase_3d_leakage_policy.json": _json(dict(load_policy("outcome_leakage"))),
        "phase_3d_deduplication_policy.json": _json(dict(load_policy("deduplication"))),
        "phase_3d_source_manifest.json": _json(source_manifest),
        "phase_3d_artifact_manifest.json": _json(artifact_manifest),
        "phase_3d_case_attempt_ledger.json": _json(batch.ledger),
        "phase_3d_biya_migrated_bundles.json": _json({"bundles": biya}),
        "phase_3d_incomplete_case_migrations.json": _json({"bundles": incomplete}),
        "phase_3d_leakage_audit.json": _json(audit_collection),
        "phase_3d_phase3b_registry_candidates.json": _json({"candidates": registry_candidates}),
        "phase_3d_phase3b_dataset_candidates.json": _json({"candidates": dataset_candidates}),
        "phase_3d_batch_summary.json": _json(batch_summary),
        "phase_3d_curation_report.md": report,
    }

    rejected_bundle = CuratedCaseBundle(
        curated_case_bundle_id="fixture-rejected", acquisition_plan_id=plan.acquisition_plan_id,
        case_attempt_id="REJECTED", symbol="REJ", curation_status=CurationStatus.REJECTED,
        fixture_classification="SYNTHETIC_EDGE_CASE", review_decision="REJECTED",
    )
    raw_anchors = {
        "acquisition_plan": str(plan.deterministic_id),
        "discovery_policy": hashlib.sha256(documents["phase_3d_discovery_policy.json"]).hexdigest(),
        "inclusion_policy": hashlib.sha256(documents["phase_3d_inclusion_policy.json"]).hexdigest(),
        "exclusion_policy": hashlib.sha256(documents["phase_3d_exclusion_policy.json"]).hexdigest(),
        "identity_resolution_policy": hashlib.sha256(documents["phase_3d_identity_resolution_policy.json"]).hexdigest(),
        "boundary_policy": hashlib.sha256(documents["phase_3d_boundary_policy.json"]).hexdigest(),
        "leakage_policy": hashlib.sha256(documents["phase_3d_leakage_policy.json"]).hexdigest(),
        "deduplication_policy": hashlib.sha256(documents["phase_3d_deduplication_policy.json"]).hexdigest(),
        "source_manifest": str(source_manifest.deterministic_id),
        "artifact_manifest": str(artifact_manifest.deterministic_id),
        "case_attempt_ledger": str(batch.ledger.deterministic_id),
        "biya_earliest_migration": str(migrated_by_id["BIYA_EARLIEST_BOUNDARY"].deterministic_id),
        "biya_latest_migration": str(migrated_by_id["BIYA_LATEST_BOUNDARY"].deterministic_id),
        "biya_duplicate_group": migrated_by_id["BIYA_LATEST_BOUNDARY"].dependent_on_bundle_id or "",
        "klrs_migration": str(migrated_by_id["KLRS_ARTIFACT_DISCOVERY"].deterministic_id),
        "lbgj_migration": str(migrated_by_id["LBGJ_ARTIFACT_DISCOVERY"].deterministic_id),
        "sg_migration": str(migrated_by_id["SG_ARTIFACT_DISCOVERY"].deterministic_id),
        "trvi_migration": str(migrated_by_id["TRVI_ARTIFACT_DISCOVERY"].deterministic_id),
        "sls_migration": str(migrated_by_id["SLS_ARTIFACT_DISCOVERY"].deterministic_id),
        "klos_conflict_migration": str(migrated_by_id["KLOS_IDENTITY_CONFLICT"].deterministic_id),
        "valid_identity_resolution": str(resolved.deterministic_id),
        "conflicted_identity_resolution": str(conflicted.deterministic_id),
        "valid_boundary_freeze": str(valid_boundary.deterministic_id),
        "outcome_aware_boundary_rejection": str(rejected_boundary.deterministic_id),
        "valid_eligibility_decision": str(valid_eligibility.deterministic_id),
        "excluded_eligibility_decision": str(excluded_eligibility.deterministic_id),
        "valid_leakage_audit": str(pass_audit.deterministic_id),
        "failed_leakage_audit": str(fail_audit.deterministic_id),
        "complete_curated_bundle": str(migrated_by_id["BIYA_EARLIEST_BOUNDARY"].deterministic_id),
        "partial_curated_bundle": str(migrated_by_id["KLRS_ARTIFACT_DISCOVERY"].deterministic_id),
        "blocked_curated_bundle": str(migrated_by_id["KLOS_IDENTITY_CONFLICT"].deterministic_id),
        "rejected_curated_bundle": str(rejected_bundle.deterministic_id),
        "phase3b_registry_candidate": str(registry_candidates[0].deterministic_id),
        "phase3b_dataset_candidate": dataset_candidates[0].row_id,
        "registry_only_candidate": str(registry_by_id["KLRS_ARTIFACT_DISCOVERY"].deterministic_id),
        "batch_summary": hashlib.sha256(documents["phase_3d_batch_summary.json"]).hexdigest(),
        "curation_report": hashlib.sha256(report).hexdigest(),
        "phase_3d_cli_output": str(batch.deterministic_id),
        "phase_3d_leakage_cli_output": str(audit_collection.deterministic_id),
        "serialized_phase_3d_collection": hashlib.sha256(_json({"batch": batch, "audits": audit_collection})).hexdigest(),
    }
    anchors = {name: _anchor(name, value) for name, value in raw_anchors.items()}
    documents["expected_phase_3d_acquisition_metadata.json"] = _json({
        "schema_version": "1.0.0", "anchors": anchors,
    })
    documents["phase_3d_fixture_metadata.json"] = _json({
        "schema_version": "1.0.0",
        "file_sha256": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in sorted(documents.items())
        },
        "fixture_classifications": (
            "SANITIZED_HISTORICAL_FIXTURE", "SANITIZED_LOCAL_ARTIFACT",
            "SANITIZED_PUBLIC_HISTORICAL_DATA",
        ),
        "sensitive_content_included": False,
    })
    return dict(sorted(documents.items()))


__all__ = ["build_phase3d_fixture_documents"]

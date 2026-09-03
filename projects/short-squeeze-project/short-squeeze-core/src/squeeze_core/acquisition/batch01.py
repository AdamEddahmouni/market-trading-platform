"""Deterministic, offline curation for historical source collection batch 01.

This module turns the committed *sanitized* discovery rows (produced once by the
separate collection utility ``scripts/acquisition/import_batch01_discovery.py``
out of the read-only archived scanner export) into the full set of Phase 3D
batch artifacts. It is pure and offline: given the committed rows file it
regenerates byte-identical outputs, so the test suite never touches the archived
evidence or the network.

Batch shape (see docs/batch-01-*.md):

* Discovery source: one archived original-platform market-scanner snapshot,
  captured point in time (2026-07-18), 13 independent real US-listed symbols.
* Selection is source-order and score-blind; the platform's own score / tier /
  target predictions were dropped upstream and are never used here.
* Every attempted case is retained. Offline, no retrospective outcome window and
  no normalized Phase 3A evaluation evidence are available, so all 13 cases are
  curated as Phase 3B *registry-only* candidates (``ARTIFACT_DISCOVERY_ONLY``).
  Detection boundaries are frozen from the platform-surfaced timestamp; the
  leakage audit confirms discovery/eligibility/boundary inputs are outcome-blind.
  No complete Phase 3B dataset candidate is claimed by this batch.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from squeeze_core.research.models import (
    AssetClass, CandidateCaseRegistry, CandidateCaseRegistryEntry, CandidateCaseStatus,
    CandidateCaseType, FixtureClassification, OriginalPlatformStatus,
)
from squeeze_core.serialization import canonical_json_bytes

from .boundary_freeze import freeze_detection_boundary
from .eligibility import decide_eligibility
from .identifiers import deterministic_acquisition_id
from .identity_resolution import resolve_identity
from .leakage_guards import audit_outcome_leakage
from .models import (
    AcquisitionPlan, AcquisitionPlanStatus, ArtifactClassification, ArtifactManifest,
    ArtifactRecord, ArtifactVerificationResult, BoundaryEvidence, BoundaryRule,
    CurationStatus, DiscoveryRecord, DiscoverySourceClass, EligibilityContext,
    HistoricalOrCurrent, IdentityClaim, LeakageAuditCollection, LeakageAuditRequest,
    ProviderProvenance, SourceManifest,
)
from .reports import render_acquisition_report
from .runner import curate_historical_cases
from .sufficiency import review_evidence_sufficiency


PLAN_ID = "phase-3d-historical-source-batch-01"
PLAN_VERSION = "phase_3d_historical_source_batch_01.v1"
REGISTRY_VERSION = "phase_3d_batch_01_registry.v1"
PHASE_3A_POLICY_VERSION = "phase_3a_transparent_candidate_policy.v1"
RAW_ARTIFACT_ID = "batch01-screener-snapshot-raw"
NORMALIZED_ARTIFACT_ID = "batch01-sanitized-discovery-rows"
PROVIDER_PROVENANCE_ID = "batch01-archived-screener-provenance"
DISCOVERY_MANIFEST_ID = "phase-3d-batch-01-source"
OUTCOME_MANIFEST_ID = "phase-3d-batch-01-outcome-not-captured"

# Fixed curation instants -- deterministic, never wall-clock. The scan itself is
# the real discovery time; these are the frozen preregistration/curation stamps.
_PLAN_FROZEN_AT = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
_BOUNDARY_FROZEN_AT = _PLAN_FROZEN_AT + timedelta(minutes=1)
_EVALUATION_REQUEST_FROZEN_AT = _PLAN_FROZEN_AT + timedelta(minutes=2)
_EVALUATION_RESULT_FROZEN_AT = _PLAN_FROZEN_AT + timedelta(minutes=3)
# Sentinel strictly after every freeze stage: no outcome was captured, so this
# only exists to satisfy the audit's freeze-ordering invariant.
_OUTCOME_SENTINEL_AT = _PLAN_FROZEN_AT + timedelta(minutes=4)


def build_batch01_acquisition_plan() -> AcquisitionPlan:
    """The preregistered, outcome-blinded batch 01 acquisition plan."""
    return AcquisitionPlan(
        acquisition_plan_id=PLAN_ID,
        plan_version=PLAN_VERSION,
        created_from_policy_version="phase_3d_acquisition_plan_policy.v1",
        research_question=(
            "Can independent real symbols surfaced by an archived point-in-time market "
            "scanner be curated point in time through the Phase 3D pipeline while "
            "preserving provenance and outcome-blindness?"
        ),
        target_population=(
            "US-listed equities surfaced by the archived original-platform market scanner "
            "on the frozen scan date"
        ),
        date_range=(date(2026, 7, 18), date(2026, 7, 18)),
        market_session_scope=("REGULAR",),
        symbol_universe_definition=(
            "Distinct US-listed equity tickers present in the frozen archived scanner "
            "snapshot screener_snapshot.json captured 2026-07-18T13:37:55Z"
        ),
        discovery_source_definitions=(
            "ARCHIVED_MARKET_SCANNER:screener_snapshot@2026-07-18T13:37:55Z",
        ),
        maximum_case_count=30,
        minimum_case_count=0,
        sampling_method="SOURCE_ORDER_THEN_UNIQUE_SECURITY_IDENTITY_SCORE_BLIND",
        deduplication_policy="phase_3d_unique_security_deduplication_policy.v1",
        boundary_policy="phase_3d_detection_boundary_policy.v1",
        inclusion_policy_version="phase_3d_historical_inclusion_policy.v1",
        exclusion_policy_version="phase_3d_historical_exclusion_policy.v1",
        provider_priority_policy_version="phase_3d_provider_priority_policy.v1",
        artifact_requirements=("DISCOVERY", "IDENTITY", "MARKET"),
        allowed_substitutions=(),
        forbidden_substitutions=("CURRENT_FOR_HISTORICAL", "SYNTHETIC_FOR_HISTORICAL"),
        outcome_blinding_state="OUTCOME_BLINDED",
        plan_status=AcquisitionPlanStatus.PREREGISTERED,
        informational_created_at=_PLAN_FROZEN_AT,
    )


def _load_rows(rows_path: Path) -> tuple[dict, bytes]:
    rows_bytes = rows_path.read_bytes()
    document = json.loads(rows_bytes)
    return document, rows_bytes


def _parse_observed_at(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


def _provider_provenance(document: dict) -> ProviderProvenance:
    capture = _parse_observed_at(document["raw_source"]["capture_timestamp"])
    return ProviderProvenance(
        provider_provenance_id=PROVIDER_PROVENANCE_ID,
        provider_name="Archived original-platform squeeze scanner",
        provider_product="Live screener snapshot (archived)",
        provider_dataset="screener_snapshot.json",
        provider_scope="US_EQUITY",
        access_method="LOCAL_ARCHIVED_FILE_REFERENCE",
        artifact_timestamp=capture,
        event_at=capture,
        observed_at=capture,
        effective_at=capture,
        published_at=None,
        received_at=capture,
        timezone="UTC",
        latency_status="POINT_IN_TIME_CAPTURE",
        historical_or_current=HistoricalOrCurrent.HISTORICAL,
        revision_status="ORIGINAL",
        terms_or_license_reference=(
            "Local forensic archive; provider-derived borrow fields (IB/Schwab/yfinance) "
            "retained locally and referenced by hash, not redistributed."
        ),
        source_artifact_id=RAW_ARTIFACT_ID,
    )


def _source_manifest(document: dict) -> SourceManifest:
    provenance = _provider_provenance(document)
    records = []
    for row in document["rows"]:
        observed = _parse_observed_at(row["observed_at"])
        records.append(DiscoveryRecord(
            discovery_record_id=f"BATCH01_{row['ticker']}_20260718",
            symbol_as_observed=row["ticker"],
            observed_at=observed,
            source_class=DiscoverySourceClass.ARCHIVED_MARKET_SCANNER,
            source_name="archived-screener-snapshot-2026-07-18",
            source_artifact_id=RAW_ARTIFACT_ID,
            provider="Archived original-platform squeeze scanner",
            provider_scope="US_EQUITY",
            query_or_filter_definition=(
                "Archived scanner surface (detection-time relative-volume / percent-change / "
                "short-float criteria); imported in source order, score-blind."
            ),
            original_order=row["original_order"],
            platform_surfaced_status="SURFACED",
            discovery_reason="Symbol surfaced by the archived point-in-time market scanner",
            fixture_classification=ArtifactClassification.LOCAL_HISTORICAL_ARTIFACT,
        ))
    return SourceManifest(
        manifest_id=DISCOVERY_MANIFEST_ID,
        discovery_records=tuple(records),
        provider_provenance=(provenance,),
    )


def _artifact_manifest(document: dict, rows_bytes: bytes) -> ArtifactManifest:
    raw = document["raw_source"]
    capture = _parse_observed_at(raw["capture_timestamp"])
    raw_artifact = ArtifactRecord(
        artifact_id=RAW_ARTIFACT_ID,
        file_name=raw["artifact_name"],
        relative_path="raw/screener_snapshot.json",
        media_type="application/json",
        byte_length=raw["byte_length"],
        sha256=raw["sha256"],
        source_class=DiscoverySourceClass.ARCHIVED_MARKET_SCANNER,
        provider_provenance_id=PROVIDER_PROVENANCE_ID,
        fixture_classification=ArtifactClassification.RESTRICTED_LOCAL_ARTIFACT,
        capture_method="LOCAL_ARCHIVE_REFERENCE",
        observed_at=capture,
        effective_at=capture,
        published_at=None,
        content_status="REFERENCED_NOT_COPIED",
        sensitive_content_status="RESTRICTED_PROVIDER_DERIVED",
    )
    normalized_artifact = ArtifactRecord(
        artifact_id=NORMALIZED_ARTIFACT_ID,
        file_name="batch01_discovery_rows.json",
        relative_path="normalized/batch01_discovery_rows.json",
        media_type="application/json",
        byte_length=len(rows_bytes),
        sha256=hashlib.sha256(rows_bytes).hexdigest(),
        source_class=DiscoverySourceClass.ARCHIVED_MARKET_SCANNER,
        provider_provenance_id=PROVIDER_PROVENANCE_ID,
        fixture_classification=ArtifactClassification.DERIVED_NORMALIZED_ARTIFACT,
        capture_method="DERIVED_SANITIZED_EXPORT",
        observed_at=capture,
        effective_at=capture,
        published_at=None,
        content_status="CAPTURED",
        sensitive_content_status="SANITIZED",
    )
    return ArtifactManifest(
        manifest_id="phase-3d-batch-01-artifacts",
        artifacts=(raw_artifact, normalized_artifact),
    )


def _verify_artifacts(manifest: ArtifactManifest, rows_bytes: bytes) -> ArtifactVerificationResult:
    # Offline verification: the sanitized derived artifact is re-hashed against its
    # committed bytes; the restricted raw artifact is referenced by its recorded hash.
    diagnostics: list[str] = []
    verified: list[str] = []
    for artifact in manifest.artifacts:
        if artifact.artifact_id == NORMALIZED_ARTIFACT_ID:
            if hashlib.sha256(rows_bytes).hexdigest() == artifact.sha256:
                verified.append(artifact.artifact_id)
            else:  # pragma: no cover - defensive
                diagnostics.append("SOURCE_ARTIFACT_HASH_MISMATCH")
        else:
            verified.append(artifact.artifact_id)
            diagnostics.append("RESTRICTED_RAW_ARTIFACT_REFERENCED_BY_HASH")
    return ArtifactVerificationResult(
        manifest_id=manifest.manifest_id,
        valid=not any(code == "SOURCE_ARTIFACT_HASH_MISMATCH" for code in diagnostics),
        verified_artifact_ids=tuple(verified),
        diagnostic_codes=tuple(diagnostics),
    )


def _identity_claim(row: dict) -> IdentityClaim:
    # Only the ticker is objectively present in the scanner row; issuer / exchange /
    # security type are unknown, so identity resolves as PARTIALLY_RESOLVED.
    return IdentityClaim(
        source_artifact_id=RAW_ARTIFACT_ID,
        symbol=row["ticker"],
    )


def _eligibility_context(row: dict, identity) -> EligibilityContext:
    missing = [
        "NORMALIZED_POINT_IN_TIME_EVIDENCE",
        "RETROSPECTIVE_OUTCOME_WINDOW",
        "ISSUER_EXCHANGE_IDENTITY",
        *row.get("missing_detection_domains", ()),
    ]
    return EligibilityContext(
        acquisition_plan_status=AcquisitionPlanStatus.PREREGISTERED,
        within_date_range=True,
        within_population=True,
        discovery_provenance_available=True,
        artifact_validation_passed=True,
        identity_resolution=identity,
        deterministic_boundary_available=True,
        objective_market_evidence_available=True,
        # A full Phase 3A request cannot be constructed offline from a flat scanner
        # row without fabricating the normalized point-in-time evidence layers, so we
        # decline: the case is retained as registry-only rather than fabricated.
        phase_3a_request_constructible=False,
        missing_domains=tuple(missing),
        duplicate_symbol=False,
        duplicate_discovery=False,
        synthetic=False,
    )


def _leakage_request(discovery_record_id: str) -> LeakageAuditRequest:
    return LeakageAuditRequest(
        case_attempt_id=discovery_record_id,
        discovery_input_fields=(
            "symbol", "observed_at", "price", "rel_volume", "change_percent",
            "short_float_percent", "days_to_cover", "shares_short", "float_shares",
        ),
        eligibility_input_fields=("identity", "artifacts", "discovery_provenance"),
        boundary_input_fields=("platform_surfaced_timestamp",),
        # No Phase 3A evaluation was performed for a registry-only case.
        evaluation_input_fields=(),
        plan_frozen_at=_PLAN_FROZEN_AT,
        boundary_frozen_at=_BOUNDARY_FROZEN_AT,
        evaluation_request_frozen_at=_EVALUATION_REQUEST_FROZEN_AT,
        evaluation_result_frozen_at=_EVALUATION_RESULT_FROZEN_AT,
        outcome_captured_at=_OUTCOME_SENTINEL_AT,
        discovery_manifest_id=DISCOVERY_MANIFEST_ID,
        outcome_manifest_id=OUTCOME_MANIFEST_ID,
        plan_changed_after_outcome_access=False,
        outcome_aware_selection_indicator=False,
        maximum_return_selection_indicator=False,
        post_event_article_used_as_discovery_source=False,
    )


def _registry_entry(row: dict, discovery_record_id: str) -> CandidateCaseRegistryEntry:
    limitations = [
        "REGISTRY_ONLY_NO_PHASE_3A_EVALUATION",
        "OUTCOME_WINDOW_NOT_ACQUIRED_OFFLINE",
        "IDENTITY_PARTIALLY_RESOLVED_ISSUER_EXCHANGE_UNKNOWN",
        *(f"DETECTION_DOMAIN_MISSING:{domain}" for domain in row.get("missing_detection_domains", ())),
    ]
    return CandidateCaseRegistryEntry(
        case_id=discovery_record_id,
        symbol=row["ticker"],
        asset_class=AssetClass.EQUITY,
        case_type=CandidateCaseType.ORIGINAL_PLATFORM_SURFACED,
        case_status=CandidateCaseStatus.ARTIFACT_DISCOVERY_ONLY,
        original_platform_status=OriginalPlatformStatus.SURFACED,
        detection_time_evidence_id=discovery_record_id,
        evaluation_as_of=None,
        evaluation_request_path=None,
        evaluation_result_path=None,
        outcome_observation_path=None,
        original_platform_artifact_ids=(RAW_ARTIFACT_ID,),
        historical_dataset_ids=(),
        phase_3a_policy_version=PHASE_3A_POLICY_VERSION,
        limitations=tuple(limitations),
        fixture_classification=FixtureClassification.SANITIZED_LOCAL_ARTIFACT,
    )


def _json(value) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _anchor(name: str, value: str) -> str:
    return hashlib.sha256(f"{name}\0{value}".encode("utf-8")).hexdigest()


def build_batch01_documents(rows_path: Path) -> dict[str, bytes]:
    document, rows_bytes = _load_rows(rows_path)
    plan = build_batch01_acquisition_plan()
    source_manifest = _source_manifest(document)
    artifact_manifest = _artifact_manifest(document, rows_bytes)
    verification = _verify_artifacts(artifact_manifest, rows_bytes)
    batch = curate_historical_cases(plan, source_manifest, artifact_manifest)

    rows_by_id = {
        f"BATCH01_{row['ticker']}_20260718": row for row in document["rows"]
    }

    identities = {}
    eligibilities = {}
    boundaries = {}
    sufficiencies = {}
    leakage_results = {}
    registry_entries = []
    for record in source_manifest.discovery_records:
        cid = record.discovery_record_id
        row = rows_by_id[cid]
        identity = resolve_identity((_identity_claim(row),))
        identities[cid] = identity
        eligibility = decide_eligibility(_eligibility_context(row, identity))
        eligibilities[cid] = eligibility
        boundary = freeze_detection_boundary(
            case_attempt_id=cid,
            symbol=record.symbol_as_observed,
            evidence=(BoundaryEvidence(
                timestamp=record.observed_at,
                source_artifact_id=RAW_ARTIFACT_ID,
                original_platform_surfaced=True,
            ),),
            rule=BoundaryRule.ORIGINAL_PLATFORM_SURFACED_TIMESTAMP,
        )
        boundaries[cid] = boundary
        sufficiencies[cid] = review_evidence_sufficiency(
            present_domains=("DISCOVERY", "DETECTION_TIME_MARKET_SNAPSHOT", "DETECTION_BOUNDARY"),
            missing_domains=tuple(eligibility.context.missing_domains),
            phase_3a_request_constructible=False,
            outcome_only_available=False,
            identity_conflicted=False,
            publication_blocked=False,
        )
        leakage_results[cid] = audit_outcome_leakage(_leakage_request(cid))
        registry_entries.append(_registry_entry(row, cid))

    leakage_collection = LeakageAuditCollection(
        batch_id=batch.batch_id,
        audits=tuple(leakage_results.values()),
    )
    registry = CandidateCaseRegistry(
        registry_version=REGISTRY_VERSION,
        entries=tuple(registry_entries),
    )

    # Curated bundles enriched with the per-case curation results.
    enriched_bundles = []
    for bundle in batch.bundles:
        cid = bundle.case_attempt_id
        row = rows_by_id[cid]
        enriched_bundles.append(bundle.model_copy(update={
            "curation_status": CurationStatus.REVIEWED,
            "provider_provenance_ids": (PROVIDER_PROVENANCE_ID,),
            "identity_resolution_id": str(identities[cid].deterministic_id),
            "eligibility_decision_id": str(eligibilities[cid].deterministic_id),
            "detection_boundary_id": boundaries[cid].boundary_id,
            "leakage_audit_id": str(leakage_results[cid].deterministic_id),
            "leakage_audit_passed": leakage_results[cid].passed,
            "outcome_capture_status": "NOT_CAPTURED",
            "review_decision": "APPROVED_WITH_LIMITATIONS",
            "diagnostics": ("REGISTRY_ONLY_CANDIDATE",),
            "limitations": (
                "REGISTRY_ONLY_NO_PHASE_3A_EVALUATION",
                "OUTCOME_WINDOW_NOT_ACQUIRED_OFFLINE",
            ),
        }))
    enriched_bundles.sort(key=lambda item: item.case_attempt_id)

    boundary_manifest = {
        "schema_version": "1.0.0",
        "boundary_rule": BoundaryRule.ORIGINAL_PLATFORM_SURFACED_TIMESTAMP.value,
        "boundaries": tuple(boundaries[cid] for cid in sorted(boundaries)),
    }
    evaluation_manifest = {
        "schema_version": "1.0.0",
        "phase_3a_policy_version": PHASE_3A_POLICY_VERSION,
        "phase_3a_requests_frozen": 0,
        "phase_3a_results_frozen": 0,
        "note": (
            "No Phase 3A request or result was constructed: normalized point-in-time "
            "evaluation evidence is unavailable offline and would require fabrication. "
            "Cases are retained as registry-only."
        ),
        "entries": (),
    }
    outcome_manifest = {
        "schema_version": "1.0.0",
        "outcome_manifest_id": OUTCOME_MANIFEST_ID,
        "outcome_label_policy_version": "phase_3b_outcome_label_policy.v1",
        "horizon": "24_HOURS",
        "upward_threshold_percent": 25,
        "downward_threshold_percent": -25,
        "captured": False,
        "note": (
            "Retrospective outcome window not acquired in this offline batch; the outcome "
            "manifest is intentionally empty and kept separate from discovery/eligibility/"
            "boundary inputs."
        ),
        "observations": (),
    }
    identity_review = {
        "schema_version": "1.0.0",
        "resolutions": tuple(identities[cid] for cid in sorted(identities)),
    }
    eligibility_review = {
        "schema_version": "1.0.0",
        "decisions": tuple(eligibilities[cid] for cid in sorted(eligibilities)),
    }
    sufficiency_review = {
        "schema_version": "1.0.0",
        "reviews": tuple(sufficiencies[cid] for cid in sorted(sufficiencies)),
    }

    empty_case_set = {"schema_version": "1.0.0", "cases": ()}
    registry_only_cases = {
        "schema_version": "1.0.0",
        "case_ids": tuple(sorted(rows_by_id)),
    }

    batch_summary = {
        "schema_version": "1.0.0",
        "batch_id": batch.batch_id,
        "acquisition_plan_id": PLAN_ID,
        "acquisition_plan_version": PLAN_VERSION,
        "discovery_source_class": DiscoverySourceClass.ARCHIVED_MARKET_SCANNER.value,
        "attempted_case_count": len(batch.ledger.attempts),
        "unique_identity_count": len(rows_by_id),
        "duplicate_discovery_count": 0,
        "included_case_count": 0,
        "registry_only_case_count": len(rows_by_id),
        "complete_dataset_candidate_count": 0,
        "excluded_case_count": 0,
        "partial_case_count": 0,
        "blocked_case_count": 0,
        "dependent_secondary_boundary_count": 0,
        "boundaries_frozen_count": len(boundaries),
        "phase_3a_requests_frozen_count": 0,
        "phase_3a_results_frozen_count": 0,
        "outcome_windows_captured_count": 0,
        "leakage_passed_count": sum(1 for r in leakage_results.values() if r.passed),
        "leakage_failed_count": sum(1 for r in leakage_results.values() if not r.passed),
        "phase_3b_registry_candidate_count": len(registry_entries),
        "phase_3b_dataset_candidate_count": 0,
        "outcome_blinding_state": plan.outcome_blinding_state,
        "interpretation": (
            "Batch 01 curates 13 independent real symbols from an archived point-in-time "
            "scanner snapshot as outcome-blind, registry-only Phase 3B candidates. No "
            "predictive validity, score, ranking, or complete dataset candidate is claimed."
        ),
    }

    report = render_acquisition_report(batch)

    documents: dict[str, bytes] = {
        "acquisition-plan.json": _json(plan),
        "source-manifest.json": _json(source_manifest),
        "artifact-manifest.json": _json(artifact_manifest),
        "artifact-verification.json": _json(verification),
        "case-attempt-ledger.json": _json(batch.ledger),
        "identity-review.json": _json(identity_review),
        "eligibility-review.json": _json(eligibility_review),
        "sufficiency-review.json": _json(sufficiency_review),
        "boundary-freeze-manifest.json": _json(boundary_manifest),
        "evaluation-freeze-manifest.json": _json(evaluation_manifest),
        "outcome-manifest.json": _json(outcome_manifest),
        "leakage-audit.json": _json(leakage_collection),
        "curated-case-bundles.jsonl": b"".join(
            canonical_json_bytes(bundle) + b"\n" for bundle in enriched_bundles
        ),
        "phase3b-registry-candidates.json": _json(registry),
        "phase3b-dataset-candidates.json": _json({"schema_version": "1.0.0", "candidates": ()}),
        "registry-only-cases.json": _json(registry_only_cases),
        "excluded-cases.json": _json(empty_case_set),
        "partial-cases.json": _json(empty_case_set),
        "blocked-cases.json": _json(empty_case_set),
        "dependent-secondary-boundaries.json": _json(empty_case_set),
        "failed-leakage-cases.json": _json(empty_case_set),
        "batch-summary.json": _json(batch_summary),
        "curation-report.md": report,
    }

    raw_anchors = {
        "acquisition_plan": str(plan.deterministic_id),
        "source_manifest": str(source_manifest.deterministic_id),
        "artifact_manifest": str(artifact_manifest.deterministic_id),
        "artifact_verification": str(verification.deterministic_id),
        "case_attempt_ledger": str(batch.ledger.deterministic_id),
        "acquisition_batch": str(batch.deterministic_id),
        "leakage_audit_collection": str(leakage_collection.deterministic_id),
        "phase3b_registry": str(registry.deterministic_id),
        "raw_artifact_sha256": document["raw_source"]["sha256"],
        "normalized_artifact_sha256": hashlib.sha256(rows_bytes).hexdigest(),
        "batch_summary": hashlib.sha256(documents["batch-summary.json"]).hexdigest(),
        "curation_report": hashlib.sha256(report).hexdigest(),
        "curated_case_bundles": hashlib.sha256(documents["curated-case-bundles.jsonl"]).hexdigest(),
    }
    for cid in sorted(rows_by_id):
        raw_anchors[f"identity::{cid}"] = str(identities[cid].deterministic_id)
        raw_anchors[f"eligibility::{cid}"] = str(eligibilities[cid].deterministic_id)
        raw_anchors[f"boundary::{cid}"] = boundaries[cid].boundary_id
        raw_anchors[f"leakage::{cid}"] = str(leakage_results[cid].deterministic_id)
        raw_anchors[f"registry_entry::{cid}"] = str(
            next(e for e in registry_entries if e.case_id == cid).deterministic_id
        )

    anchors = {name: _anchor(name, value) for name, value in raw_anchors.items()}
    documents["expected-batch-01-anchors.json"] = _json({
        "schema_version": "1.0.0",
        "anchors": anchors,
    })
    documents["batch-01-fixture-metadata.json"] = _json({
        "schema_version": "1.0.0",
        "file_sha256": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in sorted(documents.items())
        },
        "fixture_classifications": (
            "DERIVED_NORMALIZED_ARTIFACT",
            "LOCAL_HISTORICAL_ARTIFACT",
            "RESTRICTED_LOCAL_ARTIFACT",
        ),
        "sensitive_content_included": False,
        "raw_artifact_copied_into_repository": False,
    })
    return dict(sorted(documents.items()))


__all__ = ["build_batch01_acquisition_plan", "build_batch01_documents"]

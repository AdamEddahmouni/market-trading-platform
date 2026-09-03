from .identifiers import deterministic_acquisition_id
from .leakage_guards import audit_outcome_leakage
from .models import (
    AcquisitionBatch, AcquisitionLedger, AcquisitionPlan, AcquisitionPlanStatus,
    ArtifactManifest, CaseAttempt, CuratedCaseBundle, CurationStatus, ExclusionCode,
    LeakageAuditCollection, SourceManifest,
)


def curate_historical_cases(
    plan: AcquisitionPlan, source_manifest: SourceManifest,
    artifact_manifest: ArtifactManifest,
) -> AcquisitionBatch:
    if plan.plan_status not in {AcquisitionPlanStatus.PREREGISTERED, AcquisitionPlanStatus.ACTIVE}:
        raise ValueError("ACQUISITION_PLAN_NOT_PREREGISTERED")
    seen_symbols: set[str] = set()
    attempts = []
    bundles = []
    for discovery in source_manifest.discovery_records:
        duplicate = discovery.symbol_as_observed in seen_symbols
        seen_symbols.add(discovery.symbol_as_observed)
        exclusions = (ExclusionCode.DUPLICATE_SYMBOL,) if duplicate else ()
        attempt = CaseAttempt(
            case_attempt_id=discovery.discovery_record_id,
            acquisition_plan_id=plan.acquisition_plan_id,
            symbol=discovery.symbol_as_observed,
            exclusion_codes=exclusions,
            limitations=("source artifacts require evidence-availability review",),
        )
        attempts.append(attempt)
        bundle_id = deterministic_acquisition_id({
            "result_type": "CURATED_CASE_BUNDLE",
            "acquisition_plan_id": plan.acquisition_plan_id,
            "case_attempt_id": attempt.case_attempt_id,
        })
        bundles.append(CuratedCaseBundle(
            curated_case_bundle_id=bundle_id,
            acquisition_plan_id=plan.acquisition_plan_id,
            case_attempt_id=attempt.case_attempt_id,
            symbol=attempt.symbol,
            curation_status=CurationStatus.EXCLUDED if duplicate else CurationStatus.DISCOVERED,
            fixture_classification=discovery.fixture_classification.value,
            discovery_record_id=discovery.discovery_record_id,
            source_artifact_ids=(discovery.source_artifact_id,),
            review_decision="PENDING_EVIDENCE_REVIEW",
            diagnostics=tuple(code.value for code in exclusions),
            limitations=attempt.limitations,
        ))
    ledger = AcquisitionLedger(
        ledger_id=deterministic_acquisition_id({
            "result_type": "ACQUISITION_LEDGER", "plan_id": plan.acquisition_plan_id
        }),
        attempts=tuple(attempts),
    )
    return AcquisitionBatch(
        batch_id=deterministic_acquisition_id({
            "result_type": "ACQUISITION_BATCH", "plan_id": plan.acquisition_plan_id,
            "source_manifest_id": source_manifest.manifest_id,
            "artifact_manifest_id": artifact_manifest.manifest_id,
        }),
        acquisition_plan=plan,
        source_manifest=source_manifest,
        artifact_manifest=artifact_manifest,
        ledger=ledger,
        bundles=tuple(bundles),
    )


def audit_batch_outcome_leakage(batch: AcquisitionBatch) -> LeakageAuditCollection:
    return LeakageAuditCollection(
        batch_id=batch.batch_id,
        audits=tuple(audit_outcome_leakage(item) for item in batch.leakage_audit_requests),
    )


__all__ = ["audit_batch_outcome_leakage", "curate_historical_cases"]

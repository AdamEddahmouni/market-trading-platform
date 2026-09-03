from squeeze_core.research.models import CandidateCaseRegistry

from .identifiers import deterministic_acquisition_id
from .models import CuratedCaseBundle, CurationStatus


_MIGRATED_HISTORICAL_CASES = {
    "BIYA_EARLIEST_BOUNDARY", "BIYA_LATEST_BOUNDARY", "KLRS_ARTIFACT_DISCOVERY",
    "LBGJ_ARTIFACT_DISCOVERY", "SG_ARTIFACT_DISCOVERY", "TRVI_ARTIFACT_DISCOVERY",
    "SLS_ARTIFACT_DISCOVERY", "KLOS_IDENTITY_CONFLICT",
}


def _bundle_id(plan_id: str, case_id: str) -> str:
    return deterministic_acquisition_id({
        "result_type": "MIGRATED_CURATED_CASE_BUNDLE",
        "acquisition_plan_id": plan_id,
        "case_attempt_id": case_id,
    })


def migrate_phase3b_registry(
    registry: CandidateCaseRegistry, *, acquisition_plan_id: str,
) -> tuple[CuratedCaseBundle, ...]:
    earliest_bundle_id = _bundle_id(acquisition_plan_id, "BIYA_EARLIEST_BOUNDARY")
    bundles = []
    for entry in registry.entries:
        if entry.case_id not in _MIGRATED_HISTORICAL_CASES:
            continue
        if entry.case_id.startswith("BIYA_"):
            status = CurationStatus.PUBLISHED
        elif entry.case_id == "KLOS_IDENTITY_CONFLICT":
            status = CurationStatus.BLOCKED
        else:
            status = CurationStatus.PARTIAL
        bundles.append(CuratedCaseBundle(
            curated_case_bundle_id=_bundle_id(acquisition_plan_id, entry.case_id),
            acquisition_plan_id=acquisition_plan_id,
            case_attempt_id=entry.case_id,
            symbol=entry.symbol,
            curation_status=status,
            fixture_classification=entry.fixture_classification.value,
            discovery_record_id=entry.detection_time_evidence_id,
            source_artifact_ids=entry.original_platform_artifact_ids,
            phase_3a_result_id=entry.deterministic_id if entry.evaluation_result_path else None,
            outcome_capture_status="CAPTURED" if entry.outcome_observation_path else "NOT_CAPTURED",
            review_decision="MIGRATED_WITHOUT_REINTERPRETATION",
            leakage_audit_passed=True if status is CurationStatus.PUBLISHED else None,
            limitations=entry.limitations,
            dependent_on_bundle_id=(
                earliest_bundle_id if entry.case_id == "BIYA_LATEST_BOUNDARY" else None
            ),
        ))
    return tuple(sorted(bundles, key=lambda item: item.case_attempt_id))


__all__ = ["migrate_phase3b_registry"]

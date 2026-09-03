from squeeze_core.research.models import CandidateCaseRegistryEntry, ResearchDatasetRow

from .models import CuratedCaseBundle, CurationStatus


def build_phase3b_registry_candidate(
    bundle: CuratedCaseBundle, source_entry: CandidateCaseRegistryEntry,
) -> CandidateCaseRegistryEntry:
    if bundle.case_attempt_id != source_entry.case_id or bundle.symbol != source_entry.symbol:
        raise ValueError("Phase 3B registry source does not match curated bundle")
    return source_entry


def build_phase3b_dataset_candidate(
    bundle: CuratedCaseBundle, source_row: ResearchDatasetRow,
) -> ResearchDatasetRow:
    if "SYNTHETIC" in bundle.fixture_classification:
        raise ValueError("synthetic bundles cannot become empirical dataset candidates")
    if bundle.curation_status is not CurationStatus.PUBLISHED or bundle.leakage_audit_passed is not True:
        raise ValueError("dataset publication requires a complete leakage-passing bundle")
    if bundle.case_attempt_id != source_row.case_id or bundle.symbol != source_row.symbol:
        raise ValueError("Phase 3B dataset source does not match curated bundle")
    return source_row


__all__ = ["build_phase3b_dataset_candidate", "build_phase3b_registry_candidate"]

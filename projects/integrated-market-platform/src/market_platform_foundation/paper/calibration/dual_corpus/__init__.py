"""Dual-corpus evidence authority: historical development vs prospective Item 9."""

from .admission import (
    ITEM9_ADMISSION_REFUSED,
    evaluate_item9_prospective_corpus_admission,
)
from .consumption import (
    CONSUMPTION_REFUSED_PROTECTED_CORPUS,
    TRAINING_OR_SELECTION_USE_REFUSED,
    assert_corpus_consumable_for_selection_or_training,
    assert_metadata_consumable_for_selection_or_training,
    assert_payload_samples_consumable_for_selection_or_training,
    is_protected_corpus_authority,
    protected_corpus_authorities_for_selection_training,
)
from .discovery import (
    iter_item9_prospective_receipt_paths,
    validate_item9_prospective_receipt_output_dir,
)
from .evidence_authority import (
    CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT,
    CORPUS_EVIDENCE_AUTHORITY_POST_HORIZON_HISTORICAL_LABEL_EVIDENCE,
    CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE,
    CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION,
    resolve_effective_corpus_evidence_authority,
)
from .historical_manifest import (
    HISTORICAL_DATASET_MANIFEST_KIND,
    HISTORICAL_DATASET_SCHEMA_VERSION,
    build_historical_development_dataset_manifest,
    validate_historical_development_dataset_manifest,
)
from .historical_provenance import (
    HISTORICAL_DEVELOPMENT_PROVENANCE_KIND,
    HISTORICAL_PROVENANCE_SCHEMA_VERSION,
    build_historical_development_provenance,
    validate_historical_development_provenance,
)
from .contamination_auditor import (
    CONTAMINATION_STATUS_FAIL,
    CONTAMINATION_STATUS_PASS,
    audit_research_contamination_run,
    build_evidence_language_summary,
)
from .leak_audit import (
    VIOLATION_MISSING_LINEAGE,
    VIOLATION_TRAIN_TEST_OVERLAP,
)
from .normalization import normalize_historical_development_bars
from .run_manifest import (
    RESEARCH_CONTAMINATION_RUN_MANIFEST_KIND,
    RESEARCH_CONTAMINATION_RUN_SCHEMA_VERSION,
    validate_research_contamination_run_manifest,
)

__all__ = [
    "CONTAMINATION_STATUS_FAIL",
    "CONTAMINATION_STATUS_PASS",
    "RESEARCH_CONTAMINATION_RUN_MANIFEST_KIND",
    "RESEARCH_CONTAMINATION_RUN_SCHEMA_VERSION",
    "VIOLATION_MISSING_LINEAGE",
    "VIOLATION_TRAIN_TEST_OVERLAP",
    "audit_research_contamination_run",
    "build_evidence_language_summary",
    "validate_research_contamination_run_manifest",
    "CONSUMPTION_REFUSED_PROTECTED_CORPUS",
    "CORPUS_EVIDENCE_AUTHORITY_HISTORICAL_DEVELOPMENT",
    "CORPUS_EVIDENCE_AUTHORITY_POST_HORIZON_HISTORICAL_LABEL_EVIDENCE",
    "CORPUS_EVIDENCE_AUTHORITY_PROSPECTIVE_FEATURE_EVIDENCE",
    "CORPUS_EVIDENCE_AUTHORITY_UNTOUCHED_FORWARD_EVALUATION",
    "HISTORICAL_DATASET_MANIFEST_KIND",
    "HISTORICAL_DATASET_SCHEMA_VERSION",
    "HISTORICAL_DEVELOPMENT_PROVENANCE_KIND",
    "HISTORICAL_PROVENANCE_SCHEMA_VERSION",
    "ITEM9_ADMISSION_REFUSED",
    "TRAINING_OR_SELECTION_USE_REFUSED",
    "assert_corpus_consumable_for_selection_or_training",
    "assert_metadata_consumable_for_selection_or_training",
    "assert_payload_samples_consumable_for_selection_or_training",
    "build_historical_development_dataset_manifest",
    "build_historical_development_provenance",
    "evaluate_item9_prospective_corpus_admission",
    "is_protected_corpus_authority",
    "iter_item9_prospective_receipt_paths",
    "protected_corpus_authorities_for_selection_training",
    "normalize_historical_development_bars",
    "resolve_effective_corpus_evidence_authority",
    "validate_historical_development_dataset_manifest",
    "validate_historical_development_provenance",
    "validate_item9_prospective_receipt_output_dir",
]

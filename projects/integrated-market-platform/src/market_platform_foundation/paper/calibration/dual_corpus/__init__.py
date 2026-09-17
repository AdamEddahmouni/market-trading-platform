"""Dual-corpus evidence authority: historical development vs prospective Item 9."""

from .admission import (
    ITEM9_ADMISSION_REFUSED,
    evaluate_item9_prospective_corpus_admission,
)
from .consumption import (
    CONSUMPTION_REFUSED_PROTECTED_CORPUS,
    assert_corpus_consumable_for_selection_or_training,
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
from .normalization import normalize_historical_development_bars

__all__ = [
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
    "assert_corpus_consumable_for_selection_or_training",
    "build_historical_development_dataset_manifest",
    "build_historical_development_provenance",
    "evaluate_item9_prospective_corpus_admission",
    "iter_item9_prospective_receipt_paths",
    "normalize_historical_development_bars",
    "resolve_effective_corpus_evidence_authority",
    "validate_historical_development_dataset_manifest",
    "validate_historical_development_provenance",
    "validate_item9_prospective_receipt_output_dir",
]

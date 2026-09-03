"""Offline, deterministic local historical market-bar intake (Batch 03).

Validates user-supplied or licensed historical bar exports, normalizes supported
delimited artifacts into canonical bars with preserved provenance, and validates a
non-executing case-association mapping. Performs no acquisition, no outcome work,
no Phase 3A/3B records, and does not begin Phase 3E.
"""

from .artifact_validation import (
    describe_raw_artifact,
    inspect_artifact,
    validate_artifact_bytes,
    validate_raw_artifact,
)
from .case_association import validate_case_association
from .contract import build_intake_contract
from .csv_adapter import parse_delimited_rows
from .models import (
    ArtifactValidationReport,
    CanonicalMarketBar,
    CaseAssociationMapping,
    CaseAssociationValidationResult,
    ColumnMappingProfile,
    IntakeManifest,
    IntakeSummary,
    NormalizationDiagnostics,
    NormalizedBarSet,
    RawArtifactDescriptor,
    RowDiagnostic,
)
from .normalization import (
    NormalizationOutcome,
    normalize_bundle,
    normalize_from_bytes,
)
from .summary import (
    build_intake_summary,
    serialize_bars_csv,
    serialize_bars_jsonl,
)

__all__ = [
    "ArtifactValidationReport",
    "CanonicalMarketBar",
    "CaseAssociationMapping",
    "CaseAssociationValidationResult",
    "ColumnMappingProfile",
    "IntakeManifest",
    "IntakeSummary",
    "NormalizationDiagnostics",
    "NormalizationOutcome",
    "NormalizedBarSet",
    "RawArtifactDescriptor",
    "RowDiagnostic",
    "build_intake_contract",
    "build_intake_summary",
    "describe_raw_artifact",
    "inspect_artifact",
    "normalize_bundle",
    "normalize_from_bytes",
    "parse_delimited_rows",
    "serialize_bars_csv",
    "serialize_bars_jsonl",
    "validate_artifact_bytes",
    "validate_case_association",
    "validate_raw_artifact",
]

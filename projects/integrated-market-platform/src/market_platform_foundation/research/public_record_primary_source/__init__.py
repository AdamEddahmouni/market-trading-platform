"""Primary-source verification for SEC EDGAR and congressional PTR public records."""

from .artifact import (
    ARTIFACT_SCHEMA_VERSION,
    PUBLIC_RECORD_PRIMARY_SOURCE_ARTIFACT_TYPE,
    build_verification_artifact,
)
from .pipeline import (
    PublicRecordDomain,
    verify_market_trackers_row,
)

PUBLIC_RECORD_PRIMARY_SOURCE_VERIFICATION_READY = "PUBLIC_RECORD_PRIMARY_SOURCE_VERIFICATION_READY"

__all__ = [
    "ARTIFACT_SCHEMA_VERSION",
    "PUBLIC_RECORD_PRIMARY_SOURCE_ARTIFACT_TYPE",
    "PUBLIC_RECORD_PRIMARY_SOURCE_VERIFICATION_READY",
    "PublicRecordDomain",
    "build_verification_artifact",
    "verify_market_trackers_row",
]

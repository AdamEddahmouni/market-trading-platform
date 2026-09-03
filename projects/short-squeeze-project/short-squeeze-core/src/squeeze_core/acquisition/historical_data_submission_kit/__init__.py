"""Operator-facing historical-data submission kit and offline preflight (Batch 04).

Built on top of the Batch 03 ``local_bar_intake`` package. Generates blank
templates, a synthetic-valid example, operator guides, a deterministic
invalid-scenario index, reason-code troubleshooting, and an offline preflight
workflow that produces a deterministic readiness report. Performs no acquisition,
no network access, no credential access, no case association, no outcome work, no
Phase 3A/3B records, and does not begin Phase 3E.
"""

from .checklist import CHECKLIST_ITEMS, build_operator_checklist
from .kit import (
    KIT_CONTRACT_VERSION,
    KIT_ROOT,
    build_batch04_fixtures,
    build_submission_kit,
    build_synthetic_valid_preflight_report,
)
from .preflight import (
    PREFLIGHT_CONTRACT_VERSION,
    PreflightReport,
    PreflightStatus,
    hash_file,
    run_preflight,
    run_preflight_from_bytes,
)
from .synthetic import (
    BUNDLE_ID,
    PROFILE_ID,
    RAW_CSV,
    build_column_mapping_profile,
    build_valid_manifest,
)
from .templates import (
    build_case_association_template,
    build_column_mapping_profile_template,
    build_intake_manifest_template,
)
from .troubleshooting import build_invalid_scenario_index, build_troubleshooting_index

__all__ = [
    "BUNDLE_ID",
    "CHECKLIST_ITEMS",
    "KIT_CONTRACT_VERSION",
    "KIT_ROOT",
    "PREFLIGHT_CONTRACT_VERSION",
    "PROFILE_ID",
    "PreflightReport",
    "PreflightStatus",
    "RAW_CSV",
    "build_batch04_fixtures",
    "build_case_association_template",
    "build_column_mapping_profile",
    "build_column_mapping_profile_template",
    "build_intake_manifest_template",
    "build_invalid_scenario_index",
    "build_operator_checklist",
    "build_submission_kit",
    "build_synthetic_valid_preflight_report",
    "build_troubleshooting_index",
    "build_valid_manifest",
    "hash_file",
    "run_preflight",
    "run_preflight_from_bytes",
]

"""Deterministic, offline assembly of the submission kit and its canonical fixtures.

``build_submission_kit`` returns every operator-facing kit file keyed by its path
relative to ``operator-kits/historical-market-bars/``. ``build_batch04_fixtures``
returns the committed canonical fixtures keyed by filename. Both are pure functions
of in-memory synthetic bytes with fixed instants, so repeated builds are
byte-identical. No real market data, no credentials, no network, no case
association, no outcome work, no later-phase records.
"""

from __future__ import annotations

import hashlib

from squeeze_core.serialization import canonical_json_bytes

from ..local_bar_intake.models import SCHEMA_VERSION
from . import documents
from .checklist import build_operator_checklist
from .preflight import PREFLIGHT_CONTRACT_VERSION, run_preflight_from_bytes
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


KIT_CONTRACT_VERSION = "phase_3d_submission_kit.v1"
KIT_ROOT = "operator-kits/historical-market-bars"


def _json(value) -> bytes:
    return canonical_json_bytes(value) + b"\n"


def _anchor(name: str, value: str) -> str:
    return hashlib.sha256(f"{name}\0{value}".encode("utf-8")).hexdigest()


def build_synthetic_valid_preflight_report():
    manifest = build_valid_manifest()
    profile = build_column_mapping_profile()
    return run_preflight_from_bytes(manifest, profile, RAW_CSV)


def build_submission_kit() -> dict[str, bytes]:
    """Every operator-facing kit file, keyed by path relative to the kit root."""
    manifest = build_valid_manifest()
    profile = build_column_mapping_profile()
    report = run_preflight_from_bytes(manifest, profile, RAW_CSV)

    files: dict[str, bytes] = {
        "README.md": documents.readme(),
        "QUICKSTART.md": documents.quickstart(),
        "EXPORT-CHECKLIST.md": documents.export_checklist(),
        "PROVIDER-AND-ENTITLEMENT-GUIDE.md": documents.provider_and_entitlement_guide(),
        "TIMEZONE-INTERVAL-SESSION-GUIDE.md": documents.timezone_interval_session_guide(),
        "ADJUSTMENT-SEMANTICS-GUIDE.md": documents.adjustment_semantics_guide(),
        "SHA256-AND-BYTE-LENGTH-GUIDE.md": documents.sha256_and_byte_length_guide(),
        "FOLDER-PLACEMENT-GUIDE.md": documents.folder_placement_guide(),
        "PREFLIGHT-GUIDE.md": documents.preflight_guide(),
        "TROUBLESHOOTING.md": documents.troubleshooting_doc(),
        "FINAL-OPERATOR-CHECKLIST.md": documents.final_operator_checklist(),
        "templates/intake-manifest.template.json": _json(build_intake_manifest_template()),
        "templates/column-mapping-profile.template.json": _json(
            build_column_mapping_profile_template()
        ),
        "templates/case-association.template.json": _json(build_case_association_template()),
        "examples/synthetic-valid/intake-manifest.json": _json(manifest),
        "examples/synthetic-valid/column-mapping-profile.json": _json(profile),
        "examples/synthetic-valid/raw/synthetic-bars.csv": RAW_CSV,
        "examples/synthetic-valid/preflight-report.json": _json(report),
        "examples/synthetic-invalid/README.md": documents.synthetic_invalid_readme(),
        "examples/synthetic-invalid/invalid-scenario-index.json": _json(
            build_invalid_scenario_index()
        ),
    }
    return dict(sorted(files.items()))


def _submission_kit_manifest(kit: dict[str, bytes], report) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "kit_contract_version": KIT_CONTRACT_VERSION,
        "preflight_contract_version": PREFLIGHT_CONTRACT_VERSION,
        "kit_root": KIT_ROOT,
        "document": "phase_3d_batch_04_submission_kit_manifest",
        "file_sha256": {
            name: hashlib.sha256(content).hexdigest() for name, content in sorted(kit.items())
        },
        "template_files": tuple(sorted(n for n in kit if n.startswith("templates/"))),
        "example_files": tuple(sorted(n for n in kit if n.startswith("examples/"))),
        "guide_files": tuple(sorted(n for n in kit if n.endswith(".md") and "/" not in n)),
        "synthetic_valid": {
            "bundle_id": BUNDLE_ID,
            "profile_id": PROFILE_ID,
            "artifact_sha256": report.artifact_sha256,
            "artifact_byte_length": report.artifact_byte_length,
            "normalized_bar_count": report.normalized_bar_count,
            "preflight_status": report.status.value,
            "ready_for_case_association": report.ready_for_case_association,
            "preflight_report_id": str(report.deterministic_id),
        },
        "real_market_data_committed": False,
        "credentials_included": False,
        "network_used": False,
        "case_association_performed": False,
        "outcome_capture_performed": False,
        "phase_3a_records_created": False,
        "phase_3b_records_created": False,
        "phase_3e_started": False,
    }


def build_batch04_fixtures() -> dict[str, bytes]:
    """Committed canonical fixtures for tests/fixtures/acquisition/batch04/."""
    manifest = build_valid_manifest()
    profile = build_column_mapping_profile()
    report = run_preflight_from_bytes(manifest, profile, RAW_CSV)
    kit = build_submission_kit()

    fixtures: dict[str, bytes] = {
        "intake-manifest.template.json": _json(build_intake_manifest_template()),
        "column-mapping-profile.template.json": _json(build_column_mapping_profile_template()),
        "case-association.template.json": _json(build_case_association_template()),
        "synthetic-valid-intake-manifest.json": _json(manifest),
        "synthetic-valid-column-mapping-profile.json": _json(profile),
        "synthetic-valid-bars.csv": RAW_CSV,
        "synthetic-valid-preflight-report.json": _json(report),
        "invalid-scenario-index.json": _json(build_invalid_scenario_index()),
        "troubleshooting-index.json": _json(build_troubleshooting_index()),
        "operator-checklist.json": _json(build_operator_checklist()),
        "submission-kit-manifest.json": _json(_submission_kit_manifest(kit, report)),
    }

    # Determinism anchors over every fixture so far, plus deterministic identities.
    raw_anchors: dict[str, str] = {
        name: hashlib.sha256(content).hexdigest() for name, content in sorted(fixtures.items())
    }
    raw_anchors["synthetic_manifest_id"] = str(manifest.deterministic_id)
    raw_anchors["synthetic_profile_id"] = str(profile.deterministic_id)
    raw_anchors["synthetic_preflight_report_id"] = str(report.deterministic_id)
    anchors = {name: _anchor(name, value) for name, value in sorted(raw_anchors.items())}
    fixtures["determinism-anchors.json"] = _json({
        "schema_version": SCHEMA_VERSION,
        "document": "phase_3d_batch_04_determinism_anchors",
        "anchors": anchors,
    })

    fixtures["fixture-metadata.json"] = _json({
        "schema_version": SCHEMA_VERSION,
        "document": "phase_3d_batch_04_fixture_metadata",
        "kit_root": KIT_ROOT,
        "file_sha256": {
            name: hashlib.sha256(content).hexdigest()
            for name, content in sorted(fixtures.items())
        },
        "fixture_classifications": ("SYNTHETIC_EDGE_CASE", "SYNTHETIC_FIXTURE"),
        "sensitive_content_included": False,
        "real_market_data_committed": False,
        "outcome_work_performed": False,
        "case_association_performed": False,
        "phase_3a_records_created": False,
        "phase_3b_records_created": False,
        "phase_3e_started": False,
    })
    return dict(sorted(fixtures.items()))


__all__ = [
    "KIT_CONTRACT_VERSION",
    "KIT_ROOT",
    "build_submission_kit",
    "build_batch04_fixtures",
    "build_synthetic_valid_preflight_report",
]

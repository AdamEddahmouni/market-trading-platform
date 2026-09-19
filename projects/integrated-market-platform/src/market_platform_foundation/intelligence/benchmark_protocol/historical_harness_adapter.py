"""Adapt Lane B ``historical_research_run_manifest_v1`` into IBP run records."""

from __future__ import annotations

from typing import Any

from ...canonical import canonical_bytes, sha256_bytes
from .contamination import (
    assert_historical_manifest_admissible,
    assert_no_evaluator_gold_in_system_bundle,
    strip_evaluator_only_fields,
)
from .types import (
    IBP_PROTOCOL_ID,
    IBP_PROTOCOL_SCHEMA_VERSION,
    IBP_RUN_RECORD_KIND,
    IBP_RUN_RECORD_SCHEMA_VERSION,
)


def adapt_historical_research_run_manifest_v1(
    manifest: dict[str, Any],
    *,
    suite_id: str | None = None,
    suite_catalog_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Map a historical research harness manifest to an IBP provenance record."""
    assert_historical_manifest_admissible(manifest)
    system_bundle = strip_evaluator_only_fields(manifest)
    assert_no_evaluator_gold_in_system_bundle(system_bundle)
    record: dict[str, Any] = {
        "artifact_kind": IBP_RUN_RECORD_KIND,
        "schema_version": IBP_RUN_RECORD_SCHEMA_VERSION,
        "protocol_id": IBP_PROTOCOL_ID,
        "protocol_schema_version": IBP_PROTOCOL_SCHEMA_VERSION,
        "upstream": {
            "artifact_kind": manifest.get("artifact_kind"),
            "run_id": manifest.get("run_id"),
            "run_fingerprint": manifest.get("run_fingerprint"),
            "dataset_fingerprint": manifest.get("dataset_fingerprint"),
            "research_code_sha": manifest.get("research_code_sha"),
            "evidence_class": manifest.get("evidence_class"),
            "corpus_evidence_authority": manifest.get("corpus_evidence_authority"),
        },
        "system_under_test_input": system_bundle,
        "research_metrics_snapshot": manifest.get("metrics"),
        "simulator": manifest.get("simulator"),
        "contamination_controls": {
            "evaluator_gold_stripped": True,
            "labels_path_removed_from_sut": True,
            "item9_calibration_blocked": True,
            "prospective_authority_blocked": True,
        },
        "scores_executed": False,
        "case_results": [],
        "suite_id": suite_id,
        "suite_catalog_fingerprint": suite_catalog_fingerprint,
        "governance": {
            "authority": manifest.get("corpus_evidence_authority"),
            "item9_effect": "NONE",
            "item7_effect": "NONE",
            "ftep_effect": "NONE",
            "live_authority": "NONE",
        },
    }
    record["record_fingerprint"] = sha256_bytes(
        canonical_bytes(
            {
                "upstream_run_id": manifest.get("run_id"),
                "upstream_run_fingerprint": manifest.get("run_fingerprint"),
                "suite_catalog_fingerprint": suite_catalog_fingerprint,
                "system_bundle_hash": sha256_bytes(canonical_bytes(system_bundle)),
            }
        )
    )
    return record


__all__ = ["adapt_historical_research_run_manifest_v1"]

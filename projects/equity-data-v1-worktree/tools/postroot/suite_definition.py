"""Deterministic postroot acceptance contract suite definition."""

from __future__ import annotations

from .suite_catalog import (
    REASON_CODES,
    build_fixture_catalog,
    build_reason_code_registry,
)
from .suite_contracts import build_contract_schemas, contract

PROCEDURE_ID = "AI-REVIEW-PROCESS-001"
PROCEDURE_SHA256 = "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8"
PLAN_SHA256 = "EE22C688167F5016D7ED1953BB1DAE516BC6AB343655A7D96535C6605D37E904"
SPECIFICATION_SHA256 = "7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35"
SUITE_LOGICAL_ID = "phase0.postroot_acceptance_contract_suite"
SUITE_APPROVAL_LOGICAL_ID = "phase0.postroot_acceptance_contract_suite.approval"

NON_AUTHORIZATIONS = [
    "ACCEPTANCE_INDEX_PUBLICATION",
    "AI_REVIEW_COVERAGE_PUBLICATION",
    "CANDIDATE_APPROVAL_PUBLICATION",
    "CANDIDATE_ROOT_RECONSTRUCTION",
    "FINAL_ACCEPTANCE_RESULT_PUBLICATION",
    "FORMAL_AI_REVIEW_RUN_EXECUTION",
    "PHASE_0A_OR_LATER_PHASE_WORK",
    "PHASE_0_PASS",
    "PROVIDER_BROKER_MODEL_OR_REMOTE_ACCESS",
]


def fixture(
    fixture_id: str,
    target_contract_id: str,
    validation_phase: str,
    expected_status: str,
    expected_reason_codes: list[str],
    invariant_under_test: str,
    input_artifacts: list[dict[str, object]],
    expected_derived_values: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "expected_derived_values": expected_derived_values or {"NOT_COMPUTABLE": True},
        "expected_reason_codes": sorted(set(expected_reason_codes)),
        "expected_status": expected_status,
        "fixture_id": fixture_id,
        "input_artifacts": input_artifacts,
        "invariant_under_test": invariant_under_test,
        "target_contract_id": target_contract_id,
        "validation_phase": validation_phase,
    }


def build_suite() -> dict[str, object]:
    return {
        "acknowledgements": [
            {
                "acknowledgement_id": "ACK-COMPANION-INPUT-001",
                "statement": "This suite is a candidate-neutral postroot integrity-review companion input only.",
            },
            {
                "acknowledgement_id": "ACK-NO-REVIEW-CLAIM-001",
                "statement": "This suite does not claim that any formal review, coverage, approval, index, or final result exists.",
            },
        ],
        "artifact_type": "PHASE0_POSTROOT_ACCEPTANCE_CONTRACT_SUITE",
        "authority_bindings": [
            {
                "authority_class": "INDEPENDENT_AI_REVIEW_PROCEDURE",
                "logical_id": "phase0.ai_review_procedure",
                "logical_path": "docs/superpowers/governance/2026-08-14-ai-review-process-001.json",
                "sha256": PROCEDURE_SHA256,
            },
            {
                "authority_class": "CONTROLLING_PHASE_0_PLAN_WITH_EXACT_HASH_WRITTEN_APPROVAL",
                "logical_id": "phase0.governance_plan",
                "logical_path": "docs/superpowers/plans/2026-08-13-phase-0-governance-and-no-live-safety.md",
                "sha256": PLAN_SHA256,
            },
            {
                "authority_class": "CANONICAL_SPECIFICATION",
                "logical_id": "foundation.canonical_specification.revision_3",
                "logical_path": "docs/superpowers/specs/2026-08-14-integrated-market-platform-foundation-design-revision-3.md",
                "sha256": SPECIFICATION_SHA256,
            },
        ],
        "canonical_encoding_profile": {
            "encoding": "UTF-8_WITHOUT_BOM",
            "line_endings": "LF_ONLY",
            "number_rule": "SIGNED_BASE10_INTEGER_ONLY",
            "object_key_order_rule": "UNICODE_CODE_POINT_ASCENDING",
            "profile_id": "PHASE0-CANONICAL-JSON-1.0.0",
            "trailing_newline": "FORBIDDEN",
            "whitespace_rule": "NO_INSIGNIFICANT_WHITESPACE",
        },
        "closed_contract_profile": {
            "additional_property_policy": "REJECT",
            "profile_id": "PHASE0-CLOSED-CONTRACT-1.0.0",
            "schema_version": "1.0.0",
        },
        "contract_schemas": build_contract_schemas(),
        "documented_on": "2026-08-14",
        "effectivity": {
            "activation_condition": "PROJECT-PRINCIPAL-001 explicitly approves this complete suite by logical ID and exact SHA-256 after review.",
            "approval_event_state": "NOT_YET_OCCURRED_OR_RECORDED",
            "approval_must_bind": ["logical_id", "sha256"],
            "current_effectivity": "PENDING_EXACT_HASH_PRINCIPAL_APPROVAL",
            "determination_rule": "Effectivity is established by external attributable exact-hash principal-approval evidence.",
            "effective_from": "THE_TIMESTAMP_IN_THE_EXTERNAL_EXACT_HASH_APPROVAL_EVIDENCE",
            "effective_until": "SUPERSEDED_OR_REVOKED_BY_A_LATER_EXACT_HASH_PRINCIPAL_DECISION",
            "self_hash_rule": "This suite does not embed its own SHA-256.",
        },
        "fixture_catalog": build_fixture_catalog(),
        "logical_id": SUITE_LOGICAL_ID,
        "non_authorizations": NON_AUTHORIZATIONS,
        "reason_code_registry": build_reason_code_registry(),
        "schema_version": "1.0.0",
        "suite_scope": {
            "binding_model": "CANDIDATE_NEUTRAL_POSTROOT_COMPANION",
            "purpose": "Integrity review companion contracts and fixtures.",
            "synthetic_fixture_subjects_only": True,
        },
        "supersession": {
            "revision_rule": "Any suite byte change creates a new revision requiring new exact-hash approval.",
            "superseded_by": None,
            "supersedes": [],
        },
        "validation_order": [
            "BYTE_AND_JSON",
            "CLOSED_SCHEMA",
            "IDENTITY_AND_HASH",
            "CROSS_ARTIFACT_AND_COVERAGE",
            "ACCEPTANCE_INDEX",
            "FINAL_OUTCOME",
        ],
    }

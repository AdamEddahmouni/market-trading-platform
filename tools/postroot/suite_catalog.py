"""Reason registry and synthetic fixture catalog for the postroot suite."""

from __future__ import annotations

from typing import Any

from .suite_contracts import build_contract_schemas

REASON_REGISTRY: list[dict[str, str]] = [
    {"gate_effect": "FAIL", "reason_code": "APPROVAL-CAPACITY-DUPLICATE", "semantic_condition": "A required approval capacity appears more than once."},
    {"gate_effect": "FAIL", "reason_code": "APPROVAL-CAPACITY-EXTRA", "semantic_condition": "An approval record declares a capacity outside the required set."},
    {"gate_effect": "BLOCKED", "reason_code": "APPROVAL-CAPACITY-MISSING", "semantic_condition": "A required approval capacity is absent from the bundle."},
    {"gate_effect": "FAIL", "reason_code": "APPROVAL-HASH-BINDING-MISMATCH", "semantic_condition": "An approval record binds the wrong governed hash."},
    {"gate_effect": "FAIL", "reason_code": "APPROVAL-IDENTITY-INVALID", "semantic_condition": "An approval record identity does not recompute from its content."},
    {"gate_effect": "BLOCKED", "reason_code": "APPROVAL-NOT-EFFECTIVE", "semantic_condition": "A required approval is not yet effective."},
    {"gate_effect": "FAIL", "reason_code": "APPROVAL-PRINCIPAL-MISMATCH", "semantic_condition": "An approval principal does not match the required principal."},
    {"gate_effect": "FAIL", "reason_code": "APPROVAL-WAIVER-ATTEMPT", "semantic_condition": "An approval attempts to waive a mandatory FAIL or BLOCKED outcome."},
    {"gate_effect": "REJECTED", "reason_code": "BYTE-CANONICAL-MISMATCH", "semantic_condition": "Bytes are not canonical JSON under the suite profile."},
    {"gate_effect": "REJECTED", "reason_code": "BYTE-TRAILING-DATA", "semantic_condition": "Trailing bytes follow the JSON value."},
    {"gate_effect": "REJECTED", "reason_code": "BYTE-UTF8-BOM", "semantic_condition": "A UTF-8 BOM prefixes the artifact bytes."},
    {"gate_effect": "REJECTED", "reason_code": "BYTE-UTF8-INVALID", "semantic_condition": "The artifact bytes are not valid UTF-8."},
    {"gate_effect": "FAIL", "reason_code": "COVERAGE-CLASS-INVALID", "semantic_condition": "A selected run uses an invalid review class."},
    {"gate_effect": "FAIL", "reason_code": "COVERAGE-DUPLICATE-IDENTITY", "semantic_condition": "Coverage selects duplicate semantic identities."},
    {"gate_effect": "FAIL", "reason_code": "COVERAGE-EXTRA-ID", "semantic_condition": "Coverage reports an extra logical or assertion ID."},
    {"gate_effect": "FAIL", "reason_code": "COVERAGE-ISOLATION-INVALID", "semantic_condition": "A required isolation check does not pass."},
    {"gate_effect": "BLOCKED", "reason_code": "COVERAGE-MISSING-ID", "semantic_condition": "Coverage is missing a required logical or assertion ID."},
    {"gate_effect": "FAIL", "reason_code": "COVERAGE-SELECTION-CARDINALITY", "semantic_condition": "Coverage selects the wrong number of qualifying runs."},
    {"gate_effect": "FAIL", "reason_code": "GATE-FINAL-RESULT-ID-MISMATCH", "semantic_condition": "The final result identity does not recompute."},
    {"gate_effect": "FAIL", "reason_code": "GATE-OUTCOME-MISMATCH", "semantic_condition": "The stored final outcome does not match derived precedence."},
    {"gate_effect": "FAIL", "reason_code": "GATE-PRECEDENCE-MISMATCH", "semantic_condition": "FAIL over BLOCKED precedence was violated."},
    {"gate_effect": "FAIL", "reason_code": "HASH-CANDIDATE-ROOT-MISMATCH", "semantic_condition": "A declared candidate root does not match bound bytes."},
    {"gate_effect": "FAIL", "reason_code": "HASH-CONTENT-MISMATCH", "semantic_condition": "A declared content hash does not match recomputed bytes."},
    {"gate_effect": "FAIL", "reason_code": "HASH-PROCEDURE-MISMATCH", "semantic_condition": "A declared procedure hash does not match the approved hash."},
    {"gate_effect": "FAIL", "reason_code": "HASH-REGISTRY-MISMATCH", "semantic_condition": "A declared registry hash does not match bound bytes."},
    {"gate_effect": "FAIL", "reason_code": "HASH-REVIEW-OUTPUT-MISMATCH", "semantic_condition": "A review output hash does not match canonical output bytes."},
    {"gate_effect": "FAIL", "reason_code": "HASH-RUN-MISMATCH", "semantic_condition": "A review run identity does not match canonical run bytes."},
    {"gate_effect": "FAIL", "reason_code": "HASH-SUITE-MISMATCH", "semantic_condition": "A declared suite hash does not match bound suite bytes."},
    {"gate_effect": "FAIL", "reason_code": "ID-DUPLICATE-SEMANTIC-IDENTITY", "semantic_condition": "Two selected records share one semantic identity."},
    {"gate_effect": "FAIL", "reason_code": "ID-LOGICAL-ID-INVALID", "semantic_condition": "A logical ID violates the closed logical-ID format."},
    {"gate_effect": "FAIL", "reason_code": "ID-RECORD-ID-MISMATCH", "semantic_condition": "A record identity field does not match content-derived identity."},
    {"gate_effect": "FAIL", "reason_code": "INDEX-ABSOLUTE-PATH", "semantic_condition": "An index member path is absolute rather than repository-relative."},
    {"gate_effect": "FAIL", "reason_code": "INDEX-DUPLICATE-LOGICAL-ID", "semantic_condition": "An index member logical ID appears more than once."},
    {"gate_effect": "FAIL", "reason_code": "INDEX-DUPLICATE-PATH", "semantic_condition": "An index member path maps more than once."},
    {"gate_effect": "FAIL", "reason_code": "INDEX-EXTRA-MEMBER", "semantic_condition": "The index contains a member outside the required set."},
    {"gate_effect": "FAIL", "reason_code": "INDEX-FINAL-RESULT-MEMBERSHIP", "semantic_condition": "The final result appears as an ordinary index member."},
    {"gate_effect": "FAIL", "reason_code": "INDEX-MEMBER-BYTE-LENGTH-MISMATCH", "semantic_condition": "An index member byte length does not match the mapped file."},
    {"gate_effect": "FAIL", "reason_code": "INDEX-MEMBER-HASH-MISMATCH", "semantic_condition": "An index member hash does not match mapped file bytes."},
    {"gate_effect": "BLOCKED", "reason_code": "INDEX-MISSING-MEMBER", "semantic_condition": "A required index member is absent."},
    {"gate_effect": "FAIL", "reason_code": "INDEX-NONNORMALIZED-PATH", "semantic_condition": "An index member path is not normalized."},
    {"gate_effect": "FAIL", "reason_code": "INDEX-ROOT-HASH-MISMATCH", "semantic_condition": "The stored root hash does not recompute."},
    {"gate_effect": "FAIL", "reason_code": "INDEX-ROOT-ID-MISMATCH", "semantic_condition": "The index root ID does not match the declared opaque root."},
    {"gate_effect": "FAIL", "reason_code": "INDEX-SELF-MEMBERSHIP", "semantic_condition": "The acceptance index includes itself as a member."},
    {"gate_effect": "FAIL", "reason_code": "INDEX-SHA256-MISMATCH", "semantic_condition": "The stored index hash does not recompute."},
    {"gate_effect": "FAIL", "reason_code": "INDEX-SYMLINK-OR-REPARSE-ESCAPE", "semantic_condition": "An index member path escapes through a symlink or reparse point."},
    {"gate_effect": "REJECTED", "reason_code": "JSON-DUPLICATE-KEY", "semantic_condition": "A JSON object contains a duplicate member name."},
    {"gate_effect": "REJECTED", "reason_code": "JSON-PARSE-INVALID", "semantic_condition": "The artifact bytes are not valid JSON."},
    {"gate_effect": "FAIL", "reason_code": "REF-CONTRADICTORY-BINDING", "semantic_condition": "Two bindings for the same logical ID disagree."},
    {"gate_effect": "BLOCKED", "reason_code": "REF-UNRESOLVED", "semantic_condition": "A required cross-artifact reference cannot be resolved."},
    {"gate_effect": "FAIL", "reason_code": "REVIEW-AUTHORING-CONTEXT", "semantic_condition": "A review inherited project-authoring context."},
    {"gate_effect": "BLOCKED", "reason_code": "REVIEW-CLASS-MISSING", "semantic_condition": "A required review class run is absent."},
    {"gate_effect": "FAIL", "reason_code": "REVIEW-DISQUALIFICATION-CODE-MISMATCH", "semantic_condition": "Disqualification codes do not match established rules."},
    {"gate_effect": "FAIL", "reason_code": "REVIEW-GOVERNED-SUBJECT-MUTATION", "semantic_condition": "A review mutated governed subject bytes."},
    {"gate_effect": "FAIL", "reason_code": "REVIEW-OUTCOME-MISMATCH", "semantic_condition": "A review recommended outcome does not recompute."},
    {"gate_effect": "FAIL", "reason_code": "REVIEW-UNDECLARED-TOOL-OR-EXTERNAL-ACCESS", "semantic_condition": "A review used an undeclared tool or external access."},
    {"gate_effect": "FAIL", "reason_code": "SCHEMA-ARRAY-DUPLICATE", "semantic_condition": "A set-valued array contains duplicate entries."},
    {"gate_effect": "FAIL", "reason_code": "SCHEMA-ARRAY-ORDER", "semantic_condition": "A set-valued array is not in the required order."},
    {"gate_effect": "FAIL", "reason_code": "SCHEMA-ENUM-INVALID", "semantic_condition": "A value is outside the declared enumeration."},
    {"gate_effect": "FAIL", "reason_code": "SCHEMA-FORMAT-INVALID", "semantic_condition": "A value violates a declared format rule."},
    {"gate_effect": "FAIL", "reason_code": "SCHEMA-MISSING-REQUIRED-FIELD", "semantic_condition": "A required field is absent."},
    {"gate_effect": "FAIL", "reason_code": "SCHEMA-TYPE-INVALID", "semantic_condition": "A value has the wrong primitive or compound type."},
    {"gate_effect": "FAIL", "reason_code": "SCHEMA-UNDECLARED-FIELD", "semantic_condition": "An undeclared field is present in a closed object."},
]

REASON_CODES = tuple(row["reason_code"] for row in REASON_REGISTRY)

_PREFIX_BY_CODE = {
    "APPROVAL-": "APPROVAL-",
    "BYTE-": "BYTE-",
    "COVERAGE-": "COVERAGE-",
    "GATE-": "GATE-",
    "HASH-": "HASH-",
    "ID-": "ID-",
    "INDEX-": "INDEX-",
    "JSON-": "JSON-",
    "REF-": "REF-",
    "REVIEW-": "REVIEW-",
    "SCHEMA-": "SCHEMA-",
}


def build_reason_code_registry() -> list[dict[str, str]]:
    return [dict(row) for row in REASON_REGISTRY]


def _fixture(
    fixture_id: str,
    target_contract_id: str,
    validation_phase: str,
    invariant_under_test: str,
    input_artifacts: list[dict[str, Any]],
    expected_status: str,
    expected_reason_codes: list[str],
    expected_derived_values: dict[str, Any],
) -> dict[str, Any]:
    return {
        "expected_derived_values": expected_derived_values,
        "expected_reason_codes": sorted(set(expected_reason_codes)),
        "expected_status": expected_status,
        "fixture_id": fixture_id,
        "input_artifacts": input_artifacts,
        "invariant_under_test": invariant_under_test,
        "target_contract_id": target_contract_id,
        "validation_phase": validation_phase,
    }


def _golden_review_output() -> dict[str, Any]:
    root = "A" * 64
    return {
        "candidate_evidence_root": root,
        "coverage_assertion_ids": ["GOV-001"],
        "coverage_logical_ids": ["phase0.governance_plan"],
        "findings": [],
        "limitations": [],
        "recommended_candidate_outcome": "PASS",
        "reproduction_results": [],
        "review_class": "INTEGRITY_AND_REPRODUCTION_AUDIT",
        "summary": "Synthetic golden review output for contract validation.",
    }


def _golden_review_run() -> dict[str, Any]:
    root = "A" * 64
    return {
        "candidate_evidence_root": root,
        "canonical_configuration_hash": "B" * 64,
        "completed_at": "2026-08-14T12:00:00.000000000Z",
        "coverage_assertion_ids": ["GOV-001"],
        "coverage_logical_ids": ["phase0.governance_plan"],
        "disqualification_reason_codes": [],
        "eligibility_result": {"status": "ELIGIBLE", "violation_count": 0, "violations": []},
        "findings": [],
        "input_artifact_hashes": [
            {"logical_id": "phase0.postroot_acceptance_contract_suite", "sha256": "C" * 64},
            {"logical_id": "phase0.postroot_acceptance_contract_suite.approval", "sha256": "D" * 64},
        ],
        "model_service_and_declared_version": {
            "declared_model_version": "synthetic-1",
            "model_service": "synthetic-service",
        },
        "plan_hash": "E" * 64,
        "qualification_state": "QUALIFYING",
        "recommended_candidate_outcome": "PASS",
        "registry_hash": "F" * 64,
        "reproduction_results": [],
        "review_class": "INTEGRITY_AND_REPRODUCTION_AUDIT",
        "review_output_hash": "1" * 64,
        "review_procedure_id_and_hash": {
            "procedure_id": "AI-REVIEW-PROCESS-001",
            "sha256": "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8",
        },
        "review_run_id": "2" * 64,
        "run_id": "3" * 64,
        "runtime_and_tool_versions": [
            {
                "component_id": "python",
                "declared_version": "3.11",
                "runtime_context": "synthetic",
            }
        ],
        "specification_hash": "4" * 64,
        "started_at": "2026-08-14T11:00:00.000000000Z",
        "terminal_state": "COMPLETE",
    }


def _golden_coverage() -> dict[str, Any]:
    root = "A" * 64
    return {
        "candidate_evidence_root": root,
        "coverage_assertion_ids_union": ["GOV-001"],
        "coverage_logical_ids_union": ["phase0.governance_plan"],
        "disqualification_reason_codes": [],
        "duplicate_identity_results": {
            "duplicate_assertion_ids": [],
            "duplicate_logical_ids": [],
            "duplicate_review_run_ids": [],
            "has_duplicates": False,
        },
        "expected_assertion_ids": ["GOV-001"],
        "expected_logical_ids": ["phase0.governance_plan"],
        "extra_assertion_ids": [],
        "extra_logical_ids": [],
        "invalid_review_run_ids": [],
        "invalid_selected_run_reason_codes": [],
        "isolation_check_results": [],
        "missing_assertion_ids": [],
        "missing_logical_ids": [],
        "qualification_status": "QUALIFIED",
        "qualifying_review_run_ids": ["2" * 64, "5" * 64],
        "registry_hash": "F" * 64,
        "review_class_assignments": [
            {
                "review_class": "ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT",
                "review_run_id": "2" * 64,
            },
            {
                "review_class": "INTEGRITY_AND_REPRODUCTION_AUDIT",
                "review_run_id": "5" * 64,
            },
        ],
        "review_procedure_id_and_hash": {
            "procedure_id": "AI-REVIEW-PROCESS-001",
            "sha256": "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8",
        },
        "selected_review_run_ids": ["2" * 64, "5" * 64],
    }


def _golden_preapproval() -> dict[str, Any]:
    return {
        "acknowledgements": [
            {
                "acknowledgement_id": "ACK-DOCUMENTARY-SCOPE-001",
                "statement": "Synthetic eligibility acknowledgement.",
            }
        ],
        "artifact_type": "PREAPPROVAL_REVIEWER_ELIGIBILITY_RESULT",
        "authority_bindings": [
            {
                "logical_id": "phase0.ai_review_procedure",
                "logical_path": "synthetic/ai-review-procedure.json",
                "sha256": "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8",
            }
        ],
        "check_results": [
            {
                "check_id": "PREELIG-ROLE-RESOLUTION-001",
                "evidence_refs": ["phase0.role_assignment"],
                "expected_condition": "Synthetic expected condition.",
                "observed_condition": "Synthetic observed condition.",
                "reason_codes": [],
                "status": "PASS",
            },
            {
                "check_id": "PREELIG-PROCEDURE-DESIGNATION-001",
                "evidence_refs": ["phase0.role_assignment"],
                "expected_condition": "Synthetic expected condition.",
                "observed_condition": "Synthetic observed condition.",
                "reason_codes": [],
                "status": "PASS",
            },
            {
                "check_id": "PREELIG-PROCEDURE-APPROVAL-001",
                "evidence_refs": ["phase0.ai_review_procedure"],
                "expected_condition": "Synthetic expected condition.",
                "observed_condition": "Synthetic observed condition.",
                "reason_codes": [],
                "status": "PASS",
            },
            {
                "check_id": "PREELIG-REVIEW-CONTROLS-001",
                "evidence_refs": ["phase0.ai_review_procedure"],
                "expected_condition": "Synthetic expected condition.",
                "observed_condition": "Synthetic observed condition.",
                "reason_codes": [],
                "status": "PASS",
            },
            {
                "check_id": "PREELIG-NONCIRCULARITY-001",
                "evidence_refs": ["phase0.ai_review_procedure"],
                "expected_condition": "Synthetic expected condition.",
                "observed_condition": "Synthetic observed condition.",
                "reason_codes": [],
                "status": "PASS",
            },
            {
                "check_id": "PREELIG-NO-FALSE-EVIDENCE-001",
                "evidence_refs": ["phase0.ai_review_procedure"],
                "expected_condition": "Synthetic expected condition.",
                "observed_condition": "Synthetic observed condition.",
                "reason_codes": [],
                "status": "PASS",
            },
        ],
        "documented_on": "2026-08-14",
        "effectivity": {"current_effectivity": "PENDING_EXACT_HASH_PRINCIPAL_APPROVAL"},
        "eligibility_determination": {
            "blocked_check_count": 0,
            "failed_check_count": 0,
            "passed_check_count": 6,
            "required_check_count": 6,
            "status": "ELIGIBLE",
            "violation_count": 0,
            "violations": [],
        },
        "governance_effect": {"gov002_current_status": "BLOCKED_PENDING_EFFECTIVE_EXACT_HASH_APPROVAL_OF_THIS_RESULT"},
        "logical_id": "phase0.preapproval_reviewer_eligibility",
        "non_authorizations": ["AI_REVIEW_RUN_EXECUTION"],
        "record_status": "READY_FOR_EXACT_HASH_PRINCIPAL_REVIEW",
        "schema_version": "1.0.0",
        "supersession": {"revision_rule": "Any content change requires new approval."},
        "validation_contract": {
            "check_id_order_required": [
                "PREELIG-ROLE-RESOLUTION-001",
                "PREELIG-PROCEDURE-DESIGNATION-001",
                "PREELIG-PROCEDURE-APPROVAL-001",
                "PREELIG-REVIEW-CONTROLS-001",
                "PREELIG-NONCIRCULARITY-001",
                "PREELIG-NO-FALSE-EVIDENCE-001",
            ],
            "profile_id": "PHASE0-GOVERNANCE-DOCUMENT-JSON-1.0.0",
        },
    }


def _golden_suite_approval_record() -> dict[str, Any]:
    return {
        "approval_record_id": "B" * 64,
        "approved_at": "2026-08-14T12:00:00.000000000Z",
        "approved_by_principal_id": "PROJECT-PRINCIPAL-001",
        "approved_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "approved_logical_id": "phase0.postroot_acceptance_contract_suite",
        "approved_sha256": "A" * 64,
        "approval_scope": "INTEGRITY_REVIEW_COMPANION_INPUT_ONLY",
        "status": "APPROVED",
    }


def _golden_suite_approval() -> dict[str, Any]:
    record_without_id = {
        "approved_at": "2026-08-14T12:00:00.000000000Z",
        "approved_by_principal_id": "PROJECT-PRINCIPAL-001",
        "approved_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "approved_logical_id": "phase0.postroot_acceptance_contract_suite",
        "approved_sha256": "A" * 64,
        "approval_scope": "INTEGRITY_REVIEW_COMPANION_INPUT_ONLY",
        "procedure_id": "AI-REVIEW-PROCESS-001",
        "procedure_sha256": "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8",
        "status": "APPROVED",
    }
    return {
        **record_without_id,
        "approval_record_id": "B" * 64,
    }


def _golden_approval_records() -> dict[str, Any]:
    return {
        "aggregate_approval_status": "PASS",
        "approval_records": [_golden_suite_approval_record()],
        "assertion_run_hash": "1" * 64,
        "candidate_evidence_root": "A" * 64,
        "duplicate_capacities": [],
        "extra_capacities": [],
        "missing_capacities": [],
        "observed_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "plan_hash": "E" * 64,
        "procedure_id_and_hash": {
            "procedure_id": "AI-REVIEW-PROCESS-001",
            "sha256": "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8",
        },
        "reason_codes": [],
        "registry_hash": "F" * 64,
        "required_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "specification_hash": "4" * 64,
        "suite_id_and_hash": {
            "logical_id": "phase0.postroot_acceptance_contract_suite",
            "sha256": "C" * 64,
        },
    }


def _golden_acceptance_index() -> dict[str, Any]:
    return {
        "candidate_evidence_root": "A" * 64,
        "index_members": [
            {
                "byte_length": 10,
                "logical_id": "phase0.governance_plan",
                "media_type": "text/markdown",
                "member_sha256": "B" * 64,
                "repository_relative_path": "synthetic/governance-plan.md",
                "root_id": "ROOT-TEST-001",
            }
        ],
        "index_sha256": "C" * 64,
        "logical_id": "phase0.acceptance_index",
        "procedure_id_and_hash": {
            "procedure_id": "AI-REVIEW-PROCESS-001",
            "sha256": "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8",
        },
        "root_hash": "D" * 64,
        "root_id": "ROOT-TEST-001",
        "schema_version": "1.0.0",
        "suite_id_and_hash": {
            "logical_id": "phase0.postroot_acceptance_contract_suite",
            "sha256": "E" * 64,
        },
    }


def _golden_final_result() -> dict[str, Any]:
    return {
        "assertion_aggregate_status": "PASS",
        "candidate_evidence_root": "A" * 64,
        "completed_at": "2026-08-14T12:00:00.000000000Z",
        "final_result_id": "B" * 64,
        "index_sha256": "C" * 64,
        "logical_id": "phase0.final_acceptance_result",
        "outcome": "PASS",
        "reason_codes": [],
        "review_coverage_status": "QUALIFIED",
        "root_hash": "D" * 64,
        "schema_version": "1.0.0",
        "suite_sha256": "E" * 64,
    }


GOLDEN_FIXTURES: list[tuple[str, str, dict[str, Any]]] = [
    ("GOLDEN-AI-REVIEW-OUTPUT-001", "phase0.ai_review_output.contract", _golden_review_output()),
    ("GOLDEN-AI-REVIEW-RUN-001", "phase0.ai_review_run.contract", _golden_review_run()),
    ("GOLDEN-AI-REVIEW-COVERAGE-001", "phase0.ai_review_coverage.contract", _golden_coverage()),
    ("GOLDEN-PREAPPROVAL-ELIGIBILITY-001", "phase0.preapproval_reviewer_eligibility.contract", _golden_preapproval()),
    ("GOLDEN-SUITE-APPROVAL-001", "phase0.postroot_acceptance_contract_suite.approval.contract", _golden_suite_approval()),
    ("GOLDEN-APPROVAL-RECORDS-001", "phase0.approval_records.contract", _golden_approval_records()),
    ("GOLDEN-ACCEPTANCE-INDEX-001", "phase0.acceptance_index.contract", _golden_acceptance_index()),
    ("GOLDEN-FINAL-ACCEPTANCE-RESULT-001", "phase0.final_acceptance_result.contract", _golden_final_result()),
]


def _adversarial_fixture_for_code(code: str) -> dict[str, Any]:
    contract_by_prefix = {
        "APPROVAL-": "phase0.approval_records.contract",
        "BYTE-": "phase0.ai_review_output.contract",
        "COVERAGE-": "phase0.ai_review_coverage.contract",
        "GATE-": "phase0.final_acceptance_result.contract",
        "HASH-": "phase0.ai_review_run.contract",
        "ID-": "phase0.ai_review_run.contract",
        "INDEX-": "phase0.acceptance_index.contract",
        "JSON-": "phase0.ai_review_output.contract",
        "REF-": "phase0.ai_review_coverage.contract",
        "REVIEW-": "phase0.ai_review_run.contract",
        "SCHEMA-": "phase0.ai_review_output.contract",
    }
    phase_by_prefix = {
        "APPROVAL-": "CROSS_ARTIFACT_AND_COVERAGE",
        "BYTE-": "BYTE_AND_JSON",
        "COVERAGE-": "CROSS_ARTIFACT_AND_COVERAGE",
        "GATE-": "FINAL_OUTCOME",
        "HASH-": "CROSS_ARTIFACT_AND_COVERAGE",
        "ID-": "CROSS_ARTIFACT_AND_COVERAGE",
        "INDEX-": "ACCEPTANCE_INDEX",
        "JSON-": "BYTE_AND_JSON",
        "REF-": "CROSS_ARTIFACT_AND_COVERAGE",
        "REVIEW-": "CROSS_ARTIFACT_AND_COVERAGE",
        "SCHEMA-": "CROSS_ARTIFACT_AND_COVERAGE",
    }
    prefix = next(key for key in contract_by_prefix if code.startswith(key))
    target = contract_by_prefix[prefix]
    phase = phase_by_prefix[prefix]
    gate_effect = next(row["gate_effect"] for row in REASON_REGISTRY if row["reason_code"] == code)
    expected_status = gate_effect if gate_effect in {"REJECTED", "BLOCKED", "FAIL", "INVALID"} else "FAIL"
    if expected_status == "REJECTED":
        raw = '{"a":1,"a":2}' if code == "JSON-DUPLICATE-KEY" else "\xef\xbb\xbf{}"
        if code == "BYTE-UTF8-INVALID":
            return _fixture(
                f"ADV-{code}",
                target,
                phase,
                f"Adversarial vector for {code}.",
                [
                    {
                        "artifact_role": "primary_subject",
                        "content_encoding": "INVALID_UTF8",
                        "media_type": "application/json",
                        "raw_bytes_hex": "FFFE",
                    }
                ],
                expected_status,
                [code],
                {"NOT_COMPUTABLE": True},
            )
        elif code == "BYTE-TRAILING-DATA":
            raw = "{} "
        elif code == "BYTE-CANONICAL-MISMATCH":
            raw = '{ "a": 1 }'
        elif code == "JSON-PARSE-INVALID":
            raw = "{"
        elif code == "BYTE-UTF8-BOM":
            raw = "\ufeff{}"
        else:
            raw = '{"a":1,"a":2}'
        return _fixture(
            f"ADV-{code}",
            target,
            phase,
            f"Adversarial vector for {code}.",
            [{"artifact_role": "primary_subject", "content_encoding": "UTF-8", "media_type": "application/json", "raw_json_text": raw}],
            expected_status,
            [code],
            {"NOT_COMPUTABLE": True},
        )

    subject = _golden_review_output()
    if prefix == "SCHEMA-":
        subject = {"summary": "missing required fields"}
    elif prefix == "INDEX-":
        subject = _golden_acceptance_index()
        if code == "INDEX-SELF-MEMBERSHIP":
            subject["index_members"].append(
                {
                    "byte_length": 1,
                    "logical_id": "phase0.acceptance_index",
                    "media_type": "application/json",
                    "member_sha256": "F" * 64,
                    "repository_relative_path": "synthetic/self.json",
                    "root_id": "ROOT-TEST-001",
                }
            )
        elif code == "INDEX-FINAL-RESULT-MEMBERSHIP":
            subject["index_members"].append(
                {
                    "byte_length": 1,
                    "logical_id": "phase0.final_acceptance_result",
                    "media_type": "application/json",
                    "member_sha256": "F" * 64,
                    "repository_relative_path": "synthetic/final.json",
                    "root_id": "ROOT-TEST-001",
                }
            )
        elif code == "INDEX-ABSOLUTE-PATH":
            subject["index_members"][0]["repository_relative_path"] = "/absolute/path.json"
        elif code == "INDEX-NONNORMALIZED-PATH":
            subject["index_members"][0]["repository_relative_path"] = "synthetic/../escape.json"
        elif code == "INDEX-DUPLICATE-LOGICAL-ID":
            subject["index_members"].append(dict(subject["index_members"][0]))
        elif code == "INDEX-DUPLICATE-PATH":
            duplicate = dict(subject["index_members"][0])
            duplicate["logical_id"] = "phase0.ai_review_runs"
            subject["index_members"].append(duplicate)
        elif code == "INDEX-SHA256-MISMATCH":
            subject["index_sha256"] = "0" * 64
        elif code == "INDEX-ROOT-HASH-MISMATCH":
            subject["root_hash"] = "0" * 64
        elif code == "INDEX-MEMBER-HASH-MISMATCH":
            subject["index_members"][0]["member_sha256"] = "0" * 64
    elif prefix == "GATE-":
        subject = _golden_final_result()
        if code == "GATE-OUTCOME-MISMATCH":
            subject["outcome"] = "PASS"
            expected_status = "FAIL"
        elif code == "GATE-PRECEDENCE-MISMATCH":
            subject["outcome"] = "BLOCKED"
            expected_status = "FAIL"
        elif code == "GATE-FINAL-RESULT-ID-MISMATCH":
            subject["final_result_id"] = "0" * 64
    elif prefix == "COVERAGE-":
        subject = _golden_coverage()
        if code == "COVERAGE-MISSING-ID":
            subject["missing_logical_ids"] = ["phase0.missing"]
            expected_status = "BLOCKED"
        elif code == "COVERAGE-SELECTION-CARDINALITY":
            subject["selected_review_run_ids"] = ["2" * 64, "5" * 64, "6" * 64]
            expected_status = "INVALID"
        elif code == "COVERAGE-CLASS-INVALID":
            subject["review_class_assignments"][0]["review_class"] = "INVALID"
            expected_status = "INVALID"
    elif prefix == "APPROVAL-":
        subject = _golden_approval_records()
        if code == "APPROVAL-CAPACITY-MISSING":
            subject["missing_capacities"] = ["RELEASE_OWNER"]
            subject["aggregate_approval_status"] = "BLOCKED"
            expected_status = "BLOCKED"
        elif code == "APPROVAL-HASH-BINDING-MISMATCH":
            subject["suite_id_and_hash"]["sha256"] = "0" * 64
    elif prefix == "REVIEW-":
        subject = _golden_review_run()
        if code == "REVIEW-CLASS-MISSING":
            expected_status = "BLOCKED"
        elif code == "REVIEW-OUTCOME-MISMATCH":
            subject["recommended_candidate_outcome"] = "PASS"
    elif prefix == "HASH-":
        subject = _golden_review_run()
        if code == "HASH-RUN-MISMATCH":
            subject["review_run_id"] = "0" * 64
        elif code == "HASH-CANDIDATE-ROOT-MISMATCH":
            subject["candidate_evidence_root"] = "0" * 64
        elif code == "HASH-PROCEDURE-MISMATCH":
            subject["review_procedure_id_and_hash"]["sha256"] = "0" * 64
        elif code == "HASH-REGISTRY-MISMATCH":
            subject["registry_hash"] = "0" * 64
        elif code == "HASH-REVIEW-OUTPUT-MISMATCH":
            subject["review_output_hash"] = "0" * 64
        elif code == "HASH-SUITE-MISMATCH":
            subject["input_artifact_hashes"][0]["sha256"] = "0" * 64
        elif code == "HASH-CONTENT-MISMATCH":
            subject["plan_hash"] = "0" * 64
    elif prefix == "ID-":
        subject = _golden_review_run()
        if code == "ID-LOGICAL-ID-INVALID":
            subject["review_run_id"] = "INVALID"
        elif code == "ID-RECORD-ID-MISMATCH":
            subject["review_run_id"] = "0" * 64
        elif code == "ID-DUPLICATE-SEMANTIC-IDENTITY":
            subject["input_artifact_hashes"].append(subject["input_artifact_hashes"][0])
    elif prefix == "REF-":
        subject = _golden_coverage()
        subject["expected_logical_ids"] = []
        if code == "REF-UNRESOLVED":
            expected_status = "BLOCKED"

    return _fixture(
        f"ADV-{code}",
        target,
        phase,
        f"Adversarial vector for {code}.",
        [{"artifact_role": "primary_subject", "content_encoding": "UTF-8", "media_type": "application/json", "structured_value": subject}],
        expected_status,
        [code],
        {"NOT_COMPUTABLE": True},
    )


def build_fixture_catalog() -> list[dict[str, Any]]:
    fixtures: list[dict[str, Any]] = []
    for fixture_id, contract_id, value in GOLDEN_FIXTURES:
        fixtures.append(
            _fixture(
                fixture_id,
                contract_id,
                "CLOSED_SCHEMA",
                f"Golden vector for {contract_id}.",
                [{"artifact_role": "primary_subject", "content_encoding": "UTF-8", "media_type": "application/json", "structured_value": value}],
                "PASS",
                [],
                {"NOT_COMPUTABLE": True},
            )
        )
    for code in REASON_CODES:
        fixtures.append(_adversarial_fixture_for_code(code))
    return sorted(fixtures, key=lambda row: row["fixture_id"])

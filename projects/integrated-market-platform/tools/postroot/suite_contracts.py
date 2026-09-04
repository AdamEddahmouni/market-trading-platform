"""Closed contract declarations for the postroot acceptance suite."""

from __future__ import annotations

from typing import Any


def contract(
    contract_id: str,
    field_rules: dict[str, object],
    validation_rules: list[str],
) -> dict[str, object]:
    return {
        "additional_properties": "REJECT",
        "contract_id": contract_id,
        "field_rules": field_rules,
        "required_fields": sorted(field_rules),
        "schema_version": "1.0.0",
        "validation_rules": validation_rules,
    }


_SHA256 = {"type": "string", "format": "SHA256"}
_NONEMPTY = {"type": "string", "format": "NONEMPTY"}
_LOGICAL_ID = {"type": "string", "format": "LOGICAL_ID"}
_TIMESTAMP = {"type": "string", "format": "TIMESTAMP"}


def _finding_item() -> dict[str, object]:
    return {
        "additional_properties": "REJECT",
        "field_rules": {
            "affected_assertion_ids": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "affected_logical_ids": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "evidence_refs": {
                "item_rule": {
                    "additional_properties": "REJECT",
                    "field_rules": {"logical_id": _LOGICAL_ID, "sha256": _SHA256},
                    "required_fields": ["logical_id", "sha256"],
                    "type": "object",
                },
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "finding_id": _NONEMPTY,
            "finding_type": _NONEMPTY,
            "reason": _NONEMPTY,
            "recommended_resolution": _NONEMPTY,
        },
        "required_fields": [
            "affected_assertion_ids",
            "affected_logical_ids",
            "evidence_refs",
            "finding_id",
            "finding_type",
            "reason",
            "recommended_resolution",
        ],
        "type": "object",
    }


def _reproduction_item() -> dict[str, object]:
    return {
        "additional_properties": "REJECT",
        "field_rules": {
            "evidence_refs": {
                "item_rule": {
                    "additional_properties": "REJECT",
                    "field_rules": {"logical_id": _LOGICAL_ID, "sha256": _SHA256},
                    "required_fields": ["logical_id", "sha256"],
                    "type": "object",
                },
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "expected": _NONEMPTY,
            "observed": _NONEMPTY,
            "outcome": {
                "enum": ["BLOCKED", "FAIL", "PASS"],
                "type": "string",
            },
            "reproduction_id": _NONEMPTY,
            "subject_refs": {
                "item_rule": {
                    "additional_properties": "REJECT",
                    "field_rules": {"logical_id": _LOGICAL_ID, "sha256": _SHA256},
                    "required_fields": ["logical_id", "sha256"],
                    "type": "object",
                },
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
        },
        "required_fields": [
            "evidence_refs",
            "expected",
            "observed",
            "outcome",
            "reproduction_id",
            "subject_refs",
        ],
        "type": "object",
    }


def build_contract_schemas() -> list[dict[str, object]]:
    review_output = contract(
        "phase0.ai_review_output.contract",
        {
            "candidate_evidence_root": _SHA256,
            "coverage_assertion_ids": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "coverage_logical_ids": {
                "item_rule": _LOGICAL_ID,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "findings": {
                "item_rule": _finding_item(),
                "ordering": "SEQUENCE",
                "type": "array",
            },
            "limitations": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "recommended_candidate_outcome": {
                "enum": ["BLOCKED", "FAIL", "PASS"],
                "type": "string",
            },
            "reproduction_results": {
                "item_rule": _reproduction_item(),
                "ordering": "SEQUENCE",
                "type": "array",
            },
            "review_class": {
                "enum": [
                    "ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT",
                    "INTEGRITY_AND_REPRODUCTION_AUDIT",
                ],
                "type": "string",
            },
            "summary": _NONEMPTY,
        },
        ["review_output_hash equals canonical bytes without hash field"],
    )

    review_run = contract(
        "phase0.ai_review_run.contract",
        {
            "candidate_evidence_root": _SHA256,
            "canonical_configuration_hash": _SHA256,
            "completed_at": _TIMESTAMP,
            "coverage_assertion_ids": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "coverage_logical_ids": {
                "item_rule": _LOGICAL_ID,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "disqualification_reason_codes": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "eligibility_result": {
                "additional_properties": "REJECT",
                "field_rules": {
                    "status": {"enum": ["ELIGIBLE", "INELIGIBLE"], "type": "string"},
                    "violation_count": {"type": "integer"},
                    "violations": {
                        "item_rule": {
                            "additional_properties": "REJECT",
                            "field_rules": {
                                "evidence_refs": {
                                    "item_rule": _NONEMPTY,
                                    "ordering": "LEXICOGRAPHIC_UNIQUE",
                                    "type": "array",
                                },
                                "reason_code": _NONEMPTY,
                                "rule_ref": _NONEMPTY,
                            },
                            "required_fields": [
                                "evidence_refs",
                                "reason_code",
                                "rule_ref",
                            ],
                            "type": "object",
                        },
                        "ordering": "SEQUENCE",
                        "type": "array",
                    },
                },
                "required_fields": ["status", "violation_count", "violations"],
                "type": "object",
            },
            "findings": {
                "item_rule": _finding_item(),
                "ordering": "SEQUENCE",
                "type": "array",
            },
            "input_artifact_hashes": {
                "item_rule": {
                    "additional_properties": "REJECT",
                    "field_rules": {"logical_id": _LOGICAL_ID, "sha256": _SHA256},
                    "required_fields": ["logical_id", "sha256"],
                    "type": "object",
                },
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "model_service_and_declared_version": {
                "additional_properties": "REJECT",
                "field_rules": {
                    "declared_model_version": _NONEMPTY,
                    "model_service": _NONEMPTY,
                },
                "required_fields": ["declared_model_version", "model_service"],
                "type": "object",
            },
            "plan_hash": _SHA256,
            "qualification_state": {
                "enum": ["NON_QUALIFYING", "QUALIFYING"],
                "type": "string",
            },
            "recommended_candidate_outcome": {
                "enum": ["BLOCKED", "FAIL", "PASS"],
                "type": "string",
            },
            "registry_hash": _SHA256,
            "reproduction_results": {
                "item_rule": _reproduction_item(),
                "ordering": "SEQUENCE",
                "type": "array",
            },
            "review_class": {
                "enum": [
                    "ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT",
                    "INTEGRITY_AND_REPRODUCTION_AUDIT",
                ],
                "type": "string",
            },
            "review_output_hash": _SHA256,
            "review_procedure_id_and_hash": {
                "additional_properties": "REJECT",
                "field_rules": {"procedure_id": _NONEMPTY, "sha256": _SHA256},
                "required_fields": ["procedure_id", "sha256"],
                "type": "object",
            },
            "review_run_id": _SHA256,
            "run_id": _SHA256,
            "runtime_and_tool_versions": {
                "item_rule": {
                    "additional_properties": "REJECT",
                    "field_rules": {
                        "component_id": _NONEMPTY,
                        "declared_version": _NONEMPTY,
                        "runtime_context": _NONEMPTY,
                    },
                    "required_fields": [
                        "component_id",
                        "declared_version",
                        "runtime_context",
                    ],
                    "type": "object",
                },
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "specification_hash": _SHA256,
            "started_at": _TIMESTAMP,
            "terminal_state": {
                "enum": ["COMPLETE", "DISQUALIFIED", "FAILED"],
                "type": "string",
            },
        },
        [
            "review_run_id is content-derived with only review_run_id omitted",
            "integrity run input_artifact_hashes must bind suite and suite approval",
        ],
    )

    coverage = contract(
        "phase0.ai_review_coverage.contract",
        {
            "candidate_evidence_root": _SHA256,
            "coverage_assertion_ids_union": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "coverage_logical_ids_union": {
                "item_rule": _LOGICAL_ID,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "disqualification_reason_codes": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "duplicate_identity_results": {
                "additional_properties": "REJECT",
                "field_rules": {
                    "duplicate_assertion_ids": {
                        "item_rule": _NONEMPTY,
                        "ordering": "LEXICOGRAPHIC_UNIQUE",
                        "type": "array",
                    },
                    "duplicate_logical_ids": {
                        "item_rule": _LOGICAL_ID,
                        "ordering": "LEXICOGRAPHIC_UNIQUE",
                        "type": "array",
                    },
                    "duplicate_review_run_ids": {
                        "item_rule": _SHA256,
                        "ordering": "LEXICOGRAPHIC_UNIQUE",
                        "type": "array",
                    },
                    "has_duplicates": {"type": "boolean"},
                },
                "required_fields": [
                    "duplicate_assertion_ids",
                    "duplicate_logical_ids",
                    "duplicate_review_run_ids",
                    "has_duplicates",
                ],
                "type": "object",
            },
            "expected_assertion_ids": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "expected_logical_ids": {
                "item_rule": _LOGICAL_ID,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "extra_assertion_ids": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "extra_logical_ids": {
                "item_rule": _LOGICAL_ID,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "invalid_review_run_ids": {
                "item_rule": _SHA256,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "invalid_selected_run_reason_codes": {
                "item_rule": {
                    "additional_properties": "REJECT",
                    "field_rules": {
                        "reason_code": _NONEMPTY,
                        "review_run_id_observed": _NONEMPTY,
                    },
                    "required_fields": ["reason_code", "review_run_id_observed"],
                    "type": "object",
                },
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "isolation_check_results": {
                "item_rule": {
                    "additional_properties": "REJECT",
                    "field_rules": {
                        "check_id": _NONEMPTY,
                        "evidence_refs": {
                            "item_rule": _NONEMPTY,
                            "ordering": "LEXICOGRAPHIC_UNIQUE",
                            "type": "array",
                        },
                        "observed": _NONEMPTY,
                        "result": {
                            "enum": ["BLOCKED", "FAIL", "PASS"],
                            "type": "string",
                        },
                        "review_run_id": _SHA256,
                    },
                    "required_fields": [
                        "check_id",
                        "evidence_refs",
                        "observed",
                        "result",
                        "review_run_id",
                    ],
                    "type": "object",
                },
                "ordering": "SEQUENCE",
                "type": "array",
            },
            "missing_assertion_ids": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "missing_logical_ids": {
                "item_rule": _LOGICAL_ID,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "qualification_status": {
                "enum": ["BLOCKED", "INVALID", "QUALIFIED"],
                "type": "string",
            },
            "qualifying_review_run_ids": {
                "item_rule": _SHA256,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "registry_hash": _SHA256,
            "review_class_assignments": {
                "item_rule": {
                    "additional_properties": "REJECT",
                    "field_rules": {
                        "review_class": _NONEMPTY,
                        "review_run_id": _SHA256,
                    },
                    "required_fields": ["review_class", "review_run_id"],
                    "type": "object",
                },
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "review_procedure_id_and_hash": {
                "additional_properties": "REJECT",
                "field_rules": {"procedure_id": _NONEMPTY, "sha256": _SHA256},
                "required_fields": ["procedure_id", "sha256"],
                "type": "object",
            },
            "selected_review_run_ids": {
                "item_rule": _SHA256,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
        },
        [
            "QUALIFIED requires exactly two distinct qualifying runs",
            "integrity run must bind suite logical IDs in input_artifact_hashes",
        ],
    )

    preapproval = contract(
        "phase0.preapproval_reviewer_eligibility.contract",
        {
            "acknowledgements": {
                "item_rule": {
                    "additional_properties": "REJECT",
                    "field_rules": {
                        "acknowledgement_id": _NONEMPTY,
                        "statement": _NONEMPTY,
                    },
                    "required_fields": ["acknowledgement_id", "statement"],
                    "type": "object",
                },
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "artifact_type": _NONEMPTY,
            "authority_bindings": {
                "item_rule": {
                    "additional_properties": "REJECT",
                    "field_rules": {
                        "logical_id": _LOGICAL_ID,
                        "logical_path": _NONEMPTY,
                        "sha256": _SHA256,
                    },
                    "required_fields": ["logical_id", "logical_path", "sha256"],
                    "type": "object",
                },
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "check_results": {
                "item_rule": {
                    "additional_properties": "REJECT",
                    "field_rules": {
                        "check_id": _NONEMPTY,
                        "evidence_refs": {
                            "item_rule": _NONEMPTY,
                            "ordering": "LEXICOGRAPHIC_UNIQUE",
                            "type": "array",
                        },
                        "expected_condition": _NONEMPTY,
                        "observed_condition": _NONEMPTY,
                        "reason_codes": {
                            "item_rule": _NONEMPTY,
                            "ordering": "LEXICOGRAPHIC_UNIQUE",
                            "type": "array",
                        },
                        "status": {
                            "enum": ["BLOCKED", "FAIL", "PASS"],
                            "type": "string",
                        },
                    },
                    "required_fields": [
                        "check_id",
                        "evidence_refs",
                        "expected_condition",
                        "observed_condition",
                        "reason_codes",
                        "status",
                    ],
                    "type": "object",
                },
                "ordering": "SEQUENCE",
                "type": "array",
            },
            "documented_on": _NONEMPTY,
            "effectivity": {
                "additional_properties": "REJECT",
                "field_rules": {
                    "current_effectivity": _NONEMPTY,
                },
                "required_fields": ["current_effectivity"],
                "type": "object",
            },
            "eligibility_determination": {
                "additional_properties": "REJECT",
                "field_rules": {
                    "blocked_check_count": {"type": "integer"},
                    "failed_check_count": {"type": "integer"},
                    "passed_check_count": {"type": "integer"},
                    "required_check_count": {"type": "integer"},
                    "status": {
                        "enum": ["BLOCKED", "ELIGIBLE", "INELIGIBLE"],
                        "type": "string",
                    },
                    "violation_count": {"type": "integer"},
                    "violations": {
                        "item_rule": {
                            "additional_properties": "REJECT",
                            "field_rules": {
                                "check_id": _NONEMPTY,
                                "reason_code": _NONEMPTY,
                                "rule_ref": _NONEMPTY,
                            },
                            "required_fields": ["check_id", "reason_code", "rule_ref"],
                            "type": "object",
                        },
                        "ordering": "LEXICOGRAPHIC_UNIQUE",
                        "type": "array",
                    },
                },
                "required_fields": [
                    "blocked_check_count",
                    "failed_check_count",
                    "passed_check_count",
                    "required_check_count",
                    "status",
                    "violation_count",
                    "violations",
                ],
                "type": "object",
            },
            "governance_effect": {
                "additional_properties": "REJECT",
                "field_rules": {"gov002_current_status": _NONEMPTY},
                "required_fields": ["gov002_current_status"],
                "type": "object",
            },
            "logical_id": _LOGICAL_ID,
            "non_authorizations": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "record_status": _NONEMPTY,
            "schema_version": _NONEMPTY,
            "supersession": {
                "additional_properties": "REJECT",
                "field_rules": {"revision_rule": _NONEMPTY},
                "required_fields": ["revision_rule"],
                "type": "object",
            },
            "validation_contract": {
                "additional_properties": "REJECT",
                "field_rules": {
                    "check_id_order_required": {
                        "item_rule": _NONEMPTY,
                        "ordering": "SEQUENCE",
                        "type": "array",
                    },
                    "profile_id": _NONEMPTY,
                },
                "required_fields": ["check_id_order_required", "profile_id"],
                "type": "object",
            },
        },
        [
            "six checks in exact order",
            "ELIGIBLE requires zero violations and all checks PASS",
        ],
    )

    suite_approval = contract(
        "phase0.postroot_acceptance_contract_suite.approval.contract",
        {
            "approval_record_id": _SHA256,
            "approved_at": _TIMESTAMP,
            "approved_by_principal_id": _NONEMPTY,
            "approved_capacities": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "approved_logical_id": _LOGICAL_ID,
            "approved_sha256": _SHA256,
            "approval_scope": _NONEMPTY,
            "procedure_id": _NONEMPTY,
            "procedure_sha256": _SHA256,
            "status": {"enum": ["APPROVED", "REVOKED"], "type": "string"},
        },
        ["approval_record_id is content-derived with only approval_record_id omitted"],
    )

    approval_records = contract(
        "phase0.approval_records.contract",
        {
            "aggregate_approval_status": {
                "enum": ["BLOCKED", "FAIL", "PASS"],
                "type": "string",
            },
            "approval_records": {
                "item_rule": {
                    "additional_properties": "REJECT",
                    "field_rules": {
                        "approval_record_id": _SHA256,
                        "approved_at": _TIMESTAMP,
                        "approved_by_principal_id": _NONEMPTY,
                        "approved_capacities": {
                            "item_rule": _NONEMPTY,
                            "ordering": "LEXICOGRAPHIC_UNIQUE",
                            "type": "array",
                        },
                        "approved_logical_id": _LOGICAL_ID,
                        "approved_sha256": _SHA256,
                        "approval_scope": _NONEMPTY,
                        "status": {"enum": ["APPROVED", "REVOKED"], "type": "string"},
                    },
                    "required_fields": [
                        "approval_record_id",
                        "approved_at",
                        "approved_by_principal_id",
                        "approved_capacities",
                        "approved_logical_id",
                        "approved_sha256",
                        "approval_scope",
                        "status",
                    ],
                    "type": "object",
                },
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "assertion_run_hash": _SHA256,
            "candidate_evidence_root": _SHA256,
            "duplicate_capacities": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "extra_capacities": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "missing_capacities": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "observed_capacities": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "plan_hash": _SHA256,
            "procedure_id_and_hash": {
                "additional_properties": "REJECT",
                "field_rules": {"procedure_id": _NONEMPTY, "sha256": _SHA256},
                "required_fields": ["procedure_id", "sha256"],
                "type": "object",
            },
            "reason_codes": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "registry_hash": _SHA256,
            "required_capacities": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "specification_hash": _SHA256,
            "suite_id_and_hash": {
                "additional_properties": "REJECT",
                "field_rules": {"logical_id": _LOGICAL_ID, "sha256": _SHA256},
                "required_fields": ["logical_id", "sha256"],
                "type": "object",
            },
        },
        ["missing required approvals produce BLOCKED"],
    )

    acceptance_index = contract(
        "phase0.acceptance_index.contract",
        {
            "candidate_evidence_root": _SHA256,
            "index_members": {
                "item_rule": {
                    "additional_properties": "REJECT",
                    "field_rules": {
                        "byte_length": {"type": "integer"},
                        "logical_id": _LOGICAL_ID,
                        "media_type": _NONEMPTY,
                        "member_sha256": _SHA256,
                        "repository_relative_path": _NONEMPTY,
                        "root_id": _NONEMPTY,
                    },
                    "required_fields": [
                        "byte_length",
                        "logical_id",
                        "media_type",
                        "member_sha256",
                        "repository_relative_path",
                        "root_id",
                    ],
                    "type": "object",
                },
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "index_sha256": _SHA256,
            "logical_id": _LOGICAL_ID,
            "procedure_id_and_hash": {
                "additional_properties": "REJECT",
                "field_rules": {"procedure_id": _NONEMPTY, "sha256": _SHA256},
                "required_fields": ["procedure_id", "sha256"],
                "type": "object",
            },
            "root_hash": _SHA256,
            "root_id": _NONEMPTY,
            "schema_version": _NONEMPTY,
            "suite_id_and_hash": {
                "additional_properties": "REJECT",
                "field_rules": {"logical_id": _LOGICAL_ID, "sha256": _SHA256},
                "required_fields": ["logical_id", "sha256"],
                "type": "object",
            },
        },
        [
            "index_sha256 and root_hash are content-derived",
            "index never includes itself or final result",
        ],
    )

    final_result = contract(
        "phase0.final_acceptance_result.contract",
        {
            "assertion_aggregate_status": {
                "enum": ["BLOCKED", "FAIL", "PASS"],
                "type": "string",
            },
            "candidate_evidence_root": _SHA256,
            "completed_at": _TIMESTAMP,
            "final_result_id": _SHA256,
            "index_sha256": _SHA256,
            "logical_id": _LOGICAL_ID,
            "outcome": {"enum": ["BLOCKED", "FAIL", "PASS"], "type": "string"},
            "reason_codes": {
                "item_rule": _NONEMPTY,
                "ordering": "LEXICOGRAPHIC_UNIQUE",
                "type": "array",
            },
            "review_coverage_status": {
                "enum": ["BLOCKED", "INVALID", "QUALIFIED"],
                "type": "string",
            },
            "root_hash": _SHA256,
            "schema_version": _NONEMPTY,
            "suite_sha256": _SHA256,
        },
        [
            "final_result_id is content-derived",
            "FAIL precedes BLOCKED over PASS",
        ],
    )

    schemas = [
        acceptance_index,
        coverage,
        review_output,
        review_run,
        approval_records,
        final_result,
        preapproval,
        suite_approval,
    ]
    return schemas

from __future__ import annotations

from copy import deepcopy

from .acceptance_algorithms import (
    compute_index_hashes,
    expected_index_logical_ids,
    record_identity,
)
from .contract_core import canonical_bytes, sha256_bytes


PROCEDURE_ID = "AI-REVIEW-PROCESS-001"
PROCEDURE_SHA256 = "EAAA84B1D0D6FF4B6A90F36CC35F5D88E9D1EB63173A6BDE18D9C911E63C69A8"
PLAN_SHA256 = "EE22C688167F5016D7ED1953BB1DAE516BC6AB343655A7D96535C6605D37E904"
SPECIFICATION_SHA256 = "7C6AE5FC9037CA37D44CD1A2FAACD0CB821192920C46CF001541DCD2121FEB35"
SUITE_LOGICAL_ID = "phase0.postroot_acceptance_contract_suite"
SUITE_APPROVAL_LOGICAL_ID = "phase0.postroot_acceptance_contract_suite.approval"

REVIEW_CLASSES = [
    "ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT",
    "INTEGRITY_AND_REPRODUCTION_AUDIT",
]
OUTCOMES = ["BLOCKED", "FAIL", "PASS"]
PREELIGIBILITY_CHECK_IDS = [
    "PREELIG-ROLE-RESOLUTION-001",
    "PREELIG-PROCEDURE-DESIGNATION-001",
    "PREELIG-PROCEDURE-APPROVAL-001",
    "PREELIG-REVIEW-CONTROLS-001",
    "PREELIG-NONCIRCULARITY-001",
    "PREELIG-NO-FALSE-EVIDENCE-001",
]
ISOLATION_CHECK_IDS = [
    "CLASS_COMPLETENESS",
    "DECLARED_TOOLS",
    "DISTINCT_FRESH_CONTEXTS",
    "DISTINCT_REVIEW_RUN_IDS",
    "NO_AUTHORING_HISTORY",
    "NO_EXTERNAL_ACCESS",
    "READ_ONLY_GOVERNED_SUBJECT",
    "SANITIZED_INPUTS_AND_OUTPUTS",
]
DISQUALIFICATION_CODES = [
    "DISQ-AUTHORED-SUBJECT",
    "DISQ-AUTHORING-TRANSCRIPT",
    "DISQ-CONTEXT-NOT-FRESH",
    "DISQ-CREDENTIAL-OR-SENSITIVE-INPUT",
    "DISQ-GOVERNED-SUBJECT-MUTATION",
    "DISQ-HASH-OR-IDENTITY-MISMATCH",
    "DISQ-OUTCOME-MISMATCH",
    "DISQ-UNDECLARED-TOOL-OR-EXTERNAL-ACCESS",
    "DISQ-UNGOVERNED-EVIDENCE",
    "DISQ-WRONG-CANDIDATE-ROOT",
]

REASON_CODES = (
    "APPROVAL-CAPACITY-DUPLICATE",
    "APPROVAL-CAPACITY-EXTRA",
    "APPROVAL-CAPACITY-MISSING",
    "APPROVAL-HASH-BINDING-MISMATCH",
    "APPROVAL-IDENTITY-INVALID",
    "APPROVAL-NOT-EFFECTIVE",
    "APPROVAL-PRINCIPAL-MISMATCH",
    "APPROVAL-WAIVER-ATTEMPT",
    "BYTE-CANONICAL-MISMATCH",
    "BYTE-TRAILING-DATA",
    "BYTE-UTF8-BOM",
    "BYTE-UTF8-INVALID",
    "COVERAGE-CLASS-INVALID",
    "COVERAGE-DUPLICATE-IDENTITY",
    "COVERAGE-EXTRA-ID",
    "COVERAGE-ISOLATION-INVALID",
    "COVERAGE-MISSING-ID",
    "COVERAGE-SELECTION-CARDINALITY",
    "GATE-FINAL-RESULT-ID-MISMATCH",
    "GATE-OUTCOME-MISMATCH",
    "GATE-PRECEDENCE-MISMATCH",
    "HASH-CANDIDATE-ROOT-MISMATCH",
    "HASH-CONTENT-MISMATCH",
    "HASH-PROCEDURE-MISMATCH",
    "HASH-REGISTRY-MISMATCH",
    "HASH-REVIEW-OUTPUT-MISMATCH",
    "HASH-RUN-MISMATCH",
    "HASH-SUITE-MISMATCH",
    "ID-DUPLICATE-SEMANTIC-IDENTITY",
    "ID-LOGICAL-ID-INVALID",
    "ID-RECORD-ID-MISMATCH",
    "INDEX-ABSOLUTE-PATH",
    "INDEX-DUPLICATE-LOGICAL-ID",
    "INDEX-DUPLICATE-PATH",
    "INDEX-EXTRA-MEMBER",
    "INDEX-FINAL-RESULT-MEMBERSHIP",
    "INDEX-MEMBER-BYTE-LENGTH-MISMATCH",
    "INDEX-MEMBER-HASH-MISMATCH",
    "INDEX-MISSING-MEMBER",
    "INDEX-NONNORMALIZED-PATH",
    "INDEX-ROOT-HASH-MISMATCH",
    "INDEX-ROOT-ID-MISMATCH",
    "INDEX-SELF-MEMBERSHIP",
    "INDEX-SHA256-MISMATCH",
    "INDEX-SYMLINK-OR-REPARSE-ESCAPE",
    "JSON-DUPLICATE-KEY",
    "JSON-PARSE-INVALID",
    "REF-CONTRADICTORY-BINDING",
    "REF-UNRESOLVED",
    "REVIEW-AUTHORING-CONTEXT",
    "REVIEW-CLASS-MISSING",
    "REVIEW-DISQUALIFICATION-CODE-MISMATCH",
    "REVIEW-GOVERNED-SUBJECT-MUTATION",
    "REVIEW-OUTCOME-MISMATCH",
    "REVIEW-UNDECLARED-TOOL-OR-EXTERNAL-ACCESS",
    "SCHEMA-ARRAY-DUPLICATE",
    "SCHEMA-ARRAY-ORDER",
    "SCHEMA-ENUM-INVALID",
    "SCHEMA-FORMAT-INVALID",
    "SCHEMA-MISSING-REQUIRED-FIELD",
    "SCHEMA-TYPE-INVALID",
    "SCHEMA-UNDECLARED-FIELD",
)

PREELIGIBILITY_ALLOWED_FAILURES = {
    "PREELIG-NO-FALSE-EVIDENCE-001": [
        "FALSE_ACCEPTANCE_INDEX_CLAIM",
        "FALSE_AI_REVIEW_COVERAGE_CLAIM",
        "FALSE_AI_REVIEW_RUN_CLAIM",
        "FALSE_CANDIDATE_ROOT_CLAIM",
        "FALSE_FINAL_RESULT_CLAIM",
        "FALSE_FORMAL_APPROVAL_RECORD_CLAIM",
    ],
    "PREELIG-NONCIRCULARITY-001": [
        "POSTROOT_EVIDENCE_USED_FOR_PREAPPROVAL",
        "PREPOSTROOT_BOUNDARY_UNDEFINED",
        "REVIEW_EVIDENCE_LIFECYCLE_CIRCULAR",
    ],
    "PREELIG-PROCEDURE-APPROVAL-001": [
        "PROCEDURE_APPROVAL_ABSENT",
        "PROCEDURE_HASH_MISMATCH",
        "PROCEDURE_ID_MISMATCH",
    ],
    "PREELIG-PROCEDURE-DESIGNATION-001": [
        "INDEPENDENT_REVIEW_DESIGNATION_MISSING",
        "PROCEDURE_ID_DESIGNATION_MISMATCH",
        "SELF_REVIEW_MISREPRESENTED_AS_INDEPENDENT",
    ],
    "PREELIG-REVIEW-CONTROLS-001": [
        "CANDIDATE_ROOT_BINDING_CONTROL_MISSING",
        "COVERAGE_UNION_CONTROL_MISSING",
        "FRESH_CONTEXT_CONTROL_MISSING",
        "NON_AUTHORING_CONTROL_MISSING",
        "READ_ONLY_CONTROL_MISSING",
        "SANITIZATION_CONTROL_MISSING",
    ],
    "PREELIG-ROLE-RESOLUTION-001": [
        "PRINCIPAL_ID_MISMATCH",
        "REQUIRED_HUMAN_CAPACITY_UNRESOLVED",
        "ROLE_OVERLAP_DISCLOSURE_INCOMPLETE",
    ],
}

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


def string_rule(*, format_name: str | None = None, enum: list[object] | None = None) -> dict[str, object]:
    rule: dict[str, object] = {"type": "string"}
    if format_name is not None:
        rule["format"] = format_name
    if enum is not None:
        rule["enum"] = enum
    return rule


def integer_rule() -> dict[str, object]:
    return {"type": "integer"}


def boolean_rule() -> dict[str, object]:
    return {"type": "boolean"}


def array_rule(
    item_rule: dict[str, object], *, ordering: str = "LEXICOGRAPHIC_UNIQUE"
) -> dict[str, object]:
    return {"item_rule": item_rule, "ordering": ordering, "type": "array"}


def object_rule(field_rules: dict[str, object]) -> dict[str, object]:
    return {
        "additional_properties": "REJECT",
        "field_rules": field_rules,
        "required_fields": sorted(field_rules),
        "type": "object",
    }


def contract(
    contract_id: str,
    field_rules: dict[str, object],
    validation_rules: list[object],
) -> dict[str, object]:
    return {
        "additional_properties": "REJECT",
        "contract_id": contract_id,
        "field_rules": field_rules,
        "required_fields": sorted(field_rules),
        "schema_version": "1.0.0",
        "validation_rules": validation_rules,
    }


def _hash_rule() -> dict[str, object]:
    return string_rule(format_name="SHA256")


def _nonempty_array() -> dict[str, object]:
    return array_rule(string_rule(format_name="NONEMPTY"))


def _hash_binding_rule(id_field: str = "logical_id") -> dict[str, object]:
    return object_rule({id_field: string_rule(format_name="LOGICAL_ID"), "sha256": _hash_rule()})


def _evidence_ref_rule() -> dict[str, object]:
    return _hash_binding_rule()


def _finding_rule() -> dict[str, object]:
    return object_rule(
        {
            "affected_assertion_ids": _nonempty_array(),
            "affected_logical_ids": _nonempty_array(),
            "evidence_refs": array_rule(_evidence_ref_rule()),
            "finding_id": string_rule(format_name="NONEMPTY"),
            "finding_status": string_rule(enum=["NOT_APPLICABLE", "OPEN", "RESOLVED"]),
            "finding_type": string_rule(
                enum=[
                    "EVIDENCE_CONTRADICTION",
                    "INVALID_APPROVAL_REVIEW_HASH_IDENTITY_OR_INDEX",
                    "MISSING_REQUIRED_EVIDENCE",
                    "NON_MATERIAL_OBSERVATION",
                    "PROCEDURE_OR_ELIGIBILITY_VIOLATION",
                    "UNRESOLVED_MATERIAL_UNCERTAINTY",
                ]
            ),
            "materiality": string_rule(enum=["MATERIAL", "NON_MATERIAL"]),
            "reason": string_rule(format_name="NONEMPTY"),
            "recommended_resolution": string_rule(format_name="NONEMPTY"),
        }
    )


def _reproduction_rule() -> dict[str, object]:
    return object_rule(
        {
            "evidence_refs": _nonempty_array(),
            "expected": string_rule(format_name="NONEMPTY"),
            "observed": string_rule(format_name="NONEMPTY"),
            "outcome": string_rule(enum=OUTCOMES),
            "reproduction_id": string_rule(format_name="NONEMPTY"),
            "subject_refs": _nonempty_array(),
        }
    )


def _review_output_fields() -> dict[str, object]:
    return {
        "candidate_evidence_root": _hash_rule(),
        "coverage_assertion_ids": _nonempty_array(),
        "coverage_logical_ids": _nonempty_array(),
        "findings": array_rule(_finding_rule(), ordering="SEQUENCE"),
        "limitations": _nonempty_array(),
        "recommended_candidate_outcome": string_rule(enum=OUTCOMES),
        "reproduction_results": array_rule(_reproduction_rule(), ordering="SEQUENCE"),
        "review_class": string_rule(enum=REVIEW_CLASSES),
        "summary": string_rule(format_name="NONEMPTY"),
    }


def _review_output_contract() -> dict[str, object]:
    return contract(
        "phase0.ai_review_output.contract",
        _review_output_fields(),
        [
            "The output contains no review_output_hash field.",
            "Findings are sorted by finding_id and reproductions by reproduction_id.",
            "The recommended outcome is independently derived with FAIL over BLOCKED over PASS precedence.",
        ],
    )


def _review_run_contract() -> dict[str, object]:
    eligibility_violation = object_rule(
        {
            "evidence_refs": _nonempty_array(),
            "reason_code": string_rule(enum=DISQUALIFICATION_CODES),
            "rule_ref": string_rule(format_name="NONEMPTY"),
        }
    )
    fields = _review_output_fields()
    fields.update(
        {
            "canonical_configuration_hash": _hash_rule(),
            "completed_at": string_rule(format_name="TIMESTAMP"),
            "disqualification_reason_codes": array_rule(
                string_rule(enum=DISQUALIFICATION_CODES)
            ),
            "eligibility_result": object_rule(
                {
                    "status": string_rule(enum=["ELIGIBLE", "INELIGIBLE"]),
                    "violation_count": integer_rule(),
                    "violations": array_rule(eligibility_violation, ordering="SEQUENCE"),
                }
            ),
            "input_artifact_hashes": array_rule(_hash_binding_rule()),
            "model_service_and_declared_version": object_rule(
                {
                    "declared_model_version": string_rule(format_name="NONEMPTY"),
                    "model_service": string_rule(format_name="NONEMPTY"),
                }
            ),
            "plan_hash": _hash_rule(),
            "qualification_state": string_rule(enum=["NON_QUALIFYING", "QUALIFYING"]),
            "registry_hash": _hash_rule(),
            "review_output_hash": _hash_rule(),
            "review_procedure_id_and_hash": object_rule(
                {"procedure_id": string_rule(enum=[PROCEDURE_ID]), "sha256": _hash_rule()}
            ),
            "review_run_id": _hash_rule(),
            "run_id": _hash_rule(),
            "runtime_and_tool_versions": array_rule(
                object_rule(
                    {
                        "component_id": string_rule(format_name="NONEMPTY"),
                        "declared_version": string_rule(format_name="NONEMPTY"),
                        "runtime_context": string_rule(format_name="NONEMPTY"),
                    }
                )
            ),
            "specification_hash": _hash_rule(),
            "started_at": string_rule(format_name="TIMESTAMP"),
            "terminal_state": string_rule(enum=["COMPLETE", "DISQUALIFIED", "FAILED"]),
        }
    )
    fields.pop("limitations")
    fields.pop("summary")
    return contract(
        "phase0.ai_review_run.contract",
        fields,
        [
            "review_run_id is the content identity with only review_run_id omitted.",
            "review_output_hash binds the exact canonical review output bytes.",
            "completed_at does not precede started_at.",
            "The integrity run input_artifact_hashes includes the exact suite and suite-approval logical IDs and hashes.",
            "Terminal state, eligibility, disqualification reasons, qualification state, and recommendation are mutually consistent.",
        ],
    )


def _coverage_contract() -> dict[str, object]:
    id_array = _nonempty_array()
    invalid_reason_values = [
        "COV-CLASS-INVALID",
        "COV-DISQUALIFICATION-CODES-MISSING-OR-MALFORMED",
        "COV-DUPLICATE-IDENTITY",
        "COV-EXTRA-ID",
        "COV-HASH-OR-IDENTITY-INVALID",
        "COV-ISOLATION-INVALID",
        "COV-RECORD-SHAPE-INVALID",
        "COV-SELECTION-CARDINALITY",
        "COV-UNDECLARED-FIELD",
    ]
    fields = {
        "candidate_evidence_root": _hash_rule(),
        "coverage_assertion_ids_union": deepcopy(id_array),
        "coverage_logical_ids_union": deepcopy(id_array),
        "disqualification_reason_codes": array_rule(string_rule(enum=DISQUALIFICATION_CODES)),
        "duplicate_identity_results": object_rule(
            {
                "duplicate_assertion_ids": deepcopy(id_array),
                "duplicate_logical_ids": deepcopy(id_array),
                "duplicate_review_run_ids": deepcopy(id_array),
                "has_duplicates": boolean_rule(),
            }
        ),
        "expected_assertion_ids": deepcopy(id_array),
        "expected_logical_ids": deepcopy(id_array),
        "extra_assertion_ids": deepcopy(id_array),
        "extra_logical_ids": deepcopy(id_array),
        "invalid_review_run_ids": deepcopy(id_array),
        "invalid_selected_run_reason_codes": array_rule(
            object_rule(
                {
                    "reason_code": string_rule(enum=invalid_reason_values),
                    "review_run_id_observed": string_rule(format_name="NONEMPTY"),
                }
            ),
            ordering="SEQUENCE",
        ),
        "isolation_check_results": array_rule(
            object_rule(
                {
                    "check_id": string_rule(enum=ISOLATION_CHECK_IDS),
                    "evidence_refs": deepcopy(id_array),
                    "observed": string_rule(format_name="NONEMPTY"),
                    "result": string_rule(enum=OUTCOMES),
                    "review_run_id": string_rule(format_name="NONEMPTY"),
                }
            ),
            ordering="SEQUENCE",
        ),
        "missing_assertion_ids": deepcopy(id_array),
        "missing_logical_ids": deepcopy(id_array),
        "qualification_status": string_rule(enum=["BLOCKED", "INVALID", "QUALIFIED"]),
        "qualifying_review_run_ids": deepcopy(id_array),
        "registry_hash": _hash_rule(),
        "review_class_assignments": array_rule(
            object_rule(
                {
                    "review_class": string_rule(
                        enum=REVIEW_CLASSES
                        + ["DUPLICATE_REVIEW_RUN_ID_RECORDS", "MISSING_OR_INVALID_REVIEW_CLASS"]
                    ),
                    "review_run_id": string_rule(format_name="NONEMPTY"),
                }
            ),
            ordering="SEQUENCE",
        ),
        "review_procedure_id_and_hash": object_rule(
            {"procedure_id": string_rule(enum=[PROCEDURE_ID]), "sha256": _hash_rule()}
        ),
        "selected_review_run_ids": deepcopy(id_array),
    }
    return contract(
        "phase0.ai_review_coverage.contract",
        fields,
        [
            {"required_review_classes": REVIEW_CLASSES},
            {"required_isolation_check_ids": ISOLATION_CHECK_IDS},
            {"selected_qualifying_run_count": 2},
            "QUALIFIED requires exact candidate, procedure, registry, logical-ID, and assertion-ID unions with no duplicates, extras, omissions, invalid records, or isolation failures.",
            "The selected integrity run binds the suite and suite approval through input_artifact_hashes; coverage adds no suite field.",
            "Missing class evidence is BLOCKED; a selected malformed or nonqualifying record is INVALID.",
        ],
    )


def _preeligibility_contract() -> dict[str, object]:
    check_result = object_rule(
        {
            "check_id": string_rule(enum=PREELIGIBILITY_CHECK_IDS),
            "evidence_refs": _nonempty_array(),
            "expected_condition": string_rule(format_name="NONEMPTY"),
            "observed_condition": string_rule(format_name="NONEMPTY"),
            "reason_codes": _nonempty_array(),
            "status": string_rule(enum=["BLOCKED", "FAIL", "PASS"]),
        }
    )
    violation = object_rule(
        {
            "check_id": string_rule(enum=PREELIGIBILITY_CHECK_IDS),
            "reason_code": string_rule(format_name="NONEMPTY"),
            "rule_ref": string_rule(format_name="NONEMPTY"),
        }
    )
    acknowledgement = object_rule(
        {
            "acknowledgement_id": string_rule(format_name="NONEMPTY"),
            "statement": string_rule(format_name="NONEMPTY"),
        }
    )
    authority = object_rule(
        {
            "approval_basis": string_rule(format_name="NONEMPTY"),
            "effectivity_state": string_rule(format_name="NONEMPTY"),
            "logical_id": string_rule(format_name="LOGICAL_ID"),
            "logical_path": string_rule(format_name="NONEMPTY"),
            "sha256": _hash_rule(),
        }
    )
    fields = {
        "acknowledgements": array_rule(acknowledgement, ordering="SEQUENCE"),
        "artifact_type": string_rule(format_name="NONEMPTY"),
        "authority_bindings": array_rule(authority, ordering="SEQUENCE"),
        "check_results": array_rule(check_result, ordering="SEQUENCE"),
        "documented_on": string_rule(format_name="NONEMPTY"),
        "effectivity": object_rule(
            {
                "activation_condition": string_rule(format_name="NONEMPTY"),
                "approval_event_state": string_rule(format_name="NONEMPTY"),
                "approval_must_bind": _nonempty_array(),
                "current_effectivity": string_rule(format_name="NONEMPTY"),
                "determination_rule": string_rule(format_name="NONEMPTY"),
                "effective_from": string_rule(format_name="NONEMPTY"),
                "effective_until": string_rule(format_name="NONEMPTY"),
                "self_hash_rule": string_rule(format_name="NONEMPTY"),
            }
        ),
        "eligibility_determination": object_rule(
            {
                "blocked_check_count": integer_rule(),
                "failed_check_count": integer_rule(),
                "passed_check_count": integer_rule(),
                "required_check_count": integer_rule(),
                "status": string_rule(enum=["BLOCKED", "ELIGIBLE", "INELIGIBLE"]),
                "violation_count": integer_rule(),
                "violations": array_rule(violation, ordering="SEQUENCE"),
            }
        ),
        "governance_effect": object_rule(
            {
                "candidate_root_effect": string_rule(format_name="NONEMPTY"),
                "gov002_current_status": string_rule(format_name="NONEMPTY"),
                "gov002_reassessment_rule": string_rule(format_name="NONEMPTY"),
                "implementation_authority": string_rule(format_name="NONEMPTY"),
                "postroot_evidence_rule": string_rule(format_name="NONEMPTY"),
                "result_scope": string_rule(format_name="NONEMPTY"),
            }
        ),
        "logical_id": string_rule(enum=["phase0.preapproval_reviewer_eligibility"]),
        "non_authorizations": _nonempty_array(),
        "record_status": string_rule(format_name="NONEMPTY"),
        "schema_version": string_rule(enum=["1.0.0"]),
        "supersession": object_rule(
            {
                "revision_rule": string_rule(format_name="NONEMPTY"),
                "superseded_by": {"type": "null"},
                "supersedes": _nonempty_array(),
            }
        ),
        "validation_contract": object_rule(
            {
                "additional_property_rule": string_rule(format_name="NONEMPTY"),
                "aggregate_rule": string_rule(format_name="NONEMPTY"),
                "allowed_blocked_reason_codes": _nonempty_array(),
                "allowed_fail_reason_codes_by_check": object_rule(
                    {check_id: _nonempty_array() for check_id in PREELIGIBILITY_CHECK_IDS}
                ),
                "array_ordering_rule": string_rule(format_name="NONEMPTY"),
                "authority_hash_rule": string_rule(format_name="NONEMPTY"),
                "check_id_order_required": array_rule(
                    string_rule(enum=PREELIGIBILITY_CHECK_IDS), ordering="SEQUENCE"
                ),
                "check_status_values": _nonempty_array(),
                "count_consistency_rule": string_rule(format_name="NONEMPTY"),
                "duplicate_key_rule": string_rule(format_name="NONEMPTY"),
                "eligibility_status_values": _nonempty_array(),
                "encoding": string_rule(format_name="NONEMPTY"),
                "evidence_resolution_rule": string_rule(format_name="NONEMPTY"),
                "line_endings": string_rule(format_name="NONEMPTY"),
                "object_key_order_rule": string_rule(format_name="NONEMPTY"),
                "profile_id": string_rule(format_name="NONEMPTY"),
                "reason_code_rule": string_rule(format_name="NONEMPTY"),
                "required_top_level_fields": _nonempty_array(),
                "trailing_newline": string_rule(format_name="NONEMPTY"),
            }
        ),
    }
    return contract(
        "phase0.preapproval_reviewer_eligibility.contract",
        fields,
        [
            {"check_id_order_required": PREELIGIBILITY_CHECK_IDS},
            {"required_check_count": 6},
            {"allowed_blocked_reason_codes": ["REQUIRED_EVIDENCE_UNAVAILABLE"]},
            "Counts equal observed check statuses, sum to six, and violation_count equals violations length.",
            "FAIL reason codes are scoped to the exact check registry; PASS has none; BLOCKED uses only REQUIRED_EVIDENCE_UNAVAILABLE.",
            "Every evidence reference resolves within an exact authority binding and no postroot artifact is an input.",
            "Effectivity requires external attributable exact-hash principal approval and cannot be self-proved.",
        ],
    )


def _suite_approval_contract() -> dict[str, object]:
    fields = {
        "approval_record_id": _hash_rule(),
        "approved_at": string_rule(format_name="TIMESTAMP"),
        "approved_by_principal_id": string_rule(enum=["PROJECT-PRINCIPAL-001"]),
        "approved_capacities": array_rule(
            string_rule(enum=["PROJECT_OWNER", "RELEASE_OWNER"])
        ),
        "approved_logical_id": string_rule(enum=[SUITE_LOGICAL_ID]),
        "approved_sha256": _hash_rule(),
        "approval_scope": string_rule(enum=["INTEGRITY_REVIEW_COMPANION_INPUT_ONLY"]),
        "procedure_id": string_rule(enum=[PROCEDURE_ID]),
        "procedure_sha256": _hash_rule(),
        "status": string_rule(enum=["APPROVED", "REVOKED"]),
    }
    return contract(
        "phase0.postroot_acceptance_contract_suite.approval.contract",
        fields,
        [
            "approval_record_id is the content identity with only approval_record_id omitted.",
            "APPROVED binds the externally approved exact suite hash and the exact approved procedure hash.",
            "The record grants no candidate, review, coverage, index, final-result, or Phase 0 approval.",
        ],
    )


def _candidate_approval_contract() -> dict[str, object]:
    capacity_array = _nonempty_array()
    approval_record = object_rule(
        {
            "approval_record_id": _hash_rule(),
            "approval_scope": string_rule(format_name="NONEMPTY"),
            "approved_at": string_rule(format_name="TIMESTAMP"),
            "approved_by_principal_id": string_rule(enum=["PROJECT-PRINCIPAL-001"]),
            "candidate_evidence_root": _hash_rule(),
            "capacities": deepcopy(capacity_array),
            "status": string_rule(enum=["APPROVED", "REVOKED"]),
        }
    )
    fields = {
        "approval_records": array_rule(approval_record),
        "assertion_run_hash": _hash_rule(),
        "candidate_evidence_root": _hash_rule(),
        "duplicate_capacities": deepcopy(capacity_array),
        "extra_capacities": deepcopy(capacity_array),
        "logical_id": string_rule(enum=["phase0.approval_records"]),
        "missing_capacities": deepcopy(capacity_array),
        "observed_capacities": deepcopy(capacity_array),
        "plan_hash": _hash_rule(),
        "procedure_hash": _hash_rule(),
        "reason_codes": _nonempty_array(),
        "registry_hash": _hash_rule(),
        "required_capacities": deepcopy(capacity_array),
        "schema_version": string_rule(enum=["1.0.0"]),
        "specification_hash": _hash_rule(),
        "status": string_rule(enum=["BLOCKED", "FAIL", "PASS"]),
        "suite_sha256": _hash_rule(),
    }
    return contract(
        "phase0.approval_records.contract",
        fields,
        [
            "Every approval identity and candidate, plan, specification, procedure, suite, registry, and assertion-run hash is exact.",
            "Observed, missing, extra, and duplicate capacities are exact recomputations from attributable records.",
            "Missing required approvals are BLOCKED; any selected invalid approval is FAIL.",
            "Approvals cannot waive an assertion or review outcome.",
        ],
    )


def _acceptance_index_contract() -> dict[str, object]:
    member = object_rule(
        {
            "byte_length": integer_rule(),
            "logical_id": string_rule(format_name="LOGICAL_ID"),
            "media_type": string_rule(format_name="NONEMPTY"),
            "member_sha256": _hash_rule(),
            "repository_relative_path": string_rule(format_name="NONEMPTY"),
            "root_id": string_rule(format_name="NONEMPTY"),
        }
    )
    fields = {
        "candidate_evidence_root": _hash_rule(),
        "index_members": array_rule(member, ordering="SEQUENCE"),
        "index_sha256": _hash_rule(),
        "logical_id": string_rule(enum=["phase0.acceptance_index"]),
        "procedure_id_and_hash": object_rule(
            {"procedure_id": string_rule(enum=[PROCEDURE_ID]), "sha256": _hash_rule()}
        ),
        "root_hash": _hash_rule(),
        "root_id": string_rule(format_name="NONEMPTY"),
        "schema_version": string_rule(enum=["1.0.0"]),
        "suite_id_and_hash": object_rule(
            {"logical_id": string_rule(enum=[SUITE_LOGICAL_ID]), "sha256": _hash_rule()}
        ),
    }
    return contract(
        "phase0.acceptance_index.contract",
        fields,
        [
            "Index rows are sorted by logical_id then repository_relative_path and contain unique logical IDs and unique normalized repository-relative paths.",
            "The member set is the exact union of candidate tuple IDs and the six postroot member IDs.",
            "The index cannot map itself or phase0.final_acceptance_result.",
            "Every member resolves beneath the opaque root without symlink or reparse escape and matches byte length, media type, and SHA-256.",
            "index_sha256 hashes the provisional canonical index with index_sha256 and root_hash omitted.",
            "root_hash hashes exactly index_sha256 and the ordered logical-ID/member-SHA pairs.",
        ],
    )


def _final_result_contract() -> dict[str, object]:
    fields = {
        "assertion_aggregate_status": string_rule(enum=OUTCOMES),
        "candidate_evidence_root": _hash_rule(),
        "completed_at": string_rule(format_name="TIMESTAMP"),
        "final_result_id": _hash_rule(),
        "index_sha256": _hash_rule(),
        "logical_id": string_rule(enum=["phase0.final_acceptance_result"]),
        "outcome": string_rule(enum=OUTCOMES),
        "reason_codes": _nonempty_array(),
        "review_coverage_status": string_rule(enum=["BLOCKED", "INVALID", "QUALIFIED"]),
        "root_hash": _hash_rule(),
        "schema_version": string_rule(enum=["1.0.0"]),
        "suite_sha256": _hash_rule(),
    }
    return contract(
        "phase0.final_acceptance_result.contract",
        fields,
        [
            "final_result_id is the content identity with only final_result_id omitted.",
            "The completed acceptance index verifies before final result derivation and the final result is not an index member.",
            "Demonstrable invalidity yields FAIL before true absence yields BLOCKED; otherwise complete passing evidence yields PASS.",
        ],
    )


def build_contract_schemas() -> list[dict[str, object]]:
    contracts = [
        _acceptance_index_contract(),
        _coverage_contract(),
        _review_output_contract(),
        _review_run_contract(),
        _candidate_approval_contract(),
        _final_result_contract(),
        _preeligibility_contract(),
        _suite_approval_contract(),
    ]
    return sorted(contracts, key=lambda row: str(row["contract_id"]))


REASON_DESCRIPTIONS = {
    "APPROVAL-CAPACITY-DUPLICATE": "A required approval capacity appears more than once.",
    "APPROVAL-CAPACITY-EXTRA": "An approval record declares a capacity outside the required set.",
    "APPROVAL-CAPACITY-MISSING": "A required approval capacity is absent from the bundle.",
    "APPROVAL-HASH-BINDING-MISMATCH": "An approval record binds the wrong governed hash.",
    "APPROVAL-IDENTITY-INVALID": "An approval record identity does not recompute from its content.",
    "APPROVAL-NOT-EFFECTIVE": "A required approval is not yet effective.",
    "APPROVAL-PRINCIPAL-MISMATCH": "An approval principal does not match the required principal.",
    "APPROVAL-WAIVER-ATTEMPT": "An approval attempts to waive a mandatory failure or blocked outcome.",
    "BYTE-CANONICAL-MISMATCH": "Bytes are not canonical JSON under the suite profile.",
    "BYTE-TRAILING-DATA": "Trailing bytes follow the JSON value.",
    "BYTE-UTF8-BOM": "A UTF-8 byte-order mark prefixes the artifact bytes.",
    "BYTE-UTF8-INVALID": "The artifact bytes are not valid UTF-8.",
    "COVERAGE-CLASS-INVALID": "A selected run uses an invalid review class.",
    "COVERAGE-DUPLICATE-IDENTITY": "Coverage selects duplicate semantic identities.",
    "COVERAGE-EXTRA-ID": "Coverage reports an extra logical or assertion ID.",
    "COVERAGE-ISOLATION-INVALID": "A required isolation check does not pass.",
    "COVERAGE-MISSING-ID": "Coverage is missing a required logical or assertion ID.",
    "COVERAGE-SELECTION-CARDINALITY": "Coverage selects the wrong number of qualifying runs.",
    "GATE-FINAL-RESULT-ID-MISMATCH": "The final result identity does not recompute.",
    "GATE-OUTCOME-MISMATCH": "The stored final outcome does not match the derived outcome.",
    "GATE-PRECEDENCE-MISMATCH": "Failure-over-blocked precedence was violated.",
    "HASH-CANDIDATE-ROOT-MISMATCH": "A declared candidate root does not match bound bytes.",
    "HASH-CONTENT-MISMATCH": "A declared content hash does not match recomputed bytes.",
    "HASH-PROCEDURE-MISMATCH": "A declared procedure hash does not match the approved hash.",
    "HASH-REGISTRY-MISMATCH": "A declared registry hash does not match bound bytes.",
    "HASH-REVIEW-OUTPUT-MISMATCH": "A review output hash does not match canonical output bytes.",
    "HASH-RUN-MISMATCH": "A review run identity does not match canonical run bytes.",
    "HASH-SUITE-MISMATCH": "A declared suite hash does not match bound suite bytes.",
    "ID-DUPLICATE-SEMANTIC-IDENTITY": "Two selected records share one semantic identity.",
    "ID-LOGICAL-ID-INVALID": "A logical ID violates the closed logical-ID format.",
    "ID-RECORD-ID-MISMATCH": "A record identity field does not match its content-derived identity.",
    "INDEX-ABSOLUTE-PATH": "An index member path is absolute rather than repository relative.",
    "INDEX-DUPLICATE-LOGICAL-ID": "An index member logical ID appears more than once.",
    "INDEX-DUPLICATE-PATH": "An index member path maps more than once.",
    "INDEX-EXTRA-MEMBER": "The index contains a member outside the required set.",
    "INDEX-FINAL-RESULT-MEMBERSHIP": "The final result appears as an ordinary index member.",
    "INDEX-MEMBER-BYTE-LENGTH-MISMATCH": "An index member byte length does not match the mapped bytes.",
    "INDEX-MEMBER-HASH-MISMATCH": "An index member hash does not match the mapped bytes.",
    "INDEX-MISSING-MEMBER": "A required index member is absent.",
    "INDEX-NONNORMALIZED-PATH": "An index member path is not normalized.",
    "INDEX-ROOT-HASH-MISMATCH": "The stored root hash does not recompute.",
    "INDEX-ROOT-ID-MISMATCH": "The index root ID does not match the declared opaque root.",
    "INDEX-SELF-MEMBERSHIP": "The acceptance index includes itself as a member.",
    "INDEX-SHA256-MISMATCH": "The stored index hash does not recompute.",
    "INDEX-SYMLINK-OR-REPARSE-ESCAPE": "An index member escapes through a symlink or reparse point.",
    "JSON-DUPLICATE-KEY": "A JSON object contains a duplicate member name.",
    "JSON-PARSE-INVALID": "The artifact bytes are not valid JSON.",
    "REF-CONTRADICTORY-BINDING": "Two bindings for the same logical ID disagree.",
    "REF-UNRESOLVED": "A required cross-artifact reference cannot be resolved.",
    "REVIEW-AUTHORING-CONTEXT": "A review inherited project-authoring context.",
    "REVIEW-CLASS-MISSING": "A required review-class run is absent.",
    "REVIEW-DISQUALIFICATION-CODE-MISMATCH": "Disqualification codes do not match the established rules.",
    "REVIEW-GOVERNED-SUBJECT-MUTATION": "A review mutated governed subject bytes.",
    "REVIEW-OUTCOME-MISMATCH": "A review recommendation does not match the independently derived outcome.",
    "REVIEW-UNDECLARED-TOOL-OR-EXTERNAL-ACCESS": "A review used an undeclared tool or external access.",
    "SCHEMA-ARRAY-DUPLICATE": "A set-valued array contains duplicate entries.",
    "SCHEMA-ARRAY-ORDER": "A set-valued array is not in the required order.",
    "SCHEMA-ENUM-INVALID": "A value is outside the declared enumeration.",
    "SCHEMA-FORMAT-INVALID": "A value violates a declared format rule.",
    "SCHEMA-MISSING-REQUIRED-FIELD": "A required field is absent.",
    "SCHEMA-TYPE-INVALID": "A value has the wrong primitive or compound type.",
    "SCHEMA-UNDECLARED-FIELD": "An undeclared field is present in a closed object.",
}

REJECTED_REASON_CODES = {
    "BYTE-CANONICAL-MISMATCH",
    "BYTE-TRAILING-DATA",
    "BYTE-UTF8-BOM",
    "BYTE-UTF8-INVALID",
    "JSON-DUPLICATE-KEY",
    "JSON-PARSE-INVALID",
}
BLOCKED_REASON_CODES = {
    "APPROVAL-CAPACITY-MISSING",
    "APPROVAL-NOT-EFFECTIVE",
    "COVERAGE-MISSING-ID",
    "INDEX-MISSING-MEMBER",
    "REF-UNRESOLVED",
    "REVIEW-CLASS-MISSING",
}
COVERAGE_INVALID_REASON_CODES = {
    "COVERAGE-CLASS-INVALID",
    "COVERAGE-DUPLICATE-IDENTITY",
    "COVERAGE-EXTRA-ID",
    "COVERAGE-ISOLATION-INVALID",
    "COVERAGE-SELECTION-CARDINALITY",
}


def fixture(
    fixture_id: str,
    target_contract_id: str,
    validation_phase: str,
    expected_status: str,
    expected_reason_codes: list[str],
    invariant_under_test: str,
    input_artifacts: list[str],
    expected_derived_values: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "expected_derived_values": expected_derived_values
        if expected_derived_values is not None
        else {"NOT_COMPUTABLE": True},
        "expected_reason_codes": sorted(set(expected_reason_codes)),
        "expected_status": expected_status,
        "fixture_id": fixture_id,
        "input_artifacts": input_artifacts,
        "invariant_under_test": invariant_under_test,
        "target_contract_id": target_contract_id,
        "validation_phase": validation_phase,
    }


def _json_text(value: object) -> str:
    return canonical_bytes(value).decode("utf-8")


def _golden_review_output() -> dict[str, object]:
    return {
        "candidate_evidence_root": "A" * 64,
        "coverage_assertion_ids": ["GOV-001"],
        "coverage_logical_ids": ["phase0.governance_plan"],
        "findings": [],
        "limitations": [],
        "recommended_candidate_outcome": "PASS",
        "reproduction_results": [],
        "review_class": "INTEGRITY_AND_REPRODUCTION_AUDIT",
        "summary": "Synthetic golden review output.",
    }


def _golden_review_run() -> dict[str, object]:
    output = _golden_review_output()
    run: dict[str, object] = {
        "candidate_evidence_root": "A" * 64,
        "canonical_configuration_hash": "B" * 64,
        "completed_at": "2026-08-14T12:00:00.000000000Z",
        "coverage_assertion_ids": ["GOV-001"],
        "coverage_logical_ids": ["phase0.governance_plan"],
        "disqualification_reason_codes": [],
        "eligibility_result": {
            "status": "ELIGIBLE",
            "violation_count": 0,
            "violations": [],
        },
        "findings": [],
        "input_artifact_hashes": [
            {"logical_id": SUITE_LOGICAL_ID, "sha256": "C" * 64},
            {"logical_id": SUITE_APPROVAL_LOGICAL_ID, "sha256": "D" * 64},
        ],
        "model_service_and_declared_version": {
            "declared_model_version": "synthetic-1",
            "model_service": "synthetic-service",
        },
        "plan_hash": PLAN_SHA256,
        "qualification_state": "QUALIFYING",
        "recommended_candidate_outcome": "PASS",
        "registry_hash": "F" * 64,
        "reproduction_results": [],
        "review_class": "INTEGRITY_AND_REPRODUCTION_AUDIT",
        "review_output_hash": sha256_bytes(canonical_bytes(output)),
        "review_procedure_id_and_hash": {
            "procedure_id": PROCEDURE_ID,
            "sha256": PROCEDURE_SHA256,
        },
        "review_run_id": "0" * 64,
        "run_id": "3" * 64,
        "runtime_and_tool_versions": [
            {
                "component_id": "python",
                "declared_version": "3.11",
                "runtime_context": "isolated synthetic",
            }
        ],
        "specification_hash": SPECIFICATION_SHA256,
        "started_at": "2026-08-14T11:00:00.000000000Z",
        "terminal_state": "COMPLETE",
    }
    run["review_run_id"] = record_identity(run, "review_run_id")
    return run


def _golden_coverage() -> dict[str, object]:
    run_ids = ["2" * 64, "5" * 64]
    isolation_results = [
        {
            "check_id": check_id,
            "evidence_refs": ["synthetic.isolation_evidence"],
            "observed": "Synthetic isolation condition passed.",
            "result": "PASS",
            "review_run_id": run_id,
        }
        for run_id in run_ids
        for check_id in ISOLATION_CHECK_IDS
    ]
    return {
        "candidate_evidence_root": "A" * 64,
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
        "isolation_check_results": isolation_results,
        "missing_assertion_ids": [],
        "missing_logical_ids": [],
        "qualification_status": "QUALIFIED",
        "qualifying_review_run_ids": run_ids,
        "registry_hash": "F" * 64,
        "review_class_assignments": [
            {
                "review_class": "ADVERSARIAL_REQUIREMENTS_AND_CONFORMANCE_AUDIT",
                "review_run_id": run_ids[0],
            },
            {
                "review_class": "INTEGRITY_AND_REPRODUCTION_AUDIT",
                "review_run_id": run_ids[1],
            },
        ],
        "review_procedure_id_and_hash": {
            "procedure_id": PROCEDURE_ID,
            "sha256": PROCEDURE_SHA256,
        },
        "selected_review_run_ids": run_ids,
    }


def _golden_preeligibility() -> dict[str, object]:
    check_results = [
        {
            "check_id": check_id,
            "evidence_refs": ["phase0.ai_review_procedure"],
            "expected_condition": "Synthetic expected condition.",
            "observed_condition": "Synthetic observed condition.",
            "reason_codes": [],
            "status": "PASS",
        }
        for check_id in PREELIGIBILITY_CHECK_IDS
    ]
    return {
        "acknowledgements": [
            {
                "acknowledgement_id": "ACK-SYNTHETIC-SCOPE-001",
                "statement": "Synthetic eligibility fixture only.",
            }
        ],
        "artifact_type": "PREAPPROVAL_REVIEWER_ELIGIBILITY_RESULT",
        "authority_bindings": [
            {
                "approval_basis": "Synthetic exact-hash approval basis.",
                "effectivity_state": "EFFECTIVE",
                "logical_id": "phase0.ai_review_procedure",
                "logical_path": "synthetic/ai-review-procedure.json",
                "sha256": PROCEDURE_SHA256,
            }
        ],
        "check_results": check_results,
        "documented_on": "2026-08-14",
        "effectivity": {
            "activation_condition": "Synthetic exact-hash approval event.",
            "approval_event_state": "EFFECTIVE",
            "approval_must_bind": ["phase0.preapproval_reviewer_eligibility"],
            "current_effectivity": "EFFECTIVE",
            "determination_rule": "Synthetic deterministic rule.",
            "effective_from": "2026-08-14T12:00:00.000000000Z",
            "effective_until": "OPEN",
            "self_hash_rule": "The record cannot self-approve.",
        },
        "eligibility_determination": {
            "blocked_check_count": 0,
            "failed_check_count": 0,
            "passed_check_count": 6,
            "required_check_count": 6,
            "status": "ELIGIBLE",
            "violation_count": 0,
            "violations": [],
        },
        "governance_effect": {
            "candidate_root_effect": "NONE",
            "gov002_current_status": "ELIGIBLE",
            "gov002_reassessment_rule": "Reassess after any governed byte change.",
            "implementation_authority": "NONE",
            "postroot_evidence_rule": "Postroot evidence is excluded.",
            "result_scope": "Reviewer eligibility only.",
        },
        "logical_id": "phase0.preapproval_reviewer_eligibility",
        "non_authorizations": ["AI_REVIEW_RUN_EXECUTION"],
        "record_status": "SYNTHETIC_GOLDEN",
        "schema_version": "1.0.0",
        "supersession": {
            "revision_rule": "Any byte change requires a new synthetic revision.",
            "superseded_by": None,
            "supersedes": [],
        },
        "validation_contract": {
            "additional_property_rule": "Reject undeclared fields.",
            "aggregate_rule": "Counts and statuses must agree.",
            "allowed_blocked_reason_codes": ["REQUIRED_EVIDENCE_UNAVAILABLE"],
            "allowed_fail_reason_codes_by_check": deepcopy(PREELIGIBILITY_ALLOWED_FAILURES),
            "array_ordering_rule": "Set-valued arrays are sorted and unique.",
            "authority_hash_rule": "Authority hashes must match exact bytes.",
            "check_id_order_required": PREELIGIBILITY_CHECK_IDS,
            "check_status_values": ["BLOCKED", "FAIL", "PASS"],
            "count_consistency_rule": "Counts equal observed statuses.",
            "duplicate_key_rule": "Duplicate keys are rejected.",
            "eligibility_status_values": ["BLOCKED", "ELIGIBLE", "INELIGIBLE"],
            "encoding": "UTF-8 without byte-order mark.",
            "evidence_resolution_rule": "Every reference resolves exactly once.",
            "line_endings": "Not applicable to compact JSON.",
            "object_key_order_rule": "Unicode code-point ascending.",
            "profile_id": "PHASE0-GOVERNANCE-DOCUMENT-JSON-1.0.0",
            "reason_code_rule": "Reason codes are check scoped.",
            "required_top_level_fields": [],
            "trailing_newline": "Forbidden.",
        },
    }


def _golden_suite_approval() -> dict[str, object]:
    record: dict[str, object] = {
        "approval_record_id": "0" * 64,
        "approved_at": "2026-08-14T12:00:00.000000000Z",
        "approved_by_principal_id": "PROJECT-PRINCIPAL-001",
        "approved_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "approved_logical_id": SUITE_LOGICAL_ID,
        "approved_sha256": "A" * 64,
        "approval_scope": "INTEGRITY_REVIEW_COMPANION_INPUT_ONLY",
        "procedure_id": PROCEDURE_ID,
        "procedure_sha256": PROCEDURE_SHA256,
        "status": "APPROVED",
    }
    record["approval_record_id"] = record_identity(record, "approval_record_id")
    return record


def _golden_approval_records() -> dict[str, object]:
    approval: dict[str, object] = {
        "approval_record_id": "0" * 64,
        "approval_scope": "SYNTHETIC_CANDIDATE_APPROVAL",
        "approved_at": "2026-08-14T12:00:00.000000000Z",
        "approved_by_principal_id": "PROJECT-PRINCIPAL-001",
        "candidate_evidence_root": "A" * 64,
        "capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "status": "APPROVED",
    }
    approval["approval_record_id"] = record_identity(approval, "approval_record_id")
    return {
        "approval_records": [approval],
        "assertion_run_hash": "1" * 64,
        "candidate_evidence_root": "A" * 64,
        "duplicate_capacities": [],
        "extra_capacities": [],
        "logical_id": "phase0.approval_records",
        "missing_capacities": [],
        "observed_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "plan_hash": PLAN_SHA256,
        "procedure_hash": PROCEDURE_SHA256,
        "reason_codes": [],
        "registry_hash": "F" * 64,
        "required_capacities": ["PROJECT_OWNER", "RELEASE_OWNER"],
        "schema_version": "1.0.0",
        "specification_hash": SPECIFICATION_SHA256,
        "status": "PASS",
        "suite_sha256": "C" * 64,
    }


def _golden_acceptance_index() -> dict[str, object]:
    members = []
    for logical_id in expected_index_logical_ids(["phase0.governance_plan"]):
        member_bytes = canonical_bytes({"logical_id": logical_id, "synthetic": True})
        members.append(
            {
                "byte_length": len(member_bytes),
                "logical_id": logical_id,
                "media_type": "application/json",
                "member_sha256": sha256_bytes(member_bytes),
                "repository_relative_path": (
                    "synthetic/" + logical_id.replace(".", "-") + ".json"
                ),
                "root_id": "ROOT-TEST-001",
            }
        )
    index: dict[str, object] = {
        "candidate_evidence_root": "A" * 64,
        "index_members": members,
        "index_sha256": "0" * 64,
        "logical_id": "phase0.acceptance_index",
        "procedure_id_and_hash": {
            "procedure_id": PROCEDURE_ID,
            "sha256": PROCEDURE_SHA256,
        },
        "root_hash": "0" * 64,
        "root_id": "ROOT-TEST-001",
        "schema_version": "1.0.0",
        "suite_id_and_hash": {
            "logical_id": SUITE_LOGICAL_ID,
            "sha256": "C" * 64,
        },
    }
    index_sha256, root_hash = compute_index_hashes(index)
    index["index_sha256"] = index_sha256
    index["root_hash"] = root_hash
    return index


def _golden_final_result() -> dict[str, object]:
    index = _golden_acceptance_index()
    result: dict[str, object] = {
        "assertion_aggregate_status": "PASS",
        "candidate_evidence_root": "A" * 64,
        "completed_at": "2026-08-14T12:00:00.000000000Z",
        "final_result_id": "0" * 64,
        "index_sha256": index["index_sha256"],
        "logical_id": "phase0.final_acceptance_result",
        "outcome": "PASS",
        "reason_codes": [],
        "review_coverage_status": "QUALIFIED",
        "root_hash": index["root_hash"],
        "schema_version": "1.0.0",
        "suite_sha256": "C" * 64,
    }
    result["final_result_id"] = record_identity(result, "final_result_id")
    return result


def _golden_fixtures() -> list[dict[str, object]]:
    values = [
        ("GOLDEN-ACCEPTANCE-INDEX-001", "phase0.acceptance_index.contract", _golden_acceptance_index()),
        ("GOLDEN-AI-REVIEW-COVERAGE-001", "phase0.ai_review_coverage.contract", _golden_coverage()),
        ("GOLDEN-AI-REVIEW-OUTPUT-001", "phase0.ai_review_output.contract", _golden_review_output()),
        ("GOLDEN-AI-REVIEW-RUN-001", "phase0.ai_review_run.contract", _golden_review_run()),
        ("GOLDEN-APPROVAL-RECORDS-001", "phase0.approval_records.contract", _golden_approval_records()),
        ("GOLDEN-FINAL-ACCEPTANCE-RESULT-001", "phase0.final_acceptance_result.contract", _golden_final_result()),
        ("GOLDEN-PREAPPROVAL-ELIGIBILITY-001", "phase0.preapproval_reviewer_eligibility.contract", _golden_preeligibility()),
        ("GOLDEN-SUITE-APPROVAL-001", "phase0.postroot_acceptance_contract_suite.approval.contract", _golden_suite_approval()),
    ]
    fixtures = []
    for fixture_id, contract_id, value in values:
        derived: dict[str, object] = {
            "canonical_sha256": sha256_bytes(canonical_bytes(value))
        }
        if "review_run_id" in value:
            derived["review_run_id"] = value["review_run_id"]
        if "approval_record_id" in value:
            derived["approval_record_id"] = value["approval_record_id"]
        if "index_sha256" in value:
            derived["index_sha256"] = value["index_sha256"]
        if "root_hash" in value:
            derived["root_hash"] = value["root_hash"]
        if "final_result_id" in value:
            derived["final_result_id"] = value["final_result_id"]
        fixtures.append(
            fixture(
                fixture_id,
                contract_id,
                "CLOSED_SCHEMA",
                "PASS",
                [],
                f"Golden vector for {contract_id}.",
                [_json_text(value)],
                derived,
            )
        )
    return fixtures


def _adversarial_target(code: str) -> tuple[str, str]:
    mappings = {
        "APPROVAL-": ("phase0.approval_records.contract", "CROSS_ARTIFACT_AND_COVERAGE"),
        "BYTE-": ("phase0.ai_review_output.contract", "BYTE_AND_JSON"),
        "COVERAGE-": ("phase0.ai_review_coverage.contract", "CROSS_ARTIFACT_AND_COVERAGE"),
        "GATE-": ("phase0.final_acceptance_result.contract", "FINAL_OUTCOME"),
        "HASH-": ("phase0.ai_review_run.contract", "IDENTITY_AND_HASH"),
        "ID-": ("phase0.ai_review_run.contract", "IDENTITY_AND_HASH"),
        "INDEX-": ("phase0.acceptance_index.contract", "ACCEPTANCE_INDEX"),
        "JSON-": ("phase0.ai_review_output.contract", "BYTE_AND_JSON"),
        "REF-": ("phase0.ai_review_coverage.contract", "CROSS_ARTIFACT_AND_COVERAGE"),
        "REVIEW-": ("phase0.ai_review_run.contract", "CROSS_ARTIFACT_AND_COVERAGE"),
        "SCHEMA-": ("phase0.ai_review_output.contract", "CLOSED_SCHEMA"),
    }
    return next(value for prefix, value in mappings.items() if code.startswith(prefix))


def _adversarial_input(code: str) -> str:
    raw_cases = {
        "BYTE-CANONICAL-MISMATCH": '{ "synthetic": true }',
        "BYTE-TRAILING-DATA": "{}trailing",
        "BYTE-UTF8-BOM": "\ufeff{}",
        "BYTE-UTF8-INVALID": _json_text(
            {"content_encoding": "HEX", "raw_bytes_hex": "FFFE", "synthetic": True}
        ),
        "JSON-DUPLICATE-KEY": '{"synthetic":true,"synthetic":false}',
        "JSON-PARSE-INVALID": "{",
    }
    if code in raw_cases:
        return raw_cases[code]
    return _json_text({"adversarial_case": code, "synthetic": True})


def _adversarial_fixture(code: str) -> dict[str, object]:
    target_contract_id, validation_phase = _adversarial_target(code)
    if code in REJECTED_REASON_CODES:
        expected_status = "REJECTED"
    elif code in BLOCKED_REASON_CODES:
        expected_status = "BLOCKED"
    elif code in COVERAGE_INVALID_REASON_CODES:
        expected_status = "INVALID"
    else:
        expected_status = "FAIL"
    return fixture(
        f"ADV-{code}",
        target_contract_id,
        validation_phase,
        expected_status,
        [code],
        REASON_DESCRIPTIONS[code],
        [_adversarial_input(code)],
    )


def build_reason_code_registry() -> list[dict[str, object]]:
    if set(REASON_CODES) != set(REASON_DESCRIPTIONS):
        raise ValueError("REASON-REGISTRY-INVENTORY-MISMATCH")
    registry = []
    for code in REASON_CODES:
        if code in REJECTED_REASON_CODES:
            gate_effect = "REJECTED"
        elif code in BLOCKED_REASON_CODES:
            gate_effect = "BLOCKED"
        else:
            gate_effect = "FAIL"
        registry.append(
            {
                "description": REASON_DESCRIPTIONS[code],
                "gate_effect": gate_effect,
                "reason_code": code,
            }
        )
    return registry


def build_fixture_catalog() -> list[dict[str, object]]:
    fixtures = _golden_fixtures()
    fixtures.extend(_adversarial_fixture(code) for code in REASON_CODES)
    return sorted(fixtures, key=lambda row: str(row["fixture_id"]))


def build_suite() -> dict[str, object]:
    return {
        "acknowledgements": [
            {
                "acknowledgement_id": "ACK-CANDIDATE-NEUTRAL-001",
                "statement": "The suite binds no candidate evidence root and creates no acceptance evidence.",
            },
            {
                "acknowledgement_id": "ACK-EXACT-HASH-APPROVAL-001",
                "statement": "The suite remains ineffective until the principal approves its complete exact bytes and SHA-256.",
            },
        ],
        "artifact_type": "PHASE0_POSTROOT_ACCEPTANCE_CONTRACT_SUITE",
        "authority_bindings": [
            {
                "logical_id": "phase0.ai_review_procedure",
                "sha256": PROCEDURE_SHA256,
            },
            {"logical_id": "phase0.governance_plan", "sha256": PLAN_SHA256},
        ],
        "canonical_encoding_profile": {
            "encoding": "UTF-8_WITHOUT_BOM",
            "object_key_order": "UNICODE_CODE_POINT_ASCENDING",
            "profile_id": "PHASE0-CANONICAL-JSON-1.0.0",
            "trailing_newline": "FORBIDDEN",
        },
        "closed_contract_profile": {
            "formats": ["LOGICAL_ID", "NONEMPTY", "SHA256", "TIMESTAMP"],
            "ordering_modes": ["LEXICOGRAPHIC_UNIQUE", "SEQUENCE"],
            "profile_id": "PHASE0-CLOSED-CONTRACT-1.0.0",
            "types": ["array", "boolean", "integer", "null", "object", "string"],
        },
        "contract_schemas": build_contract_schemas(),
        "documented_on": "2026-08-14",
        "effectivity": {
            "activation_condition": "EXTERNAL_ATTRIBUTABLE_EXACT_HASH_PRINCIPAL_APPROVAL",
            "approval_record_logical_id": SUITE_APPROVAL_LOGICAL_ID,
            "current_effectivity": "PENDING_EXACT_HASH_PRINCIPAL_APPROVAL",
            "self_hash_embedded": False,
        },
        "fixture_catalog": build_fixture_catalog(),
        "logical_id": SUITE_LOGICAL_ID,
        "non_authorizations": NON_AUTHORIZATIONS,
        "reason_code_registry": build_reason_code_registry(),
        "schema_version": "1.0.0",
        "suite_scope": {
            "candidate_binding": "SUPPLIED_PER_REVIEW_RUN",
            "purpose": "POSTROOT_ACCEPTANCE_CONTRACT_VALIDATION",
            "synthetic_fixtures_only": True,
        },
        "supersession": {
            "change_rule": "ANY_BYTE_CHANGE_REQUIRES_NEW_EXACT_HASH_APPROVAL",
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

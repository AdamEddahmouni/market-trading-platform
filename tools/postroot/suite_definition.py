from __future__ import annotations

from copy import deepcopy


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


def build_reason_code_registry() -> list[dict[str, object]]:
    return []


def build_fixture_catalog() -> list[dict[str, object]]:
    return []


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

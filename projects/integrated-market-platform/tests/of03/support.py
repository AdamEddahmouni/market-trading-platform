from __future__ import annotations

import json
from pathlib import Path

from market_platform_foundation.canonical import write_canonical_json


REPO = Path(__file__).resolve().parents[2]


def write_registry(root: Path, *, capabilities, sops, workflows, active_capabilities=None, active_sops=None, active_workflows=None, snapshot_hash=None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    write_canonical_json(root / "capabilities.json", capabilities)
    write_canonical_json(root / "sops.json", sops)
    write_canonical_json(root / "workflows.json", workflows)
    manifest = {
        "registry_schema_version": 1,
        "active_capabilities": active_capabilities if active_capabilities is not None else {c["capability_id"]: c["definition_version"] for c in capabilities},
        "active_sops": active_sops if active_sops is not None else {s["sop_id"]: s["definition_version"] for s in sops},
        "active_workflows": active_workflows if active_workflows is not None else {w["workflow_id"]: w["definition_version"] for w in workflows},
    }
    if snapshot_hash is not None:
        manifest["registry_snapshot_hash"] = snapshot_hash
    write_canonical_json(root / "manifest.json", manifest)
    return root


def sample_capability(**overrides):
    payload = {
        "schema_version": 1,
        "capability_id": "TEST.OP.READ",
        "definition_version": 1,
        "title": "Read",
        "description": "fixture",
        "owner_subsystem": "of03",
        "consequence_profile": "C1_OPERATIONAL",
        "effect_class": "READ_ONLY",
        "binding": {
            "binding_kind": "PYTHON_API",
            "module": "market_platform_foundation.of03.operations",
            "qualname": "execute",
        },
        "input_contract_ref": "none",
        "output_contract_ref": "none",
        "required_authority_refs": ["OPERATOR_INSPECT"],
        "required_role_refs": [],
        "automation_policy": "AUTOMATION_ALLOWED",
        "human_approval_policy": "NOT_REQUIRED",
        "idempotency_class": "SAFE_REPEATABLE",
        "retry_class": "NONE",
        "of_attribution_requirement": "NONE",
        "required_evidence_classes": [],
        "feature_gates": [],
        "sop_refs": [{"sop_id": "SOP-OF03-001", "sop_version": 1}],
        "domain_reference_requirements": [],
        "deprecation": None,
        "registration_state": "DECLARED",
    }
    payload.update(overrides)
    return payload


def sample_sop(**overrides):
    payload = {
        "schema_version": 1,
        "sop_id": "SOP-OF03-001",
        "definition_version": 1,
        "title": "Inspect registry status",
        "owner_subsystem": "of03",
        "document_path": "docs/operations/of-03/SOPS.md",
        "document_anchor": "SOP-OF03-001",
        "consequence_profile": "C1_OPERATIONAL",
        "required_authority_refs": ["REGISTRY_OPERATOR"],
        "automation_policy": "AUTOMATION_ALLOWED",
        "related_capability_refs": [{"capability_id": "TEST.OP.READ", "capability_version": 1}],
        "related_workflow_refs": [{"workflow_id": "WF-TEST-001", "workflow_version": 1}],
        "prerequisites": [],
        "required_evidence_classes": [],
        "maturity": "NORMATIVE",
        "deprecation": None,
    }
    payload.update(overrides)
    return payload


def sample_workflow(**overrides):
    payload = {
        "schema_version": 1,
        "workflow_id": "WF-TEST-001",
        "definition_version": 1,
        "title": "linear",
        "objective": "fixture",
        "owner_subsystem": "of03",
        "consequence_profile": "C1_OPERATIONAL",
        "initiator_class": "HUMAN",
        "required_authority_refs": ["REGISTRY_OPERATOR"],
        "required_role_refs": [],
        "required_inputs": [],
        "domain_reference_requirements": [
            {"role": "model_candidate", "required": False, "cardinality": "ONE"},
            {"role": "dataset", "required": True, "cardinality": "ONE"},
        ],
        "required_evidence_classes": [],
        "failure_policy": "STOP_BEFORE_LATER_SUCCESS",
        "retry_policy": {"retry_kind": "NONE", "graph_cycles_permitted": False},
        "terminal_dispositions": ["SUCCESS"],
        "sop_refs": [{"sop_id": "SOP-OF03-001", "sop_version": 1}],
        "capability_refs": [{"capability_id": "TEST.OP.READ", "capability_version": 1}],
        "of_attribution_requirement": "NONE",
        "automation_policy": "AUTOMATION_ALLOWED",
        "human_approval_policy": "NOT_REQUIRED",
        "document_path": "docs/operations/of-03/WORKFLOWS.md",
        "document_anchor": "WF-OF03-001",
        "deprecation": None,
        "entry_step_id": "a",
        "steps": [
            {"step_id": "a", "kind": "CAPABILITY", "capability_id": "TEST.OP.READ", "capability_version": 1, "next": ["done"]},
            {"step_id": "done", "kind": "TERMINAL", "disposition": "SUCCESS", "next": []},
        ],
    }
    payload.update(overrides)
    return payload

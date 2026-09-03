"""Cross-registry integrity. Fail closed on ERROR findings."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .authorities import KNOWN_AUTHORITY_REFS, KNOWN_ROLE_REFS
from .bindings import verify_binding
from .contracts import CapabilityDefinition, SopDefinition, WorkflowDefinition
from .documents import read_document_sections, section_hash
from .enums import AutomationPolicy, BindingKind, FindingSeverity, HumanApprovalPolicy, StepKind
from .graph import validate_workflow_graph


def validate_loaded(
    *,
    capabilities: tuple[CapabilityDefinition, ...],
    sops: tuple[SopDefinition, ...],
    workflows: tuple[WorkflowDefinition, ...],
    active_capabilities: dict[str, int],
    active_sops: dict[str, int],
    active_workflows: dict[str, int],
    repository_root: Path,
    verify_bindings: bool = True,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    cap_index = {(c.capability_id, c.definition_version): c for c in capabilities}
    sop_index = {(s.sop_id, s.definition_version): s for s in sops}
    wf_index = {(w.workflow_id, w.definition_version): w for w in workflows}
    if len(cap_index) != len(capabilities):
        findings.append(_find(FindingSeverity.ERROR, "duplicate capability identity"))
    if len(sop_index) != len(sops):
        findings.append(_find(FindingSeverity.ERROR, "duplicate SOP identity"))
    if len(wf_index) != len(workflows):
        findings.append(_find(FindingSeverity.ERROR, "duplicate workflow identity"))

    for cap in capabilities:
        findings.extend(_validate_capability(cap, sop_index, repository_root, verify_bindings=verify_bindings))
        if cap.deprecation.deprecated:
            findings.append(_find(FindingSeverity.INFO, "deprecated capability", extra={"capability_id": cap.capability_id}))
            _require_replacement(cap.deprecation.superseded_by, cap_index, findings, "capability")
    for sop in sops:
        findings.extend(_validate_sop(sop, cap_index, wf_index, repository_root))
        if sop.deprecation.deprecated:
            findings.append(_find(FindingSeverity.INFO, "deprecated SOP", extra={"sop_id": sop.sop_id}))
            _require_replacement(sop.deprecation.superseded_by, sop_index, findings, "sop")
    for workflow in workflows:
        findings.extend(validate_workflow_graph(workflow))
        findings.extend(_validate_workflow_refs(workflow, cap_index, sop_index, repository_root))
        if workflow.deprecation.deprecated:
            findings.append(_find(FindingSeverity.INFO, "deprecated workflow", extra={"workflow_id": workflow.workflow_id}))
            _require_replacement(workflow.deprecation.superseded_by, wf_index, findings, "workflow")

    findings.extend(_validate_active("capability", active_capabilities, cap_index))
    findings.extend(_validate_active("sop", active_sops, sop_index))
    findings.extend(_validate_active("workflow", active_workflows, wf_index))
    return findings


def _validate_capability(
    cap: CapabilityDefinition,
    sop_index: dict,
    repository_root: Path,
    *,
    verify_bindings: bool,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for ref in cap.required_authority_refs:
        if ref not in KNOWN_AUTHORITY_REFS:
            findings.append(_find(FindingSeverity.ERROR, "unknown authority reference", extra={"ref": ref, "capability_id": cap.capability_id}))
    for ref in cap.required_role_refs:
        if ref not in KNOWN_ROLE_REFS:
            findings.append(_find(FindingSeverity.ERROR, "unknown role reference", extra={"ref": ref, "capability_id": cap.capability_id}))
    if cap.automation_policy is AutomationPolicy.AUTOMATION_ALLOWED and cap.human_approval_policy is HumanApprovalPolicy.REQUIRED:
        findings.append(_find(FindingSeverity.ERROR, "human approval cannot claim automation allowed", extra={"capability_id": cap.capability_id}))
    if cap.human_approval_policy is HumanApprovalPolicy.REQUIRED and cap.automation_policy is not AutomationPolicy.HUMAN_APPROVAL_REQUIRED and cap.automation_policy is not AutomationPolicy.AGENT_PROHIBITED:
        if cap.automation_policy is AutomationPolicy.AUTOMATION_ALLOWED:
            findings.append(_find(FindingSeverity.ERROR, "human approval cannot claim automation allowed", extra={"capability_id": cap.capability_id}))
    for sop_ref in cap.sop_refs:
        if (sop_ref.id, sop_ref.version) not in sop_index:
            findings.append(_find(FindingSeverity.ERROR, "unknown SOP reference", extra={"sop_id": sop_ref.id, "sop_version": sop_ref.version}))
    if cap.binding.binding_kind is BindingKind.UNBOUND:
        findings.append(_find(FindingSeverity.WARNING, "capability unbound", extra={"capability_id": cap.capability_id}))
    elif verify_bindings:
        report = verify_binding(cap, repository_root=repository_root)
        if not report["ok"]:
            findings.append(_find(FindingSeverity.ERROR, "binding verification failed", extra={"capability_id": cap.capability_id, "details": report["findings"]}))
    return findings


def _validate_sop(sop: SopDefinition, cap_index: dict, wf_index: dict, repository_root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for ref in sop.required_authority_refs:
        if ref not in KNOWN_AUTHORITY_REFS:
            findings.append(_find(FindingSeverity.ERROR, "unknown authority reference", extra={"ref": ref, "sop_id": sop.sop_id}))
    for ref in sop.related_capability_refs:
        if (ref.id, ref.version) not in cap_index:
            findings.append(_find(FindingSeverity.ERROR, "unknown capability reference", extra={"capability_id": ref.id, "sop_id": sop.sop_id}))
    for ref in sop.related_workflow_refs:
        if (ref.id, ref.version) not in wf_index:
            findings.append(_find(FindingSeverity.ERROR, "unknown workflow reference", extra={"workflow_id": ref.id, "sop_id": sop.sop_id}))
    try:
        sections = read_document_sections(repository_root, sop.document_path)
    except FileNotFoundError:
        findings.append(_find(FindingSeverity.ERROR, "SOP document missing", extra={"path": sop.document_path, "sop_id": sop.sop_id}))
        return findings
    except ValueError as exc:
        findings.append(_find(FindingSeverity.ERROR, "duplicate SOP heading", extra={"sop_id": sop.sop_id, "detail": str(exc)}))
        return findings
    if sop.document_anchor not in sections:
        findings.append(_find(FindingSeverity.ERROR, "SOP anchor missing", extra={"anchor": sop.document_anchor, "sop_id": sop.sop_id}))
        return findings
    if sop.sop_id != sop.document_anchor:
        findings.append(_find(FindingSeverity.ERROR, "SOP ID does not match document anchor", extra={"sop_id": sop.sop_id}))
    live_hash = section_hash(sections[sop.document_anchor])
    if sop.document_section_hash and sop.document_section_hash != live_hash:
        findings.append(_find(FindingSeverity.WARNING, "SOP document section drift", extra={"sop_id": sop.sop_id}))
    return findings


def _validate_workflow_refs(workflow: WorkflowDefinition, cap_index: dict, sop_index: dict, repository_root: Path) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for ref in workflow.required_authority_refs:
        if ref not in KNOWN_AUTHORITY_REFS:
            findings.append(_find(FindingSeverity.ERROR, "unknown authority reference", extra={"ref": ref, "workflow_id": workflow.workflow_id}))
    for ref in workflow.capability_refs:
        if (ref.id, ref.version) not in cap_index:
            findings.append(_find(FindingSeverity.ERROR, "unknown capability reference", extra={"capability_id": ref.id, "workflow_id": workflow.workflow_id}))
        else:
            cap = cap_index[(ref.id, ref.version)]
            if cap.deprecation.deprecated:
                findings.append(_find(FindingSeverity.WARNING, "workflow references deprecated capability", extra={"capability_id": ref.id, "workflow_id": workflow.workflow_id}))
    for ref in workflow.sop_refs:
        if (ref.id, ref.version) not in sop_index:
            findings.append(_find(FindingSeverity.ERROR, "unknown SOP reference", extra={"sop_id": ref.id, "workflow_id": workflow.workflow_id}))
    path = repository_root / workflow.document_path
    if not path.is_file():
        findings.append(_find(FindingSeverity.ERROR, "workflow document missing", extra={"path": workflow.document_path, "workflow_id": workflow.workflow_id}))
    else:
        try:
            from .documents import extract_sections

            sections = extract_sections(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            findings.append(_find(FindingSeverity.ERROR, "duplicate workflow heading", extra={"detail": str(exc)}))
            return findings
        if workflow.document_anchor not in sections:
            findings.append(_find(FindingSeverity.ERROR, "workflow anchor missing", extra={"anchor": workflow.document_anchor, "workflow_id": workflow.workflow_id}))
    for step in workflow.steps:
        if step.kind is StepKind.CAPABILITY and step.capability_id and step.capability_version is not None:
            if (step.capability_id, step.capability_version) not in cap_index:
                findings.append(_find(FindingSeverity.ERROR, "unknown capability reference", extra={"capability_id": step.capability_id, "workflow_id": workflow.workflow_id}))
        if step.kind is StepKind.SOP and step.sop_id and step.sop_version is not None:
            if (step.sop_id, step.sop_version) not in sop_index:
                findings.append(_find(FindingSeverity.ERROR, "unknown SOP reference", extra={"sop_id": step.sop_id, "workflow_id": workflow.workflow_id}))
        if step.kind is StepKind.GATE and step.gate is not None:
            if step.gate.authority_reference and step.gate.authority_reference not in KNOWN_AUTHORITY_REFS:
                findings.append(_find(FindingSeverity.ERROR, "invalid authority gate", extra={"ref": step.gate.authority_reference, "workflow_id": workflow.workflow_id}))
    if workflow.automation_policy is AutomationPolicy.AUTOMATION_ALLOWED and workflow.human_approval_policy is HumanApprovalPolicy.REQUIRED:
        findings.append(_find(FindingSeverity.ERROR, "human approval cannot claim automation allowed", extra={"workflow_id": workflow.workflow_id}))
    return findings


def _validate_active(kind: str, active: dict[str, int], index: dict) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for ident, version in active.items():
        if (ident, version) not in index:
            findings.append(_find(FindingSeverity.ERROR, "invalid active-version pointer", extra={"kind": kind, "id": ident, "version": version}))
        else:
            item = index[(ident, version)]
            if item.deprecation.deprecated:
                findings.append(_find(FindingSeverity.WARNING, "active version is deprecated", extra={"kind": kind, "id": ident, "version": version}))
    return findings


def _require_replacement(ref: Any, index: dict, findings: list[dict[str, Any]], kind: str) -> None:
    if ref is None:
        findings.append(_find(FindingSeverity.ERROR, "deprecated replacement missing", extra={"kind": kind}))
        return
    if (ref.id, ref.version) not in index:
        findings.append(_find(FindingSeverity.ERROR, "deprecated replacement missing", extra={"kind": kind, "id": ref.id, "version": ref.version}))


def _find(severity: FindingSeverity, message: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"severity": severity.value, "message": message}
    if extra:
        payload.update(extra)
    return payload


def errors_only(findings: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [f for f in findings if f.get("severity") == FindingSeverity.ERROR.value]

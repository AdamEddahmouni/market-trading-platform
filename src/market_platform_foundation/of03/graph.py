"""Acyclic workflow graph validation. Cycles are never accepted."""

from __future__ import annotations

from .contracts import WorkflowDefinition
from .enums import FindingSeverity, StepKind
from .errors import OF03Error, OF03ErrorCode


def validate_workflow_graph(workflow: WorkflowDefinition) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    ids = [step.step_id for step in workflow.steps]
    if len(ids) != len(set(ids)):
        findings.append(_err("duplicate workflow step_id", workflow.workflow_id))
        return findings
    by_id = {step.step_id: step for step in workflow.steps}
    if workflow.entry_step_id not in by_id:
        findings.append(_err("invalid entry_step_id", workflow.workflow_id))
        return findings
    for step in workflow.steps:
        for nxt in step.next:
            if nxt not in by_id:
                findings.append(_err("unknown next step", workflow.workflow_id, extra={"step_id": step.step_id, "next": nxt}))
        if step.kind is StepKind.TERMINAL:
            if step.next:
                findings.append(_err("terminal step may not have successors", workflow.workflow_id, extra={"step_id": step.step_id}))
            if not step.disposition:
                findings.append(_err("terminal step missing disposition", workflow.workflow_id, extra={"step_id": step.step_id}))
        elif not step.next:
            findings.append(_err("non-terminal step missing next", workflow.workflow_id, extra={"step_id": step.step_id}))
        if step.kind is StepKind.CAPABILITY and (not step.capability_id or step.capability_version is None):
            findings.append(_err("capability step missing exact version", workflow.workflow_id, extra={"step_id": step.step_id}))
        if step.kind is StepKind.SOP and (not step.sop_id or step.sop_version is None):
            findings.append(_err("SOP step missing exact version", workflow.workflow_id, extra={"step_id": step.step_id}))
        if step.kind is StepKind.GATE and step.gate is None:
            findings.append(_err("gate step missing gate", workflow.workflow_id, extra={"step_id": step.step_id}))
    if _has_cycle(workflow.entry_step_id, by_id):
        findings.append(_err("workflow cycle", workflow.workflow_id))
    reachable: set[str] = set()
    _walk(workflow.entry_step_id, by_id, reachable)
    unreachable = set(by_id) - reachable
    if unreachable:
        findings.append(_err("unreachable workflow step", workflow.workflow_id, extra={"steps": sorted(unreachable)}))
    terminals = [s for s in workflow.steps if s.kind is StepKind.TERMINAL]
    if not terminals:
        findings.append(_err("missing workflow terminal", workflow.workflow_id))
    else:
        if not any(t.step_id in reachable for t in terminals):
            findings.append(_err("no reachable terminal path", workflow.workflow_id))
        for node in reachable:
            if not _reaches_terminal(node, by_id, set()):
                step = by_id[node]
                if step.kind is not StepKind.TERMINAL:
                    findings.append(_err("step cannot reach terminal", workflow.workflow_id, extra={"step_id": node}))
    return findings


def _err(message: str, workflow_id: str, extra: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "severity": FindingSeverity.ERROR.value,
        "code": "WORKFLOW_STRUCTURE",
        "message": message,
        "workflow_id": workflow_id,
    }
    if extra:
        payload.update(extra)
    return payload


def _has_cycle(entry: str, by_id: dict) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for nxt in by_id[node].next:
            if dfs(nxt):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return dfs(entry)


def _walk(node: str, by_id: dict, seen: set[str]) -> None:
    if node in seen:
        return
    seen.add(node)
    for nxt in by_id[node].next:
        _walk(nxt, by_id, seen)


def _reaches_terminal(node: str, by_id: dict, stack: set[str]) -> bool:
    step = by_id[node]
    if step.kind is StepKind.TERMINAL:
        return True
    if node in stack:
        return False
    stack.add(node)
    try:
        return any(_reaches_terminal(nxt, by_id, stack) for nxt in step.next)
    finally:
        stack.remove(node)


def require_acyclic(workflow: WorkflowDefinition) -> None:
    findings = [f for f in validate_workflow_graph(workflow) if f["severity"] == FindingSeverity.ERROR.value]
    if findings:
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "workflow graph invalid", {"findings": findings})

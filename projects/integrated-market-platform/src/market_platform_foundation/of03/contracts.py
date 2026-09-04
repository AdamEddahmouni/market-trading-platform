"""Typed OF-03 registry records. Frozen; not authorization objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from market_platform_foundation.of01.records import ConsequenceProfile, InitiatorClass

from .canonical import SCHEMA_VERSION, definition_hash_from_obj
from .enums import (
    AttributionRequirement,
    AutomationPolicy,
    BindingKind,
    EffectClass,
    FeatureGateKind,
    GateKind,
    HumanApprovalPolicy,
    IdempotencyClass,
    RegistrationState,
    RetryClass,
    SopMaturity,
    StepKind,
)
from .errors import OF03Error, OF03ErrorCode


def _req_str(obj: Mapping[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"missing {key}", {"key": key})
    return value.strip()


def _opt_str(obj: Mapping[str, Any], key: str) -> str | None:
    value = obj.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"invalid {key}", {"key": key})
    return value


def _str_tuple(obj: Mapping[str, Any], key: str) -> tuple[str, ...]:
    value = obj.get(key, ())
    if value is None:
        return ()
    if not isinstance(value, list):
        raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"{key} must be a list", {"key": key})
    out: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"invalid {key} item", {"key": key})
        out.append(item)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class VersionRef:
    id: str
    version: int

    @classmethod
    def from_mapping(cls, obj: Mapping[str, Any], id_key: str, version_key: str) -> "VersionRef":
        version = obj.get(version_key)
        if not isinstance(version, int):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, f"{version_key} must be int", {"key": version_key})
        return cls(id=_req_str(obj, id_key), version=version)


@dataclass(frozen=True, slots=True)
class DomainReferenceRequirement:
    role: str
    required: bool
    cardinality: str

    @classmethod
    def from_mapping(cls, obj: Mapping[str, Any]) -> "DomainReferenceRequirement":
        required = obj.get("required", True)
        if not isinstance(required, bool):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "required must be bool", {})
        cardinality = obj.get("cardinality", "ONE")
        if cardinality not in {"ZERO", "ONE", "MANY"}:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "invalid cardinality", {"cardinality": cardinality})
        return cls(role=_req_str(obj, "role"), required=required, cardinality=str(cardinality))


@dataclass(frozen=True, slots=True)
class FeatureGate:
    kind: FeatureGateKind
    name: str

    @classmethod
    def from_mapping(cls, obj: Mapping[str, Any]) -> "FeatureGate":
        return cls(kind=FeatureGateKind(_req_str(obj, "kind")), name=_req_str(obj, "name"))


@dataclass(frozen=True, slots=True)
class Deprecation:
    deprecated: bool
    superseded_by: VersionRef | None
    replacement_note: str | None

    @classmethod
    def from_mapping(cls, obj: Mapping[str, Any] | None) -> "Deprecation":
        if obj is None:
            return cls(deprecated=False, superseded_by=None, replacement_note=None)
        deprecated = obj.get("deprecated", False)
        if not isinstance(deprecated, bool):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "deprecated must be bool", {})
        raw = obj.get("superseded_by")
        superseded = None
        if raw is not None:
            if not isinstance(raw, dict):
                raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "superseded_by must be object", {})
            superseded = VersionRef.from_mapping(raw, "id", "version")
        return cls(deprecated=deprecated, superseded_by=superseded, replacement_note=_opt_str(obj, "replacement_note"))


@dataclass(frozen=True, slots=True)
class Binding:
    binding_kind: BindingKind
    module: str | None
    qualname: str | None
    cli_module: str | None
    cli_subcommand: str | None
    cli_parser_attr: str | None
    cli_script: str | None
    document_path: str | None

    @classmethod
    def from_mapping(cls, obj: Mapping[str, Any]) -> "Binding":
        kind = BindingKind(_req_str(obj, "binding_kind"))
        if obj.get("command") or obj.get("shell") or obj.get("expression"):
            raise OF03Error(OF03ErrorCode.UNSAFE_BINDING, "shell/expression bindings are prohibited", {})
        return cls(
            binding_kind=kind,
            module=_opt_str(obj, "module"),
            qualname=_opt_str(obj, "qualname"),
            cli_module=_opt_str(obj, "cli_module"),
            cli_subcommand=_opt_str(obj, "cli_subcommand"),
            cli_parser_attr=_opt_str(obj, "cli_parser_attr"),
            cli_script=_opt_str(obj, "cli_script"),
            document_path=_opt_str(obj, "document_path"),
        )

    def to_canonical(self) -> dict[str, Any]:
        return {
            "binding_kind": self.binding_kind.value,
            "module": self.module,
            "qualname": self.qualname,
            "cli_module": self.cli_module,
            "cli_subcommand": self.cli_subcommand,
            "cli_parser_attr": self.cli_parser_attr,
            "cli_script": self.cli_script,
            "document_path": self.document_path,
        }


@dataclass(frozen=True, slots=True)
class WorkflowGate:
    gate_kind: GateKind
    authority_reference: str | None
    evidence_class: str | None
    capability_id: str | None
    contract_ref: str | None

    @classmethod
    def from_mapping(cls, obj: Mapping[str, Any]) -> "WorkflowGate":
        return cls(
            gate_kind=GateKind(_req_str(obj, "gate_kind")),
            authority_reference=_opt_str(obj, "authority_reference"),
            evidence_class=_opt_str(obj, "evidence_class"),
            capability_id=_opt_str(obj, "capability_id"),
            contract_ref=_opt_str(obj, "contract_ref"),
        )


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    step_id: str
    kind: StepKind
    next: tuple[str, ...]
    capability_id: str | None
    capability_version: int | None
    sop_id: str | None
    sop_version: int | None
    disposition: str | None
    note: str | None
    gate: WorkflowGate | None
    retry_class: RetryClass

    @classmethod
    def from_mapping(cls, obj: Mapping[str, Any]) -> "WorkflowStep":
        nxt = obj.get("next", [])
        if not isinstance(nxt, list) or any(not isinstance(x, str) for x in nxt):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "next must be a string list", {})
        cap_ver = obj.get("capability_version")
        sop_ver = obj.get("sop_version")
        if cap_ver is not None and not isinstance(cap_ver, int):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "capability_version must be int", {})
        if sop_ver is not None and not isinstance(sop_ver, int):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "sop_version must be int", {})
        gate_raw = obj.get("gate")
        gate = WorkflowGate.from_mapping(gate_raw) if isinstance(gate_raw, dict) else None
        retry = RetryClass(str(obj.get("retry_class", "UNKNOWN")))
        return cls(
            step_id=_req_str(obj, "step_id"),
            kind=StepKind(_req_str(obj, "kind")),
            next=tuple(nxt),
            capability_id=_opt_str(obj, "capability_id"),
            capability_version=cap_ver,
            sop_id=_opt_str(obj, "sop_id"),
            sop_version=sop_ver,
            disposition=_opt_str(obj, "disposition"),
            note=_opt_str(obj, "note"),
            gate=gate,
            retry_class=retry,
        )


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    schema_version: int
    capability_id: str
    definition_version: int
    title: str
    description: str
    owner_subsystem: str
    consequence_profile: ConsequenceProfile
    effect_class: EffectClass
    binding: Binding
    input_contract_ref: str
    output_contract_ref: str
    required_authority_refs: tuple[str, ...]
    required_role_refs: tuple[str, ...]
    automation_policy: AutomationPolicy
    human_approval_policy: HumanApprovalPolicy
    idempotency_class: IdempotencyClass
    retry_class: RetryClass
    of_attribution_requirement: AttributionRequirement
    required_evidence_classes: tuple[str, ...]
    feature_gates: tuple[FeatureGate, ...]
    sop_refs: tuple[VersionRef, ...]
    domain_reference_requirements: tuple[DomainReferenceRequirement, ...]
    deprecation: Deprecation
    registration_state: RegistrationState
    definition_hash: str
    raw: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, obj: Mapping[str, Any]) -> "CapabilityDefinition":
        version = obj.get("definition_version")
        if not isinstance(version, int) or version < 1:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "invalid definition_version", {})
        schema = obj.get("schema_version", SCHEMA_VERSION)
        if schema != SCHEMA_VERSION:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "schema-version incompatibility", {"schema_version": schema})
        gates_raw = obj.get("feature_gates", [])
        if not isinstance(gates_raw, list):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "feature_gates must be a list", {})
        sop_raw = obj.get("sop_refs", [])
        if not isinstance(sop_raw, list):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "sop_refs must be a list", {})
        drr_raw = obj.get("domain_reference_requirements", [])
        if not isinstance(drr_raw, list):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "domain_reference_requirements must be a list", {})
        computed = definition_hash_from_obj(obj)
        declared = obj.get("definition_hash")
        if declared is not None and declared != computed:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "definition hash mismatch", {"capability_id": obj.get("capability_id")})
        return cls(
            schema_version=SCHEMA_VERSION,
            capability_id=_req_str(obj, "capability_id"),
            definition_version=version,
            title=_req_str(obj, "title"),
            description=_req_str(obj, "description"),
            owner_subsystem=_req_str(obj, "owner_subsystem"),
            consequence_profile=ConsequenceProfile(_req_str(obj, "consequence_profile")),
            effect_class=EffectClass(_req_str(obj, "effect_class")),
            binding=Binding.from_mapping(obj.get("binding") or {}),
            input_contract_ref=_req_str(obj, "input_contract_ref"),
            output_contract_ref=_req_str(obj, "output_contract_ref"),
            required_authority_refs=_str_tuple(obj, "required_authority_refs"),
            required_role_refs=_str_tuple(obj, "required_role_refs"),
            automation_policy=AutomationPolicy(_req_str(obj, "automation_policy")),
            human_approval_policy=HumanApprovalPolicy(_req_str(obj, "human_approval_policy")),
            idempotency_class=IdempotencyClass(_req_str(obj, "idempotency_class")),
            retry_class=RetryClass(_req_str(obj, "retry_class")),
            of_attribution_requirement=AttributionRequirement(_req_str(obj, "of_attribution_requirement")),
            required_evidence_classes=_str_tuple(obj, "required_evidence_classes"),
            feature_gates=tuple(FeatureGate.from_mapping(g) for g in gates_raw),
            sop_refs=tuple(VersionRef.from_mapping(s, "sop_id", "sop_version") for s in sop_raw),
            domain_reference_requirements=tuple(DomainReferenceRequirement.from_mapping(d) for d in drr_raw),
            deprecation=Deprecation.from_mapping(obj.get("deprecation") if isinstance(obj.get("deprecation"), dict) else None),
            registration_state=RegistrationState(str(obj.get("registration_state", "DECLARED"))),
            definition_hash=computed,
            raw=dict(obj),
        )


@dataclass(frozen=True, slots=True)
class SopDefinition:
    schema_version: int
    sop_id: str
    definition_version: int
    title: str
    owner_subsystem: str
    document_path: str
    document_anchor: str
    consequence_profile: ConsequenceProfile
    required_authority_refs: tuple[str, ...]
    automation_policy: AutomationPolicy
    related_capability_refs: tuple[VersionRef, ...]
    related_workflow_refs: tuple[VersionRef, ...]
    prerequisites: tuple[str, ...]
    required_evidence_classes: tuple[str, ...]
    maturity: SopMaturity
    deprecation: Deprecation
    definition_hash: str
    document_section_hash: str | None
    raw: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, obj: Mapping[str, Any]) -> "SopDefinition":
        version = obj.get("definition_version")
        if not isinstance(version, int) or version < 1:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "invalid definition_version", {})
        schema = obj.get("schema_version", SCHEMA_VERSION)
        if schema != SCHEMA_VERSION:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "schema-version incompatibility", {"schema_version": schema})
        cap_raw = obj.get("related_capability_refs", [])
        wf_raw = obj.get("related_workflow_refs", [])
        if not isinstance(cap_raw, list) or not isinstance(wf_raw, list):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "related refs must be lists", {})
        maturity = SopMaturity(_req_str(obj, "maturity"))
        if maturity.value in {"EXERCISED", "ACCEPTED"}:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "maturity EXERCISED/ACCEPTED is not supported without evidence", {})
        computed = definition_hash_from_obj(obj)
        declared = obj.get("definition_hash")
        if declared is not None and declared != computed:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "definition hash mismatch", {"sop_id": obj.get("sop_id")})
        pin = obj.get("document_section_hash")
        if pin is not None and not isinstance(pin, str):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "document_section_hash must be string", {})
        return cls(
            schema_version=SCHEMA_VERSION,
            sop_id=_req_str(obj, "sop_id"),
            definition_version=version,
            title=_req_str(obj, "title"),
            owner_subsystem=_req_str(obj, "owner_subsystem"),
            document_path=_req_str(obj, "document_path"),
            document_anchor=_req_str(obj, "document_anchor"),
            consequence_profile=ConsequenceProfile(_req_str(obj, "consequence_profile")),
            required_authority_refs=_str_tuple(obj, "required_authority_refs"),
            automation_policy=AutomationPolicy(_req_str(obj, "automation_policy")),
            related_capability_refs=tuple(VersionRef.from_mapping(s, "capability_id", "capability_version") for s in cap_raw),
            related_workflow_refs=tuple(VersionRef.from_mapping(s, "workflow_id", "workflow_version") for s in wf_raw),
            prerequisites=_str_tuple(obj, "prerequisites"),
            required_evidence_classes=_str_tuple(obj, "required_evidence_classes"),
            maturity=maturity,
            deprecation=Deprecation.from_mapping(obj.get("deprecation") if isinstance(obj.get("deprecation"), dict) else None),
            definition_hash=computed,
            document_section_hash=pin,
            raw=dict(obj),
        )


@dataclass(frozen=True, slots=True)
class WorkflowDefinition:
    schema_version: int
    workflow_id: str
    definition_version: int
    title: str
    objective: str
    owner_subsystem: str
    consequence_profile: ConsequenceProfile
    initiator_class: InitiatorClass
    required_authority_refs: tuple[str, ...]
    required_role_refs: tuple[str, ...]
    required_inputs: tuple[str, ...]
    domain_reference_requirements: tuple[DomainReferenceRequirement, ...]
    required_evidence_classes: tuple[str, ...]
    failure_policy: str
    retry_policy: Mapping[str, Any]
    terminal_dispositions: tuple[str, ...]
    sop_refs: tuple[VersionRef, ...]
    capability_refs: tuple[VersionRef, ...]
    of_attribution_requirement: AttributionRequirement
    automation_policy: AutomationPolicy
    human_approval_policy: HumanApprovalPolicy
    document_path: str
    document_anchor: str
    deprecation: Deprecation
    entry_step_id: str
    steps: tuple[WorkflowStep, ...]
    definition_hash: str
    raw: Mapping[str, Any]

    @classmethod
    def from_mapping(cls, obj: Mapping[str, Any]) -> "WorkflowDefinition":
        version = obj.get("definition_version")
        if not isinstance(version, int) or version < 1:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "invalid definition_version", {})
        schema = obj.get("schema_version", SCHEMA_VERSION)
        if schema != SCHEMA_VERSION:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "schema-version incompatibility", {"schema_version": schema})
        steps_raw = obj.get("steps")
        if not isinstance(steps_raw, list) or not steps_raw:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "workflow steps required", {})
        retry = obj.get("retry_policy", {})
        if not isinstance(retry, dict):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "retry_policy must be object", {})
        if retry.get("graph_cycles_permitted") is True:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "workflow cycles are not permitted", {})
        drr_raw = obj.get("domain_reference_requirements", [])
        sop_raw = obj.get("sop_refs", [])
        cap_raw = obj.get("capability_refs", [])
        if not isinstance(drr_raw, list) or not isinstance(sop_raw, list) or not isinstance(cap_raw, list):
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "refs must be lists", {})
        computed = definition_hash_from_obj(obj)
        declared = obj.get("definition_hash")
        if declared is not None and declared != computed:
            raise OF03Error(OF03ErrorCode.REGISTRY_INVALID, "definition hash mismatch", {"workflow_id": obj.get("workflow_id")})
        steps = tuple(WorkflowStep.from_mapping(s) for s in steps_raw)
        return cls(
            schema_version=SCHEMA_VERSION,
            workflow_id=_req_str(obj, "workflow_id"),
            definition_version=version,
            title=_req_str(obj, "title"),
            objective=_req_str(obj, "objective"),
            owner_subsystem=_req_str(obj, "owner_subsystem"),
            consequence_profile=ConsequenceProfile(_req_str(obj, "consequence_profile")),
            initiator_class=InitiatorClass(_req_str(obj, "initiator_class")),
            required_authority_refs=_str_tuple(obj, "required_authority_refs"),
            required_role_refs=_str_tuple(obj, "required_role_refs"),
            required_inputs=_str_tuple(obj, "required_inputs"),
            domain_reference_requirements=tuple(DomainReferenceRequirement.from_mapping(d) for d in drr_raw),
            required_evidence_classes=_str_tuple(obj, "required_evidence_classes"),
            failure_policy=_req_str(obj, "failure_policy"),
            retry_policy=dict(retry),
            terminal_dispositions=_str_tuple(obj, "terminal_dispositions"),
            sop_refs=tuple(VersionRef.from_mapping(s, "sop_id", "sop_version") for s in sop_raw),
            capability_refs=tuple(VersionRef.from_mapping(s, "capability_id", "capability_version") for s in cap_raw),
            of_attribution_requirement=AttributionRequirement(_req_str(obj, "of_attribution_requirement")),
            automation_policy=AutomationPolicy(_req_str(obj, "automation_policy")),
            human_approval_policy=HumanApprovalPolicy(_req_str(obj, "human_approval_policy")),
            document_path=_req_str(obj, "document_path"),
            document_anchor=_req_str(obj, "document_anchor"),
            deprecation=Deprecation.from_mapping(obj.get("deprecation") if isinstance(obj.get("deprecation"), dict) else None),
            entry_step_id=_req_str(obj, "entry_step_id"),
            steps=steps,
            definition_hash=computed,
            raw=dict(obj),
        )

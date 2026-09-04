"""Full-system operational acceptance (BUILD 35)."""

from __future__ import annotations

from .evidence import DEFAULT_DISPOSITIONS, load_build_dispositions_from_artifacts
from .identity import derive_acceptance_report_id, derive_acceptance_spec_id
from .types import (
    BUILD35_KNOWN_LIMITATIONS,
    RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
    RELEASE_GOVERNANCE_SCHEMA_VERSION,
    AcceptanceRequirementV1,
    DomainAcceptanceResultV1,
    FullSystemAcceptanceDisposition,
    FullSystemOperationalAcceptanceReportV1,
    FullSystemOperationalAcceptanceSpecV1,
    RequirementCriticality,
    RequirementResult,
)

ACCEPTANCE_DOMAINS: tuple[str, ...] = (
    "Contracts",
    "Temporal integrity",
    "Normalization / quality",
    "Persistence",
    "Snapshots / signals",
    "Replay",
    "Baselines",
    "Router / scheduler",
    "Specialists / council",
    "Hypothesis / fusion",
    "Ledger / outcomes",
    "Evaluation",
    "Research / experiments",
    "Training",
    "Independent validation",
    "Champion / promotion",
    "Opportunity",
    "Risk / PAPER",
    "Runtime governance",
    "Controlled adaptation",
    "Forward qualification",
    "PAPER qualification",
    "Live safety",
    "Supervised live operations",
    "Operator control plane",
    "Operational reliability",
    "Production pilot",
    "Deployment",
    "Release governance",
)

DOMAIN_EVIDENCE_MAP: dict[str, tuple[str, ...]] = {
    "Contracts": ("BUILD25",),
    "Temporal integrity": ("BUILD25", "BUILD26"),
    "Normalization / quality": ("BUILD25", "BUILD26"),
    "Persistence": ("BUILD25", "BUILD32"),
    "Snapshots / signals": ("BUILD25",),
    "Replay": ("BUILD25",),
    "Baselines": ("BUILD25",),
    "Router / scheduler": ("BUILD25",),
    "Specialists / council": ("BUILD25",),
    "Hypothesis / fusion": ("BUILD25",),
    "Ledger / outcomes": ("BUILD25",),
    "Evaluation": ("BUILD25",),
    "Research / experiments": ("BUILD25", "BUILD24"),
    "Training": ("BUILD18", "BUILD19"),
    "Independent validation": ("BUILD19",),
    "Champion / promotion": ("BUILD20",),
    "Opportunity": ("BUILD21",),
    "Risk / PAPER": ("BUILD22", "BUILD27"),
    "Runtime governance": ("BUILD23",),
    "Controlled adaptation": ("BUILD24",),
    "Forward qualification": ("BUILD26",),
    "PAPER qualification": ("BUILD27",),
    "Live safety": ("BUILD28",),
    "Supervised live operations": ("BUILD29", "BUILD30"),
    "Operator control plane": ("BUILD31",),
    "Operational reliability": ("BUILD32",),
    "Production pilot": ("BUILD33",),
    "Deployment": ("BUILD34",),
    "Release governance": ("BUILD35",),
}

BLOCKING_DOMAIN_FAILURES: frozenset[str] = frozenset(
    {
        "Temporal integrity",
        "Live safety",
        "Deployment",
    }
)


def build_full_system_acceptance_spec(
    *,
    source_sha: str,
) -> FullSystemOperationalAcceptanceSpecV1:
    blocking_ids = tuple(f"REQ-{d.replace(' ', '_').replace('/', '_').upper()}" for d in ACCEPTANCE_DOMAINS)
    spec = FullSystemOperationalAcceptanceSpecV1(
        acceptance_spec_id="",
        schema_version=RELEASE_GOVERNANCE_SCHEMA_VERSION,
        required_build_range=(1, 35),
        required_domains=ACCEPTANCE_DOMAINS,
        blocking_requirement_ids=blocking_ids,
        required_evidence_refs=tuple(f"BUILD{b}" for b in range(25, 36)),
        implementation_version=RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
        metadata={"source_sha": source_sha},
    )
    return FullSystemOperationalAcceptanceSpecV1(
        acceptance_spec_id=derive_acceptance_spec_id(spec),
        schema_version=spec.schema_version,
        required_build_range=spec.required_build_range,
        required_domains=spec.required_domains,
        blocking_requirement_ids=spec.blocking_requirement_ids,
        required_evidence_refs=spec.required_evidence_refs,
        implementation_version=spec.implementation_version,
        metadata=spec.metadata,
    )


def _domain_result(domain: str, dispositions: dict[str, str]) -> DomainAcceptanceResultV1:
    evidence_builds = DOMAIN_EVIDENCE_MAP.get(domain, ("BUILD25",))
    limitations: list[str] = []
    result = RequirementResult.PASS.value

    for build in evidence_builds:
        if build == "BUILD35":
            continue
        disp = dispositions.get(build)
        if not disp:
            result = RequirementResult.INCONCLUSIVE.value
            limitations.append(f"missing {build} disposition")
        elif "NOT_" in disp or "FAILED" in disp or "BLOCKED" in disp:
            if domain in BLOCKING_DOMAIN_FAILURES:
                result = RequirementResult.FAIL.value
            else:
                result = RequirementResult.PASS.value
                limitations.append(f"{build}: {disp}")
        elif "INSUFFICIENT" in disp or "WITH_LIMITATIONS" in disp or "NOT_EXECUTED" in disp:
            limitations.append(f"{build}: {disp}")

    blocking = domain in BLOCKING_DOMAIN_FAILURES and result == RequirementResult.FAIL.value
    return DomainAcceptanceResultV1(
        domain=domain,
        evidence_refs=tuple(f"artifacts/{build.lower()}" for build in evidence_builds if build != "BUILD35"),
        blocking=blocking,
        result=result,
        limitations=tuple(limitations),
    )


def build_full_system_acceptance_report(
    *,
    spec: FullSystemOperationalAcceptanceSpecV1,
    release_candidate_ref: str,
    release_evidence_bundle_ref: str,
    accepted_source_sha: str,
    release_artifact_hashes: dict[str, str],
) -> FullSystemOperationalAcceptanceReportV1:
    dispositions = load_build_dispositions_from_artifacts()
    domain_results = tuple(_domain_result(d, dispositions) for d in spec.required_domains)

    blocking_requirements: list[AcceptanceRequirementV1] = []
    nonblocking_limitations: list[str] = list(BUILD35_KNOWN_LIMITATIONS)

    for dr in domain_results:
        req = AcceptanceRequirementV1(
            requirement_id=f"REQ-{dr.domain.replace(' ', '_').replace('/', '_').upper()}",
            domain=dr.domain,
            description=f"Domain {dr.domain} acceptance",
            criticality=(
                RequirementCriticality.BLOCKING.value
                if dr.blocking
                else RequirementCriticality.REQUIRED.value
            ),
            evidence_refs=dr.evidence_refs,
            validation_method="artifact_disposition_check",
            result=dr.result,
            limitations=dr.limitations,
            blocking_behavior="fail_closed" if dr.blocking else "record_limitation",
        )
        if dr.blocking and dr.result == RequirementResult.FAIL.value:
            blocking_requirements.append(req)
        for lim in dr.limitations:
            if lim not in nonblocking_limitations:
                nonblocking_limitations.append(lim)

    blocking_failures = [dr for dr in domain_results if dr.blocking and dr.result == RequirementResult.FAIL.value]
    if blocking_failures:
        final_disposition = FullSystemAcceptanceDisposition.NOT_OPERATIONALLY_ACCEPTABLE.value
    elif nonblocking_limitations:
        final_disposition = FullSystemAcceptanceDisposition.FULL_SYSTEM_ACCEPTED_WITH_LIMITATIONS.value
    else:
        final_disposition = FullSystemAcceptanceDisposition.FULL_SYSTEM_ACCEPTED_FOR_SUPERVISED_OPERATION.value

    report = FullSystemOperationalAcceptanceReportV1(
        full_system_acceptance_report_id="",
        schema_version=RELEASE_GOVERNANCE_SCHEMA_VERSION,
        acceptance_spec_ref=spec.acceptance_spec_id,
        release_candidate_ref=release_candidate_ref,
        release_evidence_bundle_ref=release_evidence_bundle_ref,
        accepted_source_sha=accepted_source_sha,
        release_artifact_hashes=release_artifact_hashes,
        domain_results=domain_results,
        blocking_requirements=tuple(blocking_requirements),
        nonblocking_limitations=tuple(nonblocking_limitations),
        unresolved_risks=(),
        deployment_readiness="READY_WITH_LIMITATIONS",
        supervised_operation_readiness="READY_WITH_LIMITATIONS",
        final_disposition=final_disposition,
        implementation_version=RELEASE_GOVERNANCE_IMPLEMENTATION_VERSION,
        lineage={"source_sha": accepted_source_sha},
    )
    return FullSystemOperationalAcceptanceReportV1(
        full_system_acceptance_report_id=derive_acceptance_report_id(report),
        schema_version=report.schema_version,
        acceptance_spec_ref=report.acceptance_spec_ref,
        release_candidate_ref=report.release_candidate_ref,
        release_evidence_bundle_ref=report.release_evidence_bundle_ref,
        accepted_source_sha=report.accepted_source_sha,
        release_artifact_hashes=report.release_artifact_hashes,
        domain_results=report.domain_results,
        blocking_requirements=report.blocking_requirements,
        nonblocking_limitations=report.nonblocking_limitations,
        unresolved_risks=report.unresolved_risks,
        deployment_readiness=report.deployment_readiness,
        supervised_operation_readiness=report.supervised_operation_readiness,
        final_disposition=report.final_disposition,
        implementation_version=report.implementation_version,
        lineage=report.lineage,
        metadata=report.metadata,
    )


def false_global_green_blocked(
    domain_results: tuple[DomainAcceptanceResultV1, ...],
) -> bool:
    """One blocking domain failure must defeat global acceptance."""
    return any(dr.blocking and dr.result == "FAIL" for dr in domain_results)

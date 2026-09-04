"""Service supervision (BUILD 34)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .identity import derive_service_definition_id, derive_service_graph_id
from .types import (
    DEPLOYMENT_IMPLEMENTATION_VERSION,
    DEPLOYMENT_SCHEMA_VERSION,
    RestartPolicy,
    ServiceCriticality,
    ServiceDefinitionV1,
    ServiceDesiredState,
    ServiceGraphV1,
    ServiceSupervisorStatusV1,
)

CRASH_LOOP_THRESHOLD = 5
RESTART_BACKOFF_NS = 5_000_000_000


@dataclass
class FixtureServiceSupervisor:
    """In-memory service supervisor for qualification fixtures."""

    services: dict[str, ServiceSupervisorStatusV1] = field(default_factory=dict)
    _crash_counts: dict[str, int] = field(default_factory=dict)
    _live_authority_restored: bool = False

    def register(self, defn: ServiceDefinitionV1) -> None:
        self.services[defn.service_id] = ServiceSupervisorStatusV1(
            service_id=defn.service_id,
            schema_version=DEPLOYMENT_SCHEMA_VERSION,
            desired_state=ServiceDesiredState.STOPPED.value,
            observed_state=ServiceDesiredState.STOPPED.value,
            process_ref=None,
            release_ref="",
            start_time_ns=None,
            restart_count=0,
            liveness="UNKNOWN",
            readiness="NOT_READY",
            last_failure=None,
            criticality=defn.criticality,
            implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
        )

    def start_service(
        self,
        service_id: str,
        *,
        release_ref: str,
        start_time_ns: int,
        dependencies_ready: bool = True,
    ) -> tuple[bool, str]:
        if service_id not in self.services:
            return False, "unknown service"
        if not dependencies_ready:
            return False, "dependencies not ready"
        status = self.services[service_id]
        self.services[service_id] = ServiceSupervisorStatusV1(
            service_id=status.service_id,
            schema_version=status.schema_version,
            desired_state=ServiceDesiredState.RUNNING.value,
            observed_state=ServiceDesiredState.RUNNING.value,
            process_ref=f"pid-fixture-{service_id}",
            release_ref=release_ref,
            start_time_ns=start_time_ns,
            restart_count=status.restart_count,
            liveness="HEALTHY",
            readiness="NOT_READY",
            last_failure=status.last_failure,
            criticality=status.criticality,
            implementation_version=status.implementation_version,
        )
        return True, "started blocked — readiness false until reconciliation"

    def mark_ready(self, service_id: str) -> None:
        status = self.services[service_id]
        self.services[service_id] = ServiceSupervisorStatusV1(
            service_id=status.service_id,
            schema_version=status.schema_version,
            desired_state=status.desired_state,
            observed_state=status.observed_state,
            process_ref=status.process_ref,
            release_ref=status.release_ref,
            start_time_ns=status.start_time_ns,
            restart_count=status.restart_count,
            liveness=status.liveness,
            readiness="READY",
            last_failure=status.last_failure,
            criticality=status.criticality,
            implementation_version=status.implementation_version,
        )

    def crash_service(self, service_id: str, reason: str) -> None:
        status = self.services[service_id]
        count = self._crash_counts.get(service_id, 0) + 1
        self._crash_counts[service_id] = count
        self.services[service_id] = ServiceSupervisorStatusV1(
            service_id=status.service_id,
            schema_version=status.schema_version,
            desired_state=ServiceDesiredState.RUNNING.value,
            observed_state=ServiceDesiredState.CRASHED.value,
            process_ref=None,
            release_ref=status.release_ref,
            start_time_ns=status.start_time_ns,
            restart_count=status.restart_count + 1,
            liveness="UNHEALTHY",
            readiness="NOT_READY",
            last_failure=reason,
            criticality=status.criticality,
            implementation_version=status.implementation_version,
        )

    def restart_service(self, service_id: str, *, start_time_ns: int) -> tuple[bool, str]:
        if self.is_crash_loop(service_id):
            return False, "crash loop detected"
        self._live_authority_restored = False
        return self.start_service(service_id, release_ref=self.services[service_id].release_ref, start_time_ns=start_time_ns)

    def is_crash_loop(self, service_id: str) -> bool:
        return self._crash_counts.get(service_id, 0) >= CRASH_LOOP_THRESHOLD

    def graceful_shutdown(self, service_id: str, *, timeout_ns: int, elapsed_ns: int) -> str:
        if elapsed_ns > timeout_ns:
            return "FORCED_TERMINATION"
        status = self.services[service_id]
        self.services[service_id] = ServiceSupervisorStatusV1(
            service_id=status.service_id,
            schema_version=status.schema_version,
            desired_state=ServiceDesiredState.STOPPED.value,
            observed_state=ServiceDesiredState.STOPPED.value,
            process_ref=None,
            release_ref=status.release_ref,
            start_time_ns=status.start_time_ns,
            restart_count=status.restart_count,
            liveness="STOPPED",
            readiness="NOT_READY",
            last_failure=status.last_failure,
            criticality=status.criticality,
            implementation_version=status.implementation_version,
        )
        return "GRACEFUL"

    def restart_restores_live_authority(self) -> bool:
        return self._live_authority_restored


def build_default_service_graph(environment_ref: str) -> ServiceGraphV1:
    services = []
    specs = [
        ("operator-api", "python tools/ui1/run_ui_api.py", (), ServiceCriticality.CRITICAL.value),
        ("market-data-runtime", "python -m market_platform_foundation.intelligence", ("operator-api",), ServiceCriticality.REQUIRED.value),
        ("intelligence-runtime", "python -m market_platform_foundation.intelligence", ("market-data-runtime",), ServiceCriticality.REQUIRED.value),
        ("reconciliation-worker", "python -m market_platform_foundation.intelligence.live_canary.reconciliation", ("intelligence-runtime",), ServiceCriticality.CRITICAL.value),
    ]
    for svc_id, cmd, deps, crit in specs:
        defn = ServiceDefinitionV1(
            service_id=svc_id,
            schema_version=DEPLOYMENT_SCHEMA_VERSION,
            command=cmd,
            working_directory=".",
            environment_manifest_ref=environment_ref,
            dependencies=deps,
            restart_policy=RestartPolicy.ON_FAILURE.value,
            startup_timeout_ns=60_000_000_000,
            shutdown_timeout_ns=30_000_000_000,
            liveness_probe="heartbeat",
            readiness_probe="reconciliation_clean",
            criticality=crit,
            log_location=f"logs/{svc_id}.log",
            implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
        )
        services.append(
            ServiceDefinitionV1(
                service_id=defn.service_id,
                schema_version=defn.schema_version,
                command=defn.command,
                working_directory=defn.working_directory,
                environment_manifest_ref=defn.environment_manifest_ref,
                dependencies=defn.dependencies,
                restart_policy=defn.restart_policy,
                startup_timeout_ns=defn.startup_timeout_ns,
                shutdown_timeout_ns=defn.shutdown_timeout_ns,
                liveness_probe=defn.liveness_probe,
                readiness_probe=defn.readiness_probe,
                criticality=defn.criticality,
                log_location=defn.log_location,
                implementation_version=defn.implementation_version,
                metadata={"derived_id": derive_service_definition_id(defn)},
            )
        )
    startup_order = ("operator-api", "market-data-runtime", "intelligence-runtime", "reconciliation-worker")
    graph = ServiceGraphV1(
        service_graph_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        services=tuple(services),
        startup_order=startup_order,
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
    )
    return ServiceGraphV1(
        service_graph_id=derive_service_graph_id(graph),
        schema_version=graph.schema_version,
        services=graph.services,
        startup_order=graph.startup_order,
        implementation_version=graph.implementation_version,
    )


def validate_startup_order(graph: ServiceGraphV1) -> tuple[bool, tuple[str, ...]]:
    violations: list[str] = []
    service_ids = {s.service_id for s in graph.services}
    seen: set[str] = set()
    for svc_id in graph.startup_order:
        if svc_id not in service_ids:
            violations.append(f"startup order references unknown service: {svc_id}")
        defn = next(s for s in graph.services if s.service_id == svc_id)
        for dep in defn.dependencies:
            if dep not in seen:
                violations.append(f"service {svc_id} starts before dependency {dep}")
        seen.add(svc_id)
    recon_idx = graph.startup_order.index("reconciliation-worker") if "reconciliation-worker" in graph.startup_order else -1
    intel_idx = graph.startup_order.index("intelligence-runtime") if "intelligence-runtime" in graph.startup_order else -1
    if recon_idx >= 0 and intel_idx >= 0 and recon_idx < intel_idx:
        violations.append("reconciliation must start after intelligence-runtime")
    return len(violations) == 0, tuple(violations)

"""Persistence health assessment (BUILD 32)."""

from __future__ import annotations

from .identity import derive_persistence_health_id
from .types import (
    OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
    ComponentSignalState,
    PersistenceHealthSnapshotV1,
)


def assess_persistence_health(
    *,
    as_of_ns: int,
    backend: str = "in_memory",
    connection_ready: bool = True,
    write_healthy: bool = True,
    read_healthy: bool = True,
    schema_compatible: bool = True,
    last_successful_write_ns: int | None = None,
    last_successful_read_ns: int | None = None,
    write_errors: int = 0,
    read_errors: int = 0,
    source_refs: tuple[str, ...] = (),
) -> PersistenceHealthSnapshotV1:
    """Assess canonical persistence health; failure blocks new live submissions."""
    if not connection_ready or not write_healthy or not read_healthy or not schema_compatible:
        disposition = ComponentSignalState.CRITICAL.value
        blocking = True
    elif write_errors > 0 or read_errors > 0:
        disposition = ComponentSignalState.WARNING.value
        blocking = write_errors > 0
    else:
        disposition = ComponentSignalState.HEALTHY.value
        blocking = False

    snapshot = PersistenceHealthSnapshotV1(
        snapshot_id="",
        schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
        as_of_ns=as_of_ns,
        backend=backend,
        connection_ready=connection_ready,
        write_healthy=write_healthy,
        read_healthy=read_healthy,
        schema_compatible=schema_compatible,
        last_successful_write_ns=last_successful_write_ns,
        last_successful_read_ns=last_successful_read_ns,
        write_errors=write_errors,
        read_errors=read_errors,
        disposition=disposition,
        blocking_live=blocking,
        source_refs=source_refs,
    )
    return PersistenceHealthSnapshotV1(
        snapshot_id=derive_persistence_health_id(snapshot),
        schema_version=snapshot.schema_version,
        as_of_ns=snapshot.as_of_ns,
        backend=snapshot.backend,
        connection_ready=snapshot.connection_ready,
        write_healthy=snapshot.write_healthy,
        read_healthy=snapshot.read_healthy,
        schema_compatible=snapshot.schema_compatible,
        last_successful_write_ns=snapshot.last_successful_write_ns,
        last_successful_read_ns=snapshot.last_successful_read_ns,
        write_errors=snapshot.write_errors,
        read_errors=snapshot.read_errors,
        disposition=snapshot.disposition,
        blocking_live=snapshot.blocking_live,
        source_refs=snapshot.source_refs,
        metadata=snapshot.metadata,
    )

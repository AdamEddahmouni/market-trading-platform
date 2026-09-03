"""Schema migration plans (BUILD 34)."""

from __future__ import annotations

from .identity import derive_migration_plan_id
from .types import (
    DEPLOYMENT_IMPLEMENTATION_VERSION,
    DEPLOYMENT_SCHEMA_VERSION,
    MigrationPlanV1,
)

CURRENT_SCHEMA = "intelligence-v1"
NEXT_SCHEMA = "intelligence-v1"


def build_migration_plan(
    *,
    from_schema: str = CURRENT_SCHEMA,
    to_schema: str = NEXT_SCHEMA,
    rollback_supported: bool = True,
) -> MigrationPlanV1:
    destructive = from_schema != to_schema and not rollback_supported
    plan = MigrationPlanV1(
        migration_plan_id="",
        schema_version=DEPLOYMENT_SCHEMA_VERSION,
        from_schema=from_schema,
        to_schema=to_schema,
        forward_steps=("backup_verified", "apply_migration", "validate_schema"),
        compatibility_window="expand-contract",
        rollback_supported=rollback_supported,
        backup_prerequisite=destructive or from_schema != to_schema,
        validation_checks=("schema_version_match", "index_compatibility"),
        data_loss_risk="NONE" if from_schema == to_schema else "LOW",
        implementation_version=DEPLOYMENT_IMPLEMENTATION_VERSION,
    )
    return MigrationPlanV1(
        migration_plan_id=derive_migration_plan_id(plan),
        schema_version=plan.schema_version,
        from_schema=plan.from_schema,
        to_schema=plan.to_schema,
        forward_steps=plan.forward_steps,
        compatibility_window=plan.compatibility_window,
        rollback_supported=plan.rollback_supported,
        backup_prerequisite=plan.backup_prerequisite,
        validation_checks=plan.validation_checks,
        data_loss_risk=plan.data_loss_risk,
        implementation_version=plan.implementation_version,
    )


def destructive_migration_without_backup_blocked(
    plan: MigrationPlanV1,
    *,
    backup_verified: bool,
) -> tuple[bool, str]:
    if plan.data_loss_risk != "NONE" and plan.backup_prerequisite and not backup_verified:
        return True, "destructive migration requires verified backup"
    return False, "OK"


def rollback_compatible(plan: MigrationPlanV1) -> bool:
    return plan.rollback_supported

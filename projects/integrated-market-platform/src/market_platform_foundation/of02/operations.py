"""Structured OF-02 operator capabilities. No workflow engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .config import ADAPTER_IDS, load_all_configs, load_adapter_config
from .gateway import LedgerWriter

CAPABILITY_IDS = frozenset(
    {
        "OF02.OP.STATUS",
        "OF02.OP.ADAPTER_STATUS",
        "OF02.OP.RETROSPECTIVE_DRY_RUN",
        "OF02.OP.RETROSPECTIVE_EXECUTE",
        "OF02.OP.RETROSPECTIVE_RESUME",
        "OF02.OP.RESOLVE_CONFLICT",
        "OF02.OP.RECONCILE",
        "OF02.OP.ENABLEMENT_INSPECT",
    }
)


@dataclass(frozen=True, slots=True)
class OperationResult:
    outcome_code: str
    verification: Mapping[str, Any]


def adapter_status_payload(*, writer: LedgerWriter | None = None, last_error: str | None = None) -> dict[str, Any]:
    adapters = []
    for config in load_all_configs():
        adapters.append(
            {
                "adapter_id": config.adapter_id,
                "enabled": config.enabled,
                "mode": "native+retrospective" if config.retrospective_supported else "native",
                "native_attribution_supported": config.native_supported,
                "retrospective_indexing_supported": config.retrospective_supported,
                "of_writer_ready": writer is not None,
                "last_success": None,
                "last_error": last_error,
            }
        )
    return {"adapters": adapters, "global_enabled_flag": "IMP_OF02_ENABLED"}


def execute(capability_id: str, *, writer: LedgerWriter | None = None, arguments: Mapping[str, Any] | None = None) -> OperationResult:
    if capability_id not in CAPABILITY_IDS:
        return OperationResult(outcome_code="UNKNOWN_CAPABILITY", verification={"capability_id": capability_id})
    arguments = arguments or {}
    if capability_id in {"OF02.OP.STATUS", "OF02.OP.ADAPTER_STATUS", "OF02.OP.ENABLEMENT_INSPECT"}:
        return OperationResult(outcome_code="OK", verification=adapter_status_payload(writer=writer))
    if capability_id in {
        "OF02.OP.RETROSPECTIVE_DRY_RUN",
        "OF02.OP.RETROSPECTIVE_EXECUTE",
        "OF02.OP.RETROSPECTIVE_RESUME",
    }:
        from pathlib import Path

        from .retrospective import index_sources

        paths = [Path(item) for item in arguments.get("paths", ())]
        dry_run = capability_id == "OF02.OP.RETROSPECTIVE_DRY_RUN" or bool(arguments.get("dry_run"))
        batch = index_sources(paths, writer=writer, dry_run=dry_run, enabled=True)
        return OperationResult(
            outcome_code="OK",
            verification={
                "discovered": batch.discovered,
                "eligible": batch.eligible,
                "indexed": batch.indexed,
                "already_indexed": batch.already_indexed,
                "legacy_partial": batch.legacy_partial,
                "skipped": batch.skipped,
                "conflicted": batch.conflicted,
                "failed": batch.failed,
                "dry_run": batch.dry_run,
            },
        )
    if capability_id == "OF02.OP.RESOLVE_CONFLICT":
        return OperationResult(
            outcome_code="OK",
            verification={"action": "do_not_rewrite", "guidance": "preserve existing OF records; index new source identity if content hash changed"},
        )
    if capability_id == "OF02.OP.RECONCILE":
        return OperationResult(
            outcome_code="OK",
            verification={"domain_result_authoritative": True, "of_records_attribution_only": True},
        )
    return OperationResult(outcome_code="OK", verification={})


def inspect_enablement(adapter_id: str) -> dict[str, Any]:
    config = load_adapter_config(adapter_id)
    return {
        "adapter_id": adapter_id,
        "enabled": config.enabled,
        "known": adapter_id in ADAPTER_IDS,
    }

"""Explicit OF-02 adapter enablement. Default is disabled."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ADAPTER_IDS = (
    "validation",
    "benchmark",
    "provider_smoke",
    "research",
    "training",
    "evaluation",
    "promotion",
    "drift",
    "operational_drill",
    "retrospective",
)


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class AdapterConfig:
    enabled: bool
    adapter_id: str
    native_supported: bool
    retrospective_supported: bool
    db_path: Path | None
    cas_root: Path | None
    authority_id: str | None

    def is_enabled(self) -> bool:
        return self.enabled


def load_adapter_config(adapter_id: str) -> AdapterConfig:
    global_on = _flag("IMP_OF02_ENABLED", False)
    specific = _flag(f"IMP_OF02_ADAPTER_{adapter_id.upper()}", False)
    db = os.environ.get("IMP_OF02_LEDGER_DB")
    cas = os.environ.get("IMP_OF02_CAS_ROOT")
    authority = os.environ.get("IMP_OF02_LEDGER_AUTHORITY")
    return AdapterConfig(
        enabled=global_on and specific,
        adapter_id=adapter_id,
        native_supported=True,
        retrospective_supported=adapter_id in {"validation", "benchmark", "provider_smoke", "research", "retrospective"},
        db_path=Path(db) if db else None,
        cas_root=Path(cas) if cas else None,
        authority_id=authority,
    )


def load_all_configs() -> tuple[AdapterConfig, ...]:
    return tuple(load_adapter_config(adapter_id) for adapter_id in ADAPTER_IDS)

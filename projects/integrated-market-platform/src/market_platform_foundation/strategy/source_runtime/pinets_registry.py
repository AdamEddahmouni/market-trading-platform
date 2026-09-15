"""Governed Pine script registry — imported scripts default to UNTESTED."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .pinets_fixtures import BUILTIN_PINETS_FIXTURES, PineFixtureDefinition
from .types import PineRuntimeCompatibilityStatus


@dataclass(frozen=True, slots=True)
class PineScriptRecord:
    script_id: str
    status: PineRuntimeCompatibilityStatus
    title: str
    pine_source: str
    reference_parameters: Mapping[str, int | float] = field(default_factory=dict)
    notes: str = ""

    def with_status(self, status: PineRuntimeCompatibilityStatus) -> PineScriptRecord:
        return PineScriptRecord(
            script_id=self.script_id,
            status=status,
            title=self.title,
            pine_source=self.pine_source,
            reference_parameters=dict(self.reference_parameters),
            notes=self.notes,
        )


class PineScriptRegistry:
    def __init__(self) -> None:
        self._records: dict[str, PineScriptRecord] = {}

    def register(self, record: PineScriptRecord, *, allow_downgrade: bool = False) -> None:
        existing = self._records.get(record.script_id)
        if existing and not allow_downgrade:
            if existing.status != PineRuntimeCompatibilityStatus.UNTESTED:
                return
        self._records[record.script_id] = record

    def import_script(
        self,
        script_id: str,
        pine_source: str,
        *,
        title: str = "",
        reference_parameters: Mapping[str, int | float] | None = None,
        status: PineRuntimeCompatibilityStatus = PineRuntimeCompatibilityStatus.UNTESTED,
        notes: str = "",
    ) -> PineScriptRecord:
        record = PineScriptRecord(
            script_id=script_id,
            status=status,
            title=title or script_id,
            pine_source=pine_source,
            reference_parameters=dict(reference_parameters or {}),
            notes=notes,
        )
        self.register(record)
        return record

    def get(self, script_id: str) -> PineScriptRecord | None:
        return self._records.get(script_id)

    def require(self, script_id: str) -> PineScriptRecord:
        record = self.get(script_id)
        if record is None:
            raise KeyError(f"PINETS_SCRIPT_NOT_REGISTERED:{script_id}")
        return record

    def list_records(self) -> tuple[PineScriptRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))


def _fixture_to_record(
    fixture: PineFixtureDefinition,
    *,
    status: PineRuntimeCompatibilityStatus,
) -> PineScriptRecord:
    return PineScriptRecord(
        script_id=fixture.script_id,
        status=status,
        title=fixture.title,
        pine_source=fixture.pine_source,
        reference_parameters=dict(fixture.reference_parameters),
        notes="IMP Lane E reference fixture (Python reference path; PineTS optional research bridge).",
    )


def build_default_pinets_registry() -> PineScriptRegistry:
    registry = PineScriptRegistry()
    for fixture in BUILTIN_PINETS_FIXTURES:
        registry.register(
            _fixture_to_record(
                fixture,
                status=PineRuntimeCompatibilityStatus.PARTIAL_PARITY,
            )
        )
    return registry


DEFAULT_PINETS_REGISTRY = build_default_pinets_registry()

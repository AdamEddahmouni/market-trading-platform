"""Generic specialist boundary for BUILD 11."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..contracts import ExpertDomain
from .context import SpecialistExecutionContext
from .models import SpecialistResult


@runtime_checkable
class Specialist(Protocol):
    expert_domain: ExpertDomain
    component_id: str
    component_version: str

    def analyze(self, context: SpecialistExecutionContext) -> SpecialistResult: ...


__all__ = ["Specialist"]

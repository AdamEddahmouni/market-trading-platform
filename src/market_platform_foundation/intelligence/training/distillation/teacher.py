"""Distillation types and teacher contracts (BUILD 18)."""

from __future__ import annotations

from typing import Protocol

from ..types import DistillationTargetKind, TeacherOutputV1


class TeacherProvider(Protocol):
    teacher_id: str
    teacher_version: str

    def produce(
        self,
        *,
        input_ref: str,
        features: tuple[float, ...],
        availability_time_ns: int,
    ) -> TeacherOutputV1: ...


__all__ = ["TeacherProvider"]

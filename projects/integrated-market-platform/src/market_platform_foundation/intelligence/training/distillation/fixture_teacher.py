"""Deterministic fixture teacher for distillation tests (BUILD 18)."""

from __future__ import annotations

from ..identity import artifact_content_hash
from ..types import DistillationTargetKind, TeacherOutputV1
from .teacher import TeacherProvider


class FixtureTeacher:
    """Produces stable soft binary probabilities from input features."""

    teacher_id = "fixture-teacher"
    teacher_version = "v1"

    def produce(
        self,
        *,
        input_ref: str,
        features: tuple[float, ...],
        availability_time_ns: int,
    ) -> TeacherOutputV1:
        if not features:
            p_up = 0.5
        else:
            total = sum(features)
            p_up = max(0.01, min(0.99, 0.5 + 0.1 * (total / len(features))))
        output_ref = artifact_content_hash(
            f"{self.teacher_id}:{self.teacher_version}:{input_ref}:{p_up}".encode()
        )
        return TeacherOutputV1(
            teacher_id=self.teacher_id,
            teacher_version=self.teacher_version,
            input_ref=input_ref,
            target_kind=DistillationTargetKind.TEACHER_PROBABILITIES,
            output={"p_up": p_up, "output_ref": output_ref},
            availability_time_ns=availability_time_ns,
            provenance="TEACHER",
        )


__all__ = ["FixtureTeacher"]

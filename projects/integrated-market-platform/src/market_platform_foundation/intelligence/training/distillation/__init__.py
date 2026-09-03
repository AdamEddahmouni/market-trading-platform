"""Distillation support (BUILD 18)."""

from .dataset import build_distillation_dataset
from .fixture_teacher import FixtureTeacher
from .teacher import TeacherProvider

__all__ = ["FixtureTeacher", "TeacherProvider", "build_distillation_dataset"]

"""XA-05 errors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class Xa05ErrorCode(StrEnum):
  INVALID_DECISION_TIME = "INVALID_DECISION_TIME"
  UNKNOWN_CLASSIFIER_VERSION = "UNKNOWN_CLASSIFIER_VERSION"
  INVALID_CONFIG = "INVALID_CONFIG"
  REPOSITORY_UNAVAILABLE = "REPOSITORY_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class Xa05Error(Exception):
  code: Xa05ErrorCode
  message: str
  details: Mapping[str, Any]

  def __str__(self) -> str:
    return f"{self.code.value}: {self.message}"

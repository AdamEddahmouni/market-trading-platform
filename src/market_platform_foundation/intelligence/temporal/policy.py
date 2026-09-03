"""Temporal integrity policy configuration (BUILD 02)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TemporalIntegrityPolicy:
    """Versionable policy for point-in-time eligibility and usability.

    The anti-lookahead rule ``available_time_ns <= decision_time_ns`` is always
    enforced for eligibility. There is no production bypass for future information.
  """

    max_age_ns: int | None = None
    max_provider_clock_ahead_ns: int | None = None
    max_provider_clock_behind_ns: int | None = None
    reject_stale_for_usability: bool = True
    require_event_time_before_decision: bool = False
    clock_skew_severity_error: bool = False
    per_category_max_age_ns: dict[str, int] | None = None

    def __post_init__(self) -> None:
        if self.max_age_ns is not None and self.max_age_ns < 0:
            raise ValueError("MAX_AGE_NS_NEGATIVE")
        if self.max_provider_clock_ahead_ns is not None and self.max_provider_clock_ahead_ns < 0:
            raise ValueError("MAX_PROVIDER_CLOCK_AHEAD_NS_NEGATIVE")
        if self.max_provider_clock_behind_ns is not None and self.max_provider_clock_behind_ns < 0:
            raise ValueError("MAX_PROVIDER_CLOCK_BEHIND_NS_NEGATIVE")
        if self.per_category_max_age_ns is not None:
            if not isinstance(self.per_category_max_age_ns, dict):
                raise ValueError("PER_CATEGORY_MAX_AGE_NS_INVALID")
            for key, value in self.per_category_max_age_ns.items():
                if not key or not str(key).strip():
                    raise ValueError("PER_CATEGORY_MAX_AGE_KEY_INVALID")
                if value < 0:
                    raise ValueError("PER_CATEGORY_MAX_AGE_NS_NEGATIVE")

    def max_age_for_category(self, category: str | None) -> int | None:
        if category and self.per_category_max_age_ns:
            override = self.per_category_max_age_ns.get(category)
            if override is not None:
                return override
        return self.max_age_ns

    def with_overrides(self, **kwargs: Any) -> TemporalIntegrityPolicy:
        current = {
            "max_age_ns": self.max_age_ns,
            "max_provider_clock_ahead_ns": self.max_provider_clock_ahead_ns,
            "max_provider_clock_behind_ns": self.max_provider_clock_behind_ns,
            "reject_stale_for_usability": self.reject_stale_for_usability,
            "require_event_time_before_decision": self.require_event_time_before_decision,
            "clock_skew_severity_error": self.clock_skew_severity_error,
            "per_category_max_age_ns": self.per_category_max_age_ns,
        }
        current.update(kwargs)
        return TemporalIntegrityPolicy(**current)


DEFAULT_TEMPORAL_POLICY = TemporalIntegrityPolicy()


__all__ = ["DEFAULT_TEMPORAL_POLICY", "TemporalIntegrityPolicy"]

"""Storage boundaries for operational observations and analytical consumers."""

from __future__ import annotations

from typing import Protocol

from .identity import InstrumentIdentity
from .observations import Observation


class OperationalObservationStore(Protocol):
    def append(self, observation: Observation) -> None: ...

    def query(self, instrument: InstrumentIdentity, *, as_of_time_ns: int) -> tuple[Observation, ...]: ...


class AnalyticalObservationStore(Protocol):
    def query(self, instrument: InstrumentIdentity, *, as_of_time_ns: int) -> tuple[Observation, ...]: ...


class InMemoryObservationStore:
    """Bounded-by-caller operational store; intentionally not a tick warehouse."""

    def __init__(self, *, max_observations: int = 10_000) -> None:
        self._max_observations = max_observations
        self._observations: dict[str, Observation] = {}

    def append(self, observation: Observation) -> None:
        existing = self._observations.get(observation.observation_id)
        if existing is not None:
            if existing != observation:
                raise ValueError("OBSERVATION_IMMUTABILITY_CONFLICT")
            return
        if len(self._observations) >= self._max_observations:
            raise ValueError("OBSERVATION_STORE_BOUNDED")
        self._observations[observation.observation_id] = observation

    def query(self, instrument: InstrumentIdentity, *, as_of_time_ns: int) -> tuple[Observation, ...]:
        return tuple(sorted(
            (
                item
                for item in self._observations.values()
            if item.instrument == instrument
            and item.clocks.available_time_ns <= as_of_time_ns
            and item.clocks.validity_start_ns <= as_of_time_ns
            and (
                item.clocks.validity_end_ns is None
                or as_of_time_ns < item.clocks.validity_end_ns
            )
            ),
            key=lambda item: (item.clocks.available_time_ns, item.observation_id),
        ))


__all__ = ["AnalyticalObservationStore", "InMemoryObservationStore", "OperationalObservationStore"]

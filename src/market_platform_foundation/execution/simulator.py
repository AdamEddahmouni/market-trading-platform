"""Structural simulation descriptor with no execution operations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SimulatorDescriptor:
    registry_id: str = "simulation.noop"
    routing_capability: bool = False


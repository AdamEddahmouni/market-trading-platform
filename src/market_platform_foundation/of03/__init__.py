"""Public OF-03 registry contracts. Description is not authorization."""

from __future__ import annotations

from .agent_policy import authorize_execution_from_registry, evaluate_agent_use
from .errors import OF03Error, OF03ErrorCode
from .loader import LoadedRegistry, load_registry
from .operations import CAPABILITY_IDS, execute
from .provenance import CapabilityReference, WorkflowReference, capability_reference, workflow_reference

__all__ = [
    "CAPABILITY_IDS",
    "CapabilityReference",
    "LoadedRegistry",
    "OF03Error",
    "OF03ErrorCode",
    "WorkflowReference",
    "authorize_execution_from_registry",
    "capability_reference",
    "evaluate_agent_use",
    "execute",
    "load_registry",
    "workflow_reference",
]

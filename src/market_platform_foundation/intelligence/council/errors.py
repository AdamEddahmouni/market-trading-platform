"""Council error hierarchy for BUILD 12."""

from __future__ import annotations


class CouncilError(Exception):
    """Base council coordination error."""


class CouncilConfigurationError(CouncilError):
    """Invalid council plan or policy configuration."""


class CouncilStateError(CouncilError):
    """Illegal council phase transition or state mutation."""


class CouncilIntegrityError(CouncilError):
    """Council integrity violation such as missing canonical evidence."""


class BlackboardNotReadyError(CouncilStateError):
    """Blackboard requested before blind barrier completion."""


class ProvenanceResolutionError(CouncilError):
    """Explicit provenance lineage could not be resolved."""


__all__ = [
    "BlackboardNotReadyError",
    "CouncilConfigurationError",
    "CouncilError",
    "CouncilIntegrityError",
    "CouncilStateError",
    "ProvenanceResolutionError",
]

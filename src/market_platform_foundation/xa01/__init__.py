"""IMP-XA-01 cross-asset canonical identity kernel."""

from __future__ import annotations

from .enums import (
    AnalyticalDomain,
    ExternalIdentifierType,
    InstrumentKind,
    RelationshipType,
    XaAssetClass,
)
from .operations import OperationResult, execute
from .registry import InstrumentRegistry, configure_registry, get_registry, reset_registry_for_tests

__all__ = [
    "AnalyticalDomain",
    "ExternalIdentifierType",
    "InstrumentKind",
    "InstrumentRegistry",
    "OperationResult",
    "RelationshipType",
    "XaAssetClass",
    "configure_registry",
    "execute",
    "get_registry",
    "reset_registry_for_tests",
]

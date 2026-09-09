"""IMP-XA-01 cross-asset canonical identity kernel."""

from __future__ import annotations

from .enums import (
    AnalyticalDomain,
    ExternalIdentifierType,
    InstrumentKind,
    RelationshipType,
    Tradability,
    XaAssetClass,
)
from .operations import OperationResult, execute
from .registry import InstrumentRegistry, configure_registry, get_registry, reset_registry_for_tests
from .tradability import assert_executable, default_tradability, is_executable

__all__ = [
    "AnalyticalDomain",
    "ExternalIdentifierType",
    "InstrumentKind",
    "InstrumentRegistry",
    "OperationResult",
    "RelationshipType",
    "Tradability",
    "XaAssetClass",
    "assert_executable",
    "configure_registry",
    "default_tradability",
    "execute",
    "get_registry",
    "is_executable",
    "reset_registry_for_tests",
]

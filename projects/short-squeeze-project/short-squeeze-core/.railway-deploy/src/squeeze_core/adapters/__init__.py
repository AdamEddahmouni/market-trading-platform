"""Offline provider adapter contracts."""

from .base import AdapterContext, NormalizationResult, RejectedRecord
from .diagnostics import DiagnosticCode, DiagnosticSeverity, NormalizationDiagnostic

__all__ = [
    "AdapterContext",
    "DiagnosticCode",
    "DiagnosticSeverity",
    "NormalizationDiagnostic",
    "NormalizationResult",
    "RejectedRecord",
]

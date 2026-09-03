"""Governance errors (BUILD 23)."""

from __future__ import annotations


class GovernanceError(Exception):
    """Base governance error."""

    def __init__(self, code: str, *, details: dict | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.details = details or {}


class ActivationError(GovernanceError):
    """Runtime activation failed validation."""


class RollbackError(GovernanceError):
    """Rollback evaluation failed validation."""


class OverrideForbiddenError(GovernanceError):
    """Governance override not permitted."""


class RuntimeGovernanceDisabledError(GovernanceError):
    """Runtime scope is disabled by governance."""

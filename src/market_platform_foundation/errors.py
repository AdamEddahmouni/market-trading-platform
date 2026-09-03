"""Governance-specific failures with fail-closed semantics."""


class GovernanceError(Exception):
    """Base class for governed Phase 0 errors."""


class BlockedError(GovernanceError):
    """A required authority, subject, tool, or evidence item is missing."""


class IntegrityError(GovernanceError):
    """Governed bytes contradict an integrity rule."""


class OfflineBoundaryViolation(GovernanceError):
    """A prohibited communication or process operation was attempted."""


class PolicyViolation(GovernanceError):
    """A closed Phase 0 policy rejected the subject."""


"""Known authority *references*. Membership does not grant them."""

from __future__ import annotations

KNOWN_AUTHORITY_REFS = frozenset(
    {
        "NONE",
        "LEDGER_RUNTIME",
        "LEDGER_OPERATOR",
        "LEDGER_MAINTENANCE",
        "LEDGER_RECOVERY",
        "LEDGER_PROJECTION",
        "OF_ANALYST",
        "OF_DEVELOPER",
        "AUTOMATION_AI",
        "OPERATOR_INSPECT",
        "BACKUP_RECOVERY_OPERATOR",
        "REGISTRY_OPERATOR",
        "MODEL_PROMOTION_AUTHORITY",
        "LIVE_SESSION_AUTHORITY",
        "LIVE_ORDER_AUTHORITY",
        "RISK_OVERRIDE_AUTHORITY",
        "RELEASE_AUTHORITY",
        "VALIDATION_OPERATOR",
        "TRAINING_OPERATOR",
    }
)

KNOWN_ROLE_REFS = frozenset(
    {
        "LEDGER_RUNTIME",
        "LEDGER_OPERATOR",
        "MAINTENANCE_OPERATOR",
        "RECOVERY_OPERATOR",
        "PROJECTION_OPERATOR",
        "ANALYST",
        "DEVELOPER",
        "AUTOMATION_AI",
        "HUMAN_OPERATOR",
        "REGISTRY_OPERATOR",
        "RELEASE_OWNER",
    }
)

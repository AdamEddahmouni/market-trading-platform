"""Finviz provider role — read-only discovery/context only."""

from __future__ import annotations

PROVIDER_ID = "FINVIZ_ELITE"
EXECUTION_ROLE = "NONE"

ALLOWED_ROLES = frozenset(
    {
        "DISCOVERY",
        "CONTEXT",
        "NEWS",
        "FUNDAMENTALS",
        "TECHNICALS",
        "ANALYST",
        "INSIDER_DISCOVERY",
        "GROUP_CONTEXT",
        "ETF_CONTEXT",
        "OPTIONS_CONTEXT",
    }
)

FORBIDDEN_ROLES = frozenset(
    {
        "ORDER_SUBMISSION",
        "BROKER_EXECUTION",
        "TRADE_MODIFICATION",
        "CANCEL",
        "EXECUTION_AUTHORITY",
    }
)


def assert_read_only_role(role: str) -> None:
    normalized = str(role).upper()
    if normalized in FORBIDDEN_ROLES:
        raise ValueError(f"FINVIZ_FORBIDDEN_ROLE:{normalized}")


def finviz_can_execute() -> bool:
    return False

"""Pre-canary reconciliation gates (BUILD 29)."""

from __future__ import annotations

from ..live_execution_safety.reconciliation import build_reconciliation_snapshot
from ..live_execution_safety.types import (
    AccountEnvironment,
    BrokerReconciliationSnapshotV1,
    ReconciliationHealthState,
)
from .portfolio import LivePortfolioSnapshotV1, is_flat_for_scope
from .types import LiveCanaryPolicyV1


class PreCanaryReconciliationResult:
    __slots__ = (
        "passed",
        "reason_codes",
        "reconciliation",
        "broker_healthy",
        "environment_confirmed",
        "account_matched",
        "flat_start",
    )

    def __init__(
        self,
        *,
        passed: bool,
        reason_codes: tuple[str, ...],
        reconciliation: BrokerReconciliationSnapshotV1 | None = None,
        broker_healthy: bool = False,
        environment_confirmed: bool = False,
        account_matched: bool = False,
        flat_start: bool = False,
    ) -> None:
        self.passed = passed
        self.reason_codes = reason_codes
        self.reconciliation = reconciliation
        self.broker_healthy = broker_healthy
        self.environment_confirmed = environment_confirmed
        self.account_matched = account_matched
        self.flat_start = flat_start


def evaluate_pre_canary_reconciliation(
    *,
    policy: LiveCanaryPolicyV1,
    account_ref: str,
    account_environment: AccountEnvironment,
    broker_healthy: bool,
    as_of_ns: int,
    portfolio: LivePortfolioSnapshotV1,
    local_open_intents: tuple[str, ...] = (),
    broker_open_orders: tuple[str, ...] = (),
    ambiguous_submissions: tuple[str, ...] = (),
    expected_account_ref: str | None = None,
) -> PreCanaryReconciliationResult:
    reason_codes: list[str] = []
    expected_account = expected_account_ref or policy.account_ref

    if not broker_healthy:
        reason_codes.append("BROKER_UNHEALTHY")
    if account_environment == AccountEnvironment.UNKNOWN:
        reason_codes.append("ENVIRONMENT_UNKNOWN")
    elif account_environment != AccountEnvironment.LIVE:
        reason_codes.append("ENVIRONMENT_NOT_LIVE")
    if account_ref != expected_account:
        reason_codes.append("ACCOUNT_MISMATCH")

    reconciliation = build_reconciliation_snapshot(
        broker=policy.broker,
        account_environment=account_environment,
        as_of_ns=as_of_ns,
        local_open_intents=local_open_intents,
        broker_open_orders=broker_open_orders,
    )
    if reconciliation.health_state != ReconciliationHealthState.HEALTHY:
        reason_codes.append("RECONCILIATION_UNHEALTHY")
    if reconciliation.broker_only:
        reason_codes.append("UNKNOWN_BROKER_ORDER")
    if ambiguous_submissions:
        reason_codes.append("AMBIGUOUS_PRIOR_SUBMISSION")

    flat_start = is_flat_for_scope(portfolio, allowed_instruments=policy.allowed_instruments)
    if policy.require_flat_start and not flat_start:
        reason_codes.append("FLAT_START_VIOLATION")

    passed = len(reason_codes) == 0
    return PreCanaryReconciliationResult(
        passed=passed,
        reason_codes=tuple(reason_codes),
        reconciliation=reconciliation,
        broker_healthy=broker_healthy,
        environment_confirmed=account_environment == AccountEnvironment.LIVE,
        account_matched=account_ref == expected_account,
        flat_start=flat_start,
    )

"""Supervised production pilot policy builders (BUILD 33)."""

from __future__ import annotations

from ..operational_reliability import build_default_alert_policy, build_default_slo_policy
from .identity import derive_pilot_policy_id, derive_provider_redundancy_policy_id
from .types import (
    DEFAULT_BACKUP_FRESHNESS_NS,
    DEFAULT_CHECKPOINT_INTERVAL_NS,
    DEFAULT_MAX_PILOT_FILLS,
    DEFAULT_MAX_PILOT_LIVE_EXPOSURE_MINOR,
    DEFAULT_MAX_PILOT_ORDERS,
    DEFAULT_MAX_PILOT_SESSIONS,
    DEFAULT_MAX_PILOT_SINGLE_ORDER_NOTIONAL_MINOR,
    DEFAULT_MAX_PILOT_TOTAL_NOTIONAL_MINOR,
    DEFAULT_PILOT_DURATION_NS,
    DEFAULT_PROVIDER_FAILURE_DURATION_NS,
    DEFAULT_PROVIDER_MAX_FRESHNESS_NS,
    DEFAULT_PROVIDER_RECOVERY_DURATION_NS,
    DEFAULT_PROVIDER_SWITCH_COOLDOWN_NS,
    DEFAULT_RECONCILIATION_INTERVAL_NS,
    DEFAULT_RESTORE_DRILL_AGE_NS,
    BUILD33_KNOWN_LIMITATIONS,
    LiveSupervisedPilotPolicyV1,
    ProviderCapability,
    ProviderHealthState,
    ProviderRedundancyPolicyV1,
    SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
    SUPERVISED_PILOT_SCHEMA_VERSION,
)


def build_default_provider_redundancy_policy(
    *,
    capability: str = ProviderCapability.QUOTES.value,
    primary_provider: str = "polygon",
    fallback_providers: tuple[str, ...] = ("finviz",),
) -> ProviderRedundancyPolicyV1:
    policy = ProviderRedundancyPolicyV1(
        provider_redundancy_policy_id="",
        schema_version=SUPERVISED_PILOT_SCHEMA_VERSION,
        scope="live_intelligence_path",
        capability=capability,
        instrument_class="equity",
        primary_provider=primary_provider,
        fallback_providers=fallback_providers,
        minimum_primary_health=ProviderHealthState.HEALTHY.value,
        minimum_fallback_health=ProviderHealthState.HEALTHY.value,
        maximum_freshness_ns=DEFAULT_PROVIDER_MAX_FRESHNESS_NS,
        minimum_failure_duration_ns=DEFAULT_PROVIDER_FAILURE_DURATION_NS,
        minimum_recovery_duration_ns=DEFAULT_PROVIDER_RECOVERY_DURATION_NS,
        switch_cooldown_ns=DEFAULT_PROVIDER_SWITCH_COOLDOWN_NS,
        divergence_warning_bps=50.0,
        divergence_critical_bps=200.0,
        fallback_for_observational_state=True,
        fallback_for_forecast_inputs=True,
        fallback_for_opportunity_inputs=True,
        implementation_version=SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
    )
    object.__setattr__(
        policy,
        "provider_redundancy_policy_id",
        derive_provider_redundancy_policy_id(policy),
    )
    return policy


def build_default_pilot_policy(
    *,
    source_build32_ref: str,
    pilot_start_ns: int,
    pilot_end_ns: int | None = None,
    allowed_data_providers: tuple[str, ...] = ("polygon", "finviz"),
    allowed_live_broker: str = "tradier.paper",
    allowed_live_account_ref: str = "fp-pilot-test",
) -> LiveSupervisedPilotPolicyV1:
    redundancy = build_default_provider_redundancy_policy()
    slo = build_default_slo_policy()
    alert = build_default_alert_policy()
    effective_end = pilot_end_ns or (pilot_start_ns + DEFAULT_PILOT_DURATION_NS)
    policy = LiveSupervisedPilotPolicyV1(
        pilot_policy_id="",
        schema_version=SUPERVISED_PILOT_SCHEMA_VERSION,
        source_build32_ref=source_build32_ref,
        pilot_start_ns=pilot_start_ns,
        pilot_end_ns=effective_end,
        allowed_market_sessions=("US_EQUITY_REGULAR",),
        allowed_data_providers=allowed_data_providers,
        primary_provider_policy={ProviderCapability.QUOTES.value: redundancy.primary_provider},
        allowed_live_broker=allowed_live_broker,
        allowed_live_account_ref=allowed_live_account_ref,
        allowed_canary_program_policy_refs=(),
        max_pilot_sessions=DEFAULT_MAX_PILOT_SESSIONS,
        max_pilot_orders=DEFAULT_MAX_PILOT_ORDERS,
        max_pilot_fills=DEFAULT_MAX_PILOT_FILLS,
        max_pilot_single_order_notional_minor=DEFAULT_MAX_PILOT_SINGLE_ORDER_NOTIONAL_MINOR,
        max_pilot_total_notional_minor=DEFAULT_MAX_PILOT_TOTAL_NOTIONAL_MINOR,
        max_pilot_live_exposure_minor=DEFAULT_MAX_PILOT_LIVE_EXPOSURE_MINOR,
        provider_redundancy_policy_ref=redundancy.provider_redundancy_policy_id,
        required_slo_policy_ref=slo.slo_policy_id,
        required_alert_policy_ref=alert.alert_policy_id,
        required_reconciliation_interval_ns=DEFAULT_RECONCILIATION_INTERVAL_NS,
        required_operational_checkpoint_interval_ns=DEFAULT_CHECKPOINT_INTERVAL_NS,
        required_backup_freshness_ns=DEFAULT_BACKUP_FRESHNESS_NS,
        required_restore_drill_age_ns=DEFAULT_RESTORE_DRILL_AGE_NS,
        human_session_authorization_required=True,
        human_order_confirmation_required=True,
        manual_resume_required=True,
        implementation_version=SUPERVISED_PILOT_IMPLEMENTATION_VERSION,
    )
    object.__setattr__(policy, "pilot_policy_id", derive_pilot_policy_id(policy))
    return policy


def validate_pilot_policy_constraints(policy: LiveSupervisedPilotPolicyV1) -> tuple[str, ...]:
    violations: list[str] = []
    if policy.pilot_end_ns <= policy.pilot_start_ns:
        violations.append("INVALID_PILOT_WINDOW")
    if policy.max_pilot_sessions < 1:
        violations.append("INVALID_MAX_PILOT_SESSIONS")
    if not policy.human_session_authorization_required:
        violations.append("HUMAN_SESSION_AUTHORIZATION_REQUIRED")
    if not policy.human_order_confirmation_required:
        violations.append("HUMAN_ORDER_CONFIRMATION_REQUIRED")
    if not policy.manual_resume_required:
        violations.append("MANUAL_RESUME_REQUIRED")
    return tuple(violations)

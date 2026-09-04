"""Serialization for BUILD 29 live canary contracts."""

from __future__ import annotations

from typing import Any

from .types import (
    CanaryAuthorizationPreviewV1,
    LiveCanaryPolicyV1,
    LiveCanaryQualificationReportV1,
    LiveCanaryRunV1,
)


def canary_policy_v1_to_dict(policy: LiveCanaryPolicyV1) -> dict[str, Any]:
    return {
        "canary_policy_id": policy.canary_policy_id,
        "schema_version": policy.schema_version,
        "broker": policy.broker,
        "account_ref": policy.account_ref,
        "account_environment": policy.account_environment,
        "allowed_asset_classes": list(policy.allowed_asset_classes),
        "allowed_instruments": list(policy.allowed_instruments),
        "allowed_sides": list(policy.allowed_sides),
        "allowed_order_types": list(policy.allowed_order_types),
        "max_single_order_notional_minor": policy.max_single_order_notional_minor,
        "max_total_canary_notional_minor": policy.max_total_canary_notional_minor,
        "max_net_live_exposure_minor": policy.max_net_live_exposure_minor,
        "max_gross_live_exposure_minor": policy.max_gross_live_exposure_minor,
        "max_order_count": policy.max_order_count,
        "max_fill_count": policy.max_fill_count,
        "allow_fractional": policy.allow_fractional,
        "allow_margin": policy.allow_margin,
        "allow_short": policy.allow_short,
        "allow_outside_rth": policy.allow_outside_rth,
        "authorization_duration_ns": policy.authorization_duration_ns,
        "require_flat_start": policy.require_flat_start,
        "require_flat_end": policy.require_flat_end,
        "require_manual_authorization": policy.require_manual_authorization,
        "require_manual_order_confirmation": policy.require_manual_order_confirmation,
        "implementation_version": policy.implementation_version,
    }


def preview_v1_to_dict(preview: CanaryAuthorizationPreviewV1) -> dict[str, Any]:
    return {
        "preview_id": preview.preview_id,
        "schema_version": preview.schema_version,
        "canary_policy_ref": preview.canary_policy_ref,
        "broker": preview.broker,
        "account_environment": preview.account_environment,
        "account_fingerprint": preview.account_fingerprint,
        "symbol_universe": list(preview.symbol_universe),
        "allowed_sides": list(preview.allowed_sides),
        "allowed_order_types": list(preview.allowed_order_types),
        "max_single_order_notional_minor": preview.max_single_order_notional_minor,
        "max_total_canary_notional_minor": preview.max_total_canary_notional_minor,
        "max_order_count": preview.max_order_count,
        "authorization_duration_ns": preview.authorization_duration_ns,
        "kill_switch_state": preview.kill_switch_state,
        "known_limitations": list(preview.known_limitations),
        "generated_at_ns": preview.generated_at_ns,
        "human_approved": False,
    }


def canary_run_v1_to_dict(run: LiveCanaryRunV1) -> dict[str, Any]:
    return {
        "canary_run_id": run.canary_run_id,
        "schema_version": run.schema_version,
        "source_build28_ref": run.source_build28_ref,
        "source_build27_ref": run.source_build27_ref,
        "source_head": run.source_head,
        "canary_policy_ref": run.canary_policy_ref,
        "authorization_ref": run.authorization_ref,
        "broker": run.broker,
        "account_ref": run.account_ref,
        "start_time_ns": run.start_time_ns,
        "end_time_ns": run.end_time_ns,
        "allowed_order_count": run.allowed_order_count,
        "allowed_notional_minor": run.allowed_notional_minor,
    }


def canary_report_v1_to_dict(report: LiveCanaryQualificationReportV1) -> dict[str, Any]:
    return {
        "report_id": report.report_id,
        "schema_version": report.schema_version,
        "canary_run_ref": report.canary_run_ref,
        "authorization_ref": report.authorization_ref,
        "opportunities_observed": report.opportunities_observed,
        "orders_confirmed": report.orders_confirmed,
        "submit_attempts": report.submit_attempts,
        "acks": report.acks,
        "fills": report.fills,
        "real_notional_minor": report.real_notional_minor,
        "disposition": report.disposition.value,
        "limitations": list(report.limitations),
    }

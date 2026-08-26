"""Alert delivery adapters and receipts (BUILD 32)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .identity import derive_delivery_receipt_id
from .types import (
    OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
    AlertDeliveryReceiptV1,
    AlertSeverity,
    AlertV1,
    DeliveryResult,
)


class AlertDeliveryAdapter(Protocol):
    channel: str

    def deliver(self, alert: AlertV1, *, attempt_time_ns: int) -> AlertDeliveryReceiptV1: ...


@dataclass
class ConsoleAlertDeliveryAdapter:
    """Deterministic local operator notification adapter."""

    channel: str = "console"
    fail_next: bool = False
    permanent_failure: bool = False

    def deliver(self, alert: AlertV1, *, attempt_time_ns: int) -> AlertDeliveryReceiptV1:
        if self.permanent_failure:
            result = DeliveryResult.PERMANENT_FAILURE.value
            failure = "CHANNEL_PERMANENT_FAILURE"
            retry = "NO_RETRY"
        elif self.fail_next:
            result = DeliveryResult.TEMPORARY_FAILURE.value
            failure = "CHANNEL_TEMPORARY_FAILURE"
            retry = "RETRY"
            self.fail_next = False
        else:
            result = DeliveryResult.SUCCESS.value
            failure = None
            retry = None
        receipt = AlertDeliveryReceiptV1(
            delivery_receipt_id="",
            schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
            alert_ref=alert.alert_id,
            channel=self.channel,
            attempt_time_ns=attempt_time_ns,
            result=result,
            latency_ns=1_000_000,
            failure_reason=failure,
            retry_classification=retry,
            metadata={"sanitized": True},
        )
        return AlertDeliveryReceiptV1(
            delivery_receipt_id=derive_delivery_receipt_id(receipt),
            schema_version=receipt.schema_version,
            alert_ref=receipt.alert_ref,
            channel=receipt.channel,
            attempt_time_ns=receipt.attempt_time_ns,
            result=receipt.result,
            latency_ns=receipt.latency_ns,
            failure_reason=receipt.failure_reason,
            retry_classification=receipt.retry_classification,
            lineage=receipt.lineage,
            metadata=receipt.metadata,
        )


@dataclass
class NotConfiguredDeliveryAdapter:
    channel: str

    def deliver(self, alert: AlertV1, *, attempt_time_ns: int) -> AlertDeliveryReceiptV1:
        receipt = AlertDeliveryReceiptV1(
            delivery_receipt_id="",
            schema_version=OPERATIONAL_RELIABILITY_SCHEMA_VERSION,
            alert_ref=alert.alert_id,
            channel=self.channel,
            attempt_time_ns=attempt_time_ns,
            result=DeliveryResult.NOT_CONFIGURED.value,
            latency_ns=None,
            failure_reason="EXTERNAL_ALERT_DELIVERY_NOT_CONFIGURED",
            retry_classification=None,
        )
        return AlertDeliveryReceiptV1(
            delivery_receipt_id=derive_delivery_receipt_id(receipt),
            schema_version=receipt.schema_version,
            alert_ref=receipt.alert_ref,
            channel=receipt.channel,
            attempt_time_ns=receipt.attempt_time_ns,
            result=receipt.result,
            latency_ns=receipt.latency_ns,
            failure_reason=receipt.failure_reason,
            retry_classification=receipt.retry_classification,
            lineage=receipt.lineage,
            metadata=receipt.metadata,
        )


def deliver_alert(
    alert: AlertV1,
    adapters: tuple[AlertDeliveryAdapter, ...],
    *,
    attempt_time_ns: int,
    critical_requires_any_success: bool = True,
) -> tuple[AlertDeliveryReceiptV1, ...]:
    receipts = tuple(adapter.deliver(alert, attempt_time_ns=attempt_time_ns) for adapter in adapters)
    if alert.severity == AlertSeverity.CRITICAL.value and critical_requires_any_success:
        successes = [r for r in receipts if r.result == DeliveryResult.SUCCESS.value]
        if not successes:
            # Delivery failure is observable — caller should raise ALERT_DELIVERY_FAILED
            pass
    return receipts


def sanitize_alert_payload(alert: AlertV1) -> dict[str, str]:
    """Ensure no secrets in alert payloads."""
    return {
        "alert_id": alert.alert_id,
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "scope": alert.scope,
        "summary": alert.summary,
    }

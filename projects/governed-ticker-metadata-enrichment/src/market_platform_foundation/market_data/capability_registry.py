"""Verified Moomoo capability state — never infer entitlement from config flags."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..clock import monotonic_wall_ns
from .capabilities import CapabilityState, MarketCapability, merge_capability

DEFAULT_PROBE_PATH = (
    Path(__file__).resolve().parents[3] / "evidence" / "market_data" / "moomoo" / "capability-report.json"
)
DEFAULT_STALENESS_SECONDS = 86_400


@dataclass(frozen=True, slots=True)
class ProviderDimensions:
    configured: bool = False
    connected: bool = False
    entitled: bool = False
    subscribed: bool = False
    receiving: bool = False
    healthy: bool = False


@dataclass
class VerifiedCapabilityRegistry:
    probe_path: Path = field(default_factory=lambda: DEFAULT_PROBE_PATH)
    verified_at: str | None = None
    connection: str = "UNKNOWN"
    sdk_version: str | None = None
    opend_version: str | None = None
    subscription_quota: int | None = None
    capabilities: dict[str, CapabilityState] = field(default_factory=dict)
    dimensions: ProviderDimensions = field(default_factory=ProviderDimensions)
    staleness_seconds: int | None = None
    is_stale: bool = True
    load_error: str | None = None

    @classmethod
    def from_probe_file(
        cls,
        path: Path | None = None,
        *,
        max_staleness_seconds: int = DEFAULT_STALENESS_SECONDS,
        moomoo_configured: bool = False,
        runtime_connected: bool = False,
        runtime_receiving: bool = False,
        runtime_healthy: bool = False,
    ) -> VerifiedCapabilityRegistry:
        probe_path = path or DEFAULT_PROBE_PATH
        registry = cls(probe_path=probe_path)
        if not probe_path.is_file():
            registry.load_error = "PROBE_REPORT_MISSING"
            registry.dimensions = ProviderDimensions(configured=moomoo_configured)
            registry._apply_unverified_defaults()
            return registry
        try:
            report = json.loads(probe_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            registry.load_error = str(exc)
            registry.dimensions = ProviderDimensions(configured=moomoo_configured)
            registry._apply_unverified_defaults()
            return registry

        registry.verified_at = str(report.get("verified_at") or report.get("tested_at") or "")
        registry.sdk_version = str(report.get("sdk_version") or "") or None
        connectivity = report.get("connectivity") if isinstance(report.get("connectivity"), dict) else {}
        registry.opend_version = str(connectivity.get("opend_version") or "") or None
        registry.connection = "CONNECTED" if connectivity.get("ret") == 0 else "DISCONNECTED"
        quota_payload = report.get("subscription_quota") if isinstance(report.get("subscription_quota"), dict) else {}
        nested = quota_payload.get("payload") if isinstance(quota_payload.get("payload"), dict) else {}
        if nested.get("total_used") is not None or nested.get("remain") is not None:
            try:
                used = int(nested.get("total_used") or 0)
                remain = int(nested.get("remain") or 0)
                registry.subscription_quota = used + remain
            except (TypeError, ValueError):
                pass
        after_stream = quota_payload.get("after_stream")
        if isinstance(after_stream, dict) and after_stream.get("remain") is not None:
            try:
                remain = int(after_stream.get("remain") or 0)
                used = int(after_stream.get("total_used") or 0)
                registry.subscription_quota = used + remain
            except (TypeError, ValueError):
                pass

        registry.staleness_seconds = _age_seconds(registry.verified_at)
        registry.is_stale = (
            registry.staleness_seconds is None or registry.staleness_seconds > max_staleness_seconds
        )
        registry.capabilities = _capabilities_from_report(report, stale=registry.is_stale)
        entitled = any(row.account_entitled for row in registry.capabilities.values())
        registry.dimensions = ProviderDimensions(
            configured=moomoo_configured,
            connected=runtime_connected or registry.connection == "CONNECTED",
            entitled=entitled and not registry.is_stale,
            subscribed=runtime_receiving,
            receiving=runtime_receiving,
            healthy=runtime_healthy and not registry.is_stale,
        )
        return registry

    def _apply_unverified_defaults(self) -> None:
        for cap in (
            MarketCapability.US_EQUITY_L1,
            MarketCapability.US_EQUITY_TICKS,
            MarketCapability.US_EQUITY_DEPTH,
        ):
            self.capabilities[cap.value] = merge_capability(
                CapabilityState(
                    capability=cap,
                    provider_supports=True,
                    account_entitled=False,
                    adapter_implemented=True,
                    runtime_tested=False,
                    data_currently_fresh=False,
                    evidence_class="UNTESTED",
                    reason_code="PROBE_MISSING",
                    notes="Run tools/moomoo/probe.py with OpenD running",
                )
            )

    def get(self, capability: MarketCapability | str) -> CapabilityState | None:
        key = capability.value if isinstance(capability, MarketCapability) else str(capability)
        return self.capabilities.get(key)

    def summary_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        mapping = {
            "BASIC_QUOTE": MarketCapability.US_EQUITY_L1,
            "TRADES": MarketCapability.US_EQUITY_TICKS,
            "ORDER_BOOK": MarketCapability.US_EQUITY_DEPTH,
        }
        for cap_id, cap in mapping.items():
            row = self.capabilities.get(cap.value)
            rows.append(
                {
                    "capability_id": cap_id,
                    "entitled": False if row is None else row.account_entitled,
                    "verified": row is not None and row.runtime_tested and not self.is_stale,
                    "reason_code": None if row is None else row.reason_code,
                    "notes": None if row is None else row.notes,
                }
            )
        return rows

    def to_dict(self) -> dict[str, Any]:
        return {
            "capabilities": {key: row.to_dict() for key, row in self.capabilities.items()},
            "connection": self.connection,
            "dimensions": {
                "configured": self.dimensions.configured,
                "connected": self.dimensions.connected,
                "entitled": self.dimensions.entitled,
                "healthy": self.dimensions.healthy,
                "receiving": self.dimensions.receiving,
                "subscribed": self.dimensions.subscribed,
            },
            "is_stale": self.is_stale,
            "load_error": self.load_error,
            "opend_version": self.opend_version,
            "probe_path": str(self.probe_path),
            "sdk_version": self.sdk_version,
            "staleness_seconds": self.staleness_seconds,
            "subscription_quota": self.subscription_quota,
            "verified_at": self.verified_at,
        }


def _capabilities_from_report(report: dict[str, Any], *, stale: bool) -> dict[str, CapabilityState]:
    raw = report.get("capabilities") if isinstance(report.get("capabilities"), dict) else {}
    result: dict[str, CapabilityState] = {}
    for key, payload in raw.items():
        if not isinstance(payload, dict):
            continue
        try:
            cap = MarketCapability(str(payload.get("capability") or key))
        except ValueError:
            continue
        entitled = bool(payload.get("account_entitled"))
        if stale:
            entitled = False
        result[cap.value] = merge_capability(
            CapabilityState(
                capability=cap,
                provider_supports=bool(payload.get("provider_supports", True)),
                account_entitled=entitled,
                adapter_implemented=bool(payload.get("adapter_implemented", True)),
                runtime_tested=bool(payload.get("runtime_tested")),
                data_currently_fresh=bool(payload.get("data_currently_fresh")) and not stale,
                evidence_class=str(payload.get("evidence_class") or "OBSERVED"),
                reason_code=None if entitled else str(payload.get("reason_code") or "PROBE_STALE" if stale else "NOT_ENTITLED"),
                notes=str(payload.get("notes") or ""),
            )
        )
    return result


def _age_seconds(iso_timestamp: str | None) -> int | None:
    if not iso_timestamp:
        return None
    text = iso_timestamp.replace("Z", "+00:00")
    try:
        verified = datetime.fromisoformat(text)
    except ValueError:
        return None
    if verified.tzinfo is None:
        verified = verified.replace(tzinfo=timezone.utc)
    return max(0, int(monotonic_wall_ns() / 1_000_000_000 - verified.timestamp()))

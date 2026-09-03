"""Recorded order-flow replay adapter (fixture bytes, no broker HTTP)."""

from __future__ import annotations

from pathlib import Path

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts import ProviderResult
from .fixture_order_flow import DEFAULT_ORDER_FLOW_FIXTURE, FixtureOrderFlowProvider


class RecordedOrderFlowProvider(FixtureOrderFlowProvider):
    """Time-windowed replay of captured order-flow bytes for SS P4 confirmation."""

    provider_id = "cvd.recorded.order_flow"
    entitlement = "CVD_RECORDED_REPLAY"

    def __init__(self, *, fixture_path: Path | None = None, ingest_run_id: str | None = None) -> None:
        self.fixture_path = fixture_path or DEFAULT_ORDER_FLOW_FIXTURE
        self.ingest_run_id = ingest_run_id or sha256_bytes(
            canonical_bytes({"fixture_path": str(self.fixture_path), "provider": self.provider_id})
        )
        self._fixture = self._load_fixture() if self.fixture_path.exists() else {}

    def fetch_order_flow(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        if not self.fixture_path.exists():
            return ProviderResult(
                status="unavailable",
                reason_code="ORDER_FLOW_LIVE_NOT_CONFIGURED",
                provider_id=self.provider_id,
                capability=self.capability,
            )
        return super().fetch_order_flow(symbol, as_of_time_ns=as_of_time_ns)


__all__ = [
    "RecordedOrderFlowProvider",
]

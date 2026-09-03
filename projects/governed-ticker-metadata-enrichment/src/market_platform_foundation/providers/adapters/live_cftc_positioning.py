"""Live CFTC COT positioning provider implementing FuturesPositioningProvider."""

from __future__ import annotations

from typing import Any

from ...normalization.equity_bars import iso_to_epoch_ns
from ...cftc.contracts import CotPositionScope, CotReportFamily
from ...cftc.datasets import CotDataset, dataset_spec
from ...cftc.live import transport_from_env
from ...cftc.mapping import CotProductMapper
from ...cftc.normalize import normalize_api_rows, to_futures_positioning_report
from ...cftc.transport import CotTransport, CotTransportError
from ...providers.contracts import ProviderResult

# Market name patterns for priority families
FAMILY_MARKET_PATTERNS: dict[str, str] = {
    "ES": "E-MINI S&P 500",
    "NQ": "E-MINI NASDAQ-100",
    "CL": "CRUDE OIL",
    "GC": "GOLD",
    "ZN": "10-YEAR",
}


class LiveCftcPositioningProvider:
    """Observational CFTC COT provider — not admitted, PIT-filtered."""

    provider_id = "cftc.public.futures_positioning"
    capability = "futures_positioning"
    entitlement = "CFTC_PUBLIC_OBSERVATIONAL"

    def __init__(
        self,
        *,
        transport: CotTransport | None = None,
        mapper: CotProductMapper | None = None,
        report_family: CotReportFamily = CotReportFamily.TFF,
        position_scope: CotPositionScope = CotPositionScope.FUTURES_ONLY,
        participant_category: str = "leveraged_funds",
    ) -> None:
        self.transport = transport or transport_from_env()
        self.mapper = mapper or CotProductMapper()
        self.report_family = report_family
        self.position_scope = position_scope
        self.participant_category = participant_category.lower()
        self._dataset = self._resolve_dataset()

    def _resolve_dataset(self) -> CotDataset:
        if self.report_family == CotReportFamily.TFF:
            return (
                CotDataset.TFF_FUTURES_ONLY
                if self.position_scope == CotPositionScope.FUTURES_ONLY
                else CotDataset.TFF_COMBINED
            )
        if self.report_family == CotReportFamily.DISAGGREGATED:
            return (
                CotDataset.DISAGGREGATED_FUTURES_ONLY
                if self.position_scope == CotPositionScope.FUTURES_ONLY
                else CotDataset.DISAGGREGATED_COMBINED
            )
        return (
            CotDataset.LEGACY_FUTURES_ONLY
            if self.position_scope == CotPositionScope.FUTURES_ONLY
            else CotDataset.LEGACY_COMBINED
        )

    def fetch_positioning(
        self,
        symbol: str,
        *,
        as_of_time_ns: int | None = None,
    ) -> ProviderResult:
        symbol_upper = symbol.upper()
        market_pattern = FAMILY_MARKET_PATTERNS.get(symbol_upper, symbol_upper)
        spec = dataset_spec(self._dataset)
        try:
            rows = self.transport.query_dataset(
                self._dataset,
                where=f"market_and_exchange_names like '%{market_pattern}%'",
                limit=104,
                order="report_date_as_yyyy_mm_dd ASC",
            )
        except CotTransportError:
            return ProviderResult(
                status="unavailable",
                reason_code="COT_SOURCE_UNAVAILABLE",
                provider_id=self.provider_id,
                capability=self.capability,
            )

        if not rows:
            return ProviderResult(
                status="unavailable",
                reason_code="COT_NO_REPORTS",
                provider_id=self.provider_id,
                capability=self.capability,
            )

        from datetime import datetime, timezone

        observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        observations = normalize_api_rows(
            rows,
            spec=spec,
            mapper=self.mapper,
            observed_time=observed,
            retrieved_time=observed,
        )
        reports: list[dict[str, Any]] = []
        for obs in observations:
            if obs.contract_family_id != symbol_upper:
                continue
            if obs.participant_category.value.lower() != self.participant_category.replace(" ", "_"):
                # match flexible category naming
                cat_norm = obs.participant_category.value.lower()
                if self.participant_category not in cat_norm and cat_norm not in self.participant_category:
                    continue
            report = to_futures_positioning_report(obs)
            if as_of_time_ns is not None and report.get("publication_time"):
                if iso_to_epoch_ns(str(report["publication_time"])) > as_of_time_ns:
                    continue
            reports.append(report)

        if not reports:
            return ProviderResult(
                status="unavailable",
                reason_code="COT_NOT_PIT_ELIGIBLE",
                provider_id=self.provider_id,
                capability=self.capability,
            )

        return ProviderResult(
            status="available",
            events=tuple(reports),
            provider_id=self.provider_id,
            capability=self.capability,
        )


__all__ = ["FAMILY_MARKET_PATTERNS", "LiveCftcPositioningProvider"]

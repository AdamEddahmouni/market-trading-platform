"""PIT short-intelligence store. Later publications cannot leak backward."""

from __future__ import annotations

from dataclasses import replace

from ..contracts.reference import ReferenceKind, ReferenceRecord
from ..runtime.bitemporal_store import BitemporalReferenceStore
from .clocks import visible_at
from .contracts import (
    FailsToDeliverObservation,
    ShortInterestObservation,
    ShortSaleVolumeObservation,
    ThresholdStatusObservation,
)


class ShortIntelligenceStore:
    def __init__(self, *, reference_store: BitemporalReferenceStore | None = None) -> None:
        self._short_interest: list[ShortInterestObservation] = []
        self._short_sale: list[ShortSaleVolumeObservation] = []
        self._threshold: list[ThresholdStatusObservation] = []
        self._ftd: list[FailsToDeliverObservation] = []
        self.reference_store = reference_store or BitemporalReferenceStore()

    def add_short_interest(self, row: ShortInterestObservation, *, historical_backfill: bool = False) -> None:
        quality = list(row.quality_flags)
        if historical_backfill:
            quality.extend(["REVISION_UNKNOWN", "ORIGINAL_VERSION_UNAVAILABLE"])
            row = replace(row, quality_flags=tuple(dict.fromkeys(quality)))
        siblings = [
            existing
            for existing in self._short_interest
            if existing.instrument_id == row.instrument_id and existing.settlement_date == row.settlement_date
        ]
        if siblings:
            row = replace(row, record_version=max(item.record_version for item in siblings) + 1)
        self._short_interest.append(row)
        self._append_reference(
            kind=ReferenceKind.SHORT_INTEREST,
            entity_key=f"{row.instrument_id}:{row.settlement_date}",
            record_id=f"si:{row.instrument_id}:{row.settlement_date}:{row.record_version}",
            version=row.record_version,
            valid_from=row.clocks.get("settlement_time") or row.settlement_date,
            known_from=row.clocks.get("available_time") or "",
            payload={
                "current_short_position_quantity": row.current_short_position_quantity,
                "observation_family": row.observation_family.value,
            },
        )

    def add_short_sale(self, row: ShortSaleVolumeObservation) -> None:
        self._short_sale.append(row)
        self._append_reference(
            kind=ReferenceKind.SHORT_SALE_VOLUME,
            entity_key=f"{row.instrument_id}:{row.trade_report_date}:{row.reporting_facility_code}:{row.market_code}",
            record_id=f"ssv:{row.raw_payload_hash[:16]}",
            version=1,
            valid_from=row.clocks.get("trade_report_date") or row.trade_report_date,
            known_from=row.clocks.get("available_time") or "",
            payload={
                "short_sale_volume": row.short_sale_volume,
                "observation_family": row.observation_family.value,
                "reporting_facility_code": row.reporting_facility_code,
            },
        )

    def add_threshold(self, row: ThresholdStatusObservation) -> None:
        siblings = [
            existing
            for existing in self._threshold
            if existing.instrument_id == row.instrument_id
            and existing.trade_date == row.trade_date
            and existing.source_sro == row.source_sro
            and existing.source_market == row.source_market
        ]
        if siblings:
            if any(existing.content_hash == row.content_hash for existing in siblings):
                return
            row = replace(
                row,
                record_version=max(existing.record_version for existing in siblings) + 1,
            )
        self._threshold.append(row)
        self._append_reference(
            kind=ReferenceKind.THRESHOLD_STATUS,
            entity_key=f"{row.instrument_id}:{row.trade_date}:{row.source_sro}:{row.source_market}",
            record_id=f"th:{row.content_hash[:12]}:{row.provider_symbol}:v{row.record_version}",
            version=row.record_version,
            valid_from=row.trade_date,
            known_from=row.clocks.get("available_time") or "",
            payload={
                "currently_threshold": row.currently_threshold,
                "observation_family": row.observation_family.value,
                "listing_coverage": row.listing_coverage,
                "reg_sho_threshold_flag": row.reg_sho_threshold_flag,
                "rule_4320_flag": row.rule_4320_flag,
                "threshold_list_flag": row.threshold_list_flag,
            },
        )

    def add_ftd(self, row: FailsToDeliverObservation) -> None:
        siblings = [
            existing
            for existing in self._ftd
            if existing.cusip == row.cusip
            and existing.settlement_date == row.settlement_date
            and existing.content_hash == row.content_hash
        ]
        if siblings:
            return
        self._ftd.append(row)
        self._append_reference(
            kind=ReferenceKind.FAILS_TO_DELIVER,
            entity_key=f"{row.instrument_id}:{row.cusip}:{row.settlement_date}",
            record_id=f"ftd:{row.cusip}:{row.settlement_date}:{row.content_hash[:12]}",
            version=1,
            valid_from=row.clocks.get("settlement_time") or row.settlement_date,
            known_from=row.clocks.get("available_time") or "",
            payload={
                "ftd_balance_quantity": row.ftd_balance_quantity,
                "observation_family": row.observation_family.value,
                "cusip": row.cusip,
            },
        )

    def short_interest_as_of(self, instrument_id: str, as_of: str) -> ShortInterestObservation | None:
        visible = [
            row
            for row in self._short_interest
            if row.instrument_id == instrument_id and row.clocks.get("available_time") and visible_at(row.clocks, as_of)
        ]
        if not visible:
            return None
        latest_settlement = max(row.settlement_date for row in visible)
        cohort = [row for row in visible if row.settlement_date == latest_settlement]
        return max(cohort, key=lambda row: row.record_version)

    def short_sale_as_of(self, instrument_id: str, as_of: str) -> tuple[ShortSaleVolumeObservation, ...]:
        rows = [
            row
            for row in self._short_sale
            if row.instrument_id == instrument_id and visible_at(row.clocks, as_of)
        ]
        return tuple(sorted(rows, key=lambda row: (row.trade_report_date, row.reporting_facility_code)))

    def threshold_as_of(self, instrument_id: str, as_of: str) -> tuple[ThresholdStatusObservation, ...]:
        rows = [
            row
            for row in self._threshold
            if row.instrument_id == instrument_id and visible_at(row.clocks, as_of)
        ]
        latest: dict[tuple[str, str, str], ThresholdStatusObservation] = {}
        for row in rows:
            key = (row.trade_date, row.source_sro, row.source_market)
            existing = latest.get(key)
            if existing is None or row.record_version >= existing.record_version:
                latest[key] = row
        return tuple(sorted(latest.values(), key=lambda row: (row.trade_date, row.source_sro, row.source_market)))

    def latest_threshold(self, instrument_id: str, as_of: str) -> ThresholdStatusObservation | None:
        rows = self.threshold_as_of(instrument_id, as_of)
        return rows[-1] if rows else None

    def ftd_as_of(self, instrument_id: str, as_of: str) -> tuple[FailsToDeliverObservation, ...]:
        rows = [
            row
            for row in self._ftd
            if row.instrument_id == instrument_id and visible_at(row.clocks, as_of)
        ]
        return tuple(sorted(rows, key=lambda row: row.settlement_date))

    def latest_ftd(self, instrument_id: str, as_of: str) -> FailsToDeliverObservation | None:
        rows = self.ftd_as_of(instrument_id, as_of)
        return rows[-1] if rows else None

    def _append_reference(
        self,
        *,
        kind: ReferenceKind,
        entity_key: str,
        record_id: str,
        version: int,
        valid_from: str,
        known_from: str,
        payload: dict[str, object],
    ) -> None:
        if not known_from:
            return
        start = valid_from if "T" in valid_from else f"{valid_from}T00:00:00Z"
        try:
            self.reference_store.append(
                ReferenceRecord(
                    kind=kind,
                    entity_key=entity_key,
                    record_id=record_id,
                    record_version=version,
                    valid_from=start,
                    known_from=known_from,
                    payload=payload,
                )
            )
        except ValueError:
            return

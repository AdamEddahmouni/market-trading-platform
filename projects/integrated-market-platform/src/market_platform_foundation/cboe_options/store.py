"""Append-only Cboe options statistics store with bitemporal knowledge versions."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts.reference import ReferenceKind, ReferenceRecord
from ..runtime.bitemporal_store import BitemporalReferenceStore
from .contracts import (
    OptionContractActivitySnapshot,
    OptionsMarketStatisticObservation,
    OptionsReferenceFileObservation,
    contract_snapshot_to_dict,
    market_statistic_to_dict,
    reference_file_to_dict,
)
from .pit import snapshot_as_of, statistic_as_of


@dataclass
class CboeOptionsStore:
    bitemporal: BitemporalReferenceStore = field(default_factory=BitemporalReferenceStore)
    statistics: list[OptionsMarketStatisticObservation] = field(default_factory=list)
    snapshots: list[OptionContractActivitySnapshot] = field(default_factory=list)
    references: list[OptionsReferenceFileObservation] = field(default_factory=list)
    _version_counter: int = 0

    @staticmethod
    def statistic_entity_key(obs: OptionsMarketStatisticObservation) -> str:
        parts = [
            obs.canonical_statistic_id,
            obs.trade_date,
            obs.bucket_start or "",
            obs.bucket_end or "",
            obs.reported_exchange_group.value if obs.reported_exchange_group else "",
        ]
        return ":".join(parts)

    @staticmethod
    def snapshot_entity_key(obs: OptionContractActivitySnapshot) -> str:
        return f"{obs.exchange.value}:{obs.contract_id}:{obs.snapshot_time}"

    @staticmethod
    def reference_entity_key(obs: OptionsReferenceFileObservation) -> str:
        return f"{obs.exchange.value}:{obs.reference_category}:{obs.content_hash[:16]}"

    def _close_open_knowledge_version(
        self,
        *,
        entity_key: str,
        known_from: str,
        content_hash: str,
    ) -> bool:
        updated: list[ReferenceRecord] = []
        duplicate = False
        for existing in self.bitemporal._records:
            if (
                existing.kind == ReferenceKind.OPTIONS_OI
                and existing.entity_key == entity_key.upper()
                and not existing.known_to
            ):
                if existing.payload.get("content_hash") == content_hash:
                    duplicate = True
                    updated.append(existing)
                    continue
                if known_from > existing.known_from:
                    updated.append(
                        ReferenceRecord(
                            kind=existing.kind,
                            entity_key=existing.entity_key,
                            record_id=existing.record_id,
                            record_version=existing.record_version,
                            valid_from=existing.valid_from,
                            valid_to=existing.valid_to,
                            known_from=existing.known_from,
                            known_to=known_from,
                            payload=existing.payload,
                            quality_flags=existing.quality_flags,
                        )
                    )
                    continue
            updated.append(existing)
        self.bitemporal._records = updated
        return duplicate

    def add_statistic(self, obs: OptionsMarketStatisticObservation) -> None:
        if not obs.available_time:
            raise ValueError("statistic available_time is required")
        entity_key = self.statistic_entity_key(obs)
        if self._close_open_knowledge_version(
            entity_key=entity_key,
            known_from=obs.available_time,
            content_hash=obs.content_hash,
        ):
            return
        self.statistics.append(obs)
        self._version_counter += 1
        payload = market_statistic_to_dict(obs)
        payload["record_type"] = "market_statistic"
        self.bitemporal.append(
            ReferenceRecord(
                kind=ReferenceKind.OPTIONS_OI,
                entity_key=entity_key,
                record_id=f"{entity_key}:v{self._version_counter}",
                record_version=self._version_counter,
                valid_from=obs.trade_date,
                valid_to=obs.bucket_end or obs.trade_date,
                known_from=obs.available_time,
                payload=payload,
                quality_flags=obs.quality_flags,
            )
        )

    def add_statistics(self, observations: tuple[OptionsMarketStatisticObservation, ...]) -> int:
        before = len(self.statistics)
        for obs in observations:
            self.add_statistic(obs)
        return len(self.statistics) - before

    def add_snapshot(self, obs: OptionContractActivitySnapshot) -> None:
        if not obs.available_time:
            raise ValueError("snapshot available_time is required")
        entity_key = self.snapshot_entity_key(obs)
        if self._close_open_knowledge_version(
            entity_key=entity_key,
            known_from=obs.available_time,
            content_hash=obs.content_hash,
        ):
            return
        self.snapshots.append(obs)
        self._version_counter += 1
        payload = contract_snapshot_to_dict(obs)
        payload["record_type"] = "contract_snapshot"
        self.bitemporal.append(
            ReferenceRecord(
                kind=ReferenceKind.OPTIONS_OI,
                entity_key=entity_key,
                record_id=f"{entity_key}:v{self._version_counter}",
                record_version=self._version_counter,
                valid_from=obs.snapshot_time,
                known_from=obs.available_time,
                payload=payload,
                quality_flags=obs.quality_flags,
            )
        )

    def add_snapshots(self, observations: tuple[OptionContractActivitySnapshot, ...]) -> int:
        before = len(self.snapshots)
        for obs in observations:
            self.add_snapshot(obs)
        return len(self.snapshots) - before

    def add_reference(self, obs: OptionsReferenceFileObservation) -> None:
        if not obs.available_time:
            raise ValueError("reference available_time is required")
        entity_key = f"{obs.exchange.value}:{obs.reference_category}"
        if self._close_open_knowledge_version(
            entity_key=entity_key,
            known_from=obs.available_time,
            content_hash=obs.content_hash,
        ):
            return
        self.references.append(obs)
        self._version_counter += 1
        payload = reference_file_to_dict(obs)
        payload["record_type"] = "reference_file"
        self.bitemporal.append(
            ReferenceRecord(
                kind=ReferenceKind.OPTIONS_OI,
                entity_key=entity_key,
                record_id=f"{entity_key}:v{self._version_counter}",
                record_version=self._version_counter,
                valid_from=obs.available_time,
                known_from=obs.available_time,
                payload=payload,
                quality_flags=obs.quality_flags,
            )
        )

    def add_references(self, observations: tuple[OptionsReferenceFileObservation, ...]) -> int:
        before = len(self.references)
        for obs in observations:
            self.add_reference(obs)
        return len(self.references) - before

    def statistic_as_of(
        self,
        *,
        canonical_statistic_id: str,
        trade_date: str,
        decision_time: str,
    ) -> OptionsMarketStatisticObservation | None:
        candidates = [
            obs
            for obs in self.statistics
            if obs.canonical_statistic_id == canonical_statistic_id and obs.trade_date == trade_date
        ]
        return statistic_as_of(candidates, decision_time=decision_time)

    def snapshot_as_of(
        self,
        *,
        contract_id: str,
        decision_time: str,
    ) -> OptionContractActivitySnapshot | None:
        candidates = [obs for obs in self.snapshots if obs.contract_id == contract_id]
        return snapshot_as_of(candidates, decision_time=decision_time)

    def stats(self) -> dict[str, int]:
        return {
            "statistic_count": len(self.statistics),
            "snapshot_count": len(self.snapshots),
            "reference_count": len(self.references),
            "bitemporal_records": len(self.bitemporal._records),
        }


__all__ = ["CboeOptionsStore"]

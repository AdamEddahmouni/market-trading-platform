"""PIT-safe COT positioning store with bitemporal revision support."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..contracts.reference import ReferenceKind, ReferenceRecord
from ..runtime.bitemporal_store import BitemporalReferenceStore
from .contracts import CotParticipantCategory, CotPositionScope, CotReportFamily, InstitutionalPositioningObservation
from .normalize import to_futures_positioning_report
from .quality import CotQualityFlag, quality_blocks_positioning


@dataclass
class CotStore:
    """In-memory store backed by bitemporal reference records."""

    bitemporal: BitemporalReferenceStore = field(default_factory=BitemporalReferenceStore)
    observations: list[InstitutionalPositioningObservation] = field(default_factory=list)
    _version_counter: int = 0

    def add_observation(self, obs: InstitutionalPositioningObservation) -> None:
        self._version_counter += 1
        self.observations.append(obs)
        entity_key = self._entity_key(obs)
        known_from = obs.available_time or obs.observed_time

        # Close prior open knowledge interval for same entity (source revision support)
        updated_records: list[ReferenceRecord] = []
        for existing in self.bitemporal._records:
            if (
                existing.kind == ReferenceKind.COT_POSITIONING
                and existing.entity_key == entity_key.upper()
                and not existing.known_to
                and obs.observed_time > existing.known_from
                and existing.payload.get("content_hash") != obs.content_hash
            ):
                updated_records.append(
                    ReferenceRecord(
                        kind=existing.kind,
                        entity_key=existing.entity_key,
                        record_id=existing.record_id,
                        record_version=existing.record_version,
                        valid_from=existing.valid_from,
                        valid_to=existing.valid_to,
                        known_from=existing.known_from,
                        known_to=obs.observed_time,
                        payload=existing.payload,
                        quality_flags=existing.quality_flags,
                    )
                )
                known_from = obs.observed_time
            else:
                updated_records.append(existing)
        self.bitemporal._records = updated_records

        record = ReferenceRecord(
            kind=ReferenceKind.COT_POSITIONING,
            entity_key=entity_key,
            record_id=f"{entity_key}:v{self._version_counter}",
            record_version=self._version_counter,
            valid_from=obs.position_date,
            known_from=known_from,
            payload=to_futures_positioning_report(obs),
            quality_flags=obs.quality_flags,
        )
        self.bitemporal.append(record)

    def add_observations(self, observations: tuple[InstitutionalPositioningObservation, ...]) -> int:
        for obs in observations:
            self.add_observation(obs)
        return len(observations)

    def query_visible(
        self,
        *,
        contract_family_id: str,
        decision_time: str,
        report_family: CotReportFamily | None = None,
        position_scope: CotPositionScope | None = None,
        participant_category: CotParticipantCategory | None = None,
    ) -> list[InstitutionalPositioningObservation]:
        visible: list[InstitutionalPositioningObservation] = []
        for obs in self.observations:
            if obs.contract_family_id != contract_family_id:
                continue
            if report_family and obs.report_family != report_family:
                continue
            if position_scope and obs.position_scope != position_scope:
                continue
            if participant_category and obs.participant_category != participant_category:
                continue
            if decision_time < obs.publication_time:
                continue
            visible.append(obs)
        visible.sort(key=lambda item: item.publication_time)
        return visible

    def latest_visible_or_flags(
        self,
        *,
        contract_family_id: str,
        decision_time: str,
        position_scope: CotPositionScope,
    ) -> tuple[InstitutionalPositioningObservation | None, tuple[str, ...]]:
        visible = self.query_visible(
            contract_family_id=contract_family_id,
            decision_time=decision_time,
            position_scope=position_scope,
        )
        if not visible:
            pending = any(
                obs.contract_family_id == contract_family_id
                and obs.position_scope == position_scope
                and decision_time < obs.publication_time
                for obs in self.observations
            )
            if pending:
                return None, (CotQualityFlag.REPORT_NOT_YET_RELEASED.value,)
            return None, (CotQualityFlag.EXPECTED_NOT_YET_AVAILABLE.value,)
        latest = visible[-1]
        if quality_blocks_positioning(latest.quality_flags):
            return None, latest.quality_flags
        return latest, latest.quality_flags

    @staticmethod
    def _entity_key(obs: InstitutionalPositioningObservation) -> str:
        return (
            f"{obs.contract_family_id}:{obs.report_family.value}:"
            f"{obs.position_scope.value}:{obs.participant_category.value}"
        )

    def stats(self) -> dict[str, Any]:
        families = sorted({obs.contract_family_id for obs in self.observations})
        return {
            "observation_count": len(self.observations),
            "contract_families": families,
            "bitemporal_records": len(getattr(self.bitemporal, "_records", [])),
        }


__all__ = ["CotStore"]

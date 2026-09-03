"""PIT-safe EIA physical fundamentals store with bitemporal revision support."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts.reference import ReferenceKind, ReferenceRecord
from ..runtime.bitemporal_store import BitemporalReferenceStore
from .contracts import EnergyFundamentalObservation, EnergyReleaseFamily, observation_to_dict
from .pit import latest_visible_or_flags, query_visible
from .quality import EiaQualityFlag, quality_blocks_fundamentals


@dataclass
class EiaStore:
    bitemporal: BitemporalReferenceStore = field(default_factory=BitemporalReferenceStore)
    observations: list[EnergyFundamentalObservation] = field(default_factory=list)
    release_events: list[dict[str, Any]] = field(default_factory=list)
    _version_counter: int = 0

    def add_observation(self, obs: EnergyFundamentalObservation) -> None:
        self._version_counter += 1
        self.observations.append(obs)
        entity_key = self._entity_key(obs)
        known_from = obs.available_time or obs.ingested_time

        updated_records: list[ReferenceRecord] = []
        for existing in self.bitemporal._records:
            if (
                existing.kind == ReferenceKind.ENERGY_FUNDAMENTAL
                and existing.entity_key == entity_key.upper()
                and not existing.known_to
                and obs.ingested_time > existing.known_from
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
                        known_to=obs.ingested_time,
                        payload=existing.payload,
                        quality_flags=existing.quality_flags,
                    )
                )
                known_from = obs.ingested_time
            else:
                updated_records.append(existing)
        self.bitemporal._records = updated_records

        record = ReferenceRecord(
            kind=ReferenceKind.ENERGY_FUNDAMENTAL,
            entity_key=entity_key,
            record_id=f"{entity_key}:v{self._version_counter}",
            record_version=self._version_counter,
            valid_from=obs.period_end,
            known_from=known_from,
            payload=observation_to_dict(obs),
            quality_flags=obs.quality_flags,
        )
        self.bitemporal.append(record)

    def add_observations(self, observations: tuple[EnergyFundamentalObservation, ...]) -> int:
        for obs in observations:
            self.add_observation(obs)
        return len(observations)

    def query_visible(
        self,
        *,
        decision_time: str,
        release_family: EnergyReleaseFamily | None = None,
        canonical_indicator_id: str | None = None,
    ) -> list[EnergyFundamentalObservation]:
        return query_visible(
            self.observations,
            decision_time=decision_time,
            release_family=release_family,
            canonical_indicator_id=canonical_indicator_id,
        )

    def latest_visible_or_flags(
        self,
        *,
        decision_time: str,
        canonical_indicator_id: str,
    ) -> tuple[EnergyFundamentalObservation | None, tuple[str, ...]]:
        latest, flags = latest_visible_or_flags(
            self.observations,
            decision_time=decision_time,
            canonical_indicator_id=canonical_indicator_id,
        )
        if latest and quality_blocks_fundamentals(latest.quality_flags):
            return None, latest.quality_flags
        return latest, flags

    @staticmethod
    def _entity_key(obs: EnergyFundamentalObservation) -> str:
        return f"{obs.canonical_indicator_id}:{obs.period_end}"

    def stats(self) -> dict[str, Any]:
        return {
            "observation_count": len(self.observations),
            "release_event_count": len(self.release_events),
            "bitemporal_records": len(getattr(self.bitemporal, "_records", [])),
        }


__all__ = ["EiaStore"]

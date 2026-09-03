"""Append-only weather evidence store with forecast-vintage correction history."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts.reference import ReferenceKind, ReferenceRecord
from ..runtime.bitemporal_store import BitemporalReferenceStore
from .contracts import (
    WeatherForecastObservation,
    WeatherRealizationObservation,
    WeatherReferenceObservation,
    WeatherRegionType,
    WeatherVariable,
    WeatherWeightingMethod,
    forecast_observation_to_dict,
    reference_observation_to_dict,
    realization_observation_to_dict,
)
from .pit import forecast_as_of


@dataclass
class WeatherStore:
    bitemporal: BitemporalReferenceStore = field(default_factory=BitemporalReferenceStore)
    forecasts: list[WeatherForecastObservation] = field(default_factory=list)
    realizations: list[WeatherRealizationObservation] = field(default_factory=list)
    references: list[WeatherReferenceObservation] = field(default_factory=list)
    _version_counter: int = 0

    @staticmethod
    def forecast_entity_key(obs: WeatherForecastObservation) -> str:
        return ":".join(
            (
                obs.source_product,
                obs.canonical_weather_indicator,
                obs.region_type.value,
                obs.region_id,
                obs.weighting_method.value,
                obs.target_start,
                obs.target_end,
                obs.forecast_issue_time,
            )
        )

    @staticmethod
    def realization_entity_key(obs: WeatherRealizationObservation) -> str:
        return ":".join(
            (
                obs.source_product,
                obs.canonical_weather_indicator,
                obs.region_type.value,
                obs.region_id,
                obs.weighting_method.value,
                obs.period_start,
                obs.period_end,
            )
        )

    @staticmethod
    def reference_entity_key(obs: WeatherReferenceObservation) -> str:
        return f"{obs.reference_type.value}:{obs.reference_id}:{obs.reference_version}"

    def _close_open_knowledge_version(
        self,
        *,
        kind: ReferenceKind,
        entity_key: str,
        known_from: str,
        content_hash: str,
    ) -> bool:
        updated: list[ReferenceRecord] = []
        duplicate = False
        for existing in self.bitemporal._records:
            if (
                existing.kind == kind
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

    def add_forecast(self, obs: WeatherForecastObservation) -> None:
        if not obs.forecast_available_time:
            raise ValueError("forecast_available_time is required")
        entity_key = self.forecast_entity_key(obs)
        if self._close_open_knowledge_version(
            kind=ReferenceKind.WEATHER_FORECAST,
            entity_key=entity_key,
            known_from=obs.forecast_available_time,
            content_hash=obs.content_hash,
        ):
            return
        self.forecasts.append(obs)
        self._version_counter += 1
        self.bitemporal.append(
            ReferenceRecord(
                kind=ReferenceKind.WEATHER_FORECAST,
                entity_key=entity_key,
                record_id=f"{entity_key}:v{self._version_counter}",
                record_version=self._version_counter,
                valid_from=obs.target_start,
                valid_to=obs.target_end,
                known_from=obs.forecast_available_time,
                payload=forecast_observation_to_dict(obs),
                quality_flags=obs.quality_flags,
            )
        )

    def add_forecasts(self, observations: tuple[WeatherForecastObservation, ...]) -> int:
        before = len(self.forecasts)
        for obs in observations:
            self.add_forecast(obs)
        return len(self.forecasts) - before

    def add_realization(self, obs: WeatherRealizationObservation) -> None:
        if not obs.available_time:
            raise ValueError("realization available_time is required")
        entity_key = self.realization_entity_key(obs)
        if self._close_open_knowledge_version(
            kind=ReferenceKind.WEATHER_REALIZATION,
            entity_key=entity_key,
            known_from=obs.available_time,
            content_hash=obs.content_hash,
        ):
            return
        self.realizations.append(obs)
        self._version_counter += 1
        self.bitemporal.append(
            ReferenceRecord(
                kind=ReferenceKind.WEATHER_REALIZATION,
                entity_key=entity_key,
                record_id=f"{entity_key}:v{self._version_counter}",
                record_version=self._version_counter,
                valid_from=obs.period_start,
                valid_to=obs.period_end,
                known_from=obs.available_time,
                payload=realization_observation_to_dict(obs),
                quality_flags=obs.quality_flags,
            )
        )

    def add_realizations(self, observations: tuple[WeatherRealizationObservation, ...]) -> int:
        before = len(self.realizations)
        for obs in observations:
            self.add_realization(obs)
        return len(self.realizations) - before

    def add_reference(self, obs: WeatherReferenceObservation) -> None:
        if not obs.available_from:
            raise ValueError("reference available_from is required")
        entity_key = self.reference_entity_key(obs)
        if self._close_open_knowledge_version(
            kind=ReferenceKind.WEATHER_REFERENCE,
            entity_key=entity_key,
            known_from=obs.available_from,
            content_hash=obs.content_hash,
        ):
            return
        self.references.append(obs)
        self._version_counter += 1
        self.bitemporal.append(
            ReferenceRecord(
                kind=ReferenceKind.WEATHER_REFERENCE,
                entity_key=entity_key,
                record_id=f"{entity_key}:v{self._version_counter}",
                record_version=self._version_counter,
                valid_from=obs.available_from,
                known_from=obs.available_from,
                payload=reference_observation_to_dict(obs),
                quality_flags=obs.quality_flags,
            )
        )

    def add_references(self, observations: tuple[WeatherReferenceObservation, ...]) -> int:
        before = len(self.references)
        for obs in observations:
            self.add_reference(obs)
        return len(self.references) - before

    def forecast_vintage_as_of(
        self,
        *,
        issue_time: str,
        target_time: str,
        decision_time: str,
        region_type: WeatherRegionType,
        region_id: str,
        variable: WeatherVariable,
        weighting_method: WeatherWeightingMethod,
    ) -> WeatherForecastObservation | None:
        candidates = [obs for obs in self.forecasts if obs.forecast_issue_time == issue_time]
        return forecast_as_of(
            candidates,
            target_time=target_time,
            decision_time=decision_time,
            region_type=region_type,
            region_id=region_id,
            variable=variable,
            weighting_method=weighting_method,
        )

    def stats(self) -> dict[str, int]:
        return {
            "forecast_count": len(self.forecasts),
            "realization_count": len(self.realizations),
            "reference_count": len(self.references),
            "bitemporal_records": len(self.bitemporal._records),
        }


__all__ = ["WeatherStore"]

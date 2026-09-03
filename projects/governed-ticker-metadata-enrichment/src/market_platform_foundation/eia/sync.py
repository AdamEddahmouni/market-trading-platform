"""Incremental EIA sync operations — scheduler-friendly entry points."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .contracts import EnergyHistoryClass, EnergyReleaseFamily
from .live import api_key_present, load_api_key
from .normalize import normalize_api_rows
from .quality import EiaQualityFlag
from .registry import FULL_REGISTRY, RegistryEntry, registry_for_release
from .store import EiaStore
from .transport import EiaTransport, EiaTransportError


@dataclass
class EiaSyncCheckpoint:
    last_petroleum_period_end: str = ""
    last_natural_gas_period_end: str = ""
    overlap_weeks: int = 2


@dataclass
class EiaSync:
    transport: EiaTransport | None = None
    store: EiaStore = field(default_factory=EiaStore)
    checkpoint: EiaSyncCheckpoint = field(default_factory=EiaSyncCheckpoint)

    def _transport(self) -> EiaTransport:
        if self.transport is not None:
            return self.transport
        key = load_api_key()
        if not key:
            raise EiaTransportError("AUTH_UNAVAILABLE: EIA_API_KEY unavailable")
        self.transport = EiaTransport(api_key=key)
        return self.transport

    @staticmethod
    def _query_params(entry: RegistryEntry, start: str = "") -> dict[str, Any]:
        params: dict[str, Any] = {
            "frequency": entry.frequency,
            "data[0]": entry.data_column,
            "facets[series][]": entry.series,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "length": 8,
        }
        if start:
            params["start"] = start
        return params

    def sync_registry_entry(
        self,
        entry: RegistryEntry,
        *,
        observed_time: str | None = None,
        start: str = "",
    ) -> int:
        transport = self._transport()
        now = observed_time or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            rows, _meta = transport.query_data_paginated(entry.route, params=self._query_params(entry, start=start))
        except EiaTransportError:
            return 0
        observations = normalize_api_rows(
            rows,
            entry=entry,
            observed_time=now,
            retrieved_time=now,
            history_class=EnergyHistoryClass.CURRENT_API_HISTORY,
        )
        return self.store.add_observations(tuple(observations))

    def sync_eia_petroleum(self) -> dict[str, Any]:
        count = 0
        for entry in registry_for_release(EnergyReleaseFamily.WPSR).values():
            count += self.sync_registry_entry(entry)
        return {"release_family": "WPSR", "observations_added": count}

    def sync_eia_natural_gas_storage(self) -> dict[str, Any]:
        count = 0
        for entry in registry_for_release(EnergyReleaseFamily.WNGSR).values():
            count += self.sync_registry_entry(entry)
        return {"release_family": "WNGSR", "observations_added": count}

    def sync_energy_fundamentals(self) -> dict[str, Any]:
        petroleum = self.sync_eia_petroleum()
        gas = self.sync_eia_natural_gas_storage()
        return {"petroleum": petroleum, "natural_gas": gas}

    def sync_wpsr_release(self) -> dict[str, Any]:
        return self.sync_eia_petroleum()

    def sync_wngsr_release(self) -> dict[str, Any]:
        return self.sync_eia_natural_gas_storage()

    def auth_status(self) -> dict[str, Any]:
        return {
            "api_key_present": api_key_present(),
            "quality_flags": [] if api_key_present() else [EiaQualityFlag.AUTH_UNAVAILABLE.value],
        }


__all__ = [
    "EiaSync",
    "EiaSyncCheckpoint",
]

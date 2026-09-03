"""Synchronization operations for FRED V1 granular and V2 release bulk paths."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from .normalize import normalize_v1_observation_row, normalize_v2_observation_row
from .reconcile import configured_series_for_release, reconcile_current_values, release_snapshot_metadata, utc_now_iso
from .registry import TIER1_REGISTRY, lookup_canonical
from .store import FredStore
from .transport import FredTransportError
from .v1_client import FredV1Client
from .v2_client import FredV2Client


@dataclass
class FredSyncCheckpoint:
    last_series_update_check: str = ""
    release_last_updated: dict[int, dict[str, str]] = field(default_factory=dict)


@dataclass
class FredSync:
    v1: FredV1Client
    v2: FredV2Client
    store: FredStore = field(default_factory=FredStore)
    checkpoint: FredSyncCheckpoint = field(default_factory=FredSyncCheckpoint)

    def sync_series(
        self,
        series_id: str,
        *,
        observation_start: str = "",
        observation_end: str = "",
        output_type: int = 1,
        retrieved_time: str | None = None,
    ) -> int:
        retrieved = retrieved_time or utc_now_iso()
        payload = self.v1.series_observations(
            series_id,
            observation_start=observation_start,
            observation_end=observation_end,
            output_type=output_type,
        )
        entry = next((e for e in TIER1_REGISTRY if e.fred_series_id == series_id), None)
        if entry is None:
            return 0
        rows = payload.get("observations", [])
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            obs = normalize_v1_observation_row(
                row,
                entry=entry,
                retrieved_time=retrieved,
                observed_time=retrieved,
            )
            self.store.add_observation(obs)
            count += 1
        return count

    def sync_series_updates(self, *, start_time: str = "", limit: int = 1000) -> list[str]:
        payload = self.v1.series_updates(start_time=start_time, limit=limit)
        series_ids = [
            str(row.get("id", ""))
            for row in payload.get("seriess", [])
            if isinstance(row, dict)
        ]
        tier1 = [sid for sid in series_ids if any(e.fred_series_id == sid for e in TIER1_REGISTRY)]
        self.checkpoint.last_series_update_check = utc_now_iso()
        return tier1

    def sync_vintages(self, series_id: str, *, retrieved_time: str | None = None) -> int:
        retrieved = retrieved_time or utc_now_iso()
        payload = self.v1.series_observations(series_id, output_type=2)
        entry = next((e for e in TIER1_REGISTRY if e.fred_series_id == series_id), None)
        if entry is None:
            return 0
        count = 0
        for row in payload.get("observations", []):
            if isinstance(row, dict):
                obs = normalize_v1_observation_row(
                    row,
                    entry=entry,
                    retrieved_time=retrieved,
                    observed_time=retrieved,
                )
                self.store.add_observation(obs)
                count += 1
        return count

    def sync_release_v1(self, release_id: int) -> dict[str, Any]:
        release = self.v1.release(release_id)
        dates = self.v1.release_dates(release_id)
        series_payload = self.v1.release_series(release_id, limit=1000)
        sources = self.v1.release_sources(release_id)
        return {
            "release": release.get("releases", [{}])[0] if release.get("releases") else {},
            "dates_count": len(dates.get("release_dates", [])),
            "series_count": len(series_payload.get("seriess", [])),
            "sources_count": len(sources.get("sources", [])),
        }

    def sync_release_v2(
        self,
        release_id: int,
        *,
        max_pages: int = 100,
        retry_on_mixed: bool = True,
    ) -> dict[str, Any]:
        started = utc_now_iso()
        prior = self.checkpoint.release_last_updated.get(release_id, {})
        snapshot = self.v2.fetch_release_observations(release_id, max_pages=max_pages)
        configured = configured_series_for_release(release_id)
        from .reconcile import detect_mixed_release_update

        consistency, flags = detect_mixed_release_update(
            snapshot,
            configured_series=configured,
            prior_last_updated=prior,
            retrieval_started=started,
        )
        if retry_on_mixed and "MIXED_RELEASE_UPDATE" in flags:
            snapshot = self.v2.fetch_release_observations(release_id, max_pages=max_pages)
            consistency, flags = detect_mixed_release_update(
                snapshot,
                configured_series=configured,
                prior_last_updated=prior,
                retrieval_started=started,
            )
        finished = utc_now_iso()
        hashes = [
            hashlib.sha256(json.dumps(page.raw, sort_keys=True, default=str).encode()).hexdigest()
            for page in snapshot.pages
        ]
        observed = finished
        for page in snapshot.pages:
            for row in page.observations:
                obs = normalize_v2_observation_row(
                    row,
                    retrieved_time=finished,
                    observed_time=observed,
                )
                if obs is not None:
                    self.store.add_observation(obs)
        self.checkpoint.release_last_updated[release_id] = dict(snapshot.series_last_updated)
        meta = release_snapshot_metadata(
            snapshot,
            retrieval_started=started,
            retrieval_finished=finished,
            response_hashes=hashes,
        )
        meta["consistency_result"] = consistency
        meta["quality_flags"] = list(dict.fromkeys(list(meta.get("quality_flags", [])) + list(flags)))
        return meta

    def reconcile_release(self, release_id: int, series_id: str) -> dict[str, Any]:
        entry = lookup_canonical(next(e.canonical_indicator_id for e in TIER1_REGISTRY if e.fred_series_id == series_id))
        if entry is None:
            return {"match": False, "quality_flags": ["SERIES_UNAVAILABLE"]}
        v1_payload = self.v1.series_observations(series_id, output_type=1, sort_order="desc", limit=1)
        rows = v1_payload.get("observations", [])
        v1_obs = None
        target_date = ""
        if rows and isinstance(rows[0], dict):
            target_date = str(rows[0].get("date", ""))
            v1_obs = normalize_v1_observation_row(
                rows[0],
                entry=entry,
                retrieved_time=utc_now_iso(),
                observed_time=utc_now_iso(),
            )
        v2_page = self.v2.fetch_release_observations(release_id, max_pages=10)
        v2_obs = None
        for page in v2_page.pages:
            for row in page.observations:
                if str(row.get("series_id")) == series_id and str(row.get("date", "")) == target_date:
                    v2_obs = normalize_v2_observation_row(
                        row,
                        retrieved_time=utc_now_iso(),
                        observed_time=utc_now_iso(),
                    )
                    break
            if v2_obs is not None:
                break
        result = reconcile_current_values(v1_observation=v1_obs, v2_observation=v2_obs)
        return {
            "series_id": result.series_id,
            "observation_date": result.observation_date,
            "v1_value": result.v1_value,
            "v2_value": result.v2_value,
            "match": result.match,
            "quality_flags": list(result.quality_flags),
        }

    def sync_macro_core(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in TIER1_REGISTRY:
            if entry.frequency == "Daily":
                try:
                    counts[entry.fred_series_id] = self.sync_series(entry.fred_series_id)
                except FredTransportError:
                    counts[entry.fred_series_id] = 0
        return counts


def sync_fred_from_env() -> FredSync:
    from .live import transport_from_env

    v1, v2 = transport_from_env()
    return FredSync(v1=v1, v2=v2)


__all__ = ["FredSync", "FredSyncCheckpoint", "sync_fred_from_env"]

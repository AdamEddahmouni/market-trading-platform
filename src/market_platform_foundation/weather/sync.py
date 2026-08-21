"""Scheduler-neutral incremental weather capture operations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterable

from .cpc import parse_cpc_climatology, parse_cpc_forecast, parse_cpc_realized
from .normalize import normalize_nws_forecast
from .nws import NwsForecastCapture, NwsPointMapping
from .store import WeatherStore


@dataclass
class WeatherSyncCheckpoint:
    captured_issue_dates: set[str] = field(default_factory=set)
    latest_forecast_issue: str = ""
    latest_realized_date: str = ""
    overlap_days: int = 2
    max_backfill_dates: int = 7


@dataclass
class WeatherSync:
    store: WeatherStore = field(default_factory=WeatherStore)
    checkpoint: WeatherSyncCheckpoint = field(default_factory=WeatherSyncCheckpoint)

    def issues_to_check(self, available_issue_dates: Iterable[str]) -> tuple[str, ...]:
        available = sorted(set(available_issue_dates))
        if not available:
            return ()
        if not self.checkpoint.latest_forecast_issue:
            return tuple(available[-self.checkpoint.max_backfill_dates :])
        latest = date.fromisoformat(self.checkpoint.latest_forecast_issue)
        threshold = latest - timedelta(days=max(self.checkpoint.overlap_days - 1, 0))
        return tuple(item for item in available if date.fromisoformat(item) >= threshold)

    def capture_forecast_vintage(
        self,
        text: str,
        *,
        forecast_available_time: str,
        source_file_id: str = "",
        source_file_last_modified: str = "",
        provider_first_observed_time: str = "",
        retrieved_time: str = "",
        ingested_time: str = "",
    ) -> dict[str, object]:
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        rows = parse_cpc_forecast(
            text,
            forecast_available_time=forecast_available_time,
            source_file_id=source_file_id,
            source_file_last_modified=source_file_last_modified,
            provider_first_observed_time=provider_first_observed_time,
            retrieved_time=retrieved_time,
            ingested_time=ingested_time,
            content_hash=content_hash,
            provenance_ref=f"cpc:{source_file_id}",
        )
        added = self.store.add_forecasts(rows)
        issue_date = rows[0].forecast_issue_time[:10] if rows else ""
        if issue_date:
            self.checkpoint.captured_issue_dates.add(issue_date)
            self.checkpoint.latest_forecast_issue = max(
                self.checkpoint.latest_forecast_issue,
                issue_date,
            )
        return {
            "issue_date": issue_date,
            "observations_parsed": len(rows),
            "observations_added": added,
            "content_hash": content_hash,
        }

    def sync_cpc_degree_days(
        self,
        text: str,
        *,
        available_time: str,
        source_file_id: str = "",
        retrieved_time: str = "",
        ingested_time: str = "",
    ) -> dict[str, object]:
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        rows = parse_cpc_realized(
            text,
            available_time=available_time,
            source_file_id=source_file_id,
            retrieved_time=retrieved_time,
            ingested_time=ingested_time,
            content_hash=content_hash,
        )
        added = self.store.add_realizations(rows)
        latest = max((row.period_start[:10] for row in rows), default="")
        self.checkpoint.latest_realized_date = max(self.checkpoint.latest_realized_date, latest)
        return {"observations_parsed": len(rows), "observations_added": added, "latest_date": latest}

    def sync_cpc_climatology(
        self,
        text: str,
        *,
        normal_period: str,
        normal_version: str,
        weight_vintage: str,
        available_time: str,
        source_file_id: str = "",
    ) -> dict[str, object]:
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        rows = parse_cpc_climatology(
            text,
            normal_period=normal_period,
            normal_version=normal_version,
            weight_vintage=weight_vintage,
            available_time=available_time,
            source_file_id=source_file_id,
            content_hash=content_hash,
        )
        added = self.store.add_references(rows)
        return {"references_parsed": len(rows), "references_added": added, "content_hash": content_hash}

    def sync_nws_current_forecast(
        self,
        capture: NwsForecastCapture,
        *,
        mapping: NwsPointMapping,
        ingested_time: str,
        content_hash: str,
    ) -> dict[str, object]:
        rows = normalize_nws_forecast(
            capture,
            mapping=mapping,
            ingested_time=ingested_time,
            content_hash=content_hash,
        )
        added = self.store.add_forecasts(rows)
        return {
            "forecast_kind": capture.forecast_kind,
            "observations_parsed": len(rows),
            "observations_added": added,
            "mapping_identity": mapping.mapping_identity,
            "content_hash": content_hash,
        }


def capture_forecast_vintage(text: str, **metadata) -> tuple[WeatherStore, dict[str, object]]:
    sync = WeatherSync()
    return sync.store, sync.capture_forecast_vintage(text, **metadata)


__all__ = ["WeatherSync", "WeatherSyncCheckpoint", "capture_forecast_vintage"]

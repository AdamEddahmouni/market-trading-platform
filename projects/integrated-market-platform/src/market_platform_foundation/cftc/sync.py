"""Incremental CFTC COT synchronization — idempotent, scheduler-friendly."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from .capture import build_cot_envelope, hash_rows
from .contracts import CotPositionScope
from .datasets import CotDataset, dataset_spec
from .mapping import CotProductMapper
from .normalize import normalize_api_rows
from .quality import CotQualityFlag
from .release_schedule import latest_published_release, next_expected_release
from .store import CotStore
from .transport import CotTransport, CotTransportError


@dataclass
class CotSyncCheckpoint:
    latest_position_date: str = ""
    latest_publication_date: str = ""
    latest_dataset: str = ""
    last_successful_sync: str = ""
    note: str = "checkpoint_is_not_completeness_proof"


@dataclass
class CotSync:
    store: CotStore
    transport: CotTransport
    mapper: CotProductMapper = field(default_factory=CotProductMapper)
    checkpoint: CotSyncCheckpoint = field(default_factory=CotSyncCheckpoint)
    _seen_hashes: set[str] = field(default_factory=set)

    def sync_cot(
        self,
        *,
        datasets: tuple[CotDataset, ...] | None = None,
        position_dates: tuple[str, ...] | None = None,
        market_filter: str = "",
        reconcile_latest: int = 2,
        historical_backfill: bool = False,
    ) -> dict[str, Any]:
        observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        active_datasets = datasets or (
            CotDataset.TFF_FUTURES_ONLY,
            CotDataset.DISAGGREGATED_FUTURES_ONLY,
            CotDataset.LEGACY_FUTURES_ONLY,
        )
        results: list[dict[str, Any]] = []

        if position_dates:
            dates = position_dates
        else:
            from datetime import timedelta

            latest_pub = latest_published_release()
            if latest_pub is None:
                return {
                    "status": "expected_not_yet_available",
                    "quality_flags": [CotQualityFlag.EXPECTED_NOT_YET_AVAILABLE.value],
                    "next_expected_release": str(next_expected_release() or ""),
                    "checkpoint": self.checkpoint.__dict__,
                }
            dates = tuple(
                (latest_pub - timedelta(days=7 * offset)).isoformat()
                for offset in range(reconcile_latest)
            )

        for dataset in active_datasets:
            spec = dataset_spec(dataset)
            for pos_date in dates:
                where_parts = [f"report_date_as_yyyy_mm_dd='{pos_date[:10]}'"]
                if market_filter:
                    where_parts.append(f"market_and_exchange_names like '%{market_filter}%'")
                where = " AND ".join(where_parts)
                try:
                    rows = self.transport.query_dataset(
                        dataset,
                        where=where,
                        limit=5000,
                    )
                except CotTransportError as exc:
                    results.append(
                        {
                            "dataset": spec.dataset_id,
                            "position_date": pos_date,
                            "status": "source_unavailable",
                            "error": str(exc),
                            "quality_flags": [CotQualityFlag.SOURCE_UNAVAILABLE.value],
                        }
                    )
                    continue

                if not rows:
                    results.append(
                        {
                            "dataset": spec.dataset_id,
                            "position_date": pos_date,
                            "status": "not_yet_released_or_missing",
                            "quality_flags": [CotQualityFlag.REPORT_NOT_YET_RELEASED.value],
                        }
                    )
                    continue

                payload_hash = hash_rows(rows)
                if payload_hash in self._seen_hashes:
                    results.append(
                        {
                            "dataset": spec.dataset_id,
                            "position_date": pos_date,
                            "status": "idempotent_skip",
                            "content_hash": payload_hash,
                        }
                    )
                    continue

                observations = normalize_api_rows(
                    rows,
                    spec=spec,
                    mapper=self.mapper,
                    observed_time=observed,
                    retrieved_time=observed,
                    historical_backfill=historical_backfill,
                )
                added = self.store.add_observations(observations)
                self._seen_hashes.add(payload_hash)
                envelope = build_cot_envelope(
                    dataset_id=spec.dataset_id,
                    report_family=spec.report_family.value,
                    position_scope=spec.position_scope.value,
                    position_date=pos_date[:10],
                    row_count=len(rows),
                    raw_payload_hash=payload_hash,
                    retrieved_time=observed,
                    first_observed_time=observed,
                    query_identity=where,
                )
                self.checkpoint.latest_position_date = pos_date[:10]
                self.checkpoint.latest_dataset = spec.dataset_id
                self.checkpoint.last_successful_sync = observed
                results.append(
                    {
                        "dataset": spec.dataset_id,
                        "position_date": pos_date,
                        "status": "captured",
                        "observations_added": added,
                        "content_hash": payload_hash,
                        "envelope": envelope,
                    }
                )

        return {
            "results": results,
            "checkpoint": self.checkpoint.__dict__,
            "next_expected_release": str(next_expected_release() or ""),
        }


def sync_cot(
    store: CotStore | None = None,
    *,
    transport: CotTransport | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    sync = CotSync(
        store=store or CotStore(),
        transport=transport or CotTransport(),
    )
    return sync.sync_cot(**kwargs)


__all__ = ["CotSync", "CotSyncCheckpoint", "sync_cot"]

"""Incremental SEC FTD synchronization. Idempotent, scheduler-friendly."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..sec_edgar.transport import SecTransport
from ..short_intelligence.identity import SymbolMap
from ..short_intelligence.store import ShortIntelligenceStore
from .capture import build_archive_envelope
from .discovery import discover_archives
from .normalize import normalize_ftd_archive
from .parser import parse_archive_bytes
from .periods import FtdPeriod, parse_period_key
from .transport import FtdTransport


@dataclass
class FtdSyncCheckpoint:
    latest_period_discovered: str = ""
    latest_period_captured: str = ""
    latest_file_hash: str = ""
    note: str = "checkpoint_is_not_completeness_proof"


@dataclass
class FtdSync:
    store: ShortIntelligenceStore
    symbol_map: SymbolMap
    transport: FtdTransport
    checkpoint: FtdSyncCheckpoint = field(default_factory=FtdSyncCheckpoint)
    _seen_observations: set[str] = field(default_factory=set)

    def sync_ftd(
        self,
        *,
        period_keys: tuple[str, ...] | None = None,
        requested_symbols: tuple[str, ...] | None = None,
        reconcile_latest: int = 2,
        historical_backfill: bool = False,
    ) -> dict[str, Any]:
        observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if period_keys:
            periods = [parse_period_key(key) for key in period_keys]
        else:
            discovered = discover_archives(self.transport.transport)
            if not discovered:
                raise OSError("SEC_FTD_DISCOVERY_EMPTY")
            self.checkpoint.latest_period_discovered = discovered[0].period.period_key
            periods = [item.period for item in discovered[: max(1, reconcile_latest)]]
        results: list[dict[str, Any]] = []
        for period in periods:
            capture = self.transport.fetch_archive(
                period,
                retrieved_time=observed,
                first_observed_time=observed,
            )
            parsed = parse_archive_bytes(capture.content_bytes, period_key=period.period_key)
            envelope = build_archive_envelope(capture, record_count=parsed.record_count)
            rows = normalize_ftd_archive(
                parsed,
                period=period,
                symbol_map=self.symbol_map,
                observed_time=observed,
                retrieved_time=observed,
                requested_symbols=requested_symbols,
                historical_backfill=historical_backfill,
            )
            added = 0
            for row in rows:
                identity = f"{row.cusip}:{row.settlement_date}:{row.content_hash}"
                if identity in self._seen_observations:
                    continue
                self.store.add_ftd(row)
                self._seen_observations.add(identity)
                added += 1
            self.checkpoint.latest_period_captured = period.period_key
            self.checkpoint.latest_file_hash = capture.content_hash
            results.append(
                {
                    "period_key": period.period_key,
                    "content_hash": capture.content_hash,
                    "record_count": parsed.record_count,
                    "observations_added": added,
                    "replaced_prior_hash": capture.replaced_prior_hash,
                    "envelope": envelope,
                }
            )
        return {"periods": results, "checkpoint": self.checkpoint.__dict__}


def sync_ftd_from_env(
    store: ShortIntelligenceStore,
    symbol_map: SymbolMap,
    *,
    period_keys: tuple[str, ...] | None = None,
    requested_symbols: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    from .live import transport_from_env

    transport = FtdTransport(transport_from_env())
    sync = FtdSync(store=store, symbol_map=symbol_map, transport=transport)
    return sync.sync_ftd(period_keys=period_keys, requested_symbols=requested_symbols)


__all__ = ["FtdSync", "FtdSyncCheckpoint", "sync_ftd_from_env"]

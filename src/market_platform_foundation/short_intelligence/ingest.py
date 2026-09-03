"""Incremental and bounded historical sync operations. No embedded scheduler."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..finra.query import query_reg_sho_daily, query_short_interest
from ..finra.short_interest import normalize_short_interest_row
from ..finra.short_sale_volume import normalize_short_sale_row
from ..finra.transport import FinraTransport
from ..cboe_regsho.threshold import normalize_threshold_file as normalize_cboe_threshold_file
from ..cboe_regsho.threshold import parse_threshold_file as parse_cboe_threshold_file
from ..cboe_regsho.transport import CboeTransport
from ..finra.otc_threshold import normalize_otc_threshold_rows
from ..finra.query import query_otc_threshold
from ..nyse_regsho.threshold import normalize_threshold_file as normalize_nyse_threshold_file
from ..nyse_regsho.threshold import parse_threshold_file as parse_nyse_threshold_file
from ..nasdaq_regsho.threshold import normalize_threshold_file as normalize_nasdaq_threshold_file
from ..nasdaq_regsho.threshold import parse_threshold_file as parse_nasdaq_threshold_file
from ..nasdaq_regsho.transport import NasdaqTransport
from ..nyse_regsho.transport import NyseTransport
from ..sec_ftd.sync import FtdSync
from ..sec_ftd.transport import FtdTransport
from .identity import SymbolMap
from .store import ShortIntelligenceStore


@dataclass
class IngestCheckpoint:
    last_short_interest_publication_ingested: str = ""
    last_short_sale_trade_date_ingested: str = ""
    last_nasdaq_threshold_date_ingested: str = ""
    last_nyse_threshold_date_ingested: str = ""
    last_finra_otc_threshold_date_ingested: str = ""
    last_cboe_threshold_date_ingested: str = ""
    last_ftd_period_captured: str = ""
    note: str = "checkpoint_is_not_completeness_proof"


@dataclass
class ShortIntelligenceIngest:
    store: ShortIntelligenceStore
    symbol_map: SymbolMap
    finra: FinraTransport | None = None
    nasdaq: NasdaqTransport | None = None
    nyse: NyseTransport | None = None
    cboe: CboeTransport | None = None
    ftd: FtdTransport | None = None
    checkpoint: IngestCheckpoint = field(default_factory=IngestCheckpoint)

    def sync_short_interest(self, *, symbol: str, settlement_date: str | None = None) -> dict[str, Any]:
        if self.finra is None:
            raise OSError("SOURCE_UNAVAILABLE")
        observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        response = query_short_interest(self.finra, symbol=symbol, settlement_date=settlement_date, limit=50)
        rows = [
            normalize_short_interest_row(
                row,
                symbol_map=self.symbol_map,
                observed_time=observed,
                retrieved_time=observed,
                finra_request_id=response.request_id,
            )
            for row in response.records
        ]
        for row in rows:
            self.store.add_short_interest(row)
            if row.publication_date:
                self.checkpoint.last_short_interest_publication_ingested = row.publication_date
        return {"count": len(rows), "empty": not rows, "finra_request_id": response.request_id}

    def sync_short_sale_volume(self, *, symbol: str, trade_report_date: str | None = None) -> dict[str, Any]:
        if self.finra is None:
            raise OSError("SOURCE_UNAVAILABLE")
        observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        response = query_reg_sho_daily(
            self.finra, symbol=symbol, trade_report_date=trade_report_date, limit=200
        )
        rows = [
            normalize_short_sale_row(
                row,
                symbol_map=self.symbol_map,
                observed_time=observed,
                retrieved_time=observed,
                finra_request_id=response.request_id,
            )
            for row in response.records
        ]
        for row in rows:
            self.store.add_short_sale(row)
            self.checkpoint.last_short_sale_trade_date_ingested = row.trade_report_date
        return {"count": len(rows), "empty": not rows, "finra_request_id": response.request_id}

    def sync_threshold_list(self, *, trade_date: str, symbols: tuple[str, ...] | None = None) -> dict[str, Any]:
        return self.sync_nasdaq_threshold_list(trade_date=trade_date, symbols=symbols)

    def sync_nasdaq_threshold_list(
        self, *, trade_date: str, symbols: tuple[str, ...] | None = None
    ) -> dict[str, Any]:
        if self.nasdaq is None:
            raise OSError("SOURCE_UNAVAILABLE")
        observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        raw = self.nasdaq.fetch_threshold_file(trade_date)
        parsed = parse_nasdaq_threshold_file(raw, trade_date=trade_date)
        rows = normalize_nasdaq_threshold_file(
            parsed,
            symbol_map=self.symbol_map,
            observed_time=observed,
            retrieved_time=observed,
            requested_symbols=symbols,
        )
        for row in rows:
            self.store.add_threshold(row)
        self.checkpoint.last_nasdaq_threshold_date_ingested = trade_date[:10]
        return {"count": len(rows), "content_hash": parsed.content_hash, "source": "NASDAQ"}

    def sync_nyse_threshold_list(
        self,
        *,
        trade_date: str,
        market: str,
        symbols: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        if self.nyse is None:
            raise OSError("SOURCE_UNAVAILABLE")
        observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        raw = self.nyse.fetch_threshold_file(trade_date, market=market)
        parsed = parse_nyse_threshold_file(raw, trade_date=trade_date, source_market=market)
        rows = normalize_nyse_threshold_file(
            parsed,
            symbol_map=self.symbol_map,
            observed_time=observed,
            retrieved_time=observed,
            requested_symbols=symbols,
        )
        for row in rows:
            self.store.add_threshold(row)
        self.checkpoint.last_nyse_threshold_date_ingested = trade_date[:10]
        return {
            "count": len(rows),
            "content_hash": parsed.content_hash,
            "source": "NYSE_GROUP",
            "market": market,
        }

    def sync_finra_otc_threshold_list(
        self,
        *,
        trade_date: str,
        symbols: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        if self.finra is None:
            raise OSError("SOURCE_UNAVAILABLE")
        observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        response = query_otc_threshold(self.finra, trade_date=trade_date, limit=5000)
        rows = normalize_otc_threshold_rows(
            response.records,
            symbol_map=self.symbol_map,
            observed_time=observed,
            retrieved_time=observed,
            finra_request_id=response.request_id,
            requested_symbols=symbols,
        )
        for row in rows:
            self.store.add_threshold(row)
        self.checkpoint.last_finra_otc_threshold_date_ingested = trade_date[:10]
        return {
            "count": len(rows),
            "empty": not rows,
            "finra_request_id": response.request_id,
            "source": "FINRA_OTC",
        }

    def sync_cboe_threshold_list(
        self, *, trade_date: str, symbols: tuple[str, ...] | None = None
    ) -> dict[str, Any]:
        if self.cboe is None:
            raise OSError("SOURCE_UNAVAILABLE")
        observed = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        raw = self.cboe.fetch_threshold_file(trade_date)
        parsed = parse_cboe_threshold_file(raw, trade_date=trade_date)
        rows = normalize_cboe_threshold_file(
            parsed,
            symbol_map=self.symbol_map,
            observed_time=observed,
            retrieved_time=observed,
            requested_symbols=symbols,
        )
        for row in rows:
            self.store.add_threshold(row)
        self.checkpoint.last_cboe_threshold_date_ingested = trade_date[:10]
        return {"count": len(rows), "content_hash": parsed.content_hash, "source": "CBOE_BZX"}

    def sync_ftd(
        self,
        *,
        period_keys: tuple[str, ...] | None = None,
        requested_symbols: tuple[str, ...] | None = None,
        historical_backfill: bool = False,
    ) -> dict[str, object]:
        if self.ftd is None:
            raise OSError("SOURCE_UNAVAILABLE")
        sync = FtdSync(store=self.store, symbol_map=self.symbol_map, transport=self.ftd)
        result = sync.sync_ftd(
            period_keys=period_keys,
            requested_symbols=requested_symbols,
            historical_backfill=historical_backfill,
        )
        if result.get("periods"):
            self.checkpoint.last_ftd_period_captured = str(result["periods"][-1].get("period_key", ""))
        return result

    def reconcile(self) -> dict[str, str]:
        return {
            "mode": "overlap_replay_required_by_caller",
            "last_short_interest_publication_ingested": self.checkpoint.last_short_interest_publication_ingested,
            "last_short_sale_trade_date_ingested": self.checkpoint.last_short_sale_trade_date_ingested,
            "last_nasdaq_threshold_date_ingested": self.checkpoint.last_nasdaq_threshold_date_ingested,
            "last_nyse_threshold_date_ingested": self.checkpoint.last_nyse_threshold_date_ingested,
            "last_finra_otc_threshold_date_ingested": self.checkpoint.last_finra_otc_threshold_date_ingested,
            "last_cboe_threshold_date_ingested": self.checkpoint.last_cboe_threshold_date_ingested,
            "last_ftd_period_captured": self.checkpoint.last_ftd_period_captured,
            "note": self.checkpoint.note,
        }

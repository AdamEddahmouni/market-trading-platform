"""Lawful BAR_OHLCV_1M sources for Item 9 comparator dry-runs (no broker orders)."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo

from ...adapters.equity_intraday_jsonl import (
    COLLECTION_RELATIVE_PATH,
    SOURCE_OBJECT_ID,
    EquityIntradayJsonlAdapter,
)
from ...contracts.identity import normalized_event_id
from ...providers.adapters.moomoo_opend_equity_quote import (
    MOOMOO_TRANSPORT_NOT_IMPLEMENTED,
    opend_endpoint,
    opend_is_loopback,
    opend_reachable,
)

BAR_CAPABILITY = "BAR_OHLCV_1M"
ONE_MINUTE_NS = 60_000_000_000
US_EQUITY_BAR_TZ = ZoneInfo("America/New_York")

SOURCE_ADMITTED_EQUITY_INTRADAY = SOURCE_OBJECT_ID
SOURCE_MOOMOO_OPEND_KLINE_1M = "MOOMOO_OPEND_HISTORY_KLINE_1M"

_TOOLS_KLINE_PATH = Path(__file__).resolve().parents[4] / "tools" / "moomoo" / "opend_quote_transport.py"


@dataclass(frozen=True, slots=True)
class BarLoadResult:
    source_id: str
    instrument_id: str
    bars: tuple[dict[str, Any], ...]
    provenance: dict[str, Any]
    reason_code: str | None = None

    @property
    def ok(self) -> bool:
        return self.reason_code is None and bool(self.bars)


def simulator_bars(events: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Minimal BAR_OHLCV_1M rows for ``BarConservativeSimulator``, sorted by available_time."""

    rows: list[dict[str, Any]] = []
    for event in events:
        if str(event.get("event_type")) != BAR_CAPABILITY:
            continue
        available = event.get("available_time")
        payload = event.get("bar_payload")
        if available is None or not isinstance(payload, Mapping):
            continue
        rows.append(
            {
                "available_time": int(available),
                "bar_payload": dict(payload),
                "event_time": int(event.get("event_time") or available),
                "event_type": BAR_CAPABILITY,
                "instrument_id": str(event.get("instrument_id") or ""),
                "normalized_event_id": str(event.get("normalized_event_id") or ""),
            }
        )
    rows.sort(key=lambda row: int(row["available_time"]))
    return rows


def pit_visible_bars(
    bars: Sequence[Mapping[str, Any]],
    *,
    observation_time_ns: int,
    instrument_id: str | None = None,
) -> list[dict[str, Any]]:
    visible = [
        dict(bar)
        for bar in bars
        if int(bar["available_time"]) <= observation_time_ns
        and (instrument_id is None or str(bar.get("instrument_id") or "") == instrument_id)
    ]
    visible.sort(key=lambda row: int(row["available_time"]))
    return visible


def first_admissible_post_signal_bar(
    bars: Sequence[Mapping[str, Any]],
    *,
    signal_time_ns: int,
) -> dict[str, Any] | None:
    for bar in bars:
        if int(bar["available_time"]) > signal_time_ns:
            return dict(bar)
    return None


def _parse_moomoo_time_key_ns(time_key: str) -> int | None:
    text = str(time_key or "").strip()
    if not text:
        return None
    normalized = text.replace("T", " ")
    try:
        if len(normalized) >= 19:
            parsed = datetime.strptime(normalized[:19], "%Y-%m-%d %H:%M:%S")
        else:
            parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=US_EQUITY_BAR_TZ)
    return int(parsed.timestamp() * 1_000_000_000)


def normalize_moomoo_kline_row(
    row: Mapping[str, Any],
    *,
    instrument_id: str,
    fetched_at_ns: int,
) -> dict[str, Any] | None:
    """Map OpenD 1m kline row → canonical BAR_OHLCV_1M (bar end = available_time)."""

    bar_start_ns = _parse_moomoo_time_key_ns(str(row.get("time_key") or ""))
    if bar_start_ns is None:
        return None
    bar_end_ns = bar_start_ns + ONE_MINUTE_NS
    if bar_end_ns > fetched_at_ns:
        return None
    try:
        volume = int(float(row.get("volume") or 0))
    except (TypeError, ValueError):
        volume = 0
    source_record_id = f"{instrument_id}-1_MINUTE-{bar_start_ns // 1_000_000_000}"
    normalized_id = normalized_event_id(
        provider_id="moomoo.opend",
        venue_id="US",
        publisher_id="moomoo.opend",
        channel_id=instrument_id,
        source_instance_id=SOURCE_MOOMOO_OPEND_KLINE_1M,
        source_record_id=source_record_id,
        source_revision_id="1",
        event_family=BAR_CAPABILITY,
    )
    return {
        "available_time": bar_end_ns,
        "bar_payload": {
            "close": str(row.get("close")),
            "high": str(row.get("high")),
            "low": str(row.get("low")),
            "open": str(row.get("open")),
            "timeframe": "1_MINUTE",
            "volume": volume,
        },
        "channel_id": instrument_id,
        "event_time": bar_start_ns,
        "event_type": BAR_CAPABILITY,
        "instrument_id": instrument_id,
        "normalized_event_id": normalized_id,
        "publisher_id": "moomoo.opend",
        "source_instance_id": SOURCE_MOOMOO_OPEND_KLINE_1M,
        "source_record_id": source_record_id,
    }


def load_admitted_equity_intraday_bars(
    *,
    collection_root: Path,
    instrument_id: str,
    observation_time_ns: int,
    ingest_run_id: str = "item9-bar-ohlcv-dry-run",
) -> BarLoadResult:
    path = collection_root / COLLECTION_RELATIVE_PATH
    adapter = EquityIntradayJsonlAdapter(ingest_run_id=ingest_run_id)
    verify = adapter.verify_source_bytes(path)
    if verify:
        return BarLoadResult(
            source_id=SOURCE_ADMITTED_EQUITY_INTRADAY,
            instrument_id=instrument_id,
            bars=(),
            provenance={"path": str(path), "verify_reasons": verify},
            reason_code="ADMITTED_SOURCE_UNAVAILABLE",
        )
    ingested = adapter.ingest_path(path)
    all_bars = simulator_bars(ingested.canonical_events)
    visible = pit_visible_bars(all_bars, observation_time_ns=observation_time_ns, instrument_id=instrument_id)
    if not visible:
        return BarLoadResult(
            source_id=SOURCE_ADMITTED_EQUITY_INTRADAY,
            instrument_id=instrument_id,
            bars=(),
            provenance={
                "path": str(path),
                "canonical_count": len(all_bars),
                "observation_time_ns": observation_time_ns,
            },
            reason_code="EXPERIMENT_CONTRACT_MISMATCH",
        )
    return BarLoadResult(
        source_id=SOURCE_ADMITTED_EQUITY_INTRADAY,
        instrument_id=instrument_id,
        bars=tuple(visible),
        provenance={
            "path": str(path),
            "normalization_version": "phase3.equity-intraday-jsonl/1.0.0",
            "publisher_id": "yahoo-chart",
            "evidence_class": "ADMITTED_HISTORICAL_FIXTURE",
            "observation_time_ns": observation_time_ns,
        },
    )


def _load_tools_kline_module() -> Any | None:
    path = _TOOLS_KLINE_PATH
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("imp_opend_kline_transport", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:  # noqa: BLE001
        return None
    return module


def _transport_fetch_diag(
    payload: Mapping[str, Any],
    *,
    session_date: str,
    host: str,
    port: int,
    poll_attempt_index: int | None,
) -> dict[str, Any]:
    diag: dict[str, Any] = {
        "kline_session_date": session_date,
        "kline_start": payload.get("kline_start", session_date),
        "kline_end": payload.get("kline_end", session_date),
        "max_count_requested": payload.get("max_count_requested"),
        "raw_row_count": payload.get("raw_row_count", 0),
        "first_raw_time_key": payload.get("first_raw_time_key"),
        "last_raw_time_key": payload.get("last_raw_time_key"),
        "vendor_ret": payload.get("vendor_ret"),
        "vendor_ret_msg": payload.get("vendor_ret_msg"),
        "connection_host": payload.get("connection_host", host),
        "connection_port": payload.get("connection_port", port),
        "request_duration_ms": payload.get("request_duration_ms"),
        "protocol_error_category": payload.get("protocol_error_category"),
    }
    if poll_attempt_index is not None:
        diag["poll_attempt_index"] = int(poll_attempt_index)
    return diag


def load_moomoo_opend_kline_bars(
    *,
    instrument_id: str,
    observation_time_ns: int,
    fetched_at_ns: int | None = None,
    max_count: int = 1000,
    kline_rows: Sequence[Mapping[str, Any]] | None = None,
    poll_attempt_index: int | None = None,
) -> BarLoadResult:
    """Prospective 1m bars from loopback OpenD history kline (quote context only)."""

    fetched_at = fetched_at_ns if fetched_at_ns is not None else observation_time_ns
    host, port = opend_endpoint()
    session_date = datetime.fromtimestamp(
        int(observation_time_ns) / 1_000_000_000,
        tz=US_EQUITY_BAR_TZ,
    ).strftime("%Y-%m-%d")
    if kline_rows is None:
        if not opend_is_loopback(host) or not opend_reachable(host=host, port=port):
            unavailable_prov: dict[str, Any] = {
                "host": host,
                "port": port,
                "connection_host": host,
                "connection_port": port,
            }
            if poll_attempt_index is not None:
                unavailable_prov["poll_attempt_index"] = int(poll_attempt_index)
            return BarLoadResult(
                source_id=SOURCE_MOOMOO_OPEND_KLINE_1M,
                instrument_id=instrument_id,
                bars=(),
                provenance=unavailable_prov,
                reason_code="OPEND_UNAVAILABLE",
            )
        module = _load_tools_kline_module()
        fetcher = getattr(module, "fetch_history_kline_1m", None) if module is not None else None
        if not callable(fetcher):
            return BarLoadResult(
                source_id=SOURCE_MOOMOO_OPEND_KLINE_1M,
                instrument_id=instrument_id,
                bars=(),
                provenance={"transport": str(_TOOLS_KLINE_PATH)},
                reason_code=MOOMOO_TRANSPORT_NOT_IMPLEMENTED,
            )
        payload = fetcher(
            instrument_id,
            host=host,
            port=port,
            max_count=max(int(max_count), 1000),
            session_date=session_date,
        )
        if not isinstance(payload, dict):
            return BarLoadResult(
                source_id=SOURCE_MOOMOO_OPEND_KLINE_1M,
                instrument_id=instrument_id,
                bars=(),
                provenance={"host": host, "port": port},
                reason_code="MOOMOO_PROTOCOL_ERROR",
            )
        reason = payload.get("reason_code")
        fetch_diag = _transport_fetch_diag(
            payload,
            session_date=session_date,
            host=host,
            port=port,
            poll_attempt_index=poll_attempt_index,
        )
        if reason:
            return BarLoadResult(
                source_id=SOURCE_MOOMOO_OPEND_KLINE_1M,
                instrument_id=instrument_id,
                bars=(),
                provenance={"host": host, "port": port, "transport_reason": str(reason), **fetch_diag},
                reason_code=str(reason),
            )
        raw_rows = payload.get("rows") or ()
    else:
        raw_rows = kline_rows
        fetch_diag = {}
        if poll_attempt_index is not None:
            fetch_diag["poll_attempt_index"] = int(poll_attempt_index)

    raw_tuple = tuple(raw_rows)
    raw_time_keys = [
        str(row.get("time_key") or "")
        for row in raw_tuple
        if isinstance(row, Mapping) and row.get("time_key")
    ]
    window_provenance = {
        **fetch_diag,
        "kline_session_date": session_date,
        "kline_start": fetch_diag.get("kline_start", session_date),
        "kline_end": fetch_diag.get("kline_end", session_date),
        "connection_host": fetch_diag.get("connection_host", host),
        "connection_port": fetch_diag.get("connection_port", port),
        "raw_row_count": int(fetch_diag.get("raw_row_count") or len(raw_tuple)),
        "first_raw_time_key": fetch_diag.get("first_raw_time_key") or (raw_time_keys[0] if raw_time_keys else None),
        "last_raw_time_key": fetch_diag.get("last_raw_time_key") or (raw_time_keys[-1] if raw_time_keys else None),
        "vendor_ret": fetch_diag.get("vendor_ret"),
        "vendor_ret_msg": fetch_diag.get("vendor_ret_msg"),
    }

    canonical: list[dict[str, Any]] = []
    for row in raw_tuple:
        if not isinstance(row, Mapping):
            continue
        normalized = normalize_moomoo_kline_row(row, instrument_id=instrument_id, fetched_at_ns=fetched_at)
        if normalized is not None:
            canonical.append(normalized)
    visible = pit_visible_bars(canonical, observation_time_ns=observation_time_ns, instrument_id=instrument_id)
    if not visible:
        return BarLoadResult(
            source_id=SOURCE_MOOMOO_OPEND_KLINE_1M,
            instrument_id=instrument_id,
            bars=(),
            provenance={
                "host": host,
                "port": port,
                "evidence_class": "PROSPECTIVE_OPEND_KLINE",
                "fetched_at_ns": fetched_at,
                "observation_time_ns": observation_time_ns,
                **window_provenance,
            },
            reason_code="EXPERIMENT_CONTRACT_MISMATCH",
        )
    return BarLoadResult(
        source_id=SOURCE_MOOMOO_OPEND_KLINE_1M,
        instrument_id=instrument_id,
        bars=tuple(visible),
        provenance={
            "host": host,
            "port": port,
            "provider_id": "moomoo.opend",
            "evidence_class": "PROSPECTIVE_OPEND_KLINE",
            "fetched_at_ns": fetched_at,
            "observation_time_ns": observation_time_ns,
            "timing_basis": "available_time_at_bar_end",
            **window_provenance,
        },
    )


__all__ = [
    "BAR_CAPABILITY",
    "SOURCE_ADMITTED_EQUITY_INTRADAY",
    "SOURCE_MOOMOO_OPEND_KLINE_1M",
    "BarLoadResult",
    "first_admissible_post_signal_bar",
    "load_admitted_equity_intraday_bars",
    "load_moomoo_opend_kline_bars",
    "normalize_moomoo_kline_row",
    "pit_visible_bars",
    "simulator_bars",
]

"""Phase 3F Batch 05 external cohort — symbols, boundaries, and request specs.

Loaded from the captured Finviz export discovery artifact; not mixed with the
frozen IBKR Batch 01–04 cohort constants in ``cohort.py``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .cohort import HistoricalRequestSpec, _ib_end_datetime

REPO_ROOT = Path(__file__).resolve().parents[2]
DISCOVERY_ROWS_PATH = (
    REPO_ROOT
    / "intake"
    / "batches"
    / "phase-3f-cohort-expansion-05-external"
    / "normalized"
    / "batch3f05_external_discovery_rows.json"
)

DETECTION_CONTEXT = "DETECTION_CONTEXT_PRECEDING_24H"
FROZEN_FORWARD = "FROZEN_FORWARD_24H"


def _parse_observed_at(raw: str) -> datetime:
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC)


def load_discovery_document(path: Path | None = None) -> dict:
    target = path or DISCOVERY_ROWS_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def cohort_boundary(document: dict | None = None) -> datetime:
    doc = document or load_discovery_document()
    rows = doc.get("rows") or []
    if not rows:
        raw = doc.get("raw_source", {}).get("capture_timestamp")
        if not raw:
            raise ValueError("discovery document has no rows or capture_timestamp")
        return _parse_observed_at(str(raw))
    return _parse_observed_at(str(rows[0]["observed_at"]))


def forward_window_end(boundary: datetime) -> datetime:
    return boundary + timedelta(hours=24)


def symbols(document: dict | None = None) -> tuple[str, ...]:
    doc = document or load_discovery_document()
    rows = doc.get("rows") or []
    return tuple(str(row["ticker"]).strip().upper() for row in rows if row.get("ticker"))


def case_id(symbol: str, boundary: datetime) -> str:
    return f"BATCH3F05_{symbol}_{boundary.strftime('%Y%m%d')}"


def case_ids(document: dict | None = None) -> dict[str, str]:
    doc = document or load_discovery_document()
    boundary = cohort_boundary(doc)
    return {symbol: case_id(symbol, boundary) for symbol in symbols(doc)}


def request_specs(boundary: datetime | None = None) -> tuple[HistoricalRequestSpec, ...]:
    edge = boundary or cohort_boundary()
    forward_end = forward_window_end(edge)
    detection = HistoricalRequestSpec(
        request_name=DETECTION_CONTEXT,
        end_datetime=_ib_end_datetime(edge),
        duration_str="86400 S",
        bar_size_setting="1 min",
        what_to_show="TRADES",
        use_rth=0,
        format_date=2,
        keep_up_to_date=False,
        expected_window_start=edge - timedelta(hours=24),
        expected_window_end=edge,
    )
    forward = HistoricalRequestSpec(
        request_name=FROZEN_FORWARD,
        end_datetime=_ib_end_datetime(forward_end),
        duration_str="86400 S",
        bar_size_setting="1 min",
        what_to_show="TRADES",
        use_rth=0,
        format_date=2,
        keep_up_to_date=False,
        expected_window_start=edge,
        expected_window_end=forward_end,
    )
    return (detection, forward)


__all__ = [
    "DISCOVERY_ROWS_PATH",
    "DETECTION_CONTEXT",
    "FROZEN_FORWARD",
    "load_discovery_document",
    "cohort_boundary",
    "forward_window_end",
    "symbols",
    "case_id",
    "case_ids",
    "request_specs",
]

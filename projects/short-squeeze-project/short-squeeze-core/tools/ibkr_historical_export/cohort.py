"""Frozen cohort, boundary, and historical-request specifications.

Every value here is preregistered and must never be altered by returned data.
Returned bars are never used to select, exclude, reorder, or reinterpret a case.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# Frozen source order -- never reordered.
FROZEN_SYMBOLS: tuple[str, ...] = (
    "XNCR", "PESI", "SLS", "ZNTL", "GPRE", "SSPC", "LBGJ",
    "TRVI", "LMNX", "MGNX", "BHVN", "OBE", "AVTX",
    "KLRS", "SG",
    "CELZ", "GDC", "ADVB", "GOAI", "NXXT",
    "VMAR", "ATAI", "CADL", "CGEM", "IOVA",
    "PMAX", "STAK", "APVO",
    "BIYA",
)

# Case IDs are source organization only; no association is created from them.
CASE_IDS: dict[str, str] = {
    symbol: f"BATCH01_{symbol}_20260718"
    for symbol in FROZEN_SYMBOLS[:15]
} | {
    "CELZ": "BATCH3F01_CELZ_20260718",
    "GDC": "BATCH3F01_GDC_20260718",
    "ADVB": "BATCH3F01_ADVB_20260718",
    "GOAI": "BATCH3F01_GOAI_20260718",
    "NXXT": "BATCH3F01_NXXT_20260718",
    "VMAR": "BATCH3F02_VMAR_20260718",
    "ATAI": "BATCH3F02_ATAI_20260718",
    "CADL": "BATCH3F02_CADL_20260718",
    "CGEM": "BATCH3F02_CGEM_20260718",
    "IOVA": "BATCH3F02_IOVA_20260718",
    "PMAX": "BATCH3F03_PMAX_20260718",
    "STAK": "BATCH3F03_STAK_20260718",
    "APVO": "BATCH3F03_APVO_20260718",
    "BIYA": "BATCH3F04_BIYA_20260718",
}

# Frozen boundary (fractional seconds preserved) and the 24h forward window end.
FROZEN_BOUNDARY = datetime(2026, 7, 18, 13, 37, 55, 17661, tzinfo=UTC)
FROZEN_FORWARD_END = datetime(2026, 7, 19, 13, 37, 55, 17661, tzinfo=UTC)

# Contract-resolution request template (outcome-blind).
CONTRACT_SPEC = {
    "symbol": None,  # filled per symbol
    "secType": "STK",
    "exchange": "SMART",
    "currency": "USD",
}

# Request names.
DETECTION_CONTEXT = "DETECTION_CONTEXT_PRECEDING_24H"
FROZEN_FORWARD = "FROZEN_FORWARD_24H"


def _ib_end_datetime(moment: datetime) -> str:
    """Whole-second IBKR endDateTime string in UTC (fractional seconds truncated)."""
    whole = moment.replace(microsecond=0)
    return whole.strftime("%Y%m%d %H:%M:%S UTC")


@dataclass(frozen=True, slots=True)
class HistoricalRequestSpec:
    """Frozen parameters for one historical request."""

    request_name: str
    end_datetime: str
    duration_str: str
    bar_size_setting: str
    what_to_show: str
    use_rth: int
    format_date: int
    keep_up_to_date: bool
    # Whole windows carried for provenance; fractional-second originals preserved.
    expected_window_start: datetime
    expected_window_end: datetime

    @property
    def chart_options(self) -> list:
        return []


# Request A: the exact 24h preceding the frozen boundary (detection context source).
REQUEST_A = HistoricalRequestSpec(
    request_name=DETECTION_CONTEXT,
    end_datetime=_ib_end_datetime(FROZEN_BOUNDARY),
    duration_str="86400 S",
    bar_size_setting="1 min",
    what_to_show="TRADES",
    use_rth=0,
    format_date=2,
    keep_up_to_date=False,
    expected_window_start=FROZEN_BOUNDARY - timedelta(hours=24),
    expected_window_end=FROZEN_BOUNDARY,
)

# Request B: the exact preregistered 24h forward window ending at the frozen window end.
REQUEST_B = HistoricalRequestSpec(
    request_name=FROZEN_FORWARD,
    end_datetime=_ib_end_datetime(FROZEN_FORWARD_END),
    duration_str="86400 S",
    bar_size_setting="1 min",
    what_to_show="TRADES",
    use_rth=0,
    format_date=2,
    keep_up_to_date=False,
    expected_window_start=FROZEN_BOUNDARY,
    expected_window_end=FROZEN_FORWARD_END,
)

REQUEST_SPECS: tuple[HistoricalRequestSpec, ...] = (REQUEST_A, REQUEST_B)


__all__ = [
    "FROZEN_SYMBOLS",
    "CASE_IDS",
    "FROZEN_BOUNDARY",
    "FROZEN_FORWARD_END",
    "CONTRACT_SPEC",
    "DETECTION_CONTEXT",
    "FROZEN_FORWARD",
    "HistoricalRequestSpec",
    "REQUEST_A",
    "REQUEST_B",
    "REQUEST_SPECS",
]

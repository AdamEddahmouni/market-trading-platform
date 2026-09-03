"""Official SEC Fails-to-Deliver market-activity source. Balance, not flow."""

from .capture import build_archive_envelope
from .discovery import discover_archives, latest_discovered_period
from .health import SecFtdHealth, health_from_runtime
from .live import fetch_ftd_observations, live_enabled, transport_from_env
from .normalize import normalize_ftd_archive, normalize_ftd_row, parse_sec_price
from .parser import parse_archive_bytes, parse_text_rows
from .periods import FtdPeriod, parse_period_key
from .sync import FtdSync, FtdSyncCheckpoint, sync_ftd_from_env
from .transport import FtdArchiveCapture, FtdTransport

__all__ = [
    "FtdArchiveCapture",
    "FtdPeriod",
    "FtdSync",
    "FtdSyncCheckpoint",
    "FtdTransport",
    "SecFtdHealth",
    "build_archive_envelope",
    "discover_archives",
    "fetch_ftd_observations",
    "health_from_runtime",
    "latest_discovered_period",
    "live_enabled",
    "normalize_ftd_archive",
    "normalize_ftd_row",
    "parse_archive_bytes",
    "parse_period_key",
    "parse_sec_price",
    "parse_text_rows",
    "sync_ftd_from_env",
    "transport_from_env",
]

"""SEC FTD logical period keys and URL helpers. Modern half-month archives from July 2009."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

WWW_HOST = "https://www.sec.gov"
MODERN_COVERAGE_START = date(2009, 7, 1)
FULL_COVERAGE_START = date(2008, 9, 16)
HISTORICAL_MINIMUM_THRESHOLD = 10_000
PERIOD_KEY_RE = re.compile(r"^cnsfails(?P<year>\d{4})(?P<month>\d{2})(?P<half>[ab])$", re.I)


@dataclass(frozen=True, slots=True)
class FtdPeriod:
    period_key: str
    year: int
    month: int
    half: str
    source_period_start: str
    source_period_end: str
    archive_name: str
    url_path: str = ""

    @property
    def label(self) -> str:
        half_label = "first_half" if self.half == "a" else "second_half"
        return f"{self.year:04d}-{self.month:02d}_{half_label}"

    @property
    def download_url(self) -> str:
        path = self.url_path or f"/files/data/fails-deliver-data/{self.archive_name}.zip"
        return WWW_HOST + path


def parse_period_key(period_key: str, *, url_path: str = "") -> FtdPeriod:
    text = period_key.strip().lower()
    if text.endswith(".zip"):
        text = text[:-4]
    if not text.startswith("cnsfails"):
        if re.fullmatch(r"\d{6}[ab]", text):
            text = f"cnsfails{text}"
        else:
            raise ValueError(f"SEC_FTD_PERIOD_INVALID:{period_key}")
    match = PERIOD_KEY_RE.match(text)
    if not match:
        raise ValueError(f"SEC_FTD_PERIOD_INVALID:{period_key}")
    year = int(match.group("year"))
    month = int(match.group("month"))
    half = match.group("half").lower()
    if half not in {"a", "b"}:
        raise ValueError(f"SEC_FTD_HALF_INVALID:{period_key}")
    start_day = 1 if half == "a" else 16
    end_day = 15 if half == "a" else _last_day(year, month)
    return FtdPeriod(
        period_key=text,
        year=year,
        month=month,
        half=half,
        source_period_start=f"{year:04d}-{month:02d}-{start_day:02d}",
        source_period_end=f"{year:04d}-{month:02d}-{end_day:02d}",
        archive_name=text,
        url_path=url_path,
    )


def _last_day(year: int, month: int) -> int:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return (next_month - date.resolution).day


def settlement_in_period(settlement_date: str, period: FtdPeriod) -> bool:
    day = settlement_date[:10]
    return period.source_period_start <= day <= period.source_period_end


def historical_coverage_flags(settlement_date: str) -> tuple[str, ...]:
    flags: list[str] = []
    try:
        parsed = date.fromisoformat(settlement_date[:10])
    except ValueError:
        return ("MALFORMED_SETTLEMENT_DATE",)
    if parsed < FULL_COVERAGE_START:
        flags.append("HISTORICAL_COVERAGE_LIMITED")
        flags.append("PRE_2008_09_16_MINIMUM_10K_THRESHOLD")
    return tuple(flags)


__all__ = [
    "FULL_COVERAGE_START",
    "FtdPeriod",
    "HISTORICAL_MINIMUM_THRESHOLD",
    "MODERN_COVERAGE_START",
    "WWW_HOST",
    "historical_coverage_flags",
    "parse_period_key",
    "settlement_in_period",
]

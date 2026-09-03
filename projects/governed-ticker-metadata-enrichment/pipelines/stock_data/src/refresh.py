from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class FetchRange:
    start: date | None
    end: date
    full_history: bool


def plan_fetch_range(
    latest_stored: date | None,
    through: date,
    *,
    overlap_days: int = 7,
) -> FetchRange:
    if overlap_days < 0:
        raise ValueError("overlap_days must be non-negative")
    if latest_stored is not None and latest_stored > through:
        raise ValueError("latest_stored after through")
    exclusive_end = through + timedelta(days=1)
    if latest_stored is None:
        return FetchRange(None, exclusive_end, True)
    return FetchRange(
        latest_stored - timedelta(days=overlap_days),
        exclusive_end,
        False,
    )

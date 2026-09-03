"""Official FINRA short-interest publication calendar (versioned)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..short_intelligence.clocks import ny_wall_to_utc_iso

CALENDAR_2026 = Path(__file__).with_name("publication_calendar_2026.json")


@dataclass(frozen=True, slots=True)
class PublicationCycle:
    settlement_date: str
    due_date: str
    publication_date: str
    provider_available_time: str
    calendar_id: str
    evidence_class: str


@lru_cache(maxsize=4)
def load_calendar(path: Path | None = None) -> tuple[PublicationCycle, ...]:
    payload = json.loads((path or CALENDAR_2026).read_text(encoding="utf-8"))
    clock = payload.get("api_available_clock") or {}
    hour, minute = 16, 40
    local = str(clock.get("local_time") or "16:40")
    if ":" in local:
        hour_text, minute_text = local.split(":", 1)
        hour, minute = int(hour_text), int(minute_text)
    calendar_id = str(payload.get("calendar_id") or "")
    evidence_class = str(payload.get("evidence_class") or "DOCUMENTED")
    cycles: list[PublicationCycle] = []
    for row in payload.get("cycles") or []:
        publication = str(row["publication_date"])
        cycles.append(
            PublicationCycle(
                settlement_date=str(row["settlement_date"]),
                due_date=str(row["due_date"]),
                publication_date=publication,
                provider_available_time=ny_wall_to_utc_iso(publication, hour, minute),
                calendar_id=calendar_id,
                evidence_class=evidence_class,
            )
        )
    return tuple(cycles)


def cycle_for_settlement(settlement_date: str, path: Path | None = None) -> PublicationCycle | None:
    target = settlement_date[:10]
    for cycle in load_calendar(path):
        if cycle.settlement_date == target:
            return cycle
    return None


def latest_published_cycle(as_of: str, path: Path | None = None) -> PublicationCycle | None:
    visible = [cycle for cycle in load_calendar(path) if cycle.provider_available_time <= as_of]
    if not visible:
        return None
    return max(visible, key=lambda row: row.publication_date)

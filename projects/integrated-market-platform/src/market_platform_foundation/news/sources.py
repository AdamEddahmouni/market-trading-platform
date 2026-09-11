"""Canonical source-trust catalog for deterministic news filtering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import SourceAvailability


@dataclass(frozen=True, slots=True)
class SourceTrustEntry:
    source_id: str
    display_name: str
    aliases: tuple[str, ...] = ()
    asset_classes: tuple[str, ...] = ()
    tier: int = 3
    enabled: bool = True
    availability: SourceAvailability = SourceAvailability.KNOWN
    provider_id: str = ""
    notes: str = ""

    def matches_publisher(self, publisher: str) -> bool:
        needle = publisher.strip().lower()
        if not needle:
            return False
        if needle == self.display_name.lower():
            return True
        return any(needle == alias.lower() for alias in self.aliases)


DEFAULT_SOURCE_CATALOG: tuple[SourceTrustEntry, ...] = (
    SourceTrustEntry(
        source_id="pr_newswire",
        display_name="PR Newswire",
        aliases=("prnewswire", "pr newswire"),
        asset_classes=("EQUITY", "CORPORATE"),
        tier=1,
        enabled=True,
        availability=SourceAvailability.CONFIGURED,
        notes="Professor-named; fixture-only in this increment",
    ),
    SourceTrustEntry(
        source_id="globe_newswire",
        display_name="GlobeNewswire",
        aliases=("globe newswire", "global newswire"),
        asset_classes=("EQUITY", "CORPORATE"),
        tier=1,
        enabled=True,
        availability=SourceAvailability.CONFIGURED,
    ),
    SourceTrustEntry(
        source_id="accesswire",
        display_name="Accesswire",
        aliases=("access newswire", "accesswire"),
        asset_classes=("EQUITY", "CORPORATE"),
        tier=2,
        enabled=True,
        availability=SourceAvailability.CONFIGURED,
    ),
    SourceTrustEntry(
        source_id="reuters",
        display_name="Reuters",
        aliases=("reuters wire",),
        asset_classes=("EQUITY", "MACRO", "FX", "COMMODITY"),
        tier=1,
        enabled=True,
        availability=SourceAvailability.CONFIGURED,
    ),
    SourceTrustEntry(
        source_id="dow_jones",
        display_name="Dow Jones",
        aliases=("dow jones newswires", "dj newswires"),
        asset_classes=("EQUITY", "MACRO"),
        tier=1,
        enabled=True,
        availability=SourceAvailability.CONFIGURED,
    ),
    SourceTrustEntry(
        source_id="benzinga",
        display_name="Benzinga",
        asset_classes=("EQUITY",),
        tier=2,
        enabled=True,
        availability=SourceAvailability.CONFIGURED,
    ),
    SourceTrustEntry(
        source_id="sec_edgar",
        display_name="SEC EDGAR",
        aliases=("sec", "edgar"),
        asset_classes=("EQUITY", "REGULATORY"),
        tier=1,
        enabled=True,
        availability=SourceAvailability.OPERATIONAL,
        provider_id="sec.edgar",
    ),
    SourceTrustEntry(
        source_id="fda",
        display_name="FDA",
        asset_classes=("EQUITY", "REGULATORY"),
        tier=1,
        enabled=True,
        availability=SourceAvailability.CONFIGURED,
    ),
    SourceTrustEntry(
        source_id="finviz_elite",
        display_name="Finviz",
        aliases=("finviz elite", "finviz"),
        asset_classes=("EQUITY",),
        tier=3,
        enabled=True,
        availability=SourceAvailability.OPERATIONAL,
        provider_id="finviz",
    ),
    SourceTrustEntry(
        source_id="newsapi",
        display_name="NewsAPI",
        asset_classes=("EQUITY", "MACRO"),
        tier=3,
        enabled=True,
        availability=SourceAvailability.OPERATIONAL,
        provider_id="newsapi",
    ),
    SourceTrustEntry(
        source_id="finnhub",
        display_name="Finnhub",
        asset_classes=("EQUITY",),
        tier=3,
        enabled=True,
        availability=SourceAvailability.OPERATIONAL,
        provider_id="finnhub",
    ),
    SourceTrustEntry(
        source_id="fixture_wire",
        display_name="Fixture Wire",
        aliases=("fixture", "test wire"),
        asset_classes=("EQUITY", "FUTURES", "MACRO", "REGULATORY"),
        tier=1,
        enabled=True,
        availability=SourceAvailability.OPERATIONAL,
        provider_id="news.fixture",
    ),
    SourceTrustEntry(
        source_id="unsupported_blog",
        display_name="Unsupported Blog",
        tier=5,
        enabled=False,
        availability=SourceAvailability.KNOWN,
        notes="Seeded disabled example for policy tests",
    ),
)


class SourceTrustCatalog:
    """Policy-driven source catalog — trust is contextual, not universal."""

    VERSION = "news/sources/1.0.0"

    def __init__(self, entries: tuple[SourceTrustEntry, ...] | None = None) -> None:
        self._entries = entries or DEFAULT_SOURCE_CATALOG
        self._by_id = {entry.source_id: entry for entry in self._entries}

    def get(self, source_id: str) -> SourceTrustEntry | None:
        return self._by_id.get(source_id)

    def resolve_for_event(
        self,
        *,
        source_id: str,
        publisher_source: str,
    ) -> SourceTrustEntry | None:
        if source_id and source_id in self._by_id:
            return self._by_id[source_id]
        publisher = publisher_source.strip()
        if publisher:
            for entry in self._entries:
                if entry.matches_publisher(publisher):
                    return entry
        return None

    def is_trusted(
        self,
        entry: SourceTrustEntry | None,
        *,
        enabled_source_ids: frozenset[str],
    ) -> tuple[bool, str]:
        if entry is None:
            return False, "SOURCE_UNKNOWN"
        if not entry.enabled:
            return False, "SOURCE_DISABLED"
        if enabled_source_ids and entry.source_id not in enabled_source_ids:
            return False, "SOURCE_NOT_IN_POLICY"
        if entry.availability == SourceAvailability.KNOWN:
            return False, "SOURCE_NOT_CONFIGURED"
        return True, "SOURCE_TRUSTED"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "entries": [
                {
                    "source_id": entry.source_id,
                    "display_name": entry.display_name,
                    "tier": entry.tier,
                    "enabled": entry.enabled,
                    "availability": entry.availability.value,
                    "asset_classes": list(entry.asset_classes),
                }
                for entry in self._entries
            ],
        }


__all__ = [
    "DEFAULT_SOURCE_CATALOG",
    "SourceTrustCatalog",
    "SourceTrustEntry",
]

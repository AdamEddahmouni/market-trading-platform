"""Discover official SEC FTD archive periods from the public index page."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..sec_edgar.transport import SecTransport
from .periods import FtdPeriod, WWW_HOST, parse_period_key

INDEX_URL = f"{WWW_HOST}/data-research/sec-markets-data/fails-deliver-data"
ARCHIVE_RE = re.compile(
    r'href="(?P<path>/files/data/(?:fails-deliver-data|other/fails-deliver-data)/cnsfails(?P<key>\d{6}[ab])\.zip)"',
    re.I,
)


@dataclass(frozen=True, slots=True)
class DiscoveredArchive:
    period: FtdPeriod
    url: str
    label: str = ""


def discover_archives(transport: SecTransport) -> tuple[DiscoveredArchive, ...]:
    body = transport.get(INDEX_URL, immutable=False)
    html = body.decode("utf-8", errors="replace")
    seen: dict[str, DiscoveredArchive] = {}
    for match in ARCHIVE_RE.finditer(html):
        key = match.group("key").lower()
        path = match.group("path")
        period = parse_period_key(key, url_path=path)
        seen[key] = DiscoveredArchive(period=period, url=period.download_url)
    return tuple(sorted(seen.values(), key=lambda item: item.period.period_key, reverse=True))


def latest_discovered_period(transport: SecTransport) -> DiscoveredArchive | None:
    archives = discover_archives(transport)
    return archives[0] if archives else None


__all__ = ["DiscoveredArchive", "INDEX_URL", "discover_archives", "latest_discovered_period"]

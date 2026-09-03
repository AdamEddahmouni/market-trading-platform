"""FRED API V2 client — release-level bulk current histories."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .quality import FredQualityFlag
from .transport import FredHttpTransport, FredTransportError


@dataclass
class V2ReleasePage:
    observations: list[dict[str, Any]]
    has_more: bool
    next_cursor: str | None
    page_index: int
    raw: dict[str, Any]


@dataclass
class V2ReleaseSnapshot:
    release_id: int
    pages: list[V2ReleasePage] = field(default_factory=list)
    series_last_updated: dict[str, str] = field(default_factory=dict)
    consistency_result: str = "UNKNOWN"
    quality_flags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def observation_count(self) -> int:
        return sum(len(page.observations) for page in self.pages)

    @property
    def series_count(self) -> int:
        return len(self.series_last_updated)

    @property
    def complete(self) -> bool:
        if not self.pages:
            return False
        last = self.pages[-1]
        return not last.has_more and FredQualityFlag.PARTIAL_RELEASE_RETRIEVAL.value not in self.quality_flags


class FredV2Client:
    """FRED API v2 — /fred/v2/release/observations only."""

    MAX_LIMIT = 500_000

    def __init__(self, *, api_key: str, transport: FredHttpTransport | None = None) -> None:
        if not api_key:
            raise FredTransportError("AUTH_FAILED: missing api key")
        self.api_key = api_key
        self.transport = transport or FredHttpTransport()

    def release_observations_page(
        self,
        release_id: int,
        *,
        limit: int = MAX_LIMIT,
        cursor: str | None = None,
    ) -> V2ReleasePage:
        if limit < 1 or limit > self.MAX_LIMIT:
            raise ValueError(f"limit must be 1..{self.MAX_LIMIT}")
        params: dict[str, str] = {"release_id": str(release_id), "limit": str(limit)}
        if cursor:
            params["cursor"] = cursor
        payload = self.transport.request_json(
            path="/fred/v2/release/observations",
            params=params,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        observations = _flatten_v2_observations(payload)
        has_more = bool(payload.get("has_more"))
        next_cursor = payload.get("next_cursor")
        if has_more and not next_cursor:
            raise FredTransportError("CURSOR_MISSING: has_more without next_cursor")
        return V2ReleasePage(
            observations=[row for row in observations if isinstance(row, dict)],
            has_more=has_more,
            next_cursor=str(next_cursor) if next_cursor else None,
            page_index=0,
            raw=payload,
        )

    def fetch_release_observations(
        self,
        release_id: int,
        *,
        limit: int = MAX_LIMIT,
        max_pages: int = 100,
    ) -> V2ReleaseSnapshot:
        snapshot = V2ReleaseSnapshot(release_id=release_id)
        cursor: str | None = None
        seen_cursors: set[str] = set()
        page_index = 0
        flags: list[str] = []

        while page_index < max_pages:
            page = self.release_observations_page(release_id, limit=limit, cursor=cursor)
            page.page_index = page_index
            snapshot.pages.append(page)
            for row in page.observations:
                series_id = str(row.get("series_id", ""))
                last_updated = str(row.get("last_updated", ""))
                if series_id and last_updated:
                    snapshot.series_last_updated[series_id] = last_updated
            for block in page.raw.get("series", []):
                if isinstance(block, dict):
                    series_id = str(block.get("series_id", ""))
                    last_updated = str(block.get("last_updated", ""))
                    if series_id and last_updated:
                        snapshot.series_last_updated[series_id] = last_updated
            if page.has_more:
                if not page.next_cursor:
                    flags.append(FredQualityFlag.CURSOR_MISSING.value)
                    flags.append(FredQualityFlag.PARTIAL_RELEASE_RETRIEVAL.value)
                    break
                if page.next_cursor in seen_cursors:
                    flags.append(FredQualityFlag.CURSOR_LOOP.value)
                    flags.append(FredQualityFlag.PARTIAL_RELEASE_RETRIEVAL.value)
                    break
                seen_cursors.add(page.next_cursor)
                cursor = page.next_cursor
                page_index += 1
                continue
            break
        else:
            flags.append(FredQualityFlag.PARTIAL_RELEASE_RETRIEVAL.value)

        snapshot.quality_flags = tuple(dict.fromkeys(flags))
        snapshot.consistency_result = "COMPLETE" if snapshot.complete else "PARTIAL"
        return snapshot


def _flatten_v2_observations(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize V2 payload to flat observation rows.

    Production responses nest observations under ``series[]``; fixtures may use
    a legacy top-level ``observations`` list.
    """
    top_level = payload.get("observations", [])
    if isinstance(top_level, list) and top_level:
        return [row for row in top_level if isinstance(row, dict)]

    flattened: list[dict[str, Any]] = []
    series_blocks = payload.get("series", [])
    if not isinstance(series_blocks, list):
        return flattened
    for block in series_blocks:
        if not isinstance(block, dict):
            continue
        series_id = str(block.get("series_id", ""))
        last_updated = str(block.get("last_updated", ""))
        copyright_id = str(block.get("copyright_id", ""))
        for row in block.get("observations", []):
            if not isinstance(row, dict):
                continue
            flattened.append(
                {
                    "series_id": series_id,
                    "last_updated": last_updated,
                    "copyright_id": copyright_id,
                    "date": row.get("date", ""),
                    "value": row.get("value", ""),
                }
            )
    return flattened


__all__ = ["FredV2Client", "V2ReleasePage", "V2ReleaseSnapshot", "_flatten_v2_observations"]

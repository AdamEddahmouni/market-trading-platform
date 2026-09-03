"""FRED API V1 client — granular ALFRED/PIT operations."""

from __future__ import annotations

from typing import Any

from .redaction import sanitize_v1_request_semantics
from .transport import FredHttpTransport, FredTransportError


class FredV1Client:
    """FRED API v1 — series, releases, vintages, realtime periods."""

    def __init__(self, *, api_key: str, transport: FredHttpTransport | None = None) -> None:
        if not api_key:
            raise FredTransportError("AUTH_FAILED: missing api key")
        self.api_key = api_key
        self.transport = transport or FredHttpTransport()

    def _params(self, **kwargs: str | int) -> dict[str, str]:
        params = {"api_key": self.api_key, "file_type": "json"}
        for key, value in kwargs.items():
            if value is not None and value != "":
                params[key] = str(value)
        return params

    def _get(self, endpoint: str, **kwargs: str | int) -> dict[str, Any]:
        params = self._params(**kwargs)
        payload = self.transport.request_json(path=f"/fred/{endpoint}", params=params)
        payload["_request_semantics"] = sanitize_v1_request_semantics(
            endpoint=f"/fred/{endpoint}",
            params=params,
        )
        return payload

    def series(self, series_id: str) -> dict[str, Any]:
        return self._get("series", series_id=series_id)

    def series_observations(
        self,
        series_id: str,
        *,
        observation_start: str = "",
        observation_end: str = "",
        realtime_start: str = "",
        realtime_end: str = "",
        vintage_dates: str = "",
        output_type: int = 1,
        sort_order: str = "asc",
        limit: int = 100000,
    ) -> dict[str, Any]:
        return self._get(
            "series/observations",
            series_id=series_id,
            observation_start=observation_start,
            observation_end=observation_end,
            realtime_start=realtime_start,
            realtime_end=realtime_end,
            vintage_dates=vintage_dates,
            output_type=output_type,
            sort_order=sort_order,
            limit=limit,
        )

    def series_vintage_dates(self, series_id: str) -> dict[str, Any]:
        return self._get("series/vintagedates", series_id=series_id)

    def series_release(self, series_id: str) -> dict[str, Any]:
        return self._get("series/release", series_id=series_id)

    def series_updates(
        self,
        *,
        start_time: str = "",
        limit: int = 1000,
        offset: int = 0,
    ) -> dict[str, Any]:
        return self._get(
            "series/updates",
            start_time=start_time,
            limit=limit,
            offset=offset,
        )

    def releases(self, *, limit: int = 1000, offset: int = 0) -> dict[str, Any]:
        return self._get("releases", limit=limit, offset=offset)

    def release(self, release_id: int) -> dict[str, Any]:
        return self._get("release", release_id=release_id)

    def release_dates(
        self,
        release_id: int,
        *,
        include_release_dates_with_no_data: str = "false",
    ) -> dict[str, Any]:
        return self._get(
            "release/dates",
            release_id=release_id,
            include_release_dates_with_no_data=include_release_dates_with_no_data,
        )

    def release_series(
        self,
        release_id: int,
        *,
        limit: int = 1000,
        offset: int = 0,
    ) -> dict[str, Any]:
        return self._get(
            "release/series",
            release_id=release_id,
            limit=limit,
            offset=offset,
        )

    def release_sources(self, release_id: int) -> dict[str, Any]:
        return self._get("release/sources", release_id=release_id)


__all__ = ["FredV1Client"]

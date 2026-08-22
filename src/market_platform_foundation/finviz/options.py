"""Finviz options export characterization."""

from __future__ import annotations

import csv
import io
import time
from typing import Any

from .config import FINVIZ_OPTIONS_URL, OPTIONS_CACHE_TTL_S, finviz_api_key
from .request_manager import FinvizRequestManager, RequestPriority, get_finviz_request_manager, redact_text


def parse_options_csv(text: str) -> tuple[list[dict[str, Any]], tuple[str, ...], str | None]:
    lowered = text[:10_000].lower()
    if "<html" in lowered:
        return [], (), "FINVIZ_OPTIONS_LOGIN_PAGE"
    reader = csv.DictReader(io.StringIO(text))
    columns = tuple(reader.fieldnames or ())
    if not columns:
        return [], columns, "FINVIZ_OPTIONS_NOT_CSV"
    rows: list[dict[str, Any]] = []
    for raw in reader:
        row = {str(k): str(v) if v is not None else "" for k, v in dict(raw).items()}
        rows.append(row)
    return rows, columns, None


class FinvizOptionsClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        request_manager: FinvizRequestManager | None = None,
    ) -> None:
        self._api_key = api_key or finviz_api_key()
        self._manager = request_manager or get_finviz_request_manager()

    def fetch_chain(self, symbol: str, *, force: bool = False) -> dict[str, Any]:
        if not self._api_key:
            return {"success": False, "error": "NOT_CONFIGURED", "contracts": [], "columns": []}
        needle = symbol.strip().upper()
        if force:
            self._manager.clear_cache()
        params = {"t": needle, "auth": self._api_key}
        status, body, meta = self._manager.get(
            FINVIZ_OPTIONS_URL,
            params=params,
            priority=RequestPriority.OPTIONS_CONTEXT,
            cache_ttl_s=None if force else OPTIONS_CACHE_TTL_S,
            api_key=self._api_key,
        )
        available_ns = time.time_ns()
        if status != 200:
            return {
                "success": False,
                "error": redact_text(f"HTTP_{status}", self._api_key),
                "contracts": [],
                "columns": [],
                "available_time_ns": available_ns,
            }
        contracts, columns, err = parse_options_csv(body)
        if err:
            return {
                "success": False,
                "error": err,
                "contracts": [],
                "columns": list(columns),
                "available_time_ns": available_ns,
            }
        return {
            "success": True,
            "error": None,
            "contracts": contracts,
            "columns": list(columns),
            "contract_count": len(contracts),
            "available_time_ns": available_ns,
            "meta": meta,
            "capability": {
                "OPTIONS_DISCOVERY": "AVAILABLE" if contracts else "UNAVAILABLE",
                "OPTIONS_CHAIN_CONTEXT": "AVAILABLE" if contracts else "UNAVAILABLE",
                "OPTIONS_ANALYTICS": "PARTIAL",
                "OPTIONS_EXECUTION_DATA": "NOT_AUTHORIZED",
            },
        }

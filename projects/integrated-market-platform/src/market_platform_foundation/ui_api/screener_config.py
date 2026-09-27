"""Versioned personal Screener configurations on the existing local SQLite store."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from .screener_filters import builtin_presets, validate_filters
from .screener_projections import FIELD_NAMES

PREF_KEY = "screener.s2.screens"
LAST_KEY = "screener.s2.last"
SCHEMA_VERSION = 1
VIEWS = ("Overview", "Performance", "Technical", "Volume", "Short", "Fundamentals", "Custom")
COLUMNS = frozenset((*FIELD_NAMES, "symbol", "company", "sector", "industry", "country",
                     "earnings_date", "recommendation", "bid", "ask", "spread_pct"))
SORTS = frozenset((*FIELD_NAMES, "symbol", "company"))


def validate_screen(raw: Any, *, identity: str | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("INVALID_SCREEN")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        raise ValueError("INVALID_SCREEN_NAME")
    if raw.get("universe") != "US_EQUITIES":
        raise ValueError("INVALID_SCREEN_UNIVERSE")
    if raw.get("view") not in VIEWS:
        raise ValueError("INVALID_SCREEN_VIEW")
    sort = raw.get("sort")
    if not isinstance(sort, dict) or sort.get("field") not in SORTS or not isinstance(sort.get("descending"), bool):
        raise ValueError("INVALID_SCREEN_SORT")
    columns = raw.get("columns")
    if not isinstance(columns, dict):
        raise ValueError("INVALID_SCREEN_COLUMNS")
    visible, order, widths, pinned = (columns.get(key) for key in ("visible", "order", "widths", "pinned"))
    if not isinstance(visible, list) or not visible or not isinstance(order, list) or not isinstance(pinned, list) or not isinstance(widths, dict):
        raise ValueError("INVALID_SCREEN_COLUMNS")
    if any(not isinstance(value, str) or value not in COLUMNS for value in visible + order + pinned):
        raise ValueError("INVALID_SCREEN_COLUMN")
    if len(set(visible)) != len(visible) or len(set(order)) != len(order) or len(set(pinned)) != len(pinned):
        raise ValueError("DUPLICATE_SCREEN_COLUMN")
    if not set(visible) <= set(order) or not set(pinned) <= set(visible):
        raise ValueError("INVALID_SCREEN_COLUMN_STATE")
    if any(key not in COLUMNS or isinstance(value, bool) or not isinstance(value, (int, float)) or not 50 <= value <= 600 for key, value in widths.items()):
        raise ValueError("INVALID_SCREEN_COLUMN_WIDTH")
    screen_id = identity or raw.get("id") or f"user-{uuid4().hex}"
    if not isinstance(screen_id, str) or len(screen_id) > 80 or not screen_id.startswith("user-"):
        raise ValueError("INVALID_SCREEN_ID")
    version = raw.get("version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise ValueError("UNSUPPORTED_SCREEN_VERSION")
    return {"id": screen_id, "version": version, "name": name.strip(), "universe": "US_EQUITIES",
            "filters": validate_filters(raw.get("filters")), "view": raw["view"],
            "sort": {"field": sort["field"], "descending": sort["descending"]},
            "columns": {"visible": list(visible), "order": list(order), "widths": dict(widths), "pinned": list(pinned)}}


class ScreenerConfigRepository:
    def __init__(self, store: Any):
        self._store = store

    def list_saved(self) -> list[dict[str, Any]]:
        envelope = self._store.get_preferences().get(PREF_KEY)
        if not isinstance(envelope, dict) or envelope.get("version") != SCHEMA_VERSION or not isinstance(envelope.get("screens"), list):
            return []
        screens = []
        for raw in envelope["screens"]:
            try:
                screens.append(validate_screen(raw, identity=raw.get("id") if isinstance(raw, dict) else None))
            except ValueError:
                continue
        return deepcopy(screens)

    def get(self, screen_id: str) -> dict[str, Any] | None:
        return next((screen for screen in self.list_saved() if screen["id"] == screen_id), None)

    def get_last(self) -> dict[str, Any] | None:
        raw = self._store.get_preferences().get(LAST_KEY)
        try:
            return validate_screen(raw, identity="user-last")
        except ValueError:
            return None

    def save_last(self, raw: Any) -> dict[str, Any]:
        screen = validate_screen(raw, identity="user-last")
        self._store.set_preference(LAST_KEY, screen)
        return screen

    def save(self, raw: Any) -> dict[str, Any]:
        screen = validate_screen(raw)
        screens = self.list_saved()
        existing = next((index for index, item in enumerate(screens) if item["id"] == screen["id"]), None)
        if existing is None:
            if isinstance(raw, dict) and raw.get("id") is not None:
                raise ValueError("SCREEN_NOT_FOUND")
            screens.append(screen)
        else:
            screens[existing] = screen
        self._store.set_preference(PREF_KEY, {"version": SCHEMA_VERSION, "screens": screens})
        return deepcopy(screen)

    def delete(self, screen_id: str) -> bool:
        if screen_id in {preset["id"] for preset in builtin_presets()}:
            raise ValueError("BUILTIN_SCREEN_IMMUTABLE")
        screens = self.list_saved()
        remaining = [screen for screen in screens if screen["id"] != screen_id]
        if len(remaining) == len(screens):
            return False
        self._store.set_preference(PREF_KEY, {"version": SCHEMA_VERSION, "screens": remaining})
        return True


def read_config() -> dict[str, Any]:
    from ..local_state.startup import open_local_state
    from .screener_filters import filter_catalog

    store = open_local_state()
    return {"schema_version": SCHEMA_VERSION, "catalog": filter_catalog(),
            "presets": builtin_presets(), "saved": ScreenerConfigRepository(store).list_saved() if store else [],
            "last": ScreenerConfigRepository(store).get_last() if store else None,
            "persistence_available": store is not None}


def write_config(body: dict[str, Any]) -> dict[str, Any]:
    from ..local_state.startup import open_local_state

    store = open_local_state()
    if store is None:
        raise ValueError("LOCAL_STATE_DISABLED")
    repository = ScreenerConfigRepository(store)
    action = body.get("action")
    if action == "save":
        result = repository.save(body.get("screen"))
    elif action == "delete":
        screen_id = body.get("id")
        if not isinstance(screen_id, str):
            raise ValueError("INVALID_SCREEN_ID")
        result = repository.delete(screen_id)
    elif action == "last":
        result = repository.save_last(body.get("screen"))
    else:
        raise ValueError("INVALID_SCREEN_ACTION")
    return {"result": result, "saved": repository.list_saved()}

"""Versioned personal Screener configurations on the existing local SQLite store."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any
from uuid import uuid4

from .screener_filters import builtin_presets, validate_filters
from .screener_projections import FIELD_NAMES
from .screener_universes import US_EQUITIES, canonical_view, universe_payload, universe_spec

PREF_KEY = "screener.s2.screens"
LAST_KEY = "screener.s2.last"
PREVIEW_KEY = "screener.s3.preview"
PREVIEW_WIDTH = (320, 720)
DEFAULT_PREVIEW = {"version": 1, "open": True, "width": 400}
PANEL_KEY = "screener.s4.panels"
PANEL_IDS = ("order_flow", "cvd", "level2", "charts", "futures", "options", "short_squeeze", "rates_curve", "news",
             "institutional", "congress_gov", "setup")
PANEL_LAYOUT_VERSION = 1
DOCK_HEIGHT = (140, 1200)
DEFAULT_PANEL_LAYOUT = {"version": PANEL_LAYOUT_VERSION, "open_panels": [], "active_panel": None,
                        "dock_height": 300, "dockview_layout": None}
MAX_DOCKVIEW_LAYOUT_BYTES = 32_768
SCHEMA_VERSION = 2
VIEWS = ("Overview", "Performance", "Technical", "Volume", "Short Squeeze", "Fundamentals", "Custom")
COLUMNS = frozenset((*FIELD_NAMES, "symbol", "company", "sector", "industry", "country",
                     "earnings_date", "recommendation", "bid", "ask", "spread_pct"))
SORTS = frozenset((*FIELD_NAMES, "symbol", "company"))


def validate_screen(raw: Any, *, identity: str | None = None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("INVALID_SCREEN")
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        raise ValueError("INVALID_SCREEN_NAME")
    universe = raw.get("universe", US_EQUITIES)
    spec = universe_spec(universe)
    # A screen saved before S8 with the "Short" view opens as "Short Squeeze".
    view = canonical_view(universe, raw.get("view"))
    if view not in spec.views:
        raise ValueError("INVALID_SCREEN_VIEW")
    sort = raw.get("sort")
    if not isinstance(sort, dict) or sort.get("field") not in (SORTS if universe == US_EQUITIES else spec.columns) or not isinstance(sort.get("descending"), bool):
        raise ValueError("INVALID_SCREEN_SORT")
    columns = raw.get("columns")
    if not isinstance(columns, dict):
        raise ValueError("INVALID_SCREEN_COLUMNS")
    visible, order, widths, pinned = (columns.get(key) for key in ("visible", "order", "widths", "pinned"))
    if not isinstance(visible, list) or not visible or not isinstance(order, list) or not isinstance(pinned, list) or not isinstance(widths, dict):
        raise ValueError("INVALID_SCREEN_COLUMNS")
    allowed = COLUMNS if universe == US_EQUITIES else spec.columns
    if any(not isinstance(value, str) or value not in allowed for value in visible + order + pinned):
        raise ValueError("INVALID_SCREEN_COLUMN")
    if len(set(visible)) != len(visible) or len(set(order)) != len(order) or len(set(pinned)) != len(pinned):
        raise ValueError("DUPLICATE_SCREEN_COLUMN")
    if not set(visible) <= set(order) or not set(pinned) <= set(visible):
        raise ValueError("INVALID_SCREEN_COLUMN_STATE")
    if any(key not in allowed or isinstance(value, bool) or not isinstance(value, (int, float)) or not 50 <= value <= 600 for key, value in widths.items()):
        raise ValueError("INVALID_SCREEN_COLUMN_WIDTH")
    screen_id = identity or raw.get("id") or f"user-{uuid4().hex}"
    if not isinstance(screen_id, str) or len(screen_id) > 80 or not screen_id.startswith("user-"):
        raise ValueError("INVALID_SCREEN_ID")
    version = raw.get("version", SCHEMA_VERSION)
    if version not in (1, SCHEMA_VERSION) or (version == 1 and universe != US_EQUITIES):
        raise ValueError("UNSUPPORTED_SCREEN_VERSION")
    return {"id": screen_id, "version": SCHEMA_VERSION, "name": name.strip(), "universe": universe,
            "filters": validate_filters(raw.get("filters"), universe=universe), "view": view,
            "sort": {"field": sort["field"], "descending": sort["descending"]},
            "columns": {"visible": list(visible), "order": list(order), "widths": dict(widths), "pinned": list(pinned)}}


def validate_preview_layout(raw: Any) -> dict[str, Any]:
    """Quick Preview pane layout only; saved-screen definitions are not touched."""

    if not isinstance(raw, dict) or raw.get("version", 1) != 1:
        raise ValueError("INVALID_PREVIEW_LAYOUT")
    is_open, width = raw.get("open"), raw.get("width")
    if not isinstance(is_open, bool) or isinstance(width, bool) or not isinstance(width, int):
        raise ValueError("INVALID_PREVIEW_LAYOUT")
    if not PREVIEW_WIDTH[0] <= width <= PREVIEW_WIDTH[1]:
        raise ValueError("INVALID_PREVIEW_WIDTH")
    return {"version": 1, "open": is_open, "width": width}


def _layout_views(node: Any) -> list[str]:
    """Every panel id referenced by a Dockview grid node."""

    views: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "views":
                if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                    raise ValueError("INVALID_DOCK_LAYOUT")
                views.extend(value)
            else:
                views.extend(_layout_views(value))
    elif isinstance(node, list):
        for item in node:
            views.extend(_layout_views(item))
    return views


def validate_panel_layout(raw: Any) -> dict[str, Any]:
    """Specialist dock presentation only: panel ids, arrangement, and sizes.

    Market observations never enter the layout. Dockview panel entries may hold
    only scalar presentation fields; ``params`` (where panel data could hide)
    is rejected, and every grid view must name an open specialist panel.
    """

    if not isinstance(raw, dict) or raw.get("version") != PANEL_LAYOUT_VERSION:
        raise ValueError("INVALID_PANEL_LAYOUT")
    open_panels, active, height, layout = (raw.get(key) for key in ("open_panels", "active_panel", "dock_height", "dockview_layout"))
    if not isinstance(open_panels, list) or len(set(open_panels)) != len(open_panels) or             any(panel not in PANEL_IDS for panel in open_panels):
        raise ValueError("INVALID_PANEL_IDS")
    if active is not None and active not in open_panels:
        raise ValueError("INVALID_ACTIVE_PANEL")
    if isinstance(height, bool) or not isinstance(height, int) or not DOCK_HEIGHT[0] <= height <= DOCK_HEIGHT[1]:
        raise ValueError("INVALID_DOCK_HEIGHT")
    if layout is not None:
        if not isinstance(layout, dict) or not isinstance(layout.get("grid"), dict) or not isinstance(layout.get("panels"), dict):
            raise ValueError("INVALID_DOCK_LAYOUT")
        if len(json.dumps(layout, separators=(",", ":"))) > MAX_DOCKVIEW_LAYOUT_BYTES:
            raise ValueError("DOCK_LAYOUT_TOO_LARGE")
        panels = layout["panels"]
        if set(panels) != set(open_panels):
            raise ValueError("DOCK_LAYOUT_PANEL_MISMATCH")
        for panel_id, entry in panels.items():
            if not isinstance(entry, dict) or "params" in entry or entry.get("id") != panel_id or                     entry.get("contentComponent") != panel_id or                     any(not isinstance(value, (str, int, float, bool, type(None))) for value in entry.values()):
                raise ValueError("INVALID_DOCK_PANEL")
        if not set(_layout_views(layout["grid"])) <= set(open_panels):
            raise ValueError("DOCK_LAYOUT_PANEL_MISMATCH")
        if not open_panels:
            layout = None
    return {"version": PANEL_LAYOUT_VERSION, "open_panels": list(open_panels), "active_panel": active,
            "dock_height": height, "dockview_layout": deepcopy(layout)}


class ScreenerConfigRepository:
    def __init__(self, store: Any):
        self._store = store

    def list_saved(self) -> list[dict[str, Any]]:
        envelope = self._store.get_preferences().get(PREF_KEY)
        if not isinstance(envelope, dict) or envelope.get("version") not in (1, SCHEMA_VERSION) or not isinstance(envelope.get("screens"), list):
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

    def get_preview_layout(self) -> dict[str, Any]:
        try:
            return validate_preview_layout(self._store.get_preferences().get(PREVIEW_KEY))
        except ValueError:
            return dict(DEFAULT_PREVIEW)

    def save_preview_layout(self, raw: Any) -> dict[str, Any]:
        layout = validate_preview_layout(raw)
        self._store.set_preference(PREVIEW_KEY, layout)
        return layout

    def get_panel_layout(self) -> dict[str, Any]:
        """Stored dock layout, or the default when missing, corrupt, or another version."""

        try:
            return validate_panel_layout(self._store.get_preferences().get(PANEL_KEY))
        except ValueError:
            return deepcopy(DEFAULT_PANEL_LAYOUT)

    def save_panel_layout(self, raw: Any) -> dict[str, Any]:
        layout = validate_panel_layout(raw)
        self._store.set_preference(PANEL_KEY, layout)
        return layout

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
    from .screener_query import DEFAULT_PAGE_LIMIT, MAX_PAGE_LIMIT, field_capabilities

    store = open_local_state()
    # Field capabilities come from the server so the UI never invents sort/filter support.
    universes = [{**spec, "fields": field_capabilities(str(spec["id"]))} for spec in universe_payload()]
    return {"schema_version": SCHEMA_VERSION, "catalog": filter_catalog(None), "universes": universes,
            "query": {"default_limit": DEFAULT_PAGE_LIMIT, "max_limit": MAX_PAGE_LIMIT},
            "presets": builtin_presets(), "saved": ScreenerConfigRepository(store).list_saved() if store else [],
            "last": ScreenerConfigRepository(store).get_last() if store else None,
            "preview_layout": ScreenerConfigRepository(store).get_preview_layout() if store else dict(DEFAULT_PREVIEW),
            "panel_layout": ScreenerConfigRepository(store).get_panel_layout() if store else deepcopy(DEFAULT_PANEL_LAYOUT),
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
    elif action == "preview_layout":
        result = repository.save_preview_layout(body.get("layout"))
    elif action == "panel_layout":
        result = repository.save_panel_layout(body.get("layout"))
    else:
        raise ValueError("INVALID_SCREEN_ACTION")
    return {"result": result, "saved": repository.list_saved()}

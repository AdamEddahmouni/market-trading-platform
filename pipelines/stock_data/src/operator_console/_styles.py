"""Shared styles and singletons for the `src.operator_console` package.

Centralizes the `rich.console.Console` instance and the color palette
used across `dashboard`, `timing`, `filter`, `export`, and the legacy
`__init__.py` UI.

Keeping this in a tiny module avoids circular imports between the
package submodules, since `__init__.py` re-exports from each sibling.
"""

from __future__ import annotations

from rich.console import Console

# Single shared `Console` instance — every UI module renders to this.
console = Console()


# Status colors used by the dashboard, summary, and export views.
COLOR_PENDING = "dim"
COLOR_RUNNING = "bold yellow"
COLOR_COMPLETE = "bold green"
COLOR_ERROR = "bold red"

# Color for numeric emphasis in tables.
COLOR_RECORD = "cyan"
COLOR_ETA = "yellow"

# Branding palette (matches the panels in __init__.py).
COLOR_BRAND_PRIMARY = "cyan"
COLOR_BRAND_SECONDARY = "yellow"

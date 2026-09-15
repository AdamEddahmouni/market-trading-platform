"""PineTS license boundary metadata and research-bridge entrypoints (no subprocess in foundation)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

PINETS_NPM_PACKAGE = "pinets"
PINETS_NPM_LICENSE = "AGPL-3.0-only"
PINETS_REPOSITORY = "https://github.com/LuxAlgo/PineTS"

_IMP_ROOT = Path(__file__).resolve().parents[4]


def pinets_license_audit() -> dict[str, str]:
    return {
        "npm_package": PINETS_NPM_PACKAGE,
        "npm_license": PINETS_NPM_LICENSE,
        "repository": PINETS_REPOSITORY,
        "imp_production_graph": "EXCLUDED",
        "ui_package_json": "NO_PINETS_DEPENDENCY",
        "vela_chart_lab": "NO_PINETS",
        "integration_mode": "OPTIONAL_ISOLATED_NODE_BRIDGE",
    }


def _ensure_tools_import_path() -> None:
    root = str(_IMP_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def probe_pinets_engine() -> dict[str, Any]:
    _ensure_tools_import_path()
    from tools.research.pinets_engine_probe import (  # noqa: PLC0415
        probe_pinets_engine as _probe_pinets_engine,
    )

    return _probe_pinets_engine()


def run_pinets_fixture_via_bridge(
    *,
    script_id: str,
    pine_source: str,
    bars: list[Mapping[str, Any]],
    parameters: Mapping[str, Any],
) -> dict[str, Any]:
    _ensure_tools_import_path()
    from tools.research.pinets_engine_probe import (  # noqa: PLC0415
        run_pinets_fixture_via_bridge as _run_pinets_fixture_via_bridge,
    )

    return _run_pinets_fixture_via_bridge(
        script_id=script_id,
        pine_source=pine_source,
        bars=bars,
        parameters=parameters,
    )


__all__ = [
    "PINETS_NPM_LICENSE",
    "PINETS_NPM_PACKAGE",
    "PINETS_REPOSITORY",
    "pinets_license_audit",
    "probe_pinets_engine",
    "run_pinets_fixture_via_bridge",
]

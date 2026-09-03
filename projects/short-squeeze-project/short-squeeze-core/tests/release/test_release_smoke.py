from __future__ import annotations

import json
from pathlib import Path

from apps.research_screener.api_contract import API_VERSION, SCHEMA_VERSION
from apps.research_screener.config import resolve_application_config
from apps.research_screener.frozen_demo import load_frozen_demo

ROOT = Path(__file__).resolve().parents[2]


def test_frozen_demo_is_provider_independent_and_exact() -> None:
    config = resolve_application_config(
        cli={"SQUEEZE_APP_MODE": "FROZEN_DEMO"},
        environ={},
    )
    demo = load_frozen_demo()

    assert config.private_file_loaded is False
    assert demo["totals"] == {"PASS": 97, "FAIL": 20, "UNKNOWN": 208}
    assert len(demo["rows"]) == 13


def test_stable_api_and_openapi_versions_match() -> None:
    openapi = json.loads((ROOT / "docs/openapi.json").read_text(encoding="utf-8"))

    assert API_VERSION == "1.0.0"
    assert SCHEMA_VERSION == "batch14.integration.v1"
    assert openapi["info"]["version"] == API_VERSION
    assert (
        openapi["components"]["schemas"]["Envelope"]["properties"]["schema_version"][
            "const"
        ]
        == SCHEMA_VERSION
    )


def test_release_contains_no_private_runtime_file() -> None:
    if (ROOT / "RELEASE_MANIFEST.json").is_file():
        assert not (ROOT / ".private").exists()
        assert not (ROOT / ".env").exists()
        assert not (ROOT / ".git").exists()
    else:
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".private/" in gitignore
        assert "dist/" in gitignore

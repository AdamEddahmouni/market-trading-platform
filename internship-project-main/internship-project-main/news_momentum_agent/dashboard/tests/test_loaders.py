"""Smoke tests for dashboard JSON loaders (no Streamlit server required)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# Ensure project root on path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.data import paths as P
from dashboard.data.loaders import (
    _envelope,
    horizon_explainer,
    load_json,
    load_items_file,
    path_label,
)


def test_load_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    env = load_json(missing, {"items": []})
    assert env["ok"] is False
    assert env["exists"] is False
    assert "missing" in (env.get("error") or "")


def test_load_malformed_json(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    env = load_json(bad, {})
    assert env["ok"] is False
    assert "malformed" in (env.get("error") or "").lower() or env["error"]


def test_load_watchlist_shape() -> None:
    if not P.WATCHLIST_PATH.exists():
        pytest.skip("no watchlist.json")
    env = load_items_file(P.WATCHLIST_PATH)
    assert "items" in env
    assert isinstance(env["items"], list)


def test_path_label() -> None:
    assert path_label("news") == "A"
    assert path_label("news_catalyst") == "A.2"
    assert path_label("expiry") == "B"


def test_horizon_explainer_range() -> None:
    settings = {
        "trading": {
            "options_expiry_horizon": "range",
            "options_dte_range": [0, 30],
        }
    }
    h = horizon_explainer(settings)
    assert h["mode"] == "range"
    assert "0" in h["detail"] and "30" in h["detail"]
    assert "no deadline flatten" in h["detail"]


def test_eod_summary_if_present() -> None:
    path = P.latest_eod_summary_path()
    if path is None:
        pytest.skip("no eod summaries")
    env = load_json(path, {})
    assert env["ok"] is True
    data = env["data"]
    assert isinstance(data, dict)
    assert "headline" in data or "opens" in data


def test_envelope_age() -> None:
    env = _envelope(P.SETTINGS_PATH, {"updated_at": "2020-01-01T00:00:00+00:00"}, ok=True, updated_at="2020-01-01T00:00:00+00:00")
    assert env["age_sec"] is not None
    assert env["age_sec"] > 0

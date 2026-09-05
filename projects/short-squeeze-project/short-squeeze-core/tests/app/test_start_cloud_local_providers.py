"""Tests for start_cloud local provider preload."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from start_cloud import _build_cli_args, _preload_local_providers


def test_build_cli_args_recognizes_load_local_providers_flag():
    remaining, load_local = _build_cli_args(["--load-local-providers", "--port", "8788"])
    assert load_local is True
    assert "--port" in remaining
    assert "8788" in remaining


def test_build_cli_args_env_toggle():
    os.environ["SQUEEZE_CLOUD_LOAD_LOCAL_PROVIDERS"] = "true"
    try:
        _, load_local = _build_cli_args([])
        assert load_local is True
    finally:
        os.environ.pop("SQUEEZE_CLOUD_LOAD_LOCAL_PROVIDERS", None)


def test_preload_local_providers_sets_enable_flags(tmp_path: Path, monkeypatch):
    private = tmp_path / "providers.env"
    private.write_text(
        "FINVIZ_API_KEY=test_key\nNEWSAPI_KEY=test_key\nFINNHUB_KEY=test_key\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "start_cloud.default_private_path",
        lambda: private,
    )
    for key in list(os.environ):
        if key.startswith(("FINVIZ_", "NEWSAPI_", "FINNHUB_", "SEC_")):
            monkeypatch.delenv(key, raising=False)
    path = _preload_local_providers()
    assert path == private
    assert os.environ.get("FINVIZ_ENABLED") == "true"
    assert os.environ.get("NEWSAPI_ENABLED") == "true"
    assert os.environ.get("FINNHUB_ENABLED") == "true"
    assert os.environ.get("SEC_ENABLED") == "true"

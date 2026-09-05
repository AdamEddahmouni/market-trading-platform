"""Tests for unattended Finviz token recovery."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.research_screener.finviz_auto_refresh import (
    AutoRefreshResult,
    is_token_expired_error,
    maybe_recover_finviz,
)


def test_is_token_expired_error_detects_401_and_login():
    assert is_token_expired_error("HTTP 401: Invalid auth")
    assert is_token_expired_error("FINVIZ_EXPORT_LOGIN_PAGE")
    assert not is_token_expired_error("FINVIZ_EXPORT_EMPTY")


def test_maybe_recover_finviz_refreshes_runtime_key():
    finviz = MagicMock()
    finviz.set_api_key = MagicMock()
    runtime = MagicMock(finviz=finviz)
    path = MagicMock()

    with patch(
        "apps.research_screener.finviz_auto_refresh.refresh_finviz_token_if_configured",
        return_value=AutoRefreshResult(attempted=True, refreshed=True, status="REFRESHED"),
    ), patch(
        "apps.research_screener.finviz_auto_refresh.apply_refreshed_key_to_runtime",
        return_value=True,
    ) as apply_key:
        ok = maybe_recover_finviz(runtime, "HTTP 401", path)

    assert ok is True
    apply_key.assert_called_once_with(runtime, path)


def test_maybe_recover_finviz_skips_non_auth_errors():
    runtime = MagicMock()
    assert maybe_recover_finviz(runtime, "FINVIZ_EXPORT_EMPTY", MagicMock()) is False

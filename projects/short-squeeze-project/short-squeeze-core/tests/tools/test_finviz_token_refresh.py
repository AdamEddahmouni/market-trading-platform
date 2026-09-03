from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

import pytest

from tools.provider_auth.finviz_token_refresh import (
    RefreshStatus,
    persist_private_token,
    refresh_finviz_token,
    validate_export_response,
)


TOKEN = "12345678-1234-1234-1234-123456789abc"
OLD_TOKEN = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"


@dataclass
class FakeResponse:
    text: str
    status_code: int = 200
    url: str = "https://elite.finviz.com/"
    content_type: str = "text/csv"

    @property
    def headers(self) -> dict[str, str]:
        return {"content-type": self.content_type}


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = iter(responses)
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append(("POST", url, kwargs))
        return next(self._responses)

    def get(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append(("GET", url, kwargs))
        return next(self._responses)


def _private_file(tmp_path: Path) -> Path:
    path = tmp_path / ".private" / "providers.env"
    path.parent.mkdir()
    path.write_text(
        "NEWSAPI_KEY=keep-news\n"
        "FINVIZ_USERNAME=owner@example.invalid\n"
        "FINVIZ_PASSWORD=private-password\n"
        f"FINVIZ_API_KEY={OLD_TOKEN}\n",
        encoding="utf-8",
    )
    return path


def test_validation_accepts_real_csv_shape_without_returning_secret() -> None:
    response = FakeResponse(
        "Ticker,Company,Float,Short Float,Relative Volume,Short Ratio\n"
        "AAA,AAA Inc,8M,14.0%,2.0,3.2\n"
    )
    result = validate_export_response(response)
    assert result.valid is True
    assert result.row_count == 1
    assert result.columns == (
        "Ticker", "Company", "Float", "Short Float", "Relative Volume", "Short Ratio",
    )
    assert TOKEN not in str(result)


@pytest.mark.parametrize(
    ("text", "content_type", "error"),
    [
        ("<html><form action='/login'>Sign in</form></html>", "text/html", "LOGIN_PAGE"),
        ("<html>Complete CAPTCHA to continue</html>", "text/html", "MANUAL_AUTH_REQUIRED"),
        ("Unauthorized", "text/plain", "NOT_CSV"),
    ],
)
def test_validation_rejects_non_export_responses(
    text: str, content_type: str, error: str,
) -> None:
    result = validate_export_response(FakeResponse(text, content_type=content_type))
    assert result.valid is False
    assert result.error_code == error


def test_private_update_backs_up_preserves_other_values_and_replaces_atomically(
    tmp_path: Path,
) -> None:
    path = _private_file(tmp_path)
    backup = persist_private_token(path, TOKEN, timestamp="20260725T180000Z")
    updated = path.read_text(encoding="utf-8")
    assert "NEWSAPI_KEY=keep-news" in updated
    assert "FINVIZ_PASSWORD=private-password" in updated
    assert f"FINVIZ_API_KEY={TOKEN}" in updated
    assert backup.parent == path.parent / "backups"
    assert backup.read_text(encoding="utf-8").endswith(
        f"FINVIZ_API_KEY={OLD_TOKEN}\n"
    )
    assert not list(path.parent.glob("*.tmp"))


def test_refresh_is_sanitized_validates_then_updates_private_file(
    tmp_path: Path,
) -> None:
    path = _private_file(tmp_path)
    session = FakeSession([
        FakeResponse("", url="https://elite.finviz.com/"),
        FakeResponse(f'<script>window.config = {{"userToken": "{TOKEN}"}}</script>',
                     content_type="text/html"),
        FakeResponse("Ticker,Company,Float\nAAA,AAA Inc,8M\n"),
    ])
    messages: list[str] = []

    result = refresh_finviz_token(path, lambda: session, emit=messages.append)

    assert result.status == RefreshStatus.REFRESHED
    assert result.http_status == 200
    assert result.row_count == 1
    assert result.columns == ("Ticker", "Company", "Float")
    assert f"FINVIZ_API_KEY={TOKEN}" in path.read_text(encoding="utf-8")
    public_text = "\n".join(messages) + str(result)
    assert TOKEN not in public_text
    assert OLD_TOKEN not in public_text
    assert "private-password" not in public_text
    assert "FINVIZ_EXPORT_TOKEN: REFRESHED" in messages
    assert "FINVIZ_EXPORT_VALIDATION: HTTP 200" in messages
    validation_call = session.calls[-1]
    assert validation_call[2]["params"]["auth"] == TOKEN


def test_refresh_stops_for_captcha_without_changing_private_file(
    tmp_path: Path,
) -> None:
    path = _private_file(tmp_path)
    before = path.read_bytes()
    session = FakeSession([
        FakeResponse("<html>CAPTCHA challenge</html>",
                     url="https://finviz.com/login_submit.ashx",
                     content_type="text/html"),
    ])
    messages: list[str] = []

    result = refresh_finviz_token(path, lambda: session, emit=messages.append)

    assert result.status == RefreshStatus.MANUAL_AUTH_REQUIRED
    assert path.read_bytes() == before
    assert not (path.parent / "backups").exists()
    assert messages == ["FINVIZ_AUTH_SESSION: MANUAL_AUTH_REQUIRED"]


def test_refresh_rejects_login_page_export_without_changing_token(
    tmp_path: Path,
) -> None:
    path = _private_file(tmp_path)
    session = FakeSession([
        FakeResponse("", url="https://elite.finviz.com/"),
        FakeResponse(f"&auth={TOKEN}", content_type="text/html"),
        FakeResponse("<html>Please log in</html>", content_type="text/html"),
    ])

    result = refresh_finviz_token(path, lambda: session, emit=lambda _: None)

    assert result.status == RefreshStatus.INVALID_EXPORT
    assert f"FINVIZ_API_KEY={OLD_TOKEN}" in path.read_text(encoding="utf-8")
    assert not (path.parent / "backups").exists()


def test_operational_helper_is_not_imported_by_canonical_or_app_runtime() -> None:
    repo = Path(__file__).resolve().parents[2]
    needle = "tools.provider_auth"
    runtime_files = list((repo / "src").rglob("*.py")) + list(
        (repo / "apps").rglob("*.py")
    )
    assert all(needle not in path.read_text(encoding="utf-8") for path in runtime_files)


def test_refresh_launcher_uses_local_python_and_never_embeds_credentials() -> None:
    repo = Path(__file__).resolve().parents[2]
    launcher = (repo / "refresh_finviz_token.ps1").read_text(encoding="utf-8")
    assert ".venv" in launcher
    assert "-m tools.provider_auth.finviz_token_refresh" in launcher
    assert "FINVIZ_PASSWORD=" not in launcher
    assert "FINVIZ_API_KEY=" not in launcher


def test_provider_auth_dependency_is_explicit_and_optional() -> None:
    repo = Path(__file__).resolve().parents[2]
    config = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["project"]["optional-dependencies"]["provider-auth"] == [
        "curl-cffi==0.13.0",
    ]

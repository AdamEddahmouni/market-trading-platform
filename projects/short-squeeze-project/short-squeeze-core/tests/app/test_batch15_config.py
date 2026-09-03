from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_configuration_precedence_is_cli_env_file_private_default(
    tmp_path: Path,
) -> None:
    from apps.research_screener.config import resolve_application_config

    private = tmp_path / "private.env"
    private.write_text(
        "FINVIZ_API_KEY=private-key\nPORT=8101\nIBKR_PORT=4101\n",
        encoding="utf-8",
    )
    supplied = tmp_path / "integration.env"
    supplied.write_text(
        "FINVIZ_API_KEY=file-key\nPORT=8102\nIBKR_PORT=4102\n",
        encoding="utf-8",
    )
    config = resolve_application_config(
        cli={"PORT": "8104", "IBKR_PORT": "4104"},
        environ={"PORT": "8103", "IBKR_PORT": "4103"},
        config_file=supplied,
        private_file=private,
    )

    assert config.deployment.port == 8104
    assert config.providers.ibkr.port == 4104
    assert config.providers.finviz.credential == "file-key"
    assert config.source_for("PORT") == "cli"
    assert config.source_for("IBKR_PORT") == "cli"
    assert config.source_for("FINVIZ_API_KEY") == "config_file"


def test_cloud_and_frozen_modes_never_load_private_configuration(
    tmp_path: Path,
) -> None:
    from apps.research_screener.config import resolve_application_config

    private = tmp_path / "private.env"
    private.write_text(
        "FINVIZ_API_KEY=must-not-load\nNEWSAPI_KEY=must-not-load\n",
        encoding="utf-8",
    )

    for mode in ("CLOUD_PROVIDER_MODE", "FROZEN_DEMO"):
        config = resolve_application_config(
            cli={"SQUEEZE_APP_MODE": mode},
            environ={},
            private_file=private,
        )
        assert config.private_file_loaded is False
        assert config.providers.finviz.credential is None
        assert config.providers.newsapi.credential is None
        assert "must-not-load" not in json.dumps(config.public_dict())


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("false", False),
        ("0", False),
        ("no", False),
        ("true", True),
        ("1", True),
        ("yes", True),
    ],
)
def test_provider_enable_flags_are_typed(raw: str, expected: bool) -> None:
    from apps.research_screener.config import resolve_application_config

    config = resolve_application_config(
        cli={"FINVIZ_ENABLED": raw},
        environ={},
    )
    assert config.providers.finviz.enabled is expected
    assert config.providers.finviz.status == (
        "NOT_CONFIGURED" if expected else "DISABLED"
    )


def test_environment_replaces_provider_credentials_without_source_edits() -> None:
    from apps.research_screener.config import resolve_application_config

    config = resolve_application_config(
        cli={},
        environ={
            "FINVIZ_API_KEY": "environment-finviz",
            "NEWSAPI_KEY": "environment-news",
            "FINNHUB_KEY": "environment-finnhub",
            "SEC_USER_AGENT": "ExampleOrg/1.0 integration@example.invalid",
        },
    )

    assert config.providers.finviz.credential == "environment-finviz"
    assert config.providers.newsapi.credential == "environment-news"
    assert config.providers.finnhub.credential == "environment-finnhub"
    assert config.providers.sec.user_agent == (
        "ExampleOrg/1.0 integration@example.invalid"
    )
    assert all(
        provider.status == "CONFIGURED"
        for provider in (
            config.providers.finviz,
            config.providers.newsapi,
            config.providers.finnhub,
            config.providers.sec,
        )
    )


def test_config_doctor_never_serializes_secret_values_or_private_paths(
    tmp_path: Path,
) -> None:
    from apps.research_screener.config import doctor_report, resolve_application_config

    private = tmp_path / "sensitive-location" / "providers.env"
    private.parent.mkdir()
    private.write_text(
        "FINVIZ_API_KEY=top-secret-finviz\nNEWSAPI_KEY=top-secret-news\n",
        encoding="utf-8",
    )
    config = resolve_application_config(
        cli={"SQUEEZE_APP_MODE": "LOCAL_FULL"},
        environ={},
        private_file=private,
    )
    report = doctor_report(config, probe_ibkr=False)
    encoded = json.dumps(report)

    assert report["application_mode"] == "LOCAL_FULL"
    assert report["providers"]["FINVIZ_ELITE"]["status"] == "CONFIGURED"
    assert report["providers"]["NEWSAPI"]["status"] == "CONFIGURED"
    assert "top-secret" not in encoded
    assert str(tmp_path) not in encoded
    assert report["private_configuration"]["loaded"] is True
    assert "path" not in report["private_configuration"]


def test_invalid_configuration_formats_are_reported_without_values() -> None:
    from apps.research_screener.config import ConfigurationError
    from apps.research_screener.config import resolve_application_config

    with pytest.raises(ConfigurationError, match="PORT"):
        resolve_application_config(cli={"PORT": "not-a-port"}, environ={})
    with pytest.raises(ConfigurationError, match="FINVIZ_ENABLED"):
        resolve_application_config(
            cli={"FINVIZ_ENABLED": "sometimes"},
            environ={},
        )


def test_provider_bundle_construction_honors_disable_flags() -> None:
    from apps.research_screener.config import resolve_application_config
    from apps.research_screener.live_providers import ProviderBundle

    config = resolve_application_config(
        cli={
            "FINVIZ_ENABLED": "false",
            "NEWSAPI_ENABLED": "false",
            "FINNHUB_ENABLED": "false",
            "SEC_ENABLED": "false",
        },
        environ={
            "FINVIZ_API_KEY": "ignored",
            "NEWSAPI_KEY": "ignored",
            "FINNHUB_KEY": "ignored",
        },
    )
    bundle = ProviderBundle.from_application_config(config)
    status = bundle.status()

    assert status["finviz"]["status"] == "DISABLED"
    assert status["newsapi"]["status"] == "DISABLED"
    assert status["finnhub"]["status"] == "DISABLED"
    assert status["sec_edgar"]["status"] == "DISABLED"
    assert bundle.credentials.values == {}


def test_sec_provider_uses_configured_organization_user_agent() -> None:
    from apps.research_screener.config import resolve_application_config
    from apps.research_screener.live_providers import ProviderBundle

    config = resolve_application_config(
        cli={},
        environ={
            "SEC_USER_AGENT": "ExampleOrg/2.0 security@example.invalid",
        },
    )
    bundle = ProviderBundle.from_application_config(config)

    assert bundle.sec.configured is True
    assert bundle.sec.user_agent == "ExampleOrg/2.0 security@example.invalid"

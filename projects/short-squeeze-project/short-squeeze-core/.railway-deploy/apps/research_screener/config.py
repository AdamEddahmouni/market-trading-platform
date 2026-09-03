"""Central application and provider configuration.

Resolution is explicit and side-effect free. Importing this module never reads a
private file. Entry points may opt into the repository-local private provider file
only after resolving ``LOCAL_FULL`` mode.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from .credentials import ENABLE_KEYS, KNOWN_KEYS, PROVIDER_KEYS
from .deployment import DeploymentMode
SAFE_DEFAULTS = {
    "SQUEEZE_APP_MODE": DeploymentMode.LOCAL_FULL.value,
    "PORT": "8787",
    "LOG_LEVEL": "INFO",
    "FINVIZ_ENABLED": "true",
    "NEWSAPI_ENABLED": "true",
    "FINNHUB_ENABLED": "true",
    "SEC_ENABLED": "true",
    "IBKR_ENABLED": "true",
    "SENTIMENT_ENABLED": "true",
    "SENTIMENT_PROVIDER": "local_finbert",
    "SENTIMENT_BATCH_SIZE": "8",
    "NEWS_PROVIDER_ORDER": "Finviz Elite,Finnhub News,NewsAPI",
    "NEWS_CACHE_TTL_SECONDS": "900",
    "NEWS_MAX_HEADLINES_PER_SYMBOL": "30",
    "QUOTE_REFRESH_SECONDS": "15",
    "SCANNER_REFRESH_SECONDS": "180",
    "CURRENT_SCREEN_CAP": "50",
    "FINVIZ_TOP_N": "50",
    "SCANNER_ROW_LIMIT": "50",
    "SYMBOLS_PER_CYCLE": "3",
    "SYMBOLS_PER_CYCLE_MAX": "6",
    "TARGET_LIVE_CANDIDATES": "50",
    "FRESHNESS_CURRENT_SECONDS": "90",
    "FRESHNESS_DELAYED_SECONDS": "600",
    "MAX_CHART_POINTS": "400",
    "SEC_USER_AGENT": "ResearchScreener/1.0 integration@example.invalid",
    "COLLECTORS_ENABLED": "true",
    "COLLECTOR_TICK_SECONDS": "30",
    "COLLECTOR_MAX_SYMBOLS_PER_TICK": "10",
    "COLLECTOR_MAX_REQUESTS_PER_MINUTE": "60",
    "COLLECTOR_ORDER": "FinraPublishedSI,FinraDailyVolume,RssNews,SecRss,Polygon,AlphaVantage,Yfinance,Reddit,Stocktwits",
    "COLLECTOR_OVERRIDE_POLICY": "never",
    "FINRA_SI_COLLECTOR_ENABLED": "true",
    "FINRA_DAILY_VOLUME_COLLECTOR_ENABLED": "true",
    "RSS_NEWS_ENABLED": "true",
    "SEC_RSS_COLLECTOR_ENABLED": "true",
    "YFINANCE_COLLECTOR_ENABLED": "false",
    "REDDIT_COLLECTOR_ENABLED": "false",
    "STOCKTWITS_COLLECTOR_ENABLED": "false",
    "POLYGON_COLLECTOR_ENABLED": "false",
    "ALPHA_VANTAGE_COLLECTOR_ENABLED": "false",
    "COLLECTOR_CACHE_ENABLED": "true",
    "IBKR_HOST": "127.0.0.1",
    "IBKR_PORT": "4001",
    "IBKR_CLIENT_ID": "123",
}


class ConfigurationError(ValueError):
    """A configuration value has an invalid public format."""


from .credentials import (  # noqa: F401 – re-exported for backward compat
    _read_env_file, default_private_path, load_private_env,
)


def _boolean(name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be true or false")


def _integer(name: str, value: str, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be an integer") from exc
    if not minimum <= parsed <= maximum:
        raise ConfigurationError(f"{name} must be between {minimum} and {maximum}")
    return parsed


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    provider_id: str
    enabled: bool
    credential: str | None = field(default=None, repr=False)
    requires_credential: bool = True

    @property
    def configured(self) -> bool:
        return self.enabled and (
            bool(self.credential) if self.requires_credential else True
        )

    @property
    def status(self) -> str:
        if not self.enabled:
            return "DISABLED"
        return "CONFIGURED" if self.configured else "NOT_CONFIGURED"


@dataclass(frozen=True, slots=True)
class SecProviderConfig:
    enabled: bool
    user_agent: str
    contact_email: str | None = field(default=None, repr=False)
    provider_id: str = "SEC_EDGAR"

    @property
    def configured(self) -> bool:
        return self.enabled and "/" in self.user_agent and " " in self.user_agent

    @property
    def status(self) -> str:
        if not self.enabled:
            return "DISABLED"
        return "CONFIGURED" if self.configured else "INVALID_CONFIGURATION"


@dataclass(frozen=True, slots=True)
class IbkrProviderConfig:
    enabled: bool
    host: str
    port: int
    client_id: int
    provider_id: str = "IBKR"

    @property
    def configured(self) -> bool:
        return self.enabled and bool(self.host)

    @property
    def status(self) -> str:
        return "LOCAL_CONFIGURATION_PRESENT" if self.enabled else "DISABLED"


@dataclass(frozen=True, slots=True)
class SentimentProviderConfig:
    enabled: bool
    provider: str
    model_path: str | None = field(default=None, repr=False)
    batch_size: int = 8
    provider_id: str = "SENTIMENT"

    @property
    def configured(self) -> bool:
        return self.enabled

    @property
    def status(self) -> str:
        if not self.enabled:
            return "DISABLED"
        if (self.provider or "").strip().lower() in {"keyword", "keywords"}:
            return "CONFIGURED"
        if not self.model_path:
            return "NOT_CONFIGURED"
        return "CONFIGURED"


@dataclass(frozen=True, slots=True)
class NewsConfig:
    provider_order: list[str]
    cache_ttl_seconds: int
    max_headlines_per_symbol: int


@dataclass(frozen=True, slots=True)
class ProviderConfigs:
    finviz: ProviderConfig
    newsapi: ProviderConfig
    finnhub: ProviderConfig
    sec: SecProviderConfig
    ibkr: IbkrProviderConfig
    sentiment: SentimentProviderConfig
    news: NewsConfig


@dataclass(frozen=True, slots=True)
class DeploymentConfig:
    mode: DeploymentMode
    host: str
    port: int


@dataclass(frozen=True, slots=True)
class ApplicationConfig:
    deployment: DeploymentConfig
    providers: ProviderConfigs
    log_level: str
    private_file_loaded: bool
    _sources: Mapping[str, str] = field(repr=False)

    @property
    def news_provider_order(self) -> list[str]:
        return self.providers.news.provider_order

    @property
    def news_cache_ttl_seconds(self) -> int:
        return self.providers.news.cache_ttl_seconds

    @property
    def news_max_headlines_per_symbol(self) -> int:
        return self.providers.news.max_headlines_per_symbol

    def build_sentiment_analyzer(self) -> Any:
        from .sentiment_live import (
            KeywordSentimentProvider,
            LocalFinbertProvider,
            SentimentAnalyzer,
            resolve_sentiment_model_path,
        )

        sc = self.providers.sentiment
        if not sc.enabled:
            return SentimentAnalyzer()
        provider_name = (sc.provider or "local_finbert").strip().lower()
        if provider_name in {"keyword", "keywords"}:
            return SentimentAnalyzer(provider=KeywordSentimentProvider())
        model_path = sc.model_path or resolve_sentiment_model_path(None)
        if provider_name in {"local_finbert", "finbert", "finnbert", "local"}:
            if model_path:
                return SentimentAnalyzer(
                    provider=LocalFinbertProvider(
                        model_path=model_path,
                        batch_size=sc.batch_size,
                    )
                )
            return SentimentAnalyzer()
        if model_path:
            provider = LocalFinbertProvider(
                model_path=model_path,
                batch_size=sc.batch_size,
            )
            return SentimentAnalyzer(provider=provider)
        return SentimentAnalyzer(provider=KeywordSentimentProvider())

    def source_for(self, name: str) -> str:
        return self._sources.get(name, "default")

    def public_dict(self) -> dict[str, object]:
        return {
            "application_mode": self.deployment.mode.value,
            "host": self.deployment.host,
            "port": self.deployment.port,
            "log_level": self.log_level,
            "private_configuration_loaded": self.private_file_loaded,
            "providers": {
                "FINVIZ_ELITE": self.providers.finviz.status,
                "NEWSAPI": self.providers.newsapi.status,
                "FINNHUB": self.providers.finnhub.status,
                "SEC_EDGAR": self.providers.sec.status,
                "IBKR": self.providers.ibkr.status,
                "SENTIMENT": self.providers.sentiment.status,
            },
            "news": {
                "provider_order": self.providers.news.provider_order,
                "cache_ttl_seconds": self.providers.news.cache_ttl_seconds,
                "max_headlines_per_symbol": self.providers.news.max_headlines_per_symbol,
            },
        }




def _selected_mode(
    cli: Mapping[str, str],
    environ: Mapping[str, str],
    config_values: Mapping[str, str],
) -> DeploymentMode:
    raw = (
        cli.get("SQUEEZE_APP_MODE")
        or environ.get("SQUEEZE_APP_MODE")
        or config_values.get("SQUEEZE_APP_MODE")
        or SAFE_DEFAULTS["SQUEEZE_APP_MODE"]
    )
    try:
        return DeploymentMode(raw)
    except ValueError as exc:
        raise ConfigurationError("SQUEEZE_APP_MODE is unsupported") from exc


def resolve_application_config(
    *,
    cli: Mapping[str, str] | None = None,
    environ: Mapping[str, str] | None = None,
    config_file: Path | None = None,
    private_file: Path | None = None,
) -> ApplicationConfig:
    """Resolve configuration with deterministic documented precedence."""

    cli_values = {k: str(v) for k, v in (cli or {}).items() if v is not None}
    env_values = {
        key: str(value)
        for key, value in (os.environ if environ is None else environ).items()
        if key in KNOWN_KEYS and value
    }
    file_values = _read_env_file(config_file)
    mode = _selected_mode(cli_values, env_values, file_values)
    private_values = (
        _read_env_file(private_file)
        if mode is DeploymentMode.LOCAL_FULL
        else {}
    )

    merged = dict(SAFE_DEFAULTS)
    if mode is DeploymentMode.CLOUD_PROVIDER_MODE:
        # Cloud deploys opt in to IBKR explicitly; local defaults stay enabled.
        merged["IBKR_ENABLED"] = "false"
    sources: dict[str, str] = {key: "default" for key in merged}
    for label, values in (
        ("private_file", private_values),
        ("config_file", file_values),
        ("environment", env_values),
        ("cli", cli_values),
    ):
        for key, value in values.items():
            if key in KNOWN_KEYS:
                merged[key] = value
                sources[key] = label

    port = _integer("PORT", merged["PORT"], minimum=1, maximum=65535)
    ibkr_port = _integer(
        "IBKR_PORT", merged["IBKR_PORT"], minimum=1, maximum=65535
    )
    ibkr_client_id = _integer(
        "IBKR_CLIENT_ID", merged["IBKR_CLIENT_ID"], minimum=0, maximum=2_147_483_647
    )
    host = (
        "0.0.0.0"
        if mode is DeploymentMode.CLOUD_PROVIDER_MODE
        else "127.0.0.1"
    )

    from .sentiment_live import resolve_sentiment_model_path

    raw_sentiment_path = merged.get("SENTIMENT_MODEL_PATH")
    if raw_sentiment_path and str(raw_sentiment_path).strip().lower().startswith(
        "replace_with"
    ):
        raw_sentiment_path = None
    resolved_sentiment_path = resolve_sentiment_model_path(raw_sentiment_path)
    sentiment_enabled = _boolean("SENTIMENT_ENABLED", merged["SENTIMENT_ENABLED"])
    if mode is not DeploymentMode.LOCAL_FULL:
        sentiment_enabled = False

    providers = ProviderConfigs(
        finviz=ProviderConfig(
            "FINVIZ_ELITE",
            _boolean("FINVIZ_ENABLED", merged["FINVIZ_ENABLED"]),
            merged.get("FINVIZ_API_KEY"),
        ),
        newsapi=ProviderConfig(
            "NEWSAPI",
            _boolean("NEWSAPI_ENABLED", merged["NEWSAPI_ENABLED"]),
            merged.get("NEWSAPI_KEY"),
        ),
        finnhub=ProviderConfig(
            "FINNHUB",
            _boolean("FINNHUB_ENABLED", merged["FINNHUB_ENABLED"]),
            merged.get("FINNHUB_KEY"),
        ),
        sec=SecProviderConfig(
            _boolean("SEC_ENABLED", merged["SEC_ENABLED"]),
            merged["SEC_USER_AGENT"],
            merged.get("SEC_CONTACT_EMAIL"),
        ),
        ibkr=IbkrProviderConfig(
            _boolean("IBKR_ENABLED", merged["IBKR_ENABLED"])
            and mode is not DeploymentMode.FROZEN_DEMO,
            merged["IBKR_HOST"],
            ibkr_port,
            ibkr_client_id,
        ),
        sentiment=SentimentProviderConfig(
            sentiment_enabled,
            merged.get("SENTIMENT_PROVIDER", "local_finbert"),
            resolved_sentiment_path,
            _integer("SENTIMENT_BATCH_SIZE", merged["SENTIMENT_BATCH_SIZE"], minimum=1, maximum=64),
        ),
        news=NewsConfig(
            provider_order=[
                p.strip()
                for p in merged.get(
                    "NEWS_PROVIDER_ORDER", "Finviz Elite,Finnhub News,NewsAPI"
                ).split(",")
                if p.strip()
            ],
            cache_ttl_seconds=_integer(
                "NEWS_CACHE_TTL_SECONDS", merged["NEWS_CACHE_TTL_SECONDS"],
                minimum=60, maximum=86400,
            ),
            max_headlines_per_symbol=_integer(
                "NEWS_MAX_HEADLINES_PER_SYMBOL", merged["NEWS_MAX_HEADLINES_PER_SYMBOL"],
                minimum=1, maximum=100,
            ),
        ),
    )
    return ApplicationConfig(
        deployment=DeploymentConfig(mode, host, port),
        providers=providers,
        log_level=merged["LOG_LEVEL"].upper(),
        private_file_loaded=(
            mode is DeploymentMode.LOCAL_FULL and bool(private_values)
        ),
        _sources=sources,
    )


def _ibkr_reachable(config: IbkrProviderConfig) -> bool:
    if not config.enabled:
        return False
    try:
        with socket.create_connection((config.host, config.port), timeout=0.25):
            return True
    except OSError:
        return False


def doctor_report(
    config: ApplicationConfig,
    *,
    probe_ibkr: bool = True,
) -> dict[str, object]:
    providers = {
        "FINVIZ_ELITE": {"status": config.providers.finviz.status},
        "NEWSAPI": {"status": config.providers.newsapi.status},
        "FINNHUB": {"status": config.providers.finnhub.status},
        "SEC_EDGAR": {"status": config.providers.sec.status},
        "IBKR": {"status": config.providers.ibkr.status},
        "SENTIMENT": {
            "status": config.providers.sentiment.status,
            "provider": config.providers.sentiment.provider,
            "model_path": config.providers.sentiment.model_path,
        },
    }
    if probe_ibkr and config.providers.ibkr.enabled:
        providers["IBKR"]["reachable"] = _ibkr_reachable(config.providers.ibkr)
    required_missing = [
        name
        for name, item in providers.items()
        if name != "IBKR" and item["status"] in {"NOT_CONFIGURED", "INVALID_CONFIGURATION"}
    ]
    cloud_ready = config.providers.sec.configured or any(
        provider.configured
        for provider in (
            config.providers.finviz,
            config.providers.newsapi,
            config.providers.finnhub,
        )
    )
    return {
        "application_mode": config.deployment.mode.value,
        "deployment": {
            "bind_host": config.deployment.host,
            "port": config.deployment.port,
            "cloud_ready_without_ibkr": cloud_ready,
        },
        "providers": providers,
        "missing_optional_providers": required_missing,
        "private_configuration": {"loaded": config.private_file_loaded},
    }


def _render_text(report: Mapping[str, object]) -> str:
    lines = [f"APPLICATION_MODE: {report['application_mode']}"]
    providers = report["providers"]
    assert isinstance(providers, dict)
    for name, details in providers.items():
        assert isinstance(details, dict)
        suffix = (
            f" (reachable={str(details['reachable']).lower()})"
            if "reachable" in details
            else ""
        )
        lines.append(f"{name}: {details['status']}{suffix}")
    deployment = report["deployment"]
    assert isinstance(deployment, dict)
    ready = (
        "READY_WITHOUT_IBKR"
        if deployment["cloud_ready_without_ibkr"]
        else "PROVIDER_CONFIGURATION_OPTIONAL_FOR_FROZEN_DEMO"
    )
    lines.append(f"CLOUD_DEPLOYMENT: {ready}")
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apps.research_screener.config")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="validate configuration without exposing values")
    doctor.add_argument("--json", action="store_true", dest="as_json")
    doctor.add_argument("--config", type=Path)
    doctor.add_argument("--private-config", type=Path, dest="private_config")
    doctor.add_argument("--private-path", type=Path, dest="private_config",
                        help="alias for --private-config")
    doctor.add_argument("--mode", choices=[mode.value for mode in DeploymentMode])
    doctor.add_argument("--port", type=int)
    doctor.add_argument("--no-ibkr-probe", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    cli = {
        "SQUEEZE_APP_MODE": args.mode,
        "PORT": str(args.port) if args.port is not None else None,
    }
    default_private = default_private_path()
    try:
        config = resolve_application_config(
            cli=cli,
            config_file=args.config,
            private_file=args.private_config or default_private,
        )
        report = doctor_report(config, probe_ibkr=not args.no_ibkr_probe)
    except ConfigurationError as exc:
        error = {"status": "INVALID", "error_code": "CONFIGURATION_INVALID", "message": str(exc)}
        print(json.dumps(error, sort_keys=True) if args.as_json else f"CONFIGURATION_INVALID: {exc}")
        return 2
    print(
        json.dumps(report, sort_keys=True, indent=2)
        if args.as_json
        else _render_text(report)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "ApplicationConfig",
    "ConfigurationError",
    "DeploymentConfig",
    "IbkrProviderConfig",
    "ProviderConfig",
    "ProviderConfigs",
    "SecProviderConfig",
    "default_private_path",
    "doctor_report",
    "load_private_env",
    "main",
    "resolve_application_config",
]

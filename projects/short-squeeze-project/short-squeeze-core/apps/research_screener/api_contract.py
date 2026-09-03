from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

API_VERSION = "1.0.0"
SCHEMA_VERSION = "batch14.integration.v1"


def _now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def envelope(
    data: Any,
    *,
    mode: str,
    status: str = "OK",
    missingness: list | dict | None = None,
    provenance: dict | None = None,
) -> dict[str, Any]:
    return {
        "api_version": API_VERSION,
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "as_of": _now(),
        "data": data,
        "status": status,
        "missingness": [] if missingness is None else missingness,
        "provenance": {
            "application": "short-squeeze-research-screener",
            "predictive_validation": "NOT_APPLICABLE",
            **(provenance or {}),
        },
    }


def compatible_envelope(data: dict[str, Any], *, mode: str) -> dict[str, Any]:
    """Add the v1 envelope while retaining legacy top-level fields for old clients."""
    return {**data, **envelope(data, mode=mode)}


def integration_manifest(mode: str) -> dict[str, Any]:
    return {
        "application_name": "Short Squeeze Research Screener",
        "application_version": "0.16.0",
        "api_version": API_VERSION,
        "schema_version": SCHEMA_VERSION,
        "supported_modes": ["LOCAL_FULL", "CLOUD_PROVIDER_MODE", "FROZEN_DEMO"],
        "methodology_ids": [
            "legacy_prime_setup",
            "peer_reference_methodology",
            "adam_evidence_gated_prime.v1",
        ],
        "methodology_versions": {
            "legacy_prime_setup": "1.0.0",
            "peer_reference_methodology": "reference-email.v1",
            "adam_evidence_gated_prime.v1": "1.0.0",
        },
        "methodology_display_labels": {
            "legacy_prime_setup": "Legacy Prime Setup",
            "peer_reference_methodology": "Peer Reference Methodology",
            "adam_evidence_gated_prime.v1": "Evidence-Gated Prime v1",
        },
        "canonical_phase3a_policy": "phase_3a_transparent_candidate_policy.v1",
        "provider_capabilities": ["IBKR", "Finviz Elite", "NewsAPI", "Finnhub", "Finnhub News", "SEC EDGAR", "FinBERT Sentiment"],
        "environment_variables": [
            "SQUEEZE_APP_MODE", "PORT", "LOG_LEVEL",
            "FINVIZ_ENABLED", "FINVIZ_API_KEY",
            "NEWSAPI_ENABLED", "NEWSAPI_KEY",
            "FINNHUB_ENABLED", "FINNHUB_KEY",
            "SEC_ENABLED", "SEC_USER_AGENT", "SEC_CONTACT_EMAIL",
            "IBKR_ENABLED", "IBKR_HOST", "IBKR_PORT", "IBKR_CLIENT_ID",
            "SENTIMENT_ENABLED", "SENTIMENT_PROVIDER", "SENTIMENT_MODEL_PATH",
            "SENTIMENT_BATCH_SIZE",
            "NEWS_PROVIDER_ORDER", "NEWS_CACHE_TTL_SECONDS",
            "NEWS_MAX_HEADLINES_PER_SYMBOL",
            "COLLECTORS_ENABLED", "COLLECTOR_TICK_SECONDS",
            "COLLECTOR_MAX_SYMBOLS_PER_TICK", "COLLECTOR_ORDER",
            "FINRA_SI_COLLECTOR_ENABLED", "RSS_NEWS_ENABLED",
            "YFINANCE_COLLECTOR_ENABLED",
            "QUOTE_REFRESH_SECONDS", "SCANNER_REFRESH_SECONDS",
            "CURRENT_SCREEN_CAP", "FINVIZ_TOP_N", "SCANNER_ROW_LIMIT",
            "SYMBOLS_PER_CYCLE", "SYMBOLS_PER_CYCLE_MAX", "TARGET_LIVE_CANDIDATES",
        ],
        "status_enums": ["OK", "PARTIAL", "UNAVAILABLE", "ERROR"],
        "classification_enums": [
            "PRIME", "SUBPRIME", "WATCH", "NOT_QUALIFIED", "UNEVALUABLE",
            "CONFLICTED", "REFERENCE_DEFINITION_INCOMPLETE",
        ],
        "missingness_semantics": "Missing values are explicit nulls and never zero.",
        "endpoints": [
            "/health", "/healthz", "/ready", "/api/deployment",
            "/api/providers", "/api/frozen/candidates",
            "/api/frozen/candidate/<symbol>", "/api/current/candidates",
            "/api/current/candidate/<symbol>", "/api/current/refresh",
            "/api/discovery/refresh", "/api/methodologies",
            "/api/methodologies/<symbol>", "/api/export",
            "/api/v1/integration/manifest",
            "/api/news/status", "/api/news/symbol",
            "/api/collectors/status", "/api/collectors/symbol",
            "/api/sentiment/status", "/api/sentiment/symbol",
        ],
        "deployment_mode": mode,
        "health_path": "/healthz",
        "readiness_path": "/ready",
        "prohibited_capabilities": {
            "trading": "UNSUPPORTED",
            "orders": "UNSUPPORTED",
            "account_access": "UNSUPPORTED",
        },
        "security_boundary": {
            "credentials_in_api": False,
            "private_files_in_cloud": False,
            "local_ibkr_in_cloud": False,
            "provider_values_replaceable_without_source_edits": True,
        },
        "predictive_validation": "NOT_COMPLETED",
    }

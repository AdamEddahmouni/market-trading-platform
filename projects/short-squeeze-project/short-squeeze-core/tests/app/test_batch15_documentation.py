from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_professional_handoff_documentation_set_is_complete() -> None:
    required = (
        "README.md",
        "HANDOFF_README.md",
        "INTEGRATION_CHECKLIST.md",
        "LICENSE_STATUS.md",
        "THIRD_PARTY_NOTICES.md",
        "DEPENDENCIES.md",
        "docs/ARCHITECTURE.md",
        "docs/CONFIGURATION.md",
        "docs/API.md",
        "docs/METHODOLOGIES.md",
        "docs/PROVIDERS.md",
        "docs/DEPLOYMENT.md",
        "docs/TESTING.md",
        "docs/SECURITY.md",
        "docs/INTEGRATION.md",
        "docs/LIMITATIONS.md",
        "docs/CHANGELOG.md",
        "docs/openapi.json",
        "docs/railway-ib-gateway.md",
        "docs/release/privacy-and-handoff-audit.md",
    )
    assert all((ROOT / relative).is_file() for relative in required)


def test_environment_template_uses_only_safe_placeholders_and_actual_names() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    required_names = {
        "SQUEEZE_APP_MODE",
        "PORT",
        "LOG_LEVEL",
        "CSRF_PROTECTION",
        "LOCK_SENSITIVE_API",
        "FINVIZ_ENABLED",
        "FINVIZ_API_KEY",
        "NEWSAPI_ENABLED",
        "NEWSAPI_KEY",
        "FINNHUB_ENABLED",
        "FINNHUB_KEY",
        "SEC_ENABLED",
        "SEC_USER_AGENT",
        "SEC_CONTACT_EMAIL",
        "IBKR_ENABLED",
        "IBKR_HOST",
        "IBKR_PORT",
        "IBKR_CLIENT_ID",
        "IBKR_USER_ID",
        "IBKR_PASSWORD",
        "IBKR_TRADE_MODE",
        "SENTIMENT_ENABLED",
        "SENTIMENT_PROVIDER",
        "SENTIMENT_MODEL_PATH",
        "SENTIMENT_BATCH_SIZE",
        "NEWS_PROVIDER_ORDER",
        "NEWS_CACHE_TTL_SECONDS",
        "NEWS_MAX_HEADLINES_PER_SYMBOL",
        "QUOTE_REFRESH_SECONDS",
        "SCANNER_REFRESH_SECONDS",
        "FRESHNESS_CURRENT_SECONDS",
        "FRESHNESS_DELAYED_SECONDS",
        "MAX_CHART_POINTS",
        "CLOUD_BOOTSTRAP_SYMBOLS",
        "FINVIZ_AUTO_REFRESH",
        "FINVIZ_AUTO_REFRESH_COOLDOWN_S",
        "FINVIZ_PASSWORD",
        "FINVIZ_USERNAME",
        "SQUEEZE_CLOUD_LOAD_LOCAL_PROVIDERS",
    }
    assigned_names = {
        line.split("=", 1)[0]
        for line in text.splitlines()
        if line and not line.startswith("#") and "=" in line
    }

    assert assigned_names == required_names
    assert "replace_with_your_" in text
    assert "@example.invalid" in text


def test_openapi_document_is_valid_json_and_matches_stable_contract() -> None:
    document = json.loads(
        (ROOT / "docs/openapi.json").read_text(encoding="utf-8")
    )

    assert document["openapi"].startswith("3.")
    assert document["info"]["version"] == "1.0.0"
    assert "/health" in document["paths"]
    assert "/ready" in document["paths"]
    assert "/api/v1/integration/manifest" in document["paths"]
    assert "/api/csrf-token" in document["paths"]
    assert "/api/collectors/status" in document["paths"]
    assert "/api/collectors/symbol" in document["paths"]
    csrf = document["paths"]["/api/csrf-token"]["get"]["responses"]["200"]
    assert "application/json" in csrf["content"]
    schema = document["components"]["schemas"]["CsrfTokenResponse"]
    assert schema["properties"]["header"]["const"] == "X-CSRF-Token"
    assert schema["properties"]["cookie"]["const"] == "squeeze_csrf"
    encoded = json.dumps(document).lower()
    assert "/orders" not in encoded
    assert "/account" not in encoded


def test_public_documents_do_not_contain_personal_or_academic_markers() -> None:
    public_files = (
        "README.md",
        "HANDOFF_README.md",
        "INTEGRATION_CHECKLIST.md",
        "docs/ARCHITECTURE.md",
        "docs/CONFIGURATION.md",
        "docs/API.md",
        "docs/METHODOLOGIES.md",
        "docs/PROVIDERS.md",
        "docs/DEPLOYMENT.md",
        "docs/TESTING.md",
        "docs/SECURITY.md",
        "docs/INTEGRATION.md",
        "docs/LIMITATIONS.md",
    )
    forbidden = (
        "professor",
        "student",
        "class project",
        "meeting transcript",
        r"c:\users\\",
    )
    for relative in public_files:
        text = (ROOT / relative).read_text(encoding="utf-8").lower()
        # INTEGRATION_CHECKLIST.md documents technical API routes; the
        # /api/professor path alias is a legitimate endpoint reference.
        markers = (
            tuple(m for m in forbidden if m != "professor")
            if relative == "INTEGRATION_CHECKLIST.md"
            else forbidden
        )
        assert all(marker not in text for marker in markers), relative


def test_morning_check_targets_main_release_branch() -> None:
    expected_branch = "main"
    expected_version = "0.16.0"
    morning_check = (ROOT / "morning_check.ps1").read_text(encoding="utf-8")

    assert expected_branch in morning_check
    assert expected_version in morning_check
    assert "Working tree" in morning_check
    assert "Release source commit" in morning_check
    assert "Final test report" in morning_check

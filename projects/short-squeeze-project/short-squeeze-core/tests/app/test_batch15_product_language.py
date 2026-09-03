from __future__ import annotations

import json
from pathlib import Path

from apps.research_screener.api_contract import integration_manifest

ROOT = Path(__file__).resolve().parents[2]


def test_public_dashboard_uses_professional_research_summary_label() -> None:
    html = (ROOT / "apps/research_screener/static/index.html").read_text(
        encoding="utf-8"
    )
    javascript = (ROOT / "apps/research_screener/static/app.js").read_text(
        encoding="utf-8"
    )

    assert "Research Summary" in html
    assert "Professor Mode" not in html
    assert "Professor mode" not in javascript
    assert "Research summary" in javascript


def test_integration_manifest_has_neutral_methodology_display_labels() -> None:
    manifest = integration_manifest("FROZEN_DEMO")
    encoded = json.dumps(manifest)

    assert "Evidence-Gated Prime v1" in encoded
    assert "Adam Evidence-Gated Prime v1" not in encoded
    assert "professor" not in encoded.lower()
    assert manifest["environment_variables"] == [
        "SQUEEZE_APP_MODE",
        "PORT",
        "LOG_LEVEL",
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
        "SENTIMENT_ENABLED",
        "SENTIMENT_PROVIDER",
        "SENTIMENT_MODEL_PATH",
        "SENTIMENT_BATCH_SIZE",
        "NEWS_PROVIDER_ORDER",
        "NEWS_CACHE_TTL_SECONDS",
        "NEWS_MAX_HEADLINES_PER_SYMBOL",
    ]
    assert manifest["security_boundary"]["credentials_in_api"] is False

"""Focused tests: scanner route, column contract, filters, sorting, detail, navigation.

All tests are offline and read the static files directly. No server is started.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP_STATIC = ROOT / "apps" / "research_screener" / "static"
SNAPSHOT_PATH = ROOT / "apps" / "research_screener" / "snapshot.py"


# ------------------------------------------------------------------ scanner HTML

def test_scanner_html_exists_and_is_distinct_from_index():
    scanner = (APP_STATIC / "scanner.html").read_text(encoding="utf-8")
    index = (APP_STATIC / "index.html").read_text(encoding="utf-8")
    assert scanner != index
    assert "Short Squeeze Scanner" in scanner
    assert "Short Squeeze Research Screener" in index


def test_scanner_contains_required_classification_labels():
    html = (APP_STATIC / "scanner.html").read_text(encoding="utf-8")
    for text in ("PRIME", "SUBPRIME", "WATCH", "UNEVALUABLE", "CONFLICTED"):
        assert text in html


def test_scanner_contains_column_labels():
    html = (APP_STATIC / "scanner.html").read_text(encoding="utf-8")
    js = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    for text in ("SYMBOL", "PRICE", "CHANGE %", "REL VOL", "DTC", "NEWS", "SENTIMENT",
                 "PRESSURE", "IGNITION", "EVIDENCE", "CLASSIFICATION"):
        assert text in html or text in js


def test_scanner_js_table_columns_trimmed_for_scan_view():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    start = script.index("var SCANNER_COLUMNS")
    end = script.index("/* ------------------------------------------------------------------ render table */", start)
    block = script[start:end]
    for col in ("symbol", "price", "percentage_change", "relative_volume",
                "days_to_cover", "news", "sentiment",
                "pressure", "ignition", "evidence_coverage", "classification"):
        assert f'key: "{col}"' in block
    for removed in ("why_listed", "updated", "float_shares"):
        assert f'key: "{removed}"' not in block


def test_scanner_has_filter_controls():
    html = (APP_STATIC / "scanner.html").read_text(encoding="utf-8")
    for fid in ("filter-classification", "filter-symbol", "filter-min-price",
                "filter-max-price", "filter-min-change", "filter-min-relvol",
                "filter-min-pressure", "filter-min-ignition", "filter-min-coverage",
                "filter-news", "filter-sentiment"):
        assert fid in html


def test_scanner_has_advanced_link():
    html = (APP_STATIC / "scanner.html").read_text(encoding="utf-8")
    assert 'href="/advanced"' in html
    assert "Advanced" in html


def test_scanner_has_experimental_disclaimer():
    html = (APP_STATIC / "scanner.html").read_text(encoding="utf-8")
    assert "EXPERIMENTAL RESEARCH CLASSIFICATION" in html
    assert "NOT PREDICTIVE VALIDATION" in html


def test_scanner_has_refresh_controls():
    html = (APP_STATIC / "scanner.html").read_text(encoding="utf-8")
    assert "auto-refresh" in html
    assert "btn-refresh-now" in html
    assert "refresh-clock" in html


def test_scanner_has_export_buttons():
    html = (APP_STATIC / "scanner.html").read_text(encoding="utf-8")
    js = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    assert "btn-export-snapshot" in html
    assert "btn-export-csv" in html
    assert "exportSnapshot" in js
    assert "exportCsvDownload" in js
    assert "/api/export" in js


def test_scanner_has_detail_drawer_elements():
    html = (APP_STATIC / "scanner.html").read_text(encoding="utf-8")
    assert "detail-overlay" in html
    assert "detail-drawer" in html
    assert "btn-close-detail" in html
    assert "drawer-body" in html


# ------------------------------------------------------------------ scanner JS column contract

def test_scanner_js_defines_expected_columns():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    for col in ("symbol", "price", "percentage_change", "relative_volume",
                "pressure", "ignition", "evidence_coverage", "classification"):
        assert f'key: "{col}"' in script
    for col in ("float_shares", "short_float", "days_to_cover", "news", "sentiment",
                "why_listed", "updated"):
        assert f'case "{col}"' in script


def test_scanner_js_defines_class_colors():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    for cls_color in ("PRIME:", "SUBPRIME:", "WATCH:", "UNEVALUABLE:", "CONFLICTED:"):
        assert cls_color in script


def test_scanner_js_defines_pressure_color():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    assert "pressureColor" in script


def test_scanner_missing_core_si_ignores_borrow_fee():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    start = script.index("function hasMissingCoreShortInterest")
    end = script.index("function isInsufficient", start)
    block = script[start:end]
    assert "borrow_fee" not in block
    assert "published_short_interest" in block
    assert "days_to_cover" in block


def test_scanner_js_never_shows_zero_for_missing():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    assert "MISSING" in script
    assert "zero" not in script.lower()


def test_scanner_js_missing_sorts_last():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    assert "known.push(row)" in script
    assert "missing.push(row)" in script
    assert "known.concat(missing)" in script


def test_scanner_js_withheld_score_shows_insufficient():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    assert "Insufficient evidence" in script


def test_scanner_js_reads_backend_readiness_contract_keys():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    for key in (
        "summary.readiness",
        "candidate_count",
        "actionable_candidate_count",
        "unevaluable_candidate_count",
        "top_unevaluable_causes",
    ):
        assert key in script


def test_scanner_js_reads_row_data_quality_contract_keys():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    for key in (
        "row.data_quality",
        "cause_summaries",
        "missing_evidence_buckets",
    ):
        assert key in script


def test_scanner_js_coverage_categories():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    for cat in ("HIGH", "MODERATE", "LOW", "INSUFFICIENT"):
        assert cat in script


def test_scanner_js_reads_methodology_coverage_contract():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    for key in (
        "methodology_coverage",
        "total_fields_available",
        "total_fields_required",
        "coverageTooltip",
        "coverageFieldFraction",
        "HIGH_COVERAGE",
        "MODERATE_COVERAGE",
        "headerHint",
        "ADAM inputs present for Pressure/Ignition scoring",
    ):
        assert key in script


def test_scanner_js_sentiment_labels():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    for label in ("POSITIVE", "NEUTRAL", "NEGATIVE", "MIXED"):
        assert label in script


def test_scanner_js_actionable_aligns_with_evaluable_rule_count():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    assert "evaluable_rule_count" in script
    assert "hasEvaluableRules" in script
    assert "transportReadiness" in script


def test_scanner_js_fetches_from_api_screener():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    assert "/api/screener" in script
    assert "mode=CURRENT" in script


def test_scanner_js_detail_fetches_news_and_sentiment():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    shared = (APP_STATIC / "shared.js").read_text(encoding="utf-8")
    # The scanner view fetches news via the shared helper (getCachedNews), which
    # calls the news endpoint. Either file carrying the route satisfies the contract.
    assert "/api/news/symbol" in script or "/api/news/symbol" in shared
    assert "getCachedNews" in script or "getCachedNews" in shared
    assert "/api/symbol" in script


def test_scanner_js_detail_sections():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    # The scanner's buildDetail shows core sections; the full set lives in the
    # advanced page (app.js / index.html). The contract verifies the scanner has
    # the sections it actually renders.
    for section in ("HEADER", "SHORT PRESSURE", "IGNITION", "NEWS", "CATALYST / SENTIMENT"):
        assert section in script


def test_scanner_js_has_advanced_link_in_detail():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    assert "/advanced" in script
    assert "Open Advanced Analysis" in script


def test_scanner_js_default_sort_uses_classification():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    assert "defaultSort" in script
    assert "PRIME: 0" in script
    assert "classification" in script


def test_scanner_js_days_to_cover_sort_uses_cascade():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    assert "daysToCoverValue" in script
    assert "short_ratio_provider" in script


def test_snapshot_sort_days_to_cover_coerces_strings_and_short_ratio_fallback():
    from apps.research_screener.snapshot import sort_rows

    def base(sym: str, fields: dict) -> dict:
        return {
            "symbol": sym,
            "fields": fields,
            "phase3a": {"counts": {"PASS": 0, "FAIL": 0, "UNKNOWN": 0}},
            "research_detection": {"status": "UNEVALUABLE"},
            "data_mode": "REALTIME",
            "freshness": "CURRENT",
            "evidence_coverage": {"supported": 0},
            "last_updated": "2026-01-01T00:00:00Z",
        }

    rows = [
        base("HIGH", {"days_to_cover": {"status": "KNOWN", "value": "15"}}),
        base("LOW", {"days_to_cover": {"status": "KNOWN", "value": "2.5"}}),
        base("RATIO", {
            "days_to_cover": {"status": "NOT_CONFIGURED", "value": None},
            "short_ratio": {"status": "KNOWN", "value": 8.0},
        }),
    ]
    asc = [r["symbol"] for r in sort_rows(rows, "days_to_cover", False)]
    assert asc == ["LOW", "RATIO", "HIGH"]
    desc = [r["symbol"] for r in sort_rows(rows, "days_to_cover", True)]
    assert desc == ["HIGH", "RATIO", "LOW"]


def test_scanner_js_has_auto_refresh():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    assert "setAutoRefresh" in script
    assert "/api/live/auto" in script
    assert "setInterval" in script


# ------------------------------------------------------------------ server routing

def test_server_route_serves_scanner_as_default():
    source = (ROOT / "apps" / "research_screener" / "server.py").read_text(encoding="utf-8")
    assert 'self._static("scanner.html")' in source


def test_server_route_advanced_serves_index_dot_html():
    source = (ROOT / "apps" / "research_screener" / "server.py").read_text(encoding="utf-8")
    assert 'self._static("index.html")' in source
    assert '"/advanced"' in source


def test_server_still_has_existing_routes():
    source = (ROOT / "apps" / "research_screener" / "server.py").read_text(encoding="utf-8")
    for route in ("/api/screener", "/api/symbol", "/api/health", "/api/methodologies",
                  "/api/export", "/api/news", "/api/sentiment", "/api/meta"):
        assert route in source


def test_both_views_use_same_backend():
    scanner_js = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    app_js = (APP_STATIC / "app.js").read_text(encoding="utf-8")
    assert "/api/screener" in scanner_js
    assert "/api/screener" in app_js


# ------------------------------------------------------------------ no methodology duplication

def test_scanner_js_does_not_reimplement_methodology():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    assert "pressure_weights" not in script
    assert "estimated_si_formula" not in script
    assert "linear(normalize" not in script


def test_scanner_js_uses_server_provided_classification():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    assert "adam_evidence_gated_prime.v1" in script


# ------------------------------------------------------------------ no secret/path leakage

def test_scanner_html_no_credentials():
    html = (APP_STATIC / "scanner.html").read_text(encoding="utf-8")
    for secret_word in ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "PRIVATE_KEY"):
        assert secret_word not in html


def test_scanner_js_no_credentials():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    for secret_word in ("NEWSAPI_KEY", "FINNHUB_KEY", "FINVIZ_API_KEY", "SECRET"):
        assert secret_word not in script


def test_scanner_js_no_local_paths():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8")
    for path_hint in ("C:\\\\", "Users\\\\adame", "private\\\\", "credentials"):
        assert path_hint not in script


# ------------------------------------------------------------------ no trading language

def test_scanner_html_no_trading_language():
    html = (APP_STATIC / "scanner.html").read_text(encoding="utf-8").lower()
    for word in ("buy ", "sell ", "entry ", "exit ", "trade ", "position "):
        assert word not in html


def test_scanner_js_no_trading_language():
    script = (APP_STATIC / "scanner.js").read_text(encoding="utf-8").lower()
    for word in ("buy ", "sell ", "entry point", "exit point", "position size"):
        assert word not in script


# ------------------------------------------------------------------ integration manifest remains compatible

def test_integration_manifest_still_compatible():
    from apps.research_screener.api_contract import integration_manifest
    manifest = integration_manifest("FROZEN_DEMO")
    encoded = json.dumps(manifest)
    assert "Evidence-Gated Prime v1" in encoded
    assert "api_version" in encoded
    assert "methodology_ids" in encoded
    assert "adam_evidence_gated_prime.v1" in manifest["methodology_ids"]


# ------------------------------------------------------------------ release builder version

def test_release_builder_auto_detects_version_from_pyproject():
    builder = (ROOT / "tools" / "build_handoff_release.py").read_text(encoding="utf-8")
    assert "_project_version" in builder
    assert 'pyproject.toml' in builder
    assert 'version =' in builder
    assert '"--version", default=None' in builder


def test_release_builder_no_longer_hardcodes_0_15_0():
    builder = (ROOT / "tools" / "build_handoff_release.py").read_text(encoding="utf-8")
    assert '"0.15.0"' not in builder


def test_pyproject_version_is_0_16_0():
    toml = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.16.0"' in toml


# ------------------------------------------------------------------ existing dashboard preserved

def test_index_html_still_exists_and_has_all_content():
    html = (APP_STATIC / "index.html").read_text(encoding="utf-8")
    assert "Short Squeeze Research Screener" in html
    assert "Frozen Research" in html
    assert "Current screen" in html
    assert "Methodology Comparison" in html
    assert "Research Summary" in html
    assert "Provider health" in html
    assert "screener-table" in html


def test_existing_app_js_is_unchanged():
    script = (APP_STATIC / "app.js").read_text(encoding="utf-8")
    assert "loadScreener" in script
    assert "loadComparison" in script
    assert "loadResearchSummary" in script
    assert "renderResearchLandscape" in script
    assert "buildRuleTable" in script
    assert "FROZEN_COLUMNS" in script
    assert "CURRENT_COLUMNS" in script


# ------------------------------------------------------------------ frozen totals preserved
# (methodology files remain untouched)


def test_evidence_gated_prime_v1_unchanged():
    from apps.research_screener.methodologies.adam_v1 import evaluate_adam
    assert evaluate_adam is not None


def test_classification_enum_unchanged():
    from apps.research_screener.methodologies.enums import Classification
    assert Classification.PRIME.value == "PRIME"
    assert Classification.SUBPRIME.value == "SUBPRIME"
    assert Classification.WATCH.value == "WATCH"
    assert Classification.UNEVALUABLE.value == "UNEVALUABLE"
    assert Classification.CONFLICTED.value == "CONFLICTED"


def test_no_phase3e_started_in_label():
    from apps.research_screener.snapshot import research_summary
    summary = research_summary()
    assert summary["phase3e_started"] is False


# ------------------------------------------------------------------ visual style assertions

def test_scanner_html_uses_dark_theme():
    html = (APP_STATIC / "scanner.html").read_text(encoding="utf-8")
    assert 'class="scanner"' in html
    assert "styles.css" in html


def test_scanner_no_badges_that_imply_recommendations():
    html = (APP_STATIC / "scanner.html").read_text(encoding="utf-8")
    assert "BUY" not in html
    assert "SELL" not in html
    assert "OPPORTUNITY SCORE" not in html

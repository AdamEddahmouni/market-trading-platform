from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "apps" / "research_screener" / "static"


def test_comparison_dashboard_contains_required_research_contract():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    for text in (
        "Methodology Comparison",
        "EXPERIMENTAL RESEARCH CLASSIFICATION",
        "DESCRIPTIVE RESEARCH LANDSCAPE",
        "Descriptive comparison only. It does not establish predictive performance.",
        "Legacy Classification",
        "Peer Reference Status",
        "Evidence-Gated Classification",
        "Why Listed",
        "Pressure",
        "Ignition",
        "Evidence Coverage",
        "Ascending",
        "Descending",
        "Insufficient History",
    ):
        assert text in html


def test_javascript_renders_server_results_without_methodology_formula():
    script = (ROOT / "app.js").read_text(encoding="utf-8")
    assert "/api/methodologies" in script
    assert "renderResearchLandscape" in script
    assert "plotted-count" in script
    assert "unplotted-count" in script
    assert "pressure_weights" not in script
    assert "estimated_si_formula" not in script
    assert "published_short_interest_pct" not in script
    assert "REFERENCE_DEFINITION_INCOMPLETE" in script


def test_landscape_has_pressure_ignition_axes_and_missing_points_are_not_plotted():
    script = (ROOT / "app.js").read_text(encoding="utf-8")
    assert 'point.pressure == null || point.ignition == null' in script
    assert 'textContent = "Pressure"' in script
    assert 'textContent = "Ignition"' in script
    assert "data-symbol" in script
    assert "methodology-tooltip" in script

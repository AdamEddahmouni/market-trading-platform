import ast
from pathlib import Path

METRICS_SRC = Path(__file__).resolve().parents[2] / "src" / "squeeze_core" / "metrics"

FORBIDDEN_MODULES = {
    "socket",
    "http",
    "http.client",
    "urllib",
    "urllib.request",
    "requests",
    "sqlite3",
    "psycopg2",
    "pandas",
    "numpy",
    "tkinter",
    "asyncio",
}

FORBIDDEN_CALLS = {
    ("datetime", "now"),
    ("time", "time"),
    ("uuid", "uuid4"),
}

# "relative_volume" was forbidden in Phase 2A only (ADR 0031: deferred, not prohibited). Phase 2B
# implements RELATIVE_VOLUME as a descriptive, non-scored ratio (handoff Section 10.1), so the
# concept itself is now legitimate; "rvol" (the handoff's explicitly rejected informal/signal
# name, "Do not call this 'RVOL signal.'") remains forbidden. See docs/phase-2b-design.md
# Section 14.
FORBIDDEN_IDENTIFIER_SUBSTRINGS = (
    "rvol",
    "moving_average",
    "bollinger",
    "keltner",
    "ttm_squeeze",
    "candidate_score",
    "candidate_rank",
    "prime_subprime",
    "recommendation",
    "order_placement",
    "place_order",
    "cancel_order",
    "paper_trade",
    "live_trade",
    # Phase 2B additions (handoff Section 20 / docs/phase-2b-design.md Section 20): concepts
    # explicitly excluded from Phase 2B that must not leak into source even incidentally.
    # "annualiz" was narrowed to "annualized_vol"/"annualized_return" in Phase 2C: Phase 1B's
    # own pre-existing, approved BorrowFeePayload.annualized_fee_percent field legitimately
    # contains "annualiz" and is read throughout metrics/borrow_fee_changes.py -- the concept
    # actually excluded is annualized *volatility*/*return* statistics, never reintroduced by
    # Phase 2C's plain percentage-point/percentage delta arithmetic. See docs/phase-2c-design.md
    # Section 14, mirroring Phase 2B's own "relative_volume" legitimate-field carve-out above.
    "squeeze_score",
    "is_squeeze_confirmed",
    "weekly_volatility",
    "annualized_vol",
    "annualized_return",
    "sharpe",
    "true_range",
    "ewma",
    "percentile",
    "median_absolute_deviation",
    # Phase 2C additions (docs/phase-2c-design.md Section 14): concepts explicitly excluded
    # from Phase 2C that must not leak into source even incidentally.
    "short_pressure_score",
    "borrow_pressure_score",
    "cost_to_borrow_score",
    "hard_to_borrow_score",
    "squeeze_probability",
    "fail_to_deliver",
    "gamma_exposure",
    "open_interest",
)


def _all_metric_source_files():
    return sorted(METRICS_SRC.glob("*.py"))


def test_metrics_package_exists_and_has_source_files():
    files = _all_metric_source_files()
    assert len(files) >= 8


def test_no_forbidden_imports_in_metrics_source():
    for path in _all_metric_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[0] not in FORBIDDEN_MODULES, f"{path}: forbidden import {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert module.split(".")[0] not in FORBIDDEN_MODULES, f"{path}: forbidden import from {module}"


def test_no_wall_clock_or_random_uuid_calls_in_metrics_source():
    for path in _all_metric_source_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if isinstance(node.func.value, ast.Name):
                    pair = (node.func.value.id, node.func.attr)
                    assert pair not in FORBIDDEN_CALLS, f"{path}: forbidden call {pair}"
            if isinstance(node, ast.Name) and node.id == "uuid4":
                raise AssertionError(f"{path}: forbidden bare reference to uuid4")


def test_no_disallowed_metric_concepts_named_in_source():
    for path in _all_metric_source_files():
        lowered = path.read_text(encoding="utf-8").lower()
        for needle in FORBIDDEN_IDENTIFIER_SUBSTRINGS:
            assert needle not in lowered, f"{path}: contains forbidden concept {needle!r}"


def test_no_result_field_could_carry_a_ratio_ranking_or_recommendation():
    from squeeze_core.metrics import (
        BaselineStatistics,
        DaysToCoverComponents,
        MetricResult,
        NormalizedMetricResult,
        PressureMetricResult,
    )

    for model in (
        MetricResult,
        NormalizedMetricResult,
        BaselineStatistics,
        PressureMetricResult,
        DaysToCoverComponents,
    ):
        field_names = set(model.model_fields)
        # "relative_volume" is deliberately NOT forbidden here: NormalizedMetricResult's own
        # `value` field legitimately carries a relative-volume number, it just isn't named
        # "relative_volume" -- there is no field on any of these three models with that name
        # today, and there must never be a field literally named "rvol"/"score"/"rank"/
        # "recommendation"/"signal".
        for needle in ("rvol", "score", "rank", "recommendation", "signal"):
            assert not any(needle in name for name in field_names), f"{model.__name__}: unexpected field concept: {needle}"

"""Structural guards. These fail if the application ever gains a forbidden capability.

They are deliberately source-level: a runtime test only proves the path was not taken on
one run, whereas an AST scan proves the capability is not present at all.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from apps.research_screener import export as export_module
from apps.research_screener import live, providers, truth
from apps.research_screener.paths import ForwardWindowAccessError, FrozenLayout, guard_readable

APP_DIR = Path(truth.__file__).resolve().parent
PYTHON_SOURCES = sorted(APP_DIR.rglob("*.py"))
STATIC_SOURCES = sorted((APP_DIR / "static").rglob("*"))

#: IBKR order and account API surface. None of it may appear anywhere in the app.
FORBIDDEN_ORDER_IDENTIFIERS = (
    "placeOrder", "cancelOrder", "reqOpenOrders", "reqAllOpenOrders", "reqGlobalCancel",
    "reqCompletedOrders", "reqAutoOpenOrders", "exerciseOptions", "MarketOrder",
    "LimitOrder", "place_order", "cancel_order", "modify_order", "preview_order",
)
FORBIDDEN_ACCOUNT_IDENTIFIERS = (
    "reqAccountSummary", "reqAccountUpdates", "reqPositions", "reqPnL", "reqPnLSingle",
    "reqAccountUpdatesMulti", "accountSummary", "updatePortfolio", "reqFamilyCodes",
)
#: Vocabulary that would turn a research status into a recommendation or a score.
FORBIDDEN_OUTPUT_LABELS = (
    "SQUEEZE_SCORE", "squeeze_score", "PRIME_SETUP", "SUBPRIME",
    "SQUEEZE CONFIRMED", "PROFIT_POTENTIAL", "profit_potential",
)


#: ``guard.py`` exists to *name* the forbidden API surface so it can forbid it, exactly as
#: ``tools/ibkr_historical_export/guard.py`` does, and it excludes itself from its own
#: scan for the same reason. Scanning it here would flag the prohibition as the violation.
#: Its own coverage lives in ``test_current_guards.py``, which asserts the forbidden set is
#: complete and that the scanner catches an injected violation.
GUARD_MODULE_NAME = "guard.py"


def _source_text(include_guard: bool = False) -> dict[Path, str]:
    return {
        path: path.read_text(encoding="utf-8")
        for path in PYTHON_SOURCES
        if include_guard or path.name != GUARD_MODULE_NAME
    }


def test_no_order_methods_anywhere_in_the_application() -> None:
    for path, text in _source_text().items():
        for name in FORBIDDEN_ORDER_IDENTIFIERS:
            assert name not in text, f"{path.name} references order API {name!r}"


def test_no_account_data_methods_anywhere_in_the_application() -> None:
    for path, text in _source_text().items():
        for name in FORBIDDEN_ACCOUNT_IDENTIFIERS:
            assert name not in text, f"{path.name} references account API {name!r}"


def test_the_guard_module_is_the_only_exemption_and_it_only_forbids() -> None:
    """The exemption must not become a hiding place.

    ``guard.py`` may name a forbidden method only inside its forbidden-set literals; it
    may never call one. Any call syntax on a forbidden name is a violation.
    """
    guard_path = next(p for p in PYTHON_SOURCES if p.name == GUARD_MODULE_NAME)
    text = guard_path.read_text(encoding="utf-8")
    for name in FORBIDDEN_ORDER_IDENTIFIERS + FORBIDDEN_ACCOUNT_IDENTIFIERS:
        assert f"{name}(" not in text, f"guard.py calls {name!r}"
        assert f".{name}" not in text, f"guard.py invokes {name!r} as an attribute"


def test_static_assets_carry_no_trading_controls() -> None:
    for path in STATIC_SOURCES:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for word in (">BUY<", ">SELL<", ">TRADE<", "placeOrder", "buy-button"):
            assert word not in text, f"{path.name} contains {word!r}"


def test_no_score_or_ranking_model_is_introduced() -> None:
    for path, text in _source_text().items():
        for label in FORBIDDEN_OUTPUT_LABELS:
            approved_batch14_vocabulary = (
                label == "SUBPRIME"
                and (
                    (APP_DIR / "methodologies") in path.parents
                    or path.name == "api_contract.py"
                    or path.name == "server.py"
                    or path.name == "squeeze_priority.py"  # owner-approved (2026-09-04): internal discovery-trim / refresh-priority bucket, not user-facing output
                )
            )
            if approved_batch14_vocabulary:
                continue
            assert label not in text or "FORBIDDEN" in text, (
                f"{path.name} introduces the forbidden output label {label!r}"
            )


def test_sort_keys_contain_no_score_or_rank() -> None:
    from apps.research_screener.snapshot import SORT_KEYS

    for key in SORT_KEYS:
        assert "score" not in key
        assert "rank" not in key
        assert "probability" not in key


def test_application_defines_no_percentage_arithmetic_of_its_own() -> None:
    """The view layer must not re-implement a metric.

    ``x * 100`` and ``100 * x`` are the signature of a percentage computation. Neither
    appears anywhere in the package: percentages are read from the frozen metric records.
    """
    for path in PYTHON_SOURCES:
        # Batch 14's approved backend-only methodology package contains preregistered
        # normalization math. Operational logging modules (data_logger, snapshot) may
        # compute display-only percentages for rotation stats.
        if (APP_DIR / "methodologies") in path.parents:
            continue
        if path.name in ("data_logger.py", "snapshot.py"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Mult):
                continue
            for side in (node.left, node.right):
                assert not (isinstance(side, ast.Constant) and side.value == 100), (
                    f"{path.name} line {node.lineno} multiplies by 100; the view layer "
                    "must not compute a percentage"
                )


def test_no_decimal_arithmetic_is_performed_in_the_view_layer() -> None:
    """Canonical metric arithmetic is Decimal-based and lives in ``squeeze_core.metrics``."""
    for path, text in _source_text().items():
        assert "Decimal" not in text, f"{path.name} imports Decimal; it must not do metric math"


def test_displayed_percentage_equals_the_frozen_metric_value() -> None:
    """Behavioural proof that the displayed number is read, not re-derived."""
    from apps.research_screener.frozen import FrozenResearchSource

    if not FrozenLayout().available:
        pytest.skip("private frozen artifact root not present")
    source = FrozenResearchSource()
    source.load()
    for case in source.cases:
        row = source.screener_row(case)
        field = row["fields"]["percentage_change"]
        frozen_value = float(source._metrics[case["case_id"]]["value"])
        assert field["value"] == round(frozen_value, 4)
        assert field["evidence_id"] == source._metrics[case["case_id"]]["deterministic_id"]


def test_forward_window_artifacts_are_hard_blocked() -> None:
    for candidate in (
        "intake/local-bars/ibkr-batch-05/raw/XNCR-frozen-forward-24h.csv",
        "some/path/FROZEN_FORWARD_24H.jsonl",
    ):
        with pytest.raises(ForwardWindowAccessError):
            guard_readable(candidate)


def test_detection_context_path_is_permitted() -> None:
    layout = FrozenLayout()
    path = layout.detection_context_csv("XNCR")
    assert path.name == "XNCR-detection-context.csv"


def test_a_missing_field_can_never_carry_a_value() -> None:
    with pytest.raises(ValueError):
        truth.FieldValue(
            status=truth.ValueStatus.UNKNOWN, value=0, missing_reason="not collected"
        )
    with pytest.raises(ValueError):
        truth.FieldValue(status=truth.ValueStatus.UNKNOWN, missing_reason=None)
    with pytest.raises(ValueError):
        truth.FieldValue(status=truth.ValueStatus.KNOWN, value=None)


def test_missing_renders_as_a_dash_not_a_zero() -> None:
    field = truth.missing(truth.ValueStatus.NOT_COLLECTED, "never collected")
    assert field.display == truth.MISSING_PLACEHOLDER
    assert field.value is None
    assert field.as_dict()["value"] is None


def test_field_provenance_exposes_provider_label_selection_and_admissibility() -> None:
    field = truth.known(
        8_000_000,
        unit="SHARES",
        provider="Finviz Elite",
        provider_field="Float",
        selection_reason="ONLY_AVAILABLE",
        research_admissibility="RESEARCH_ADMISSIBLE",
    ).as_dict()
    assert field["provider_field"] == "Float"
    assert field["selection_reason"] == "ONLY_AVAILABLE"
    assert field["research_admissibility"] == "RESEARCH_ADMISSIBLE"


def test_historical_and_frozen_data_are_never_labelled_live() -> None:
    """The only way to produce a LIVE label is an explicit LIVE data mode."""
    assert truth.DataMode.HISTORICAL != truth.DataMode.LIVE
    assert live.classify_freshness(None) is truth.Freshness.UNKNOWN_AGE
    assert live.classify_freshness(0) is truth.Freshness.CURRENT
    assert live.classify_freshness(live.STALE_AFTER_S + 1) is truth.Freshness.STALE


def test_no_synthetic_replay_data_is_shipped() -> None:
    """REPLAY exists in the enum but nothing produces it, so nothing can fall back to it."""
    for path, text in _source_text().items():
        if path.name == "truth.py":
            continue
        assert "DataMode.REPLAY" not in text, f"{path.name} can produce REPLAY data"


def test_provider_availability_is_never_asserted_without_a_probe() -> None:
    from apps.research_screener.live_providers import ProviderBundle

    # Pass a clean runtime with no configured providers to avoid state leakage
    # from other tests that configure Finviz/NewsAPI/Finnhub clients.
    clean = ProviderBundle(finviz=None, news=None, finnhub=None, sec=None)
    down = providers.provider_health(
        probe=lambda host, port, timeout=0.5: False,
        frozen_available=False,
        runtime=clean,
    )
    by_name = {entry["name"]: entry["state"] for entry in down}
    assert by_name["IB Gateway"] == "DISCONNECTED"
    assert by_name["Market Data"] == "UNAVAILABLE"
    assert by_name["Historical Bars"] == "UNAVAILABLE"
    assert by_name["Frozen Research Artifacts"] == "UNAVAILABLE"
    assert by_name["NewsAPI"] == "NOT CONFIGURED"
    assert by_name["Finviz Elite"] == "NOT CONFIGURED"
    assert by_name["Finnhub"] == "NOT CONFIGURED"
    assert by_name["SEC EDGAR"] == "NOT CONFIGURED"
    assert by_name["Sentiment"] == "NOT CONFIGURED"


def test_provider_probe_refuses_non_localhost() -> None:
    with pytest.raises(ValueError):
        providers._socket_open("example.com", 4001)


def test_finviz_tls_impersonation_helper_is_not_referenced() -> None:
    for path, text in _source_text().items():
        if path.name == "finviz_auto_refresh.py":
            # Owner-approved exemption (2026-09-04): the Finviz Elite export-token
            # auto-refresh feature intentionally uses curl_cffi TLS impersonation.
            continue
        for banned in ("curl_cffi", "impersonate", "finviz_auth", "login_submit"):
            assert banned not in text, f"{path.name} references {banned!r}"


def test_export_refuses_credential_shaped_keys() -> None:
    with pytest.raises(export_module.CredentialInExportError):
        export_module._assert_no_credentials({"rows": [{"api_key": "x"}]})
    with pytest.raises(export_module.CredentialInExportError):
        export_module._assert_no_credentials({"schwab_token": "x"})
    export_module._assert_no_credentials({"symbol": "XNCR", "rows": [{"value": 1}]})


def test_manual_symbol_input_is_validated() -> None:
    assert live.normalize_symbol("  xncr ") == "XNCR"
    for bad in ("", "   ", "A" * 40, "DROP TABLE", "../etc/passwd", "<script>"):
        with pytest.raises(live.InvalidSymbolError):
            live.normalize_symbol(bad)

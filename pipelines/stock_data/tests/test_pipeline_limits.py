import sys
from unittest.mock import patch

from src.pipeline import (
    _run_all_with_dashboard,
    main,
    run_all,
    run_v1,
    stage_prices,
    v1_stages,
)
from src.run_config import PipelineRunConfig


def test_v1_defaults_to_unbounded_prices_and_no_aggregation():
    calls = []
    with (
        patch("src.pipeline.init_database"),
        patch("src.pipeline.ensure_progress_table"),
        patch("src.pipeline.stage_discover", side_effect=lambda: calls.append(("discover", None))),
        patch("src.pipeline.stage_prices", side_effect=lambda **kw: calls.append(("prices", kw))),
        patch("src.pipeline.stage_indexes", side_effect=lambda: calls.append(("indexes", None))),
        patch("src.pipeline.stage_validate", side_effect=lambda: calls.append(("validate", None))),
    ):
        run_v1(PipelineRunConfig())
    assert calls[1] == (
        "prices",
        {"retry_errored": False, "max_tickers": None, "aggregate": False},
    )
    assert [name for name, _ in calls] == ["discover", "prices", "indexes", "validate"]


def test_v1_stage_contract_is_explicit_and_ordered():
    stages = v1_stages(PipelineRunConfig())
    assert tuple(name for name, _ in stages) == (
        "discover",
        "prices",
        "indexes",
        "validate",
    )


def test_v1_development_limit_is_explicit():
    with (
        patch("src.pipeline.init_database"),
        patch("src.pipeline.ensure_progress_table"),
        patch("src.pipeline.stage_discover"),
        patch("src.pipeline.stage_indexes"),
        patch("src.pipeline.stage_validate"),
        patch("src.pipeline.stage_prices") as prices,
    ):
        run_v1(PipelineRunConfig(limit=17, retry_errored=True))
    prices.assert_called_once_with(
        retry_errored=True,
        max_tickers=17,
        aggregate=False,
    )


def test_price_stage_forwards_explicit_limit_and_aggregation_mode():
    with (
        patch("src.pipeline.print_header"),
        patch("src.pipeline.print_filter_summary"),
        patch("src.pipeline.get_ticker_count", return_value=0),
        patch("src.pipeline.get_data_stats", return_value={}),
        patch("src.scrapers.prices.run_price_scraper") as scraper,
    ):
        stage_prices(retry_errored=True, max_tickers=17, aggregate=False)
    scraper.assert_called_once_with(
        retry_errored=True,
        ticker_filter=None,
        max_tickers=17,
        aggregate=False,
    )


def test_legacy_all_uses_one_explicit_limit_without_hidden_caps():
    with (
        patch("src.pipeline.print_header"),
        patch("src.pipeline.init_database"),
        patch("src.pipeline.ensure_progress_table"),
        patch("src.pipeline.stage_discover"),
        patch("src.pipeline.stage_prices"),
        patch("src.pipeline.stage_fundamentals"),
        patch("src.pipeline.stage_supplemental") as supplemental,
        patch("src.pipeline.stage_indexes"),
        patch("src.pipeline.stage_export"),
        patch("src.pipeline.stage_options") as options,
        patch("src.pipeline.stage_earnings") as earnings,
        patch("src.pipeline.stage_insiders") as insiders,
        patch("src.pipeline.show_stats"),
    ):
        run_all(retry_errored=True, max_tickers=17)
    supplemental.assert_called_once_with(max_tickers=17, retry_errored=True)
    options.assert_called_once_with(max_tickers=17, retry_errored=True)
    earnings.assert_called_once_with(max_tickers=17, retry_errored=True)
    insiders.assert_called_once_with(max_tickers=17, retry_errored=True)


def test_dashboard_all_uses_one_explicit_limit_without_hidden_caps():
    with (
        patch("src.pipeline.print_header"),
        patch("src.pipeline.init_database"),
        patch("src.pipeline.ensure_progress_table"),
        patch("src.pipeline.stage_discover"),
        patch("src.pipeline.stage_prices"),
        patch("src.pipeline.stage_fundamentals"),
        patch("src.pipeline.stage_supplemental") as supplemental,
        patch("src.pipeline.stage_indexes"),
        patch("src.pipeline.stage_export"),
        patch("src.pipeline.stage_options") as options,
        patch("src.pipeline.stage_earnings") as earnings,
        patch("src.pipeline.stage_insiders") as insiders,
        patch("src.pipeline.get_data_stats", return_value={}),
        patch("src.pipeline.show_stats"),
        patch("src.ui.dashboard.LivePipelineDashboard"),
    ):
        _run_all_with_dashboard(retry_errored=True, max_tickers=17)
    supplemental.assert_called_once_with(max_tickers=17, retry_errored=True)
    options.assert_called_once_with(max_tickers=17, retry_errored=True)
    earnings.assert_called_once_with(max_tickers=17, retry_errored=True)
    insiders.assert_called_once_with(max_tickers=17, retry_errored=True)


def test_v1_cli_dispatches_explicit_limit_without_aggregation():
    with (
        patch.object(sys, "argv", ["pipeline", "v1", "17", "--retry-errored"]),
        patch("src.pipeline.init_database"),
        patch("src.pipeline.ensure_progress_table"),
        patch("src.pipeline.run_v1") as runner,
    ):
        main()
    runner.assert_called_once_with(
        PipelineRunConfig(limit=17, retry_errored=True, aggregate=False)
    )


def test_v1_cli_accepts_named_development_limit():
    with (
        patch.object(sys, "argv", ["pipeline", "v1", "--limit", "25"]),
        patch("src.pipeline.init_database"),
        patch("src.pipeline.ensure_progress_table"),
        patch("src.pipeline.run_v1") as runner,
    ):
        main()
    runner.assert_called_once_with(
        PipelineRunConfig(limit=25, retry_errored=False, aggregate=False)
    )

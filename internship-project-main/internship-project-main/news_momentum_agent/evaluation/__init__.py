"""Evaluation and backtest helpers for the news momentum agent.

Purpose
-------
Offline research pipeline: historical chain replay, panel building, pattern mining,
and proposal reports — **never** mutates live ``settings.json`` or broker code.

Features / API role
-------------------
Submodules cover IVolatility ingest, SPY/QQQ Path B replay, 0DTE backtest,
macro/VIX enrichment, pattern mining, and human-review proposals.

How this package uses ``options_confirmation_engine``
-----------------------------------------------------
Several modules prepend ``../options_confirmation_engine`` to ``sys.path`` and
import ``options_engine.data_models``, ``compute_features``, ``score_options``,
and ``features_liquidity`` so replay matches production scoring.

Options-specific vs reusable
----------------------------
Options-specific: chain adapters and options-feature replay. Reusable: chronological
train/validate splits, Wilson CI mining, and audit-log proposal workflow.
"""

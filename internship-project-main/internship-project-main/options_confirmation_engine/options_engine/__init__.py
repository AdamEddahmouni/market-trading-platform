"""Options confirmation engine — library package root.

Purpose
-------
Sibling package to ``news_momentum_agent/`` that turns an options chain snapshot
into a directional **confirmation score** (0–100) and bias label for a single
underlying. It does not place broker orders; it only produces research/signal
artifacts consumed by the news agent's decision layer.

Features / API role
-------------------
- **Ingest**: ``data_ingestor.fetch_options_snapshot`` → normalized ``Snapshot``.
- **Features**: ``features.compute_features`` → float dict + ``*_available`` flags.
- **Score**: ``scoring.score_options`` → ``options_score``, ``options_bias``,
  ``data_quality``, ``reasoning_summary``.
- **Orchestrate**: ``runner.run_ticker`` / ``run_batch`` — full pipeline + state I/O.

How ``news_momentum_agent`` consumes it
---------------------------------------
``agent/options_client.score_ticker`` prepends ``settings.options_confirmation.engine_path``
to ``sys.path``, imports ``options_engine.runner.run_batch``, and maps the first
batch item into the agent schema. ``agent/odte_decision.py`` reads liquidity
feature keys via ``features_liquidity.format_liquidity_reject_detail``. Evaluation
modules under ``news_momentum_agent/evaluation/`` import ``compute_features``,
``score_options``, and ``data_models`` for offline SPY/QQQ replay.

Options-specific vs reusable
----------------------------
Options-specific: chain providers, PCR/skew/GEX/max-pain/liquidity features,
0DTE time-of-day helpers, and the scoring weight model. Reusable patterns:
``Snapshot``/``ContractRow`` normalization, JSON state I/O (``utils``),
``merge_nested_dicts`` settings merge, and the availability-flag feature pattern
(drop missing inputs from weighted sums rather than biasing neutral).
"""

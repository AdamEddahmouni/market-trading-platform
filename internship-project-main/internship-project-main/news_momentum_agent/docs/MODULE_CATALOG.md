# Module catalog — news_momentum_agent

One-line map of first-party modules. For merge guidance see [`../../HANDOFF.md`](../../HANDOFF.md). For ops/results/bugs see [`../README.md`](../README.md).

## Orchestration

| Module | Role |
|--------|------|
| `main.py` | Live scheduler: Path A / A.2 / B, news jobs, Telegram, EOD, portfolio marks |
| `settings.json` | All knobs (horizon, gates, paths, Telegram); reload requires restart |
| `dashboard/app.py` | Streamlit UI over `state/*.json` |

## agent/ — decisions, risk, execution

| Module | Role |
|--------|------|
| `decision_engine.py` | BUY/SELL/REVIEW/LOG + lean probs; Path B override + lean gate |
| `odte_decision.py` | Agreement confidence, conflict, liquidity/setup post-layer |
| `herd_alert.py` | Multi-path HIGH_ALERT (stocktwits / news_catalyst / volume_spike) |
| `herd_scorer.py` | Herd stage, urgency, candidate merge helpers |
| `market_session.py` | RTH + expiry horizon (`same_day` / `deadline` / `range`) |
| `news_decay.py` | Age-decay news scores before decisions |
| `near_miss_tracker.py` | Shadow PnL for gated LOGs (no execution) |
| `portfolio.py` | Paper positions: stock **or** options fills, exits, equity |
| `paper_trader.py` | Decision log (`trade_log.json`) + reason templates |
| `alpaca_broker.py` | Alpaca **paper** option order mirror + contract helpers |
| `option_contracts.py` | ATM selection, marks, expiry windows |
| `options_client.py` | Bridge to `options_confirmation_engine` scoring |
| `telegram_notifier.py` | Alerts + REVIEW approve/skip + TTL → LOG |
| `risk_manager.py` | Daily loss / exposure style blocks |
| `quote_sanity.py` | Stale / identical-quote pause before entry |
| `flip_guard.py` | Flip close cooldown / min-hold |
| `alert_manager.py` | Console / structured alert printing |
| `eod_summary.py` | End-of-day Telegram/text summary |
| `eod_flatten_state.py` | Idempotent EOD flatten markers |
| `scheduler_guard.py` | Job timeouts, socket default timeout, wrap helpers |
| `path_a_pipeline_health.py` | Path A funnel counters |
| `path_b_universe_health.py` | Path B universe / kill-reason stats |
| `pattern_learner.py` | Offline insight mining from near-miss + executions |
| `decision_explainer.py` | Human-readable decision narratives |

## news/ — ingest

| Module | Role |
|--------|------|
| `news_aggregator.py` | Per-ticker multi-source news pack for scoring |
| `rss_monitor.py` | Wire RSS + seen-article dedupe |
| `web_scraper.py` | Yahoo/Benzinga/etc page body fallbacks |
| `catalyst_scanner.py` | Path A.2 broader catalyst scan |
| `solicitation_filter.py` | Drop law-firm securities solicitation PRs |
| `edgar_client.py` | SEC filing atom helpers |

## screener/

| Module | Role |
|--------|------|
| `finviz_screener.py` | Path A universe (small quiet + mid/large optionable) |
| `expiry_screener.py` | Path B liquid expiry candidates |
| `odte_screener.py` | Setup-quality / 0DTE-style prefilter watchlist |

## social/ & sentiment/

| Module | Role |
|--------|------|
| `social/stocktwits_scanner.py` | StockTwits scrape → IGNORE/WATCH/HIGH_ALERT |
| `social/keyword_detector.py` | Keyword escalation rules |
| `sentiment/claude_scorer.py` | LLM news score |
| `sentiment/llm_client.py` | Claude/Gemini client + JSON extract |
| `sentiment/keyword_boost.py` | Deterministic score nudge from keywords |
| `sentiment/claude_action_advisor.py` | Optional next-action hint |
| `sentiment/claude_trade_rationale.py` | Trade rationale text |
| `sentiment/claude_circuit.py` | Pause LLM after repeated failures |

## evaluation/ — research only (safe offline)

| Module | Role |
|--------|------|
| `odte_backtest.py` | Historical options decision simulation |
| `pattern_miner.py` | Bucket mining + OOS validation |
| `spy_qqq_replay.py` | Replay cached SPY/QQQ snapshots through Path B logic |
| `research_panel.py` / `enrich_research_panel.py` | Panel build + enrich |
| `ivolatility_client.py` | IVolatility pull/cache |
| `historical_chain_adapter.py` | Map historical rows → engine Snapshot |
| `vix_history.py` / `macro_calendar.py` | Regime / event enrichers |
| `proposals.py` | Research → settings change proposals |

## scripts/

CLI wrappers for research, demo seed, smoke tests, paper verify. Each module docstring states whether it is safe vs live-agent. Prefer `scripts/run_research_pipeline.py` for offline work.

## Sibling package

| Path | Role |
|------|------|
| `../options_confirmation_engine/` | Chain ingest → features → liquidity → score (see its README) |

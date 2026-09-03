# Internship agent notes

## Purpose and package boundary

`internship-project-main/internship-project-main` is a paper-only research
prototype with two sibling packages:

- `news_momentum_agent`: scheduler/orchestrator, discovery, scoring, decisions,
  paper portfolio, Telegram review flow, Streamlit dashboard, evaluation, and
  JSON runtime state.
- `options_confirmation_engine`: no-broker chain ingestion → features → hard
  liquidity gate → 0–100 directional score/bias; imported by path rather than
  installed as a package.

## Decision flow and equations

Three discovery paths feed one action stack: Path A (FinViz/social/news), Path
A.2 (broad wire/catalyst research; auto-execution off by default), and Path B
(liquid near-expiry/options-positioning; off by default). Candidate signals are
news, options, flow trend, and max pain, casting `+1`, `-1`, or `0`.

`agreement` is the share of non-zero directional votes on the dominant side.
The documented confidence approximation is:

```text
confidence = 100 × agreement × data_quality × regime_mult
             × sample_factor × IV_penalty / late_day_factor
sample_factor = min(1, max(0, n_dir − 1) / 3)
```

Thus one directional vote yields zero confidence; two cap near 33%, three near
67%, and four or more reach the full sample factor. Confidence (evidence
agreement) and lean (BUY/SELL/WAIT/AVOID action mass) are separate gates.
Actions are `BUY`, `SELL`, `REVIEW`, or `LOG`; unanswered review requests expire
to `LOG` (default eight-minute TTL). Options liquidity requires an ATM-band
contract meeting spread-as-percent-of-mid and open-interest thresholds.

## Modules and tools

- `agent/decision_engine.py`, `odte_decision.py`, `market_session.py`,
  `portfolio.py`, `options_client.py`, `telegram_notifier.py`, and
  `near_miss_tracker.py` provide the core decision/ops layer.
- `news/`, `social/`, `sentiment/`, and `screener/` provide catalyst discovery,
  StockTwits/herd tagging, LLM scoring, solicitation filtering, and FinViz
  screens. `evaluation/` is explicitly offline research.
- The options engine uses Unusual Whales (preferred), yfinance fallback, optional
  FinViz, or offline replay. Its output includes feature values/subscores/weights,
  data quality, score, bias, and a liquidity reject reason.
- Environment integrations: Anthropic Claude, Gemini, Unusual Whales, Alpaca
  paper, Telegram, FinViz, IVolatility (research), Yahoo/yfinance, StockTwits,
  SEC EDGAR, RSS/site scraping. Settings load only at agent startup.

## State, horizons, and lessons

State under `news_momentum_agent/state/` includes portfolio/executions, trade
log, reviews, watchlists, health, and near-miss outcomes. Option horizons are
`same_day` (0DTE), `deadline`, and `range` (DTE range; current direction).
Documented experience: 0DTE was a poor fit for a minutes-scale news/LLM/review
loop; a COIN 0DTE paper stop lost $410 amid unlogged bid/ask noise. The handoff
reports no profitable proof (TGB/NWL underwater and COIN loss) and no validated
N≥30 out-of-sample 0DTE patterns in the stated research window.

## Merge guidance / constraints

Reuse discovery, scoring, confidence gates, review and research patterns; route
futures separately rather than through option contracts. Prefer shares for thin
catalysts and options only where liquidity passes. **Fixed (2026-08-15/16):**
headline plumbing (`extract_primary_headline`), Telegram approve confidence
floor, bid/ask logging on executions, and equity fallback when options fail
liquidity on strong catalysts (`prefer_equity_on_liquidity_reject`). Remaining:
fragile scraping/providers, possible LLM billing failure.

## Windows baseline (2026-08-14)

| Check | Result |
|---|---|
| `pip install -r requirements.txt` + `yfinance` | Pass — `yfinance` is required by `agent/paper_trader.py` but missing from `requirements.txt` |
| `python scripts/seed_demo_state.py` | Pass — creates `state/demo.lock` and seeded portfolio (Unicode arrow in final print may error on cp1252 consoles; seed still succeeds) |
| Streamlit `:8501` | Pass — HTTP 200 |
| `settings.json` `options_confirmation.engine_path` | Fixed to `../options_confirmation_engine` (was a Mac-specific absolute path) |

**Demo walkthrough:** from `news_momentum_agent/`, run `python scripts/seed_demo_state.py` then `python -m streamlit run dashboard/app.py`. Do not run `main.py` while `state/demo.lock` exists.

## Windows baseline (2026-08-15)

| Check | Result |
|---|---|
| `pip install -r requirements.txt` in `.venv` | Pass |
| `python scripts/seed_demo_state.py` | Pass — Unicode arrows in walkthrough prints fixed for cp1252 consoles |
| Streamlit `:8501` | Pass — HTTP 200 with `--server.headless true` |
| `state/demo.lock` | Present — blocks `main.py` scheduler (paper orders) |
| Equity fallback on illiquid options | Pass — strong catalyst + `liquidity_reject` → `REVIEW` with `instrument_hint=stock` |
| `tests/test_donor_fixes.py` + `tests/test_odte_decision.py` | Pass — 21/21 unittest |
| IMP catalyst bridge (`/explore/catalyst`) | Available when demo state seeded — read-only trade_log/watchlist projection |

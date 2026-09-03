# Internship project handoff — merge into stocks / futures stack

This repo is **two sibling packages** that work together as a **paper options research agent**. The receiving project already (or will) trade **stocks and futures**; this document explains what to keep, what to replace, and how to wire the options lane without copying the whole loop blindly.

**Start here, then dive into code:**

| Doc | Audience |
|-----|----------|
| **This file (`HANDOFF.md`)** | Integrator merging into a multi-asset finance app |
| [`news_momentum_agent/README.md`](news_momentum_agent/README.md) | **Full story**, confidence math, Jul 31 results with live marks, bugs, APIs/subscriptions, path to consistency |
| [`news_momentum_agent/docs/MODULE_CATALOG.md`](news_momentum_agent/docs/MODULE_CATALOG.md) | Every first-party module, one line each |
| [`news_momentum_agent/docs/eod_2026-07-31_analysis.md`](news_momentum_agent/docs/eod_2026-07-31_analysis.md) | Jul 31 near-miss skew — confidence-gate check (one session) |
| [`options_confirmation_engine/README.md`](options_confirmation_engine/README.md) | Options feature/scoring package API |

**Honesty:** as of the 2026-07-31 paper session the options book was **not profitable** (COIN 0DTE **−$410**; TGB/NWL still open underwater). Treat this as a researched prototype with a clear evolution from equity catalysts → options → failed pure-0DTE → multi-day options product — not a proven strategy.

---

## 1. What you are inheriting

```
internship project/
├── HANDOFF.md                          ← you are here
├── news_momentum_agent/                ← live paper agent + research + dashboard
│   ├── main.py                         ← scheduler / orchestrator
│   ├── settings.json                   ← all runtime knobs (loaded once at start)
│   ├── agent/ news/ screener/ social/ sentiment/
│   ├── evaluation/                     ← offline research (safe; no live fills)
│   ├── dashboard/                      ← Streamlit UI over state/*.json
│   ├── state/                          ← runtime JSON (portfolio, logs, health)
│   └── logs/
└── options_confirmation_engine/        ← chain → features → score (no broker)
    └── options_engine/
```

**Product in one sentence:** discover short-horizon equity catalysts (news/social/volume or options urgency), score them, gate on liquidity + agreement confidence + lean, then open **Alpaca paper options** (or local paper only).

Three discovery paths feed **one** decision/execution stack (not three products): Path A, Path A.2 (research-only by default), Path B.

---

## 2. Recommended merge strategy (stocks + futures + options)

Do **not** drop `main.py` wholesale into a multi-asset bot. Split by **lane**:

### Keep / reuse as libraries (asset-agnostic or easy to retarget)

| Piece | Why it’s useful for stocks/futures |
|-------|--------------------------------------|
| News ingest (`news/*`, RSS, scrapers, solicitation filter) | Catalyst detection for any underlier |
| Social funnel (`social/*`, `herd_alert`) | Attention / volume spike tagging |
| LLM scoring (`sentiment/*`) | Headline → signed score + rationale |
| Decision skeleton (`decision_engine`, confidence ideas in `odte_decision`) | Gate patterns; retarget votes |
| Scheduler guards, Telegram REVIEW flow | Ops patterns |
| Risk / flip / quote sanity concepts | Risk UX for any instrument |
| `portfolio` **stock** path | Already supports `trading.instrument: "stock"` |
| `evaluation/*` research harness | Pattern mining mindset (extend beyond 0DTE SPY/QQQ) |

### Keep as the **options lane** (do not force onto futures)

| Piece | Notes |
|-------|--------|
| `options_confirmation_engine` | Chain features, liquidity floor, bias/score |
| `agent/options_client.py`, `option_contracts.py` | Bridge + ATM selection |
| Path B expiry screener | Liquid equity options only |
| Options exits (TP/SL/EOD/deadline/range) | Premium-based; futures need different exits |
| Alpaca **option** order mirroring | Separate from futures broker |

### Replace or stub for futures / cash equity

| Current | Futures / stock fork |
|---------|----------------------|
| Finviz equity screens | Futures universe / continuous contracts / your scanner |
| `require_optionable` / liquidity_reject on chains | Equity: optional; futures: margin/liquidity of the future itself |
| Options confirmation gate | Volume, basis, term structure, or skip |
| `instrument: options` + ATM calls/puts | Stock shares or futures contracts + multiplier |
| 0DTE / DTE range horizon | Session / roll calendar for futures |
| Alpaca paper options | Your broker adapters |

### Suggested integration shape

```
Your platform
├── discovery/          ← reuse news + social + screens (retargeted)
├── scoring/            ← reuse LLM + keyword boost
├── gates/              ← port confidence/lean/liquidity concepts
├── instruments/
│   ├── equity.py       ← portfolio stock path + your broker
│   ├── futures.py      ← NEW
│   └── options.py      ← this project’s options lane (engine + contracts)
└── execution/          ← shared risk, Telegram REVIEW, ledger
```

**Instrument policy (from this week’s lessons):** options for **liquid** names (Path B–like); consider **direct equity** for thin small-cap catalysts where chains don’t exist or spreads are 46–60%+. Futures are a third lane — don’t shoehorn them through `option_contracts.py`.

---

## 3. Decision → execution contract (what to call from your app)

Stable mental model for the receiving team:

1. **Candidate** — ticker + `signal_source` (`news` | `news_catalyst` | `expiry`) + social level  
2. **News score** — Claude/Gemini float in roughly `[-1, 1]` (+ optional keyword boost)  
3. **Options confirmation** (equity options only) — `options_client` → score/bias/features/liquidity  
4. **`decide_trade_action(...)`** → `BUY | SELL | REVIEW | LOG` + meta (`confidence`, lean, reason codes)  
5. **Execution** — `portfolio.execute_*` and/or Telegram approve → same portfolio APIs  
6. **Exits** — `manage_option_exits` / stock exits; horizon from `market_session`

Reason codes you will see in logs / near-miss: `low_confidence`, `weak_lean`, `liquidity_reject`, `options_not_clear`, `stale_quote`, …

---

## 4. Runtime dependencies (env)

| Env var | Used by | Required for |
|---------|---------|--------------|
| `ANTHROPIC_API_KEY` | Claude scoring | Live Path A news scores |
| `GEMINI_API_KEY` | Alternate LLM | Optional |
| `UNUSUAL_WHALES_API_TOKEN` | Chain features | Preferred options confirmation |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | Paper fills + some contract discovery | Broker-mirrored paper |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Alerts + REVIEW | Phone approvals |
| `FINVIZ_AUTH_TOKEN` | Elite CSV | Optional |
| `IVOLATILITY_API_KEY` | `evaluation/*` only | Research; not live agent |

Wire `settings.json` → `options_confirmation.engine_path` to the absolute path of `options_confirmation_engine/`.

---

## 5. Safe commands (do not disturb a live agent)

```bash
# Live agent (single instance via state/agent.pid) — only if you intend to run it
cd news_momentum_agent && ./venv/bin/python -u main.py

# Dashboard (read-only over state/)
./venv/bin/python -m streamlit run dashboard/app.py

# Research — does NOT place live trades
./venv/bin/python -m evaluation.odte_backtest
./venv/bin/python scripts/run_research_pipeline.py
```

Changing `settings.json` requires an agent **restart** to take effect. Do not restart someone else’s live session without coordination.

---

## 6. State files that matter

Under `news_momentum_agent/state/`:

| File | Role |
|------|------|
| `portfolio.json` / `executions.json` | Paper book + fill ledger |
| `trade_log.json` | Every decision (including LOG) |
| `pending_reviews.json` | Telegram REVIEW queue |
| `watchlist.json` / `high_alert.json` | Path A universe |
| `expiry_watchlist.json` | Path B |
| `health.json` | Heartbeat / funnel |
| `near_miss_tracker_*.json` | Shadow outcomes for gated LOGs |
| `agent.pid` / `demo.lock` | Process / demo guards |

---

## 7. Known limitations (read before merging)

Full detail in `news_momentum_agent/README.md` §4–6. Short list:

- Not profitable on 2026-07-31 paper trades (TGB, NWL, COIN).  
- REVIEW cards can show **“No headline”** when scrapes score body text but RSS `matched_articles` is empty.  
- Small-cap news ≠ tradeable options (no chain / wide spreads).  
- Historical miner: **0** validated N≥30 OOS patterns on 6m SPY/QQQ 0DTE.  
- Confidence sample-size penalty exists because thin agreement caused losses.  
- Fast 0DTE stops (COIN) can be **mark/spread noise**; bid/ask not logged yet.  
- Path A.2 should stay research-only until more sessions (solicitation false positives).

---

## 8. Concrete next steps for the receiving intern

1. Port **discovery + scoring** into the parent app; keep options as an optional confirmation + instrument adapter.  
2. Implement **instrument routing**: liquid → options; thin equity catalyst → shares; futures → futures adapter.  
3. Add **earnings calendar / VIX regime** features (missed scheduled AMZN-sized moves).  
4. Extend research beyond 0DTE index options.  
5. Log **bid/ask** at entry/exit.  
6. Fix headline plumbing for scrape-backed scores.  
7. Evaluate Path A.2 over more days before auto-execute.

---

## 9. Documentation map in code

Every first-party `.py` under `news_momentum_agent/` and `options_confirmation_engine/options_engine/` has an expanded **module docstring** covering purpose, pipeline role, and stocks/futures merge notes. Prefer those + this file over tribal knowledge from the internship week.

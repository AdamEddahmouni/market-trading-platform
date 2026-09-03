# News Momentum Agent — Internship Handoff

Paper-trading research system that watches for short-horizon stock catalysts, scores them with news + social + options features, and (when gates pass) opens **paper** options on Alpaca. This document is for whoever picks the work up next — including the **story of how the project evolved**, honest results, bugs, APIs/subscriptions, and what it would take to earn money more consistently.

**Merging into a larger stocks/futures project?** Start at the repo root: [`../HANDOFF.md`](../HANDOFF.md). Module map: [`docs/MODULE_CATALOG.md`](docs/MODULE_CATALOG.md). Jul 31 near-miss gate analysis: [`docs/eod_2026-07-31_analysis.md`](docs/eod_2026-07-31_analysis.md). Options engine: [`../options_confirmation_engine/README.md`](../options_confirmation_engine/README.md). Every first-party `.py` has an expanded module docstring (purpose, pipeline role, merge notes).

**Status (marks pulled ~2026-08-01 early UTC):** early-stage research system. **Not profitable.** Do not treat paper P&L as proof of an edge. Live book still holds TGB/NWL calls underwater; COIN 0DTE put was stopped out for **−$410** the same session.

---

## 0. The story of the project (read this first)

This did not start as an options bot.

### Phase 1 — News catalyst + herd on small caps (equity)

The original idea was simple and practical: find **small-cap stocks** that were already moving a little (**roughly +0.5% to +1%**) with **news catalysts** and **herd / social attention**, then buy the **stock** to try to catch a larger jump the same day or soon after.

That version worked **decently well** for a research prototype. The edge thesis was “attention + catalyst + early move,” not “predict the whole market.” Path A (Finviz quiet/catalyst universe → StockTwits → news score → decision) is the descendant of that loop.

### Phase 2 — Path B: near-expiry / options-positioning lane

Next came **Path B**: a liquid-name / near-expiry scan that looked at options positioning and urgency **without** needing a news headline first. In practice Path B **did not fire often**. When it did, it was occasional — useful as a second discovery door into the same decision stack, not as a constant trade printer.

### Phase 3 — Move the product to options

The project then shifted from “buy the stock” toward **options** as the instrument: leverage on catalysts, defined risk on premium, and a path that looked more like a finance-product demo. Early options paper trading was “alright” in the sense that the pipeline could discover → score → open contracts end-to-end.

### Phase 4 — Pure 0DTE experiment (hard lesson)

About two weeks into a more aggressive options push, the project was steered toward a **pure 0DTE** (same-day expiry) trader.

That was **extremely difficult** — and the last trading day’s COIN trade is a concrete example of why.

0DTE is a game mostly won by firms with:
- co-located / institutional-grade market data,
- microstructure-aware execution,
- tight spread control,
- and risk systems built for premiums that can **halve in minutes**.

If retail-style automated 0DTE were easy, far more people would print it consistently. This agent is not that stack. The bot tended to **lose money**, and it was hard to run a fully automatic AI agent into 0DTE because:
- premiums move faster than news-cycle loops,
- a high confidence bar is required (and still not enough),
- mark/mid quotes without logged bid/ask make stop-losses easy to trip on **noise**,
- and thin agreement (few independent votes) can still look “actionable” to a human on Telegram REVIEW.

### Phase 5 — Back to a multi-day options product (where we are now)

After the 0DTE pain, the project moved **back** toward a more realistic options product: **multi-day expiries** (`range` horizon, e.g. DTE in `[0, 30]`), wider Path A market-cap coverage, liquidity floors kept strict, Path A.2 kept research-only by default, and Telegram REVIEW as a human brake.

**That is why the handoff looks the way it does:** three discovery paths into **paper options**, with equity-style catalyst DNA still underneath, and a clear scar from the 0DTE era.

```
Equity catalyst herd (worked OK)
        → Path B near-expiry (rare fires)
        → Options instrument
        → Pure 0DTE attempt (painful; COIN example)
        → Multi-day options product (current)
```

---

## 1. What this project does

### Plain language

The bot looks for stocks that might move soon (unusual volume, social chatter, or a strong news headline). It reads the news, checks whether options markets look bullish or bearish, and only then considers a small paper options trade. Every trade is fake money on Alpaca paper. If something is unclear, it can ask a human on Telegram to approve or skip. It is a learning lab for catalyst → options decision-making, not a finished strategy.

### Architecture (three discovery routes → one instrument)

All three paths feed the **same** decision and paper-options machinery. They are not three products.

| Path | Role | Auto-execute? |
|------|------|----------------|
| **Path A** | Watchlist from Finviz “quiet / catalyst” screens (small-cap quiet movers **plus** mid/large optionable movers). StockTwits + multi-path HIGH_ALERT tagging → news scoring → full gates → trade or LOG. | Yes, when settings allow and gates pass (or Telegram APPROVE on REVIEW). |
| **Path A.2** | Broader wire/catalyst scan (`news_catalyst`) — research lane for strong headlines without requiring social herd first. | **No** by default (`path_a2_auto_execute: false`). REVIEW/Telegram possible; treat as research-only until proven. |
| **Path B** | Liquid-name / seed-ETF expiry scan — options positioning and urgency without a news gate. | Off by default (`path_b_auto_execute: false`); high confidence + lean bars when enabled. |

```
Finviz / wires / expiry screener
        │
        ▼
Alert tagging (HIGH_ALERT via stocktwits OR news_catalyst OR volume_spike)
        │
        ▼
News aggregate + Claude/Gemini score  (+ keyword boost; solicitation filter)
        │
        ▼
Social gate (require_social_signal — IGNORE blocked unless path exempt)
        │
        ▼
Options score + liquidity floor (spread / OI / chain present)
        │
        ▼
Agreement confidence + lean gates  →  BUY | SELL | REVIEW | LOG
        │
        ├── LOG: audit / near-miss shadow only
        ├── REVIEW: Telegram approve/skip (TTL → auto LOG)
        └── BUY/SELL: paper options open (Alpaca paper + local portfolio.json)
                │
                ▼
        Exits: take-profit / stop-loss / same-day EOD flatten / deadline flatten / expiry
```

### Paper-only

- Local portfolio: `state/portfolio.json`
- Broker mirror: Alpaca **paper** API (fills appear in Alpaca paper UI)
- **No live/real-money execution** in this codebase’s intended use
- Settings load once at `main.py` start — change `settings.json`, then restart the agent process

---

## 2. How confidence and decisions work

### Votes → agreement → confidence

Independent signals each cast **+1 (bullish), −1 (bearish), or 0 (neutral / uncounted)**:

- **news** (decayed score vs buy/sell thresholds)
- **options** (bias / score bands)
- **flow_trend** (if available)
- **max_pain** (if available)

GEX and setup-quality “screener” do **not** vote directionally.

Only non-zero votes enter `n_dir` (directional count) and agreement (share of votes on the dominant side).

**Confidence (0–100)** is roughly:

`100 × agreement × data_quality × regime_mult × sample_factor × (IV penalty) / (late-day tod if needed)`

where

`sample_factor = min(1, max(0, n_dir − 1) / 3)`  

So: **1 vote → 0 conf**, **2 votes → at most ~33%** even with perfect agreement, **3 → ~67%**, **≥4 → full**.  

**Why:** an earlier formula let two agreeing signals look “high confidence” and produced real losing paper trades. The sample-size penalty exists so Path B’s ~65 bar cannot clear on a thin vote set.

### Lean vs confidence (separate gates)

- **Lean** = which way action-probability mass points (BUY/SELL/WAIT/AVOID %) from news + social + options.
- **Confidence** = how much independent evidence agrees (above).

Both matter. Example: Path B can have a directional lean but still LOG on `low_confidence` or `weak_lean` (lean not strong enough vs WAIT).

Path B also requires clearer options bias and usually `n_dir ≥ 2` before auto-resolving REVIEW → BUY/SELL.

### REVIEW, Telegram, timeout

- **REVIEW** = conflict or ambiguous setup; human gate preferred.
- Telegram alert includes inline buttons (buy stock / buy call / sell-put / skip) or yes/no + ticker reply.
- Pending rows live in `state/pending_reviews.json`.
- TTL: `execution.review_ttl_minutes` / `notifications.pending_ttl_minutes` (default **8**). Unanswered → **`expired` → LOG (no trade)**.
- Important: `trading.instrument: "options"` means a “Buy stock” button still opens **calls** (options mode). Label vs behavior mismatch is a known footgun.
- Heartbeat only reports `pending_reviews=N`; the approval UI is on the REVIEW message itself.

---

## 3. Setup and running

### Environment variables

Put secrets in `.env` (never commit). Names only:

| Variable | Role | Required? |
|----------|------|-----------|
| `ANTHROPIC_API_KEY` | Claude news scoring / rationales | Preferred; billing can run out (see §8) |
| `GEMINI_API_KEY` | Default LLM in current `settings.llm.provider` | Primary when provider=`gemini` |
| `UNUSUAL_WHALES_API_TOKEN` | Options features / chains | Preferred for options; Yahoo/Alpaca fallbacks exist |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | Alpaca **paper** orders + quotes | Required for broker-mirrored paper trades |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Alerts + REVIEW approvals | Required for phone approvals; agent runs without |
| `FINVIZ_AUTH_TOKEN` | Finviz Elite CSV | Optional; default Path A uses HTML scraper |
| `IVOLATILITY_API_KEY` | Historical research (`evaluation/*`) | Research only — not needed for live agent |

### Start the live agent

```bash
cd news_momentum_agent
./venv/bin/python -u main.py
# or append logs:
# nohup ./venv/bin/python -u main.py >> logs/overnight_agent.log 2>&1 &
```

Single-instance lock: `state/agent.pid`. Demo lock: `state/demo.lock` pauses live overwrites.

Config: `settings.json` (horizon mode, gates, Path A mid/large, Telegram, etc.).

### Dashboard

```bash
./venv/bin/python -m streamlit run dashboard/app.py
# → http://localhost:8501
```

Professor-style demo (seeds state, does **not** start `main.py`):

```bash
./scripts/run_demo.sh
```

### Research / backtest (independent of live trading)

Under `evaluation/` — IVolatility replay, pattern miner, SPY/QQQ panels, etc. Safe to run without the live agent; does not place trades.

```bash
./venv/bin/python -m evaluation.odte_backtest
# plus scripts under evaluation/ and scripts/smoke_*.py
```

---

## 4. Results — 2026-07-31 session (honest, with live marks)

**Verdict:** the bot was **not profitable** on this session. COIN alone realized **−$410**. TGB and NWL remain open and are still **slightly underwater** on mark. Cumulative paper `realized_pnl` in `portfolio.json` is also deeply negative (~**−$2,669**), reflecting more than just this one day.

Sources of truth: `state/portfolio.json`, `state/executions.json`, `state/pending_reviews.json`, `logs/overnight_agent.log`. Live marks below were re-pulled via the agent’s option mark helper + Yahoo chain (~2026-08-01 early UTC).

| Ticker | Contract | Why it traded | Entry | Live standing | P&L |
|--------|----------|---------------|-------|---------------|-----|
| **TGB** | 7× Aug 21 2026 **$7 calls** | Path A REVIEW → Telegram approve. News ~**+0.75** (quarterly strength / estimate revisions / ~27% implied upside narrative). Options bias **neutral** (~48.5). Lean **BUY ~81%**. Agreement confidence only **~12%** (`n_dir=2`, news vs max-pain conflict). Card showed “No headline.” | $0.40 @ 18:56Z | Spot ~**$6.77**; mark ~**$0.38** (Yahoo bid/ask **0.35 / 0.45**); still open | Unrealized ≈ **−$14** at $0.38 mark (worse if you mark at bid) |
| **NWL** | 7× Aug 21 2026 **$6 calls** | Path A.2 REVIEW → Telegram approve. News **+0.85** Q2 beat / sales growth / tariff recovery narrative. Options **neutral** (~53.5). Lean **BUY ~57%**. Agreement conf **~12%**. Earlier same day often **liquidity_reject** on ATM OI/spreads — still a structurally thin options name. | $0.275 @ 19:33Z | Spot ~**$5.60**; mark ~**$0.245** (Yahoo bid/ask **0.15 / 0.30**, last 0.20); still open | Unrealized ≈ **−$21** at $0.245 mark (much worse at bid) |
| **COIN** | 10× Jul 31 2026 **$150 puts** (**0DTE**) | Path A REVIEW → Telegram approve in seconds. News **−0.85** (surprise quarterly loss / weak outlook / crypto weakness). Lean **SELL ~87%**. Options neutral (~58.8). Agreement conf still only **~12%**. Spot at signal ~**$151.10**. | $0.875 @ 19:07:37Z | **stop_loss** @ **$0.465** @ 19:08:25Z (~**48 seconds**) | Realized **−$410** |

Earlier same-day eyeball marks (TGB ~$0.35 / NWL ~$0.15) were worse; the table above is the **newer API pull**. Spreads are wide enough that “P&L” depends heavily on which side of the quote you believe.

### Why those buys/sells happened (decision detail)

All three cleared as **REVIEW**, not auto-BUY/SELL. The human Telegram approval is what turned low-agreement setups into fills.

**TGB (bullish calls)**  
- Gemini/news rationale at entry: strong quarterly results, upward estimate revisions, large implied upside vs street.  
- System math disagreed with itself: bullish news vs bearish **max pain** distance; options score ~neutral. That is why confidence sat at **12%** even with an **81% BUY lean**.  
- At entry the AI “if right” story was: drift up toward the **$7** OI wall / strike so the call can work before theta hurts; “if wrong”: max-pain gravity / negative GEX pulls it down into the stop.

**NWL (bullish calls, Path A.2)**  
- Catalyst: Q2 beat and tariff-recovery narrative with a large intraday move / 52-week-high framing.  
- Same pattern: strong news, weak agreement (`n_dir=2`), neutral options, **12%** confidence, REVIEW.  
- Liquidity had already rejected NWL multiple times earlier (`oi_below_min`, spreads often **20%+**). Approving calls on that name is exactly the small-cap-options mismatch the project learned the hard way.

**COIN (0DTE puts — the cautionary tale)**  
- Catalyst: Coinbase surprise loss + weak outlook while crypto was sliding; news score **−0.85**.  
- Strong **SELL lean (87%)** but still only **12%** agreement confidence — conflict between bearish news and other positioning features.  
- Product chose **same-day $150 puts**. Within ~48 seconds the premium mark fell from **$0.875 → $0.465** and hit **stop_loss**.  
- Important nuance: by the next mark check, COIN spot was ~**$146.26** (and headlines still bearish). So the **directional news thesis eventually moved the stock the “right” way**, but the **0DTE option position was already dead** — classic “right story, wrong instrument / wrong stop on noisy marks” failure. We only store mid/mark in executions (no bid/ask), so microstructure noise vs a real micro-bounce cannot be separated cleanly. Either way, it is a **0DTE process failure**, not proof the headline was fake.

### Where it stands now + what the AI thinks next

Fresh Gemini pass (documentation only, **not** trading advice; confidence labels are the model’s):

| Name | Now | Model outlook (low confidence) |
|------|-----|--------------------------------|
| **TGB** | Still long Aug21 **$7** calls; spot under strike (~6.77 vs 7) | Thesis still “estimate / growth upside,” but path 1–2 weeks looks sideways-to-choppy; main risk is failure to follow through so OTM calls decay. **Confidence: low.** |
| **NWL** | Still long Aug21 **$6** calls; spot ~5.60; **very wide** option quotes | Post-earnings hangover + illiquid options → hard to realize “fair” exits; spread is a tax. **Confidence: low.** |
| **COIN** | Flat / closed | Lesson: 0DTE stops can fire on noise **before** the underlying move you wanted shows up. Do not treat that loss as “the news was wrong.” |

Entry-time Gemini rationales (stored on the REVIEW cards) already warned that agreement was weak and REVIEW was appropriate — the losses came after **human approval** of low-confidence cards, plus 0DTE microstructure on COIN.

### Near-miss / confidence-gate check (same day)

While the three filled trades lost money, the **rejected** pile tells a different story about the gates. Full write-up with caveats: [`docs/eod_2026-07-31_analysis.md`](docs/eod_2026-07-31_analysis.md).

From `state/near_miss_eod_2026-07-31.json`: **138** near-misses (**56** `low_confidence`, **82** `liquidity_reject`). Among low-confidence shadow outcomes with decisive labels: **26 would_have_lost vs 8 would_have_won** (~3:1 against). In the **0–44** confidence band alone (**N=55**): **26 lost / 7 won**. That is the signature you want from a working risk filter — the setups the confidence gate blocked looked, in aggregate, more like shadow losers than winners — and it is the first session-level quantitative hint that the **sample-size confidence fix** (motivated by earlier thin-evidence losses such as QQQ/IWM-style Path B pain) is filtering in the right direction. **One day, shadows not fills, does not measure false negatives** — see the linked doc before treating it as proven.

---

## 5. Known bugs / limitations (this week and from the 0DTE era)

### REVIEW card shows “No headline”

`main.py` sets Telegram/trade-log `news_headline` from `matched_articles[0]` (RSS/wire matches). Yahoo/Benzinga/MarketWatch scrapes append body text under synthetic titles like `"COIN ticker news page"` and often **never** become `matched_articles` headlines. The LLM can still score that body (**−0.85** COIN, **+0.85** NWL, **+0.75** TGB) while the card says **“No headline” / Unknown source**. Confused debugging on BE, COIN, NWL, AAPL, etc.

- Sometimes the underlying score was legitimate (COIN earnings-loss narrative; NWL Q2 beat; TGB estimate/upside narrative).
- Sometimes it was not (BE: Kaplan Fox **securities-solicitation** PR misread as company catastrophe). Mitigation: `news/solicitation_filter.py` + `news.exclude_law_firm_solicitations` (default true).

### Small/micro-cap vs options liquidity

Many Path A news names have **no chain** (`no_listed_chain`) or **46–60%+** ATM spreads — structurally bad for an options-only book even when news is real. NWL’s repeated `liquidity_reject` / wide bid-ask on the open call is the live exhibit. Motivated:

1. Horizon pivot off pure 0DTE → **deadline** then live **`range`** (`options_dte_range`, e.g. `[0, 30]`).
2. Path A universe widen: quiet small-cap scan **plus** mid/large optionable catalyst scan.
3. Strategic recommendation: **equity** for thin catalysts; **options** only for liquid names.

Liquidity floor values were **not** loosened to “fix” this — discovery was steered toward names that can pass the floor.

### Pure 0DTE is a bad fit for this agent’s loop

News aggregation + LLM scoring + Telegram REVIEW is a **minutes-scale** loop. 0DTE premiums are a **seconds-scale** market. High confidence bars help but cannot fix:
- mid/mark stop-outs (COIN),
- missing bid/ask logs,
- and competing with desks that live in the order book.

Historical research (IVolatility + pattern miner, ~6 months SPY/QQQ **0DTE**): **0** patterns with N≥30 and out-of-sample validation. Read as: naive feature combos don’t show an obvious edge in ultra-efficient index 0DTE — not as “the pipeline is broken.”

### Confidence sample-size fix

Pre-fix: few agreeing votes → inflated confidence → losing paper trades (including liquid-name / Path B pain earlier in the week that motivated the change). Post-fix: `sample_factor` from `n_dir` (see §2). Note today’s three REVIEW fills still had **~12% agreement confidence** — the human override is currently more powerful than the confidence gate. The same day’s **near-miss skew** (losers dominating the LOG pile; see [`docs/eod_2026-07-31_analysis.md`](docs/eod_2026-07-31_analysis.md)) is preliminary evidence the automatic gate is filtering the right way when it is allowed to LOG.

### Other footguns

- Telegram Markdown used to 400 on underscores (e.g. `herd_forming`); escaping/fallback added.
- “Buy stock” under `instrument: options` → calls.
- Path A.2 found at least one bad solicitation-style source before the filter — keep research-only until more sessions.
- Anthropic credits can hit zero mid-session (logs show billing errors); Gemini fallback/provider switch matters for uptime.
- Missed **scheduled** catalysts (e.g. Amazon’s large earnings move) because discovery is reactive, not calendar-driven.

---

## 6. What it would take to earn money more consistently

There is no honest claim that a settings tweak tomorrow creates a proven edge. These are the highest-leverage changes suggested by this week’s evidence:

1. **Instrument routing by universe**  
   - Liquid / Path B–like names → options (where leverage and tighter spreads exist).  
   - Thin small-cap Path A catalysts → **shares** (return to what worked in Phase 1).  
   - Futures (in the parent project) → separate adapter; do not force through `option_contracts.py`.

2. **Stay off pure 0DTE until microstructure is first-class**  
   Keep `range` / multi-day. If 0DTE returns, require NBBO, log bid/ask, widen or delay stops, and much stricter session filters.

3. **Log bid/ask at entry and exit**  
   Makes COIN-class losses diagnosable from `executions.json` alone.

4. **Scheduled catalysts + regime**  
   Earnings calendar, known events, VIX regime — so foreseeable jumps (AMZN-style) are not invisible to discovery.

5. **Do not let Telegram approve ignore confidence forever**  
   Either block approve below a floor, or size down dramatically on `confidence_pct < 30` / `n_dir < 3`.

6. **Fix headline plumbing**  
   Promote scrape/primary titles into `news_headline` so humans and auditors see what the LLM scored.

7. **Extend research beyond 0DTE SPY/QQQ**  
   Mine multi-day single-name options and equity-catalyst panels with proper OOS validation before raising auto-execute.

8. **Path A.2**  
   More research sessions before `path_a2_auto_execute`; solicitation filter is necessary but not sufficient.

9. **Honor Telegram instrument hints** or relabel buttons when global mode is options.

10. **Keep paper long enough**  
    Consistent profitability needs a measured expectancy after costs/spreads — not three REVIEW fills on one afternoon.

---

## 7. APIs, subscriptions, and alternatives

Nothing below includes secret values — only **what** is used and **why**.

| Service | Env / config | Why this project used it | Cost shape (typical) | Alternatives |
|---------|--------------|--------------------------|----------------------|--------------|
| **Anthropic Claude** | `ANTHROPIC_API_KEY`; models in `settings.llm` / `claude` | Strong structured news scoring & rationales | Usage / prepaid credits (can hit $0 mid-day — seen in logs) | Gemini (already wired), OpenAI (`openai` provider in `llm_client`), local open models (quality drop) |
| **Google Gemini** | `GEMINI_API_KEY`; often `settings.llm.provider: gemini` | Cheap/fast JSON scoring & REVIEW copy; good fallback when Claude billing fails | Free tier + paid | Claude, OpenAI, or keyword-only scoring (weaker) |
| **Unusual Whales** | `UNUSUAL_WHALES_API_TOKEN` | Preferred live options chain + flow features for confirmation | Paid options/flow subscription | **yfinance** (free, flaky), Alpaca option chain helpers, Polygon/Tradier/ORATS, Intrinio |
| **Alpaca Paper** | `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | Paper fills that show in a real broker UI; some expiry/contract fallback | Free paper trading | Local-only `portfolio.json` (already works), other paper brokers (IBKR paper, etc.) |
| **Telegram Bot API** | `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | Mobile REVIEW approve/skip + alerts | Free | Slack/Discord webhooks, dashboard-only approve, email |
| **Finviz** | HTML scraper by default; optional `FINVIZ_AUTH_TOKEN` Elite | Path A / Path B universe discovery (quiet movers, optionable filters) | Free scrape (fragile) / Elite paid CSV | TradingView screener APIs, Polygon snapshots, custom exchange feeds, Yahoo screeners |
| **Yahoo Finance (yfinance)** | No key (unofficial) | Spots, option chains, news headlines, engine fallback | Free, rate-limited, can break | Paid market-data vendors above |
| **IVolatility** | `IVOLATILITY_API_KEY` | Historical options research / replay only | Paid historical | Databento, ORATS, CBOE LiveVol, Polygon options history |
| **StockTwits** | Scraped in `social/stocktwits_scanner.py` | Herd / keyword attention for Path A | Free scrape (fragile) | Reddit/X APIs (ToS/cost), FinViz news+volume only, proprietary alt-data |
| **SEC EDGAR** | Public | Filing catalyst hints | Free | Third-party filing APIs (Quiver, etc.) |
| **RSS / site scrapes** | `news/*` | Wire & page-body catalysts | Free + brittle (401s on MarketWatch etc.) | NewsAPI, Benzinga paid, Polygon news, Bloomberg (enterprise) |

### Design intent behind the stack

- **LLM** turns messy text into a signed score humans can audit.  
- **Unusual Whales** (or fallback chain) answers “does the options market vaguely agree?” and enforces **liquidity**.  
- **Alpaca paper** makes the demo feel like a real product without risking cash.  
- **Telegram** is the safety brake that 0DTE especially needed — though approving low-confidence cards can still hurt.  
- **IVolatility** is for **offline** honesty checks, not live fills.

### If the parent stocks/futures project wants to cut cost

1. Run discovery + equity execution **without** Unusual Whales until you need options confirmation.  
2. Prefer Gemini (or a single LLM) to avoid double spend.  
3. Keep Alpaca paper or even local JSON until strategy expectancy is positive after spreads.  
4. Replace fragile scrapes with one paid news + one paid market-data pipe when you go near live money.

---

## 8. Horizon modes (quick reference)

Configured by `trading.options_expiry_horizon`:

- **`same_day`** — 0DTE only; EOD flatten on expiry day. **Tried; painful for this agent.**
- **`deadline`** — expiries on/before `deadline_date` (legacy aliases: `through_friday`, …); deadline-day flatten enabled.
- **`range`** — DTE in `options_dte_range` (e.g. `[0, 30]`); **no** deadline flatten; TP/SL still apply; EOD flatten only if the contract expires **today**. **Current product direction.**

---

## Key files (map)

| Area | Path |
|------|------|
| Live loop | `main.py` |
| Settings | `settings.json` |
| Decisions + lean | `agent/decision_engine.py` |
| Agreement confidence | `agent/odte_decision.py` |
| HIGH_ALERT multi-path | `agent/herd_alert.py` |
| Session / expiry horizon | `agent/market_session.py` |
| Paper portfolio / exits | `agent/portfolio.py` |
| Telegram REVIEW | `agent/telegram_notifier.py` |
| Near-miss shadows | `agent/near_miss_tracker.py` |
| Path A Finviz | `screener/finviz_screener.py` |
| Solicitation filter | `news/solicitation_filter.py` |
| Liquidity floor | `../options_confirmation_engine/options_engine/features_liquidity.py` |
| Research | `evaluation/*` |
| Dashboard | `dashboard/app.py` |
| Runtime state | `state/*` |
| Logs | `logs/overnight_agent.log` |

Full catalog: [`docs/MODULE_CATALOG.md`](docs/MODULE_CATALOG.md).

---

## License / use

Internship research code. **Paper trading only** unless you deliberately change that (not recommended without a full risk redesign, bid/ask logging, and instrument routing). This README is a handoff document, not a pitch deck.

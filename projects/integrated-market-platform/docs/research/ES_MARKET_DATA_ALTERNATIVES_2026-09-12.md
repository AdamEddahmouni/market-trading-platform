# ES / E-mini S&P 500 market-data alternatives (overnight research)

**Date:** 2026-09-12  
**Lane:** A  
**Classification:** `RESEARCH_COMPLETE` — candidate catalog only; no provider activation  
**Doctrine:** Distinguish **cataloged IMP integration** vs **verified entitled live stream**

## Campaign context (read-only synthesis)

FTEP-V1-001 prospective ES evidence (foreground branch artifacts, not edited overnight) requires a **verified entitled US futures quote stream**. Reconciliation gate and `es-news-provider-stack-selection.json` record:

- **Primary candidate:** Moomoo `US_FUTURES_QUOTE` — stale probe showed not entitled (`PROBE-MOOMOO`, `EXT-MOOMOO-FUTURES-ENTITLEMENT`).
- **Secondary challenger:** IBKR observational `DELAYED_L1` — not a substitute for entitled continuous ES quote.
- **Engineering-only:** `news.fixture` and recorded-eval bridges — not prospective market evidence.

## Alternative provider matrix (candidates)

| Provider / path | ES continuous quote | Depth / L2 | Trade tape (CVD) | IMP integration state | External dependency | Overnight verdict |
|---|---|---|---|---|---|---|
| Moomoo OpenD | Primary design intent | Yes (equity path mature) | Partial | `moomoo.live` cataloged | OpenD + futures entitlement | **NEEDS_OWNER_DECISION** + fresh probe |
| IBKR observational | Delayed L1 only (verified live canary) | L2 blocked NOT_ENTITLED on test account | TRADES NOT_ENTITLED | G6–G11 complete offline | Gateway + market data subs | **SECONDARY** / calibration only |
| CME MDP (direct) | Yes (vendor) | Yes | Yes | Not in IMP | Commercial license, infra | **NEEDS_EXTERNAL_ACCESS** |
| Databento / Polygon futures | Yes (vendor APIs) | Varies by tier | Varies | Not wired | Paid API + legal review | **SPEC_READY_FOR_LATER** |
| Tradier | Equities/options focus | Limited futures | No | Paper slot exists | Not ES-primary | **LOW_VALUE** for ES campaign |
| Alpaca | Equities/crypto | No ES CME | No | Broker inventory only | N/A | **DROP** for ES |
| Internal fixture / replay | Deterministic | Fixture depth | Fixture trades | Verified offline | None | **ENGINEERING_ONLY** |

## Smallest sufficient stacks (by use case)

### 1. FTEP prospective campaign (lawful ES evidence)

1. Refresh Moomoo capability probe with owner-approved OpenD session.
2. Record capability row per `MARKET_DATA_CAPABILITY_CONTRACT.md`.
3. Optional IBKR delayed L1 as **challenger**, not primary.

### 2. Offline IMP development / regression

1. `ibkr.observational` capture/replay fixtures (existing G6–G9 machinery).
2. Deterministic news + recorded strategy eval (FTEP-D006 path).

### 3. Research / backtest (non-campaign)

1. `pipelines/stock_data` Parquet export path for external tools.
2. DECISION-RESEARCH-001 SS family fixtures (no live ES).

## Risks

- Treating delayed IBKR L1 as campaign-primary → **false qualification**.
- Activating paid vendors without governance → violates overnight doctrine.
- Foreground overlap: `US_FUTURES_QUOTE` projection fixes → **DEFER_TO_FOREGROUND_LANE**.

## Recommended morning action

Owner-run Moomoo futures entitlement probe and append fresh evidence to capability matrix (foreground), then re-evaluate G-A6 campaign-readiness.

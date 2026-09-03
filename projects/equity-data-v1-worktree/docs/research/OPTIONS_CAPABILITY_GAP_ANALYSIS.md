# Options Capability Gap Analysis (Deliverable 7)

**Status:** Data and capability inventory for Options redesign  
**Date:** 2026-08-18

---

## Summary

| Category | Exists | Provider | Missing | Delayed | Cost | Reconstructable | Research-only |
|---|---|---|---|---|---|---|---|
| Unusual activity events | YES | Fixture BIYA | Live feed | N/A | Free (fixture) | Per-event from trades | No |
| Full options chain | NO | Tradier stub | Entire chain | N/A | $$ likely | Partial from NBBO | Until O1 |
| Historical chains | NO | — | Expired contracts | N/A | $$$ | Some from paid archives | Yes |
| NBBO quotes | Partial | Fixture bid/ask | Live NBBO | Real-time | $$ | No | No |
| Option trades | NO | — | Prints | Real-time | $$ | No | O5 |
| Open interest | Partial | Fixture | Live OI | T+1 typical | $ | No | No |
| Provider IV | NO | — | Vendor IV | Varies | $ | Internal recompute | O2 |
| Provider Greeks | NO | — | Vendor Greeks | Varies | $ | Internal recompute | O2 |
| Full surface | NO | — | σ(K,T) | N/A | $$ | From chain if quotes | O2 |
| Participant side | NO | — | Open/close, customer/dealer | N/A | $$$ | No | O5 — fail closed |
| Complex order classification | NO | — | Spreads, combos | N/A | $$$ | No | O5 |
| Exercise/assignment data | NO | — | Assignment history | N/A | Broker | No | O9 |
| Corporate action adjustments | NO | — | Adjusted chains | N/A | $ | Manual for key names | O1 |
| Earnings calendar | Partial | Donor news | PIT earnings dates | Varies | $ | SEC + vendor | O7 |
| Dividend schedule | NO | — | Ex-dates, amounts | N/A | $ | Some free sources | O2/O9 |
| Borrow rate (for carry) | NO | SS P2 planned | Securities lending | T+1 | $$ | No | O2 |
| Risk-free rate | Partial | Manual assumption | Live curve | Daily | Free (FRED) | Yes | O2 |
| Underlying forward | Partial | Spot from bars | Dividend-adjusted forward | N/A | — | Yes from spot+div | O2 |

---

## 1. What exists today

### 1.1 Admitted fixture data

**`ADMITTED-OPTIONS-BIYA-001`**
- 5 unusual-activity events
- Fields: strike, expiry, type, bid/ask, volume, OI, pre-computed iv_rank/volume_ratio/skew_signal
- PIT: `event_time`, `available_time` on envelope
- Symbol: BIYA only

### 1.2 Platform primitives available to Options

| Primitive | Source | Options use |
|---|---|---|
| Bar OHLCV | Replay fixtures | RV baseline, P inputs |
| Order flow / CVD | NVDA fixture | Cross-lane context, P inputs |
| Walk-forward harness | `research/walk_forward.py` | Model validation |
| Model spec identity | `research/model_spec.py` | Version tracking |
| Quality observations | `data_quality/` | Chain QA |
| Whale ledger PIT queries | `whale_ledger.py` | Activity history |

### 1.3 Provider interfaces (stubs)

| Protocol | Status | Notes |
|---|---|---|
| `OptionChainProvider` | Stub | Tradier-class per foundation design |
| `FixtureOptionsProvider` | **Implemented** | BIYA only |
| `UnconfiguredOptionChainProvider` | Fail-closed | Returns unavailable |

### 1.4 Cross-lane

| Signal | Producer | Consumer |
|---|---|---|
| Order flow → squeeze | **Working** | SS causal evaluator |
| Options → squeeze | **Missing** | SS evaluator (fields exist) |
| Squeeze → options | **Missing** | P forecast (planned) |

---

## 2. What is missing (by roadmap phase)

### O1 — Contract correctness
- Canonical contract schema
- Multi-symbol entitlement
- Historical expired chain archive
- Corporate action adjustment pipeline
- Quality taxonomy enforcement

### O2 — IV/Greeks/Surface
- Live chain ingestion
- Internal IV solver
- Greeks engine
- Surface builder + QA
- Borrow/carry for American options

### O3 — Q inference
- Risk-neutral density extraction
- Event-implied move from straddle prices

### O4 — P vs Q
- Physical distribution (SHARED P2)
- Edge decomposition framework
- VRP estimation

### O5 — Flow
- Signed trade classification
- Abnormal flow baselines
- Complex order resolution

### O6 — Dealer
- Participant-side data (typically unavailable retail)
- OI×gamma proxy with explicit uncertainty

### O7 — Events
- Earnings-implied move history
- IV crush empirical database

### O8 — Strategy
- Payoff engine
- Multi-leg liquidity aggregation

### O9 — Execution
- Options fill model in simulator
- Assignment/exercise logic

---

## 3. Provider capability matrix (Options extensions)

Extend `PROVIDER_AND_DATA_RESEARCH_MATRIX.md`:

| Capability | Tradier (candidate) | IBKR (candidate) | CBOE (candidate) | Minimum for phase |
|---|---|---|---|---|
| Options chain | Research | Research | N/A | O1 |
| Historical chain | Research | Research | Paid | O1 backtest |
| NBBO quotes | Research | Research | — | O2 |
| Trade prints | Research | Research | — | O5 |
| OI | Research | Research | — | O1 |
| Greeks/IV | Vendor | Vendor | — | O2 (or recompute) |
| Open/close flag | Often no | Sometimes | — | O5 — fail closed |
| Complex orders | Rare | Sometimes | — | O5 |

**Selection principle:** incremental research value / total data cost. No procurement authorized in this document.

---

## 4. What can be reconstructed

| Data | Method | Confidence |
|---|---|---|
| Internal IV | Newton/Brent from mid prices | High if quotes valid |
| Internal Greeks | BSM/Binomial from IV | High if IV valid |
| Surface | Fit to chain quotes | Medium — depends on QA |
| Forward price | Spot − PV(dividends) | Medium |
| RV | From bar history | High |
| Abnormal flow | vs historical baselines | Medium — needs history |
| Dealer gamma | OI × gamma proxy | **Low** — label as proxy only |

---

## 5. What must remain research-only

| Capability | Until |
|---|---|
| Dealer true positioning | Participant data or validated proxy model |
| Calibrated P vs Q trade signals | O4 + walk-forward validation |
| 0DTE intraday surface | O11 + execution correctness |
| Cross-asset vol ML | O10 + out-of-sample evidence |
| Squeeze → call recommendation | Never — must go through P vs Q |

---

## 6. Cost / licensing notes

| Item | Estimate | Notes |
|---|---|---|
| Real-time options NBBO | $50–500+/mo | Vendor dependent |
| Historical options tick | $500+/mo or one-time | Required for serious backtest |
| OPRA full feed | $$$$ | Institutional |
| Finviz (donor) | Existing | SI context, not options chain |
| FRED rates | Free | Carry assumptions |

---

## 7. Immediate gaps blocking next milestone (O1)

1. No `OptionContract` schema — **implement**
2. No formal quality flags — **implement**
3. No cross-lane Options publisher — **implement adapter stub**
4. No multi-symbol fixture for surface testing — **admit incrementally**
5. No historical chain — **plan only; do not fake backtests**

---

## Related documents

- `PROVIDER_AND_DATA_RESEARCH_MATRIX.md`
- `OPTIONS_DISCREPANCY_REGISTER.md`
- `PLATFORM_COOPERATIVE_MASTER_ROADMAP.md`

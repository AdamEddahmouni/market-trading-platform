# Short Squeeze Capability Gap Analysis

**Status:** Living provider capability matrix for the causal Short Squeeze lane
**Spec:** [SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md](SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md) (§7)
**Companion:** [SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md](SHORT_SQUEEZE_IMPLEMENTATION_ROADMAP.md) (Phase 7)
**Product version:** 0.16.0
**Last updated:** 2026-09-05

## 1. Purpose and scope

This document is the **provider capability matrix** the causal research spec points
to in §7. It maps every evidence field the causal model consumes (or wants to
consume) to the providers that can supply it, records what is currently available
versus missing, and registers each gap with an owner, prerequisite, and closure
path.

Reading rules:

- The [spec](SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md) is authoritative where the two
  conflict.
- **Runtime truth beats this document.** The screener probes providers live and
  serves the results at `GET /api/capabilities` (see §2). This doc is the
  design-time map; the probe registry is the runtime report. When a probe flips a
  status, update this doc to match.
- Nothing here authorizes new providers, live signal promotion, or fabricated
  missingness. Gaps stay explicit (`UNKNOWN`, `NOT_SUPPORTED`,
  `RESEARCH_INADMISSIBLE`) — never synthesized
  ([LIMITATIONS.md](../LIMITATIONS.md), ADR-0047).

## 2. Vocabulary (three surfaces, one set of facts)

| Surface | Location | Role |
|---|---|---|
| Runtime probe registry | `apps/research_screener/provider_capabilities.py`, served at `GET /api/capabilities` | Per-provider, per-capability probe status (`Capability` × `CapabilityStatus`) |
| Causal evaluator missingness | `src/squeeze_core/intelligence/evaluator.py` → `SqueezeIntelligenceResult.missing_capabilities` | Per-symbol list of evidence the model wanted but did not receive; rendered as the "Missing capabilities" node in the explanation graph (`intelligence/explanation.py`) |
| Field admissibility | `docs/PROVIDERS.md` — `RESEARCH_ADMISSIBLE` / `RESEARCH_INADMISSIBLE` / `DISPLAY_ONLY` | Whether a field may enter rules and methodology at all |

The probe registry's `Capability` enum is the canonical vocabulary:
`DISCOVERY`, `REALTIME_QUOTE`, `DELAYED_QUOTE`, `HISTORICAL_BARS`, `VOLUME`,
`RELATIVE_VOLUME`, `FLOAT`, `SHARES_OUTSTANDING`, `SHORT_FLOAT`, `SHORT_RATIO`,
`SHORT_INTEREST`, `DAYS_TO_COVER`, `BORROW_FEE`, `SHORTABLE_SHARES`,
`SHORTABILITY`, `NEWS`, `FILINGS`, `HALTS`, `SENTIMENT`, `FUNDAMENTALS`,
`MARKET_CAP`. Statuses: `AVAILABLE`, `AUTHENTICATION_REQUIRED`,
`INVALID_CREDENTIAL`, `PERMISSION_UNAVAILABLE`, `NOT_CONFIGURED`, `NOT_SUPPORTED`,
`ERROR`, `STALE`, `UNTESTED`.

## 3. Provider capability matrix

### 3A. Available in the current pipeline (research-admissible)

| Causal field | Provider(s) | Runtime capability | Notes |
|---|---|---|---|
| `float_shares` | Finviz Elite | `FLOAT` | Admissible |
| `published_short_interest` (SI %) | Finviz Elite; FINRA published SI (`FinraPublishedSICollector`, `FINRA_SHORT_INTEREST_V1`) | `SHORT_INTEREST` / `SHORT_FLOAT` | Two admissible sources; publication-lag rules apply (spec §6) |
| `short_float` | Finviz Elite; FINRA published SI collector | `SHORT_FLOAT` | |
| `days_to_cover` / short ratio | Finviz Elite | `DAYS_TO_COVER` / `SHORT_RATIO` | |
| `relative_volume` | Finviz Elite | `RELATIVE_VOLUME` | |
| `percentage_change` (canonical return) | IBKR | `REALTIME_QUOTE` / `HISTORICAL_BARS` | IBKR is authoritative; Finviz day-change is display-only fallback |
| `completed_bar_acceleration` | IBKR (computed from bars) | `HISTORICAL_BARS` | |
| `catalyst_age_hours` | Computed: news + SEC `filed_at` | `NEWS` / `FILINGS` | SEC EDGAR needs no key; fair-access limits apply |
| `borrow_availability_pct_float` | IBKR + Finviz (both legs required) | `SHORTABLE_SHARES` + `FLOAT` | One provider's indicative figure ≠ whole market (handoff §12) |
| `borrow_fee` | IBKR (secondary) | `BORROW_FEE` | See G1 — the live-retrieval adapter is a placeholder |
| Historical OHLCV bars | IBKR (`intake/local-bars/ibkr-batch-*`) | `HISTORICAL_BARS` | Backbone of the Phase 3E/3F cohort (29 symbols, 48-entry registry = 36 historical case boundaries + synthetic/blocked entries) |
| `news_headlines` | NewsAPI, Finnhub News, RSS | `NEWS` | Feed order is configurable (`NEWS_PROVIDER_ORDER`) |
| SEC filings metadata | SEC EDGAR | `FILINGS` | `filed_at` feeds catalyst age |
| Halts | halts adapter | `HALTS` | Supplemental evidence |
| Sentiment | Local ProsusAI FinBERT (`SENTIMENT_PROVIDER=local_finbert`) or keyword | `SENTIMENT` | Local model; `MIXED` only as an aggregate label |

### 3B. Partial or absent (the gaps the causal model actually reports)

| Causal field | Status today | Missing-capability key | Why it is a gap |
|---|---|---|---|
| `borrow_utilization_velocity` | Not admitted from any provider | `borrow_utilization_velocity` | The IBKR Borrow Fee adapter is a placeholder (no live retrieval verified); the evaluator removes this key only when a governed lending snapshot supplies the field |
| `shares_on_loan_delta` | Not admitted from any provider | `shares_on_loan_delta` | Same root cause as utilization velocity — needs a governed lending snapshot time series |
| Lending snapshot (`lending_fee_rate`, `lending_shares_available`, `lending_utilization_rate`, `lending_shares_on_loan`) | Cross-lane contract only | (sets `lending_available`) | No admitted provider yet; consumed via `cross_lane` when the platform or acquisition track publishes it |
| `order_flow_cvd` (CVD slope, aggressive buy/sell) | Cross-lane contract only | `order_flow_cvd` | Owned by the **Order Flow lane** (spec §14); absent in standalone screener mode |
| `options_dealer_positioning` (gamma, hedging pressure, flow reversal) | Cross-lane contract only | `options_dealer_positioning` | Owned by the **Options lane** (spec §14); absent in standalone screener mode |
| Horizon probabilities P(1/3/5/10/20d) | `RESEARCH_ONLY` null slots | (status, not a key) | Model capability, not a provider field — needs walk-forward calibration (roadmap Phase 4) |
| ShortPainDistribution (entry-price distribution) | No field, no provider | (not a key) | Needs an entry-price inference method plus adjudication (spec §19.3, §20) |
| Fails-to-deliver balances | **No adapter, no collector anywhere in the pipeline** | (not a key) | Un-sourced; relevant to spec §5 — never merge into SI even if acquired |
| SEC threshold list / forced-cover countdown | **No adapter, no collector** | (not a key) | Un-sourced; spec §5: threshold list ≠ forced-cover countdown |
| Cross-exchange crypto liquidation mapping | None | (not a key) | Explicitly out of scope until the US-equity baseline is calibrated (spec §20) |

### 3C. Collected but never scored (display-only / inadmissible)

| Field | Provider | Admissibility | Why it stays out |
|---|---|---|---|
| `finra_daily_short_volume` | FINRA CNMSshvol (`FinraDailyVolumeCollector`) | `RESEARCH_INADMISSIBLE` | `FINRA_DAILY_SHORT_VOLUME_NOT_SUPPORTED` (finra adapter validation); spec §5: daily short volume ≠ outstanding short interest |
| Estimated DTC from Short Float / Avg Volume | Computed proxy | `DISPLAY_ONLY` | Proxy, not a published DTC |
| Finviz day-change (when IBKR `PERCENTAGE_RETURN` missing) | Finviz Elite | `DISPLAY_ONLY` | Fallback rendering only |
| `yfinance_news` / `yfinance_quote` | yfinance collector | `RESEARCH_INADMISSIBLE` | Supplemental display; not in the admissible pipeline |

## 4. Cross-lane ownership (spec §14)

The squeeze lane **consumes** normalized evidence; it never collects or owns these:

| Evidence group | Owner lane | Entry path |
|---|---|---|
| CVD / aggressor flow | Order Flow | `cross_lane.order_flow_*` |
| Gamma / dealer positioning | Options | `cross_lane.options_*` |
| Utilization / shares-on-loan | Governed lending provider (acquisition track) | `cross_lane.lending_*`, `borrow_utilization_velocity` |
| Attention acceleration | Attention / market context | `cross_lane.attention_*` |
| Catalyst strength / thesis invalidation | Market context | `cross_lane.catalyst_*`, `thesis_invalidation_score` |

All of it enters through `src/squeeze_core/intelligence/cross_lane.py`, which is
the only sanctioned bridge (spec §14; roadmap track C). When a lane is not
publishing, the corresponding `missing_capabilities` key stays populated — the
evaluator never invents the evidence.

## 5. Gap register

| ID | Gap | Owner | Prerequisite | Closure path | Spec / roadmap ref |
|---|---|---|---|---|---|
| G1 | `borrow_utilization_velocity` / `shares_on_loan_delta` / lending snapshot | Data acquisition | Verify a governed lending feed (IBKR borrow API mechanism, or commercial lending-data provider) and its PIT semantics | Admit the fields through the same admissibility pipeline as existing fields; the evaluator already flips the missing keys off when the snapshot is supplied (`evaluator.py` lending branch) | §19.2; roadmap Phase 7 |
| G2 | `order_flow_cvd` | Order Flow lane | Lane publishes normalized CVD evidence | Platform live-wiring so the donor bridge stops degrading to fixtures (roadmap track C) | §14 |
| G3 | `options_dealer_positioning` | Options lane | Lane publishes normalized dealer-positioning evidence | Same as G2 | §14 |
| G4 | Horizon probabilities | Model calibration | 48-entry labeled registry + mechanism-class adjudication | Walk-forward harness producing `HorizonModelSnapshot(status=CALIBRATED, pit_verified=True)` | §9, §11–13; roadmap Phase 4 |
| G5 | ShortPainDistribution | Research | Entry-price inference method + adjudication | Separate research track; de-scope explicitly until method exists | §19.3, §20 |
| G6 | Recall observability | Research | Define recall window + labeling pipeline | Missed-event labeling so recall is measurable, not just precision | §20 |
| G7 | FTD / threshold list | Decision: acquire vs de-scope | Source identification (SEC/FINRA FTD feeds; exchange threshold lists) | If acquired: separate fields with their own admissibility, never conflated with SI | §5 |
| G8 | Crypto liquidation mapping | Explicitly de-scoped | US-equity baseline calibrated (Phase 4 complete) | Revisit only after Phase 4 | §20 |

**Explicit non-gaps.** Batch 07 `PRICE_RANGE` blocking on detection-evaluability
(ADR-0067) is a bar/semantics issue, not a provider capability gap — it is tracked
separately in roadmap track B and is not fixed by adding providers. Frozen-demo
operation (`FROZEN_SNAPSHOT_NO_LIVE_TRANSITIONS`) is a mode property, not a
capability gap.

## 6. Closure policy

A row flips from gap to available only when all of the following hold:

1. **Admissible:** the field passes unit, time-basis, provenance, and freshness
   requirements (`RESEARCH_ADMISSIBLE`, per [PROVIDERS.md](../PROVIDERS.md)).
2. **Point-in-time correct:** `event_time` / `available_time` / `ingested_time`
   and publication-lag rules are honored (spec §6) — a revised float or SI is
   usable only after its `available_time`.
3. **Honest:** missingness is reported as `UNKNOWN` / `NOT_SUPPORTED` /
   `RESEARCH_INADMISSIBLE`, never synthesized (ADR-0047).
4. **Visible:** the evaluator's `missing_capabilities` and the explanation graph's
   "Missing capabilities" node stop listing the key only when real evidence
   arrived — not when an adapter exists (probe registry tracks actual results,
   not code presence).
5. **Documented here and in `docs/PROVIDERS.md`:** both the design-time matrix and
   the reference doc are updated in the same change.

## 7. How to update

- **New provider or entitlement change:** run the probe path, update
  `apps/research_screener/provider_capabilities.py` statuses, then sync §3A–3C.
- **New causal field:** add a §3B row with its `missing_capabilities` key (or note
  if it has none), an owner, and a spec reference — before wiring it into the
  evaluator.
- **Gap closed:** move the row from §3B to §3A, note the closure artifact in the
  register, and record it in the roadmap's Phase 7 table.

## Revision history

| Date | Change |
|---|---|
| 2026-09-05 | Initial matrix; closes the link from [SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md](SHORT_SQUEEZE_CAUSAL_RESEARCH_SPEC.md) §7 |
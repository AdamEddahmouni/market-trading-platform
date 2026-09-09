# Phase 4 — Reference cost set addendum (open item O-4)

**Status:** DRAFT — written before any Phase 4 fitting; **pending owner confirmation**
(open item O-4 in the
[Phase 4 calibration preregistration](phase-4-calibration-preregistration.md)).
EV reporting must not start until this addendum is confirmed.
**Version:** `phase_4_cost_set_addendum.v0.1-draft`

## 1. Not-tuned / outcome-blind statement

The cost values below are a **reference cost set fixed before any fit**: they were
chosen from public market-structure references and from conservative engineering
judgment about the cohort's securities (micro/small-cap, sub-$2B float names), **not
by inspecting outcome labels, not by tuning on held-out performance, and not to make
EV look favorable or unfavorable**. The point of fixing them here is precisely that
they are *not* a modeling output: EV is a reporting lens with explicit assumptions,
not a result the model optimizes.

Any amendment to this addendum (owner-specified values, or a change of reference
position model) must be recorded in the revision history **before** any fit that would
use it, and must itself be outcome-blind.

## 2. Reference position model (fixed, reporting-only)

EV is computed for a single, deliberately simple reference position:

- **Instrument:** the candidate equity, long.
- **Size:** 1× cash notional; no margin, no leverage, no options.
- **Entry:** at the **boundary close** — the close of the first eligible trade bar at
  or after the detection boundary
  (`first_eligible_trade_bar_close_at_or_after_boundary.v1`, the same rule the
  outcome observations use).
- **Exit:** at the **first close ≥ +25%** relative to entry within the 24-hour
  forward window when the detection event occurs (win); otherwise at the **final close
  of the 24-hour forward window** (loss). This mirrors the pre-registered outcome
  definition (§3 of the preregistration) exactly — EV never invents a second exit rule.
- **Holding period:** ≤ 24 hours. No overnight financing, no margin interest, no
  borrow fee (a long position borrows nothing).
- **No position sizing, no stops, no partial exits, no portfolio context.** EV is a
  per-trade reference quantity reported at the pre-registered operating point of §9.

This model is chosen because it is the *minimal* position consistent with the owned
outcome data. The outcome observations structurally cannot hold fills, entries, exits,
P&L, or commissions ([outcome-observation-semantics.md](outcome-observation-semantics.md)
§2); EV therefore computes its win/loss magnitudes from **observed window returns and
held-out model probabilities**, combined with the fixed cost set below — it never
reads a fill or a trade record.

## 3. The reference cost set

Costs are expressed as **percent of notional, per side**, and applied on both entry
and exit (round trip = 2 × per-side total). All values are reference defaults for the
owner to confirm or amend in the revision history.

| # | Cost component | Reference value (per side) | Rationale / citation |
|---|---|---|---|
| C01 | Commission | **0.50% of notional** | Conservative stand-in for retail paid-for-order-flow economics on low-priced micro-caps (SEC [Rule 606 disclosure reports](https://www.sec.gov/divisions/marketreg/rule606info.htm)); $0.00–$0.005/share flat fees are typical for liquid names but inadequate for these securities. 0.50% ≈ $0.05 on a $10 stock, a conservative all-in order-cost allowance |
| C02 | Slippage / market impact | **0.50% of notional** | Impact for small-cap, low-float names is materially larger than for liquid large caps; 0.50% per side is a conservative default (academic estimates of small-cap implementation shortfall commonly range 0.1%–1%+ per side; e.g. Almgren et al., *Direct Estimation of Equity Market Impact*, 2005, reports impact rising sharply with trade size and decreasing liquidity) |
| C03 | Financing / borrow | **0.00%** | Long, 1× cash, ≤ 24 h holding → no margin interest, no borrow fee, no short rebate. A short or leveraged variant is **not** part of this reference set; if one is ever reported, it requires its own pre-registered cost values, not a tuning of these |
| C04 | Market data / connectivity | **0.00%** | Infrastructure cost is not a per-trade cost of the signal; reported separately if the owner ever wants a total-cost-of-signal figure |

Round-trip reference cost = `2 × (C01 + C02)` = **2.00% of notional**, fixed.

## 4. EV expression under the reference set

Reported at the pre-registered operating point (preregistration §9), on **held-out
evaluation folds only**:

```
EV = P(win) × E[win] − P(loss) × E[loss] − costs
```

with, under this addendum:

- `P(win)`, `P(loss)` — calibrated occurrence probabilities from the held-out folds
  at the pre-registered operating point (never training-fold probabilities);
- `E[win]` — mean observed window return at the +25% crossing close for event rows
  (data quantity, reported from held-out observations);
- `E[loss]` — mean observed 24-hour window-end return for non-event rows (data
  quantity, reported from held-out observations);
- `costs` = **2.00%** (round-trip, §3).

`E[win]` and `E[loss]` are **measured from the data, not tuned**; the only
owner-specified quantities are the costs in §3. If `E[win]`, `E[loss]`, or the event
counts are unavailable for a fold (degenerate fold, §7 of the preregistration), EV for
that fold is reported as `UNAVAILABLE`, never imputed.

## 5. Reporting constraints (carried from §9 and the outcome semantics)

- EV is **reporting-only**: it is never used to tune thresholds, to select operating
  points, to rank models, or to claim backtest/P&L validity (spec §17;
  `Signal ≠ decision ≠ execution`).
- EV is reported **only** under this pre-registered reference cost set; any other cost
  assumption would be a different addendum.
- Every EV report carries the base rate and event counts alongside it, and the
  `COUNTERFACTUAL_EXPLORATION_ONLY` / `SMALL_SAMPLE_WARNING` /
  `NO_THRESHOLD_AUTO_PROMOTION` framing (preregistration §9).
- Nothing here authorizes live trading, live signal promotion, or threshold changes
  ([LIMITATIONS.md](LIMITATIONS.md), ADR-0047, ADRs 0065/0067/0068).
- No EV number is ever written into an outcome observation or any serialized evidence
  record — the outcome schema has no field for it (outcome-observation-semantics §2).

## 6. Re-derivation rule

If the owner changes the reference position model (e.g. adds a short leg, leverage, or
a multi-day horizon), the new cost values are derived by the same rule — fixed
**before** the fit that uses them, recorded in the revision history, and never tuned
on outcomes. Defaults under this addendum remain in force for the long, 1× cash, ≤ 24 h
reference position until amended.

## Revision history

| Date | Change |
|---|---|
| 2026-09-05 | Initial draft (v0.1): reference cost set (commission 0.50% + slippage 0.50% per side, round-trip 2.00%; financing 0.00% for the long 1× cash ≤24 h reference position), fixed EV expression and reporting constraints; outcome-blind; pending owner confirmation (O-4) |
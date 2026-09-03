# Options Glossary (Deliverable 11 partial — glossary component)

**Status:** Canonical terminology for Options lane redesign  
**Date:** 2026-08-18

Terms marked **WHAT THIS DOES NOT MEAN** clarify common misconceptions enforced by platform policy.

---

## Contract mechanics

| Term | Definition | What this does NOT mean |
|---|---|---|
| **call** | Right to buy underlying at strike before/on expiration | Not inherently bullish positioning |
| **put** | Right to sell underlying at strike before/on expiration | Not inherently bearish positioning |
| **strike** | Exercise price of the option | Not a price forecast |
| **expiration** | Last date/time option can be exercised (style-dependent) | Not the only date P&L matters (path-sensitive) |
| **DTE** | Days to expiration | Not linear in risk — 0DTE is a distinct regime |
| **moneyness** | Strike relative to underlying (spot, forward, or delta) | Not the same across coordinate systems |
| **American exercise** | Exercise any time before expiration | Not always optimal to hold to expiry |
| **European exercise** | Exercise only at expiration | Not the only style for US equity options |
| **intrinsic** | max(S−K,0) calls; max(K−S,0) puts | Not total option value |
| **extrinsic** | Option price minus intrinsic (time + vol value) | Not "free" — carries theta risk |
| **assignment** | Short option holder obligated to fulfill | Not automatic at any ITM — rules apply |
| **exercise** | Long holder invokes right | Not always rational (extrinsic remaining) |
| **open interest** | Count of open contracts | **Not** bullish/bearish — every contract has long and short side |
| **volume** | Contracts traded in period | **Not** signed flow or direction without initiation data |

---

## Greeks

| Term | Definition | What this does NOT mean |
|---|---|---|
| **delta** | ∂V/∂S — sensitivity to underlying move | **Not** physical real-world probability of expiring ITM |
| **gamma** | ∂²V/∂S² — delta sensitivity | Not dealer gamma without participant data |
| **theta** | ∂V/∂t — time decay | Not constant — accelerates near expiry |
| **vega** | ∂V/∂σ — sensitivity to implied vol | Not equal to vol risk premium |
| **rho** | ∂V/∂r — rate sensitivity | Not dominant for short-dated equity options |
| **vanna** | ∂delta/∂σ | — |
| **charm** | ∂delta/∂t | — |

---

## Volatility

| Term | Definition | What this does NOT mean |
|---|---|---|
| **implied volatility (IV)** | Volatility that equates model price to market price | **Not** unbiased forecast of realized vol |
| **realized volatility (RV)** | Historical volatility from observed returns | Not interchangeable with IV |
| **volatility risk premium** | E[IV − RV] (conditional) | **Not** automatic "sell vol" signal |
| **surface** | σ(K,T) across strikes and expirations | Not a single ATM number |
| **skew** | IV variation across moneyness | Not constant directional bias |
| **smile** | Skew curvature across strikes | — |
| **term structure** | IV variation across expirations | Not always upward sloping |
| **IV crush** | Post-event IV decline | Correct direction can still lose on long options |

---

## Distributions

| Term | Definition | What this does NOT mean |
|---|---|---|
| **physical distribution (P)** | Real-world forecast of future prices/returns | Not what options "imply" |
| **risk-neutral distribution (Q)** | Market-implied distribution from option prices | Not physical probability |
| **P vs Q** | Comparison of forecast vs market-implied | **Not** automatic arbitrage — risk premia exist |
| **option edge** | Executable disagreement between P and Q after costs | Not "bullish" or "high IV" alone |

---

## Flow and positioning

| Term | Definition | What this does NOT mean |
|---|---|---|
| **signed flow** | Initiator-classified buy/sell pressure | Not raw call/put volume |
| **opening flow** | New position creation | Not known without open/close flag |
| **closing flow** | Position reduction | Not known without open/close flag |
| **dealer gamma** | Market maker net gamma exposure | **Not** equal to −OI × gamma without evidence |
| **gamma exposure (GEX)** | OI-weighted gamma proxy | **Not** proven dealer position — use "estimated" |
| **gamma flip** | Price level where net gamma changes sign | Model-dependent; include confidence |
| **hedging pressure** | Estimated dealer hedge flow needed | Must be validated against order flow |

---

## Strategies (economic exposure)

| Term | Definition |
|---|---|
| **vertical** | Same expiry, different strikes |
| **calendar** | Same strike, different expiries |
| **straddle** | Long call + long put, same strike/expiry |
| **strangle** | Long OTM call + long OTM put |
| **risk reversal** | Long call + short put (or reverse) — skew exposure |
| **butterfly** | Limited risk skew/curvature expression |
| **collar** | Long put + short call against stock |

---

## Platform-specific

| Term | Definition | What this does NOT mean |
|---|---|---|
| **confirmation_score** | Phase 11 per-event unusual-activity blend | **Not** the terminal Options lane output; not universal score |
| **NO_CLEAR_EDGE** | Valid optimizer outcome | Not a failure — often correct |
| **TheoreticalEdge** | Model mispricing before costs | Not tradable without ExecutableEdge |
| **ExecutableEdge** | Edge after spread, slippage, fees | Not guaranteed fill at mid |
| **estimated_gamma_exposure** | OI×gamma proxy with method tag | **Not** "dealer gamma" |

---

## Cross-lane terms (Options ↔ Short Squeeze)

| Term | Owner | Consumer |
|---|---|---|
| **squeeze_state** | Short Squeeze | Options (P feature) |
| **ignition_strength** | Short Squeeze | Options (tail forecast) |
| **remaining_squeeze_fuel** | Short Squeeze | Options (duration) |
| **call_demand_anomaly** | Options | Short Squeeze (ignition) |
| **gamma_amplification_potential** | Options | Short Squeeze (reflexivity) |
| **implied_upside_tail_probability** | Options | Short Squeeze (priced-in check) |

---

## Related documents

- `OPTIONS_TARGET_ARCHITECTURE.md`
- `SHORT_SQUEEZE_GLOSSARY.md`
- `ADR-WHALE-004` (direction ambiguity)

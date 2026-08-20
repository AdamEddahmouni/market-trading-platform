# Participant Intelligence — Research Plan (Deliverable 8)

**Default hypothesis:** Swim With the Whales is **conditional**, not universal.

```text
SwimWithWhales ONLY WHEN
  mechanism ∈ {INFORMED, STRATEGIC, PERSISTENT_MECHANICAL}
  AND copyability remains positive after delay/costs
```

---

## Model ladder (W0–W11)

| Level | Features | Status |
|---|---|---|
| W0 | No participant features | Baseline |
| W1 | Raw disclosure / large trade | Whale Phases 9–12 |
| W2 | + participant type | **PI1** |
| W3 | + action semantics | **PI2** |
| W4 | + relative size / commitment | PI3–PI4 |
| W5 | + freshness / horizon | PI9 |
| W6 | + walk-forward participant skill | PI5 |
| W7 | + mechanism + alternatives | PI7 |
| W8 | + liquidity / impact (from OF) | PI6 |
| W9 | + Market Context timing | PI8 |
| W10 | + Order Flow metaorder | PI6 + OF11 |
| W11 | + cross-lane alignment | PI10 |

Retain complexity only with incremental OOS benefit.

---

## Follow hypotheses (alignment research)

| ID | Participant type | Mechanism | Horizon | Evaluation |
|---|---|---|---|---|
| F-INS-01 | Insider discretionary open-market buy | INFORMED | 20–60d post-`available_time` | CAR vs matched control |
| F-ACT-01 | 13D initiation | STRATEGIC | 60–252d | Activist objective success |
| F-13F-01 | New 13F position | PORTFOLIO_ALLOCATION | 60d post-filing | Delay-adjusted alpha |
| F-META-01 | Active metaorder buy | MECHANICAL | minutes–hours | Continuation vs OF baseline |
| F-CON-01 | Cross-participant alignment | MIXED | strategy-dependent | W11 ablation |

## Fade hypotheses (contrarian research)

| ID | Condition | Mechanism | Evaluation |
|---|---|---|---|
| FD-FORCE-01 | Forced-flow probability high + no catalyst | FORCED | Post-flow reversal |
| FD-META-01 | Metaorder LIKELY_COMPLETE | MECHANICAL | Post-execution decay |
| FD-INS-01 | Insider 10b5-1 sale cluster | COMPENSATION | No short signal |
| FD-13F-01 | Stale 13F + price +40% vs filing | PASSIVE | Underperformance of copy |

---

## Skill estimation (PI5)

- Separate: buy_skill, sell_skill, sector_skill, horizon_skill, activism_success
- Walk-forward only; Bayesian shrinkage; minimum sample gates
- Never label permanently "smart money"

## Copyability metrics (PI9)

Compare:

1. Participant gross return
2. Public follower return (at `available_time`)
3. Cost-adjusted follower return

---

## Cross-lane experiments

| ID | Question | Lanes |
|---|---|---|
| PI-Q1 | Does discretionary insider buy + Context improvement beat insider alone? | PI + MC |
| PI-Q2 | Does metaorder probability improve short-horizon continuation beyond OFI? | PI + OF |
| PI-Q3 | Does large-buyer persistence improve squeeze ignition? | PI + SS |
| PI-Q4 | Does participant disagreement predict IV expansion? | PI + Options |
| PI-Q5 | Does participant crowding improve liquidation prediction? | PI + Futures |
| PI-Q6 | Pre-catalyst unexplained accumulation → future news? | PI + MC |

---

## Validation requirements

- Chronological walk-forward; no random shuffle of participant events
- Disclosure delays enforced in all copy strategies
- Survivorship: include failed funds/activists where data exist
- Break down by participant type, mechanism, horizon, regime
- Report Brier/log loss for skill models; CAR/Sharpe for follow/fade

---

## Research status

| Capability | Status |
|---|---|
| PI1 identity contracts | IMPLEMENTED |
| PI2 action contracts + disclosure bridge | IMPLEMENTED |
| PI3 public equity disclosures (rich) | EXPERIMENTAL |
| PI5 skill | UNAVAILABLE → fixture scope | **IMPLEMENTED** (fixture) |
| PI6 metaorder | UNAVAILABLE (blocked OF11) | **IMPLEMENTED** (fixture) |
| PI7 mechanism engine | EXPERIMENTAL (schema only) |
| PI9 copyability | UNAVAILABLE → fixture scope | **IMPLEMENTED** (fixture) |
| PI14 crypto | NOT_AUTHORIZED |

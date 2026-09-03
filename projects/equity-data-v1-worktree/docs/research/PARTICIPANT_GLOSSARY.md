# Participant Intelligence Glossary

Canonical definitions for Participant / Whale Intelligence. See `SWIM_WITH_THE_WHALES.md` for the eight legacy evidence families.

---

## Core terms

**Participant** — Any economic actor whose actions may contain information, strategic influence, mechanical impact, forced flow, or reflexive effects. Broader than "whale."

**Whale** — UI shorthand only. Architecturally means **participant-scale** behavior relative to liquidity, float, ADV, OI, or participant history — not a universal dollar threshold.

**Participant identity** — Resolved entity with `participant_id`, type, confidence tier, and resolution method. Never invented from anonymous flow.

**Institutional-scale flow** — Large relative to market depth/ADV without attributable identity. `ANONYMOUS_INSTITUTIONAL_SCALE`, not a named fund.

**Metaorder** — Inferred parent execution from persistent child flow. Order Flow owns primitives; Participant Intelligence interprets lifecycle states probabilistically.

**Copyability** — Whether a follower can still capture edge after delay, price move, liquidity, horizon mismatch, and costs. Separate from participant skill.

**Entry quality** — Current price vs participant basis and remaining opportunity. A skilled participant may have a bad copy entry.

**Participant skill** — Out-of-sample historical performance conditional on action type and context. Shrunk; decays; never a universal smart-money score.

**Mechanism** — Plausible causal explanation: informed, strategic, mechanical, forced, hedging, passive, reflexive. Multiple alternatives may coexist.

**Research classification** — Evidence label (e.g. `ALIGNMENT_CANDIDATE`, `POST_FLOW_CONTRARIAN_CANDIDATE`). Not an order.

---

## Disclosure terms

**13D** — Activist beneficial ownership. Strategic influence research; not automatic buy signal.

**13G** — Passive large ownership context. Not conviction.

**13F** — Quarterly manager holdings snapshot. `quarter_end ≠ available_time`. Long-only; incomplete exposure.

**Form 4** — Insider transaction. Must distinguish open-market vs grant/exercise/tax.

**10b5-1** — Pre-planned sale/purchase program. Reduces informational weight of sales.

---

## What this does NOT mean

| Statement | Truth |
|---|---|
| Large trade → informed | **False** — may be mechanical, hedge, rebalance |
| Large ownership → bullish | **False** — may be passive, index, hedge |
| 13F long → net bullish | **False** — shorts/hedges omitted |
| Large call → bullish whale | **False** — may be spread/hedge/close |
| Commercial futures short → bearish | **False** — often hedge |
| Crypto transfer → sell | **False** — may be custody reshuffle |
| Whale buying → we should buy | **False** — check mechanism + copyability |
| Institutional → skilled | **False** — skill is empirical and conditional |
| Many whales → independent consensus | **False** — check affiliation/index tracking |

---

## Swim With the Whales (mature definition)

```text
FOLLOW when informative / strategic / persistently mechanical
  AND copyability remains positive.

IGNORE when passive / ambiguous / stale / hedging-driven.

FADE when forced / temporary mechanical dislocation is recoverable.

USE AS CONTEXT when participant matters but cannot support standalone thesis.
```

Empirical research determines which cases work — the platform does not assume whales are right because they are large.

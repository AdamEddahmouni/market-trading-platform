# NOW — Market Command Center

**Status:** `PROPOSED`

## Purpose

Answer: **What deserves my attention right now?**

The homepage is not a collection of every module. Scarce resource = user attention.

## Layout (wireframe summary)

See [wireframes/01-now-command-center.md](wireframes/01-now-command-center.md).

```
┌─ CONTEXT BAR ─────────────────────────────────────────────────┐
├───────────────────────────────────────────────────────────────┤
│ MARKET REGIME (compact)     │ DATA HEALTH (if not GOOD)       │
├─────────────────────────────┴─────────────────────────────────┤
│ ATTENTION FEED (ranked, state-change first)                   │
│ ┌─ Card ─────────────────────────────────────────────────┐   │
│ │ NVDA — WATCH → CONFIRMED                    2m ago      │   │
│ │ Changed: CVD threshold, large-buy ↑, offer consumed     │   │
│ │ Unchanged: options ambiguous                              │   │
│ │ [Why is this here?] [Open] [Explain transition]         │   │
│ └─────────────────────────────────────────────────────────┘   │
│ ┌─ Card ─────────────────────────────────────────────────┐   │
│ │ SYSTEM — CVD quality PARTIAL on 3 watchlist symbols     │   │
│ └─────────────────────────────────────────────────────────┘   │
├───────────────────────────────────────────────────────────────┤
│ WATCHLIST PULSE (compact — not full screener)                 │
└───────────────────────────────────────────────────────────────┘
```

## Attention Priority

Separate from trade score, bullishness, squeeze probability, model probability.

### Ranking inputs (illustrative weights — NEEDS DECISION)
| Factor | Examples |
|---|---|
| State transition | WATCH→CONFIRMED, risk breach |
| Magnitude | Unusual vs baseline |
| Novelty | First occurrence in session |
| Acceleration | Rate of change increasing |
| Watchlist relevance | User lists |
| Position relevance | Open exposure (future) |
| Risk proximity | Near stop/limit (future) |
| Catalyst proximity | Earnings, filing |
| Data failure | Quality degradation |

### "Why is this here?" response
Structured reason codes:
```
ATTENTION_REASONS:
  - state_transition:squeeze_watch_to_confirmed
  - magnitude:rel_volume 3.4x
  - watchlist:default
  - position:none
```

Never display as opaque rank score to user by default. Optional sort indicator only.

## Alert architecture

Alerts are state-transition-first. Every alert answers:

1. What changed?
2. Why does it matter?
3. When?
4. What evidence supports it?
5. What remains uncertain?
6. What can I inspect next?

### Deduplication
- Group by instrument + transition type within time window
- Escalate only on new information
- Risk events bypass deduplication (Tier 1)

## What NOW excludes

- Full DOM, option chains, model dashboards
- Dense tables (link to WORKSPACE)
- Historical research tools

## Mobile NOW

Subset: attention feed, regime one-liner, tap-through to instrument overview + 30-second explanation path. See [mobile-strategy.md](mobile-strategy.md).

## Current capability honesty

At Phase 5 boundary, NOW can show:
- Bar-derived feature state changes on admitted fixture
- Quality/data-health problems
- Institutional modules as `UNAVAILABLE` with explanation (not fake data)

Cannot show live order flow, options flow, or squeeze confirmations until entitled sources exist.

## "What matters" card template

```
LARGE BUYING PRESSURE

3.4× recent normal

Observed:
Aggressive large-trade participation increased.

Interpretation:
Supports bullish flow hypothesis.

Quality: Good
Updated: 2 sec ago

[Explain]
```

Progressive disclosure: not every field visible on card face.

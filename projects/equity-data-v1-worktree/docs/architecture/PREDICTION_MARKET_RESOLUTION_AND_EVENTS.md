# Prediction Market Resolution and Events

**Status:** `PROPOSED` — future architecture guidance

**Authority:** Subordinate to Revision 3 and
[2026-08-16-prediction-markets-expansion-design.md](../superpowers/specs/2026-08-16-prediction-markets-expansion-design.md)

## Purpose

Resolution semantics are first-class data. Understanding what is actually being bet
on is as important as price. Two markets with similar titles may have non-equivalent
settlement semantics.

## Resolution rule versioning

Never overwrite historical rules when they change.

`ResolutionRuleVersion`:

```text
effective_at
observed_at
content_hash
source
rules (full text or structured extraction)
amendment_type (if applicable)
```

Store: full question; full rules; primary resolution source; secondary source;
edge cases; deadline; timezone; early-close rules; dispute rules; amendments.

## Resolution semantic risk

`ResolutionSemanticRisk` states:

```text
LOW | MODERATE | HIGH | AMBIGUOUS
```

Example non-equivalence:

```text
Market A: "Will X happen by December 31?"
Market B: "Will X officially be announced before December 31?"
```

Cross-market strategies must account for semantic risk explicitly.

## Canonical real-world event mapping

`CanonicalRealWorldEvent` — multiple provider markets may reference one real-world
topic while retaining separate settlement semantics.

Entity resolution produces two distinct outputs:

```text
same_real_world_topic     — topical grouping
settlement_equivalent     — semantic equivalence (often false)
```

Example:

```text
Canonical Event: 2028 US Presidential Election
  ├─ Kalshi market A
  ├─ Kalshi market B
  ├─ Polymarket market A
  └─ Other venue
```

## Cross-market consistency

Related contracts may impose logical constraints:

- mutually exclusive outcomes (P(A)+P(B)+P(C) ≈ 1)
- nested thresholds (P(rate>5%) ≤ P(rate>4%))
- complementary YES/NO relationships
- conditional structures

`CrossMarketConsistencyEngine` flags impossible or economically inconsistent
probability structures. Opportunities require executable verification — not
midpoint comparison alone.

## Resolution-rule AI (non-authoritative)

```text
original rules
  → deterministic/structured extraction where possible
  → AI interpretation (summarize, diff, match)
  → human-review flag for ambiguity
```

LLM interpretation is not authoritative for settlement.

## Resolution amendment alerts

Alert type: `MARKET RULES CHANGED`

- what changed
- when observed
- potential position impact
- link to rule version history

Never silently recompute history using newer rules.

## Market uncertainty vs resolution uncertainty

| Type | Meaning |
|---|---|
| Outcome uncertainty | We do not know what will happen |
| Resolution uncertainty | We do not know how written rules will classify what happened |

Model and risk layers must not absorb resolution uncertainty into outcome noise.

## Integrity flags

May cause automatic strategy abstention:

```text
ACTOR_CONTROLS_OUTCOME
DIRECT_INFLUENCE_RISK
NONPUBLIC_INFORMATION_RISK
MARKET_INTEGRITY_RISK
```

Public-actor markets (what someone will say/do/attend) require special handling.
Trades by the controlling person are not ordinary whale intelligence.

## Event knowledge graph (conceptual)

```text
Actor → Statement → Policy Event → Prediction Markets / Assets
Prediction Market → Participants
Assets → Strategies
```

Implement storage pragmatically — graph database only when requirements justify.

## Research event ledger

Extend canonical event ledger joining:

```text
prediction market | news | social | filing | macro release
  | on-chain event | asset market reaction
```

Point-in-time joins only — no hindsight linkage.

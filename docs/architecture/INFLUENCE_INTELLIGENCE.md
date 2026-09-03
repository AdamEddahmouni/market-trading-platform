# Influence Intelligence Engine

**Status:** `PROPOSED` — future architecture guidance

## Purpose

Cross-asset subsystem to detect high-impact public information events, resolve
which assets they plausibly concern, measure market response, and learn
historically which actor/event/asset combinations produced repeatable effects —
for crypto, equities, sectors, and eventually other markets.

Influence is **not** a generic sentiment classifier. Do not hard-code individual
actors or asset pairs.

## Core pipeline

```text
PublicInfluenceEvent (observed)
    → Actor verification
    → Asset resolution (with ambiguity preserved)
    → Novelty assessment
    → Historical impact model
    → Current market reaction
    → Order-flow confirmation
    → Derivatives confirmation
    → On-chain context
    → Liquidity / spread / cost
    → Strategy (may abstain)
    → Risk
    → Execution simulation
```

## Influence sources (lawful public)

X, official blogs, company channels, press releases, livestreams, interviews,
YouTube, Reddit, public Telegram/Discord where lawful, regulatory and government
announcements.

Use official APIs where practical. Respect terms of service, licensing,
redistribution, API cost, and retention. Never bypass access controls.

## InfluenceActor registry

Immutable identity where possible — not username alone.

| Metadata | Purpose |
|---|---|
| platform, platform_user_id, current_handle | Identity stability across handle changes |
| verified_status (when meaningful) | Source trust context |
| category | executive, company, investor, regulator, protocol, media, … |
| assets_historically_associated | Empirical association, not assumption |
| historical_event_count | Sample size context |

Popularity alone does not imply market influence.

## PublicInfluenceEvent contract (conceptual)

```text
event_id, source, source_object_id, actor_id
published_at, first_observed_at, ingested_at, last_observed_at
content_hash, content_version, event_type
mentioned_entities, resolved_assets
sentiment, stance, novelty, ambiguity
engagement_snapshot (point-in-time, not final totals)
raw_reference, provenance, quality
```

## Edits, deletions, reposts

Preserve: first observed content; subsequent edits; deletion detection;
repost/quote/reply relationships; media changes when observable.

Research input: **what content was observable when the strategy could have reacted** —
not what the post says today.

## Event type taxonomy

`DIRECT_ASSET_MENTION`, `INDIRECT_ASSET_REFERENCE`, `ENDORSEMENT`,
`CRITICISM`, `PRODUCT_ANNOUNCEMENT`, `PURCHASE_DISCLOSURE`,
`SALE_DISCLOSURE`, `POLICY_STATEMENT`, `REGULATORY_STATEMENT`, `MEME`,
`IMAGE_OR_SYMBOL_REFERENCE`, `INTERVIEW_STATEMENT`, `REPOST`, `REPLY`

Not every event maps to positive/negative sentiment.

## Asset resolution

Resolve financial assets with explicit ambiguity:

| Reference | Resolution example |
|---|---|
| `DOGE` | Dogecoin — direct |
| `Tesla` | TSLA — company mapping |
| `Bitcoin` | BTC — direct |
| indirect product/sector | ambiguous — preserve multiple candidates |

Distinguish: direct asset mention; company mention; product mention; sector
implication; ambiguous reference. Do not invent mappings.

## Actor × asset effect model

Research abstraction:

```text
ACTOR × EVENT TYPE × ASSET × REGIME × HORIZON
```

Track: sample size; median/mean abnormal return; hit rate; return distribution;
volume/volatility response; MFE/MAE; reaction latency; effect decay; regime
dependence.

## Influence is not sentiment

Important dimensions: actor; asset; message type; novelty; direction; historical
impact; surprise; reach; engagement velocity; timing; market regime; existing
positioning.

A neutral factual statement from a highly relevant actor may matter more than a
highly positive post from an irrelevant user.

## Event-reaction engine

For each event, measure horizons where data quality supports them:

1s, 5s, 15s, 30s, 1m, 2m, 5m, 15m, 30m, 1h, 4h, 24h.

Measure: raw/abnormal return; volume; volatility; spread; depth; CVD; OFI;
funding; OI; liquidations; on-chain flows.

## Narrative engine (future)

Mentions per time unit; mention acceleration; unique authors; engagement velocity;
high-influence adoption; topic emergence; asset co-mentions; sentiment
distribution; novelty; bot/spam likelihood when supportable.

Raw mention counts are not naive buy signals.

## Pump-and-dump / manipulation risk

Explicit research/risk features: thin liquidity; concentrated ownership;
coordinated promotion; sudden mention spikes; low-quality accounts; abnormal
spread; severe slippage; parabolic movement; exchange fragmentation; suspicious
pre-event price movement.

Platform may output:

```text
ABSTAIN — Possible promotional/manipulation pattern.
Liquidity insufficient relative to expected size.
```

## Cross-asset and cross-market propagation

Study measured lead/lag: BTC → ETH → alts; NVDA → semiconductor basket; crypto
policy → BTC/ETH → crypto equities. Require empirical evidence — no assumed
propagation trees.

## Social API cost control

Prioritized actors/assets; event-driven queries; caching; deduplication; backfill
separate from live; explicit spend limits. Do not re-scrape stored immutable
events.

## Latency measurement

Record full chain:

```text
publication → provider availability → ingestion → classification
→ asset resolution → features → strategy → risk → order → fill
```

An event may have predictive value with **zero executable value** if the market
moves first. This distinction is mandatory.

## Engagement snapshots

If engagement is a feature, store snapshots at publication, +10s, +30s, +1m,
+5m, +15m. Reconstruct velocity honestly. Never use final likes/reposts for
historical prediction at early horizons.

## AI role

Classify semantics, resolve entities, summarize, detect ambiguity, explain.
LLM output is `MODEL` or `INFERRED` with provenance — never `OBSERVED`.
Prefer small models and rules on high-volume paths.

## Future contracts (conceptual)

`PublicInfluenceEvent`, `InfluenceActor`, `SocialEngagementSnapshot`,
`MarketReaction`, `EventStudyRun`, `NarrativeObservation`

## Prediction market integration (future)

Influence events may precede or coincide with prediction-market repricing:

```text
Public statement → Influence event → prediction-market probability change
  → sector / crypto / rates reaction
```

Prediction-market movement can confirm whether an information event is being
economically repriced — supporting evidence, not proof. See
[PREDICTION_MARKET_CROSS_ASSET_INTELLIGENCE.md](./PREDICTION_MARKET_CROSS_ASSET_INTELLIGENCE.md)
and [2026-08-16-prediction-markets-expansion-design.md](../superpowers/specs/2026-08-16-prediction-markets-expansion-design.md).

# On-Chain Data Feasibility Study Plan

**Status:** `PROPOSED` — not authorized until principal authorization

## Objective

Characterize on-chain data availability for **one chain first** — likely Bitcoin
or Ethereum depending on the first hypothesis (exchange flow vs DeFi vs whale
transfer).

Do not attempt every chain simultaneously.

## Source categories

| Category | Evaluate |
|---|---|
| Direct node/RPC | cost, finality, throughput, historical limits |
| Indexers | backfill depth, parser versions, uptime |
| Analytics providers | entity labels, methodology, label versioning, cost |

## Dimensions

- raw block/tx availability and lag
- token transfer decoding coverage
- DEX swap coverage (if Ethereum hypothesis)
- exchange deposit/withdrawal labeling quality
- historical backfill cost and time
- finality semantics for research policy
- label retroactivity policy
- licensing and retention

## Entity labeling feasibility

- which entity types are supportable with evidence
- confidence scoring availability
- unknown rate for large transfers
- policy for social-media-attributed wallets (default: reject or quarantine)

## Deliverables

1. `onchain_feasibility_report.json`
2. Chain selection recommendation with rationale
3. Finality policy recommendation for ADR-CHAIN-001
4. Entity labeling gap analysis for ADR-CHAIN-002
5. Cost estimate for minimum validating on-chain dataset

## Authorization required

Principal authorization for provider pricing review and any lawful test queries.

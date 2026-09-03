# On-Chain Intelligence Engine

**Status:** `PROPOSED` — future architecture guidance

## Purpose

Formal **On-Chain Intelligence Engine** operating independently from CEX market-data
adapters. Observes blockchain state and transfers; produces canonical on-chain
events with full provenance; feeds whale research, exchange-flow research, and
Market Story — without inventing participant identity.

## Raw object types

| Object | Key metadata |
|---|---|
| `Block` | chain ID, network, number, hash, timestamp, confirmations |
| `Transaction` | tx hash, block ref, first observed, finality state |
| `TokenTransfer` | token, sender, recipient, amount, USD value when derived |
| `NativeTransfer` | chain native asset movement |
| `ContractEvent` | contract, parser version, decoded fields |
| `DEXSwap` | pool, routing, slippage, venue protocol |
| `BridgeTransfer` | source chain, dest chain, bridge protocol |
| `WalletBalanceObservation` | address, asset, balance, observation time |

Every object binds: `chain_id`, `network`, `block_number`, `block_hash`,
`transaction_hash`, `block_timestamp`, `first_observed_at`, `confirmations`,
`finality_state`, `source`, `parser_version`, provenance, quality.

## Finality and reorganizations

Blockchain events are not immutable the instant they appear. Explicit states:

```text
SEEN → PENDING → CONFIRMED → FINALIZED
              ↘ REORGED
              ↘ FAILED
```

Chain-specific finality semantics are parameterized (e.g. Bitcoin confirmations
vs Ethereum finality). State changes preserve history — no silent rewrite.

Research and replay use the finality policy declared in the experiment manifest.
`first_observable_time` for strategies is at or after the declared observability
threshold, not block inclusion time unless policy explicitly allows earlier
observation with labeled uncertainty.

## Entity labeling layer

Separate **entity-attribution layer** — not mixed with raw transfers.

| Entity type (examples) | Label metadata |
|---|---|
| exchange, fund, protocol, treasury, bridge, market maker, project team, miner, validator, individual (when legitimately established), unknown | source, confidence, first_seen, last_verified, label_version, evidence |

Unknown remains unknown. Social media claims do not establish wallet identity.
Retroactive label updates preserve prior label versions for replay.

## Whale / large-wallet intelligence

Extend Swim With the Whales into crypto:

> Observe large, economically meaningful capital flows; verify what can be
> established; contextualize; determine whether market behavior confirms the
> flow; align only when complete evidence supports the hypothesis.

Features: large transfer, large DEX swap, exchange deposit/withdrawal, wallet
accumulation/distribution, stablecoin movement, dormant-wallet activation,
concentration change, entity-cluster activity.

**Size normalization** — no static dollar whale threshold. Context: asset
liquidity, circulating supply, market cap, ADV, historical transfer distribution,
wallet holdings, exchange flow distribution.

## Copy / follow research (research only)

Actor/wallet following is research-first, not automatic copying.

Question: Does following this actor **after information becomes observable to us**
produce net-of-cost value?

Use `first_observable_time`, not `actor transaction time`, unless the platform
could have known at that time.

## DEX intelligence (longer-term)

Swaps, pool changes, LP add/remove, slippage, pool imbalance, routing,
cross-DEX price differences. DEX liquidity never merged with CEX without
explicit derived layer labeling.

## Future contracts (conceptual)

`ChainEvent`, `TokenTransfer`, `EntityLabel`, `WalletObservation`,
`ExchangeFlowObservation`, `FinalityStateRecord`

## Tests (future)

- duplicate transaction handling
- chain reorg and state transition
- missing block recovery
- incorrect label quarantine
- retroactive label update with version history
- observability vs inclusion time leakage sentinels

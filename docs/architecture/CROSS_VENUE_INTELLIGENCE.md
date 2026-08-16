# Cross-Venue Intelligence

**Status:** `PROPOSED` — future architecture guidance

## Purpose

Future **Cross-Venue Engine** studies price dispersion, spread differences,
book imbalance, liquidity and volume differences, lead/lag relationships,
cross-exchange price discovery, basis, funding differences, and arbitrage-like
dislocations — without assuming executable arbitrage.

## Principles

1. **Venue-native inputs preserved** — aggregation is derived, never primary.
2. **No fictional universal price** — BTC on Venue A ≠ BTC on Venue B without
   explicit cross-venue derived record.
3. **Executable arbitrage is a hypothesis** — research must account for fees,
   transfer delays, capital fragmentation, inventory constraints, rate limits,
   latency, withdrawal restrictions, and exchange counterparty risk.

## Study dimensions

| Dimension | Examples |
|---|---|
| Price dispersion | cross-venue spread at matched timestamps |
| Liquidity | depth at size, effective spread |
| Volume | venue share, acceleration |
| Lead/lag | Venue A move → delayed Venue B response |
| Basis | spot vs perp vs dated future per venue |
| Funding | cross-venue funding differentials |

## Research family (candidate)

**Cross-venue lead/lag:** measurable delayed response between venues after
realistic detection latency. Reject if required speed exceeds infrastructure.

## Counterparty / venue risk

Track venue status, deposit/withdrawal health, market-data and order API health,
custody model, and account balance exposure. Strategies cannot ignore venue
concentration.

## Future derived artifacts

Cross-venue dispersion snapshots, lead/lag estimates, and basis panels bind:
input venue set, timestamp alignment policy, fee assumption version, and
transfer-delay assumption — all versioned for replay.

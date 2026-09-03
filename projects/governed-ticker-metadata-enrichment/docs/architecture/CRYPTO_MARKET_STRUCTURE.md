# Crypto Market Structure

**Status:** `PROPOSED` — future architecture guidance

## Why crypto is not "stocks 24/7"

Traditional equity semantics assume consolidated tape, session boundaries,
central clearing, and relatively uniform tick/lot rules. Crypto markets violate
these assumptions routinely. The platform must represent structural differences
explicitly rather than silently mapping crypto into equity adapters.

## Structural dimensions

| Dimension | Crypto reality | Platform requirement |
|---|---|---|
| Trading hours | Continuous 24/7 (venue maintenance excepted) | UTC canonical accounting; explicit maintenance windows |
| Price discovery | Fragmented across many venues | Venue-native prices preserved; aggregation is derived |
| Order book | Venue-specific depth | No fictional universal book |
| Fees | Maker/taker tiers, venue-specific | Parameterized cost model per venue |
| Quote currency | USD, USDT, USDC, … | Explicit quote asset; stablecoin risk separate |
| Settlement | Blockchain finality vs internal ledger | Finality states; transfer delays for arb research |
| Derivatives | Perpetual funding, liquidations, mark/index | Separate event types and simulation |
| Leverage | Exchange-defined, varies | Risk limits per venue and instrument |
| Outages | Chain and exchange downtime | `ExchangeStatusEvent`; stale-data gates |

## Perpetual swaps

Perpetuals introduce funding payments, mark/index basis, open interest, and
liquidation cascades. These are not optional metadata — they affect P&L,
risk, and strategy evaluation.

Funding extremes, OI changes, and liquidation intensity are derivatives
intelligence inputs, not standalone buy signals.

## Stablecoins

Stablecoins are distinct instruments with depeg, liquidity, issuer, redemption,
and cross-venue dispersion risk. USD stablecoins are not cash equivalents in
risk modeling without explicit policy.

Stablecoin intelligence includes exchange inflows/outflows, issuance/redemption,
bridge activity, and supply migration — each as hypotheses requiring empirical
testing, not axioms (`issuance = buy` is forbidden).

## DEX vs CEX

Decentralized and centralized exchange liquidity must remain distinguishable in
provenance, capabilities, and simulation. DEX observations include swaps, pool
changes, LP add/remove, slippage, imbalance, routing, and cross-DEX dispersion.

## Token supply events

Cliff unlocks, vesting releases, treasury movements, emissions changes, and burns
are **event objects** with schedules and provenance — not buried in sentiment.
Research: pre/post returns, liquidity, volume, whale movement, derivatives
behavior around supply events.

## Protocol / token fundamentals

Where appropriate: circulating supply, emissions, inflation, unlock schedules,
staking, validator activity, fees, protocol revenue, TVL, active addresses,
transaction counts, governance, treasury, developer activity.

Not every token has equity-like fundamentals. Unsupported metrics remain
`UNAVAILABLE`.

## Exchange flow semantics

`ExchangeInflow`, `ExchangeOutflow`, `ExchangeNetflow` distinguish BTC, ETH,
stablecoin, and token flows.

**Forbidden assumptions:**

- `exchange inflow = sell`
- `withdrawal = buy`

These are testable hypotheses measured by asset, horizon, regime, venue, and
flow type.

## 24/7 operations implications

- Rolling daily risk windows and UTC accounting boundaries
- User-local presentation vs canonical UTC storage
- Maintenance period handling and restart behavior
- Always-on health monitoring
- Strategy availability schedules
- Explicit definition of "daily P&L" for crypto portfolios

See [CRYPTO_SIMULATION_AND_RISK.md](./CRYPTO_SIMULATION_AND_RISK.md).

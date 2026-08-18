# Cross-Lane Boundary Matrix (Deliverable 3 — extended 2026-08-18)

Extended for Options ↔ Short Squeeze ↔ Futures ↔ **Order Flow** cooperative redesign.

| Capability / Signal | Platform | Short Squeeze | Options | Futures | Order Flow | Crypto (future) | Prediction Mkt (future) |
|---|---|---|---|---|---|---|---|
| Point-in-time / provenance | **owner** | consumes | consumes | consumes | consumes | consumes | consumes |
| Physical distribution P | **shared** | consumes | major consumer | consumes | inputs | future | inputs |
| Risk-neutral distribution Q | contract | context | **owner** | partial | no | implied | implied prob |
| P vs Q edge decomposition | — | no | **owner** | no | no | future | partial |
| CVD / aggressor delta | infra | consumer | context | major consumer | **owner** | consumer | consumer |
| ClassifiedTrade / aggressor provenance | infra | consumer | consumer | consumer | **owner semantics** | consumer | consumer |
| Book imbalance / DOM | infra | consumer | context | major consumer | **owner semantics** | exchange-specific | owner |
| Microprice / queue imbalance | infra | context | context | consumer | **owner** | consumer | consumer |
| OFI / MLOFI | infra | consumer | context | consumer | **owner** | consumer | consumer |
| Liquidity withdrawal / replenishment | infra | consumer | context | consumer | **owner** | consumer | consumer |
| Book fragility / resiliency | infra | consumer | context | consumer | **owner** | consumer | consumer |
| Short-horizon microstructure forecast | shared contract | consumer | consumer | consumer | **major producer** | future | future |
| Execution forecast (fill, slippage) | **shared** | consumer | consumer | consumer | **major producer** | downstream | downstream |
| Depth imbalance interpretation policy | — | applies | applies | **contrarian (FuturesX)** | **raw ratio only** | venue-specific | — |
| Borrow utilization | infra | **owner** | optional context | N/A | N/A | funding/OI mechanism | N/A |
| Shares on loan | infra | **owner** | N/A | N/A | N/A | perp OI analog | N/A |
| Cost to borrow | infra | **owner** | carry input | N/A | N/A | funding rate | N/A |
| Published short interest | infra | **owner** | context | N/A | no | different definition | N/A |
| Daily short volume (FINRA) | infra | flow feature only | no | N/A | no | N/A | N/A |
| Option contract normalization | infra | — | **owner** | partial | no | perp specs | N/A |
| IV / Greeks engine | infra | — | **owner** | vol surface | no | implied vol | N/A |
| Gamma / dealer positioning | contract | consumer | **owner** (proxy) | instrument-specific | confirms | perp MM | N/A |
| Call demand anomaly | contract | consumer | **owner** | N/A | context | N/A | N/A |
| Signed options flow | infra | consumer | **owner** | N/A | confirms | N/A | N/A |
| IV / skew / term structure | infra | context | **owner** | vol surface | no | implied vol | implied prob |
| Event volatility / IV crush | infra | context | **owner** | macro events | no | unlocks | resolution |
| Open interest (derivatives) | infra | consumer | **owner** | **owner** | no | **owner** | **owner** |
| Liquidation / forced exit | infra | consumer (equity cover) | partial | **owner** | context | **owner** | partial |
| Contango / basis / roll | infra | no | partial | **owner** | no | **owner** | arb |
| Catalyst / filing | infra | consumer | event vol input | macro | no | unlocks | resolution |
| Attention / social | infra | major | context | context | no | major | major |
| Whale / block flow | infra | consumer | consumer | consumer | consumer | on-chain | large trader |
| Causal squeeze states | — | **owner** | consumes (feature) | no (different) | no | different | no |
| Squeeze probabilities / fuel | — | **owner** | consumes (feature) | no | no | no | no |
| Confirmation score (Phase 11) | — | no | legacy per-event | no | no | no | no |
| Strategy optimizer / payoff | infra | no | **owner** | partial | no | future | partial |
| EV / execution | **shared** | domain inputs | domain inputs | domain inputs | inputs | downstream | downstream |

**Rule:** share evidence infrastructure; do not share causal assumptions unless mechanisms match.

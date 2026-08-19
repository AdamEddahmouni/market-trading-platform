# Cross-Lane Boundary Matrix (Deliverable 3 — extended 2026-08-19)

Extended for Options ↔ Short Squeeze ↔ Futures ↔ Order Flow ↔ Market Context ↔ **Participant Intelligence**.

See also `MARKET_CONTEXT_OWNERSHIP_MATRIX.md` and `PARTICIPANT_TARGET_ARCHITECTURE.md`.

## Core platform matrix

| Capability / Signal | Platform | Short Squeeze | Options | Futures | Order Flow | Market Context | Participant | Crypto (future) | Prediction Mkt (future) |
|---|---|---|---|---|---|---|---|---|---|
| Point-in-time / provenance | **owner** | consumes | consumes | consumes | consumes | consumes | major consumer | consumes | consumes |
| Physical distribution P | **shared** | consumes | major consumer | consumes | inputs | — | consumes | future | inputs |
| Risk-neutral distribution Q | contract | context | **owner** | partial | no | — | no | implied | implied prob |
| P vs Q edge decomposition | — | no | **owner** | no | no | — | no | future | partial |
| CVD / aggressor delta | infra | consumer | context | major consumer | **owner** | — | consumes | consumer | consumer |
| ClassifiedTrade / aggressor provenance | infra | consumer | consumer | consumer | **owner semantics** | — | consumes | consumer | consumer |
| Book imbalance / DOM | infra | consumer | context | major consumer | **owner semantics** | — | consumes | exchange-specific | owner |
| OFI / MLOFI | infra | consumer | context | consumer | **owner** | — | consumes | consumer | consumer |
| Liquidity / impact primitives | infra | consumer | context | consumer | **owner** | — | interprets | consumer | consumer |
| Metaorder primitives | infra | context | context | context | **owner** | — | interprets lifecycle | future | future |
| Borrow / short interest | infra | **owner** | context | N/A | N/A | — | consumes | funding/OI | N/A |
| Option contract / IV / Greeks | infra | — | **owner** | vol surface | no | — | consumes | implied vol | N/A |
| Signed options flow | infra | consumer | **owner** | N/A | confirms | — | consumes (no reinterp) | N/A | N/A |
| COT / futures positioning | infra | context | context | **owner** | — | — | consumes categories | perp OI | N/A |
| Causal squeeze states | — | **owner** | consumes | no | no | — | no | different | no |
| Catalyst / event extraction | infra | consumer | O7 input | F7 input | no | **owner** | consumes timing | unlocks | resolution |
| EV / opportunity | **shared** | domain inputs | domain inputs | domain inputs | inputs | context inputs | participant inputs | downstream | downstream |

## Participant Intelligence ownership (extended)

| Capability | Platform | SS | Options | Futures | Order Flow | Market Context | **Participant** |
|---|---|---|---|---|---|---|---|
| Participant entity semantics | shared contract | context | context | context | context | context | **owner** |
| Participant identity confidence | shared contract | consumes | consumes | consumes | consumes | consumes | **owner** |
| Insider Form 4/5 transaction semantics | infra ingest | consumes | context | N/A | context | context | **owner** |
| Activist 13D interpretation | shared event | consumes | context | context | context | owns event extract | **owner participant view** |
| 13F holdings / limitations | infra ingest | context | context | N/A | no | context | **owner copyability semantics** |
| Participant action object | shared contract | consumes | consumes | consumes | consumes | consumes | **owner** |
| Intent / mechanism inference | — | consumes | context | context | context | catalyst timing | **owner** |
| Participant skill (walk-forward) | shared contract | consumes | consumes | consumes | context | context | **owner** |
| Copyability / entry quality | shared contract | consumes | consumes | consumes | execution input | context | **owner** |
| MetaorderEvidence | contract | consumes | context | context | produces raw | context | **owner interpretation** |
| Forced-flow probability | contract | consumes | partial | consumes | confirms | no catalyst | **owner research** |
| Participant crowding / consensus | contract | consumes | consumes | consumes | context | context | **owner** |
| Whale 8-family ledger ingest | infra | consumes | consumes | consumes | consumes | consumes | **major consumer** |
| Universal whale score | — | forbidden | forbidden | forbidden | forbidden | forbidden | **forbidden** |

**Rule:** share evidence infrastructure; do not share causal assumptions unless mechanisms match.

**Participant rule:** large ≠ informed; ownership ≠ bullish; flow ≠ information; whale direction ≠ trade direction.

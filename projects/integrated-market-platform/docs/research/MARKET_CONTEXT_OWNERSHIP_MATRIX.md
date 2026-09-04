# Market Context Ownership Matrix (Deliverable 3)

Extended from `CROSS_LANE_BOUNDARY_MATRIX.md` for Information Intelligence redesign.

| Capability | Platform | Short Squeeze | Options | Futures | Order Flow | Market Context |
|---|---|---|---|---|---|---|
| Point-in-time semantics | **Owns** | Consumes | Consumes | Consumes | Consumes | Stress-tests (publication vs event time) |
| Provenance / quality | **Owns** | Consumes | Consumes | Consumes | Consumes | Major producer |
| Instrument identity | **Shared** | Consumes | Consumes | Consumes | Consumes | Major consumer |
| Entity identity / graph | **Shared** | Consumes | Consumes | Consumes | Context | **Major consumer/producer** |
| Raw document store | Infra | — | — | — | — | **Owns semantics** |
| Information source model | Infra | — | — | — | — | **Owns** |
| Source credibility | Contract | Context | Context | Context | — | **Owns semantics** |
| Source informativeness (learned) | Research | — | — | — | — | **Owns** |
| Event clustering / dedupe | Infra | — | — | — | — | **Owns** |
| Event ontology | **Shared taxonomy** | Consumes | Consumes | Consumes | Context | **Owns curation** |
| Fact / numeric extraction | Infra | — | — | — | — | **Owns extraction layer** |
| Baseline semantic sentiment (FinBERT) | Infra model slot | Display only | Context feature | — | — | **Owns as BaselineFinancialSentiment** |
| Targeted entity sentiment | — | Context | Context | — | — | **Owns** |
| Uncertainty (textual) | — | Context | Context | — | — | **Owns** |
| Expectations / consensus PIT | Infra store | Context | O7 input | F7 input | — | **Owns snapshots** |
| Economic surprise | Contract | Context | Major consumer | Major consumer | Context | **Owns calculation** |
| Novelty | Contract | Consumer | Context | Context | — | **Owns** |
| Materiality | Contract | Consumer | Consumer | Context | — | **Owns** |
| Corroboration / rumor state | Contract | Context | Context | Context | — | **Owns** |
| Catalyst semantics | Contract | **Consumer** | Consumer | Consumer | Context | **Owns** |
| Short thesis invalidation evidence | Contract | **Consumer** | Context | N/A | Context | **Produces** |
| Bull/bear thesis graph | Research | Consumer | Context | — | — | **Owns evidence** |
| Attention level/velocity | Contract | Major consumer | Context | Context | — | **Owns measurement** |
| Narrative intelligence | Research | Consumer | Vol input | — | — | **Owns (experimental)** |
| Macro context regimes | Contract | Context | Consumer | Partial overlap | — | **Owns event semantics** |
| Macro futures interpretation | — | — | Partial | **Owns** | — | Does not duplicate |
| Market reaction observation | Infra prices | Context | IV reaction | Curve reaction | **Owns microstructure** | **Owns interpretation** |
| Reaction confirmation | Contract | Context | Context | Context | Confirms | **Owns classification** |
| Priced-in / remaining edge | Research | Context | Context | — | — | **Owns (experimental)** |
| Information decay | Contract | Consumer | Consumer | — | — | **Owns metadata** |
| LLM extraction governance | **Owns policy** | — | — | — | — | **Owns schema outputs** |
| CVD / OFI / book state | Infra | Consumes | Context | Consumes | **Owns** | Reaction consumer only |
| IV surface / Greeks | Infra | Context | **Owns** | Consumes | — | Reaction consumer |
| Physical distribution P | **Shared** | Consumes | Major consumer | Consumes | Inputs | Contributes features |
| Risk-neutral Q | Contract | Context | **Owns** | Context | — | Does not set fair value |
| P vs Q edge | — | — | **Owns** | — | — | Context does not override |
| Squeeze state machine | — | **Owns** | Consumes | — | — | Context does not set state |
| EV / opportunity | **Shared P4** | Domain inputs | Domain inputs | Domain inputs | Execution inputs | Context inputs only |

**Rule:** Market Context owns semantic and informational interpretation. Domain engines own market-specific causal models.

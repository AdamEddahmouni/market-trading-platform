# Market Context Joint Lane Report (Deliverable 12)

**Date:** 2026-08-19  
**Scope:** Cooperative integration outcome after Information Intelligence redesign initiation

---

## What Market Context now owns

- Canonical contracts in `contracts/market_context.py` (MC1 foundation)
- Semantic interpretation layer: sources, documents, events, baseline sentiment, surprise, novelty, materiality, credibility, catalyst components, thesis invalidation, attention, narrative, macro context, market reaction envelopes
- `LaneId.MARKET_CONTEXT` and expanded cross-lane signals in `cross_lane/evidence.py`
- Documentation: audit, architecture, glossary, discrepancy register, ownership matrix, gap analysis, research plan, five-lane reconciliation

---

## What happened to the old sentiment system

- **Not removed:** Short Squeeze FinBERT remains in donor screener as display-only experimental semantic sentiment
- **Renamed conceptually:** `positive/neutral/negative` → `BaselineFinancialSentiment` (semantic target, not trade direction)
- **Excluded from research rules:** Catalyst/momentum evaluation still forbids sentiment inference (unchanged — correct)
- **Product direction:** No universal news/sentiment score in canonical IMP UI

---

## What FinBERT still does

- Inference-only per-headline classification via `ProsusAI/finbert` or keyword fallback
- Populates screener UI/API with dominant label + counts
- **Does not:** set squeeze state, catalyst research scores, or cross-lane evidence (until MC4 bridge)

---

## What Short Squeeze now gains (path)

- `ShortThesisInvalidationEvidence` contract (already in `squeeze_structural.py`; MC8 will populate)
- `CatalystEvidence` with decomposed novelty/surprise/materiality (MC7–MC8)
- `AttentionEvidence` separate from information value (MC9)
- Consumption without owning squeeze state transitions

---

## What Options now gains (path)

- `SurpriseEvidence` and `EventEvidence` for O7 without duplicating IV math
- `UncertaintyEvidence` for surface/event vol inputs
- Context does not set fair option value or Q

---

## What Futures now gains (path)

- Shared macro event ontology + surprise semantics (MC11)
- Futures retains curve/carry/positioning interpretation (F7 unchanged owner)

---

## What Order Flow now gains (path)

- Event time/type annotation for conditioning microstructure (MC publishes; OF consumes)
- OF publishes reaction evidence; Context classifies confirmation/contradiction (MC12) without owning CVD/OFI

---

## What duplication was removed (conceptually)

- Isolated "sentiment lane" framing replaced by Market Context in roadmaps
- Catalyst confidence blend flagged for refactor into component evidence (MC-D07)
- Surprise cannot default to neutral when consensus missing (`surprise_unavailable_when_expectation_missing`)

---

## Cross-lane contracts added

| Contract / signal | Type |
|---|---|
| `InformationSource`, `RawDocument`, `InformationEvent` | Data model |
| `BaselineFinancialSentiment`, `TargetedSentiment` | Semantic layer |
| `ExpectationSnapshot`, `SurpriseEvidence` | Surprise layer |
| `CatalystEvidence`, `ShortThesisInvalidationEvidence` | Catalyst/thesis |
| `AttentionEvidence`, `NarrativeEvidence`, `MacroContextEvidence` | Context layers |
| `MarketReactionEvidence`, `ContextEvidenceEnvelope` | Fusion |
| `LaneId.MARKET_CONTEXT` | Publisher id |
| `EVENT_SURPRISE_*`, `NOVELTY_HIGH`, `REACTION_CONFIRMED`, etc. | Cross-lane signals |

---

## Data still missing

- Point-in-time analyst consensus / guidance store
- Live news ingest admitted to IMP replay
- Social attention with provenance
- FinBERT evaluation dataset
- Narrative / priced-in / remaining-edge validated datasets

---

## Remains experimental

- Narrative intelligence (MC10)
- Priced-in probability (MC13)
- Remaining information edge (MC13)
- Cross-entity propagation (MC15)
- Multi-document LLM synthesis (MC16)
- Internship Claude trade-driving scores

---

## Next shared milestone

**Platform P1 + Market Context MC2–MC3:** entity resolution and event clustering on admitted fixtures — unblocks trustworthy catalyst/attention counts before MC6 surprise work.

Parallel: continue Futures F9, Order Flow OF10, SS live lending (vendor-dependent) without blocking Context foundation.

---

## Test report

- New: `tests/contracts/test_market_context_contract.py` — **5 tests, all PASS**
- Full IMP suite (`tools/run_all_tests.py`): **exit 0** (~549 tests across 34 directories)
- Skips: live donor bridges (squeeze :8787, FuturesX :8788), symlink test — expected without live servers
- Failures: **none**

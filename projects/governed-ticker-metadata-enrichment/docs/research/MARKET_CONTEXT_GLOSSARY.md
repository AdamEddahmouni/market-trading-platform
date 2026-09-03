# Market Context Glossary

Canonical definitions for Information Intelligence. See `MARKET_CONTEXT_TARGET_ARCHITECTURE.md` for architecture.

---

## sentiment

Semantic tone of text toward an entity or event (`positive`, `negative`, `neutral`, `mixed`).  
**Does not mean:** positive stock return.

## targeted sentiment

Entity-specific polarity within a multi-entity document (e.g. Ford positive, GM negative).

## BaselineFinancialSentiment

Canonical name for FinBERT/keyword/lexicon semantic sentiment models — intermediate feature, not catalyst engine.

## uncertainty

Textual uncertainty/risk/modal strength — modeled separately from polarity.

## event

Underlying information occurrence cluster (`InformationEvent`), not a single article.

## catalyst

Interpreted information impact potential from novelty, surprise, materiality, credibility — **separate from sentiment**.

## novelty

Whether information is actually new vs duplicate/recap.

## materiality

Economic significance relative to entity scale (revenue, cash, cap).

## surprise

`actual - expectation` with PIT expectations; missing expectation → `SURPRISE_UNAVAILABLE`, not zero.

## expectation / consensus

Point-in-time expected value with `available_time` before event.

## revision

Initial vs revised macro/estimate values — initial release preserved for backtests.

## attention

Participation/visibility — separate from information quality.

## attention velocity / acceleration

First and second differences of attention level over time.

## information diffusion

Spread across sources/platforms tied to one event cluster.

## narrative

Evolving market thesis cluster (e.g. AI capex boom) — not synonym for sentiment.

## thesis

Bull/bear case with evidence; may be strengthened/weakened/invalidated.

## short-thesis invalidation

Evidence that specific bear mechanisms are weakened — produced by Context, consumed by SS.

## credibility

Trustworthiness of source/event — separate from historical predictiveness.

## corroboration

Independent confirmation state (`UNVERIFIED` → `CONFIRMED` / `DENIED` / `RETRACTED`).

## rumor

Information state with verification history — false rumors can still move markets.

## market reaction

Observed price/volume/vol/flow response — consumed from lane evidence, not reimplemented.

## reaction mismatch

Semantic/predicted direction disagrees with observed reaction.

## priced-in

Experimental probability that event was anticipated — not asserted without validation.

## remaining information edge

Experimental: expected impact minus realized, adjusted for diffusion — **UNVALIDATED**.

## information decay

Expected half-life class for evidence (`SECONDS` … `STRUCTURAL`).

## semantic_sentiment ≠ economic_surprise

Positive headline + miss vs consensus → negative surprise.

## article count ≠ event count

Track `document_count`, `source_count`, `independent_source_count`, `event_count` separately.

## influence ≠ truth

High influence with low forecast accuracy can still move prices (reflexive regimes).

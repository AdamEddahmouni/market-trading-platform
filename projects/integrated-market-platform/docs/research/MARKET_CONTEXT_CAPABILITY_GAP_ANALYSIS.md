# Market Context Capability Gap Analysis (Deliverable 7)

**Date:** 2026-08-19

## Provider / data capability matrix

| Capability | Exists today | Provider / location | Historical depth | PIT support | Gap |
|---|---|---|---|---|---|
| Company news headlines | Donor live | Finviz, Finnhub, NewsAPI, RSS | Session logs only | Partial (`published_at`) | Not admitted to IMP replay |
| Press releases | Partial | RSS, scrapers | Limited | Partial | No primary-source registry |
| SEC filings | Fixture + donor | EDGAR adapter, SEC RSS | BIYA fixture | Yes (Phase 9) | No delta analysis |
| Economic releases | Fixture | Futures macro slice | ES fixture | Yes | No equity-wide registry |
| Analyst consensus | **Missing** | — | — | — | **MC6 blocker** |
| Earnings calendar | Partial | Options O7 fixture | NVDA slice | Partial | No platform registry |
| Earnings transcripts | **Missing** | — | — | — | MC5 future |
| Social posts | Internship only | Keyword/RSS paths | Session state | Weak | Licensing + provenance |
| Search attention | **Missing** | — | — | — | MC9 |
| Company guidance | **Missing** | — | — | — | MC6 |
| Regulatory events | Partial | SEC + macro | Fixtures | Partial | Ontology incomplete |
| Government releases | **Missing** | — | — | — | MC11 |
| Court documents | **Missing** | — | — | — | Research only |
| Source timestamps | Partial | NEWS_ITEM, whale events | Variable | ADR-governed | Revision lineage gaps |
| Revision history | Partial | News ADR 0022 (squeeze) | Donor docs | Designed | Not in IMP |
| FinBERT inference | Donor | ProsusAI/finbert | None stored | Runtime only | Not canonical lane |
| LLM extraction | Internship | Claude | None governed | **Risk** | Schema-bound MC5 |

## Cost / licensing notes

| Source | Cost | Licensing constraint |
|---|---|---|
| NewsAPI | Paid tiers | Rate limits; enrichment policy exists |
| Finviz Elite | Subscription | Donor screener only |
| Finnhub | API key | Donor screener |
| EDGAR | Free | Primary filings — prioritize |
| Social platforms | Variable | Often research-only / deferred |
| Analyst consensus | Typically paid | Point-in-time history expensive |

## Reconstructability

| Data | Can reconstruct? | Notes |
|---|---|---|
| Headline sentiment logs | Partial | Session JSONL in screener |
| Historical consensus | Low | Requires vendor snapshot archive |
| Event surprise | Low without consensus PIT | MC6 prerequisite |
| Social attention | Low | Platform APIs change |

## Research-only (must not fake in production)

- Narrative clustering (MC10)
- Priced-in probability (MC13)
- Remaining information edge (MC13)
- Cross-entity propagation (MC15)
- Multi-document LLM synthesis (MC16)

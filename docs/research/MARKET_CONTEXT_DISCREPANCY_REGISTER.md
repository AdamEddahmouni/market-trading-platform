# Market Context Discrepancy Register (Deliverable 4)

| ID | Existing behavior | Why incomplete / incorrect | Evidence | Risk | Recommended change | Affected files | Owner | Phase | Priority |
|---|---|---|---|---|---|---|---|---|---|
| MC-D01 | Sentiment shown as screener column | Conflates semantic tone with catalyst/trade signal | `session_state.py`, `PROVIDERS.md` | False bullish/bearish inference | Label `BaselineFinancialSentiment`; separate catalyst card | squeeze screener UI | Market Context | MC4 | **PARTIAL (IMP path labeled; donor screener pending)** |
| MC-D02 | No `InformationEvent` clustering | Duplicate headlines inflate catalyst counts | No clustering code | Reflexive over-counting | MC3 event clusters | `market_context/event_clustering.py` | Market Context | MC3 | **RESOLVED (fixture scope)** |
| MC-D03 | FinBERT aggregate `MIXED` vs per-headline classes | UX ambiguity | `sentiment_live.py` | Misread tie states | Document + UI separation | sentiment_live, UI | Market Context | MC4 | P1 |
| MC-D04 | Internship LLM score drives trades | Unvalidated, ungoverned extraction | `decision_engine.py` | Research invalidity | Schema-bound extraction only | internship agent | Research | MC5 | **PARTIAL (IMP fixture-llm-v1 path)** |
| MC-D05 | Two incompatible sentiment systems | FinBERT [0,1] vs Claude [-1,1] | Both donors | Integration failure | Unified contracts; bridge FinBERT first | contracts/market_context.py | Market Context | MC4 | **RESOLVED (fixture scope)** |
| MC-D06 | Catalyst = news age in Adam (D-13) | Not thesis invalidation | `SHORT_SQUEEZE_DISCREPANCY_REGISTER D-13` | Weak ignition | `ShortThesisInvalidationEvidence` | squeeze_structural.py | SS+MC | MC8 | **RESOLVED (fixture scope via MC8)** |
| MC-D07 | `CATALYST_STRENGTH` without components | Single scalar hides surprise/novelty | `cross_lane/evidence.py` | Over-trust | Expose component evidence objects | market_context contracts | Market Context | MC8 | P1 — **RESOLVED (fixture scope: MC8 catalyst fusion + component metadata)** |
| MC-D08 | No expectations PIT store | Historical surprise leakage risk | No consensus module | Backtest invalidity | `ExpectationSnapshot` + TC001 | market_context/expectations.py | Market Context | MC6 | P0 — **RESOLVED** (fixture scope) |
| MC-D09 | Missing consensus → neutral surprise (internship) | Violates fail-closed | decision_engine patterns | False in-line events | `SURPRISE_UNAVAILABLE` flags | internship + MC6 | Market Context | MC6 | P0 — **RESOLVED** (IMP fixture path) |
| MC-D10 | Macro surprise in Futures only | Equity macro events fragmented | `macro_events.py` | Duplicate ontology | Shared macro taxonomy; Futures interprets | F7 + MC11 | Futures+MC | MC11 | P2 |
| MC-D11 | O7 event vol without Context surprise | Options-only earnings semantics | `event_vol.py` | Split surprise definitions | Context publishes `SurpriseEvidence` | options + MC6 | Options+MC | MC6 | P2 |
| MC-D12 | No reaction confirmation | Cannot detect contradiction | No MC12 module | Hidden disagreement | Consume OF/Options evidence | MC12 | Market Context | MC12 | **RESOLVED (fixture scope via MC12)** |
| MC-D13 | Entity resolution donor-only | Cross-asset propagation blocked | squeeze `identity_resolution.py` | Wrong entity attribution | Platform entity graph MC2 | `market_context/entity_resolution.py` | Platform | MC2 | **RESOLVED (fixture scope)** |
| MC-D14 | Revision lineage incomplete for news | Backtest knows V3 before V1 | squeeze news ADR 0022 | Temporal leakage | Revision-aware documents MC1 | squeeze news docs | Market Context | MC1 | P1 |
| MC-D15 | Social treated as truth in internship | Influence ≠ accuracy | herd_alert, claude_scorer | Reflexive false positives | Separate influence vs accuracy MC14 | influence track | Research | MC14 | P3 |
| MC-D16 | No LLM prompt/model versioning (internship) | Silent semantic drift | claude_scorer | Non-reproducible research | `ModelVersionRef` on all extractions | MC5/MC16 | Market Context | MC5 | **PARTIAL (IMP fixture path)** |
| MC-D17 | Phase 3d dropped `sentiment_label` without archive | Data archaeology confusion | batch01_discovery_rows.json | Mislabeled historical research | Dataset audit + version tag | intake batches | Research | MC4 | P2 |
| MC-D18 | Catalyst lane fixture-only | No live ingest admitted | Phase 15 PASS scope | Production gap | MC1 ingest + provenance | catalyst_lane | Platform | MC1 | P2 |
| MC-D19 | Attention UI without publisher lane | Attention metrics ungrounded | NowPage.tsx | Decorative attention | MC9 attention evidence producer | UI + MC9 | Market Context | MC9 | **RESOLVED (fixture scope via MC9)** |
| MC-D20 | Same-timestamp Context↔Options risk | Circular reinforcement possible | fusion DAG not enforced for NLP | Self-fulfilling signals | Provenance class + lag rules | cross_lane fusion | Platform | P3 | P1 |

## Migration classification

| Component | Action |
|---|---|
| FinBERT inference | KEEP → EXTEND as BaselineFinancialSentiment (**fixture labels in IMP**) |
| NEWS_ITEM contract | KEEP |
| Catalyst lane fixture | KEEP → bridge to CatalystEvidence |
| Claude free-form scoring | DEPRECATE for canonical path |
| Universal news score UX | REMOVE |
| Generic catalyst confidence blend | REFACTOR into components |
| Squeeze sentiment in research rules | KEEP excluded |

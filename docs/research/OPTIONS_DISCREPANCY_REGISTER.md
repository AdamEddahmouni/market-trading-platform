# Options Discrepancy Register (Deliverable 4)

**Status:** Living register — update on each Options milestone  
**Date:** 2026-08-18  
**Format:** ID | Existing behavior | Why incomplete/incorrect | Evidence | Risk | Recommended change | Affected files | Priority | Roadmap dependency

---

| ID | Existing behavior | Why incomplete/incorrect | Evidence | Risk | Recommended change | Affected files | Priority | Roadmap |
|---|---|---|---|---|---|---|---|---|
| O-01 | No canonical option contract model | Cannot support adjusted contracts, multipliers, exercise semantics | `envelope.py` activity shape only | Invalid backtests, wrong payoffs | Define `OptionContract` schema (O1) | `contracts/options.py` (new) | P0 | O1 |
| O-02 | `confirmation_score` displayed as primary "Score" | Collapses IV/vol/skew into single number; resembles forbidden universal score | `OptionsWorkspacePanel.tsx`, `options_lane.py` | Misleading trade framing | Demote to per-event activity context; primary UI becomes edge components (O4) | UI, projections | P1 | O4 |
| O-03 | `iv_rank`, `skew_signal` are fixture inputs | Not computed from market data | `biya_options_slice.json` | False precision in demos | IV engine computes or provider_IV with methodology tag (O2) | `fixture_options.py`, IV engine | P0 | O2 |
| O-04 | No internal IV normalization | Cannot compare IV across methodologies | No IV code | Silent methodology mixing | `provider_IV` + `internal_IV` with `pricing_model`, `solver`, version (O2) | IV engine (new) | P0 | O2 |
| O-05 | No Greeks engine | Cannot support surface, Q, dealer estimates | No Greeks code | Missing core capability | Reproducible Greeks subsystem (O2) | `options/greeks.py` (new) | P1 | O2 |
| O-06 | No volatility surface | Single IV per event, not σ(K,T) | Phase 11 spec out of scope | No skew/term edge | Surface engine with normalized coordinates (O2) | surface module (new) | P1 | O2 |
| O-07 | No surface quality gating | Would fit garbage to sophisticated models | N/A | Arbitrage-violating surfaces | Surface QA taxonomy before fitting (O2) | `options/surface_qa.py` (new) | P1 | O2 |
| O-08 | No risk-neutral distribution Q | Cannot do P vs Q | N/A | Core thesis unsupported | Q inference research path (O3) | `options/risk_neutral.py` (new) | P2 | O3 |
| O-09 | No physical distribution P | Cannot do P vs Q | ADR-fcast-001 interface only | Core thesis unsupported | SHARED P2 platform module | `research/distribution/` (new) | P2 | SHARED P2 |
| O-10 | Cross-lane Options not published | SS causal evaluator lacks gamma/flow context | `cross_lane_adapter.py` L59 `options_available: False` | D-07 SS gap | Options publisher adapter (SHARED P3) | `cross_lane_adapter.py` | P1 | SHARED P3 |
| O-11 | Dual scoring: whale `confirmation_score` vs catalyst `options_score` | Inconsistent semantics | `donor_bridge/projections.py` | Conflicting UI narratives | Unify under edge decomposition or clearly separate scopes | projections, catalyst bridge | P2 | O4 |
| O-12 | `OptionChainProvider` stub only | No live chain ingestion | `providers/stubs.py` | Cannot scale beyond BIYA | Tradier-class adapter when authorized (O1) | `providers/adapters/` | P2 | O1 |
| O-13 | BIYA-only entitlement | Cannot test multi-symbol surfaces | Phase 11 admission | Limited research | Expand admission incrementally with PIT fixtures | fixtures, admission manifest | P2 | O1 |
| O-14 | No historical expired chains | Rigorous backtest impossible | No archive | Research invalidity | Historical chain archive plan (O1) | data layer | P2 | O1 |
| O-15 | No signed flow classification | Cannot distinguish buy/sell initiation | ADR-WHALE-004 acknowledges | Direction-from-volume risk | Signed flow engine; fail closed when unavailable (O5) | flow module (new) | P2 | O5 |
| O-16 | `CALL_DEMAND_ANOMALY` enum unused | Signal defined but no producer | `evidence.py` | Future naive wiring risk | Producer only with abnormal-flow baseline (O5) | cross_lane adapter | P2 | O5 |
| O-17 | No dealer positioning model | GEX claims impossible today | `options/dealer.py` OI×gamma proxy | N/A if labeled proxy | **RESOLVED (fixture scope)** — `build_dealer_snapshot`; never claim true dealer gamma | `options/dealer.py`, `cross_lane_adapter.py` | P3 | O6 |
| O-18 | No event volatility subsystem | Earnings IV crush invisible | N/A | Wrong event trades | **RESOLVED (fixture scope)** — `options/event_vol.py` state machine + IV crush; `nvda_earnings_event_slice.json` | `options/event_vol.py`, `cross_lane_adapter.py` | P3 | O7 |
| O-19 | No strategy optimizer | Cannot express P vs Q as trades | Foundation spec separates strategy | Missing decision layer | **RESOLVED (fixture scope)** — `options/strategy.py` template rank + `NO_CLEAR_EDGE` | `options/strategy.py`, `cross_lane_adapter.py` | P3 | O8 |
| O-20 | No payoff / expected P&L engine | Cannot rank structures | N/A | EV claims impossible | **RESOLVED (fixture scope)** — `options/payoff.py` physical-P quantile payoff | `options/payoff.py` | P3 | O8 |
| O-21 | Simulator is bar-only | No option legs, assignment, spread crossing | `execution/simulator.py` | Invalid options backtest | **RESOLVED (fixture scope)** — `options/execution.py` + `execution/options_conservative.py` NBBO multi-leg | `options/execution.py`, `execution/options_conservative.py` | P3 | O9 |
| O-22 | No options quality taxonomy (formal) | Missing data may become zero | `liquidity_reasons` only | Silent failures | `OPTION_QUALITY_FLAGS` enum (O1) | `contracts/options_quality.py` | P0 | O1 |
| O-23 | No point-in-time on OI/earnings/dividends | Leakage risk when live | Whale ledger has cutoff; no earnings join | Backtest leakage | PIT joins centralized (PLATFORM P0) | replay, features | P0 | P0 |
| O-24 | Wireframe shows chain/skew; UI is table only | UX expectation gap | `07-options.md` vs panel | User confusion | Progressive disclosure per O2/O4 milestones | UI | P2 | O2/O4 |
| O-25 | No volatility risk premium model | IV−RV misread as sell signal | N/A | Systematic vol mis-trading | Explicit VRP research (O4) | research plan | P3 | O4 |
| O-26 | No delta-hedged return research primitive | Cannot isolate vol edge | N/A | Research gap | **RESOLVED (fixture scope)** — `delta_hedged.py` + `r_o6.py` correlation gate wired in projections | `options/delta_hedged.py`, `options/r_o6.py`, `providers/projections.py` | P4 | O10 |
| O-27 | SS squeeze evidence not consumed by Options | Tail forecasts miss reflexivity | `squeeze_context.py` + O7 crush conditioning | Suboptimal P | **PARTIAL (fixture scope)** — `exhaustion_risk` conditions IV crush in O7; full P forecast integration deferred | `options/event_vol.py`, `options/features/squeeze_context.py` | P2 | O7 |
| O-28 | No circular-dependency guard in evidence DAG | Cross-lane loops possible | N/A | Model amplification | `EvidenceProvenanceClass` + DAG validation (SHARED P3) | `cross_lane/evidence.py` | P1 | SHARED P3 |
| O-29 | `confirmation_score` unit test missing | Only liquidity_gate tested | `test_donor_patterns.py` | Regression risk | Add scoring boundary tests | tests | P1 | O1 |
| O-30 | 0DTE treated as ordinary small DTE | Would mis-model gamma/theta | N/A | Path risk when implemented | 0DTE subdomain (O11) | dedicated module | P4 | O11 |
| O-31 | Baseline gates not evidenced on admitted fixtures | O11 blocked without R-O6/R-O5/R-O10-SURF validation | N/A | Premature ML / 0DTE work | **RESOLVED (fixture scope)** — `run_o10_baseline_gate_validation()` + `nvda_o10_baseline_gates_expected.json`; aggregate PASS on admitted NVDA fixtures | `options/research/harness.py`, `tools/options/run_o10_baseline_gate_validation.py` | P4 | O10 |

---

## Migration classification

| Component | Action |
|---|---|
| Phase 11 fixture adapter | **KEEP** — extend into O1 |
| `liquidity_gate` | **KEEP** — becomes strategy liquidity gating |
| `confirmation_score` | **REFACTOR** — demote from primary output |
| `whale_event` envelope | **EXTEND** — toward canonical contract |
| `OptionChainProvider` stub | **IMPLEMENT** when provider authorized |
| Universal options score | **FORBIDDEN** — per ADR-WHALE-004 |
| Dealer gamma without flow | **FORBIDDEN** until O6 |
| P vs Q without SHARED P2 | **FORBIDDEN** until distributions exist |

---

## SS register cross-references

| Options ID | Related SS ID |
|---|---|
| O-10 | D-07 |
| O-09, O-08 | D-06 (don't substitute scores for calibrated probs) |
| O-21 | D-14 |
| O-27 | SS P5 exhaustion → O7 IV crush |

# Futures Discrepancy Register (Deliverable 4)

| ID | Existing behavior | Why incorrect/incomplete | Evidence | Risk | Recommended change | Affected files | Owner | Phase | Priority |
|---|---|---|---|---|---|---|---|---|---|
| F-D-01 | Whale family named `futures_positioning` | Depth imbalance ≠ CFTC/COT positioning | Phase 14 whale taxonomy | Misleading institutional flow UX | Rename interpretation; separate depth vs COT evidence | whale ledger, fixture_futures | Futures | F4 | P0 — **RESOLVED** (canonical `futures_depth` alias; legacy envelope id retained) |
| F-D-02 | `contract_month` YYYYMM only | No distinct `contract_id` (e.g. ESU26) | es_depth_slice.json | Roll/PnL ambiguity | Canonical FuturesContract with contract_id | contracts/futures.py | Futures | F1 | P0 |
| F-D-03 | No multiplier/tick in canonical model | PnL cannot be contract-accurate | No spec in fixture | Wrong risk sizing | FuturesContractSpec first-class | contracts/futures.py, notional.py | Futures | F1 | P0 |
| F-D-04 | No notional / leverage display | "2 contracts" without economic context | UI workspace | Capital misallocation | exposure_summary in UI | futures UI, notional.py | Futures | F1 | P1 |
| F-D-05 | `quarterly_contract_month()` picks nearest quarter | No volume/OI lead selection | futures_lane.py | Wrong analysis contract | select_lead_contract rule v1 | futures/roll.py | Futures | F2 | P1 |
| F-D-06 | No roll_state | Cannot distinguish PRE_ROLL/ROLLING | None | Roll window blind spot | RollState on contract/curve | futures/roll.py | Futures | F2 | P1 |
| F-D-07 | No continuous vs tradeable separation | Backtest leakage risk | None | Double-counting roll returns | Explicit series methodology flags | contracts/futures.py | Futures | F2 | P1 |
| F-D-08 | No curve snapshot object | Term structure not first-class | None | No carry/RV research | FuturesCurveSnapshot | contracts/futures.py | Futures | F3 | P1 |
| F-D-09 | No basis definition | Sign convention unspecified | None | Mixed-series errors | BasisObservation + BasisDefinition | contracts/futures.py | Futures | F3 | P1 |
| F-D-10 | Contango/backwardation not modeled | Curve shape invisible | None | Miss commodity tightness signals | Curve derived metrics F3 | planned | Futures | F3 | P2 |
| F-D-11 | No COT ingestion | Positioning unknown | None | Crowding blind spot | FuturesPositioningSnapshot + PIT | planned | Futures | F4 | P2 — **RESOLVED** (`cot.fixture.futures_positioning`) |
| F-D-12 | No COT publication delay enforcement | Potential lookahead if added naively | None | Backtest invalidation | cot_point_in_time_valid + tests | contracts/futures.py | Futures | F4 | P0 — **RESOLVED** (PIT filter + lookahead golden) |
| F-D-13 | OI rising interpreted nowhere but whale conflates depth | OI ≠ direction not enforced platform-wide | Phase 14 naming | False directional inference | Document + block inference without evidence | docs, quality flags | Futures | F4 | P2 — **RESOLVED** (OI velocity hypothesis labels) |
| F-D-14 | No margin engine | Leverage stress impossible | None | Liquidation risk blind | Margin fields on contract F8 | planned | Futures | F8 | P2 — **RESOLVED** (`margin.fixture.futures_margin` + `leverage_stress.py`) |
| F-D-15 | Depth imbalance owned in futures_lane | Order Flow owns DOM/book semantics | futures_lane.py | Duplication vs Order Flow | Futures consumes OrderFlowEvidence | cross_lane | Order Flow | P1 | P1 |
| F-D-16 | No cross-lane futures publisher | Options/Squeeze lack index futures context | cross_lane_adapter | Missed cooperative signals | build_cross_lane_snapshot_from_futures | cross_lane_adapter.py | Futures | P3 | P1 |
| F-D-17 | Simulator bar-only | No rolls, VM, limits | simulator.py | Futures backtest invalid | Extend shared simulator F10 | execution/simulator.py | Platform | F10 | P3 |
| F-D-18 | `imbalance_signal` contrarian without confidence | Single threshold 1.5 | futures_lane.py | Fragile signal | Quality flags + session baselines | futures_lane.py | Order Flow | P1 | P3 |
| F-D-19 | No asset-family branching | ES treated as generic future | futures_lane.py | Wrong fundamentals for CL/ZN | FuturesFamily plugin interface F6 | planned | Futures | F6 | P2 — **RESOLVED** (`futures/families/` EQUITY_INDEX v1) |
| F-D-20 | No delivery guardrails | Accidental delivery exposure possible in future sim | None | Operational risk | DELIVERY_RISK quality flag | planned | Futures | F10 | P3 |
| F-D-21 | ES full session deferred ADR-DATA-001 | Limited depth history | ADR | Research depth constrained | Lawful bytes + ADR update | ADR-DATA-001 | Platform | — | DEFERRED |
| F-D-22 | FuturesX live trader not admitted | Donor experiments outside governance | FUTURESX_NOTES | Scope creep if merged | Keep bridge read-only | donor bridge | Platform | — | OK |
| F-D-23 | Missing ≠ neutral not enforced for futures | No futures quality taxonomy | None | Silent degradation | FuturesQualityFlag enum | futures_quality.py | Futures | F1 | P0 |
| F-D-24 | No futures opportunity taxonomy | Implicit depth signal only | UI | No RV/carry/trend separation | Opportunity types F66 | planned UI | Futures | F9+ | P3 |

## Migration classification

| Component | Action |
|---|---|
| Phase 14 fixture depth | KEEP |
| futures_lane depth patterns | KEEP (migrate interpretation to Order Flow consumer) |
| `futures_positioning` whale label | REFACTOR semantics in docs; split evidence types — **canonical `futures_depth` alias live** |
| Donor bridge | EXTEND read-only |
| Generic futures score | FORBIDDEN |
| COT without publication delay | FORBIDDEN until PIT enforced |
| Independent CVD in Futures | FORBIDDEN — use Order Flow |

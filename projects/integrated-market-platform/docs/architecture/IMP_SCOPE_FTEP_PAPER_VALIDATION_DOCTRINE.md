# IMP Scope, FTEP, and Paper-Validation Doctrine

**Classification:** `CURRENT_CANONICAL_ARCHITECTURE`  
**Established:** 2026-09-11  
**Applies to:** research, Opportunity Engine, forward tests, Paper execution, provider/data admission, and future strategy-family implementation

## 1. Scope hierarchy

IMP is the whole multi-strategy, multi-asset platform. No campaign, instrument, strategy family, provider, or professor-priority increment is the platform by itself.

The canonical hierarchy is:

1. **IMP** — opportunity discovery, evidence, portfolio/risk, governed Paper execution, monitoring, and operator workflow.
2. **Strategy/research families** — news/catalysts, short squeezes/crowding, technical/price action, futures, options/volatility, microstructure/order flow, macro/cross-asset, quantitative factors, participant/alternative data, crypto/on-chain, regimes, risk/portfolio, and execution/frictions.
3. **FTEP** — the reusable Forward-Test Experimental Protocol used to test candidates prospectively.
4. **Campaign manifests** — frozen, bounded empirical campaigns assembled from FTEP components.
5. **FTEP-V1-001 / ES-news** — the current candidate first campaign only. ES is one futures instrument family, not IMP.

Professor-directed work controls near-term sequencing. It does not redefine permanent product scope.

## 2. Three-layer Paper evidence model

Paper-market conclusions must keep three layers distinct.

### A. Market Evidence Layer

Prospective external reality available at the decision cutoff: quotes, trades, bars, volume, session state, news/events, reference data and, where lawfully entitled, depth/order-book observations.

Market Evidence records must preserve provider/source identity, instrument identity, source/event time, receive/observation time, data mode, freshness, coverage, quality flags, entitlement/use-right status, and provenance.

### B. IMP Execution Simulation Layer

IMP's hypothetical orders, acknowledgements, fills, partial fills, rejects, cancels/replaces, positions, costs, margin assumptions and P&L. This layer uses fake money. It is not market ground truth merely because engineering tests pass.

### C. External Simulation Comparator Layer

A broker/exchange/vendor Paper, sandbox, replay, or simulation environment used to challenge IMP's execution model when suitable for the asset and experiment.

An external simulator is a **comparator, never ground truth**. Agreement with a comparator is evidence of consistency under that comparator's rules, not proof of real execution realism. Material disagreements among market evidence, IMP simulation and external simulation must be retained and explained rather than silently reconciled to the favorable result.

## 3. FTEP is layered, reusable, and versioned

The canonical protocol composition is:

`FTEP Core -> Asset-Class Profile -> Strategy Profile -> Campaign Manifest`

### FTEP Core

Universal experiment rules: preregistration, point-in-time/anti-look-ahead controls, provenance, immutable decision lock, evidence classes, baseline/treatment rules, metrics, multiple-testing controls, invalidation, reproducibility, change control, outcome states, account isolation and zero automatic Live authority.

### Asset-Class Profile

Asset-specific market/execution semantics. Examples:

- **Equities:** sessions/halts, corporate actions, dividends, tick/lot rules, SSR where applicable, borrow/locate availability and borrow costs for short strategies.
- **Futures:** dated executable contracts, contract multiplier/tick economics, exchange sessions, expiry/roll, settlement, margin, price limits and contract-month liquidity.
- **Options:** chain/surface state, contract adjustments, spreads/depth, IV/Greeks provenance, expiration, exercise/assignment, and multi-leg execution semantics.
- **Crypto:** venue identity, 24/7 calendars, venue-specific books, fees/funding where relevant, fragmentation and instrument/venue custody/execution assumptions.
- **Other assets:** must receive their own profile before execution evidence is claimed.

### Strategy Profile

Strategy-specific candidate-generation rules, features, horizon, baseline, treatment, exclusions, opportunity semantics, metrics and failure criteria. A strategy profile cannot weaken FTEP Core or the asset profile.

### Campaign Manifest

The exact prospective experiment: protocol/profile versions, source SHA, account, instruments, dates/session windows, provider/data bindings, comparator, execution mode, sizing, horizons, costs, acceptance thresholds, exclusions and analysis plan.

## 4. Freeze and version semantics

`FTEP-V1/0.1.0-PREREG` is a **preregistration/design artifact**, not an activated empirical campaign. Its unresolved `OPEN DECISION` items prove that activation freeze has not occurred.

A campaign is considered **FROZEN FOR ACTIVATION** only when every required activation gate is satisfied and the final campaign manifest is immutable and hash/version bound before the first qualifying prospective observation.

Rules:

- FTEP Core and profiles remain versioned architecture and may evolve prospectively.
- A running campaign stays bound to the versions recorded in its frozen manifest.
- A material post-freeze rule/source/model/parameter/execution change requires a new campaign manifest/version, unless the current campaign is explicitly invalidated.
- No result may be used to retroactively choose thresholds, horizons, exclusions, providers or favorable execution assumptions.

## 5. Market Data Capability Contract

Every source used for empirical market evidence must have a campaign-relevant capability record. At minimum:

| Field | Required meaning |
|---|---|
| Provider / dataset / endpoint | Exact source identity |
| Asset / venue / instrument coverage | What the source actually covers |
| Data mode | `REALTIME`, `DELAYED`, `HISTORICAL`, `REPLAY`, or explicitly defined equivalent |
| Observation type | Trade, quote/L1, depth/L2/MBO, bar, news/event, reference, derived |
| Source/event timestamp | Timestamp supplied by the source/exchange/publisher |
| Receive/observation timestamp | When IMP received/observed it |
| Timestamp precision/semantics | Clock meaning and precision |
| Venue/consolidation coverage | Single venue, consolidated, partial, unknown |
| Freshness/staleness policy | Campaign-valid freshness rule |
| Gaps/backfills/revisions | Known mutation and recovery behavior |
| Entitlement | Account-level access actually verified |
| Permitted use | Research/runtime/storage/display/redistribution/non-display as applicable |
| Reliability/rate limits | Operational constraints |
| PIT reconstructability | Whether historical state can be reconstructed without future revisions |
| Campaign role | Authority, challenger, context-only, comparator-only, or prohibited |

"Real time" alone is not a sufficiency claim. A source must be sufficient for the exact hypothesis and execution-model question being tested.

## 6. Simulator Calibration & Validation Contract

Before IMP Paper fills/P&L are used as evidence about strategy implementability, each relevant asset/order-policy profile must have a calibration contract.

### Required comparison dimensions

- order acceptance/rejection and reason;
- trigger/submit/ack/fill/cancel timestamps;
- fill/no-fill disagreement;
- fill price error and slippage;
- spread-crossing assumptions;
- partial fills and completion rate;
- stop, limit, market and cancel/replace semantics;
- session/overnight/auction handling where applicable;
- fees/commissions/exchange costs;
- margin/collateral assumptions;
- realized/unrealized P&L and position reconciliation;
- stale/missing-market handling;
- latency assumptions;
- capacity/liquidity assumptions where relevant.

### Quantitative gate rule

Every activated campaign using simulated execution must specify **numeric acceptance thresholds before the run** for the metrics material to that campaign. At minimum, thresholds must address fill/no-fill disagreement rate, fill-price/slippage error, timing error where timing matters, position/P&L reconciliation tolerance, and unexplained material-divergence rate.

No universal numbers are invented in this doctrine. Threshold values must be justified from the asset/order/data resolution and frozen in the campaign manifest. If a defensible number cannot yet be set, that metric is `UNSET/BLOCKING` and the campaign cannot use the corresponding execution claim.

### Calibration disposition

Each comparison is classified `WITHIN_TOLERANCE`, `EXPLAINED_DIVERGENCE`, `UNEXPLAINED_DIVERGENCE`, or `NOT_OBSERVABLE`. Unexplained material divergence blocks promotion of the affected execution model.

## 7. Strategy readiness is a vector, not one maturity label

Every strategy family is tracked independently across these axes:

1. Research maturity
2. Data readiness and rights
3. Signal/strategy implementation
4. Historical/OOS validation
5. Prospective shadow readiness/evidence
6. Paper execution readiness/evidence
7. Execution-model calibration
8. Opportunity Engine integration
9. Portfolio/risk integration
10. Live eligibility

Summary labels may be shown for convenience but must never replace the readiness vector. **Live eligibility is independently governed and never follows automatically from research, OOS or Paper success.**

Recommended state vocabulary per axis: `NOT_STARTED`, `PLANNED`, `IMPLEMENTED`, `VALIDATED`, `BLOCKED`, and `NOT_APPLICABLE`, with evidence links for any `VALIDATED` state.

## 8. Opportunity Engine common contract

One Opportunity Engine means one governed comparison/decision architecture, not one universal magic score.

Every strategy lane should eventually emit a common Opportunity Contract containing, as applicable:

- opportunity/candidate ID and strategy provenance;
- canonical instrument and asset class;
- direction/expression and horizon;
- catalyst/mechanism and concise explanation;
- expected edge/range plus uncertainty/calibration;
- evidence class and confidence basis;
- freshness and source/data quality;
- liquidity/capacity and execution feasibility;
- expected spread/slippage/fees/cost range;
- downside/tail risk and invalidation condition;
- portfolio exposure/concentration effects;
- regime/context tags;
- required order/instrument expression;
- eligibility/safety state;
- abstention reason when not actionable.

Ranking, filtering and portfolio construction may use these normalized attributes differently by horizon/strategy. No single scalar score is required to erase meaningful differences among strategies.

## 9. Provider and comparator admission

Provider existence, credentials, entitlement, data suitability and campaign binding are separate facts.

A candidate external Paper/sandbox environment may be used only after an asset/experiment-specific capability audit verifies the required instrument, order types, market-data timing, session behavior, account mode, API/access path and known simulation limitations. Candidate names are not pre-approved merely because IMP has an adapter or prior research.

Private/local credentials or old setup must be freshly audited before the project claims a provider is currently configured or campaign-ready. No secret values are copied into documentation.

## 10. Evidence ladder

The canonical evidence progression is:

`ENGINEERING_VALIDATION -> HISTORICAL/OOS_RESEARCH -> LIVE_DAY_SHADOW -> PAPER_OBSERVED -> REPEATED_PROSPECTIVE_EVIDENCE`

Progression is not automatic. Fixture success proves software behavior under the fixture, not market edge. Historical replay is not prospective evidence. Paper evidence does not grant Live authority.

## 11. Current-state interpretation

As of `main@a4858103baa3531051791a632ed36a9339fd6414`:

- the governed Paper forward-testing bridge exists;
- PD-09 durable forward-test SQLite persistence is implemented and merged;
- `FTEP-V1/0.1.0-PREREG` exists and is explicitly not empirical evidence;
- unresolved campaign activation decisions remain;
- the internal simulator is not yet presumed calibrated market ground truth;
- no first FTEP empirical campaign is activated by this doctrine;
- Live production execution remains separately blocked/unauthorized.

The next work before a first execution-bearing ES/news campaign is governed by [FTEP Activation & Pre-Implementation Gates](../engineering/FTEP_ACTIVATION_GATES.md).

## 12. Non-negotiable boundaries

- No campaign activation from documentation alone.
- No Live trading authority from FTEP, Paper success, provider connectivity or model confidence.
- No paid service/trial/entitlement activation without owner authorization.
- No hidden substitution of delayed/replay/synthetic data for a declared prospective evidence class.
- No external simulator is labeled market truth.
- No strategy is labeled validated without evidence matching the claimed readiness axis.
- No campaign is frozen while required thresholds, data rights, source bindings or comparator/calibration decisions remain unresolved.

# Phase 3E — Systematic Historical Evidence Construction and Outcome-Blind Phase 3A Enablement

## Status

**Preregistered before any outcome data access.** This document is the Phase 3E design
and the initial preregistered acquisition plan for **Stage 1 only** (outcome-blind
evidence construction). It is committed on branch
`phase/3e-systematic-historical-acquisition` before any retrospective outcome data,
forward bar data, or price-return information for the 13 registry-only symbols is
inspected, computed, or evaluated.

**Stage 2** (forward outcome acquisition and full pipeline execution) requires a
separate batch-level acquisition plan committed as a distinct document **before** any
outcome data is fetched. This Phase 3E design defines Stage 2's intended protocol but
does not authorize outcome data access — that authorization comes only after the Stage 2
plan is independently committed.

## Preregistered research question

Can point-in-time evidence layers for the 13 registry-only Phase 3D pilot symbols be
constructed from the available IBKR historical bar data, the archived scanner snapshot,
and the existing public provider adapters (NewsAPI, SEC EDGAR, Finnhub) to enable
outcome-blind Phase 3A evaluation, without fabricating missing evidence and without
reinterpreting honestly unresolved IBKR bar semantics?

This question is falsifiable: if no symbol's evidence layers can be constructed to
intake `READY`, the answer is "no, not with the currently available evidence sources."
That is a valid outcome.

A secondary question (Stage 2): for symbols that reach `READY` and pass Phase 3A
evaluation, can forward outcome bars be acquired from the authenticated IBKR connection
to complete the Phase 3B research evaluation pipeline?

## Objective

Phase 3E constructs the point-in-time evidence layers needed to move the 13
registry-only Phase 3D pilot cases (XNCR, PESI, SLS, ZNTL, GPRE, SSPC, LBGJ, TRVI,
LMNX, MGNX, BHVN, OBE, AVTX) from Phase 3B registry status to full Phase 3A evaluable
status, using the authenticated Interactive Brokers connection as the primary
historical bar source, and remaining strictly outcome-blind throughout evidence
construction.

After evidence construction and preregistration are complete, Phase 3E will acquire
forward outcome bars via the same IBKR connection, run Phase 3A evaluation, and
proceed through the Phase 3B research evaluation and Phase 3C descriptive analysis
pipeline. No outcome data is inspected before this document is committed.

The phase does not optimize thresholds, change Phase 3A policies, create composite
scores, rank candidates, generate recommendations, produce alerts, perform backtesting,
compute P&L, or add trading capabilities.

## Background and current state

Phase 3D established the acquisition pipeline (`squeeze_core.acquisition`) and ran two
preregistered batches:

- **Batch 01** curated 13 symbols from the archived scanner snapshot
  (`screener_snapshot.json`, captured `2026-07-18T13:37:55Z`). All 13 were assessed as
  **registry-only** — no Phase 3A evaluation was possible because normalized
  point-in-time evidence layers cannot be constructed from the flat scanner snapshot
  without fabrication.

- **Batch 02** searched for lawful public non-authenticated sources for forward outcome
  bars. All 13 candidate sources were evaluated and zero were acceptable. Conclusion:
  `NO_ACCEPTABLE_LAWFUL_NONAUTHENTICATED_SOURCE`.

- **Batches 05-06** established the IBKR TWS API connection, resolved contract metadata
  for all 13 symbols (distinct conIds, primary exchanges confirmed), collected
  detection-context and forward-window historical bars via the authenticated IB Gateway
  (localhost port 4001), and resolved IBKR bar semantics for price adjustment
  (`SPLIT_ADJUSTED`), corporate-action handling (`ADJUSTMENTS_APPLIED`), timestamp
  representation (epoch seconds → UTC), session policy (`EXTENDED`), and filtered-feed
  disclosure. Some fields remain honestly unresolved: `volume_adjustment_semantics` and
  `timestamp_semantics` (bar start/end) are `UNKNOWN`, and the volume unit (shares vs.
  round lots) is `HISTORICAL_VOLUME_UNIT_UNRESOLVED`. All 26 preflights were honestly
  `PREFLIGHT_REJECTED` due to these unresolved fields.

- The `FROZEN_FORWARD_24H` artifacts returned **pre-boundary Friday data** because the
  frozen boundary fell on a Saturday (non-trading day). These artifacts must never be
  treated as forward-outcome evidence.

Phase 3E inherits:
- 13 registry-only cases with resolved IBKR contract identities
- 26 collected CSV/JSONL bar artifacts (detection-context and forward-window)
- An authenticated and working IBKR Gateway connection
- Resolved price-adjustment and timestamp-representation semantics
- Honest unresolved status for volume adjustment and bar start/end semantics
- The full Phase 3A evaluation engine, Phase 3B research pipeline, Phase 3C analysis
  layer, and Phase 3D acquisition infrastructure

## Architecture

Phase 3E adds capabilities within the existing `squeeze_core.acquisition` package and
the existing `tools/ibkr_historical_export/` tooling. No new top-level packages are
created. The work is organized in two stages:

### Stage 1 — Outcome-blind evidence construction (this preregistration)

1. **IBKR bar-semantics resolution extension.** Resolve whether the remaining `UNKNOWN`
   fields (`volume_adjustment_semantics`, `timestamp_semantics`, volume unit) can be
   determined from official IBKR documentation, the installed `ibapi` contract, or
   read-only Gateway configuration. If they remain genuinely unresolvable, extend the
   Batch 03 intake contract to accept an honest `UNKNOWN` declaration with explicit
   provenance rather than treating it as a fatal `MISSING_ADJUSTMENT_SEMANTICS`
   rejection.

2. **Evidence-layer construction.** For each of the 13 registry-only symbols, construct
   the normalized point-in-time evidence layers required for Phase 3A evaluation:
   - Market bar evidence from the IBKR detection-context CSVs
   - Short-interest and borrow evidence from the archived scanner snapshot where
     available
   - Catalyst evidence from available public sources (NewsAPI, SEC EDGAR)
   - Evidence-validity metadata from structural evidence availability
   
   Evidence construction is outcome-blind. No price returns, threshold crossings, or
   outcome labels are computed during construction.

3. **Intake manifest finalization.** For each symbol whose evidence layers can be
   constructed, finalize the intake manifest, run the existing offline preflight, and
   produce `READY` or `PREFLIGHT_REJECTED` with explicit reason codes. Registry-only
   symbols that cannot be brought to `READY` remain honestly registry-only with
   documented limitations.

4. **Phase 3A request and result freeze.** For each `READY` symbol, serialize the
   Phase 3A request (unchanged policy `phase_3a_transparent_candidate_policy.v1`),
   run the existing `evaluate_candidate` function, freeze the result, and record its
   deterministic identity and SHA-256 hash. This is the same outcome-blind freeze
   established in Phase 3D.

### Stage 2 — Outcome acquisition and full pipeline execution (after preregistration)

Executed only after Stage 1 commits are complete and the preregistration is frozen.
A separate batch-level acquisition plan will be committed before Stage 2 begins.

1. **Forward outcome bar acquisition.** Using the IBKR authenticated connection, acquire
   forward 24-hour trade bars for each `READY` symbol on an actual trading day (Monday
   through Friday, non-holiday). The frozen boundary timestamps remain unchanged. The
   forward window is the 24 hours immediately following the frozen detection boundary.

2. **Outcome capture.** Using the existing Phase 3B outcome-label policy
   (`phase_3b_outcome_label_policy.v1`) with fixed 24-hour horizon and ±25% thresholds,
   compute the retrospective outcome label for each symbol. The outcome manifest is
   written as a separate contract per the Phase 3D leakage-audit convention.

3. **Leakage audit.** Run the existing Phase 3D leakage audit to verify that the plan,
   boundary freeze, Phase 3A request, and Phase 3A result were all frozen before
   outcome capture. Any failure blocks empirical publication and is recorded in the
   case-attempt ledger.

4. **Phase 3B evaluation and Phase 3C analysis.** For each leakage-passing case,
   register it in the Phase 3B research registry, run the research detection and
   classification pipeline, and produce Phase 3C descriptive analysis reports.

## Preregistered policies

All policies are frozen at the versions established in prior phases. No policy is
changed, optimized, or threshold-adjusted.

| Policy | Version | Established in |
|--------|---------|----------------|
| Acquisition plan policy | `phase_3d_acquisition_plan_policy.v1` | Phase 3D |
| Candidate discovery policy | `phase_3d_candidate_discovery_policy.v1` | Phase 3D |
| Historical inclusion policy | `phase_3d_historical_inclusion_policy.v1` | Phase 3D |
| Historical exclusion policy | `phase_3d_historical_exclusion_policy.v1` | Phase 3D |
| Identity resolution policy | `phase_3d_identity_resolution_policy.v1` | Phase 3D |
| Detection boundary policy | `phase_3d_detection_boundary_policy.v1` | Phase 3D |
| Outcome leakage policy | `phase_3d_outcome_leakage_policy.v1` | Phase 3D |
| Unique security deduplication policy | `phase_3d_unique_security_deduplication_policy.v1` | Phase 3D |
| Phase 3A transparent candidate policy | `phase_3a_transparent_candidate_policy.v1` | Phase 3A |
| Research detection policy | `phase_3b_research_detection_policy.v1` | Phase 3B |
| Outcome-label policy | `phase_3b_outcome_label_policy.v1` | Phase 3B |
| Descriptive statistics policy | `phase_3c_descriptive_statistics_policy.v1` | Phase 3C |
| Interval policy | `phase_3c_interval_policy.v1` | Phase 3C |
| Sample-size policy | `phase_3c_sample_size_policy.v1` | Phase 3C |

If the IBKR bar-semantics resolution reveals that the existing intake contract cannot
honestly represent the collected bar data, a new policy version or contract extension
may be proposed. Any such change would:
1. Be documented in a focused proposal with explicit rationale
2. Preserve backward compatibility with existing Batch 01-06 artifacts
3. Not be used to fabricate or force acceptance of data whose semantics remain unknown

**A new Architecture Decision Record (ADR) is required before any intake-contract
extension is implemented.** This follows the precedent set in Phase 3C (ADRs 0053-0058)
and Phase 3D, where material design decisions were documented and frozen before
implementation. The ADR must cite the specific IBKR documentation that supports (or
fails to support) each semantic field, and must demonstrate that the extension does not
weaken validation for non-IBKR data sources.

## Symbol universe, identity, and evidence sources

### Universe

Exactly the 13 symbols from the archived scanner snapshot `screener_snapshot.json`
(captured `2026-07-18T13:37:55Z`): XNCR, PESI, SLS, ZNTL, GPRE, SSPC, LBGJ, TRVI,
LMNX, MGNX, BHVN, OBE, AVTX.

No additional symbols are added during Phase 3E. Expanding the symbol universe is left
to a future phase.

### Identity

IBKR contract identities are already resolved for all 13 symbols (distinct conIds,
primary exchanges confirmed in Batch 05). These identities are reused. The Phase 3D
identity-resolution policy is applied outcome-blind.

### Evidence sources

| Source | Status | Purpose |
|--------|--------|---------|
| IBKR TWS API (localhost:4001) | Authenticated and working | Historical trade bars for detection context and forward outcome |
| Archived scanner snapshot | Committed and frozen | Discovery metadata, candidate-level evidence |
| NewsAPI (if available) | Configured | Catalyst evidence for Phase 3A evaluation |
| SEC EDGAR (if available) | Configured | Catalyst evidence for Phase 3A evaluation |
| Finviz Elite (if available) | Configured (token status unknown) | Float and short-interest evidence |
| Finnhub (if available) | Configured | Supplementary evidence |

All evidence sources are queried outcome-blind. Forward bar acquisition is the only
new IBKR data request; all other evidence is constructed from already-collected or
already-configured sources.

### Evidence not available

The following evidence domains remain unavailable for these 13 symbols and are
recorded as honestly missing:
- Published short interest (FINRA/Exchange) — not in the scanner snapshot
- Days to cover — not computable without short interest
- Borrow fee — not in the scanner snapshot
- Borrow availability — not in the scanner snapshot
- Historical relative-volume baseline — not computable without extended bar history

These are preserved as `UNKNOWN` or `INSUFFICIENT_DATA` Phase 3A rule outcomes per the
existing policy. Missing evidence is never fabricated and never converted to `FAIL`.

## IBKR bar-semantics resolution

The Batch 06 IBKR semantics resolution established the following:

- **Price adjustment**: `SPLIT_ADJUSTED` (official IBKR documentation: TRADES data is
  adjusted for splits but not dividends).
- **Corporate-action handling**: `ADJUSTMENTS_APPLIED` (split adjustment is applied).
- **Timestamp representation**: Epoch seconds since 1/1/1970 GMT → `event_timezone =
  UTC`.
- **Session policy (requested)**: `EXTENDED` (useRTH=0).
- **Filtered-feed disclosure**: IBKR historical trade data is provider-filtered (trades
  away from NBBO excluded); recorded as limitation, not rejection.

The following fields remain unresolved:

- **Volume adjustment**: `UNKNOWN` — official docs state split adjustment for TRADES
  **price** only; volume corporate-action treatment is absent. Not inferred from price
  adjustment.
- **Bar start/end semantics**: `UNKNOWN` — only the daily-bar close-date rule is
  officially documented; intraday start/end is absent.
- **Volume unit**: `HISTORICAL_VOLUME_UNIT_UNRESOLVED` — the setting lives in IB
  Gateway's obfuscated binary and is not recoverable as safe plaintext.

Phase 3E will re-examine these unresolved fields. If official IBKR documentation or
the installed `ibapi` contract provides sufficient evidence to resolve any of them,
the resolution is recorded with explicit source citations. If they remain genuinely
unresolvable, Phase 3E will extend the intake contract to accept an honest `UNKNOWN`
declaration for these specific fields — with explicit provenance and without weakening
any broader validation — rather than continuing to emit a fatal
`MISSING_ADJUSTMENT_SEMANTICS` rejection.

The forward-outcome bar acquisition in Stage 2 uses the same resolved or unresolvable
semantic declarations consistently. Semantics are never resolved differently for
outcome bars than for detection-context bars.

## Evidence-layer construction plan

For each of the 13 symbols, the evidence layer is constructed as follows:

### Market bar evidence

1. Use the existing IBKR detection-context CSV artifacts (already collected in Batch 05,
   byte-hashes committed in the Batch 05 completion report).
2. Apply the resolved/admitted semantic declarations.
3. Run the existing Batch 03/04 intake pipeline to normalize the bars into the standard
   market-bar contract.
4. For symbols where the intake pipeline succeeds (`READY`), the bars become Phase 3A
   evidence for the `PRICE_RANGE`, `PERCENTAGE_CHANGE_MINIMUM`, `RELATIVE_VOLUME_MINIMUM`,
   `MARKET_DATA_AVAILABLE`, and `COMPLETED_BAR_AVAILABLE` rules.
5. For symbols where the intake pipeline remains `PREFLIGHT_REJECTED`, record the honest
   rejection reason and retain the symbol as registry-only.

### Short-interest and borrow evidence

The archived scanner snapshot contains limited short-interest and borrow metadata.
Where available, this evidence is extracted and normalized. Where absent, the
corresponding Phase 3A rules (`PUBLISHED_SHORT_INTEREST_AVAILABLE`,
`SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM`, `DAYS_TO_COVER_MINIMUM`,
`BORROW_FEE_MINIMUM`, `BORROW_FEE_CHANGE_MINIMUM`, `BORROW_AVAILABILITY_MAXIMUM`,
`BORROW_AVAILABILITY_CHANGE_MAXIMUM`) are honestly recorded as `UNKNOWN` or
`INSUFFICIENT_DATA` per the existing policy.

### Catalyst evidence

For each symbol, NewsAPI and SEC EDGAR are queried for catalyst evidence around the
detection boundary. The existing adapter infrastructure is used. News and filing
evidence before the frozen `evaluation_as_of` timestamp is included; evidence after
is excluded. The `CORPORATE_ACTION_CONTEXT_AVAILABLE` rule is evaluated from the
scanner snapshot if available.

### Evidence-validity metadata

The existing Phase 2D readiness infrastructure evaluates structural evidence
availability: domain presence, material conflicts, point-in-time eligibility, unit
compatibility, history sufficiency, default-substitution status, and provider scope.
These evaluations are reused unchanged.

## Phase 3A evaluation (outcome-blind)

For each symbol whose evidence layers are successfully constructed, the existing
`evaluate_candidate` function is called with the unchanged
`phase_3a_transparent_candidate_policy.v1`. Each rule result is recorded with the
standard Phase 3A outcome vocabulary (PASS, FAIL, UNKNOWN, CONFLICTED,
INSUFFICIENT_DATA, NOT_APPLICABLE). The evaluation result is frozen with its
deterministic identity and SHA-256 hash before any outcome data is accessed.

The Phase 3A evaluation does not compute a composite score, rank, recommendation, or
alert. It produces the standard 25-rule outcome vector with category summaries.

## Forward outcome bar acquisition (Stage 2 — after preregistration)

After this preregistration is committed, Stage 2 acquires forward outcome bars via the
IBKR authenticated connection.

### Acquisition protocol

- **Source**: IBKR TWS API via local IB Gateway (localhost port 4001)
- **Data type**: `whatToShow=TRADES`
- **Bar size**: `1 min`
- **Session**: `useRTH=0` (extended hours eligible)
- **Window**: 24 hours immediately following the frozen detection boundary timestamp
  (`2026-07-18T13:37:55Z` → `2026-07-19T13:37:55Z`)

### Window adjustment rule

If the 24-hour forward window falls on a non-trading day (weekend or holiday), the
window is shifted to the next available trading day. The shift is applied identically
to all symbols and is documented in the acquisition manifest. The shift is applied
before outcome computation and is not adjusted per-symbol to obtain favorable outcomes.

**Limitation acknowledged:** a shift from Saturday to Monday changes the forward window
from 24 hours to 72+ hours of calendar time, with only ~6.5 hours of trading session.
This materially changes the window definition and introduces a bias: the shifted window
captures more total market activity than a true 24-hour window would. This limitation
is documented and preserved; it is not remedied by further window manipulation.

### Outcome computation

Using the existing Phase 3B outcome-label policy
(`phase_3b_outcome_label_policy.v1`, `first_eligible_trade_bar_close_at_or_after_boundary.v1`,
24-hour horizon, +25% upward threshold, -25% downward threshold):

1. Compute the reference price (first eligible trade-bar close at or after the detection
   boundary).
2. For each bar in the forward window, compute the percentage return from the reference
   price.
3. Apply the outcome-label policy: `SUBSTANTIAL_UPWARD_MOVE`, `NO_SUBSTANTIAL_UPWARD_MOVE`,
   `MIXED_OR_VOLATILE`, `SUBSTANTIAL_DOWNWARD_MOVE`, `OUTCOME_INSUFFICIENT_DATA`, or
   `OUTCOME_UNKNOWN`.
4. Record the outcome in a separate outcome manifest (never merged with the Phase 3A or
   boundary-frozen evidence).

### Leakage audit

The existing Phase 3D leakage audit verifies:
1. The acquisition plan was frozen before outcome capture.
2. The boundary freeze was frozen before outcome capture.
3. The Phase 3A request was frozen before outcome capture.
4. The Phase 3A result was frozen before outcome capture.
5. The outcome manifest is a separate contract.

Any failure blocks empirical publication while retaining the attempted case in the
ledger. A leakage audit must pass before any case advances to Phase 3B publication.

## Publication to Phase 3B

Using the existing `squeeze_core.acquisition.publication` adapter:

### Registry candidates

All 13 symbols are registered in the Phase 3B registry, regardless of Phase 3A
evaluability. Registry-only symbols retain their honest incompleteness status. Symbols
with completed Phase 3A evaluations are registered with their frozen evaluation
identifiers.

### Dataset candidates

Only symbols that pass all of the following enter the Phase 3B dataset:
- Evidence layers constructed successfully (intake `READY`)
- Phase 3A evaluation completed and frozen
- Forward outcome bars acquired
- Outcome computed
- Leakage audit passed
- Non-synthetic (all 13 are real historical symbols)

### Research classification

The existing Phase 3B research classification truth table is applied. The research
detection policy (`phase_3b_research_detection_policy.v1`, requiring PRICE_RANGE,
MARKET_DATA_AVAILABLE, and COMPLETED_BAR_AVAILABLE all PASS) determines detection
status. The outcome label from Stage 2 and the detection status determine the research
classification (TP, FP, TN, FN, or UNEVALUABLE).

## Phase 3C descriptive analysis

After Phase 3B dataset candidates are populated, the existing Phase 3C descriptive
analysis pipeline is run on the expanded dataset:

- Historical case-boundary analysis (all 13 boundaries)
- Historical unique-symbol analysis (13 independent symbols, per
  `earliest_detection_boundary_per_symbol.v1`)
- All-registered data-quality analysis (including any remaining registry-only cases)
- Rule-outcome prevalence across the expanded cohort
- Missingness analysis with materially more data points
- Confusion-matrix descriptions (where denominators are nonzero)
- Wilson intervals (where sample sizes support)
- Sample-size assessments (expected: `LIMITED` at 13-20 symbols or `DESCRIPTIVE_ONLY`
  at 20-49)

All Phase 3C reports include the same required interpretation limitations established in
Phase 3C — no predictive validation, no causal claims, no threshold optimization.

## Curation lifecycle

The existing Phase 3D bundle lifecycle is used:
```
DISCOVERED → CAPTURED → NORMALIZED → IDENTITY_REVIEWED → ELIGIBILITY_REVIEWED →
BOUNDARY_FROZEN → EVALUATION_FROZEN → OUTCOME_CAPTURED → RESEARCH_EVALUATED →
REVIEWED → PUBLISHED
```

The 13 existing Phase 3D cases are at `REGISTRY_ONLY`. Phase 3E advances the eligible
subset through the remaining lifecycle states.

## Determinism and identity

All identities are UUIDv5 over canonical semantic inputs. Wall-clock time, absolute
paths, and random values never participate. The existing Phase 3A-3D identifier
conventions are used unchanged.

## Serialization

Canonical JSON with stable key ordering, exact Decimal strings, UTF-8, LF line endings.
Markdown reports with fixed section ordering and required interpretation language. The
existing Phase 3A-3D serializers are reused unchanged.

## Explicit non-goals

Phase 3E does not:

- Change Phase 3A thresholds, rules, or policies
- Change Phase 3B detection or outcome-label policies
- Change Phase 3C analysis policies
- Change Phase 3D acquisition policies
- Create composite scores, candidate rankings, or Prime/Subprime labels
- Generate recommendations or alerts
- Perform backtesting or P&L calculation
- Execute trading, order placement, or portfolio simulation
- Add machine learning, sentiment models, or technical indicators
- Add permanent live provider integrations beyond the existing IBKR connection
- Add database persistence or authentication infrastructure
- Expand the symbol universe beyond the 13 existing registry-only cases
- Fabricate missing evidence (short interest, borrow fee, borrow availability)
- Claim predictive validation or statistical significance from the expanded sample
- Begin Phase 3F

## Required interpretation language

Every Phase 3E analysis report must state:

- The 13 symbols were identified by a single archived scanner snapshot from 2026-07-18.
  They are not a random or representative sample of the US equity market.
- Missing short-interest, borrow, and float evidence means certain Phase 3A rules remain
  `UNKNOWN` or `INSUFFICIENT_DATA` for all 13 symbols. This does not imply a negative
  result for those rules.
- Phase 3A evaluation was limited to rules whose evidence was constructible from the
  available sources.
- Forward outcome bars were acquired from an authenticated IBKR connection. Bar
  semantics reflect the resolved official IBKR documentation where available, and
  honest `UNKNOWN` where not.
- Outcome confirmation does not prove short-squeeze causation or predictive validity.
- Rule prevalence does not prove predictive importance.
- Thresholds and policies remain unoptimized and provisional.
- The expanded cohort is descriptive-only unless and until the sample size supports
  statistical estimation (currently `LIMITED` or `DESCRIPTIVE_ONLY`).
- No P&L, backtest, entry, exit, recommendation, or trading simulation was performed.
- Phase 3E is a systematic evidence-construction phase. It does not validate the
  research methodology.

## Test plan

Phase 3E tests exercise the following areas. A focused `tests/acquisition_phase3e/` or
extensions to `tests/acquisition/` are established during implementation.

1. **IBKR bar-semantics resolution extension (if needed).** If the intake contract is
   extended to accept honest `UNKNOWN` semantics, tests verify:
   - The extension accepts `UNKNOWN` declarations with explicit provenance.
   - The extension does not accept fabricated or inferred values.
   - All existing Batch 01-06 artifacts still pass validation (backward compatibility).
   - Non-IBKR data sources remain governed by the original validation rules.

2. **Evidence-layer construction.** For each symbol, tests verify:
   - The constructed evidence is outcome-blind (no price returns, no threshold crossings).
   - Missing evidence domains are recorded as `UNKNOWN`, not `FAIL`.
   - Evidence timestamps respect the frozen `evaluation_as_of` boundary.

3. **Phase 3A evaluation freeze.** Tests verify:
   - The evaluation result is frozen with deterministic identity and SHA-256 hash.
   - The frozen result is identical when regenerated (byte-identical repeat).
   - No outcome data enters the frozen evaluation.

4. **Forward outcome acquisition (Stage 2).** Tests verify:
   - The acquisition follows the preregistered protocol (data type, bar size, session).
   - The window adjustment rule is applied uniformly before outcome computation.
   - The outcome manifest is a separate contract from the evaluation freeze.

5. **Leakage audit.** Tests verify:
   - Plan, boundary, Phase 3A request, and Phase 3A result were frozen before outcome.
   - Any ordering violation blocks empirical publication.

6. **Compatibility.** All Phase 1-3D tests and anchors remain unchanged.

## Completion criteria

Phase 3E is complete only when:

1. Branch `phase/3e-systematic-historical-acquisition` exists and this preregistration
   is committed.
2. The IBKR bar-semantics extension (if needed) is designed, implemented, tested, and
   documented, or the honest unresolvable status is accepted with a contract extension.
3. Evidence layers are constructed for all 13 symbols where possible.
4. Intake manifests are finalized and preflight results are recorded.
5. Phase 3A evaluation is completed and frozen for all `READY` symbols.
6. Stage 2 (forward outcome acquisition) has a dedicated batch-level acquisition plan
   committed before any outcome data is fetched.
7. Forward outcome bars are acquired and outcome labels are computed.
8. Leakage audit passes for all eligible cases.
9. Phase 3B research registry and dataset candidates are populated.
10. Phase 3C descriptive analysis is run on the expanded dataset.
11. All deterministic outputs regenerate byte-identically.
12. All prior Phase 1-3D anchors remain unchanged.
13. Archived repositories (SHA `0897562e...`, `6dbefd1...`, `84f770d...`) remain
    at their required commits.
14. Full test suite passes with no regressions.
15. Working tree is clean. No remotes are added. Nothing is pushed or merged.

## Non-blocking conditions

The following are expected limitations, not blockers:

- Some or all of the 13 symbols may remain `PREFLIGHT_REJECTED` after the IBKR
  semantic resolution extension. Registry-only status for unresolvable symbols is an
  honest outcome, not a failure.
- Some or all forward-outcome windows may land on non-trading days, requiring window
  adjustment. The adjustment and its rationale are documented.
- Zero complete Phase 3B dataset candidates (if all symbols remain registry-only or
  all forward outcome acquisitions fail) is a valid outcome. It honestly reflects the
  current evidence availability.
- Undefined descriptive rates, wide confidence intervals, and `ONE_OBSERVATION`
  sample-size assessments are expected and must remain explicit.

# Phase 3E — Evidence-Readiness Audit for 13 Registry-Only Symbols

**Audit date:** 2026-07-26
**Branch:** `phase/3e-systematic-historical-acquisition`
**Outcome-blinding status:** No outcome data was accessed, inspected, or computed during this audit. All findings
are derived from preregistered Phase 3D acquisition artifacts, the archived scanner snapshot, and IBKR bar-semantics
records — all of which were frozen before any outcome information was available.

## Executive summary

All 13 Phase 3D pilot symbols share the same evidence-readiness profile: they are `SUFFICIENT_FOR_REGISTRY_ONLY`,
with `phase_3a_request_constructible = false` for every symbol. The single critical blocker is the absence of
`NORMALIZED_POINT_IN_TIME_EVIDENCE` — the normalized market-bar, metric, and structural-evidence layers required to
construct a Phase 3A evaluation request.

Phase 3E Stage 1 can construct this missing evidence layer for all 13 symbols using the already-collected IBKR
historical bar CSVs (detection-context) combined with the archived scanner snapshot for candidate-level metadata
and existing public provider adapters (NewsAPI, SEC EDGAR, Finnhub) for catalyst evidence.

However, two additional blockers must be addressed first:

1. **IBKR bar-semantics resolution.** All 26 preflights are `PREFLIGHT_REJECTED` with
   `MISSING_ADJUSTMENT_SEMANTICS` because volume adjustment and bar start/end semantics remain honestly
   `UNKNOWN`. Until the intake contract accepts honest `UNKNOWN` declarations for these fields (with
   explicit provenance and backward compatibility), the IBKR bar data cannot be normalized into the
   `MARKET_BARS` evidence domain.

2. **Short-pressure evidence permanently missing.** Published short interest, borrow fee, and borrow
   availability are not present in the scanner snapshot and cannot be obtained from any available source
   for these historical dates. The corresponding Phase 3A rules will remain `UNKNOWN` or
   `INSUFFICIENT_DATA` for all 13 symbols regardless of other evidence construction.

## Phase 3A evidence-domain requirements

Phase 3A evaluates 25 rules across 4 categories. The rules require evidence from these domains:

| Phase 3A category | Rules | Required evidence domains |
|---|---|---|
| Momentum discovery | PRICE_RANGE, PERCENTAGE_CHANGE_MINIMUM, RELATIVE_VOLUME_MINIMUM, FLOAT_MAXIMUM, MARKET_DATA_AVAILABLE, COMPLETED_BAR_AVAILABLE | `MARKET_BARS`, `CANDIDATE_SNAPSHOT` |
| Short-pressure confirmation | PUBLISHED_SHORT_INTEREST_AVAILABLE, SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM, DAYS_TO_COVER_MINIMUM, BORROW_FEE_MINIMUM, BORROW_FEE_CHANGE_MINIMUM, BORROW_AVAILABILITY_MAXIMUM, BORROW_AVAILABILITY_CHANGE_MAXIMUM | `PUBLISHED_SHORT_INTEREST`, `BORROW_FEE`, `BORROW_AVAILABILITY` |
| Catalyst evidence | NEWS_AVAILABLE, NEWS_AVAILABLE_BEFORE_AS_OF, NEWS_TIMESTAMP_KNOWN, SEC_FILING_AVAILABLE, CORPORATE_ACTION_CONTEXT_AVAILABLE | `NEWS`, `SEC_FILINGS` |
| Evidence validity | REQUIRED_DOMAINS_PRESENT, NO_MATERIAL_CONFLICTS, POINT_IN_TIME_ELIGIBLE, REQUIRED_UNITS_COMPATIBLE, REQUIRED_HISTORY_SUFFICIENT, NO_DEFAULT_SUBSTITUTION, PROVIDER_SCOPE_EXPLICIT | Structural (derived from above) |

The Phase 2D readiness infrastructure evaluates domain coverage, evidence age, reporting-period alignment,
conflicts, missingness, and input sufficiency for each operation (e.g., `percentage-return`, `relative-volume`,
`short-interest-change`, etc.) against an explicit `OperationRequirementPolicy`.

## Current evidence state (from Phase 3D Batch 01 sufficiency review)

### Per-symbol evidence profile (identical for 11 of 13 symbols)

| Attribute | Value |
|---|---|
| Sufficiency state | `SUFFICIENT_FOR_REGISTRY_ONLY` |
| Phase 3A request constructible | `false` |
| Outcome only available | `false` |
| Identity state | `PARTIALLY_RESOLVED` — ticker resolved; issuer, exchange, and security type absent |
| **Present domains** | `DETECTION_BOUNDARY`, `DETECTION_TIME_MARKET_SNAPSHOT`, `DISCOVERY` |
| **Missing domains** | `IB_BORROW_FEE_RATE`, `IB_SHORTABLE_SHARES`, `ISSUER_EXCHANGE_IDENTITY`, `NORMALIZED_POINT_IN_TIME_EVIDENCE`, `RETROSPECTIVE_OUTCOME_WINDOW`, `SCHWAB_HTB_QUANTITY` |
| Exclusion codes | `CASE_REQUIRES_FABRICATED_EVIDENCE` |
| Satisfied conditions | `ARTIFACTS_VALID`, `BOUNDARY_AVAILABLE`, `DISCOVERY_PROVENANCE`, `MARKET_EVIDENCE`, `WITHIN_DATE_RANGE`, `WITHIN_POPULATION` |
| Missing conditions | `PHASE_3A_REQUEST_CONSTRUCTIBLE` |
| Discovery source | `ARCHIVED_MARKET_SCANNER` |
| Platform status | `SURFACED` |
| Artifact validation | `passed` |
| Identity claims | Single claim per symbol, no conflicts, no symbol-reuse risk |

### Two symbols with additional missing domains

**LMNX (BATCH01_LMNX_20260718)** and **SSPC (BATCH01_SSPC_20260718)** have two additional missing domains:

| Missing domain | Relevance |
|---|---|
| `DAYS_TO_COVER` | Required for DAYS_TO_COVER_MINIMUM rule |
| `SHORT_FLOAT_PERCENT` | Display-only field; not a required Phase 3A input |

These additional missing domains do not materially change the sufficiency assessment because
`phase_3a_request_constructible` is already `false` for all symbols due to the
`NORMALIZED_POINT_IN_TIME_EVIDENCE` gap, and short-pressure evidence is already missing for all symbols.

## Evidence-domain detail

### Present domains

| Domain | Source | Contents |
|---|---|---|
| `DETECTION_BOUNDARY` | Phase 3D boundary-freeze manifest | Frozen `ORIGINAL_PLATFORM_SURFACED_TIMESTAMP = 2026-07-18T13:37:55.017661Z` for all 13 symbols |
| `DETECTION_TIME_MARKET_SNAPSHOT` | Archived scanner snapshot | Point-in-time scanner row: price, volume, change, float, short-interest metadata present |
| `DISCOVERY` | Archived scanner snapshot | Discovery provenance: scanner query definition, source order, platform-surfaced status |

### Constructible domains (Phase 3E Stage 1 target)

| Domain | Source | Construction path | Blockers | Status |
|---|---|---|---|---|
| `MARKET_BARS` | IBKR detection-context CSVs (Batch 05) | Normalize through Batch 03/04 intake pipeline | **Volume adjustment UNKNOWN**; **Bar start/end UNKNOWN**; Intake contract rejects these as fatal `MISSING_ADJUSTMENT_SEMANTICS` | **BLOCKED** — requires IBKR semantics resolution or contract extension |
| `NEWS` | NewsAPI | Existing adapter; query for each symbol before boundary timestamp | Boundary falls on Saturday; news coverage near weekend is unpredictable | Potentially constructible with no-code changes |
| `SEC_FILINGS` | SEC EDGAR | Existing adapter; query for each symbol before boundary timestamp | Some symbols may have no filings near the boundary | Potentially constructible with no-code changes |
| `CANDIDATE_SNAPSHOT` | Archived scanner snapshot | Extract float from snapshot row | Float present in snapshot; can be extracted without fabrication | **AVAILABLE** — needs extraction and normalization |
| `CORPORATE_ACTION_CONTEXT` | Scanner snapshot / public sources | Corporate actions (splits, mergers) near boundary | Not systematically available | Unknown |

### Permanently missing domains (no viable source)

| Domain | Reason |
|---|---|
| `PUBLISHED_SHORT_INTEREST` | FINRA/Exchange short interest data not present in scanner snapshot; no historical archive available |
| `BORROW_FEE` | Borrow fee not present in scanner snapshot; IBKR borrow fee requires account-level access |
| `BORROW_AVAILABILITY` | Borrow availability not present in scanner snapshot; requires provider-specific data access |
| `IB_BORROW_FEE_RATE` | IBKR-specific borrow fee rate; not available from non-account API surface |
| `IB_SHORTABLE_SHARES` | IBKR-specific shortable shares; not available from non-account API surface |
| `SCHWAB_HTB_QUANTITY` | Schwab hard-to-borrow quantity; not available from available sources |
| `ISSUER_EXCHANGE_IDENTITY` | Issuer name, exchange, security type not available from scanner snapshot alone |

### Future-available domains (Stage 2 target, outcome-blinded)

| Domain | Source | Required before access |
|---|---|---|
| `RETROSPECTIVE_OUTCOME_WINDOW` | IBKR forward bars | Phase 3E Stage 2 batch-level acquisition plan must be committed |

## Per-symbol evidence breakdown

All 13 symbols share the identical evidence profile described above. The only distinguishing characteristics are:

| Symbol | Primary exchange (from Batch 05) | conId | Scanner order | Additional missing domains |
|---|---|---|---|---|
| XNCR | NASDAQ | 139508766 | 1 | none |
| PESI | NASDAQ | 136257468 | 2 | none |
| SLS | NASDAQ | 390872440 | 3 | none |
| ZNTL | NASDAQ | 415881332 | 4 | none |
| GPRE | NASDAQ | 38333348 | 5 | none |
| SSPC | BATS | 891519449 | 6 | DAYS_TO_COVER, SHORT_FLOAT_PERCENT |
| LBGJ | NASDAQ | 868499891 | 7 | none |
| TRVI | NASDAQ | 364036151 | 8 | none |
| LMNX | NASDAQ | 823013254 | 9 | DAYS_TO_COVER, SHORT_FLOAT_PERCENT |
| MGNX | NASDAQ | 136046701 | 10 | none |
| BHVN | NYSE | 586873967 | 11 | none |
| OBE | AMEX | 369218017 | 12 | none |
| AVTX | NASDAQ | 674693864 | 13 | none |

None of these distinguishing characteristics affect the evidence-readiness assessment. All 13 symbols share:
- The same present domains (DETECTION_BOUNDARY, DETECTION_TIME_MARKET_SNAPSHOT, DISCOVERY)
- The same state (SUFFICIENT_FOR_REGISTRY_ONLY)
- The same critical blocker (NORMALIZED_POINT_IN_TIME_EVIDENCE missing → phase_3a_request_constructible = false)
- The same exclusion code (CASE_REQUIRES_FABRICATED_EVIDENCE)

## Phase 3A rule-level outcome prediction (without fabrication)

Based on the evidence available today (before evidence construction), here is the honest expected outcome for
each Phase 3A rule category assuming the NORMALIZED_POINT_IN_TIME_EVIDENCE blocker is resolved:

### Momentum discovery

| Rule | Expected outcome | Basis |
|---|---|---|
| PRICE_RANGE | EVALUABLE (PASS/FAIL) | IBKR bars provide price data; threshold: $2–$20 |
| PERCENTAGE_CHANGE_MINIMUM | EVALUABLE (PASS/FAIL) | IBKR bars enable percentage-return calculation; threshold: ≥10% |
| RELATIVE_VOLUME_MINIMUM | LIKELY INSUFFICIENT_DATA | Needs trailing-window baseline; 1 day of bars likely insufficient for the requested window |
| FLOAT_MAXIMUM | EVALUABLE (PASS/FAIL) | Float available from scanner snapshot; threshold: ≤20M shares |
| MARKET_DATA_AVAILABLE | PASS (bars exist) | IBKR bars confirmed at 1,000+ per symbol |
| COMPLETED_BAR_AVAILABLE | PASS (completed bars exist) | IBKR bars are historical completed bars |

### Short-pressure confirmation

All 7 rules in this category will be **UNKNOWN** or **INSUFFICIENT_DATA** for all 13 symbols because the
required evidence domains (PUBLISHED_SHORT_INTEREST, BORROW_FEE, BORROW_AVAILABILITY) are permanently missing
from all available sources. This is an honest limitation, not a failed condition.

### Catalyst evidence

| Rule | Expected outcome | Basis |
|---|---|---|
| NEWS_AVAILABLE | Depends on NewsAPI coverage | Some symbols may have news; others may not |
| NEWS_AVAILABLE_BEFORE_AS_OF | Depends on NewsAPI coverage | Needs news with timestamp before 2026-07-18T13:37:55Z |
| NEWS_TIMESTAMP_KNOWN | Depends on NewsAPI coverage | Most NewsAPI articles have timestamps |
| SEC_FILING_AVAILABLE | Depends on SEC EDGAR coverage | Some symbols may have filings near boundary |
| CORPORATE_ACTION_CONTEXT_AVAILABLE | **UNKNOWN** | Not systematically available from scanner snapshot |

### Evidence validity

All 7 validity rules derive from the structural state of the evidence bundle. They will be EVALUABLE once
the evidence bundle is constructed, because they check for presence, conflicts, compatibility, and
point-in-time eligibility of whatever evidence is available. These rules will honestly report any
deficiencies in the underlying evidence.

## Specific blockers to reaching Phase 3A evaluable status

### Blocker 1: IBKR intake preflight rejection (resolution path: Phase 3E Stage 1)

**What:** The Batch 03/04 intake contract requires `price_adjustment_semantics`, `volume_adjustment_semantics`,
and `timestamp_semantics` to be non-`UNKNOWN`. While price adjustment is resolved to `SPLIT_ADJUSTED`,
volume adjustment and bar start/end semantics remain honestly `UNKNOWN` (no official IBKR documentation
establishes their values).

**Resolution options:**
1. **ADR and contract extension.** Write an ADR documenting that official IBKR documentation is silent on
   volume adjustment for TRADES bars and intraday bar start/end semantics. Extend the intake contract to
   accept an honest `UNKNOWN` declaration for these fields with explicit provenance — without weakening
   validation for non-IBKR data sources.
2. **Re-examine official docs.** Re-check the installed `ibapi` source and official IBKR documentation for
   any overlooked evidence about volume adjustment or bar timestamp semantics.

**If unresolved:** All 13 symbols remain `PREFLIGHT_REJECTED` and `REGISTRY_ONLY`. This is an honest outcome
but prevents any Phase 3A evaluation.

### Blocker 2: Market-bar normalization and metric computation (resolution path: Phase 3E Stage 1)

**What:** Even after intake contract acceptance, the IBKR detection-context CSVs must be normalized into
standard `MARKET_BARS` observations, and Phase 2A/2B metrics (percentage return, relative volume, etc.)
must be computed from those bars.

**Resolution:** This is straightforward engineering using the existing `squeeze_core.evidence.bars`,
`squeeze_core.metrics`, and `squeeze_core.readiness` infrastructure. No novel research decisions are
required.

**If unresolved:** Phase 3A evaluation cannot proceed. This is an engineering blocker, not a research blocker.

### Blocker 3: Short-pressure evidence permanently missing (no resolution path)

**What:** Published short interest, borrow fee, and borrow availability are not available from any lawful
public non-authenticated source for these historical dates (Phase 3D Batch 02 exhaustively searched).

**Impact:** Rules PUBLISHED_SHORT_INTEREST_AVAILABLE, SHORT_INTEREST_PERCENTAGE_CHANGE_MINIMUM,
DAYS_TO_COVER_MINIMUM, BORROW_FEE_MINIMUM, BORROW_FEE_CHANGE_MINIMUM, BORROW_AVAILABILITY_MAXIMUM, and
BORROW_AVAILABILITY_CHANGE_MAXIMUM will be `UNKNOWN` or `INSUFFICIENT_DATA` for all 13 symbols regardless of
other evidence construction.

**Note:** Per the Phase 3A rule policy, `UNKNOWN` and `INSUFFICIENT_DATA` are valid outcomes. They are not
`FAIL`. This is an honest limitation, not a research defect.

### Blocker 4: Forward outcome window unavailable until Stage 2 (by design)

**What:** The `RETROSPECTIVE_OUTCOME_WINDOW` domain is intentionally not populated during the outcome-blind
Stage 1. Forward outcome bars require authenticated IBKR access after the Stage 2 batch-level acquisition
plan is committed.

**Impact:** Phase 3B research classification (TP, FP, TN, FN) and Phase 3C confusion-matrix analysis are
not possible until Stage 2 completes. Phase 3A evaluation is possible without outcomes.


## Phase 3A evaluability summary by symbol

After Stage 1 evidence construction (assuming Blockers 1 and 2 are resolved):

| Symbol | Phase 3A evaluable? | Momentum rules evaluable? | Short-pressure rules | Catalyst rules | Validity rules |
|---|---|---|---|---|---|
| XNCR | Yes | 5 of 6 evaluable | All UNKNOWN | Conditional | Evaluable |
| PESI | Yes | 5 of 6 evaluable | All UNKNOWN | Conditional | Evaluable |
| SLS | Yes | 5 of 6 evaluable | All UNKNOWN | Conditional | Evaluable |
| ZNTL | Yes | 5 of 6 evaluable | All UNKNOWN | Conditional | Evaluable |
| GPRE | Yes | 5 of 6 evaluable | All UNKNOWN | Conditional | Evaluable |
| SSPC | Yes | 5 of 6 evaluable | All UNKNOWN | Conditional | Evaluable |
| LBGJ | Yes | 5 of 6 evaluable | All UNKNOWN | Conditional | Evaluable |
| TRVI | Yes | 5 of 6 evaluable | All UNKNOWN | Conditional | Evaluable |
| LMNX | Yes | 5 of 6 evaluable | All UNKNOWN | Conditional | Evaluable |
| MGNX | Yes | 5 of 6 evaluable | All UNKNOWN | Conditional | Evaluable |
| BHVN | Yes | 5 of 6 evaluable | All UNKNOWN | Conditional | Evaluable |
| OBE | Yes | 5 of 6 evaluable | All UNKNOWN | Conditional | Evaluable |
| AVTX | Yes | 5 of 6 evaluable | All UNKNOWN | Conditional | Evaluable |

"Momentum rules evaluable" means the rule can return PASS, FAIL, or INSUFFICIENT_DATA based on available
evidence (as opposed to UNKNOWN due to missing evidence domains). RELATIVE_VOLUME_MINIMUM will likely be
INSUFFICIENT_DATA due to limited bar history — this is still an evaluable outcome (it honestly reports the
state of available data). PERCENTAGE_CHANGE_MINIMUM is evaluable because IBKR bars provide closes for
return calculation. The 5 of 6 count includes all momentum rules except PRICE_RANGE (which may also be
evaluable if price falls within 2–20 range; included in the 5).

"Conditional" for catalyst rules means evaluability depends on whether NewsAPI/SEC EDGAR return data for
that specific symbol near the detection boundary. Some symbols may have catalyst evidence; others may not.

## Required actions for Phase 3E Stage 1

Ordered by dependency:

1. **Resolve IBKR bar semantics.** Re-examine official IBKR documentation and the installed `ibapi` contract
   for any evidence about volume adjustment or intraday bar timestamp semantics. If genuinely unresolvable,
   write the ADR and extend the intake contract to accept honest `UNKNOWN` declarations.

2. **Normalize IBKR bars into MARKET_BARS.** Run the 13 detection-context CSVs through the existing intake
   pipeline after the contract extension. Produce normalized bar observations for each symbol.

3. **Construct evidence bundle.** Build a `PointInTimeEvidenceBundle` for each symbol containing:
   - Market bars from step 2
   - Candidate snapshot data from scanner snapshot (float, price, volume)
   - News from NewsAPI (if available)
   - SEC filings from SEC EDGAR (if available)
   - Structural evidence-validity metadata

4. **Run Phase 2D readiness evaluation.** Run the existing coverage, age, conflict, missingness, and
   sufficiency infrastructure on each constructed evidence bundle.

5. **Finalize intake manifest.** Produce `READY` or `PREFLIGHT_REJECTED` with explicit reason codes.

6. **Freeze Phase 3A evaluation.** For each `READY` symbol, construct the Phase 3A request, run
   `evaluate_candidate`, and freeze the result with its deterministic identity and SHA-256 hash.

## Outcome-blind verification

This audit accessed only:
- Phase 3D preregistered and committed artifacts (batch 01 fixtures: sufficiency-review, eligibility-review,
  identity-review, source-manifest, case-attempt-ledger, batch-summary, curation-report)
- Phase 3A rule policy JSON (phase_3a_transparent_candidate_policy_v1.json)
- IBKR bar-semantics documents (batch-05-ibkr-collection-summary.md, batch-06-official-ibkr-semantics-evidence.md)
- Evidence model definitions (CoverageDomain enum, PointInTimeEvidenceBundle, readiness models)
- Acquisition model definitions (EvidenceSufficiencyReview, EligibilityContext, EligibilityDecision)
- Phase 3E design document (phase-3e-design.md)

No forward outcome data, price-return data, threshold-crossing computations, or retrospective outcome labels
were accessed, inspected, or computed during this audit.

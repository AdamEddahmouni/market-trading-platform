# IMP master architecture

| Field | Value |
|---|---|
| Document ID | `IMP-ARCHITECTURE` |
| Classification | `CANONICAL` |
| Primary Truth Class | `CURRENT_CANONICAL_TRUTH` |
| Canonical Subject | Whole-program composition and architectural relationships |
| Establishing Milestone | `IMP-REBASE-01` |
| Version | `1.6` |
| Last Verified | `2026-09-21` |
| Supersedes | No accepted post-EVIDENCE whole-program architecture |
| Superseded By | None |

This document explains how IMP fits together. It does not define policy values
or grant runtime authority. Executable authorities listed in the
[Canonical Truth Map](CANONICAL_TRUTH_MAP.md) control their own behavior.

## State labels

- `IMPLEMENTED`: code or an executable contract exists. The label does not by
  itself imply validation, qualification, or production eligibility.
- `PARTIAL`: reusable foundations exist, but the program family lacks a
  universal consolidated authority or system.
- `ABSENT`: the named program capability is not present.
- `APPROVED_FUTURE_DESIGN`: an accepted direction that is not implemented by
  this document.

## End-to-end shape

```text
[IMPLEMENTED] sources and provider boundaries
       |
       v
[IMPLEMENTED] ingestion, envelopes, clocks, admission and normalization
       |
       v
[IMPLEMENTED] temporal/provenance/quality contracts and canonical state
       |
       +--------------------------+
       |                          |
       v                          v
[IMPLEMENTED] intelligence,   [IMPLEMENTED] prediction ledger
hypotheses and models              |
       |                          v
       |                    [IMPLEMENTED] evidence campaigns
       |                          |
       |                          v
       |                    [IMPLEMENTED] outcome settlement
       +-------------+------------+
                     |
                     v
       [IMPLEMENTED foundations / PARTIAL family]
       opportunity detection and Real-Time Opportunity Fabric
                     |
                     v
       [IMPLEMENTED] risk and execution-state authorities
                     |
                     v
       [IMPLEMENTED guarded paper/mock paths]
       [ABSENT production live broker transport]
                     |
                     v
       [IMPLEMENTED] reconciliation foundations
                     |
                     v
       [IMPLEMENTED standards / PARTIAL family]
       operations, runbooks and Operating Fabric
                     |
                     v
       [IMPLEMENTED] read-only UI and assistant surfaces
```

Broker acceptance, rejection, or fill is external reality. When a broker path is
used, that reality must flow through reconciliation before it becomes canonical
state. A provider connection, signal, forecast, release approval, or UI mode is
never a substitute for that flow.

## Operator workflow surface map

This table maps the explanatory end-to-end flowchart onto current operator
surfaces. It is comprehension, not permission to rewrite working code so it
resembles a diagram. Missing boxes are classified; they are not automatically
defects.

| Flowchart stage | Current operator surface | Honesty / classification |
|---|---|---|
| Market + information sources | Control diagnostics; Lab hops; Path A / FTEP CLIs | Provenance and provider health are implemented. Live market wires remain gated/`LIVE_PROVIDER_UNVERIFIED` in several lanes. **docs/UI comprehension** if a surface looks like a universal live tape. |
| Ingestion / normalization / processing | Observation ingress router; EventV1/PIT admission; G6–G11 observational runtime | Foundations exist. There is still **no production ingest bus** for every normalize path (intentional implementation detail / later OF work). |
| Research + strategy analysis | Research, Lab, admitted fixtures, historical-research harness | Multi-strategy capable. Campaign assumptions (Item 9 / AAPL / ES) must stay campaign-scoped. **docs** if research copy implies a single-strategy product. |
| Candidate opportunities | Radar Screeners / Discover mixed (`INVESTIGATE`, `execution_authority=NONE`) | Candidates are investigation-only. They are **not** Opportunity Engine mint. Weekend copy already labels this; leftover donor catalyst overlay on Research screens is a separate honesty lane. **UI comprehension**. |
| Opportunity Engine | Radar queue / NOW / `GET /opportunities*`; Path A `OpportunityEngine.assess` | Demo/Paper review loop is implemented. Live GET stays empty `UNAVAILABLE`. STALE/UNKNOWN cannot stay ELIGIBLE. Path A MATCHED ≠ empirical PRODUCTION hop. **intentional implementation detail** plus remaining **real gap**: no production ingest bus, no FTEP-tuned ranking numerics. |
| Operator decision | Radar watch/dismiss/review ack; Workspace Paper draft | Observational lifecycle is allowed in Live without broker execution. Workspace is the Paper submit boundary. **UNAVAILABLE** eligibility must not open workspace/ack ([#358](https://github.com/AdamEddahmouni/market-trading-platform/pull/358)). |
| Execution | Workspace Paper submit; internal simulator; Alpaca Paper comparator | Guarded Paper/mock paths implemented. Production live broker transport is **ABSENT**. Live is OFF for governance/readiness, not because execution is outside product scope. No AI-independent live orders. **real implementation gap** for live broker transport. |
| Monitoring / lifecycle | Radar, Portfolio, Control, execution traces, trade review | Paper lifecycle reconstructable. Live observational monitoring exists. Unified opportunity→risk→order_ready tracing remains **PARTIAL** (technical debt / RT-01 follow-on). |
| Evidence / outcomes | Research evidence, OF-01 ledger, FTEP/Item 9 receipts, prediction settlement | Evidence classes stay distinct. Prospective Item 9 collection is frozen at collector `fed2d9f7`, not current software. **docs** if operator SHA tables lag `origin/main`. |
| Controlled improvement | Lab, historical-research harness, findings queues | No automated promotion of `CANDIDATE` → `VERIFIED` and no production auto-learning loop. **real implementation gap** (controlled, not autonomous). |

Primary IA (Command, Radar, Workspace, Portfolio, Research, Lab, Control) is
the operator mental model. `/explore` redirects into Radar screeners. Cross-
cutting provenance, freshness, risk/governance, observability, and operator
control already exist as contracts; UI must keep `UNKNOWN`/`UNAVAILABLE`/`STALE`
visible rather than coercing a pass.

The P6 Shadow Run 1 forward-observation campaign is deferred, not active.
Its protocol and historical records remain preserved as evidence artifacts and
do not change the current runtime architecture or grant execution authority.

## Two different fabrics

The **Real-Time Opportunity Fabric** is the data-to-decision-support path. It
owns bounded callback ingestion, observational state, feature calculation,
detection, routing, opportunity economics, and the ingest-path timing baseline.
It is `PARTIAL` because accepted tracing covers executable ingest paths only;
no accepted trace spans the unified opportunity→risk→order_ready chain or
broker/reconciliation stages. Follow-on work extends RT-01 rather than replacing
its ingest-path baseline. G8 attaches IBKR observational L1/L2 through an outer
`tools/ibkr` bootstrap that injects `IbkrObservationalTransport` into canonical
`live_runtime` / `ObservationalRuntimeComposition`; src does not import tools
implementation. G11 adds a separate read-only query injection path
(`IbkrReadOnlyQueryProvider` → `IbkrObservationalQueryService`) for
contract/secdef, historical bars, and read-only account observation; outer
`tools/ibkr/query_provider.py` implements the protocol; registration occurs
only in `runtime_bootstrap.py` (src never imports tools). Provider account
facts are observational only and cannot mutate canonical portfolio state. Live
IBKR remains `LIVE_PROVIDER_UNVERIFIED`.

The **Operating Fabric** is the operation-to-evidence control plane. OF-01
provides the append-only run/artifact ledger, OF-02 attributes existing
subsystems onto that ledger, and OF-03 indexes governed capabilities, SOPs, and
workflows. RT-01 adds causal trace and latency instrumentation for executable
ingest paths. Existing run manifests, schedulers, pipelines, health controls,
runbooks, and release operations remain reusable. The family is still `PARTIAL`
because unified opportunity-risk-order_ready tracing is not accepted. OF-03 does
not execute workflows or grant domain authority.

Neither fabric grants order authority. Their detailed responsibility boundaries
are in [System Boundaries](SYSTEM_BOUNDARIES.md).

## Workload classes

`HOT`, `WARM`, and `COLD` describe architectural workloads, not performance
guarantees:

- `HOT`: bounded state and processing needed for current observations and
  time-sensitive projections.
- `WARM`: recent durable state, derived features, evaluation, and operator
  context that can tolerate non-immediate processing.
- `COLD`: immutable evidence, historical datasets, manifests, reports, and
  reproducibility records.

No latency target is implied. `IMP-RT-01` accepted fixture baseline measurements
for executable ingest paths; `IMP-RT-02` may optimize only after measured need
and `IMP-RT-03` may consider an event bus or native hot path only if measured
need remains.

## Required reuse

New program families must extend rather than fork these foundations:

| Concern | Reusable authority or foundation |
|---|---|
| Event and temporal semantics | [`EventV1`](../../src/market_platform_foundation/intelligence/contracts/event.py), temporal contracts, and point-in-time validation |
| Provenance and normalization | [`ProviderProvenance`](../../src/market_platform_foundation/intelligence/normalization/models.py) and provider envelopes |
| Quality and capability | Shared quality models plus domain extensions and provider capability contracts; **`ProviderRegistry`** holds implemented-capability metadata; **`RuntimeCapabilityRegistry`** (G7) is the runtime-state/readiness facade over that authority; **`VerifiedCapabilityRegistry`** holds bounded Moomoo probe evidence only — not a competing runtime-capability authority |
| Prediction | [`PredictionLedgerEntryV1`](../../src/market_platform_foundation/intelligence/contracts/prediction_ledger.py) |
| Settlement | [`OutcomeSettlementService`](../../src/market_platform_foundation/intelligence/outcomes/service.py) |
| Risk and execution state | Risk, execution, live-safety, authorization, and confirmation implementations indexed by the truth map |
| External-state closure | Reconciliation authorities under `portfolio/`, `platform/reconciliation/`, and live-canary reconciliation |
| Reproducibility | [Reproducibility and Run Standard](REPRODUCIBILITY_AND_RUN_STANDARD.md) defines run, attempt, outcome, disposition, artifact, and reproducibility semantics; existing run manifests, frozen policies, hashes, validation reports, and campaign records remain authoritative within their scope; future ledger work indexes them rather than replacing them |
| Observability | [Observability Standard](OBSERVABILITY_STANDARD.md) defines logs, metrics, traces, and correlation semantics; RT-01 provides accepted ingest-path causal tracing and latency profiles; platform-wide propagation beyond ingest remains follow-on work |
| Test and evaluation | [Test and Evaluation Standard](TEST_AND_EVALUATION_STANDARD.md) defines validation, benchmark, backtest, replay, and evaluation semantics; executable validation remains under `tools/validate.py` |

## Family attachment points

- **Cross-Asset — `PARTIAL`.** IMP-XA-01 implements the cross-asset canonical
  identity and analytical-domain participation kernel
  (`src/market_platform_foundation/xa01`), extended (G1) with one canonical
  asset-class vocabulary (`CRYPTO`, `BOND` added; paper `ASSET_CLASSES`
  deprecated as a compatibility view), first-class crypto pair identity
  (base/quote/venue/network), typed bond/fixed-income identity (issuer,
  CUSIP/ISIN, maturity, coupon, par, credit tier), explicit commodity
  Gold/Silver spot/reference/proxy identities, explicit tradable-vs-reference
  semantics, and a fail-closed continuous-futures non-execution guard at both
  canonical resolution and Paper order-intent creation. IMP-XA-02 admitted the first bounded
  FRED rates reference vertical with point-in-time observation provenance and
  typed indicator-to-XA reference relationships (`src/market_platform_foundation/xa02`).
  IMP-XA-03 admitted the second bounded CFTC positioning vertical with
  source-neutral admission and typed market-report-to-XA relationships.
  IMP-XA-04 made the admitted-source and identity catalog durable with
  documented local-integration limitations.  IMP-XA-05 added ephemeral,
  reconstructable strategic state and regime inspection. G2 added the canonical
  multi-asset portfolio foundation (account/mode-scoped, instrument-keyed,
  per-currency cash, asset-aware valuation, explicit FX boundary — see the
  [G2 portfolio spec](../superpowers/specs/2026-09-07-imp-g2-canonical-multi-asset-portfolio-foundation.md),
  the single canonical architecture home for the portfolio contract). G12 added
  the canonical multi-asset runtime domain projection (`cross_lane/multi_asset_runtime.py`):
  one shared path from XA-01 identity through G7 observational lanes to G2/G4
  valuation and G3 fail-closed risk probes, with explicit `RuntimeDomainStatus`
  semantics (AVAILABLE/EMPTY/UNAVAILABLE/NOT_ENTITLED/DELAYED/STALE/INVALID/
  UNSUPPORTED_INSTRUMENT). IBKR L2/TRADES account-entitlement limits are
  isolated from software completeness; L1 live-path verification is separate
  from realtime entitlement. Cross-asset analytics, relationship intelligence
  engines, and additional admitted reference verticals remain future work.
- **Narrative/Motive — `PARTIAL`.** Existing events, participants, hypotheses,
  bounded narrative features, and contradiction flags are reusable. The
  uncertain motive/thesis method and admitted runtime remain future work under
  `IMP-NARRATIVE-01`.
- **AI/Agents — `PARTIAL`.** A read-only assistant and versioned fixture outputs
  exist. Universal run attribution, prompt/tool provenance, evaluation, and
  approval lifecycle are missing; `IMP-AI-01` is read-only first.

A canonical instrument identity may participate in multiple analytical domains
without being duplicated into disconnected identities. Gold, for example, may
participate in commodity analysis and monetary/reserve analysis. `IMP-XA-01`
defines extension requirements; REBASE-01 does not implement an identity schema
or universal ontology.

Future Japan/rates/FX work may relate JPY, JGBs, BOJ actions, intervention,
reserve activity, Treasury holdings, cross-border flows, and hedging costs. The
architecture must preserve competing causal hypotheses rather than encode a
predetermined causal chain.

## Time-scoped authority

The current architecture cannot rewrite what BUILD35 historically accepted.
BUILD35's immutable acceptance cannot override current architecture merely
because it is historical. Current behavior, current explanation, historical
evidence, and future design each control only their subject and time scope.
